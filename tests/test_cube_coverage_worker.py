import json
from pathlib import Path

from workers.__main__ import main
from workers.cube_coverage import CoverageEngine, stable_hash

FIXTURE = Path("tests/fixtures/cube_coverage.json")


def evaluate():
    return CoverageEngine().evaluate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_scope_cells_and_denominators_are_locale_specific():
    result = evaluate()
    assert result["cube_cells_scanned"] == 2
    metrics = {(m["locale"],m["name"]):m for m in result["metrics"]}
    assert metrics[("en","model_overview_coverage")]["denominator"] == 1
    assert metrics[("en","model_overview_coverage")]["numerator"] == 0
    assert metrics[("sv","model_specs_coverage")]["percentage"] == 0


def test_empty_cell_is_not_applicable_not_zero():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["models"] = []
    metric = CoverageEngine().evaluate(data)["metrics"][0]
    assert metric["availability"] == "not_applicable" and metric["percentage"] is None


def test_initial_catalogue_detects_concrete_defects_only():
    types = {x["finding_type"] for x in evaluate()["findings"]}
    assert {"missing_model_overview","missing_model_specs","unresolved_variant_candidate",
            "product_code_without_active_model_identity","error_code_placeholder_content",
            "error_code_missing_translation","fault_missing_translation","guide_missing_translation",
            "guide_missing_procedure","guide_without_topic","error_code_relation_conflict",
            "missing_source_evidence"} <= types


def test_finding_hash_and_priority_are_deterministic_and_conflicts_block():
    first, second = evaluate(), evaluate()
    assert [x["finding_hash"] for x in first["findings"]] == [x["finding_hash"] for x in second["findings"]]
    conflict = next(x for x in first["backlog"] if x["reason"]["rule"] == "error_code_relation_conflict")
    assert conflict["priority_band"] == "P0" and conflict["status"] == "blocked"
    assert stable_hash("x") == stable_hash("x")


def test_filters_isolate_locale_brand_category_and_finding_type():
    result = CoverageEngine().evaluate(json.loads(FIXTURE.read_text(encoding="utf-8")), filters={"locale":"sv","brand":"acme","category":"washers","finding_type":"missing_model_overview"})
    assert result["cube_cells_scanned"] == 1
    assert {(x["finding_type"],x["locale"]) for x in result["findings"]} == {("missing_model_overview","sv")}


def test_offline_cli_dry_run_writes_reports_only(tmp_path, capsys):
    assert main(["cube-coverage","--site","appliance-repair-base","--fixture",str(FIXTURE),"--output-dir",str(tmp_path)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["dry_run"] is True and output["findings"] > 0
    assert len(list(tmp_path.glob("*.json"))) == 1 and len(list(tmp_path.glob("*.md"))) == 1


def test_fixture_mode_ignores_environment():
    # Fixture mode never touches a database or network regardless of
    # --environment, so it is not blanket-rejected for production - only a
    # real, unapproved production *write* is (see config/target_safety.py).
    main(["cube-coverage","--site","x","--environment","production","--fixture",str(FIXTURE)])


def test_no_external_or_content_mutation_capabilities_are_imported():
    source = Path("workers/cube_coverage.py").read_text(encoding="utf-8") + Path("workers/cube_repository.py").read_text(encoding="utf-8")
    assert "requests" not in source and "httpx" not in source and "anthropic" not in source
    for table in ("brands","categories","models","error_codes","faults","guides","url_registry"):
        assert f"UPDATE {table}" not in source and f"INSERT INTO {table}" not in source


def test_migration_is_internal_and_history_preserving():
    sql = Path("db/migrations/020_cube_coverage_backlog_worker.sql").read_text(encoding="utf-8").lower()
    for table in ("cube_scope_snapshots","cube_coverage_observations","findings","content_backlog","worker_runs"):
        assert f"create table public.{table}" in sql
    assert "on delete cascade" not in sql
    assert "revoke all on public.%i from public,anon,authenticated" in sql
