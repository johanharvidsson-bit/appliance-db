"""Run content-policy flags against every locale in a review proposal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.audit_article_priority0 import _translation_flags


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--forbid", action="append", default=[])
    args = parser.parse_args()
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    results = []
    for article_id in proposal["article_ids"]:
        for locale in ("en", "sv"):
            flags = _translation_flags(proposal["translations"][str(article_id)][locale])
            results.append({"article_id": article_id, "locale": locale, "flags": flags})
    text = json.dumps(proposal, ensure_ascii=False)
    forbidden = [token for token in ("SPARE_PARTS", *args.forbid) if token in text]
    print(json.dumps({"rows": results, "forbidden": forbidden}, ensure_ascii=False))
    if any(row["flags"] for row in results) or forbidden:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
