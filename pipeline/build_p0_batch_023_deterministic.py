"""Build reviewed LG fault and Samsung 15C/1AC/1C content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    157: {"brand": "LG", "code": "—", "en": ("LG Washing Machine Drum Not Turning", "the drum does not rotate during the wash or spin phase", "Check the selected cycle, load, closed door and drainage, then stop if the drum remains stationary"), "sv": ("LG-tvättmaskinens trumma snurrar inte", "trumman roterar inte under tvätt- eller centrifugeringsfasen", "Kontrollera valt program, last, stängd lucka och tömning och stoppa om trumman förblir stilla")},
    161: {"brand": "LG", "code": "—", "en": ("LG Washing Machine Shows an Error Code", "the washer has detected a condition identified by the complete displayed code", "Photograph the full code, confirm the exact model number and use LG's model-specific manual or official code guide"), "sv": ("LG-tvättmaskinen visar en felkod", "tvättmaskinen har upptäckt ett tillstånd som identifieras av hela koden på displayen", "Fotografera hela koden, bekräfta exakt modellnummer och använd LG:s modellspecifika manual eller officiella kodguide")},
    7: {"brand": "Samsung", "code": "15C", "en": ("Samsung Washing Machine Error Code 15C", "15C is not defined in Samsung's generic public washer code table and must be confirmed in the exact model manual", "Record the complete code and model, switch off for one minute once and contact Samsung support if it returns"), "sv": ("Samsung-tvättmaskin felkod 15C", "15C definieras inte i Samsungs generella offentliga kodtabell för tvättmaskiner och måste bekräftas i exakt modellmanual", "Notera hela koden och modellen, stäng av i en minut en gång och kontakta Samsung-support om den återkommer")},
    8: {"brand": "Samsung", "code": "1AC", "en": ("Samsung Washing Machine Error Code 1AC", "1AC is model-specific; Samsung's public guide identifies AC/AE-family codes as communication checks between control boards", "Record the complete code and model, switch off for one minute once and contact Samsung service if it returns"), "sv": ("Samsung-tvättmaskin felkod 1AC", "1AC är modellspecifik; Samsungs offentliga guide beskriver AC-/AE-familjen som kommunikationskontroller mellan styrkort", "Notera hela koden och modellen, stäng av i en minut en gång och kontakta Samsung-service om den återkommer")},
    9: {"brand": "Samsung", "code": "1C", "en": ("Samsung Washing Machine Error Code 1C", "Samsung identifies 1C as a water-level sensor error", "Switch the washer off for one minute once and restart; request Samsung service if 1C returns"), "sv": ("Samsung-tvättmaskin felkod 1C", "Samsung anger att 1C är ett fel på vattennivågivaren", "Stäng av tvättmaskinen i en minut en gång och starta om; boka Samsung-service om 1C återkommer")},
}


def make(article_id: int, sv: bool) -> dict:
    item = ITEMS[article_id]; code = item["code"]; title, meaning, action = item["sv" if sv else "en"]; samsung = item["brand"] == "Samsung"
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"{title}: betydelse och säkra steg" if samsung else f"{title}: säkra kontroller",
            "meta_description": f"{title}? Läs verifierad betydelse, säkra kontroller enligt officiell support och när auktoriserad service krävs.",
            "h1": (f"Vad betyder {code} på en Samsung-tvättmaskin?" if samsung else title), "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–20 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Gissa inte en intern del från koden eller symptomet och öppna eller mät inga interna kretsar.</p>",
            "causes_json": ([
                {"cause": "Modellspecifik kod", "detail": "Hela kodsträngen och exakt modell krävs för korrekt betydelse."},
                {"cause": "Tillfälligt styrtillstånd", "detail": "En enda avstängning kan utesluta ett tillfälligt tillstånd."},
                {"cause": "Givar- eller kommunikationsfel", "detail": "1C gäller nivågivning; AC-familjen gäller kommunikation på modeller där manualen bekräftar det."},
                {"cause": "Internt styr- eller kablagefel", "detail": "Detta kräver Samsung-service och är ingen användarreparation."},
            ] if samsung else [
                {"cause": "Kodspecifikt maskintillstånd", "detail": "Den fullständiga koden styr rätt felsökning."},
                {"cause": "Last, lucka eller tömning", "detail": "Yttre driftsvillkor kan stoppa program eller trumrörelse."},
                {"cause": "Tillfälligt styrfel", "detail": "En dokumenterad omstart kan utesluta ett tillfälligt tillstånd."},
                {"cause": "Internt motor-, givar- eller styrfel", "detail": "Bestående kod eller stillastående trumma kräver diagnos."},
            ]),
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Dokumentera exakt", "detail": action + "."},
                {"step": 3, "action": "Följ rätt manual", "detail": "Använd modellnumret och hela koden; gör endast dokumenterade användarkontroller."},
                {"step": 4, "action": "Återställ en gång", "detail": "Koppla ur med torra händer enligt tillverkarens råd och starta bara om utan läckage, lukt, rök, värme eller elskada."},
                {"step": 5, "action": "Boka auktoriserad service", "detail": "Boka service om koden eller symptomet återkommer. Demontera inte paneler och mät inga givare, motorer eller styrkort."},
            ],
            "when_to_call_technician_html": "<p>Boka auktoriserad service om koden återkommer efter en omstart, om trumman inte roterar eller om exakt manual anger ett internt givar-, motor-, kommunikations- eller styrfel.</p><p>Koppla ur direkt vid vatten nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ lastgränser, töm fickor, håll maskinen i nivå och notera alltid hela koden och modellnumret innan support kontaktas.</p><p>Interna sensor-, motor-, kommunikations- och elektronikfel kan inte förebyggas eller diagnostiseras säkert genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"{title}: Meaning and Safe Steps" if samsung else f"{title}: Safe Checks",
            "meta_description": f"{title}? Read the verified meaning, safe checks from official support and when authorised service is required.",
            "h1": (f"What Does {code} Mean on a Samsung Washing Machine?" if samsung else title), "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–20 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Do not guess an internal part from the code or symptom, and open or measure no internal circuits.</p>",
            "causes_json": ([
                {"cause": "Model-specific code", "detail": "The complete code string and exact model are required for the correct meaning."},
                {"cause": "Temporary control condition", "detail": "One shutdown can rule out a temporary state."},
                {"cause": "Sensor or communication fault", "detail": "1C concerns level sensing; the AC family concerns communication where the model manual confirms it."},
                {"cause": "Internal control or wiring fault", "detail": "This requires Samsung service and is not a user repair."},
            ] if samsung else [
                {"cause": "Code-specific appliance condition", "detail": "The complete code determines the correct troubleshooting path."},
                {"cause": "Load, door or drainage", "detail": "External operating conditions can stop a cycle or drum movement."},
                {"cause": "Temporary control fault", "detail": "A documented restart can rule out a temporary condition."},
                {"cause": "Internal motor, sensor or control fault", "detail": "A persistent code or stationary drum requires diagnosis."},
            ]),
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Record exactly", "detail": action + "."},
                {"step": 3, "action": "Follow the correct manual", "detail": "Use the model number and complete code; perform documented user checks only."},
                {"step": 4, "action": "Reset once", "detail": "Unplug with dry hands as the manufacturer advises and restart only without leakage, smell, smoke, heat or electrical damage."},
                {"step": 5, "action": "Arrange authorised service", "detail": "Request service if the code or symptom returns. Remove no panels and measure no sensors, motors or boards."},
            ],
            "when_to_call_technician_html": "<p>Arrange authorised service if the code returns after one restart, if the drum does not rotate or if the exact manual identifies an internal sensor, motor, communication or control fault.</p><p>Unplug immediately for water near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow load limits, empty pockets, keep the washer level and always record the full code and model number before contacting support.</p><p>Internal sensor, motor, communication and electronics faults cannot be safely prevented or diagnosed through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-023-lg-samsung-transition-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "023-lg-samsung-transition", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.lg.com/us/support/help-library/lg-front-load-washer-error-code-list-CT10000010-20155069413456",
        "https://www.lg.com/us/support/help-library/lg-washer-troubleshooting-washing-machine-drum-not-spinning-CT10000010-20150584818000",
        "https://www.samsung.com/uk/support/home-appliances/check-out-the-information-codes-on-my-washing-machine/",
        "https://www.samsung.com/uk/support/home-appliances/what-do-the-codes-on-my-washing-machine-mean/",
    ], "translations": {}}
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": item["code"], "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-023-lg-samsung-transition-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
