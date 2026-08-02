"""Build reviewed Electrolux heating/vibration/seal/drum/control content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    356: {
        "en": ("Washing Machine Not Heating Water", "the washer appears not to heat the wash water", "Confirm the selected programme and temperature; remember that the final rinse is normally cold"),
        "sv": ("Tvättmaskinen värmer inte vattnet", "tvättmaskinen verkar inte värma tvättvattnet", "Kontrollera valt program och temperatur; tänk på att slutsköljningen normalt är kall"),
        "cause_en": ["Cold or low-temperature programme", "Normal cold final rinse", "Heating-system fault", "Temperature-sensing or control fault"],
        "cause_sv": ["Kallt eller lågtempererat program", "Normal kall slutsköljning", "Fel i värmesystemet", "Fel på temperaturgivning eller styrning"],
    },
    357: {
        "en": ("Washing Machine Vibrating Excessively", "the washer moves or vibrates more than expected", "Check transit bolts on a new installation, level all feet, provide clearance and redistribute the load"),
        "sv": ("Tvättmaskinen vibrerar för mycket", "tvättmaskinen rör sig eller vibrerar mer än förväntat", "Kontrollera transportbultar vid ny installation, nivellera alla fötter, ge frigång och fördela om lasten"),
        "cause_en": ["Transit bolts still fitted", "Washer not level or floor unstable", "Unbalanced or unusual load", "Internal suspension or mechanical fault"],
        "cause_sv": ["Transportbultar sitter kvar", "Maskinen står ojämnt eller golvet är instabilt", "Obalanserad eller ovanlig last", "Internt upphängnings- eller mekanikfel"],
    },
    360: {
        "en": ("Damaged or Mouldy Washing Machine Door Seal", "the door gasket is damaged, loose, deformed or contaminated", "Do not use a washer with a damaged or leaking seal; clean only an intact seal by the exact manual"),
        "sv": ("Skadad eller möglig dörrtätning", "lucktätningen är skadad, lös, deformerad eller smutsig", "Använd inte en maskin med skadad eller läckande tätning; rengör endast en hel tätning enligt manualen"),
        "cause_en": ["Laundry trapped in the door", "Zips or metal objects", "Overloading", "Residue and persistent moisture"],
        "cause_sv": ["Tvätt fastnar i luckan", "Dragkedjor eller metallföremål", "Överlast", "Rester och kvarstående fukt"],
    },
    361: {
        "en": ("Washing Machine Drum Not Turning", "the drum does not rotate during the programme", "Check the programme, load, closed door and drainage; do not reach inside or inspect the drive system"),
        "sv": ("Tvättmaskinens trumma snurrar inte", "trumman roterar inte under programmet", "Kontrollera program, last, stängd lucka och tömning; för inte in händer och inspektera inte drivsystemet"),
        "cause_en": ["Programme delay or paused cycle", "Load or drainage problem", "Door not locked", "Internal motor, drive or control fault"],
        "cause_sv": ["Programfördröjning eller paus", "Last- eller tömningsproblem", "Luckan är inte låst", "Internt motor-, driv- eller styrfel"],
    },
    362: {
        "en": ("Washing Machine Control Panel Unresponsive", "the display or controls do not respond normally", "Check the mains supply, door and child lock shown in the exact manual, then disconnect for 15 minutes once"),
        "sv": ("Tvättmaskinens kontrollpanel svarar inte", "displayen eller reglagen svarar inte normalt", "Kontrollera nätmatning, lucka och barnlås enligt exakt manual och koppla sedan ur i 15 minuter en gång"),
        "cause_en": ["No power at the outlet", "Child lock active", "Door not fully closed", "Internal interface or control fault"],
        "cause_sv": ["Ingen spänning i uttaget", "Barnlåset är aktivt", "Luckan är inte helt stängd", "Internt gränssnitts- eller styrfel"],
    },
}


def make(item: dict, sv: bool) -> dict:
    loc = "sv" if sv else "en"
    title, meaning, action = item[loc]
    v = build_sv("—", meaning, action) if sv else build_en("—", meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux {title.lower()}: säkra kontroller",
            "meta_description": f"{title}? Läs verifierade orsaker, säkra kontroller enligt manualen och när auktoriserad service krävs.",
            "h1": title,
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Koppla ur före rengöring eller yttre kontroll och öppna aldrig maskinens paneler.</p>",
            "causes_json": [{"cause": x, "detail": "Kontrollera detta endast med användaråtkomliga och modellspecifika steg i manualen."} for x in item["cause_sv"]],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Kontrollera inställning och symptom", "detail": action + "."},
                {"step": 3, "action": "Dokumentera", "detail": "Notera programfas, eventuell kod och PNC-/produktnummer."},
                {"step": 4, "action": "Följ exakt manual", "detail": "Gör bara dokumenterade användarkontroller; demontera inget och gör inga elektriska mätningar."},
                {"step": 5, "action": "Boka service", "detail": "Avsluta om felet kvarstår eller om tätning, värmare, motor, elektronik eller intern mekanik misstänks."},
            ],
            "when_to_call_technician_html": "<p>Boka auktoriserad service om problemet kvarstår efter yttre kontroller. Använd inte maskinen med skadad tätning, läckage eller onormal mekanisk rörelse.</p><p>Koppla ur direkt vid vatten nära el, bränd lukt, rök, onormal värme, utlöst elskydd, gnistor eller kraftigt malande/skrapande ljud.</p>",
            "prevention_html": "<p>Följ lastgränser, töm fickor, stäng dragkedjor, lämna luckan på glänt efter användning när det är säkert och rengör tätning och åtkomliga delar enligt manualen.</p><p>Håll maskinen nivellerad och använd rätt program; detta förebygger inte interna komponentfel.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux {title}: Safe Checks",
            "meta_description": f"{title}? Read verified causes, safe manual-based checks and when authorised service is required.",
            "h1": title,
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5–30 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Unplug before cleaning or external checks and never open appliance panels.</p>",
            "causes_json": [{"cause": x, "detail": "Check this only through user-accessible, model-specific steps in the manual."} for x in item["cause_en"]],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Check settings and symptoms", "detail": action + "."},
                {"step": 3, "action": "Record details", "detail": "Note the programme stage, any code and the PNC/product number."},
                {"step": 4, "action": "Follow the exact manual", "detail": "Perform documented user checks only; dismantle nothing and make no electrical measurements."},
                {"step": 5, "action": "Arrange service", "detail": "Stop if the issue remains or the seal, heater, motor, electronics or internal mechanics are suspected."},
            ],
            "when_to_call_technician_html": "<p>Arrange authorised service if the problem remains after external checks. Do not use the washer with a damaged seal, leakage or abnormal mechanical movement.</p><p>Unplug immediately for water near electricity, burning smell, smoke, abnormal heat, tripped protection, sparks or severe grinding or scraping.</p>",
            "prevention_html": "<p>Follow load limits, empty pockets, close zips, leave the door ajar after use when safe and clean the seal and accessible areas as the manual specifies.</p><p>Keep the washer level and select the correct programme; this does not prevent internal component faults.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-017-electrolux-common-faults-2-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {
        "batch": "017-electrolux-common-faults-2", "status": "proposal_only_not_applied", "article_ids": list(ITEMS),
        "sources": [
            "https://support.electrolux.co.uk/support-articles/article/washing-machine-does-not-heat-up-and-does-not-display-an-error-message",
            "https://support.electrolux.co.uk/support-articles/article/how-to-stop-your-washing-machine-vibrating-and-reduce-noise-unbalanced-load-reduce-vibration-during-rinse",
            "https://support.electrolux.co.uk/support-articles/article/seal-on-the-washing-machines-door-is-damaged",
            "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-code-e20-e21-or-c2-emits-2-beeps-or-2-flashes",
            "https://support.electrolux.co.uk/support-articles/article/washing-machine-does-not-work-does-not-react",
        ], "translations": {},
    }
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": "—", "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(item, False), "sv": make(item, True)}
    path = BASE_DIR / "data/article_reviews/batch-017-electrolux-common-faults-2-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
