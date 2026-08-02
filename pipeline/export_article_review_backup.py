"""Export an exact, read-only production backup for an article-review batch."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from config.settings import BASE_DIR, SUPABASE_URL
from pipeline.apply_article_review_batch import read


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch")
    parser.add_argument("article_ids", nargs="+", type=int)
    args = parser.parse_args()
    if "jqepafrexisjmzoefvpr.supabase.co" in SUPABASE_URL:
        raise RuntimeError("retired cloud blocked")
    article_ids = sorted(set(args.article_ids))
    exported_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "exported_at": exported_at,
        "source": "production-vps-read-only",
        "article_ids": article_ids,
        "rows": read(article_ids),
    }
    path: Path = (
        BASE_DIR
        / "data/backups/article_reviews"
        / f"batch-{args.batch}-before.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(path), "articles": len(article_ids), "rows": len(payload["rows"])}))


if __name__ == "__main__":
    main()
