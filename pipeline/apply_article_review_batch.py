"""Safely apply a reviewed multi-article proposal. Dry-run unless --apply."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timezone
from pathlib import Path
from config.settings import BASE_DIR,SUPABASE_URL,supabase

FIELDS=("title_tag","meta_description","h1","description","quick_fix","intro_html","causes_json","steps_json","when_to_call_technician_html","prevention_html","faq_json","parts_json")
READ="article_id,locale,slug,"+",".join(FIELDS)+",affected_models_json,translation_status,source_locale,last_updated"

def read(ids):
 rows=(supabase.table('article_translations').select(READ).in_('article_id',ids).in_('locale',['en','sv']).order('article_id').order('locale').execute().data or [])
 if len(rows)!=2*len(ids) or {(r['article_id'],r['locale']) for r in rows}!={(i,l) for i in ids for l in ('en','sv')}: raise RuntimeError('unexpected row set')
 return rows
def validate(v,loc):
 if set(v)!=set(FIELDS): raise RuntimeError(f'{loc}: field mismatch')
 for k,keys,lo,hi in [('causes_json',{'cause','detail'},4,6),('steps_json',{'step','action','detail'},5,7),('faq_json',{'question','answer'},4,5)]:
  if not isinstance(v[k],list) or not lo<=len(v[k])<=hi or any(set(x)!=keys for x in v[k]): raise RuntimeError(f'{loc}: invalid {k}')
 if v['parts_json']!=[]: raise RuntimeError(f'{loc}: parts must be empty')
 if len(v['title_tag'])>70 or len(v['meta_description'])>165: raise RuntimeError(f'{loc}: SEO length')
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('proposal',type=Path); ap.add_argument('--apply',action='store_true'); a=ap.parse_args()
 if 'jqepafrexisjmzoefvpr.supabase.co' in SUPABASE_URL: raise RuntimeError('retired cloud blocked')
 p=json.loads(a.proposal.read_text(encoding='utf-8')); ids=sorted(map(int,p['article_ids']))
 if set(map(int,p['translations']))!=set(ids): raise RuntimeError('proposal id mismatch')
 for i in ids:
  for loc in ('en','sv'): validate(p['translations'][str(i)][loc],f'{i}/{loc}')
 before=read(ids); old={(r['article_id'],r['locale']):r for r in before}
 for i in ids:
  q=p['translations'][str(i)]['preserve']
  if old[(i,'en')]['slug']!=q['en_slug'] or old[(i,'sv')]['slug']!=q['sv_slug']: raise RuntimeError(f'{i}: slug mismatch')
  if old[(i,'sv')]['translation_status']!='pending': raise RuntimeError(f'{i}: sv not pending')
 changes={f'{i}/{l}':[k for k in FIELDS if old[(i,l)].get(k)!=p['translations'][str(i)][l][k]] for i in ids for l in ('en','sv')}
 print(json.dumps({'mode':'apply' if a.apply else 'dry-run','rows':len(before),'changes':changes}))
 if not a.apply:return
 stamp=datetime.now(timezone.utc); d=BASE_DIR/'data/backups/article_reviews'; d.mkdir(parents=True,exist_ok=True); bp=d/f"{p['batch']}-before-{stamp.strftime('%Y%m%dT%H%M%SZ')}.json"; bp.write_text(json.dumps({'exported_at':stamp.isoformat(),'source':'production-vps','article_ids':ids,'rows':before},ensure_ascii=False,indent=2),encoding='utf-8'); print(f'backup={bp}')
 updated=stamp.isoformat()
 for i in ids:
  for loc in ('en','sv'):
   payload={k:p['translations'][str(i)][loc][k] for k in FIELDS}; payload['last_updated']=updated
   res=(supabase.table('article_translations').update(payload).eq('article_id',i).eq('locale',loc).execute().data or [])
   if len(res)!=1: raise RuntimeError(f'{i}/{loc}: update count {len(res)}')
 after=read(ids); new={(r['article_id'],r['locale']):r for r in after}
 for i in ids:
  for loc in ('en','sv'):
   r=new[(i,loc)]; want=p['translations'][str(i)][loc]
   if any(r[k]!=want[k] for k in FIELDS): raise RuntimeError(f'{i}/{loc}: readback mismatch')
   if r['slug']!=old[(i,loc)]['slug'] or r['affected_models_json']!=old[(i,loc)]['affected_models_json'] or r['translation_status']!=old[(i,loc)]['translation_status']: raise RuntimeError(f'{i}/{loc}: invariant changed')
 print(json.dumps({'status':'verified','articles':len(ids),'rows':len(after),'last_updated':updated}))
if __name__=='__main__':main()
