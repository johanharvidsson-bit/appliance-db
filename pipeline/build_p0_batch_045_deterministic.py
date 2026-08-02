"""Build the final reviewed P0 core washing-machine batch."""
from __future__ import annotations

import json
from config.settings import BASE_DIR
from pipeline import build_p0_batch_041_deterministic as base


CODES = {
    245:("Electrolux","E10","a water-inlet problem or insufficient water entering the washer","ett tilloppsproblem eller att för lite vatten kommer in i maskinen","Open the tap, check household flow and straighten the visible inlet hose","Öppna kranen, kontrollera bostadens vattenflöde och räta synlig tilloppsslang"),
    246:("Electrolux","E11","the washer did not fill with enough water during the required time","maskinen inte fylldes med tillräckligt vatten inom föreskriven tid","Open the tap, check water pressure and the visible inlet hose","Öppna kranen och kontrollera vattentryck samt synlig tilloppsslang"),
    247:("Electrolux","E13","water has been detected in the base or a leakage condition is present","vatten har registrerats i botten eller att ett läckagetillstånd finns","Stop use, close the tap and isolate power only from a dry safe position","Sluta använda maskinen, stäng kranen och bryt strömmen endast från en torr och säker plats"),
    249:("Electrolux","E21","a water-drainage problem","ett tömningsproblem","Switch off, unplug, let hot water cool and check the visible drain path as the model manual specifies","Stäng av, dra ur kontakten, låt hett vatten svalna och kontrollera synlig avloppsväg enligt modellmanualen"),
    266:("Electrolux","E57","an inverter or motor-current condition that requires authorised diagnosis","ett växelriktar- eller motorströmstillstånd som kräver auktoriserad diagnos","Record the code, stop use and arrange authorised Electrolux service","Notera koden, sluta använda maskinen och boka auktoriserad Electrolux-service"),
    277:("Electrolux","EF1","a blocked drain path or excessively long draining","en blockerad avloppsväg eller alltför lång tömning","Check the visible drain hose and user-accessible filter only as the exact manual specifies","Kontrollera synlig avloppsslang och användaråtkomligt filter endast enligt exakt manual"),
    88:("LG","CL","Child Lock is active rather than a component fault","barnlåset är aktivt snarare än att ett komponentfel föreligger","Use the marked Child Lock control or exact model manual because the key sequence varies","Använd den markerade barnlåskontrollen eller exakt modellmanual eftersom knappsekvensen varierar"),
    94:("LG","FE","an overfill condition","ett överfyllnadstillstånd","Close the water taps, stop use and arrange LG service if water continues entering","Stäng vattenkranarna, sluta använda maskinen och boka LG-service om vatten fortsätter att strömma in"),
    95:("LG","IE","the washer cannot obtain enough inlet water","maskinen inte får tillräckligt med tilloppsvatten","Open the taps, check household flow and straighten visible inlet hoses","Öppna kranarna, kontrollera bostadens flöde och räta synliga tilloppsslangar"),
    99:("LG","PF","a power failure interrupted the programme","ett strömavbrott avbröt programmet","Confirm safe power and restart once only if there is no electrical warning sign","Bekräfta säker strömförsörjning och starta om en gång endast om inga tecken på elfel finns"),
    101:("LG","tCL","the Tub Clean reminder is displayed","påminnelsen om Tub Clean visas","Empty the drum and run the exact model's Tub Clean cycle as the manual specifies","Töm trumman och kör modellens Tub Clean-program enligt manualen"),
    207:("Siemens","CL","Child Lock is active on models using this display","barnlåset är aktivt på modeller som använder denna visning","Use the marked key control or exact E-Nr manual because the sequence varies","Använd den markerade nyckelkontrollen eller manualen för exakt E‑Nr eftersom sekvensen varierar"),
    209:("Siemens","E17","the water supply is impaired by flow, hose or inlet-filter conditions","vattentillförseln begränsas av flöde, slang eller inloppsfilter","Open the tap, check flow and straighten the visible inlet hose","Öppna kranen, kontrollera flödet och räta synlig tilloppsslang"),
    213:("Siemens","E22","no universal meaning in Siemens' current public washer table; the exact E-Nr manual is required","ingen universell betydelse i Siemens aktuella offentliga tvättmaskinstabell; manualen för exakt E‑Nr krävs","Photograph the full display and contact Siemens with the exact E-Nr","Fotografera hela displayen och kontakta Siemens med exakt E‑Nr"),
    219:("Siemens","E29","the water supply is impaired or pressure is too low","vattentillförseln är begränsad eller trycket för lågt","Open the tap, check household flow and straighten the visible inlet hose","Öppna kranen, kontrollera bostadens flöde och räta synlig tilloppsslang"),
    224:("Siemens","E38","no universal meaning in Siemens' current public washer table; the exact E-Nr manual is required","ingen universell betydelse i Siemens aktuella offentliga tvättmaskinstabell; manualen för exakt E‑Nr krävs","Record every character and contact Siemens before taking model-specific action","Notera varje tecken och kontakta Siemens innan en modellspecifik åtgärd görs"),
    240:("Siemens","E91","no universal meaning in Siemens' current public washer table; the exact E-Nr manual is required","ingen universell betydelse i Siemens aktuella offentliga tvättmaskinstabell; manualen för exakt E‑Nr krävs","Record the full code and arrange Siemens diagnosis without opening panels","Notera hela koden och boka Siemens-diagnos utan att öppna paneler"),
    242:("Siemens","END","normally a programme-status message, but its exact behaviour is model-specific","normalt är ett programstatusmeddelande men att exakt beteende är modellspecifikt","Confirm that the programme ended and check the exact E-Nr manual if the controls remain unavailable","Bekräfta att programmet avslutats och kontrollera manualen för exakt E‑Nr om kontrollerna förblir otillgängliga"),
}

