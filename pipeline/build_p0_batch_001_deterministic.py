"""Build reviewed Bosch batch 001 content without an external LLM."""
from __future__ import annotations
import json
from pathlib import Path
from config.settings import BASE_DIR

IDS = {164:"E16",167:"E19",168:"E20",169:"E21",170:"E22"}

PROFILE = {
"E16": {
 "meaning":"Bosch identifies E16/F16 as a door that is open or not locked correctly.",
 "safe":"Check for laundry trapped between the door and housing, reduce an overfull load, and close the door until it clicks.",
 "service":"If the code remains after the door is clear and firmly closed, Bosch advises contacting customer support.",
},
"E19": {
 "meaning":"Bosch identifies E19/F19 as the permitted heating time being exceeded.",
 "safe":"Bosch states that this fault cannot be rectified by the user.",
 "service":"Stop the programme safely, switch off and unplug the washer, and arrange Bosch service.",
},
"E20": {
 "meaning":"Bosch identifies E20/F20 as unexpected heating in the washing machine.",
 "safe":"This is not a homeowner electrical test or repair task.",
 "service":"Stop the programme safely, switch off and unplug the washer, and arrange Bosch service if the code is present.",
},
"E21": {
 "meaning":"E21/F21 is model-dependent: an official recent Bosch manual uses E:21 for detergent solution not being pumped out, while another Bosch manual uses F:21 for a motor fault.",
 "safe":"Record the exact code and E-Nr and follow only the troubleshooting steps in the manual for that washer.",
 "service":"If the exact manual identifies a motor fault, or the code persists after documented drain maintenance, arrange Bosch service.",
},
"E22": {
 "meaning":"Bosch does not give E22 a universal washing-machine meaning in its general washer error-code list.",
 "safe":"Do not use Bosch dishwasher E22 advice for a washing machine; record the exact code and E-Nr and check the washer's own manual.",
 "service":"If the manual does not provide a safe user action, or the code returns, arrange Bosch service.",
}}

