"""Build reviewed LG dE/dE1/dE2/E6/EE content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    89: ("dE", "the washer was unable to lock the door", "tvättmaskinen kunde inte låsa luckan"),
    90: ("dE1", "the door is not closed properly", "luckan är inte korrekt stängd"),
    91: ("dE2", "the door is closed but has not locked", "luckan är stängd men har inte låsts"),
    92: ("E6", "LG documents E6 on applicable models as a clutch error, sometimes caused by an object between the pulsator and tub; the exact model manual must confirm this meaning", "LG dokumenterar E6 på tillämpliga modeller som ett kopplingsfel, ibland orsakat av ett föremål mellan pulsator och trumma; exakt modellmanual måste bekräfta betydelsen"),
    93: ("EE", "LG documents EE on applicable models as an EEPROM/main-control-board error; the exact model manual must confirm this meaning", "LG dokumenterar EE på tillämpliga modeller som ett EEPROM-/huvudkortsfel; exakt modellmanual måste bekräfta betydelsen"),
}


def make(article_id: int, sv: bool) -> dict:
    code, en_meaning, sv_meaning = ITEMS[article_id]; meaning = sv_meaning if sv else en_meaning
    door = article_id in (89, 90, 91)
    action = (("Kontrollera att tvätt eller smuts inte sitter mellan lucka och tätning, stäng luckan igen och gör en enda dokumenterad återställning" if sv else "Check that laundry or debris is not trapped between the door and gasket, close the door again and make one documented reset") if door else ("Stäng av, koppla ur och kontrollera endast synliga lösa föremål som kan tas bort utan demontering; boka service om koden återkommer" if sv else "Switch off, unplug and check only visible loose objects removable without dismantling; arrange service if the code returns"))
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"LG-tvättmaskin felkod {code}: betydelse och säkra steg",
            "meta_description": f"Visar LG-tvättmaskinen {code}? Läs verifierad, modellspecifik betydelse, säkra kontroller och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en LG-tvättmaskin?", "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–20 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Koden bekräftar inte en viss reservdel och lucklås, koppling eller elektronik ska inte provas elektriskt av användaren.</p>",
            "causes_json": ([
                {"cause": "Tvätt eller smuts i lucköppningen", "detail": "Material mellan glas och tätning kan hindra korrekt stängning."},
                {"cause": "Luckan är inte helt stängd", "detail": "Öppna och stäng igen utan att slå eller tvinga luckan."},
                {"cause": "Överlast eller skadad spärr", "detail": "För stor last kan trycka mot luckan; skadad spärr kräver service."},
                {"cause": "Lucklås eller styrfel", "detail": "Återkommande kod efter yttre kontroll kräver diagnos."},
            ] if door else [
                {"cause": "Modellspecifik kodbetydelse", "detail": "Bekräfta alltid koden i manualen för exakt modell."},
                {"cause": "Synligt främmande föremål", "detail": "E6 kan på tillämpliga pulsator-modeller utlösas av ett föremål i springan."},
                {"cause": "Internt kopplings- eller drivfel", "detail": "E6 som kvarstår kräver auktoriserad service."},
                {"cause": "EEPROM- eller styrkortsfel", "detail": "EE som kvarstår kräver auktoriserad service och är ingen användarreparation."},
            ]),
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Vänta tills trumman står stilla. Tvinga inte lucka, trumma eller pulsator."},
                {"step": 2, "action": "Koppla ur", "detail": "Stäng av och dra ur kontakten med torra händer före yttre kontroll."},
                {"step": 3, "action": "Gör användarkontrollen", "detail": action + "."},
                {"step": 4, "action": "Bekräfta modell och kod", "detail": "Använd modellnumret för rätt LG-manual; kodbetydelser kan skilja mellan front- och toppmatade plattformar."},
                {"step": 5, "action": "Boka service", "detail": "Boka auktoriserad LG-service om koden återkommer. Öppna inga paneler och mät inga kretsar."},
            ],
            "when_to_call_technician_html": f"<p>Boka auktoriserad service om {code} återkommer efter den enda säkra kontrollen. Skadat lucklås, intern koppling och EEPROM-/styrkortsfel kräver utbildad tekniker.</p><p>Koppla ur direkt vid läckage, bränd lukt, rök, onormal värme, gnistor eller utlöst elskydd.</p>",
            "prevention_html": "<p>Undvik överlast, kontrollera fickor, håll lucköppning och tätning rena och stäng luckan utan våld.</p><p>Föremål ska bara tas bort om de är tydligt synliga och åtkomliga; interna mekanik- och elektronikfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"LG Washing Machine Error {code}: Meaning and Safe Steps",
            "meta_description": f"LG washer showing {code}? Read the verified, model-specific meaning, safe checks and when authorised service is required.",
            "h1": f"What Does {code} Mean on an LG Washing Machine?", "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–20 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. The code does not confirm a specific part, and users must not electrically test the lock, clutch or electronics.</p>",
            "causes_json": ([
                {"cause": "Laundry or debris in the opening", "detail": "Material between the glass and gasket can prevent correct closure."},
                {"cause": "Door not fully closed", "detail": "Open and close it again without slamming or forcing it."},
                {"cause": "Overload or damaged latch", "detail": "A large load can press on the door; a damaged latch requires service."},
                {"cause": "Door-lock or control fault", "detail": "A recurring code after external checks requires diagnosis."},
            ] if door else [
                {"cause": "Model-specific code meaning", "detail": "Always confirm the code in the exact model manual."},
                {"cause": "Visible foreign object", "detail": "On applicable pulsator models, an object in the gap can trigger E6."},
                {"cause": "Internal clutch or drive fault", "detail": "Persistent E6 requires authorised service."},
                {"cause": "EEPROM or control-board fault", "detail": "Persistent EE requires authorised service and is not a user repair."},
            ]),
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Wait for the drum to stop. Do not force the door, drum or pulsator."},
                {"step": 2, "action": "Unplug", "detail": "Switch off and unplug with dry hands before external checks."},
                {"step": 3, "action": "Make the user check", "detail": action + "."},
                {"step": 4, "action": "Confirm model and code", "detail": "Use the model number for the correct LG manual; meanings can differ between front- and top-load platforms."},
                {"step": 5, "action": "Arrange service", "detail": "Request authorised LG service if the code returns. Open no panels and measure no circuits."},
            ],
            "when_to_call_technician_html": f"<p>Arrange authorised service if {code} returns after the one safe check. A damaged lock, internal clutch and EEPROM/control-board faults require a trained technician.</p><p>Unplug immediately for leakage, burning smell, smoke, abnormal heat, sparks or tripped protection.</p>",
            "prevention_html": "<p>Avoid overloading, check pockets, keep the door opening and gasket clean and close the door without force.</p><p>Remove objects only when clearly visible and accessible; internal mechanical and electronic faults cannot be prevented through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-019-lg-de-e6-ee-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "019-lg-de-e6-ee", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.lg.com/us/support/help-library/front-load-washer-what-are-de-de1-and-de2-error-codes--1400508168566",
        "https://www.lg.com/us/support/help-library/lg-washer-troubleshooting-an-e6-error-code-CT10000010-20152420542110",
        "https://www.lg.com/us/support/help-library/lg-top-load-washer-led-blinking-error-codes-CT00000305-20154392606264",
    ], "translations": {}}
    for article_id, (code, _, _) in ITEMS.items():
        out["translations"][str(article_id)] = {"code": code, "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-019-lg-de-e6-ee-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
