"""Build the reviewed nine-article Priority 1 pilot proposal."""
from __future__ import annotations
import json
from config.settings import BASE_DIR, supabase
from pipeline import build_p0_batch_041_deterministic as base

SOURCES={
 "washing-machines":"https://www.samsung.com/uk/support/home-appliances/what-do-the-codes-on-my-washing-machine-mean/",
 "dishwashers":"https://www.samsung.com/uk/support/home-appliances/displayed-information-codes-on-my-dishwasher/",
 "dryers":"https://www.samsung.com/us/support/troubleshoot/TSG10001006/",
}
ITEMS={
 760:("washing-machines","HC","a heating-temperature condition that requires model-specific checks and service if it persists","ett temperaturtillstånd i värmesystemet som kräver modellspecifik kontroll och service om det kvarstår","Stop the cycle and arrange Samsung service if HC returns; do not test the heater","Stoppa programmet och boka Samsung-service om HC återkommer; prova inte värmaren"),
 869:("washing-machines","9C1","a low-voltage or power-supply condition","ett lågspännings- eller strömförsörjningstillstånd","Check the plug and household circuit only from a dry safe position and avoid extension leads","Kontrollera kontakt och bostadens elskydd endast från en torr och säker plats och undvik förlängningssladd"),
 881:("washing-machines","8C","a MEMS or vibration-sensor condition","ett tillstånd för MEMS- eller vibrationsgivaren","Stop the washer, record the full code and restart once only if there is no safety warning","Stoppa maskinen, notera hela koden och starta om en gång endast om inga varningssignaler finns"),
 556:("dishwashers","4C","a water-supply condition","ett tillstånd i vattentillförseln","Open the water supply, check household flow and straighten the visible inlet hose","Öppna vattentillförseln, kontrollera bostadens flöde och räta synlig tilloppsslang"),
 420:("dishwashers","5E","a drainage condition, also displayed as 5C on newer models","ett tömningstillstånd som även visas som 5C på nyare modeller","Switch off, let hot water cool and check the visible drain connection and accessible filter by the model manual","Stäng av, låt hett vatten svalna och kontrollera synlig avloppsanslutning samt åtkomligt filter enligt modellmanualen"),
 523:("dishwashers","LC","a leak check has been triggered","en läckagekontroll har aktiverats","Close the water valve, isolate dishwasher power safely and do not run it again until the leak is assessed","Stäng vattenventilen, bryt strömmen till diskmaskinen säkert och kör den inte igen förrän läckaget bedömts"),
 568:("dryers","DE","the dryer detects an open or improperly closed door","torktumlaren registrerar en öppen eller felaktigt stängd lucka","Remove trapped laundry and close the door firmly without forcing the latch","Ta bort fastklämd tvätt och stäng luckan ordentligt utan att tvinga låset"),
 566:("dryers","TE","an air-temperature sensor condition","ett tillstånd för lufttemperaturgivaren","Clean the lint filter and check the user-accessible vent path, then request service if TE returns","Rengör luddfiltret och kontrollera användaråtkomlig ventilationsväg och boka service om TE återkommer"),
 567:("dryers","HE","a high-temperature or heating condition","ett högtemperatur- eller värmetillstånd","Stop the dryer, clean the lint filter and visible vent path, and do not continue if it overheats","Stoppa torktumlaren, rengör luddfilter och synlig ventilationsväg och fortsätt inte om den överhettas"),
}

def make(aid:int,sv:bool)->dict:
    category,code,en_m,sv_m,en_a,sv_a=ITEMS[aid]; appliance={"washing-machines":"washing machine","dishwashers":"dishwasher","dryers":"dryer"}[category]; sv_appliance={"washing-machines":"tvättmaskin","dishwashers":"diskmaskin","dryers":"torktumlare"}[category]
    item={"type":"code","subject":code,"en_title":f"What Does {code} Mean on a Samsung {appliance.title()}?","sv_title":f"Vad betyder {code} på en Samsung-{sv_appliance}?","en_meaning":f"Samsung identifies {code} as {en_m}","sv_meaning":f"Samsung anger att {code} betyder {sv_m}","en_action":en_a,"sv_action":sv_a,"en_causes":["External installation or operating condition","Blocked or restricted user-accessible path","Model-specific sensor or control condition","Internal fault requiring Samsung service"],"sv_causes":["Yttre installations- eller driftstillstånd","Blockerad eller hindrad användaråtkomlig väg","Modellspecifikt givar- eller styrtillstånd","Internt fel som kräver Samsung-service"]}
    value=base.make(item,sv); value["parts_json"]=[]; value["symptoms_json"]=[]; value["affected_models_json"]=[]
    sv_slug_appliance={"washing-machines":"tvattmaskin","dishwashers":"diskmaskin","dryers":"torktumlare"}[category]
    value["slug"]=(f"samsung-{sv_slug_appliance}-felkod-{code.lower()}" if sv else f"samsung-{appliance.replace(' ','-')}-error-code-{code.lower()}")
    value["translation_status"]="pending" if sv else "published"; value["source_locale"]="en"; value["translated_by"]="hybrid"; return value

def main()->None:
    ids=list(ITEMS); current=supabase.table("error_codes").select("id,code,brand_id,category_id,short_description,description,severity,diy_possible,source,last_verified_at,scrape_status").in_("id",ids).order("id").execute().data or []
    out={"batch":"p1-pilot-nine","classification":"A-after-official-source-review","error_code_ids":ids,"sources":SOURCES,"current_error_codes":current,"entries":{}}
    for aid in ids:
        category,code,*_=ITEMS[aid]; out["entries"][str(aid)]={"brand":"samsung","category":category,"code":code,"classification":"A","source":SOURCES[category],"uncertainties":["Meaning and user sequence may vary by model; exact model manual controls"],"en":make(aid,False),"sv":make(aid,True)}
    path=BASE_DIR/"data/article_reviews/p1-pilot-nine-proposal.json"; path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8"); print(path)
if __name__=="__main__": main()
