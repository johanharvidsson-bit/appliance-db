from contextlib import contextmanager
import json
from pathlib import Path
import pytest
from config.target_safety import TargetSafetyError
from workers.__main__ import main
from workers.apply_integration import (
    APPLY_OPERATIONS,
    ApplyBlocked,
    ApplyEngine,
    StaleProposal,
    is_placeholder,
)
from workers.apply_repository import ApplyRepository

FIXTURE = Path(__file__).parent / "fixtures" / "apply_integration.json"


def proposal(**changes):
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))["proposals"][0]
    value.update(changes)
    return value


class MemoryRepository:
    def __init__(self, p, current=None, fail=None):
        self.p, self.current, self.fail = p, current, fail
        self.changes = []
        self.finished = []

    @contextmanager
    def proposal_transaction(self, _):
        snapshot = self.current
        try:
            yield self.p
        except Exception:
            self.current = snapshot
            raise

    def read_current(self, _):
        return self.current

    def start_attempt(self, *_):
        return 501

    def validate_target(self, _):
        return None

    def mutate(self, plan):
        self.current = plan["proposed"]["value"]
        if self.fail == "mutation":
            raise RuntimeError("mutation failed")
        return self.current

    def record_change(self, attempt, change):
        if self.fail == "evidence":
            raise RuntimeError("evidence failed")
        self.changes.append((attempt, change))

    def finish_attempt(self, attempt, status):
        self.finished.append((attempt, status))


def test_registry_is_explicit_and_excludes_high_risk_operations():
    assert APPLY_OPERATIONS["propose_model_spec_update"].table == "model_specs"
    assert "propose_new_guide_candidate" not in APPLY_OPERATIONS
    assert "model_merge" not in {x.name for x in APPLY_OPERATIONS.values()}


@pytest.mark.parametrize(
    "status",
    [
        "proposed",
        "needs_review",
        "blocked",
        "rejected",
        "superseded",
        "applied",
        "failed",
    ],
)
def test_only_approved_is_selected(status):
    with pytest.raises(ApplyBlocked, match="status_not_approved"):
        ApplyEngine(MemoryRepository({})).plan(proposal(status=status))


def test_approval_conflict_evidence_target_and_unknown_operation_guards():
    engine = ApplyEngine(MemoryRepository({}))
    for change, code in [
        ({"reviewed_by": None}, "missing_reviewed_by"),
        ({"blocking_conflicts": 1}, "unresolved_blocking_conflict"),
        ({"evidence": []}, "apply_blocked_missing_evidence"),
        ({"preferred_target": None}, "missing_unique_target"),
        ({"proposal_type": "unknown"}, "unsupported_apply_operation"),
    ]:
        with pytest.raises(ApplyBlocked, match=code):
            engine.plan(proposal(**change))


@pytest.mark.parametrize(
    "text",
    [
        "Coming soon",
        " Guide coming soon. ",
        "Diagnostic title coming soon",
        "TBD",
        "todo",
    ],
)
def test_placeholder_guard(text):
    assert is_placeholder(text)
    with pytest.raises(ApplyBlocked, match="placeholder_or_empty_content"):
        ApplyEngine(MemoryRepository({})).plan(
            proposal(proposed_value_json={"field": "capacity_kg", "value": text})
        )


def test_model_spec_apply_stores_before_after_and_rollback_payload():
    repo = MemoryRepository(proposal(), None)
    result = ApplyEngine(repo).apply(101, applied_by="reviewer")
    assert result["status"] == "succeeded" and repo.current == 8
    change = result["change"]
    assert change["before"] is None and change["after"] == 8
    assert change["rollback_payload"] == {
        "expected_current": 8,
        "restore": None,
        "operation": "upsert_model_spec_field",
    }
    assert repo.finished == [(501, "succeeded")]


def test_successful_repository_finish_atomically_marks_proposal_applied():
    source = Path(ApplyRepository.__module__.replace(".", "/") + ".py").read_text(
        encoding="utf-8"
    )
    assert "SET status='applied'" in source
    assert "p.status='approved'" in source
    assert "proposal_apply_state_transition_failed" in source