def en(code):
 p=PROFILE[code]
 service_only=code in {"E19","E20","E22"}
 title=f"Bosch Washing Machine Error {code}: Safe Next Steps"
 meta=(f"Bosch washer showing {code}? Check the verified meaning, safe steps, model differences and when to stop troubleshooting and contact Bosch service.")
 if len(meta)<140: meta += " for help"
 causes=[
  {"cause":"What Bosch confirms","detail":p["meaning"]},
  {"cause":"Model and market differences","detail":"Bosch codes and permitted checks can differ by model family and market. The E-Nr identifies the exact appliance and its applicable manual."},
  {"cause":"A repeat rather than a one-off display","detail":"If the same code returns after the appliance has been restarted exactly as its manual permits, it needs further assessment rather than repeated resets."},
  {"cause":"A condition requiring professional diagnosis","detail":"The code alone does not identify a part that a homeowner should order or replace. Internal electrical, sensing, heating, locking, drain or drive work belongs with an authorised service technician."},
 ]
 if code=="E16": causes[2]={"cause":"Laundry obstructing the door","detail":"A garment caught between the door and housing, or an overfull load pressing against the door, can prevent the lock from engaging."}
 if code=="E21": causes[2]={"cause":"Different documented meanings","detail":"On a model where the manual defines E:21 as a drain problem, a blocked drain path, pump cover position or excessive detergent may be relevant. A model defining F:21 as a motor fault requires service."}
 steps=[
  {"step":1,"action":"Record the complete display","detail":f"Photograph {code} and note whether the display includes an F, punctuation or additional digits. Find the E-Nr on the rating plate so the correct Bosch manual can be used."},
  {"step":2,"action":"Stop the programme safely","detail":"Use the controls to stop or cancel the programme and wait for the drum to stop. Do not force the door; if water or heat keeps it locked, follow the model manual for safe draining and unlocking."},
  {"step":3,"action":"Switch off and unplug","detail":"Disconnect the washer from the mains before any permitted external check. Do not remove a panel, bypass a lock or test internal wiring or components."},
  {"step":4,"action":"Follow only the exact model manual","detail":p["safe"]+" Do not apply instructions for a dishwasher or a different Bosch washer series."},
  {"step":5,"action":"Restart only if the manual permits it","detail":"Reconnect the appliance and perform a single documented restart. Do not repeatedly reset a heating, motor or unknown fault to continue washing."},
  {"step":6,"action":"Arrange service if the code remains","detail":p["service"]+" Give Bosch the E-Nr, full code and a description of when it appeared."},
 ]
 if code=="E16": steps[3]["detail"]="Check the door opening for trapped laundry and reduce the load if it presses against the door. Close the door firmly until it clicks, without slamming or forcing the latch."
 if code=="E21": steps[3]["detail"]="If the exact manual defines E:21 as a drain fault, follow its unplugging, cooling, draining and pump-maintenance procedure. If it defines F:21 as a motor fault, do not attempt a repair and book service."
 return {
  "title_tag":title,
  "meta_description":meta[:160],
  "h1":f"What Does {code} Mean on a Bosch Washing Machine?",
  "description":p["meaning"],
  "quick_fix":("Clear any trapped laundry and close the door firmly; if the code remains, stop and contact Bosch service (about 5 minutes)." if code=="E16" else "Record the full code and E-Nr, switch off and unplug the washer, then follow the exact model manual or arrange Bosch service (about 5 minutes)."),
  "intro_html":f"<p>{p['meaning']} The safest response depends on the full code, model family and market, so the exact Bosch manual matters.</p><p>{p['safe']} Do not remove appliance panels, test live circuits or order a replacement part from the code alone. Preserve the full display and E-Nr for Bosch support.</p>",
  "causes_json":causes,"steps_json":steps,
  "when_to_call_technician_html":f"<p>{p['service']} Request service immediately if there is a burning smell, smoke, visible water leakage, repeated tripping of the electrical supply, or abnormal heat.</p><p>Do not remove the front, rear or top panel or inspect internal locks, heaters, pumps, motors, wiring or control boards. The error code alone is not a confirmed parts diagnosis.</p>",
  "prevention_html":"<p>Use the programme and load limits in the exact model manual, keep the door opening clear, dose detergent correctly and maintain only the user-accessible items Bosch specifies.</p><p>Keep the E-Nr and manual available. Stop using the washer when a service-only or unknown code returns instead of repeatedly resetting it.</p>",
  "faq_json":[
   {"question":f"Can I keep using the washer with {code}?","answer":"Do not continue if the code returns, the programme cannot finish safely, or there is heat, leakage, odour or unusual noise. Record the code and follow the exact manual or Bosch service advice."},
   {"question":f"Does {code} mean I need a replacement part?","answer":"No specific part can be confirmed from the code alone. Bosch service should diagnose a persistent internal fault before any part is ordered."},
   {"question":"Why does the E-Nr matter?","answer":"Bosch code meanings and controls vary between model families and markets. The E-Nr identifies the correct appliance documentation and service information."},
   {"question":"Can I inspect the washer internally?","answer":"No. Do not remove panels or test internal electrical or mechanical components; use only the external maintenance steps stated in the exact model manual."},
   {"question":"What information should I give Bosch service?","answer":f"Provide the E-Nr, the complete {code} display including any F or extra digits, when it appeared, and any visible symptoms. A photo of the display is useful."},
  ],"parts_json":[]}

