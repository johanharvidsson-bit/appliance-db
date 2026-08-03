"""Deterministic, offline-first model/variant profiler for the bounded PR 3 pilot."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import unicodedata

import psycopg2
from psycopg2.extensions import connection as PgConnection

from config.target_safety import assert_safe_target


_SPACE_RE = re.compile(r"\s+")
_EXACT_SUFFIX_RE = re.compile(r"^([A-Z0-9][A-Z0-9 ._-]*?)/([A-Z0-9._-]{1,12})$")


def normalize_model_code(value: str) -> str:
    """Spec 0 code normalization: NFKC, trim, collapse whitespace, uppercase."""
    return _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", value).strip()).upper()


@dataclass(frozen=True)
class ModelRecord:
    id: int
    brand_id: int
    category_id: int
    name: str
    slug: str
    base_model: str | None = None


@dataclass(frozen=True)
class MappingCandidate:
    legacy_model_id: int
    candidate_model_id: int
    candidate_variant_code: str | None
    normalized_candidate_variant_code: str | None
    confidence: int
    mapping_reason: str


@dataclass(frozen=True)
class ProfileDecision:
    legacy_model_id: int
    canonical_model_id: int
    recommended_status: str
    review_classification: str
    confidence: int
    mapping_reason: str
    candidate_variant_code: str | None = None
    normalized_candidate_variant_code: str | None = None


@dataclass(frozen=True)
class ProfileReport:
    brand_id: int
    category_id: int
    records: int
    decisions: list[ProfileDecision]
    candidates: list[MappingCandidate]
    stop_gates: list[str]


def _family(record: ModelRecord) -> str:
    if record.base_model and normalize_model_code(record.base_model):
        return normalize_model_code(record.base_model)
    normalized = normalize_model_code(record.name)
    match = _EXACT_SUFFIX_RE.fullmatch(normalized)
    return match.group(1) if match else normalized


def profile_models(records: list[ModelRecord]) -> ProfileReport:
    if not records:
        raise ValueError("pilot scope contains no models")
    scopes = {(record.brand_id, record.category_id) for record in records}
    if len(scopes) != 1:
        raise ValueError("pilot input must contain exactly one brand/category scope")
    brand_id, category_id = next(iter(scopes))
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate legacy model id in pilot input")

    groups: dict[str, list[ModelRecord]] = {}
    for record in sorted(records, key=lambda item: item.id):
        groups.setdefault(_family(record), []).append(record)

    decisions: list[ProfileDecision] = []
    candidates: list[MappingCandidate] = []
    stop_gates: list[str] = []
    for family, group in sorted(groups.items()):
        exact_mains = [
            record
            for record in group
            if normalize_model_code(record.name) == family and "/" not in record.name
        ]
        if len(exact_mains) == 1:
            canonical = exact_mains[0]
            for record in group:
                if record.id == canonical.id:
                    decisions.append(
                        ProfileDecision(
                            record.id,
                            record.id,
                            "unchanged",
                            "retain_200",
                            100,
                            "unique exact main identity in bounded scope",
                        )
                    )
                    continue
                normalized_name = normalize_model_code(record.name)
                suffix_match = _EXACT_SUFFIX_RE.fullmatch(normalized_name)
                if suffix_match and suffix_match.group(1) == family:
                    variant = suffix_match.group(2)
                    decisions.append(
                        ProfileDecision(
                            record.id,
                            canonical.id,
                            "mapped_to_variant",
                            "retain_200_with_new_data_model",
                            100,
                            "exact slash-delimited regional/revision suffix",
                            variant,
                            normalize_model_code(variant),
                        )
                    )
                    candidates.append(
                        MappingCandidate(
                            record.id,
                            canonical.id,
                            variant,
                            normalize_model_code(variant),
                            100,
                            "exact slash-delimited regional/revision suffix",
                        )
                    )
                else:
                    decisions.append(
                        ProfileDecision(
                            record.id,
                            record.id,
                            "unchanged",
                            "manual_review",
                            0,
                            "shared family but no exact approved suffix rule",
                        )
                    )
                    candidates.append(
                        MappingCandidate(
                            record.id,
                            canonical.id,
                            None,
                            None,
                            50,
                            "same normalized family; manual review required",
                        )
                    )
            continue

        reason = "no exact main identity" if not exact_mains else "multiple plausible exact main identities"
        if len(group) > 1:
            stop_gates.append(f"family {family}: {reason}")
        for record in group:
            decisions.append(
                ProfileDecision(
                    record.id,
                    record.id,
                    "unchanged",
                    "manual_review" if len(group) > 1 else "retain_200",
                    0 if len(group) > 1 else 100,
                    reason if len(group) > 1 else "no safe group; preserve self identity",
                )
            )
            if len(group) > 1:
                for candidate in group:
                    if candidate.id != record.id:
                        candidates.append(
                            MappingCandidate(
                                record.id,
                                candidate.id,
                                None,
                                None,
                                25,
                                f"{reason}; non-authoritative alternative",
                            )
                        )

    decisions.sort(key=lambda item: item.legacy_model_id)
    candidates.sort(
        key=lambda item: (
            item.legacy_model_id,
            item.candidate_model_id,
            item.normalized_candidate_variant_code or "",
        )
    )
    if {decision.legacy_model_id for decision in decisions} != set(ids):
        raise RuntimeError("traceable identity stop gate: not every input has one decision")
    return ProfileReport(brand_id, category_id, len(records), decisions, candidates, stop_gates)


def load_records(path: Path) -> list[ModelRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("pilot input must be a JSON array")
    return [ModelRecord(**row) for row in payload]


def write_report(report: ProfileReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def persist_candidates(report: ProfileReport, *, dsn: str, environment: str) -> dict:
    if environment != "development":
        raise ValueError("PR 3 candidate persistence is restricted to development")
    assert_safe_target(dsn, app_env=environment, operation="write")
    connection = psycopg2.connect(dsn)
    try:
        return _persist_candidates(connection, report)
    finally:
        connection.close()


def _persist_candidates(connection: PgConnection, report: ProfileReport) -> dict:
    created_variant_ids: list[int] = []
    touched_variant_ids: list[int] = []
    created_candidate_ids: list[int] = []
    touched_candidate_ids: list[int] = []
    with connection:
        with connection.cursor() as cursor:
            for candidate in report.candidates:
                variant_id = None
                if candidate.normalized_candidate_variant_code:
                    cursor.execute(
                        "SELECT id FROM model_variants WHERE model_id=%s AND normalized_variant_code=%s",
                        (candidate.candidate_model_id, candidate.normalized_candidate_variant_code),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        variant_id = existing[0]
                        touched_variant_ids.append(variant_id)
                    else:
                        cursor.execute(
                            "INSERT INTO model_variants(model_id,variant_code,normalized_variant_code,status) "
                            "VALUES(%s,%s,%s,'candidate') RETURNING id",
                            (
                                candidate.candidate_model_id,
                                candidate.candidate_variant_code,
                                candidate.normalized_candidate_variant_code,
                            ),
                        )
                        variant_id = cursor.fetchone()[0]
                        created_variant_ids.append(variant_id)
                cursor.execute(
                    "SELECT id,candidate_status FROM legacy_model_mapping_candidates "
                    "WHERE legacy_model_id=%s AND candidate_model_id=%s "
                    "AND normalized_candidate_variant_code IS NOT DISTINCT FROM %s",
                    (
                        candidate.legacy_model_id,
                        candidate.candidate_model_id,
                        candidate.normalized_candidate_variant_code,
                    ),
                )
                existing_candidate = cursor.fetchone()
                if existing_candidate:
                    touched_candidate_ids.append(existing_candidate[0])
                    if existing_candidate[1] == "candidate":
                        cursor.execute(
                            "UPDATE legacy_model_mapping_candidates SET candidate_variant_code=%s,confidence=%s,mapping_reason=%s "
                            "WHERE id=%s",
                            (
                                candidate.candidate_variant_code,
                                candidate.confidence,
                                candidate.mapping_reason,
                                existing_candidate[0],
                            ),
                        )
                else:
                    cursor.execute(
                        "INSERT INTO legacy_model_mapping_candidates(" 
                        "legacy_model_id,candidate_model_id,candidate_variant_code,"
                        "normalized_candidate_variant_code,candidate_status,confidence,mapping_reason) "
                        "VALUES(%s,%s,%s,%s,'candidate',%s,%s) RETURNING id",
                        (
                            candidate.legacy_model_id,
                            candidate.candidate_model_id,
                            candidate.candidate_variant_code,
                            candidate.normalized_candidate_variant_code,
                            candidate.confidence,
                            candidate.mapping_reason,
                        ),
                    )
                    created_candidate_ids.append(cursor.fetchone()[0])
    return {
        "created_variant_ids": created_variant_ids,
        "touched_variant_ids": sorted(set(touched_variant_ids)),
        "created_candidate_ids": created_candidate_ids,
        "touched_candidate_ids": sorted(set(touched_candidate_ids)),
        "authoritative_mappings_written": 0,
        "rollback": {
            "delete_candidate_ids": created_candidate_ids,
            "delete_variant_ids_after_candidates": created_variant_ids,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="deterministic bounded model/variant pilot")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", default="development")
    parser.add_argument("--persist-candidates", action="store_true")
    parser.add_argument("--database-url-env", default="REPAIRBASE_MODEL_PROFILE_DB_URL")
    parser.add_argument("--rollback-output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = profile_models(load_records(args.input))
    write_report(report, args.output)
    persistence = None
    if args.persist_candidates:
        dsn = os.getenv(args.database_url_env, "").strip()
        if not dsn:
            raise RuntimeError(f"missing database URL environment variable: {args.database_url_env}")
        persistence = persist_candidates(report, dsn=dsn, environment=args.environment)
        rollback_output = args.rollback_output or args.output.with_suffix(".rollback.json")
        rollback_output.write_text(json.dumps(persistence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records": report.records, "candidates": len(report.candidates), "stop_gates": len(report.stop_gates), "persisted": persistence is not None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
