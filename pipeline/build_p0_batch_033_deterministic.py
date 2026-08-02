"""Build reviewed Siemens E32/E36/E37/E42/E45 content."""
from __future__ import annotations
import json
from config.settings import BASE_DIR
from pipeline import build_p0_batch_031_deterministic as base

ITEMS={221:"E32",222:"E36",223:"E37",225:"E42",226:"E45"}
def unknown(code):
 return (f"{code} is not defined in Siemens' generic public washer error table; confirm the complete code and exact E-Nr manual before assigning a meaning",f"{code} definieras inte i Siemens generella offentliga felkodstabell för tvättmaskiner; bekräfta hela koden och manualen för exakt E‑Nr innan betydelse anges","Switch the washer off for five seconds once, photograph the complete display and contact Siemens with the exact E-Nr if the code returns","Stäng av tvättmaskinen i fem sekunder en gång, fotografera hela displayen och kontakta Siemens med exakt E‑Nr om koden återkommer","unknown")
DATA={
221:("Siemens identifies E32 alternating with End as unbalanced-load detection interrupting the spin; it is not an appliance fault","Siemens anger att E32 växelvis med End betyder att obalansdetekteringen har avbrutit centrifugeringen; det är inte ett maskinfel","Distribute small and large items evenly and, if needed, select one additional spin cycle","Fördela små och stora plagg jämnt och välj vid behov en extra centrifugering","balance"),
222:unknown("E36"),223:unknown("E37"),225:unknown("E42"),226:unknown("E45"),
}
CAUSES={
"balance":(["Single heavy or absorbent item","Small and large items distributed unevenly","Load is too small or too large","Persistent spin problem requiring model-specific support"],["Ett ensamt tungt eller absorberande plagg","Små och stora plagg är ojämnt fördelade","Lasten är för liten eller för stor","Kvarstående centrifugeringsproblem som kräver modellspecifik support"]),
"unknown":(["Incomplete or misread display","Model-specific information code","A neighbouring character is not visible","Internal condition requiring Siemens diagnosis"],["Ofullständig eller feltolkad display","Modellspecifik informationskod","Ett intilliggande tecken syns inte","Internt tillstånd som kräver Siemens-diagnos"]),
}

def make(i,sv):
 v=base.make(i,sv);code=ITEMS[i]
 if sv:v['when_to_call_technician_html']=f"<p>E32 kräver normalt bara omfördelning av lasten. Boka Siemens-service om centrifugeringen fortsatt misslyckas eller om {code} återkommer efter den enda tillåtna avstängningen.</p><p>Demontera inte maskinen och mät inga interna delar.</p>"
 else:v['when_to_call_technician_html']=f"<p>E32 normally requires only redistributing the load. Arrange Siemens service if spinning still fails or {code} returns after the single permitted power-off.</p><p>Do not dismantle the washer or measure internal parts.</p>"
 return v

def main():
 base.ITEMS=ITEMS;base.DATA=DATA;base.CAUSES=CAUSES
 b=json.loads((BASE_DIR/'data/backups/article_reviews/batch-033-siemens-e32-e45-before.json').read_text(encoding='utf-8'));rows={(r['article_id'],r['locale']):r for r in b['rows']};o={"batch":"033-siemens-e32-e45","status":"proposal_only_not_applied","article_ids":list(ITEMS),"sources":["https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/error-codes-symbols","https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines","https://www.siemens-home.bsh-group.com/uk/customer-service/support/washing-machine"],"translations":{}}
 for i,c in ITEMS.items():o['translations'][str(i)]={"code":c,"preserve":{"en_slug":rows[(i,'en')]['slug'],"sv_slug":rows[(i,'sv')]['slug']},"en":make(i,False),"sv":make(i,True)}
 p=BASE_DIR/'data/article_reviews/batch-033-siemens-e32-e45-proposal.json';p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8');print(p)
if __name__=='__main__':main()