def sv(code):
 p=PROFILE[code]
 meanings={
 "E16":"Bosch anger att E16/F16 betyder att luckan är öppen eller inte korrekt låst.",
 "E19":"Bosch anger att E19/F19 betyder att den tillåtna uppvärmningstiden har överskridits.",
 "E20":"Bosch anger att E20/F20 betyder oväntad uppvärmning i tvättmaskinen.",
 "E21":"E21/F21 är modellberoende: en nyare officiell Bosch-manual använder E:21 för att tvättvattnet inte pumpas ut, medan en annan Bosch-manual använder F:21 för motorfel.",
 "E22":"Bosch anger ingen generell betydelse för E22 på tvättmaskiner i sin övergripande felkodslista.",}
 e=en(code); meaning=meanings[code]
 safe={"E16":"Kontrollera om tvätt har fastnat vid luckan, minska en överfull last och stäng luckan tills den klickar.","E19":"Bosch anger att användaren inte själv kan åtgärda detta fel.","E20":"Detta är inte ett elektriskt test- eller reparationsarbete för användaren.","E21":"Anteckna hela koden och E‑Nr och följ endast anvisningarna i manualen för just den maskinen.","E22":"Använd inte råd för Bosch-diskmaskinens E22; anteckna hela koden och E‑Nr och kontrollera tvättmaskinens egen manual."}[code]
 causes=[{"cause":"Det Bosch bekräftar","detail":meaning},{"cause":"Skillnader mellan modeller och marknader","detail":"Bosch-koder och tillåtna kontroller kan skilja sig mellan modellserier och marknader. E‑Nr identifierar rätt maskin och manual."},{"cause":"Koden återkommer","detail":"Om samma kod återkommer efter den enda omstart som manualen medger behövs vidare bedömning, inte upprepade återställningar."},{"cause":"Ett tillstånd som kräver professionell diagnos","detail":"Koden pekar inte ensam ut en reservdel som användaren ska beställa eller byta. Interna arbeten ska utföras av servicetekniker."}]
 if code=="E16": causes[2]={"cause":"Tvätt hindrar luckan","detail":"Ett plagg mellan luckan och höljet eller en överfull last kan hindra lucklåset från att gå i ingrepp."}
 if code=="E21": causes[2]={"cause":"Olika dokumenterade betydelser","detail":"Om manualen definierar E:21 som tömningsfel kan avloppsväg, pumplock eller för mycket tvättmedel vara relevant. F:21 som motorfel kräver service."}
 steps=[{"step":1,"action":"Dokumentera hela displayen","detail":f"Fotografera {code} och notera om ett F, skiljetecken eller fler siffror visas. Leta upp E‑Nr på typskylten så att rätt Bosch-manual används."},{"step":2,"action":"Stoppa programmet säkert","detail":"Stoppa eller avbryt programmet med reglagen och vänta tills trumman står stilla. Tvinga inte upp luckan; följ manualen om maskinen måste tömmas."},{"step":3,"action":"Stäng av och dra ur kontakten","detail":"Koppla bort maskinen före en tillåten yttre kontroll. Ta inte bort paneler, förbikoppla inte lås och mät inte interna ledningar eller komponenter."},{"step":4,"action":"Följ endast rätt modellmanual","detail":safe+" Använd inte instruktioner för en diskmaskin eller annan Bosch-serie."},{"step":5,"action":"Starta bara om när manualen medger det","detail":"Anslut maskinen och gör en enda dokumenterad omstart. Återställ inte upprepade gånger ett uppvärmnings-, motor- eller okänt fel."},{"step":6,"action":"Boka service om koden kvarstår","detail":"Kontakta Bosch och uppge E‑Nr, hela koden och när den visades. Försök inte diagnostisera interna delar själv."}]
 if code=="E16": steps[3]["detail"]="Kontrollera om tvätt sitter i lucköppningen och minska lasten om den trycker mot luckan. Stäng luckan bestämt tills den klickar, utan att slå igen eller tvinga låset."
 if code=="E21": steps[3]["detail"]="Om manualen definierar E:21 som tömningsfel följer du dess anvisningar för urkoppling, avsvalning, tömning och pumpunderhåll. Om den definierar F:21 som motorfel bokar du service."
 return {"title_tag":f"Bosch tvättmaskin felkod {code}: säkra nästa steg","meta_description":f"Visar Bosch-tvättmaskinen {code}? Läs den verifierade betydelsen, säkra kontroller, modellskillnader och när du ska avbryta och boka Bosch-service.","h1":f"Vad betyder {code} på en Bosch-tvättmaskin?","description":meaning,"quick_fix":("Ta bort tvätt som hindrar luckan och stäng den ordentligt; kvarstår koden bokar du Bosch-service (cirka 5 minuter)." if code=="E16" else "Anteckna hela koden och E‑Nr, stäng av och dra ur kontakten och följ rätt modellmanual eller boka Bosch-service (cirka 5 minuter)."),"intro_html":f"<p>{meaning} Den säkra åtgärden beror på hela koden, modellserien och marknaden. Använd därför rätt Bosch-manual.</p><p>{safe} Ta inte bort paneler, mät inte interna kretsar och beställ inte reservdelar utifrån koden ensam.</p>","causes_json":causes,"steps_json":steps,"when_to_call_technician_html":"<p>Boka service om koden återkommer efter de kontroller som uttryckligen anges i rätt modellmanual. Avbryt direkt vid bränd lukt, rök, synligt vattenläckage, onormal värme eller återkommande utlöst säkring.</p><p>Ta inte bort front-, bak- eller toppanelen och kontrollera inte interna lås, värmare, pumpar, motorer, ledningar eller styrkort. Felkoden är inte en säker reservdelsdiagnos.</p>","prevention_html":"<p>Följ programmets lastgränser, håll lucköppningen fri, dosera tvättmedel korrekt och underhåll bara de användaråtkomliga delar som Bosch anger.</p><p>Spara E‑Nr och manualen. Sluta använda maskinen om en servicekod eller okänd kod återkommer i stället för att återställa den upprepade gånger.</p>","faq_json":[{"question":f"Kan jag fortsätta använda maskinen med {code}?","answer":"Fortsätt inte om koden återkommer eller programmet inte kan slutföras säkert. Dokumentera koden och följ rätt manual eller Bosch serviceanvisning."},{"question":f"Betyder {code} att en reservdel måste bytas?","answer":"Ingen särskild reservdel kan bekräftas från koden ensam. En servicetekniker ska diagnostisera ett kvarstående internt fel före beställning."},{"question":"Varför behövs E‑Nr?","answer":"Kodbetydelser och reglage varierar mellan Bosch-serier och marknader. E‑Nr identifierar rätt dokumentation."},{"question":"Kan jag kontrollera maskinen invändigt?","answer":"Nej. Ta inte bort paneler eller testa interna elektriska eller mekaniska delar; följ endast manualens yttre underhåll."},{"question":"Vad ska jag uppge till Bosch?","answer":f"Uppge E‑Nr, hela {code}-visningen, när den uppstod och synliga symptom. Ett foto av displayen är användbart."}],"parts_json":[]}

