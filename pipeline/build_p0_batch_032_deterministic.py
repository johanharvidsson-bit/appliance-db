"""Build reviewed Siemens E24/E26/E27/E28/E30 content."""
from __future__ import annotations
import json
from config.settings import BASE_DIR
from pipeline import build_p0_batch_031_deterministic as base

ITEMS={215:"E24",216:"E26",217:"E27",218:"E28",220:"E30"}
UNKNOWN_EN="is not defined in Siemens' generic public washer error table; confirm the complete code and exact E-Nr manual before assigning a meaning"
UNKNOWN_SV="definieras inte i Siemens generella offentliga felkodstabell för tvättmaskiner; bekräfta hela koden och manualen för exakt E‑Nr innan betydelse anges"
UNKNOWN_ACTION_EN="Switch the washer off for five seconds once, photograph the complete display and contact Siemens with the exact E-Nr if the code returns"
UNKNOWN_ACTION_SV="Stäng av tvättmaskinen i fem sekunder en gång, fotografera hela displayen och kontakta Siemens med exakt E‑Nr om koden återkommer"
DATA={
215:(f"E24 {UNKNOWN_EN}",f"E24 {UNKNOWN_SV}",UNKNOWN_ACTION_EN,UNKNOWN_ACTION_SV,"unknown"),
216:("Siemens identifies E26 or F26 as a fault in the analogue pressure sensor","Siemens anger att E26 eller F26 betyder fel i den analoga trycksensorn","Stop using the washer and arrange Siemens service; this fault cannot be rectified by the user","Sluta använda tvättmaskinen och boka Siemens-service; felet kan inte åtgärdas av användaren","sensor"),
217:("Siemens identifies E27 or F27 as a pressure-sensor fault","Siemens anger att E27 eller F27 betyder fel i trycksensorn","Stop using the washer and arrange Siemens service; do not test the sensor, tubing, wiring or electronics","Sluta använda tvättmaskinen och boka Siemens-service; testa inte sensor, slangar, kablage eller elektronik","sensor"),
218:(f"E28 {UNKNOWN_EN}",f"E28 {UNKNOWN_SV}",UNKNOWN_ACTION_EN,UNKNOWN_ACTION_SV,"unknown"),
220:(f"E30 {UNKNOWN_EN}",f"E30 {UNKNOWN_SV}",UNKNOWN_ACTION_EN,UNKNOWN_ACTION_SV,"unknown"),
}
CAUSES={
"unknown":(["Incomplete or misread display","Model-specific information code","A neighbouring character is not visible","Internal condition requiring Siemens diagnosis"],["Ofullständig eller feltolkad display","Modellspecifik informationskod","Ett intilliggande tecken syns inte","Internt tillstånd som kräver Siemens-diagnos"]),
"sensor":(["Pressure signal outside the expected range","Analogue or model-specific pressure sensor fault","Internal tubing or wiring fault","Control-electronics fault"],["Trycksignal utanför förväntat område","Fel i analog eller modellspecifik trycksensor","Internt slang- eller kablagefel","Fel i styrelektroniken"]),
}

def make(i,sv):
 v=base.make(i,sv);code=ITEMS[i]
 if sv:v['when_to_call_technician_html']=f"<p>Boka Siemens-service om {code} kvarstår eller återkommer efter den enda tillåtna avstängningen. E26 och E27 är uttryckligen servicefel.</p><p>Trycksensorer, interna slangar, kablage och elektronik är inte användarreparationer.</p>"
 else:v['when_to_call_technician_html']=f"<p>Arrange Siemens service if {code} remains or returns after the single permitted power-off. E26 and E27 are explicitly service faults.</p><p>Pressure sensors, internal tubing, wiring and electronics are not user repairs.</p>"
 return v

def main():
 base.ITEMS=ITEMS;base.DATA=DATA;base.CAUSES=CAUSES
 b=json.loads((BASE_DIR/'data/backups/article_reviews/batch-032-siemens-e24-e30-before.json').read_text(encoding='utf-8'));rows={(r['article_id'],r['locale']):r for r in b['rows']};o={"batch":"032-siemens-e24-e30","status":"proposal_only_not_applied","article_ids":list(ITEMS),"sources":["https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/error-codes-symbols","https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines","https://www.siemens-home.bsh-group.com/uk/customer-service/support/washing-machine"],"translations":{}}
 for i,c in ITEMS.items():o['translations'][str(i)]={"code":c,"preserve":{"en_slug":rows[(i,'en')]['slug'],"sv_slug":rows[(i,'sv')]['slug']},"en":make(i,False),"sv":make(i,True)}
 p=BASE_DIR/'data/article_reviews/batch-032-siemens-e24-e30-proposal.json';p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8');print(p)
if __name__=='__main__':main()
