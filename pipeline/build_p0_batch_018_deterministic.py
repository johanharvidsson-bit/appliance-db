"""Build reviewed Electrolux safety faults and LG AE/CE content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    363: {"brand": "Electrolux", "code": "—", "en": ("Washing Machine Won't Complete a Cycle", "the washer stops or remains in one programme phase", "Check the displayed code, load balance, water supply and drainage, then make one documented reset"), "sv": ("Tvättmaskinen slutför inte programmet", "tvättmaskinen stannar eller blir kvar i en programfas", "Kontrollera visad kod, lastbalans, vattentillförsel och tömning och gör sedan en dokumenterad återställning")},
    366: {"brand": "Electrolux", "code": "—", "en": ("Washing Machine Trips the Electrics", "the washer trips a breaker, fuse or residual-current device", "Stop using the washer, unplug it if safe and have the electrical supply and appliance checked by qualified professionals"), "sv": ("Tvättmaskinen löser ut säkringen", "tvättmaskinen löser ut säkring, dvärgbrytare eller jordfelsbrytare", "Sluta använda maskinen, koppla ur om det kan göras säkert och låt behöriga fackpersoner kontrollera elmatning och maskin")},
    367: {"brand": "Electrolux", "code": "—", "en": ("Burning Smell From Washing Machine", "a burning smell is a safety warning rather than a cleaning issue", "Stop the appliance, unplug it immediately if safe and contact an authorised service centre"), "sv": ("Bränd lukt från tvättmaskinen", "bränd lukt är en säkerhetsvarning och inte ett rengöringsproblem", "Stoppa maskinen, koppla ur den omedelbart om det kan göras säkert och kontakta auktoriserad service")},
    86: {"brand": "LG", "code": "AE", "en": ("LG Washing Machine Error Code AE", "AE on the affected LG front-load washers indicates an internal leakage condition that activates flood protection", "Stop the washer, close the water taps, unplug if the area is dry and inspect only visible inlet-hose connections and damage"), "sv": ("LG-tvättmaskin felkod AE", "AE på berörda frontmatade LG-maskiner anger ett internt läckagetillstånd som aktiverar översvämningsskyddet", "Stoppa maskinen, stäng vattenkranarna, koppla ur om området är torrt och kontrollera endast synliga tilloppsanslutningar och skador")},
    87: {"brand": "LG", "code": "CE", "en": ("LG Washing Machine Error Code CE", "CE indicates over-current in the motor electrical circuit", "Stop the washer, unplug for 10 seconds once and retry only if there is no leak, smell, heat, smoke or electrical damage"), "sv": ("LG-tvättmaskin felkod CE", "CE anger överström i motorns elektriska krets", "Stoppa maskinen, koppla ur i 10 sekunder en gång och prova endast om inget läckage, lukt, värme, rök eller elskada finns")},
}


CAUSES = {
    363: (["Unbalanced or overloaded load", "Water-supply restriction", "Drainage restriction", "Internal appliance fault"], ["Obalanserad eller överlastad trumma", "Begränsad vattentillförsel", "Tömningshinder", "Internt maskinfel"]),
    366: (["Fault in the appliance", "Damaged cord, plug or outlet", "Supply-circuit problem", "Moisture or leakage near electrics"], ["Fel i maskinen", "Skadad kabel, kontakt eller uttag", "Fel i matande elkrets", "Fukt eller läckage nära el"]),
    367: (["Electrical overheating", "Motor or drive overheating", "Friction from a mechanical fault", "Damaged wiring or component"], ["Elektrisk överhettning", "Överhettad motor eller drivning", "Friktion från mekaniskt fel", "Skadat kablage eller komponent"]),
    86: (["Internal water leakage", "Loose or damaged inlet hose", "Leak at a visible connection", "Faulty leak-safety switch"], ["Internt vattenläckage", "Lös eller skadad tilloppsslang", "Läckage vid synlig anslutning", "Fel på läckageskyddets brytare"]),
    87: (["Motor-circuit over-current", "Short circuit or ground fault", "Loose internal connection", "Power surge or internal component fault"], ["Överström i motorkretsen", "Kortslutning eller jordfel", "Lös intern anslutning", "Spänningsstörning eller internt komponentfel"]),
}


def make(article_id: int, sv: bool) -> dict:
    item = ITEMS[article_id]; title, meaning, action = item["sv" if sv else "en"]; code = item["code"]
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    dangerous = article_id in (366, 367, 86, 87)
    if sv:
        v.update({
            "title_tag": f"{title}: betydelse och säkra steg" if code != "—" else f"Electrolux {title.lower()}: agera säkert",
            "meta_description": f"{title}? Läs verifierad betydelse, omedelbara säkerhetssteg och när auktoriserad service eller elektriker krävs.",
            "h1": title,
            "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 1–20 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Öppna inga paneler, gör inga elmätningar och beställ inte en del från symptomet eller koden ensam.</p>",
            "causes_json": [{"cause": x, "detail": "Detta är en möjlig orsak, inte en bekräftad reservdelsdiagnos."} for x in CAUSES[article_id][1]],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Avbryt programmet. Vid elutlösning, bränd lukt eller läckage ska maskinen inte startas om."},
                {"step": 2, "action": "Bryt riskkällor", "detail": ("Koppla ur med torra händer om det är säkert och stäng vattenkranarna." if dangerous else "Koppla ur före användaråtkomlig kontroll och vänta tills trumman står stilla.")},
                {"step": 3, "action": "Kontrollera endast utsidan", "detail": action + "."},
                {"step": 4, "action": "Dokumentera", "detail": f"Fotografera hela {code + '-koden' if code != '—' else 'symptomet'}, notera PNC-/modellnummer och vad som hände före stoppet."},
                {"step": 5, "action": "Anlita fackperson", "detail": "Boka auktoriserad service; använd behörig elektriker om uttag, säkring eller fast installation misstänks."},
            ],
            "when_to_call_technician_html": "<p>Boka auktoriserad service omedelbart vid bränd lukt, AE som visar läckage, återkommande CE eller om maskinen löser ut elskydd. Återkommande programstopp efter yttre kontroller kräver också service.</p><p>Håll maskinen urkopplad vid vatten nära el, rök, gnistor, onormal värme, skadad kabel eller upprepad elutlösning.</p>",
            "prevention_html": "<p>Undvik överlast, dosera rätt och kontrollera regelbundet att synliga slangar, kabel och kontakt är oskadade utan att demontera maskinen.</p><p>Interna läckage-, motor- och elfel kan inte förebyggas eller diagnostiseras säkert genom användarunderhåll.</p>",
        })
    else:
        v.update({
            "title_tag": f"{title}: Meaning and Safe Steps" if code != "—" else f"Electrolux {title}: Act Safely",
            "meta_description": f"{title}? Read the verified meaning, immediate safety steps and when authorised service or an electrician is required.",
            "h1": title,
            "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 1–20 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Open no panels, make no electrical measurements and do not order a part from the symptom or code alone.</p>",
            "causes_json": [{"cause": x, "detail": "This is a possible cause, not a confirmed parts diagnosis."} for x in CAUSES[article_id][0]],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Cancel the programme. Do not restart after electrical tripping, a burning smell or leakage."},
                {"step": 2, "action": "Isolate hazards", "detail": ("Unplug with dry hands if safe and close the water taps." if dangerous else "Unplug before user-accessible checks and wait for the drum to stop.")},
                {"step": 3, "action": "Check externally only", "detail": action + "."},
                {"step": 4, "action": "Record details", "detail": f"Photograph the complete {code + ' code' if code != '—' else 'symptom'}, note the PNC/model and what happened before the stop."},
                {"step": 5, "action": "Use a qualified professional", "detail": "Arrange authorised service; use a qualified electrician if the outlet, protection or fixed supply is suspect."},
            ],
            "when_to_call_technician_html": "<p>Arrange authorised service immediately for a burning smell, AE leakage indication, recurring CE or electrical tripping. Repeated cycle stops after external checks also require service.</p><p>Keep the washer unplugged for water near electricity, smoke, sparks, abnormal heat, a damaged cord or repeated tripping.</p>",
            "prevention_html": "<p>Avoid overloading, dose correctly and regularly check visible hoses, cord and plug for damage without dismantling the washer.</p><p>Internal leakage, motor and electrical faults cannot be safely prevented or diagnosed through user maintenance.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-018-electrolux-lg-safety-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "018-electrolux-lg-safety", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-stops-in-the-middle-of-a-cycle",
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-does-not-work-does-not-react",
        "https://support.electrolux.co.uk/support-articles/article/washing-machine-emits-a-burning-smell",
        "https://www.lg.com/us/support/help-library/lg-front-load-washer-error-code-list-CT10000010-20155069413456",
    ], "translations": {}}
    for article_id in ITEMS:
        out["translations"][str(article_id)] = {"code": ITEMS[article_id]["code"], "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-018-electrolux-lg-safety-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
