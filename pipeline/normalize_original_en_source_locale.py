"""Normalize EN source_locale for the original reviewed article population."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from config.settings import BASE_DIR,SUPABASE_URL,supabase

def ids_from_proposals()->list[int]:
 ids=set()
 for p in (BASE_DIR/"data/article_reviews").glob("batch-*-proposal.json"):
  ids.update(map(int,json.loads(p.read_text(encoding="utf-8"))["article_ids"]))
 return sorted(ids)

def main()->None:
 p=argparse.ArgumentParser();p.add_argument("--apply",action="store_true");a=p.parse_args()
 if "jqepafrexisjmzoefvpr.supabase.co" in SUPABASE_URL:raise RuntimeError("retired cloud blocked")
 ids=ids_from_proposals();
 if len(ids)!=259:raise RuntimeError(f"expected 259 ids, got {len(ids)}")
 rows=[]
 for i in range(0,len(ids),100):rows.extend(supabase.table("article_translations").select("article_id,locale,source_locale,translation_status,slug,affected_models_json,last_updated").in_("article_id",ids[i:i+100]).in_("locale",["en","sv"]).execute().data or [])
 changes=[r for r in rows if r["locale"]=="en" and r.get("source_locale")!="en"]
 sv_bad=[r for r in rows if r["locale"]=="sv" and r.get("source_locale")!="en"]
 print(json.dumps({"mode":"apply" if a.apply else "dry-run","host":SUPABASE_URL,"population":len(ids),"rows":len(rows),"en_changes":len(changes),"sv_invalid":len(sv_bad)}))
 if sv_bad:raise RuntimeError("SV source_locale invariant failed")
 if not a.apply:return
 stamp=datetime.now(timezone.utc);d=BASE_DIR/"data/backups/article_reviews";bp=d/f'original-259-source-locale-before-{stamp.strftime("%Y%m%dT%H%M%SZ")}.json';bp.write_text(json.dumps({"exported_at":stamp.isoformat(),"host":SUPABASE_URL,"rows":rows},ensure_ascii=False,indent=2),encoding="utf-8");print(f"backup={bp}")
 for i in range(0,len(changes),100):
  part=[r["article_id"] for r in changes[i:i+100]];supabase.table("article_translations").update({"source_locale":"en","last_updated":stamp.isoformat()}).in_("article_id",part).eq("locale","en").execute()
 after=[]
 for i in range(0,len(ids),100):after.extend(supabase.table("article_translations").select("article_id,locale,source_locale,translation_status,slug,affected_models_json").in_("article_id",ids[i:i+100]).in_("locale",["en","sv"]).execute().data or [])
 old={(r["article_id"],r["locale"]):r for r in rows};new={(r["article_id"],r["locale"]):r for r in after}
 for k,r in new.items():
  if r["source_locale"]!="en":raise RuntimeError(f"{k}: readback")
  for f in ("translation_status","slug","affected_models_json"):
   if r[f]!=old[k][f]:raise RuntimeError(f"{k}: {f} changed")
 print(json.dumps({"status":"verified","rows":len(after),"en_source_locale":"en","sv_source_locale":"en"}))
if __name__=="__main__":main()
