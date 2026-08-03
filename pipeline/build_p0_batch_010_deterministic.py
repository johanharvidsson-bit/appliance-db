"""Build reviewed Bosch safety faults and Electrolux E20/E23 content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {325: "CYCLE", 328: "ELECTRICS", 329: "BURNING", 248: "E20", 250: "E23"}


def base(subject: str, meaning: str, action: str, sv: bool) -> dict:
    v = build_sv(subject, meaning, action) if sv else build_en(subject, meaning, action)
    v["parts_json"] = []
    return v


def electrolux(code: str, sv: bool) -> dict:
    drain = code == "E20"
    if sv:
        meaning = ("Electrolux anger att E20, E21 eller C2 betyder ett tömningsproblem" if drain else "Electrolux servicedokumentation anger att E23 är ett fel i den elektroniska styrningen av avloppspumpen")
        action = ("Stäng av, dra ur kontakten, låt hett vatten svalna och kontrollera avloppsslang, hushållsavlopp och användaråtkomligt pumpfilter exakt enligt modellmanualen" if drain else "Stäng av, dra ur kontakten och boka auktoriserad Electrolux-service; öppna inte maskinen och testa inte pump eller elektronik")
        v = base(code, meaning, action, True)
        v.update({
            "title_tag": f"Electrolux tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Electrolux-tvättmaskinen {code}? Läs verifierad betydelse, säkra kontroller och när du ska avbryta och boka auktoriserad service.",
            "h1": f"Vad betyder {code} på en Electrolux-tvättmaskin?",
            "description": meaning + ".",
            "quick_fix": action + " (cirka 10–30 minuter).",
            "intro_html": f"<p>{meaning}. E20 kan ofta spåras till avloppsinstallation eller ett användaråtkomligt filter, medan E23 är ett internt elektroniskt pumpstyrningsfel.</p><p>{action}. Dokumentera full kod och produktnummer innan kontakt med service.</p>",
        })
        v["causes_json"] = ([
            {"cause": "Vikt eller felplacerad avloppsslang", "detail": "Electrolux anger att slangens insticksdjup och höjd ska följa installationsmanualen."},
            {"cause": "Blockerat avlopp eller pumpfilter", "detail": "Ludd eller främmande föremål kan hindra tömningen; öppna aldrig filtret medan maskinen går eller vattnet är varmt."},
            {"cause": "För mycket skum", "detail": "Överdosering kan störa nivåsystemet och tömningen."},
            {"cause": "Pump- eller internt fel", "detail": "Om säkra kontroller inte hjälper krävs auktoriserad diagnos."},
        ] if drain else [
            {"cause": "Elektronisk pumpstyrning", "detail": "Electrolux servicedokumentation definierar E23 som fel i den komponent som styr avloppspumpen."},
            {"cause": "Modellspecifik elektronik", "detail": "Kretsutförandet beror på produktnummer och ska diagnostiseras med rätt servicedata."},
            {"cause": "Pumpkrets som kräver mätning", "detail": "Pump, ledningar och styrkort sitter bakom paneler och ska inte testas av användaren."},
            {"cause": "Kvarstående säkerhetsfel", "detail": "En återställning bekräftar inte att styrfelet är reparerat."},
        ])
    else:
        meaning = ("Electrolux identifies E20, E21 or C2 as a water-drainage problem" if drain else "Electrolux service documentation identifies E23 as a malfunction in the electronic component controlling the drain pump")
        action = ("Switch off, unplug, let hot water cool and check the drain hose, household drain and user-accessible pump filter exactly as the model manual describes" if drain else "Switch off, unplug and arrange authorised Electrolux service; do not open the washer or test the pump or electronics")
        v = base(code, meaning, action, False)
        v.update({
            "title_tag": f"Electrolux Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Electrolux washer showing {code}? Check the verified meaning, safe user actions and when to stop and arrange authorised service.",
            "h1": f"What Does {code} Mean on an Electrolux Washing Machine?",
            "description": meaning + ".",
            "quick_fix": action + " (about 10–30 minutes).",
            "intro_html": f"<p>{meaning}. E20 can often be traced to the drain installation or a user-accessible filter, while E23 is an internal electronic pump-control fault.</p><p>{action}. Record the complete code and product number before contacting service.</p>",
        })
        v["causes_json"] = ([
            {"cause": "Kinked or incorrectly positioned drain hose", "detail": "Electrolux specifies that insertion depth and drain height must follow the installation manual."},
            {"cause": "Blocked drain or pump filter", "detail": "Lint or foreign objects can stop drainage; never open the filter while the washer runs or water is hot."},
            {"cause": "Excess foam", "detail": "Detergent overdosing can interfere with level sensing and drainage."},
            {"cause": "Pump or internal fault", "detail": "If safe checks do not help, authorised diagnosis is required."},
        ] if drain else [
            {"cause": "Electronic pump control", "detail": "Electrolux service documentation defines E23 as a fault in the component controlling the drain pump."},
            {"cause": "Model-specific electronics", "detail": "Circuit design depends on the product number and requires the correct service data."},
            {"cause": "Pump circuit requiring measurement", "detail": "The pump, wiring and control board are behind panels and are not user tests."},
            {"cause": "Persistent safety fault", "detail": "A reset does not prove that the control fault has been repaired."},
        ])
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa programmet säkert", "detail": "Vänta tills trumman står stilla. Tvinga inte luckan och töm inte vatten som kan vara varmt."},
        {"step": 2, "action": "Stäng av och dra ur kontakten", "detail": "Koppla bort maskinen med torra händer på en torr plats."},
        {"step": 3, "action": "Dokumentera kod och produktnummer", "detail": f"Fotografera hela {code}-visningen och notera PNC eller produktnummer från typskylten."},
        {"step": 4, "action": "Följ rätt modellmanual", "detail": action + "."},
        {"step": 5, "action": "Kontrollera efter läckage", "detail": "Återanslut bara om alla åtkomliga anslutningar är täta och torra och manualen medger test."},
        {"step": 6, "action": "Boka auktoriserad service", "detail": "Boka service om koden kvarstår, om maskinen inte tömmer eller om E23 visas. Ta inte bort paneler."},
    ] if sv else [
        {"step": 1, "action": "Stop the programme safely", "detail": "Wait for the drum to stop. Do not force the door or drain water that may be hot."},
        {"step": 2, "action": "Switch off and unplug", "detail": "Disconnect the washer with dry hands from a dry location."},
        {"step": 3, "action": "Record the code and product number", "detail": f"Photograph the complete {code} display and note the PNC or product number from the rating plate."},
        {"step": 4, "action": "Follow the exact model manual", "detail": action + "."},
        {"step": 5, "action": "Check for leakage", "detail": "Reconnect only if all accessible connections are watertight and dry and the manual permits a test."},
        {"step": 6, "action": "Arrange authorised service", "detail": "Request service if the code remains, the washer will not drain or E23 is displayed. Do not remove panels."},
    ])
    v["when_to_call_technician_html"] = ("<p>E23 kräver auktoriserad service. För E20 bokar du service om tömningen inte fungerar efter modellmanualens säkra kontroller eller om koden återkommer.</p><p>Avbryt direkt vid läckage nära el, bränd lukt, rök, onormal värme eller utlöst säkring.</p>" if sv else "<p>E23 requires authorised service. For E20, request service if drainage does not work after the model manual's safe checks or the code returns.</p><p>Stop immediately for leakage near electricity, a burning smell, smoke, abnormal heat or a tripped supply.</p>")
    v["prevention_html"] = ("<p>Installera avloppsslangen enligt manualen, töm fickor, dosera tvättmedel korrekt och rengör ett externt pumpfilter med det intervall Electrolux anger.</p><p>Interna styrfel kan inte förebyggas eller diagnostiseras genom användarunderhåll.</p>" if sv else "<p>Install the drain hose as instructed, empty pockets, dose detergent correctly and clean an external pump filter at the interval Electrolux specifies.</p><p>Internal control faults cannot be prevented or diagnosed through user maintenance.</p>")
    v["parts_json"] = []
    return v


def bosch(kind: str, sv: bool) -> dict:
    profiles = {
        "CYCLE": {
            False: ("the programme does not complete, which can result from a selected delay or rinse hold, water-supply or drainage problem, load imbalance or a displayed fault", "Record where the programme stops and any display message, then check only the exact manual's load, water-supply and drainage steps"),
            True: ("programmet inte slutförs, vilket kan bero på vald fördröjning eller sköljstopp, problem med vattenintag eller tömning, lastobalans eller visat fel", "Dokumentera var programmet stannar och displaymeddelandet och kontrollera endast manualens last-, vatten- och tömningssteg"),
        },
        "ELECTRICS": {
            False: ("the washer is tripping the electrical protection; Bosch lists possible internal causes including motor, heater, suppressor, shorted wiring or water on an electrical part", "Do not reset the protection repeatedly or use the washer; switch off, unplug if dry and safe, and arrange a qualified Bosch engineer"),
            True: ("tvättmaskinen löser ut elskyddet; Bosch anger möjliga interna orsaker som motor, värmare, störningsskydd, kortslutet kablage eller vatten på en elektrisk del", "Återställ inte elskyddet upprepade gånger och använd inte maskinen; stäng av, dra ur kontakten om det är torrt och säkert och boka kvalificerad Bosch-tekniker"),
        },
        "BURNING": {
            False: ("a charred or burning smell is a stop-use safety symptom, not the normal stale or drain odour covered by cleaning advice", "Switch the washer off immediately, disconnect power only if safely accessible and dry, ventilate the area and contact Bosch service"),
            True: ("bränd eller svedd lukt är ett säkerhetssymptom som kräver att användningen stoppas och ska inte förväxlas med vanlig unken lukt eller avloppslukt", "Stäng av maskinen omedelbart, bryt strömmen endast om det är torrt och säkert, vädra och kontakta Bosch-service"),
        },
    }
    meaning, action = profiles[kind][sv]
    label = {"CYCLE": ("slutför inte programmet" if sv else "won't complete a cycle"), "ELECTRICS": ("löser ut säkringen" if sv else "trips the electrics"), "BURNING": ("bränd lukt" if sv else "burning smell")}[kind]
    v = base(label, meaning, action, sv)
    if sv:
        titles = {"CYCLE": "Bosch tvättmaskin slutför inte programmet: felsök säkert", "ELECTRICS": "Bosch tvättmaskin löser ut säkringen: stoppa säkert", "BURNING": "Bränd lukt från Bosch tvättmaskin: stäng av direkt"}
        h1s = {"CYCLE": "Varför slutför inte Bosch-tvättmaskinen programmet?", "ELECTRICS": "Varför löser Bosch-tvättmaskinen ut säkringen?", "BURNING": "Vad gör jag vid bränd lukt från Bosch-tvättmaskinen?"}
        v.update({"title_tag": titles[kind], "meta_description": "Verifierade Bosch-råd, säkra kontroller och tydliga stoppsignaler för tvättmaskinsproblem. Ta inte bort paneler eller testa interna eldelar.", "h1": h1s[kind], "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5 minuter).", "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Dokumentera E‑Nr, programfas och eventuella koder utan att öppna maskinen.</p>"})
    else:
        titles = {"CYCLE": "Bosch Washer Won't Complete a Cycle: Safe Checks", "ELECTRICS": "Bosch Washer Trips the Electrics: Stop Using It", "BURNING": "Burning Smell from Bosch Washer: Switch Off Now"}
        h1s = {"CYCLE": "Why Won't My Bosch Washing Machine Complete a Cycle?", "ELECTRICS": "Why Does My Bosch Washing Machine Trip the Electrics?", "BURNING": "What Should I Do About a Burning Smell from My Bosch Washer?"}
        v.update({"title_tag": titles[kind], "meta_description": "Verified Bosch guidance, safe checks and clear stop-use warnings for washing machine problems. Do not remove panels or test internal electrics.", "h1": h1s[kind], "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5 minutes).", "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Record the E-Nr, programme stage and any code without opening the washer.</p>"})
    urgent = kind in {"ELECTRICS", "BURNING"}
    if sv:
        v["causes_json"] = ([
            {"cause": "Programinställning eller fördröjning", "detail": "Finish in, sköljstopp eller ett program som förlängs av lastdetektering kan uppfattas som stopp."},
            {"cause": "Vattenintag eller tömning", "detail": "Stängd kran, vikt slang eller blockerad användaråtkomlig pump kan hindra programförloppet."},
            {"cause": "Obalanserad last", "detail": "Maskinen kan göra upprepade fördelningsförsök eller avbryta centrifugeringen."},
            {"cause": "Visat eller internt fel", "detail": "Dokumentera koden; kvarstående stopp kräver Bosch-service."},
        ] if kind == "CYCLE" else [
            {"cause": "Elektriskt eller värmerelaterat fel", "detail": "Bosch anger flera möjliga interna orsaker; symptomet kan inte diagnostiseras säkert av användaren."},
            {"cause": "Skadat kablage eller komponent", "detail": "Kortslutning, överhettning eller isolationsfel kräver fackmässig mätning."},
            {"cause": "Fukt eller läckage nära el", "detail": "Rör inte stickpropp eller uttag om området är vått; bryt strömmen säkert på annan plats."},
            {"cause": "Överhettning eller bränd lukt", "detail": "Fortsatt användning kan förvärra skadan och ska inte testas med ett nytt program."},
        ])
    else:
        v["causes_json"] = ([
            {"cause": "Programme setting or delay", "detail": "Finish-in, rinse hold or load sensing that extends a programme can look like a stall."},
            {"cause": "Water supply or drainage", "detail": "A closed tap, kinked hose or blocked user-accessible pump can stop progress."},
            {"cause": "Unbalanced load", "detail": "The washer may repeat redistribution attempts or cancel the spin."},
            {"cause": "Displayed or internal fault", "detail": "Record the code; a persistent stop needs Bosch service."},
        ] if kind == "CYCLE" else [
            {"cause": "Electrical or heating-related fault", "detail": "Bosch lists several possible internal causes; the symptom is not a safe user diagnosis."},
            {"cause": "Damaged wiring or component", "detail": "A short circuit, overheating or insulation fault requires qualified measurement."},
            {"cause": "Moisture or leakage near electricity", "detail": "Do not touch the plug or socket if wet; isolate power safely elsewhere."},
            {"cause": "Overheating or charred odour", "detail": "Continued use can worsen damage and must not be tested with another programme."},
        ])
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa omedelbart" if urgent else "Pausa säkert", "detail": "Vänta tills trumman står stilla och tvinga inte upp luckan."},
        {"step": 2, "action": "Säkra ström och vatten", "detail": action + "."},
        {"step": 3, "action": "Dokumentera", "detail": "Fotografera displayen och anteckna E‑Nr, programfas, ljud, lukt och om elskydd utlöstes."},
        {"step": 4, "action": "Följ bara rätt manual", "detail": "Gör endast yttre användarkontroller som anges för exakt modell."},
        {"step": 5, "action": "Starta inte om vid säkerhetssymptom", "detail": "Vid bränd lukt eller utlöst elskydd ska maskinen förbli bortkopplad tills den kontrollerats."},
        {"step": 6, "action": "Boka Bosch-service", "detail": "Uppge E‑Nr och observationerna. Ta inte bort paneler och testa inte interna komponenter."},
    ] if sv else [
        {"step": 1, "action": "Stop immediately" if urgent else "Pause safely", "detail": "Wait for the drum to stop and do not force the door."},
        {"step": 2, "action": "Make power and water safe", "detail": action + "."},
        {"step": 3, "action": "Record the evidence", "detail": "Photograph the display and note the E-Nr, programme stage, noises, odour and whether protection tripped."},
        {"step": 4, "action": "Follow only the exact manual", "detail": "Perform only external user checks specified for the exact model."},
        {"step": 5, "action": "Do not restart after a safety symptom", "detail": "For a burning smell or tripped protection, keep the washer disconnected until inspected."},
        {"step": 6, "action": "Arrange Bosch service", "detail": "Provide the E-Nr and observations. Do not remove panels or test internal components."},
    ])
    v["when_to_call_technician_html"] = ("<p>Bränd lukt och återkommande utlöst elskydd kräver omedelbart stopp och Bosch-service. Ett program som upprepade gånger inte slutförs efter manualens yttre kontroller kräver också diagnos.</p><p>Ta inte bort paneler eller kontrollera motor, värmare, störningsskydd, ledningar, pump eller styrkort själv.</p>" if sv else "<p>A burning smell and repeatedly tripped electrical protection require immediate stop-use and Bosch service. A programme that repeatedly fails after the manual's external checks also needs diagnosis.</p><p>Do not remove panels or inspect the motor, heater, suppressor, wiring, pump or control board yourself.</p>")
    v["prevention_html"] = ("<p>Följ last-, installations- och underhållsanvisningarna för exakt E‑Nr och håll synliga slanganslutningar torra och oskadade.</p><p>Interna elfel och överhettning kan inte förebyggas eller diagnostiseras säkert genom användarunderhåll.</p>" if sv else "<p>Follow load, installation and maintenance instructions for the exact E-Nr and keep visible hose connections dry and undamaged.</p><p>Internal electrical faults and overheating cannot be safely prevented or diagnosed by user maintenance.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-010-bosch-safety-electrolux-e20-e23-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "010-bosch-safety-electrolux-e20-e23", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.bosch-home.com/ae/en/customer-service/get-support/washing-machine-trips-the-electrics",
        "https://www.bosch-home.com/ae/en/customer-service/get-support/why-does-my-washing-machine-smell",
        "https://www.bosch-home.com/ne/service/get-support/get_support_st4/get_support_st4_washing_machines_static_page",
        "https://support.electrolux.co.uk/support-articles/article/washer-dryer-displays-error-message-e20-or-c2-emits-2-beeps-or-2-flashes",
        "https://tds.electrolux.com/others/599/705/670EN.PDF",
    ], "translations": {}}
    for i, kind in ITEMS.items():
        en = electrolux(kind, False) if kind in {"E20", "E23"} else bosch(kind, False)
        sv = electrolux(kind, True) if kind in {"E20", "E23"} else bosch(kind, True)
        out["translations"][str(i)] = {"code": kind, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": en, "sv": sv}
    p = BASE_DIR / "data/article_reviews/batch-010-bosch-safety-electrolux-e20-e23-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
