"""Build reviewed LG common washing-machine fault content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    149: {"en": ("LG Washing Machine Won't Spin", "the washer does not complete its spin phase", "Confirm that a spin option is selected, redistribute the load and check that the washer can drain"), "sv": ("LG-tvättmaskinen centrifugerar inte", "tvättmaskinen slutför inte centrifugeringen", "Bekräfta att centrifugering är vald, fördela om lasten och kontrollera att maskinen kan tömma"), "en_causes": ["Wash-only or no-spin selection", "Unbalanced or unsuitable load", "Drainage restriction", "Internal motor or control fault"], "sv_causes": ["Endast tvätt eller ingen centrifugering vald", "Obalanserad eller olämplig last", "Tömningshinder", "Internt motor- eller styrfel"]},
    152: {"en": ("LG Washing Machine Won't Fill With Water", "the washer receives no water or fills too slowly", "Open the water taps, check for an outage and straighten the external inlet hoses; clean accessible inlet filters only by the model manual"), "sv": ("LG-tvättmaskinen fyller inte med vatten", "tvättmaskinen får inget vatten eller fyller för långsamt", "Öppna vattenkranarna, kontrollera vattenavbrott och räta yttre tilloppsslangar; rengör åtkomliga inloppsfilter endast enligt modellmanualen"), "en_causes": ["Water outage or closed tap", "Kinked inlet hose", "Blocked accessible inlet filter", "Internal inlet-valve or control fault"], "sv_causes": ["Vattenavbrott eller stängd kran", "Vikt tilloppsslang", "Blockerat åtkomligt inloppsfilter", "Internt ventil- eller styrfel"]},
    154: {"en": ("LG Washing Machine Making Loud Noise", "unusual noise may come from installation, an unbalanced load or an accessible foreign object", "Stop the washer, redistribute the load and check shipping materials, levelling and clearly visible loose objects"), "sv": ("LG-tvättmaskinen låter högt", "ovanligt ljud kan bero på installation, obalanserad last eller ett åtkomligt främmande föremål", "Stoppa maskinen, fördela om lasten och kontrollera transportmaterial, nivå och tydligt synliga lösa föremål"), "en_causes": ["Shipping bolts or packing", "Unbalanced or overloaded load", "Washer not level", "Internal bearing, drive or suspension fault"], "sv_causes": ["Transportbultar eller emballage", "Obalanserad eller överlastad trumma", "Maskinen står inte i nivå", "Internt lager-, driv- eller upphängningsfel"]},
    155: {"en": ("LG Washing Machine Not Heating Water", "the selected wash may seem cooler than expected, or the washer may not reach the set temperature", "Confirm the selected cycle and temperature and compare behaviour with the exact model manual; do not test the heater"), "sv": ("LG-tvättmaskinen värmer inte vattnet", "vald tvätt kan kännas kallare än väntat eller inte nå inställd temperatur", "Kontrollera valt program och temperatur och jämför beteendet med exakt modellmanual; prova inte värmaren"), "en_causes": ["Cool or low-temperature programme", "Cold incoming water", "Normal programme energy control", "Internal heater, sensor or control fault"], "sv_causes": ["Kallt eller lågtempererat program", "Kallt inkommande vatten", "Normal energistyrning i programmet", "Internt värmar-, givar- eller styrfel"]},
    156: {"en": ("LG Washing Machine Vibrating Excessively", "the washer moves or vibrates more than expected", "Check shipping bolts on a recent installation, redistribute the load and ensure all feet are level on a stable floor"), "sv": ("LG-tvättmaskinen vibrerar för mycket", "tvättmaskinen rör sig eller vibrerar mer än förväntat", "Kontrollera transportbultar vid ny installation, fördela om lasten och se till att alla fötter står i nivå på stabilt golv"), "en_causes": ["Shipping bolts or packing remain", "Unbalanced or unsuitable load", "Washer not level", "Internal suspension or mechanical fault"], "sv_causes": ["Transportbultar eller emballage finns kvar", "Obalanserad eller olämplig last", "Maskinen står inte i nivå", "Internt upphängnings- eller mekanikfel"]},
}


def make(item: dict, sv: bool) -> dict:
    title, meaning, action = item["sv" if sv else "en"]
    v = build_sv("—", meaning, action) if sv else build_en("—", meaning, action)
    if sv:
        v.update({
            "title_tag": f"{title}: säkra kontroller", "meta_description": f"{title}? Läs verifierade orsaker, säkra kontroller enligt LG:s råd och när auktoriserad service krävs.",
            "h1": title, "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–30 minuter).", "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Koppla ur före åtkomlig kontroll och öppna aldrig maskinens paneler.</p>",
            "causes_json": [{"cause": x, "detail": "Kontrollera detta endast med yttre, användaråtkomliga steg i rätt modellmanual."} for x in item["sv_causes"]],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Kontrollera yttre förhållanden", "detail": action + "."},
                {"step": 3, "action": "Följ exakt LG-manual", "detail": "Använd modellnumret och gör bara dokumenterade användarkontroller; demontera inget och mät ingen el."},
                {"step": 4, "action": "Gör ett kontrollerat test", "detail": "Testa en gång endast utan läckage, bränd lukt, rök, onormal värme, elfel eller kraftigt skrapande ljud."},
                {"step": 5, "action": "Boka LG-service", "detail": "Avsluta om problemet återkommer eller om värmare, motor, pump, givare eller intern mekanik misstänks."},
            ],
            "when_to_call_technician_html": "<p>Boka auktoriserad LG-service om problemet kvarstår efter yttre kontroller, om trumman inte rör sig normalt eller om värmare, motor, pump, givare, elektronik eller mekanik misstänks.</p><p>Koppla ur direkt vid vatten nära el, bränd lukt, rök, gnistor, onormal värme, utlöst elskydd eller kraftigt malande/skrapande ljud.</p>",
            "prevention_html": "<p>Följ lastgränser, blanda stora och små plagg, töm fickor, dosera rätt och håll yttre slangar och användaråtkomliga filter rena enligt manualen.</p><p>Håll maskinen i nivå och kontrollera installationen; interna komponentfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"{title}: Safe Checks", "meta_description": f"{title}? Read verified causes, safe checks from LG guidance and when authorised service is required.",
            "h1": title, "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–30 minutes).", "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Unplug before accessible checks and never open appliance panels.</p>",
            "causes_json": [{"cause": x, "detail": "Check this only through external, user-accessible steps in the correct model manual."} for x in item["en_causes"]],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Check external conditions", "detail": action + "."},
                {"step": 3, "action": "Follow the exact LG manual", "detail": "Use the model number and perform documented user checks only; dismantle nothing and measure no electricity."},
                {"step": 4, "action": "Make one controlled test", "detail": "Test once only without leakage, burning smell, smoke, abnormal heat, electrical fault or severe scraping noise."},
                {"step": 5, "action": "Arrange LG service", "detail": "Stop if the issue returns or the heater, motor, pump, sensor or internal mechanics are suspected."},
            ],
            "when_to_call_technician_html": "<p>Arrange authorised LG service if the problem remains after external checks, if the drum does not move normally or if the heater, motor, pump, sensor, electronics or mechanics are suspected.</p><p>Unplug immediately for water near electricity, burning smell, smoke, sparks, abnormal heat, tripped protection or severe grinding or scraping.</p>",
            "prevention_html": "<p>Follow load limits, mix large and small items, empty pockets, dose correctly and keep external hoses and user-accessible filters clean as the manual specifies.</p><p>Keep the washer level and check installation; internal component faults cannot be prevented through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-022-lg-common-faults-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "022-lg-common-faults", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.lg.com/us/support/help-library/lg-front-load-washer-no-spin-drain-after-washing-CT10000010-20154720372345",
        "https://www.lg.com/us/support/help-library/lg-washer-why-is-there-no-water-in-my-front-load-washing-machine-CT10000012-20153089688891",
        "https://www.lg.com/us/support/help-library/lg-washer-troubleshooting-vibration-issues-CT10000010-1366656981583",
        "https://www.lg.com/us/support/help-library/lg-washing-machine-water-does-not-heat-up-or-reach-the-set-temperature--20155101730997",
    ], "translations": {}}
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": "—", "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(item, False), "sv": make(item, True)}
    path = BASE_DIR / "data/article_reviews/batch-022-lg-common-faults-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
