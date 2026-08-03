"""Idempotent, filterable P1 article creator. Dry-run unless --apply."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from config.settings import BASE_DIR, SUPABASE_URL, supabase

RETIRED="jqepafrexisjmzoefvpr.supabase.co"
REQUIRED=("title_tag","meta_description","h1","description","quick_fix","intro_html","causes_json","symptoms_json","steps_json","affected_models_json","when_to_call_technician_html","prevention_html","faq_json","parts_json","slug","translation_status","source_locale","translated_by")

def validate(v:dict,loc:str)->None:
    if any(k not in v for k in REQUIRED): raise RuntimeError(f"{loc}: missing field")
    for k,keys,lo,hi in (("causes_json",{"cause","detail"},4,6),("steps_json",{"step","action","detail"},5,7),("faq_json",{"question","answer"},4,5)):
        if not isinstance(v[k],list) or not lo<=len(v[k])<=hi or any(set(x)!=keys for x in v[k]): raise RuntimeError(f"{loc}: invalid {k}")
    if len(v["title_tag"])>70 or len(v["meta_description"])>165: raise RuntimeError(f"{loc}: SEO length")
    if v["parts_json"]!=[]: raise RuntimeError(f"{loc}: unverified parts")

def main()->None:
    p=argparse.ArgumentParser(); p.add_argument("proposal",type=Path); p.add_argument("--apply",action="store_true"); p.add_argument("--brand",default="samsung"); p.add_argument("--category"); p.add_argument("--error-code-ids",nargs="*",type=int); p.add_argument("--batch-size",type=int); a=p.parse_args()
    if RETIRED in SUPABASE_URL: raise RuntimeError("retired Supabase Cloud blocked")
    doc=json.loads(a.proposal.read_text(encoding="utf-8")); entries={int(k):v for k,v in doc["entries"].items()}; ids=sorted(entries)
    if a.error_code_ids: ids=[i for i in ids if i in set(a.error_code_ids)]
    ids=[i for i in ids if entries[i]["brand"]==a.brand and (not a.category or entries[i]["category"]==a.category)]
    if a.batch_size: ids=ids[:a.batch_size]
    if not ids: raise RuntimeError("no selected entries")
    existing=supabase.table("articles").select("id,error_code_id").in_("error_code_id",ids).execute().data or []; existing_by={r["error_code_id"]:r["id"] for r in existing}
    report=[]
    for i in ids:
        e=entries[i]
        if e["classification"]!="A": raise RuntimeError(f"{i}: blocked classification")
        for loc in ("en","sv"): validate(e[loc],f"{i}/{loc}")
        if e["en"]["translation_status"]!="published" or e["sv"]["translation_status"]!="pending": raise RuntimeError(f"{i}: language status")
        for loc in ("en","sv"):
            collision=supabase.table("article_translations").select("article_id").eq("locale",loc).eq("slug",e[loc]["slug"]).execute().data or []
            if collision and existing_by.get(i) not in {r["article_id"] for r in collision}: raise RuntimeError(f"{i}/{loc}: slug collision")
        report.append({"error_code_id":i,"code":e["code"],"category":e["category"],"operation":"skip_existing" if i in existing_by else "create","en_slug":e["en"]["slug"],"sv_slug":e["sv"]["slug"],"source":e["source"]})
    print(json.dumps({"mode":"apply" if a.apply else "dry-run","host":SUPABASE_URL,"selected":len(ids),"operations":report},ensure_ascii=False,indent=2))
    if not a.apply:return
    stamp=datetime.now(timezone.utc); backup={"exported_at":stamp.isoformat(),"host":SUPABASE_URL,"batch":doc["batch"],"selection":ids,"existing_articles":existing}; d=BASE_DIR/"data/backups/p1"; d.mkdir(parents=True,exist_ok=True); bp=d/f'{doc["batch"]}-before-{stamp.strftime("%Y%m%dT%H%M%SZ")}.json'; bp.write_text(json.dumps(backup,ensure_ascii=False,indent=2),encoding="utf-8"); print(f"backup={bp}")
    created=[]
    try:
        for i in ids:
            if i in existing_by: continue
            ar=(supabase.table("articles").insert({"error_code_id":i,"status":"published","article_type":"error_code","review_flag":False}).execute().data or [])
            if len(ar)!=1: raise RuntimeError(f"{i}: article insert")
            aid=ar[0]["id"]; created.append(aid)
            for loc in ("en","sv"):
                v=entries[i][loc]; row={"article_id":aid,"locale":loc,**{k:v[k] for k in REQUIRED},"last_updated":stamp.isoformat()}; ins=supabase.table("article_translations").insert(row).execute().data or []
                if len(ins)!=1: raise RuntimeError(f"{i}/{loc}: translation insert")
            check=supabase.table("article_translations").select("locale,slug,translation_status,source_locale").eq("article_id",aid).execute().data or []
            if {(r["locale"],r["translation_status"]) for r in check}!={("en","published"),("sv","pending")}: raise RuntimeError(f"{i}: readback")
        print(json.dumps({"status":"verified","created_article_ids":created,"skipped_error_code_ids":[i for i in ids if i in existing_by]},ensure_ascii=False))
    except Exception:
        if created: supabase.table("articles").delete().in_("id",created).execute()
        raise
if __name__=="__main__": main()