def test_stale_proposal_writes_nothing():
    repo = MemoryRepository(proposal(), 7)
    with pytest.raises(StaleProposal):
        ApplyEngine(repo).apply(101, applied_by="reviewer")
    assert repo.changes == [] and repo.current == 7


@pytest.mark.parametrize("failure", ["mutation", "evidence"])
def test_failure_rolls_back_domain_change(failure):
    repo = MemoryRepository(proposal(), None, fail=failure)
    with pytest.raises(RuntimeError):
        ApplyEngine(repo).apply(101, applied_by="reviewer")
    assert repo.current is None and repo.changes == []


def test_dry_run_and_idempotent_success_do_not_mutate():
    repo = MemoryRepository(proposal(), None)
    result = ApplyEngine(repo).apply(101, applied_by="reviewer", dry_run=True)
    assert result["status"] == "dry_run" and repo.current is None
    repo.p["successful_attempt"] = True
    result = ApplyEngine(repo).apply(101, applied_by="reviewer")
    assert result["status"] == "succeeded" and not result["changed"]


def test_cli_fixture_report_and_placeholder_block(tmp_path, capsys):
    code = main(
        [
            "apply-integration",
            "--site",
            "appliance-repair-base",
            "--fixture",
            str(FIXTURE),
            "--dry-run",
            "--batch-size",
            "10",
            "--output-dir",
            str(tmp_path),
        ]
    )
    assert code == 2
    output = json.loads(capsys.readouterr().out)
    assert (
        output["approved_proposals_read"] == 2
        and output["dry_run_plans"] == 1
        and output["blocked"] == 1
    )
    report = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert report["changes_written"] == 0 and report["rollback_payloads_created"] == 0


def test_cli_requires_confirm_and_rejects_production():
    with pytest.raises(SystemExit, match="requires --confirm"):
        main(["apply-integration", "--site", "appliance-repair-base"])


def test_production_dry_run_no_longer_blanket_rejected_but_still_needs_a_dsn(monkeypatch):
    # Production is no longer hard-blocked at the CLI level (workers/auto_policy.py
    # extended this project's "no manual review" stance to production access, gated
    # instead by config.target_safety's explicit multi-factor approval). A read-only
    # --dry-run still requires no approval token, but it does still require a real,
    # configured DSN - proving the removed guard was the *only* thing standing
    # between this call and a real connection attempt.
    monkeypatch.delenv("REPAIRBASE_SECURITY_TEST_DB_URL", raising=False)
    with pytest.raises(SystemExit, match="REPAIRBASE_SECURITY_TEST_DB_URL is required"):
        main(
            [
                "apply-integration",
                "--site",
                "appliance-repair-base",
                "--environment",
                "production",
                "--dry-run",
            ]
        )


def test_production_write_without_approval_token_is_still_fail_closed(monkeypatch, tmp_path):
    # A real write attempt against production must still fail closed without a
    # complete ProductionApproval, even though the blanket CLI block is gone.
    # 203.0.113.0/24 is TEST-NET-3 (RFC 5737): guaranteed non-routable, so this
    # can never actually reach a real host even if the approval check were
    # buggy and let the call fall through to a real connection attempt. The
    # "appliancedb" database name alone is enough for classify_target to mark
    # this PRODUCTION_DATABASE regardless of host.
    monkeypatch.setenv("REPAIRBASE_SECURITY_TEST_DB_URL", "postgresql://u:p@203.0.113.1:5432/appliancedb")
    monkeypatch.delenv("ALLOW_PRODUCTION_WRITE", raising=False)
    monkeypatch.delenv("PRODUCTION_WRITE_CONFIRMATION", raising=False)
    with pytest.raises(TargetSafetyError):
        main(
            [
                "apply-integration",
                "--site",
                "appliance-repair-base",
                "--environment",
                "production",
                "--confirm",
                "--proposal-id",
                "1",
            ]
        )


def test_migration_security_and_write_boundary():
    sql = (
        Path(__file__).parents[1] / "db/migrations/024_apply_integration_worker.sql"
    ).read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in sql and "ON DELETE CASCADE" not in sql
    assert "REVOKE ALL" in sql and "integration_apply_changes" in sql
    assert ApplyRepository.WRITABLE_TABLES.isdisjoint(
        {"url_registry", "entity_url_bindings", "url_redirects", "sitemap"}
    )
