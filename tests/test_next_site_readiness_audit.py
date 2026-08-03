import os
from pathlib import Path

import pytest

from pipeline.audit_next_site_readiness import audit


def test_readiness_audit_passes_on_isolated_platform():
    dsn = os.getenv("REPAIRBASE_SECURITY_TEST_DB_URL")
    if not dsn:
        pytest.skip("explicit dev integration DSN not set")
    result = audit(dsn, Path("site_templates/example-next-site.json"))
    assert result["ready"], result
    assert len(result["checks"]) >= 9
    assert all(check["passed"] for check in result["checks"])

