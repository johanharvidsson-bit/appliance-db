"""Remove inherited Bosch wording from already-reviewed Samsung FAQs."""
from __future__ import annotations
import json
from config.settings import BASE_DIR
from pipeline.apply_article_review_batch import FIELDS

IDS=[7,8,9,24,25,26,27,29,30,31,32,33,35,36,38,39,40,41,42,43,45,46,47]

def fix(value,locale):
    text=json.dumps(value,ensure_ascii=False)
    text=text.replace("Bosch","Samsung").replace("bosch","Samsung")
    if locale=="sv":
        text=text.replace("E‑Nr","modellnummer").replace("E-Nr","modellnummer")
    else:
        text=text.replace("E‑Nr","model number").replace("E-Nr","model number")
    return json.loads(text)

def main():
    b=json.loads((BASE_DIR/'data/backups/article_reviews/remediation-samsung-faq-brand-before.json').read_text(encoding='utf-8'))
    rows={(r['article_id'],r['locale']):r for r in b['rows']}
    out={"batch":"remediation-samsung-faq-brand","status":"proposal_only_not_applied","article_ids":IDS,"sources":["Internal quality remediation: brand-specific FAQ wording; technical claims and cited batch sources unchanged."],"translations":{}}
    for i in IDS:
        en,sv=rows[(i,'en')],rows[(i,'sv')]
        code=en['h1'].split('Mean on a Samsung Washing Machine?')[0].replace('What Does ','') if 'Mean on a Samsung Washing Machine?' in en['h1'] else str(i)
        out['translations'][str(i)]={"code":code,"preserve":{"en_slug":en['slug'],"sv_slug":sv['slug']},"en":{k:(fix(en[k],'en') if k=='faq_json' else en[k]) for k in FIELDS},"sv":{k:(fix(sv[k],'sv') if k=='faq_json' else sv[k]) for k in FIELDS}}
        for loc in ('en','sv'):
            blob=json.dumps(out['translations'][str(i)][loc]['faq_json'],ensure_ascii=False)
            assert 'Bosch' not in blob and 'bosch' not in blob and 'E‑Nr' not in blob and 'E-Nr' not in blob
    p=BASE_DIR/'data/article_reviews/remediation-samsung-faq-brand-proposal.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(p)
if __name__=='__main__':main()
