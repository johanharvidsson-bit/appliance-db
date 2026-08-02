"""Build reviewed Electrolux E24-E35 safety content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {251: "E24", 252: "E25", 253: "E30", 254: "E31", 255: "E35"}

EN = {
    "E24": ("official Electrolux service documentation identifies E24 as a fault in the sensing circuit for the electronic component that controls the drain pump", "Switch off, unplug and arrange authorised Electrolux service; do not test the pump circuit, wiring or control board"),
    "E25": ("Electrolux does not publish one universal consumer meaning for bare E25 across all washer platforms; the exact model, product number and full display are required", "Record the full code and product number, switch off and unplug, then use the exact manual or authorised Electrolux service"),
    "E30": ("Electrolux describes E30 or C3 as a water-pressure sensing condition that can be associated with water in the base or leakage", "Turn off the water supply, switch off and unplug, then inspect only visible supply-hose connections, trapped laundry and the door seal as the exact manual permits"),
    "E31": ("official Electrolux service documentation identifies E31 as an electronic pressure-switch circuit signal outside its permitted limits", "Switch off, unplug and arrange authorised Electrolux service; do not open the washer or test the pressure sensor, wiring or board"),
    "E35": ("official Electrolux service documentation identifies E35 as the water level being too high and the washer entering a safety-drain state", "Turn off the water tap, switch off and unplug if safely possible, do not open the door, and arrange authorised Electrolux service"),
}

SV = {
    "E24": ("officiell Electrolux-servicedokumentation anger att E24 är ett fel i avkänningskretsen för den elektroniska komponent som styr avloppspumpen", "Stäng av, dra ur kontakten och boka auktoriserad Electrolux-service; testa inte pumpkrets, kablage eller styrkort"),
    "E25": ("Electrolux publicerar ingen generell konsumentbetydelse för enbart E25 på alla tvättmaskinsplattformar; exakt modell, produktnummer och hela displaykoden krävs", "Dokumentera hela koden och produktnumret, stäng av och dra ur kontakten och använd rätt manual eller auktoriserad Electrolux-service"),
    "E30": ("Electrolux beskriver E30 eller C3 som ett tillstånd i vattentrycksmätningen som kan vara kopplat till vatten i botten eller läckage", "Stäng vattenkranen, stäng av och dra ur kontakten och kontrollera endast synliga tilloppsanslutningar, fastnad tvätt och lucktätning enligt rätt manual"),
    "E31": ("officiell Electrolux-servicedokumentation anger att E31 betyder att signalen från den elektroniska tryckvaktens krets ligger utanför tillåtna gränser", "Stäng av, dra ur kontakten och boka auktoriserad Electrolux-service; öppna inte maskinen och testa inte trycksensor, kablage eller kort"),
    "E35": ("officiell Electrolux-servicedokumentation anger att E35 betyder för hög vattennivå och att maskinen går in i säkerhetstömning", "Stäng vattenkranen, stäng av och dra ur kontakten om det kan göras säkert, öppna inte luckan och boka auktoriserad Electrolux-service"),
}


def make(code: str, sv: bool) -> dict:
    meaning, action = (SV if sv else EN)[code]
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Electrolux-tvättmaskinen {code}? Läs verifierad betydelse, säkra första åtgärder och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Electrolux-tvättmaskin?",
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Ange hela koden och PNC-/produktnumret till service. Felkoden ensam är inte en säker reservdelsdiagnos.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Electrolux washer showing {code}? Check the verified meaning, the safe first response and when authorised service is required.",
            "h1": f"What Does {code} Mean on an Electrolux Washing Machine?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Give service the complete code and PNC/product number. The code alone is not a safe replacement-parts diagnosis.</p>",
        })
    unknown = code == "E25"
    leak = code in {"E30", "E35"}
    if sv:
        v["causes_json"] = ([
            {"cause": "Ofullständig kodinformation", "detail": "Kodformat och betydelse kan variera mellan Electrolux-plattformar. Dokumentera hela displayen."},
            {"cause": "Modell- och marknadsskillnad", "detail": "PNC-/produktnumret identifierar rätt manual och elektronikplattform."},
            {"cause": "Möjligt internt tillstånd", "detail": "Gör endast de yttre kontroller som uttryckligen anges för exakt modell."},
            {"cause": "Kvarstående servicebehov", "detail": "Om koden återkommer eller manualen saknar användaråtgärd krävs auktoriserad diagnos."},
        ] if unknown else ([
            {"cause": "Synligt läckage eller vatten i botten", "detail": "En otät slanganslutning, skadad lucktätning eller tvätt i lucköppningen kan släppa ut vatten."},
            {"cause": "Vattentrycks- eller nivåsystem", "detail": "E30 omfattar tryckmätning; E35 anger för hög nivå och säkerhetstömning."},
            {"cause": "Ventil eller intern hydraulik", "detail": "Interna ventiler, slangar och tryckkammare kräver auktoriserad service."},
            {"cause": "Sensor-, kablage- eller styrfel", "detail": "Kod och PNC behövs för rätt diagnos; användaren ska inte mäta interna kretsar."},
        ] if leak else [
            {"cause": "Verifierad elektronisk krets", "detail": meaning.capitalize() + "."},
            {"cause": "Modellspecifik komponentuppbyggnad", "detail": "Pump-, sensor- och styrkretsar varierar med PNC och elektronikplattform."},
            {"cause": "Kablage eller anslutning", "detail": "Interna anslutningar kräver säker mätning av utbildad tekniker."},
            {"cause": "Styrkort eller komponentfel", "detail": "Koden pekar på ett system men bekräftar inte vilken del som ska bytas."},
        ]))
    else:
        v["causes_json"] = ([
            {"cause": "Incomplete code information", "detail": "Code format and meaning can differ between Electrolux platforms. Record the entire display."},
            {"cause": "Model and market difference", "detail": "The PNC/product number identifies the correct manual and electronic platform."},
            {"cause": "Possible internal condition", "detail": "Perform only external checks explicitly specified for the exact model."},
            {"cause": "Persistent need for service", "detail": "If the code returns or the manual provides no user action, authorised diagnosis is required."},
        ] if unknown else ([
            {"cause": "Visible leakage or water in the base", "detail": "A leaking hose connection, damaged door seal or laundry trapped in the opening can release water."},
            {"cause": "Water-pressure or level system", "detail": "E30 concerns pressure sensing; E35 identifies excessive level and safety draining."},
            {"cause": "Valve or internal hydraulics", "detail": "Internal valves, hoses and pressure chambers require authorised service."},
            {"cause": "Sensor, wiring or control fault", "detail": "The code and PNC are needed for diagnosis; users must not measure internal circuits."},
        ] if leak else [
            {"cause": "Verified electronic circuit", "detail": meaning[0].upper() + meaning[1:] + "."},
            {"cause": "Model-specific component design", "detail": "Pump, sensor and control circuits vary by PNC and electronic platform."},
            {"cause": "Wiring or connection", "detail": "Internal connections require safe measurement by a trained technician."},
            {"cause": "Control-board or component fault", "detail": "The code identifies a system but does not confirm which part needs replacement."},
        ]))
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa programmet", "detail": "Vänta tills trumman står stilla. Tvinga inte upp luckan, särskilt inte vid E35 eller synligt vatten."},
        {"step": 2, "action": "Stäng vattenkranen", "detail": "Stoppa vattenflödet vid E30, E35, synligt läckage eller osäker nivå."},
        {"step": 3, "action": "Stäng av och koppla ur säkert", "detail": "Dra ur kontakten med torra händer om uttaget och området är torra. Bryt annars strömmen säkert på annan plats."},
        {"step": 4, "action": "Dokumentera kod och PNC", "detail": f"Fotografera hela {code}-visningen och notera PNC-/produktnummer från typskylten."},
        {"step": 5, "action": "Följ rätt modellmanual", "detail": action + "."},
        {"step": 6, "action": "Boka auktoriserad service", "detail": "Boka service för kvarstående kod och alltid för interna krets- eller nivåkoder. Ta inte bort paneler."},
    ] if sv else [
        {"step": 1, "action": "Stop the programme", "detail": "Wait for the drum to stop. Do not force the door, especially with E35 or visible water."},
        {"step": 2, "action": "Turn off the water tap", "detail": "Stop the supply for E30, E35, visible leakage or uncertain water level."},
        {"step": 3, "action": "Switch off and disconnect safely", "detail": "Unplug with dry hands if the outlet and area are dry. Otherwise isolate power safely elsewhere."},
        {"step": 4, "action": "Record the code and PNC", "detail": f"Photograph the complete {code} display and note the PNC/product number from the rating plate."},
        {"step": 5, "action": "Follow the exact model manual", "detail": action + "."},
        {"step": 6, "action": "Arrange authorised service", "detail": "Request service for a persistent code and always for internal circuit or level codes. Do not remove panels."},
    ])
    v["when_to_call_technician_html"] = ("<p>Boka auktoriserad Electrolux-service omedelbart för E24, E31 och E35 samt för E25 när rätt manual inte ger en användaråtgärd. För E30 bokar du service om läckage syns eller koden återkommer.</p><p>Avbryt direkt vid vatten nära el, bränd lukt, rök, onormal värme eller utlöst elskydd.</p>" if sv else "<p>Arrange authorised Electrolux service immediately for E24, E31 and E35, and for E25 when the exact manual gives no user action. For E30, request service if leakage is visible or the code returns.</p><p>Stop immediately for water near electricity, burning smell, smoke, abnormal heat or tripped protection.</p>")
    v["prevention_html"] = ("<p>Kontrollera synliga slanganslutningar, håll lucköppningen fri och följ installations- och tvättmedelsanvisningarna för exakt modell.</p><p>Interna pump-, tryck- och styrkretsfel kan inte förebyggas eller diagnostiseras säkert med användarunderhåll.</p>" if sv else "<p>Check visible hose connections, keep the door opening clear and follow installation and detergent instructions for the exact model.</p><p>Internal pump, pressure and control-circuit faults cannot be safely prevented or diagnosed through user maintenance.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-011-electrolux-e24-e35-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "011-electrolux-e24-e35", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-code-e30",
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-an-error-code-how-to-fix-it",
        "https://tds.electrolux.com/others/599/705/670EN.PDF",
    ], "translations": {}}
    for i, code in ITEMS.items():
        out["translations"][str(i)] = {"code": code, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": make(code, False), "sv": make(code, True)}
    p = BASE_DIR / "data/article_reviews/batch-011-electrolux-e24-e35-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
