"""Verify translation and article invariants after a batch update."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from config.settings import supabase
from pipeline.apply_article_review_batch import FIELDS, read


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal", type=Path)
    parser.add_argument("before", type=Path)
    args = parser.parse_args()
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    before_doc = json.loads(args.before.read_text(encoding="utf-8"))
    ids = sorted(map(int, proposal["article_ids"]))
    before = {(row["article_id"], row["locale"]): row for row in before_doc["rows"]}
    after_rows = read(ids)
    after = {(row["article_id"], row["locale"]): row for row in after_rows}
    for article_id in ids:
        for locale in ("en", "sv"):
            old = before[(article_id, locale)]
            new = after[(article_id, locale)]
            expected = proposal["translations"][str(article_id)][locale]
            for field in FIELDS:
                if new[field] != expected[field]:
                    raise RuntimeError(f"{article_id}/{locale}: {field} read-back mismatch")
            for field in ("slug", "affected_models_json", "translation_status", "source_locale"):
                if new[field] != old[field]:
                    raise RuntimeError(f"{article_id}/{locale}: {field} changed")
            expected_status = "published" if locale == "en" else "pending"
            if new["translation_status"] != expected_status:
                raise RuntimeError(f"{article_id}/{locale}: unexpected translation status")
            if new["parts_json"] != []:
                raise RuntimeError(f"{article_id}/{locale}: parts_json not empty")
    articles = (
        supabase.table("articles")
        .select("id,error_code_id,fault_id,status,article_type")
        .in_("id", ids)
        .order("id")
        .execute()
        .data
        or []
    )
    if len(articles) != len(ids):
        raise RuntimeError("unexpected article row count")
    for row in articles:
        if row["status"] != "published":
            raise RuntimeError(f"{row['id']}: article not published")
        is_code = row["article_type"] == "error_code"
        if is_code != bool(row["error_code_id"]) or is_code == bool(row["fault_id"]):
            raise RuntimeError(f"{row['id']}: invalid article relation")
    print(json.dumps({"status": "invariants-verified", "articles": len(ids), "rows": len(after_rows), "ids": ids}))


if __name__ == "__main__":
    main()
