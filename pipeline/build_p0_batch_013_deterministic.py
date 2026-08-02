"""Build reviewed Electrolux E45/E50/E51/E52/E54 service content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {261: "E45", 262: "E50", 263: "E51", 264: "E52", 265: "E54"}

EN = {
    "E45": "official Electrolux service documentation identifies E45 as a fault in the sensing circuit for the electronic component that operates the door interlock",
    "E50": "Electrolux identifies E50 as a motor-fault family and advises stopping use until an authorised technician has repaired the appliance",
    "E51": "official Electrolux service documentation identifies E51 as a short-circuited motor power-control triac or related motor, wiring or control-board fault",
    "E52": "official Electrolux service documentation identifies E52 as no signal from the motor tachometer generator, with possible motor, wiring or control-board causes",
    "E54": "official Electrolux service documentation identifies E54 as motor-relay contacts sticking, with voltage potentially present in the motor circuit when it should be inactive",
}

SV = {
    "E45": "officiell Electrolux-servicedokumentation anger att E45 är ett fel i avkänningskretsen för den elektroniska komponent som aktiverar lucklåset",
    "E50": "Electrolux anger att E50 tillhör motorfelen och rekommenderar att apparaten inte används innan en auktoriserad tekniker har reparerat den",
    "E51": "officiell Electrolux-servicedokumentation anger att E51 betyder kortsluten effekttriac för motorn eller relaterat fel i motor, kablage eller styrkort",
    "E52": "officiell Electrolux-servicedokumentation anger att E52 betyder att signal saknas från motorns varvtalsgivare, med möjliga orsaker i motor, kablage eller styrkort",
    "E54": "officiell Electrolux-servicedokumentation anger att E54 betyder att motorreläets kontakter har fastnat och att spänning kan finnas i motorkretsen när den ska vara inaktiv",
}


def make(code: str, sv: bool) -> dict:
    meaning = (SV if sv else EN)[code]
    action = ("Stäng av, dra ur kontakten, stäng vattenkranen och boka auktoriserad Electrolux-service; använd inte maskinen och öppna inga paneler" if sv else "Switch off, unplug, turn off the water tap and arrange authorised Electrolux service; do not use the washer or remove any panels")
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux tvättmaskin felkod {code}: stoppa och boka service",
            "meta_description": f"Visar Electrolux-tvättmaskinen {code}? Läs verifierad betydelse, hur maskinen säkras och varför auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Electrolux-tvättmaskin?",
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Koden gäller ett internt lås-, motor- eller styrfel och är inte en uppmaning till användaren att mäta eller byta delar.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux Washing Machine Error {code}: Stop and Service",
            "meta_description": f"Electrolux washer showing {code}? Check the verified meaning, how to make the washer safe and why authorised service is required.",
            "h1": f"What Does {code} Mean on an Electrolux Washing Machine?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. This is an internal lock, motor or control fault, not a prompt for a user to measure or replace parts.</p>",
        })
    door = code == "E45"
    if sv:
        v["causes_json"] = ([
            {"cause": "Lucklåsets avkänningskrets", "detail": "Electrolux anger att fel signal når styrsystemet från kretsen som aktiverar lucklåset."},
            {"cause": "Styrkort", "detail": "Servicedokumentationen placerar diagnosen i intern elektronik och kräver rätt PNC och plattform."},
            {"cause": "Internt kablage eller anslutning", "detail": "Anslutningar bakom paneler ska endast kontrolleras av utbildad tekniker."},
            {"cause": "Kvarstående säkerhetsspärr", "detail": "Lucklåset får aldrig förbikopplas eller tvingas för att köra maskinen."},
        ] if door else [
            {"cause": "Motor- eller drivkrets", "detail": meaning.capitalize() + "."},
            {"cause": "Internt kablage", "detail": "Skadade eller felaktiga anslutningar kan påverka motorstyrning och återkoppling."},
            {"cause": "Styrkort eller effektelektronik", "detail": "E51 och E54 gäller elektriska kopplingstillstånd som kräver säker mätning."},
            {"cause": "Motor eller varvtalsgivare", "detail": "E52 gäller utebliven återkopplingssignal; koden ensam bekräftar inte vilken del som ska bytas."},
        ])
    else:
        v["causes_json"] = ([
            {"cause": "Door-interlock sensing circuit", "detail": "Electrolux identifies an incorrect signal in the circuit that operates the door interlock."},
            {"cause": "Control board", "detail": "Service documentation places diagnosis in internal electronics and requires the correct PNC and platform."},
            {"cause": "Internal wiring or connection", "detail": "Connections behind panels must be checked only by a trained technician."},
            {"cause": "Persistent safety interlock", "detail": "Never bypass or force the door lock to run the washer."},
        ] if door else [
            {"cause": "Motor or drive circuit", "detail": meaning[0].upper() + meaning[1:] + "."},
            {"cause": "Internal wiring", "detail": "Damaged or incorrect connections can affect motor control and feedback."},
            {"cause": "Control board or power electronics", "detail": "E51 and E54 concern electrical switching states that require safe measurement."},
            {"cause": "Motor or tachometer", "detail": "E52 concerns missing speed feedback; the code alone does not confirm which part needs replacement."},
        ])
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa programmet", "detail": "Vänta tills trumman står stilla. Tvinga inte upp luckan och försök inte starta ett nytt program."},
        {"step": 2, "action": "Stäng av och koppla ur", "detail": "Dra ur kontakten med torra händer om uttag och område är torra. Bryt annars strömmen säkert på annan plats."},
        {"step": 3, "action": "Stäng vattenkranen", "detail": "Lämna maskinen avstängd och utan vattentillförsel tills den har bedömts."},
        {"step": 4, "action": "Dokumentera kod och PNC", "detail": f"Fotografera hela {code}-visningen och notera PNC-/produktnummer från typskylten."},
        {"step": 5, "action": "Starta inte om", "detail": "En återställning är inte bevis på att ett motor-, lås- eller elektriskt styrfel är säkert."},
        {"step": 6, "action": "Boka auktoriserad service", "detail": "Uppge PNC, kod och programfas. Ta inte bort paneler och testa inte motor, lås, kablage eller kort."},
    ] if sv else [
        {"step": 1, "action": "Stop the programme", "detail": "Wait for the drum to stop. Do not force the door or attempt another programme."},
        {"step": 2, "action": "Switch off and disconnect", "detail": "Unplug with dry hands if the outlet and area are dry. Otherwise isolate power safely elsewhere."},
        {"step": 3, "action": "Turn off the water tap", "detail": "Leave the washer switched off and without a water supply until assessed."},
        {"step": 4, "action": "Record the code and PNC", "detail": f"Photograph the complete {code} display and note the PNC/product number from the rating plate."},
        {"step": 5, "action": "Do not restart", "detail": "A reset is not proof that a motor, lock or electrical control fault is safe."},
        {"step": 6, "action": "Arrange authorised service", "detail": "Provide the PNC, code and programme stage. Do not remove panels or test the motor, lock, wiring or board."},
    ])
    v["when_to_call_technician_html"] = (f"<p>{code} kräver auktoriserad Electrolux-service. Lämna maskinen avstängd och bortkopplad tills den är professionellt kontrollerad.</p><p>Avbryt omedelbart och isolera strömmen säkert vid bränd lukt, rök, onormal värme, läckage nära el eller utlöst elskydd.</p>" if sv else f"<p>{code} requires authorised Electrolux service. Leave the washer switched off and disconnected until professionally inspected.</p><p>Stop immediately and isolate power safely for a burning smell, smoke, abnormal heat, leakage near electricity or tripped protection.</p>")
    v["prevention_html"] = ("<p>Följ lastgränser, installation och underhåll för exakt PNC och stoppa maskinen när ett motor- eller låsfel visas.</p><p>Interna elektroniska fel, reläfel och givarfel kan inte förebyggas eller diagnostiseras säkert med användarunderhåll.</p>" if sv else "<p>Follow load limits, installation and maintenance for the exact PNC and stop the washer when a motor or lock fault appears.</p><p>Internal electronic, relay and sensor faults cannot be safely prevented or diagnosed by user maintenance.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-013-electrolux-e45-e54-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "013-electrolux-e45-e54", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-message-e50",
        "https://tds.electrolux.com/others/599/705/670EN.PDF",
        "https://tds.electrolux.com/others/599/724/080EN.PDF",
    ], "translations": {}}
    for i, code in ITEMS.items():
        out["translations"][str(i)] = {"code": code, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": make(code, False), "sv": make(code, True)}
    p = BASE_DIR / "data/article_reviews/batch-013-electrolux-e45-e54-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
