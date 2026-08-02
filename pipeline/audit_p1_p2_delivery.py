"""Read-only final coverage and invariant audit for the P1/P2 delivery."""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime,timezone
from config.settings import BASE_DIR,SUPABASE_URL,supabase

def main()->None:
 brands={r["slug"]:r["id"] for r in (supabase.table("brands").select("id,slug").execute().data or [])}; cats={r["slug_en"]:r["id"] for r in (supabase.table("categories").select("id,slug_en").execute().data or [])}; bid=brands["samsung"]
 ecs=supabase.table("error_codes").select("id,category_id").eq("brand_id",bid).execute().data or []; ecids=[r["id"] for r in ecs]; arts=supabase.table("articles").select("id,error_code_id,fault_id,status,article_type").execute().data or []; byec={r["error_code_id"]:r for r in arts if r.get("error_code_id")}; missing=[r for r in ecs if r["id"] not in byec]
 p2faults=supabase.table("faults").select("id,category_id,slug,canonical_name").eq("brand_id",bid).in_("category_id",[cats["dishwashers"],cats["dryers"]]).execute().data or []; fids=[r["id"] for r in p2faults]; farts=[r for r in arts if r.get("fault_id") in fids]; aids=[r["id"] for r in farts]; tr=supabase.table("article_translations").select("article_id,locale,translation_status,slug").in_("article_id",aids).execute().data or []; ft=supabase.table("fault_translations").select("fault_id,locale").in_("fault_id",fids).execute().data or []; maps=supabase.table("fault_error_code_map").select("fault_id,error_code_id").in_("fault_id",fids).execute().data or []
 dup=[k for k,v in Counter((r["category_id"],r["slug"]) for r in p2faults).items() if v>1]
 statuses=Counter(f'{r["locale"]}:{r["translation_status"]}' for r in tr)
 report={"generated_at":datetime.now(timezone.utc).isoformat(),"host":SUPABASE_URL,"p1":{"samsung_error_codes":len(ecs),"with_articles":len(ecids)-len(missing),"missing_articles":len(missing),"missing_by_category":dict(Counter(next(k for k,v in cats.items() if v==r["category_id"]) for r in missing))},"p2":{"faults":len(p2faults),"fault_articles":len(farts),"fault_translations":len(ft),"article_translations":len(tr),"approved_mappings":len(maps),"translation_statuses":dict(statuses),"duplicate_slugs":dup,"orphan_fault_ids":[i for i in fids if i not in {r["fault_id"] for r in farts}]}}
 p=BASE_DIR/"data/p1-p2-final-coverage.json"; p.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