def validate(v):
 assert 4<=len(v['causes_json'])<=6 and 5<=len(v['steps_json'])<=7 and 4<=len(v['faq_json'])<=5 and v['parts_json']==[]
 assert len(v['title_tag'])<=70 and len(v['meta_description'])<=165

def main():
 b=json.loads((BASE_DIR/'data/backups/article_reviews/batch-001-bosch-e16-e22-before.json').read_text(encoding='utf-8')); rows={(r['article_id'],r['locale']):r for r in b['rows']}; out={"batch":"001-bosch-e16-e22","status":"proposal_only_not_applied","article_ids":list(IDS),"sources":["https://www.bosch-home.com/us/experience-bosch/heart-of-the-home/tips-and-tricks/washer-error-codes","https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e16-or-f16-washing-machine","https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e19-or-f19-washing-machine","https://media3.bosch-home.com/Documents/9001994523_B.pdf","https://media3.bosch-home.com/Documents/9001026001_A.pdf"],"translations":{}}
 for i,c in IDS.items():
  a,z=en(c),sv(c); validate(a); validate(z); out['translations'][str(i)]={"code":c,"preserve":{"en_slug":rows[(i,'en')]['slug'],"sv_slug":rows[(i,'sv')]['slug']},"en":a,"sv":z}
 p=BASE_DIR/'data/article_reviews/batch-001-bosch-e16-e22-proposal.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8'); print(p)
if __name__=='__main__': main()
