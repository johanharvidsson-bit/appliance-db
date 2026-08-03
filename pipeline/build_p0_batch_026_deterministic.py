"""Build reviewed Samsung AC/AC3/AC4/BC2/CE content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {36: "AC", 38: "AC3", 39: "AC4", 40: "BC2", 41: "CE"}


def make(article_id: int, sv: bool) -> dict:
    code = ITEMS[article_id]
    if article_id in (36, 38, 39):
        meaning = (f"Samsung groups {code} with communication errors; the exact communicating units depend on the model" if not sv else f"Samsung grupperar {code} med kommunikationsfel; exakt vilka enheter som kommunicerar beror på modellen")
        action = ("Switch the washer off and unplug it for one minute once; arrange Samsung service if the code returns" if not sv else "Stäng av tvättmaskinen och dra ur kontakten i en minut en gång; boka Samsung-service om koden återkommer")
        kind = "communication"
    elif article_id == 40:
        meaning = ("Samsung uses bC2 or BC2 differently across washer models; some manuals identify a pressed-button condition, so the exact characters and model manual are required" if not sv else "Samsung använder bC2 eller BC2 olika mellan tvättmaskinsmodeller; vissa manualer anger ett intryckt reglage, så exakta tecken och modellmanual krävs")
        action = ("Unplug the washer and inspect only the external buttons for one that is visibly stuck or damaged; contact Samsung with the exact model if the code remains" if not sv else "Dra ur kontakten och kontrollera endast de yttre knapparna efter en knapp som synligt fastnat eller skadats; kontakta Samsung med exakt modell om koden kvarstår")
        kind = "control"
    else:
        meaning = ("Samsung identifies CE as a water-temperature or supplied-water-temperature error on applicable washers" if not sv else "Samsung anger att CE är ett fel i vattentemperaturen eller det tillförda vattnets temperatur på berörda modeller")
        action = ("Turn off power and water, then verify that the cold inlet hose is connected to the cold tap and the supply is not abnormally hot" if not sv else "Stäng av ström och vatten och kontrollera sedan att kallvattenslangen är ansluten till kallvattenkranen och att tillförseln inte är onormalt varm")
        kind = "temperature"

    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    causes = {
        "communication": (["Temporary communication interruption", "Model-specific communication link", "Connector or wiring fault", "Control-electronics fault"], ["Tillfälligt kommunikationsavbrott", "Modellspecifik kommunikationslänk", "Fel i kontakt eller kablage", "Fel i styrelektroniken"]),
        "control": (["A button held or visibly stuck on some models", "Characters misread on the display", "A model-specific sensor or control condition", "Internal control fault"], ["En knapp som hålls inne eller synligt fastnat på vissa modeller", "Feltolkade tecken på displayen", "Ett modellspecifikt sensor- eller styrtillstånd", "Internt styrfel"]),
        "temperature": (["Cold inlet connected to an incorrect or hot supply", "Supplied water is abnormally hot", "Model-specific temperature sensing fault", "Internal heater or control fault"], ["Kallvattenintaget anslutet till fel eller varm tillförsel", "Tillfört vatten är onormalt varmt", "Modellspecifikt fel i temperaturavkänningen", "Internt värmar- eller styrfel"]),
    }[kind][1 if sv else 0]

    if sv:
        v.update({
            "title_tag": f"Samsung-tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Samsung-tvättmaskinen {code}? Läs verifierad betydelse, säkra yttre kontroller och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Samsung-tvättmaskin?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (cirka 5–10 minuter).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Öppna inga paneler, mät inga interna delar och beställ inte en reservdel från koden ensam.</p>",
            "causes_json": [{"cause": x, "detail": "Detta är en möjlig orsak; exakt modellmanual och professionell diagnos avgör interna fel."} for x in causes],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman stannat och tvinga inte luckan."},
                {"step": 2, "action": "Dokumentera exakt", "detail": f"Fotografera hela {code}-visningen och anteckna exakt modellnummer och programfas."},
                {"step": 3, "action": "Gör endast säker yttre kontroll", "detail": action + ". Rengör ett yttre reglage endast när maskinen är urkopplad och låt det torka helt."},
                {"step": 4, "action": "Testa en gång", "detail": "Starta om endast en gång efter korrigerad yttre orsak och aldrig vid läckage, bränd lukt, rök, onormal värme eller elskada."},
                {"step": 5, "action": "Boka Samsung-service", "detail": "Boka auktoriserad service om koden återkommer. Demontera inget och gör inga elektriska mätningar."},
            ],
            "when_to_call_technician_html": f"<p>Boka Samsung-service om {code} kvarstår eller återkommer efter den säkra yttre kontrollen. Kommunikation, givare, värmare, kablage och elektronik är inte användarreparationer.</p><p>Koppla ur direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ installationsanvisningen för exakt modell, håll reglagen torra och anslut kallvattenintaget till föreskriven kallvattenkran.</p><p>Notera hela koden och modellnumret. Interna kommunikations-, givar- och elektronikfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"Samsung Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Samsung washer showing {code}? Read the verified meaning, safe external checks and when authorised service is required.",
            "h1": f"What Does {code} Mean on a Samsung Washing Machine?",
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5–10 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Open no panels, measure no internal parts and do not order a part from the code alone.</p>",
            "causes_json": [{"cause": x, "detail": "This is a possible cause; the exact model manual and professional diagnosis determine internal faults."} for x in causes],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Record exactly", "detail": f"Photograph the complete {code} display and note the exact model number and programme stage."},
                {"step": 3, "action": "Make only the safe external check", "detail": action + ". Clean an external control only while unplugged and let it dry fully."},
                {"step": 4, "action": "Test once", "detail": "Restart only once after correcting an external cause, and never with leakage, burning smell, smoke, abnormal heat or electrical damage."},
                {"step": 5, "action": "Arrange Samsung service", "detail": "Request authorised service if the code returns. Dismantle nothing and make no electrical measurements."},
            ],
            "when_to_call_technician_html": f"<p>Arrange Samsung service if {code} remains or returns after the safe external check. Communication, sensor, heater, wiring and electronics work is not a user repair.</p><p>Unplug immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow the installation instructions for the exact model, keep controls dry and connect the cold inlet to the specified cold-water tap.</p><p>Record the complete code and model number. Internal communication, sensor and electronics faults cannot be prevented through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-026-samsung-communication-controls-temperature-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "026-samsung-communication-controls-temperature", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.samsung.com/latin_en/support/home-appliances/how-to-fix-the-washing-machine-with-ac6-error/",
        "https://www.samsung.com/uk/support/home-appliances/what-do-the-codes-on-my-washing-machine-mean/",
        "https://www.samsung.com/us/support/troubleshoot/TSG10000997/",
        "https://image-us.samsung.com/SamsungUS/support/policy/Laundry_Combo_User_ManualD.pdf",
        "https://www.samsung.com/de/support/home-appliances/waschmaschinen-fehlermeldungen/",
        "https://www.samsung.com/au/support/home-appliances/samsung-washing-machine-error-codes/",
    ], "translations": {}}
    for article_id, code in ITEMS.items():
        out["translations"][str(article_id)] = {"code": code, "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-026-samsung-communication-controls-temperature-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
