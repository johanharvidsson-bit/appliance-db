"""Prove completion invariants for the original 259-article review goal."""
from __future__ import annotations
import json,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from config.settings import BASE_DIR,SUPABASE_URL,supabase
from pipeline.apply_article_review_batch import FIELDS
from pipeline.audit_article_priority0 import _translation_flags

OFFICIAL=("samsung.com","bosch-home.com","siemens-home.bsh-group.com","electrolux.","lg.com","media3.bosch-home.com","images.samsung.com","image-us.samsung.com")

def chunks(values,n=100):
 for i in range(0,len(values),n):yield values[i:i+n]

def main()->None:
 proposals=[]
 for path in sorted((BASE_DIR/"data/article_reviews").glob("batch-*-proposal.json")):
  d=json.loads(path.read_text(encoding="utf-8")); proposals.append((path,d))
 latest={}; baseline={}; batch_backup={}; source_issues=[]
 for path,d in proposals:
  batch=d["batch"]
  exact=BASE_DIR/"data/backups/article_reviews"/f"batch-{batch.removeprefix('batch-')}-before.json"
  timestamped=list((BASE_DIR/"data/backups/article_reviews").glob(f"{batch.removeprefix('batch-')}-before-*.json"))+list((BASE_DIR/"data/backups/article_reviews").glob(f"{batch}-before-*.json"))
  batch_backup[batch]={"exact_before":exact.exists(),"timestamped_after_apply":bool(timestamped)}
  if exact.exists():
   before=json.loads(exact.read_text(encoding="utf-8"))
   for row in before.get("rows",[]):
    baseline.setdefault((int(row["article_id"]),row["locale"]),row)
  sources=d.get("sources",[])
  if not sources:source_issues.append({"batch":batch,"issue":"no_sources"})
  for u in sources:
   host=urlparse(u).netloc.lower()
   if not any(x in host for x in OFFICIAL):source_issues.append({"batch":batch,"source":u,"issue":"not_recognised_official"})
  for raw in d["article_ids"]:latest[int(raw)]=(path,d)
 # A later, separately backed-up remediation corrected inherited Bosch wording
 # in 23 Samsung FAQs without changing any technical claim or article relation.
 remediation_path=BASE_DIR/"data/article_reviews/remediation-samsung-faq-brand-proposal.json"
 if remediation_path.exists():
  remediation=json.loads(remediation_path.read_text(encoding="utf-8"))
  for raw in remediation["article_ids"]:latest[int(raw)]=(remediation_path,remediation)
 ids=sorted(latest); articles=[]; translations=[]
 for part in chunks(ids):
  articles.extend(supabase.table("articles").select("id,error_code_id,fault_id,status,article_type").in_("id",part).execute().data or [])
  translations.extend(supabase.table("article_translations").select("*").in_("article_id",part).in_("locale",["en","sv"]).execute().data or [])
 amap={r["id"]:r for r in articles}; tmap={(r["article_id"],r["locale"]):r for r in translations}; failures=[]
 for aid in ids:
  if aid not in amap:failures.append(f"{aid}:missing_article");continue
  a=amap[aid]
  if a["status"]!="published":failures.append(f"{aid}:article_not_published")
  if bool(a.get("error_code_id"))==bool(a.get("fault_id")):failures.append(f"{aid}:relation_invalid")
  path,p=latest[aid]; item=p["translations"][str(aid)]
  for loc,status in (("en","published"),("sv","pending")):
   row=tmap.get((aid,loc))
   if not row:failures.append(f"{aid}/{loc}:missing");continue
   if row["translation_status"]!=status:failures.append(f"{aid}/{loc}:status")
   if row["source_locale"]!="en":failures.append(f"{aid}/{loc}:source_locale")
   if row["slug"]!=item["preserve"][f"{loc}_slug"]:failures.append(f"{aid}/{loc}:slug_changed")
   old=baseline.get((aid,loc))
   if not old:failures.append(f"{aid}/{loc}:missing_baseline")
   else:
    if row["slug"]!=old["slug"]:failures.append(f"{aid}/{loc}:slug_changed_from_backup")
    if row.get("affected_models_json")!=old.get("affected_models_json"):failures.append(f"{aid}/{loc}:model_links_changed")
   for field in FIELDS:
    if row.get(field)!=item[loc].get(field):failures.append(f"{aid}/{loc}:{field}_readback")
   if _translation_flags(row):failures.append(f"{aid}/{loc}:quality_flags={_translation_flags(row)}")
 missing_backups=[b for b,v in batch_backup.items() if not all(v.values())]
 report={"generated_at":datetime.now(timezone.utc).isoformat(),"host":SUPABASE_URL,"proposal_batches":len(proposals),"unique_original_article_ids":len(ids),"article_rows":len(articles),"translation_rows":len(translations),"baseline_rows":len(baseline),"statuses":dict(Counter(r["locale"]+":"+r["translation_status"] for r in translations)),"backup_coverage":batch_backup,"missing_backup_batches":missing_backups,"source_issues":source_issues,"failures":failures,"passed":len(ids)==259 and len(articles)==259 and len(translations)==518 and len(baseline)==518 and not failures and not missing_backups and not source_issues}
 out=BASE_DIR/"data/original-259-completion-audit.json";out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps({k:report[k] for k in ("proposal_batches","unique_original_article_ids","article_rows","translation_rows","statuses","missing_backup_batches","source_issues","failures","passed")},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