FAULTS = {
    320:("Bosch","Clothes Still Wet After Spin Cycle","Kläderna är fortfarande våta efter centrifugering","wet"), 321:("Bosch","Washing Machine Has a Bad Smell","Tvättmaskinen luktar illa","odour"), 322:("Bosch","Door Seal Is Damaged or Mouldy","Lucktätningen är skadad eller möglig","gasket"), 326:("Bosch","Washing Machine Producing Too Much Foam","Tvättmaskinen skummar för mycket","foam"), 327:("Bosch","Detergent Not Dispensing From the Drawer","Tvättmedel doseras inte från lådan","detergent"),
    351:("Electrolux","Washing Machine Won't Start","Tvättmaskinen startar inte","start"), 352:("Electrolux","Washing Machine Is Leaking Water","Tvättmaskinen läcker vatten","leak"), 358:("Electrolux","Clothes Still Wet After Spin Cycle","Kläderna är fortfarande våta efter centrifugering","wet"), 359:("Electrolux","Washing Machine Has a Bad Smell","Tvättmaskinen luktar illa","odour"), 364:("Electrolux","Washing Machine Producing Too Much Foam","Tvättmaskinen skummar för mycket","foam"), 365:("Electrolux","Detergent Not Dispensing From the Drawer","Tvättmedel doseras inte från lådan","detergent"),
    150:("LG","Washing Machine Won't Start","Tvättmaskinen startar inte","start"), 151:("LG","Washing Machine Is Leaking Water","Tvättmaskinen läcker vatten","leak"), 153:("LG","Washing Machine Door Won't Open","Tvättmaskinens lucka går inte att öppna","door"), 158:("LG","Clothes Still Wet After Spin Cycle","Kläderna är fortfarande våta efter centrifugering","wet"), 159:("LG","Washing Machine Has a Bad Smell","Tvättmaskinen luktar illa","odour"), 160:("LG","Child Lock Is Active or Stuck","Barnlåset är aktivt eller fastnat","lock"), 162:("LG","Washing Machine Won't Complete a Cycle","Tvättmaskinen slutför inte programmet","cycle"),
    332:("Siemens","Washing Machine Won't Start","Tvättmaskinen startar inte","start"), 333:("Siemens","Washing Machine Is Leaking Water","Tvättmaskinen läcker vatten","leak"), 335:("Siemens","Washing Machine Door Won't Open","Tvättmaskinens lucka går inte att öppna","door"), 340:("Siemens","Washing Machine Has a Bad Smell","Tvättmaskinen luktar illa","odour"), 341:("Siemens","Door Seal Is Damaged or Mouldy","Lucktätningen är skadad eller möglig","gasket"), 344:("Siemens","Washing Machine Won't Complete a Cycle","Tvättmaskinen slutför inte programmet","cycle"), 345:("Siemens","Washing Machine Producing Too Much Foam","Tvättmaskinen skummar för mycket","foam"), 346:("Siemens","Detergent Not Dispensing From the Drawer","Tvättmedel doseras inte från lådan","detergent"),
}

DETAIL = {
 "start":("safe power, a fully closed door, active lock or delay settings and displayed alerts","säker ström, helt stängd lucka, aktiva lås- eller fördröjningsinställningar och visade meddelanden"),
 "leak":("the door seal, detergent foam and visible hoses or connections","lucktätningen, tvättmedelsskum och synliga slangar eller anslutningar"),
 "door":("water, temperature, drum movement or an active safety lock","vatten, temperatur, trumrörelse eller ett aktivt säkerhetslås"),
 "wet":("an unbalanced load, low spin selection or restricted drainage","obalanserad last, låg centrifugeringshastighet eller hindrad tömning"),
 "odour":("retained moisture, residue and missed manual-specified cleaning","kvarvarande fukt, rester och utebliven rengöring enligt manualen"),
 "gasket":("residue, trapped objects, persistent moisture or physical damage","rester, fastnade föremål, kvarvarande fukt eller fysisk skada"),
 "foam":("too much, unsuitable or incorrectly dosed detergent","för mycket, olämpligt eller fel doserat tvättmedel"),
 "detergent":("drawer residue, an incorrect insert position or a model-specific dosing setting","rester i lådan, fel läge på insatsen eller en modellspecifik doseringsinställning"),
 "lock":("Child Lock activation or a model-specific control sequence","aktiverat barnlås eller en modellspecifik knappsekvens"),
 "cycle":("load, supply, drainage, foam or a displayed model-specific condition","last, tillförsel, tömning, skum eller ett visat modellspecifikt tillstånd"),
}

