"""
pipeline/health_check.py

Daily health check for the VPS-hosted stack. Catches the class of failure
that ran silently for 3 days undetected (2026-07-27 to 2026-07-30): a hard
Anthropic API cap that got swallowed as "0 codes found" instead of surfacing
anywhere. Writes a plain-text status summary to STATUS.md so it's a single
file to glance at, and exits non-zero with a clear message on any check
failure so it shows up in the cron log / any future alerting hook.

Checks:
  1. PostgREST API reachable
  2. error_codes count grew in the last 24h (proxy for "extraction is
     actually making progress", not just "the process didn't crash")
  3. Known failure signatures in last night's cron log (usage limit, credit
     balance, connection refused) — the things that have already bitten us
  4. Disk space on the VPS

Usage:
    python -m pipeline.health_check
"""

import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from config.settings import supabase

STATUS_FILE = "STATUS.md"
CRON_LOG = "logs/overnight_cron.log"

KNOWN_FAILURE_PATTERNS = [
    (r"usage limit", "Anthropic API usage cap hit"),
    (r"credit balance is too low", "Anthropic API credits exhausted"),
    (r"Connection refused", "A service (DB/API) was unreachable"),
    (r"rate_limit", "Rate limited (should self-recover, but check if persistent)"),
]


def check_api() -> tuple[bool, str]:
    try:
        r = supabase.table("brands").select("id", count="exact").limit(1).execute()
        return True, f"API reachable ({r.count} brands)"
    except Exception as e:
        return False, f"API unreachable: {e}"


def check_error_code_growth() -> tuple[bool, str]:
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        r = supabase.table("error_codes").select("id", count="exact").gte("created_at", cutoff).execute()
        new_count = r.count or 0
        if new_count == 0:
            return False, "0 new error codes in the last 24h (extraction may be stalled)"
        return True, f"{new_count} new error codes in the last 24h"
    except Exception as e:
        return False, f"Could not check error code growth: {e}"


def check_cron_log() -> tuple[bool, str]:
    try:
        with open(CRON_LOG, encoding="utf-8", errors="ignore") as f:
            # Only look at the tail — this log grows large fast when something
            # is looping on a failure, which is exactly what we want to catch.
            lines = f.readlines()[-5000:]
    except FileNotFoundError:
        return False, f"{CRON_LOG} not found"

    hits: dict[str, int] = {}
    for line in lines:
        for pattern, label in KNOWN_FAILURE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                hits[label] = hits.get(label, 0) + 1

    if not hits:
        return True, "No known failure patterns in recent log"
    summary = ", ".join(f"{label} ({count}x)" for label, count in hits.items())
    return False, f"Found: {summary}"


def check_disk_space() -> tuple[bool, str]:
    try:
        out = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=10).stdout
        lines = out.strip().splitlines()
        if len(lines) < 2:
            return False, "Could not parse df output"
        use_pct = int(lines[1].split()[4].rstrip("%"))
        if use_pct >= 90:
            return False, f"Disk {use_pct}% full — getting critical"
        return True, f"Disk {use_pct}% full"
    except Exception as e:
        return False, f"Could not check disk space: {e}"


def main() -> None:
    checks = [
        ("PostgREST API", check_api()),
        ("Error code growth (24h)", check_error_code_growth()),
        ("Cron log failure patterns", check_cron_log()),
        ("Disk space", check_disk_space()),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# Health check — {now}", ""]
    all_ok = True
    for name, (ok, detail) in checks:
        icon = "✅" if ok else "⚠️"
        lines.append(f"{icon} **{name}**: {detail}")
        all_ok = all_ok and ok

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines))

    if not all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
