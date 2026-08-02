"""Build reviewed Electrolux E71/E91/E92/E94/EF0 content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {272: "E71", 273: "E91", 274: "E92", 275: "E94", 276: "EF0"}

EN = {
    "E71": "official Electrolux service documentation identifies E71 as a washing-temperature NTC sensor signal outside limits, caused by a short/open sensor, wiring or control-board fault",
    "E91": "Electrolux identifies E91 as an electronic communication problem; service documentation specifies communication between the user interface and main board",
    "E92": "Electrolux identifies E92 as an electronic configuration or communication problem; service documentation describes a protocol mismatch",
    "E94": "Electrolux identifies E94 as an electronic configuration problem; service documentation specifies incorrect washing-cycle configuration",
    "EF0": "Electrolux states that EF0 can be triggered by water leakage, excessive foam, an unbalanced load or an appliance malfunction",
}

SV = {
    "E71": "officiell Electrolux-servicedokumentation anger att E71 betyder att tvättens NTC-temperaturgivarsignal ligger utanför gränserna på grund av kortsluten/öppen givare, kablage eller styrkort",
    "E91": "Electrolux anger att E91 är ett elektroniskt kommunikationsproblem; servicedokumentationen specificerar kommunikationen mellan användargränssnitt och huvudkort",
    "E92": "Electrolux anger att E92 är ett elektroniskt konfigurations- eller kommunikationsproblem; servicedokumentationen beskriver en protokollavvikelse",
    "E94": "Electrolux anger att E94 är ett elektroniskt konfigurationsproblem; servicedokumentationen specificerar felaktig konfiguration av tvättprogram",
    "EF0": "Electrolux anger att EF0 kan utlösas av vattenläckage, för mycket skum, obalanserad last eller fel i maskinen",
}


def make(code: str, sv: bool) -> dict:
    meaning = (SV if sv else EN)[code]
    user = code == "EF0"
    action = (("Stäng av, stäng vattenkranen och koppla ur säkert; kontrollera synligt läckage, tvätt i luckan, dosering, lastbalans och användaråtkomliga anslutningar enligt rätt manual" if sv else "Switch off, turn off the water tap and disconnect safely; check visible leakage, trapped laundry, detergent dose, load balance and user-accessible connections as the exact manual describes") if user else ("Stäng av, dra ur kontakten och boka auktoriserad Electrolux-service; öppna inte maskinen och testa inte givare, kablage eller elektronik" if sv else "Switch off, unplug and arrange authorised Electrolux service; do not open the washer or test sensors, wiring or electronics"))
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Electrolux-tvättmaskinen {code}? Läs verifierad betydelse, säkra kontroller och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Electrolux-tvättmaskin?",
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Dokumentera hela koden och PNC-/produktnumret och beställ inte en reservdel från koden ensam.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Electrolux washer showing {code}? Check the verified meaning, safe user actions and when authorised service is required.",
            "h1": f"What Does {code} Mean on an Electrolux Washing Machine?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5–30 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Record the complete code and PNC/product number and do not order a part from the code alone.</p>",
        })
    if sv:
        v["causes_json"] = ([
            {"cause": "För mycket tvättmedel eller skum", "detail": "Överdosering kan störa nivåsystemet och hindra centrifugering."},
            {"cause": "Obalanserad last", "detail": "Ett stort eller få plagg kan inte fördelas och maskinen gör upprepade centrifugeringsförsök."},
            {"cause": "Synligt eller internt läckage", "detail": "Kontrollera endast slanganslutningar, filterområde, lucktätning och fastnad tvätt som manualen medger."},
            {"cause": "Aqua Control eller maskinfel", "detail": "Återkommande EF0 efter säkra kontroller kräver auktoriserad service."},
        ] if user else [
            {"cause": "Verifierat elektroniskt tillstånd", "detail": meaning.capitalize() + "."},
            {"cause": "Modellspecifik givare eller kommunikation", "detail": "PNC identifierar rätt elektronikplattform och servicedata."},
            {"cause": "Internt kablage eller anslutning", "detail": "Kretsar bakom paneler ska endast kontrolleras av utbildad tekniker."},
            {"cause": "Styrkort eller konfiguration", "detail": "Koden pekar ut ett system men bekräftar inte vilken del som ska bytas."},
        ])
    else:
        v["causes_json"] = ([
            {"cause": "Excess detergent or foam", "detail": "Overdosing can interfere with level sensing and prevent spinning."},
            {"cause": "Unbalanced load", "detail": "One large item or a few items may not distribute and the washer repeats spin attempts."},
            {"cause": "Visible or internal leakage", "detail": "Check only hose connections, filter area, door seal and trapped laundry covered by the manual."},
            {"cause": "Aqua Control or appliance fault", "detail": "Recurring EF0 after safe checks requires authorised service."},
        ] if user else [
            {"cause": "Verified electronic condition", "detail": meaning[0].upper() + meaning[1:] + "."},
            {"cause": "Model-specific sensor or communication", "detail": "The PNC identifies the correct electronics platform and service data."},
            {"cause": "Internal wiring or connection", "detail": "Circuits behind panels must be checked only by a trained technician."},
            {"cause": "Control board or configuration", "detail": "The code identifies a system but does not confirm which part needs replacement."},
        ])
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa programmet", "detail": "Vänta tills trumman står stilla. Tvinga inte luckan och hantera inte vatten som kan vara varmt."},
        {"step": 2, "action": "Stäng vatten och ström", "detail": "Stäng vattenkranen och dra ur kontakten med torra händer om området är torrt."},
        {"step": 3, "action": "Dokumentera kod och PNC", "detail": f"Fotografera hela {code}-visningen och notera PNC-/produktnummer och programfas."},
        {"step": 4, "action": "Följ rätt modellmanual", "detail": action + "."},
        {"step": 5, "action": "Testa bara när det är säkert", "detail": "För EF0 kan ett enda test göras efter att skum lagt sig och synliga orsaker åtgärdats, om inget läckage eller annan varningssignal finns."},
        {"step": 6, "action": "Boka auktoriserad service", "detail": "Boka direkt för E71/E91/E92/E94 och för EF0 som återkommer. Ta inte bort paneler."},
    ] if sv else [
        {"step": 1, "action": "Stop the programme", "detail": "Wait for the drum to stop. Do not force the door or handle water that may be hot."},
        {"step": 2, "action": "Turn off water and power", "detail": "Close the water tap and unplug with dry hands if the area is dry."},
        {"step": 3, "action": "Record the code and PNC", "detail": f"Photograph the complete {code} display and note the PNC/product number and programme stage."},
        {"step": 4, "action": "Follow the exact model manual", "detail": action + "."},
        {"step": 5, "action": "Test only when safe", "detail": "For EF0, make one test after foam subsides and visible causes are corrected only if there is no leakage or other warning sign."},
        {"step": 6, "action": "Arrange authorised service", "detail": "Request service directly for E71/E91/E92/E94 and for recurring EF0. Do not remove panels."},
    ])
    v["when_to_call_technician_html"] = (f"<p>{code} kräver auktoriserad service om det är en E71/E9-kod eller om EF0 återkommer efter dokumenterade yttre kontroller. Använd inte maskinen vid läckage.</p><p>Avbryt direkt vid vatten nära el, bränd lukt, rök, onormal värme eller utlöst elskydd.</p>" if sv else f"<p>{code} requires authorised service when it is an E71/E9 code or when EF0 returns after documented external checks. Do not use the washer when leaking.</p><p>Stop immediately for water near electricity, burning smell, smoke, abnormal heat or tripped protection.</p>")
    v["prevention_html"] = ("<p>Dosera tvättmedel efter vattenhårdhet och last, fördela stora och små plagg och håll dispenser, lucköppning och synliga slanganslutningar rena och täta.</p><p>Interna givarfel, kommunikationsfel och konfigurationsfel kan inte förebyggas eller diagnostiseras säkert genom användarunderhåll.</p>" if sv else "<p>Dose detergent for water hardness and load, mix large and small items and keep the dispenser, door opening and visible hose connections clean and watertight.</p><p>Internal sensor, communication and configuration faults cannot be safely prevented or diagnosed through user maintenance.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-015-electrolux-e71-ef0-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "015-electrolux-e71-ef0", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-message-e90-e91-e92-e93-or-e94",
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-warning-code-ef0",
        "https://tds.electrolux.com/others/599/705/670EN.PDF",
        "https://tds.electrolux.com/others/599/724/080EN.PDF",
    ], "translations": {}}
    for i, code in ITEMS.items():
        out["translations"][str(i)] = {"code": code, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": make(code, False), "sv": make(code, True)}
    p = BASE_DIR / "data/article_reviews/batch-015-electrolux-e71-ef0-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
