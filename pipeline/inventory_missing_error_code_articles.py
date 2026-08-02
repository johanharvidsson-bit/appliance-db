"""Read-only Priority 1 inventory for error codes and article-language coverage."""
from __future__ import annotations

import argparse, csv, json, re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from config.settings import SUPABASE_URL, supabase

RETIRED = "jqepafrexisjmzoefvpr.supabase.co"
SUSPECT = re.compile(r"^(TYPE\s*\d+|MODEL|ERROR|CODE|N/?A|UNKNOWN|\?+)$", re.I)

def classify(row: dict) -> tuple[str, list[str]]:
    blockers=[]; code=(row.get("code") or "").strip(); source=(row.get("source") or "").lower()
    if not code or SUSPECT.match(code) or len(code)>20: blockers.append("suspect_code_shape")
    if not row.get("short_description") or not row.get("description"): blockers.append("missing_description")
    if row.get("scrape_status") not in {"enriched","verified","complete"}: blockers.append("not_verified")
    if "samsung.com" not in source: blockers.append("no_official_samsung_source")
    if "suspect_code_shape" in blockers: return "C", blockers
    if blockers: return "B", blockers
    return "A", []

def inventory()->dict:
    if RETIRED in SUPABASE_URL: raise RuntimeError("Refusing retired Supabase Cloud")
    brands={r["id"]:r for r in (supabase.table("brands").select("id,name,slug").execute().data or [])}
    cats={r["id"]:r for r in (supabase.table("categories").select("id,slug_en").execute().data or [])}
    codes=supabase.table("error_codes").select("id,code,brand_id,category_id,short_description,description,severity,diy_possible,source,last_verified_at,scrape_status").order("id").execute().data or []
    articles=supabase.table("articles").select("id,error_code_id,status").not_.is_("error_code_id","null").execute().data or []
    by_ec={r["error_code_id"]:r for r in articles}; aids=[r["id"] for r in articles]
    trans=supabase.table("article_translations").select("article_id,locale,translation_status").in_("article_id",aids).execute().data if aids else []
    locales={};
    for r in trans or []: locales.setdefault(r["article_id"],set()).add(r["locale"])
    links=supabase.table("error_code_product_codes").select("error_code_id,product_code_id").execute().data or []
    counts=Counter(r["error_code_id"] for r in links)
    rows=[]
    for ec in codes:
        brand=brands.get(ec["brand_id"]); cat=cats.get(ec["category_id"]); article=by_ec.get(ec["id"]); ls=locales.get(article["id"],set()) if article else set()
        if article and {"en","sv"}.issubset(ls): continue
        row={**ec,"brand":brand["name"] if brand else None,"brand_slug":brand["slug"] if brand else None,"category":cat["slug_en"] if cat else None,"category_slug":cat["slug_en"] if cat else None,"linked_product_codes":counts[ec["id"]],"article_exists":bool(article),"article_id":article["id"] if article else None,"en_exists":"en" in ls,"sv_exists":"sv" in ls}
        grade, blockers=classify(row); row["classification"]=grade; row["recommended_action"]={"A":"create_or_complete_article","B":"fact_review","C":"exclude_and_investigate"}[grade]; row["blocking_issues"]=blockers
        rows.append(row)
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"source_host":SUPABASE_URL,"read_only":True,"candidate_count":len(rows),"classification_counts":dict(Counter(r["classification"] for r in rows)),"group_counts":dict(Counter(f'{r["brand_slug"]}/{r["category_slug"]}' for r in rows)),"rows":rows}

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("--json",type=Path,required=True); p.add_argument("--csv",type=Path,required=True); a=p.parse_args(); report=inventory(); a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    cols=["id","code","brand","category","short_description","description","severity","diy_possible","source","last_verified_at","scrape_status","linked_product_codes","article_exists","en_exists","sv_exists","classification","recommended_action","blocking_issues"]
    with a.csv.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader();
        for r in report["rows"]: w.writerow({k:";".join(r[k]) if k=="blocking_issues" else r.get(k) for k in cols})
    print(json.dumps({k:report[k] for k in ("source_host","candidate_count","classification_counts","group_counts")},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
