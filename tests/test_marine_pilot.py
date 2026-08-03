from pathlib import Path

ROOT = Path(__file__).parents[1] / "pilots/marine"

def test_pilot_is_isolated_and_secret_free():
    compose = (ROOT / "compose.dev.yml").read_text()
    example = (ROOT / ".env.example").read_text()
    assert "marine_repair_dev" in compose
    assert "PGRST_DB_SCHEMAS: api_public" in compose
    assert "127.0.0.1:" in compose
    assert "repairbase_marine_dev_db" in compose
    assert "appliance" not in compose.lower()
    bootstrap = (ROOT / "000_roles.sh").read_text()
    assert "CREATE ROLE anon NOLOGIN" in bootstrap
    assert "CREATE ROLE authenticated NOLOGIN" in bootstrap
    assert "CREATE ROLE marine_postgrest LOGIN PASSWORD" in bootstrap
    assert "GRANT anon TO marine_postgrest" in bootstrap
    for line in example.splitlines():
        if "PASSWORD=" in line or "URI=" in line or "SECRET=" in line:
            assert line.endswith("=")

def test_seed_scope_is_three_five_fifty():
    seed = (ROOT / "seed.sql").read_text()
    assert all(category in seed for category in ("outboard-engines", "inboard-engines", "sterndrives"))
    assert all(brand in seed for brand in ("mercury", "yamaha-marine", "volvo-penta", "suzuki-marine", "honda-marine"))
    assert "generate_series(1,50)" in seed
    assert "scrape" not in seed.lower()
