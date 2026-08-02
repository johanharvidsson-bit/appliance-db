"""Build reviewed Siemens E47/E50/E60/E61/E62 content."""
from __future__ import annotations
import json
from config.settings import BASE_DIR
from pipeline import build_p0_batch_031_deterministic as base

ITEMS={227:"E47",228:"E50",229:"E60",230:"E61",231:"E62"}

def entry(code):
 listed=code in ("E47","E50")
 if listed:
  me=f"Siemens support lists {code} as a washer display code, but a universal component meaning is not exposed in its generic public table; use the exact E-Nr support result"
  ms=f"Siemens support listar {code} som en displaykod för tvättmaskiner, men någon universell komponentbetydelse visas inte i den generella offentliga tabellen; använd supportresultatet för exakt E‑Nr"
 else:
  me=f"A display beginning {code} may be incomplete because current Siemens washers also use longer E60-series codes; record every character and use the exact E-Nr support result"
  ms=f"En visning som börjar med {code} kan vara ofullständig eftersom aktuella Siemens-tvättmaskiner även använder längre E60-seriekoder; dokumentera varje tecken och använd supportresultatet för exakt E‑Nr"
 ae="Switch the washer off for five seconds once, photograph the complete display and contact Siemens with the exact E-Nr if the code returns"
 av="Stäng av tvättmaskinen i fem sekunder en gång, fotografera hela displayen och kontakta Siemens med exakt E‑Nr om koden återkommer"
 return me,ms,ae,av,"unknown"

DATA={i:entry(c) for i,c in ITEMS.items()}
CAUSES={"unknown":(["Incomplete or misread display","Model-specific information code","A longer multi-part code is not fully visible","Internal condition requiring Siemens diagnosis"],["Ofullständig eller feltolkad display","Modellspecifik informationskod","En längre flerdelad kod syns inte fullständigt","Internt tillstånd som kräver Siemens-diagnos"])}

def make(i,sv):
 v=base.make(i,sv);code=ITEMS[i]
 if sv:v['when_to_call_technician_html']=f"<p>Boka Siemens-service om {code} kvarstår eller återkommer efter den enda tillåtna femsekundersavstängningen. Uppge hela displayen och exakt E‑Nr.</p><p>Demontera inte maskinen och mät inga interna delar.</p>"
 else:v['when_to_call_technician_html']=f"<p>Arrange Siemens service if {code} remains or returns after the single permitted five-second power-off. Provide the complete display and exact E-Nr.</p><p>Do not dismantle the washer or measure internal parts.</p>"
 return v

def main():
 base.ITEMS=ITEMS;base.DATA=DATA;base.CAUSES=CAUSES
 b=json.loads((BASE_DIR/'data/backups/article_reviews/batch-034-siemens-e47-e62-before.json').read_text(encoding='utf-8'));rows={(r['article_id'],r['locale']):r for r in b['rows']};o={"batch":"034-siemens-e47-e62","status":"proposal_only_not_applied","article_ids":list(ITEMS),"sources":["https://www.siemens-home.bsh-group.com/uk/customer-service/support/washing-machine","https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/error-codes-symbols","https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting"],"translations":{}}
 for i,c in ITEMS.items():o['translations'][str(i)]={"code":c,"preserve":{"en_slug":rows[(i,'en')]['slug'],"sv_slug":rows[(i,'sv')]['slug']},"en":make(i,False),"sv":make(i,True)}
 p=BASE_DIR/'data/article_reviews/batch-034-siemens-e47-e62-proposal.json';p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8');print(p)
if __name__=='__main__':main()
