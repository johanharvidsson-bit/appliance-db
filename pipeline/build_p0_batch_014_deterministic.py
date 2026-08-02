"""Build reviewed Electrolux E59/E60/E61/E62/E68 content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {267: "E59", 268: "E60", 269: "E61", 270: "E62", 271: "E68"}

EN = {
    "E59": "official Electrolux documentation identifies E59 as no motor-tachometer signal for three seconds, with possible motor-inverter wiring, inverter-board or motor causes",
    "E60": "Electrolux identifies E60 and other E6-family washing-machine codes as heating problems requiring authorised service",
    "E61": "official Electrolux service documentation identifies E61 as insufficient heating during washing",
    "E62": "official Electrolux service documentation identifies E62 as overheating during washing, documented as temperature above 88°C for more than five minutes",
    "E68": "official Electrolux service documentation identifies E68 as electrical current leakage between the washing heater and earth",
}

SV = {
    "E59": "officiell Electrolux-dokumentation anger att E59 betyder att signal saknas från motorns varvtalsgivare i tre sekunder, med möjliga orsaker i motor–inverter-kablage, inverterkort eller motor",
    "E60": "Electrolux anger att E60 och andra E6-koder på tvättmaskiner gäller värmeproblem som kräver auktoriserad service",
    "E61": "officiell Electrolux-servicedokumentation anger att E61 betyder otillräcklig uppvärmning under tvätt",
    "E62": "officiell Electrolux-servicedokumentation anger att E62 betyder överhettning under tvätt, dokumenterat som temperatur över 88 °C i mer än fem minuter",
    "E68": "officiell Electrolux-servicedokumentation anger att E68 betyder elektriskt läckage mellan tvättvärmaren och jord",
}


def make(code: str, sv: bool) -> dict:
    meaning = (SV if sv else EN)[code]
    urgent = code in {"E62", "E68"}
    action = ("Stäng av omedelbart, dra ur kontakten om området är torrt och säkert, stäng vattenkranen och boka auktoriserad Electrolux-service" if sv else "Switch off immediately, unplug if the area is dry and safe, turn off the water tap and arrange authorised Electrolux service")
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux tvättmaskin felkod {code}: stoppa och boka service",
            "meta_description": f"Visar Electrolux-tvättmaskinen {code}? Läs verifierad betydelse, hur maskinen säkras och varför auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Electrolux-tvättmaskin?",
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Starta inte om för att testa ett motor-, värme-, överhettnings- eller jordfel.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux Washing Machine Error {code}: Stop and Service",
            "meta_description": f"Electrolux washer showing {code}? Check the verified meaning, how to make it safe and why authorised service is required.",
            "h1": f"What Does {code} Mean on an Electrolux Washing Machine?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Do not restart to test a motor, heating, overheating or earth-leakage fault.</p>",
        })
    motor = code == "E59"
    if sv:
        v["causes_json"] = ([
            {"cause": "Utebliven varvtalssignal", "detail": "Electrolux anger att styrsystemet inte får förväntad återkoppling från motorn."},
            {"cause": "Motor–inverter-kablage", "detail": "Interna anslutningar kräver säker kontroll av utbildad tekniker."},
            {"cause": "Inverterkort", "detail": "Effektelektroniken kan behöva modellspecifik diagnos för rätt PNC."},
            {"cause": "Motor", "detail": "Koden ensam bekräftar inte vilken komponent som ska bytas."},
        ] if motor else [
            {"cause": "Dokumenterat värmetillstånd", "detail": meaning.capitalize() + "."},
            {"cause": "Temperaturgivare", "detail": "NTC-sensor eller placering kan påverka temperaturmätningen och kräver intern diagnos."},
            {"cause": "Värmare eller internt kablage", "detail": "Värmekretsen arbetar med nätspänning och ska inte mätas av användaren."},
            {"cause": "Styrkort eller relä", "detail": "Styrning av värmen och jordfelsövervakning kräver rätt servicedata och mätutrustning."},
        ])
    else:
        v["causes_json"] = ([
            {"cause": "Missing speed signal", "detail": "Electrolux states that the control system receives no expected feedback from the motor."},
            {"cause": "Motor-to-inverter wiring", "detail": "Internal connections require safe inspection by a trained technician."},
            {"cause": "Inverter board", "detail": "Power electronics may need model-specific diagnosis for the correct PNC."},
            {"cause": "Motor", "detail": "The code alone does not confirm which component needs replacement."},
        ] if motor else [
            {"cause": "Documented heating condition", "detail": meaning[0].upper() + meaning[1:] + "."},
            {"cause": "Temperature sensor", "detail": "The NTC sensor or its position can affect temperature sensing and needs internal diagnosis."},
            {"cause": "Heater or internal wiring", "detail": "The heating circuit uses mains voltage and is not a user measurement."},
            {"cause": "Control board or relay", "detail": "Heating control and earth-leakage monitoring require the correct service data and equipment."},
        ])
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa omedelbart" if urgent else "Stoppa programmet", "detail": "Vänta tills trumman står stilla. Tvinga inte luckan och försök inte fortsätta programmet."},
        {"step": 2, "action": "Stäng av och koppla ur säkert", "detail": "Dra ur kontakten med torra händer om området är torrt. Finns fukt nära el bryter du strömmen säkert på annan plats."},
        {"step": 3, "action": "Stäng vattenkranen", "detail": "Lämna maskinen utan vatten och ström tills professionell kontroll är utförd."},
        {"step": 4, "action": "Dokumentera kod och PNC", "detail": f"Fotografera hela {code}-visningen och notera PNC-/produktnummer och programfas."},
        {"step": 5, "action": "Starta inte om", "detail": "En återställning bekräftar inte att motor-, värme- eller isolationsfelet är säkert."},
        {"step": 6, "action": "Boka auktoriserad service", "detail": "Uppge PNC och full kod. Ta inte bort paneler och testa inte motor, inverter, värmare, givare eller jordkrets."},
    ] if sv else [
        {"step": 1, "action": "Stop immediately" if urgent else "Stop the programme", "detail": "Wait for the drum to stop. Do not force the door or try to continue the programme."},
        {"step": 2, "action": "Switch off and disconnect safely", "detail": "Unplug with dry hands if the area is dry. If moisture is near electricity, isolate power safely elsewhere."},
        {"step": 3, "action": "Turn off the water tap", "detail": "Leave the washer without water and power until professionally inspected."},
        {"step": 4, "action": "Record the code and PNC", "detail": f"Photograph the complete {code} display and note the PNC/product number and programme stage."},
        {"step": 5, "action": "Do not restart", "detail": "A reset does not confirm that the motor, heating or insulation fault is safe."},
        {"step": 6, "action": "Arrange authorised service", "detail": "Provide the PNC and full code. Do not remove panels or test the motor, inverter, heater, sensor or earth circuit."},
    ])
    v["when_to_call_technician_html"] = (f"<p>{code} kräver auktoriserad Electrolux-service. E62 och E68 är särskilt säkerhetskritiska på grund av överhettning respektive elektriskt läckage mot jord.</p><p>Isolera strömmen säkert vid bränd lukt, rök, onormal värme, läckage nära el eller utlöst elskydd.</p>" if sv else f"<p>{code} requires authorised Electrolux service. E62 and E68 are particularly safety-critical because they concern overheating and electrical leakage to earth.</p><p>Isolate power safely for a burning smell, smoke, abnormal heat, leakage near electricity or tripped protection.</p>")
    v["prevention_html"] = ("<p>Följ last-, installations- och programanvisningarna för exakt PNC och avbryt när en motor- eller värmekod visas.</p><p>Interna motor-, värme- och isolationsfel kan inte förebyggas eller diagnostiseras säkert genom användarunderhåll.</p>" if sv else "<p>Follow load, installation and programme instructions for the exact PNC and stop when a motor or heating code appears.</p><p>Internal motor, heating and insulation faults cannot be safely prevented or diagnosed through user maintenance.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-014-electrolux-e59-e68-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "014-electrolux-e59-e68", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support.electrolux.co.uk/support-articles/article/washer-dryer-displays-error-message-e50-e59-c9-or-f9",
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-message-e60",
        "https://tds.electrolux.com/others/599/724/080EN.PDF",
        "https://tds.electrolux.com/others/599/705/670EN.PDF",
    ], "translations": {}}
    for i, code in ITEMS.items():
        out["translations"][str(i)] = {"code": code, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": make(code, False), "sv": make(code, True)}
    p = BASE_DIR / "data/article_reviews/batch-014-electrolux-e59-e68-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
