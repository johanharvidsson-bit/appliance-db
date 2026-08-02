"""Idempotent P2 cluster writer with dry-run, backup and rollback."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from config.settings import BASE_DIR,SUPABASE_URL,supabase

def main()->None:
 p=argparse.ArgumentParser(); p.add_argument("proposal",type=Path); p.add_argument("--apply",action="store_true"); p.add_argument("--brand",default="samsung"); p.add_argument("--category"); a=p.parse_args()
 if "jqepafrexisjmzoefvpr.supabase.co" in SUPABASE_URL: raise RuntimeError("retired cloud blocked")
 d=json.loads(a.proposal.read_text(encoding="utf-8")); brand=supabase.table("brands").select("id").eq("slug",a.brand).single().execute().data; cats={r["slug_en"]:r["id"] for r in (supabase.table("categories").select("id,slug_en").execute().data or [])}; clusters=[x for x in d["clusters"] if not a.category or x["category"]==a.category]
 ops=[]
 for x in clusters:
  cid=cats[x["category"]]; old=supabase.table("faults").select("id").eq("brand_id",brand["id"]).eq("category_id",cid).eq("slug",x["slug"]).execute().data or []; ops.append({"category":x["category"],"slug":x["slug"],"operation":"skip_existing" if old else "create","mappings":len(x["mappings"])})
  for loc in ("en","sv"):
   v=x["article"][loc]
   if not 4<=len(v["causes_json"])<=6 or not 5<=len(v["steps_json"])<=7 or not 4<=len(v["faq_json"])<=5 or v["parts_json"]!=[]: raise RuntimeError(f'{x["slug"]}/{loc}: invalid article')
 print(json.dumps({"mode":"apply" if a.apply else "dry-run","host":SUPABASE_URL,"clusters":len(clusters),"operations":ops},ensure_ascii=False,indent=2));
 if not a.apply:return
 stamp=datetime.now(timezone.utc); bd=BASE_DIR/"data/backups/p2"; bd.mkdir(parents=True,exist_ok=True); bp=bd/f'{d["batch"]}-before-{stamp.strftime("%Y%m%dT%H%M%SZ")}.json'; existing=supabase.table("faults").select("*").eq("brand_id",brand["id"]).in_("category_id",list({cats[x["category"]] for x in clusters})).execute().data or []; bp.write_text(json.dumps({"exported_at":stamp.isoformat(),"host":SUPABASE_URL,"existing_faults":existing},ensure_ascii=False,indent=2),encoding="utf-8"); print(f"backup={bp}")
 created=[]
 try:
  for x in clusters:
   cid=cats[x["category"]]; old=supabase.table("faults").select("id").eq("brand_id",brand["id"]).eq("category_id",cid).eq("slug",x["slug"]).execute().data or []
   if old: continue
   f=(supabase.table("faults").insert({"brand_id":brand["id"],"category_id":cid,"slug":x["slug"],"canonical_name":x["canonical_name"],"severity":x["severity"],"has_error_code":x["has_error_code"]}).execute().data or [])[0]; fid=f["id"]; created.append(fid)
   supabase.table("fault_translations").insert([{"fault_id":fid,"locale":loc,**x["fault_translations"][loc]} for loc in ("en","sv")]).execute()
   ar=(supabase.table("articles").insert({"fault_id":fid,"status":"published","article_type":"fault"}).execute().data or [])[0]; aid=ar["id"]
   rows=[]
   for loc in ("en","sv"): rows.append({"article_id":aid,"locale":loc,**x["article"][loc],"last_updated":stamp.isoformat()})
   supabase.table("article_translations").insert(rows).execute()
   if x["mappings"]: supabase.table("fault_error_code_map").insert([{"fault_id":fid,"error_code_id":m["error_code_id"]} for m in x["mappings"]]).execute()
  fids=[r["id"] for r in (supabase.table("faults").select("id").eq("brand_id",brand["id"]).in_("category_id",list({cats[x["category"]] for x in clusters})).execute().data or [])]; ats=supabase.table("articles").select("id,fault_id").in_("fault_id",fids).execute().data or []; aids=[r["id"] for r in ats]; trs=supabase.table("article_translations").select("article_id,locale,translation_status").in_("article_id",aids).execute().data or []; print(json.dumps({"status":"verified","created_fault_ids":created,"faults_in_scope":len(fids),"article_translations":len(trs)},ensure_ascii=False))
 except Exception:
  if created:supabase.table("faults").delete().in_("id",created).execute()
  raise
if __name__=="__main__":main()