def item_for(article_id:int)->dict[str,object]:
    if article_id in CODES:
        brand,code,en_m,sv_m,en_a,sv_a=CODES[article_id]
        return {"type":"code","subject":code,"en_title":f"What Does {code} Mean on a {brand} Washing Machine?","sv_title":f"Vad betyder {code} på en {brand}-tvättmaskin?","en_meaning":f"{brand} identifies {code} as {en_m}","sv_meaning":f"{brand} anger att {code} betyder {sv_m}","en_action":en_a,"sv_action":sv_a,"en_causes":["External operating condition", "Model-specific installation condition", "Complete code or suffix not recorded", "Internal fault requiring authorised service"],"sv_causes":["Yttre driftstillstånd","Modellspecifikt installationstillstånd","Hela koden eller suffixet har inte noterats","Internt fel som kräver auktoriserad service"]}
    brand,en_t,sv_t,kind=FAULTS[article_id]; en_d,sv_d=DETAIL[kind]
    action_en = "Stop use and isolate water or power safely; inspect user-accessible areas only by the exact model manual" if kind=="leak" else "Check the safe external conditions and follow only the exact model manual's user procedure"
    action_sv = "Sluta använda maskinen och stäng vatten eller bryt ström säkert; kontrollera endast användaråtkomliga områden enligt exakt modellmanual" if kind=="leak" else "Kontrollera säkra yttre förhållanden och följ endast modellmanualens användarprocedur"
    en_t=en_t.replace("Washing Machine", "Washer")
    sv_t=sv_t.replace("Tvättmaskinens ", "").replace("Tvättmaskinen ", "")
    sv_t={"wet":"Våt tvätt efter centrifugering","odour":"Dålig lukt","gasket":"Skadad eller möglig lucktätning","foam":"För mycket skum","detergent":"Tvättmedel doseras inte","start":"Startar inte","leak":"Vattenläckage","door":"Luckan öppnas inte","lock":"Barnlåset är aktivt","cycle":"Programmet slutförs inte"}[kind]
    en_causes=([x.capitalize() for x in en_d.split(", ")]+["Incorrect user setting","Model-specific operating condition","Internal fault requiring authorised service"])[:4]
    sv_causes=([x.capitalize() for x in sv_d.split(", ")]+["Felaktig användarinställning","Modellspecifikt driftstillstånd","Internt fel som kräver auktoriserad service"])[:4]
    return {"type":"fault","subject":kind,"en_title":f"{brand} {en_t}","sv_title":f"{brand}: {sv_t}","en_meaning":f"Official {brand} guidance links this symptom to {en_d}","sv_meaning":f"Officiell vägledning från {brand} kopplar symtomet till {sv_d}","en_action":action_en,"sv_action":action_sv,"en_causes":en_causes,"sv_causes":sv_causes}

def make(article_id:int, sv:bool)->dict[str,object]:
    item=item_for(article_id); brand=CODES.get(article_id,FAULTS.get(article_id))[0]
    value=base.make(item,sv)
    value=json.loads(json.dumps(value,ensure_ascii=False).replace("Samsung",brand).replace("samsung",brand))
    value["parts_json"]=[]
    return value

def main()->None:
    backup=json.loads((BASE_DIR/"data/backups/article_reviews/batch-045-p0-core-final-before.json").read_text(encoding="utf-8")); rows={(r["article_id"],r["locale"]):r for r in backup["rows"]}; ids=[*CODES,*FAULTS]
    out={"batch":"045-p0-core-final","status":"proposal_only_not_applied","article_ids":ids,"sources":["https://www.bosch-home.com/us/owner-support/get-support/washers","https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-message-e10-c1-or-emits-1-beep-1-flash","https://www.lg.com/us/support/help-library/lg-washer-error-code-list--20150140270078","https://www.siemens-home.bsh-group.com/uk/customer-service/support/troubleshooting/washing-machines"],"translations":{}}
    for aid in ids:
        it=item_for(aid); out["translations"][str(aid)]={"code":it["subject"],"preserve":{"en_slug":rows[(aid,"en")]["slug"],"sv_slug":rows[(aid,"sv")]["slug"]},"en":make(aid,False),"sv":make(aid,True)}
    path=BASE_DIR/"data/article_reviews/batch-045-p0-core-final-proposal.json"; path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(path)

if __name__=="__main__": main()
