"""Build reviewed Electrolux E38/E40/E41/E42/E44 content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {256: "E38", 257: "E40", 258: "E41", 259: "E42", 260: "E44"}

EN = {
    "E38": ("official Electrolux service documentation identifies E38 as a blocked pressure chamber or no detected water-level change during drum rotation", "Switch off, unplug and arrange authorised Electrolux service; do not open the washer or inspect the pressure system or drive belt"),
    "E40": ("Electrolux identifies E40 as a door or lid that is not properly closed or detected", "Remove laundry trapped at the seal, reduce an overloaded drum and close the door firmly until the lock clicks"),
    "E41": ("Electrolux identifies E41 as a door-open or door-not-detected condition after the programme attempts to start", "Remove trapped laundry, reduce the load and close the door firmly; if E41 remains, arrange authorised service"),
    "E42": ("official Electrolux service documentation identifies E42 as a door-closure problem involving the interlock, wiring or control system", "Check only for trapped laundry and correct external closure, then switch off, unplug and arrange authorised Electrolux service if E42 remains"),
    "E44": ("official Electrolux service documentation identifies E44 as a fault in the door-interlock sensing circuit", "Switch off, unplug and arrange authorised Electrolux service; do not bypass the lock or test wiring or the control board"),
}

SV = {
    "E38": ("officiell Electrolux-servicedokumentation anger att E38 betyder blockerad tryckkammare eller att ingen förändring av vattennivån registreras under trumrotation", "Stäng av, dra ur kontakten och boka auktoriserad Electrolux-service; öppna inte maskinen och kontrollera inte trycksystem eller drivrem"),
    "E40": ("Electrolux anger att E40 betyder att luckan eller locket inte är korrekt stängt eller registrerat", "Ta bort tvätt som fastnat vid tätningen, minska en överfull last och stäng luckan bestämt tills låset klickar"),
    "E41": ("Electrolux anger att E41 betyder att luckan är öppen eller inte registreras efter att programmet försökt starta", "Ta bort fastnad tvätt, minska lasten och stäng luckan bestämt; kvarstår E41 bokar du auktoriserad service"),
    "E42": ("officiell Electrolux-servicedokumentation anger att E42 är ett luckstängningsproblem som kan beröra lås, kablage eller styrsystem", "Kontrollera endast fastnad tvätt och korrekt yttre stängning och stäng sedan av, dra ur kontakten och boka auktoriserad service om E42 kvarstår"),
    "E44": ("officiell Electrolux-servicedokumentation anger att E44 är ett fel i lucklåsets avkänningskrets", "Stäng av, dra ur kontakten och boka auktoriserad Electrolux-service; förbikoppla inte låset och testa inte kablage eller styrkort"),
}


def make(code: str, sv: bool) -> dict:
    meaning, action = (SV if sv else EN)[code]
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Electrolux-tvättmaskinen {code}? Läs verifierad betydelse, säkra luckkontroller och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Electrolux-tvättmaskin?",
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Tvinga inte luckan, förbikoppla inte säkerhetslåset och beställ inte en del från koden ensam.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Electrolux washer showing {code}? Check the verified meaning, safe door checks and when authorised service is required.",
            "h1": f"What Does {code} Mean on an Electrolux Washing Machine?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Do not force the door, bypass the safety lock or order a part from the code alone.</p>",
        })
    user_door = code in {"E40", "E41"}
    internal_door = code in {"E42", "E44"}
    if sv:
        v["causes_json"] = ([
            {"cause": "Tvätt har fastnat i lucköppningen", "detail": "Ett plagg mellan tätning och glas kan hindra luckan från att stängas och låsas."},
            {"cause": "Överfull trumma", "detail": "Tvätt som trycker mot luckan kan hindra korrekt låsning."},
            {"cause": "Mekaniskt barnlås eller modellinställning", "detail": "Kontrollera endast enligt manualen för exakt PNC-/produktnummer."},
            {"cause": "Defekt lucklås eller registrering", "detail": "Om den yttre kontrollen inte hjälper krävs auktoriserad diagnos."},
        ] if user_door else ([
            {"cause": "Lucklåsets avkänningskrets", "detail": "Electrolux servicedokumentation placerar felet i låsregistrering eller styrkrets."},
            {"cause": "Lucklås eller kablage", "detail": "E42 kan beröra lås, interna anslutningar eller styrsystem."},
            {"cause": "Styrkort", "detail": "E44 är en intern avkänningskrets och ska diagnostiseras med rätt servicedata."},
            {"cause": "Kvarstående säkerhetsspärr", "detail": "Maskinen ska inte köras genom att låset pressas eller förbikopplas."},
        ] if internal_door else [
            {"cause": "Blockerad tryckkammare", "detail": "Electrolux anger att vattennivån inte ändras som förväntat under trumrotation."},
            {"cause": "Trycksystemets hydrauliska väg", "detail": "Intern slang eller kammare kan vara blockerad och kräver servicetillgång."},
            {"cause": "Drivrem eller utebliven trumrotation", "detail": "Vissa dokumenterade orsaker hör till drivsystemet och ska inte inspekteras av användaren."},
            {"cause": "Sensor-, kablage- eller styrfel", "detail": "PNC behövs för korrekt teknisk diagnos."},
        ]))
    else:
        v["causes_json"] = ([
            {"cause": "Laundry trapped in the door opening", "detail": "An item between the seal and glass can prevent closing and locking."},
            {"cause": "Overloaded drum", "detail": "Laundry pressing against the door can stop the lock engaging correctly."},
            {"cause": "Mechanical child lock or model setting", "detail": "Check only by the manual for the exact PNC/product number."},
            {"cause": "Faulty door lock or detection", "detail": "If the external check does not help, authorised diagnosis is required."},
        ] if user_door else ([
            {"cause": "Door-lock sensing circuit", "detail": "Electrolux service documentation places the fault in lock detection or its control circuit."},
            {"cause": "Door interlock or wiring", "detail": "E42 may involve the lock, internal connections or control system."},
            {"cause": "Control board", "detail": "E44 is an internal sensing circuit and requires the correct service data."},
            {"cause": "Persistent safety interlock", "detail": "Do not run the washer by forcing or bypassing the lock."},
        ] if internal_door else [
            {"cause": "Blocked pressure chamber", "detail": "Electrolux states that water level does not change as expected during drum rotation."},
            {"cause": "Pressure-system hydraulic path", "detail": "An internal hose or chamber may be blocked and requires service access."},
            {"cause": "Drive belt or absent drum rotation", "detail": "Some documented causes involve the drive and are not user inspections."},
            {"cause": "Sensor, wiring or control fault", "detail": "The PNC is needed for correct technical diagnosis."},
        ]))
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa och vänta", "detail": "Vänta tills trumman står stilla. Tvinga inte upp en låst lucka och öppna inte om vatten syns."},
        {"step": 2, "action": "Dokumentera kod och PNC", "detail": f"Fotografera hela {code}-visningen och notera PNC-/produktnummer från typskylten."},
        {"step": 3, "action": "Kontrollera luckan utvändigt", "detail": "Ta bort synligt fastnad tvätt, minska överlast och kontrollera tätningen utan verktyg."},
        {"step": 4, "action": "Följ rätt modellmanual", "detail": action + "."},
        {"step": 5, "action": "Gör högst ett säkert test", "detail": "Testa endast E40/E41 en gång efter korrekt stängning och bara om maskinen är torr och manualen medger det."},
        {"step": 6, "action": "Boka auktoriserad service", "detail": "Boka service om koden kvarstår och direkt för E38 eller interna E42/E44. Ta inte bort paneler."},
    ] if sv else [
        {"step": 1, "action": "Stop and wait", "detail": "Wait for the drum to stop. Do not force a locked door or open it when water is visible."},
        {"step": 2, "action": "Record the code and PNC", "detail": f"Photograph the complete {code} display and note the PNC/product number from the rating plate."},
        {"step": 3, "action": "Check the door externally", "detail": "Remove visibly trapped laundry, reduce overloading and inspect the seal without tools."},
        {"step": 4, "action": "Follow the exact model manual", "detail": action + "."},
        {"step": 5, "action": "Make at most one safe test", "detail": "Test E40/E41 once after correct closure only if the washer is dry and the manual permits it."},
        {"step": 6, "action": "Arrange authorised service", "detail": "Request service if the code remains and immediately for E38 or internal E42/E44. Do not remove panels."},
    ])
    v["when_to_call_technician_html"] = ("<p>Boka auktoriserad Electrolux-service om E40/E41 kvarstår efter att luckan frigjorts och stängts korrekt. E38, E42 och E44 kräver professionell intern diagnos.</p><p>Sluta använda maskinen vid vatten i trumman med osäkert lås, läckage, bränd lukt, rök eller utlöst elskydd.</p>" if sv else "<p>Arrange authorised Electrolux service if E40/E41 remains after the door is cleared and closed correctly. E38, E42 and E44 require professional internal diagnosis.</p><p>Stop using the washer for water in the drum with an unsafe lock, leakage, burning smell, smoke or tripped protection.</p>")
    v["prevention_html"] = ("<p>Överfyll inte trumman, håll lucköppning och tätning fria från tvätt och stäng luckan utan att slå igen den.</p><p>Följ last- och underhållsanvisningarna för exakt modell. Interna tryck- och låskretsfel kan inte förebyggas med användarunderhåll.</p>" if sv else "<p>Do not overload the drum, keep the opening and seal clear of laundry and close the door without slamming it.</p><p>Follow load and maintenance instructions for the exact model. Internal pressure and lock-circuit faults cannot be prevented by user maintenance.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-012-electrolux-e38-e44-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "012-electrolux-e38-e44", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-code-e40",
        "https://support.electrolux.co.uk/support-articles/article/the-washing-machine-door-does-not-close-properly",
        "https://tds.electrolux.com/others/599/705/670EN.PDF",
        "https://tds.electrolux.com/others/599/703/247EN.PDF",
    ], "translations": {}}
    for i, code in ITEMS.items():
        out["translations"][str(i)] = {"code": code, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": make(code, False), "sv": make(code, True)}
    p = BASE_DIR / "data/article_reviews/batch-012-electrolux-e38-e44-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
