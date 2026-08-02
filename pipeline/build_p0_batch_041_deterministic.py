"""Build reviewed Samsung LC and common-fault content for batch 041."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline import build_p0_batch_037_deterministic as base


ITEMS = {
    48: {"type": "code", "subject": "LC", "en_title": "What Does LC Mean on a Samsung Washing Machine?", "sv_title": "Vad betyder LC på en Samsung-tvättmaskin?", "en_meaning": "Samsung uses LC in model-dependent leakage or low-water-level conditions; some guides identify detected leakage while others direct users to drain-hose placement", "sv_meaning": "Samsung använder LC för modellberoende läckage- eller lågvattennivåtillstånd; vissa guider anger upptäckt läckage medan andra hänvisar till avloppsslangens placering", "en_action": "Stop the washer, check for visible leakage and verify the external drain-hose position in the exact model manual", "sv_action": "Stoppa maskinen, kontrollera synligt läckage och verifiera den yttre avloppsslangens placering i exakt modellmanual", "en_causes": ["Visible hose, connection or door leakage", "Drain hose installed too low or incorrectly", "Model-specific low-water-level condition", "Internal leak, level-sensor or control fault"], "sv_causes": ["Synligt läckage från slang, anslutning eller lucka", "Avloppsslang monterad för lågt eller felaktigt", "Modellspecifikt lågvattennivåtillstånd", "Internt läckage-, nivågivar- eller styrfel"]},
    131: {"type": "fault", "subject": "start", "en_title": "Samsung Washing Machine Won't Start", "sv_title": "Samsung-tvättmaskinen startar inte", "en_meaning": "Samsung recommends checking safe power supply, water taps, full door closure, displayed alerts and whether Child Lock is active", "sv_meaning": "Samsung rekommenderar kontroll av säker strömförsörjning, vattenkranar, helt stängd lucka, visade meddelanden och om barnlåset är aktivt", "en_action": "Check the plug and circuit protection from a dry safe position, open the water taps, close the door firmly and use the exact model manual for any Child Lock symbol", "sv_action": "Kontrollera kontakt och elskydd från en torr säker plats, öppna vattenkranarna, stäng luckan ordentligt och använd exakt modellmanual för eventuell barnlåssymbol", "en_causes": ["No safe power supply", "Door or lid not fully closed", "Child Lock, Delay End or another setting active", "Internal door-lock, interface or control fault"], "sv_causes": ["Säker strömförsörjning saknas", "Luckan är inte helt stängd", "Barnlås, fördröjt slut eller annan inställning är aktiv", "Internt lucklås-, gränssnitts- eller styrfel"]},
    135: {"type": "fault", "subject": "noise", "en_title": "Samsung Washing Machine Making Loud Noise", "sv_title": "Samsung-tvättmaskinen låter högt", "en_meaning": "Samsung links excessive noise to installation, an unbalanced load, shipping bolts or foreign objects, while some persistent sounds require service", "sv_meaning": "Samsung kopplar kraftigt ljud till installation, obalanserad last, transportbultar eller främmande föremål, medan vissa ihållande ljud kräver service", "en_action": "Stop the washer, redistribute the load and check the level floor, spacing, shipping-bolt status and visible loose objects according to the model manual", "sv_action": "Stoppa maskinen, fördela om lasten och kontrollera plant golv, avstånd, transportbultar och synliga lösa föremål enligt modellmanualen", "en_causes": ["Unbalanced, overloaded or unsuitable load", "Washer not level or touching another object", "Shipping bolts remain after installation", "Foreign object or internal drive, bearing or suspension fault"], "sv_causes": ["Obalanserad, överlastad eller olämplig last", "Maskinen står inte i nivå eller vidrör annat föremål", "Transportbultar sitter kvar efter installation", "Främmande föremål eller internt driv-, lager- eller upphängningsfel"]},
    139: {"type": "fault", "subject": "odour", "en_title": "Samsung Washing Machine Has a Bad Smell", "sv_title": "Samsung-tvättmaskinen luktar illa", "en_meaning": "Samsung identifies retained moisture, detergent or softener residue, a dirty gasket, drawer or filter and missed tub-cleaning cycles as common causes of musty odour", "sv_meaning": "Samsung anger kvarvarande fukt, tvättmedels- eller sköljmedelsrester, smutsig tätning, låda eller filter och utebliven trumrengöring som vanliga orsaker till unken lukt", "en_action": "Remove laundry, wipe and dry the gasket and drawer, then run the empty Self Clean, Pure Cycle or manual-specified cleaning cycle", "sv_action": "Ta ur tvätten, torka ren tätning och tvättmedelslåda och kör sedan tom Self Clean, Pure Cycle eller rengöringscykeln som modellmanualen anger", "en_causes": ["Moisture retained behind a closed door", "Detergent or softener residue", "Dirty gasket, drawer or accessible filter", "Missed tub-cleaning cycle or a drain/plumbing odour"], "sv_causes": ["Fukt kvar bakom stängd lucka", "Rester av tvättmedel eller sköljmedel", "Smutsig tätning, låda eller åtkomligt filter", "Utebliven trumrengöring eller lukt från avlopp"]},
    140: {"type": "fault", "subject": "gasket", "en_title": "Samsung Washer Door Seal Damaged or Mouldy", "sv_title": "Samsung-tvättmaskinens lucktätning är skadad eller möglig", "en_meaning": "Samsung recommends regular gentle cleaning and drying for residue or surface mould; a torn, deformed or leaking seal requires service assessment", "sv_meaning": "Samsung rekommenderar regelbunden skonsam rengöring och torkning vid rester eller ytligt mögel; en sprucken, deformerad eller läckande tätning kräver servicebedömning", "en_action": "With the empty washer off, inspect and gently wipe the user-accessible gasket as the model manual specifies; do not run the washer if it is torn, deformed or leaking", "sv_action": "Med tom och avstängd maskin, inspektera och torka försiktigt den användaråtkomliga tätningen enligt modellmanualen; kör inte maskinen om den är sprucken, deformerad eller läcker", "en_causes": ["Moisture and residue retained in gasket folds", "Surface mould from limited drying", "Foreign object abrasion or chemical damage", "Torn, deformed or leaking door seal"], "sv_causes": ["Fukt och rester kvar i tätningens veck", "Ytligt mögel från otillräcklig torkning", "Nötning från främmande föremål eller kemisk skada", "Sprucken, deformerad eller läckande lucktätning"]},
}


def make(item: dict[str, object], sv: bool) -> dict[str, object]:
    value = base.make(item, sv)
    value = json.loads(json.dumps(value, ensure_ascii=False).replace("Siemens", "Samsung").replace("siemens", "Samsung"))
    if item["type"] == "code":
        value["title_tag"] = "Samsung Washing Machine Error LC: Safe Steps" if not sv else "Samsung-tvättmaskin felkod LC: säkra steg"
        value["meta_description"] = ("Samsung washer showing LC? Read the model-dependent meaning, safe leak and drain-hose checks and when Samsung service is required."
                                     if not sv else "Visar Samsung-tvättmaskinen LC? Läs modellberoende betydelse, säkra läckage- och slangkontroller och när service krävs.")
    if item["subject"] == "gasket":
        value["title_tag"] = "Samsung Washer Door Seal: Damage or Mould" if not sv else "Samsung lucktätning: skada eller mögel"
    if item["subject"] in {"gasket", "odour"}:
        if sv:
            value["steps_json"] = [
                {"step": 1, "action": "Stoppa och töm maskinen", "detail": "Ta ur all tvätt, stäng av maskinen och vänta tills trumman står stilla."},
                {"step": 2, "action": "Skilj lukt från akut fara", "detail": "Vid bränd lukt, rök, gnistor eller onormal värme: bryt strömmen säkert, kör inte maskinen och boka service."},
                {"step": 3, "action": "Rengör endast åtkomliga ytor", "detail": str(item["sv_action"]) + ". Använd bara medel och metod som modellmanualen tillåter."},
                {"step": 4, "action": "Låt maskinen torka", "detail": "Torka tätning och låda och lämna lucka och låda öppna när det är säkert och maskinen inte används."},
                {"step": 5, "action": "Boka Samsung-service vid skada", "detail": "Använd inte maskinen om tätningen är sprucken, deformerad eller läcker, eller om lukt kvarstår trots korrekt rengöring."},
            ]
        else:
            value["steps_json"] = [
                {"step": 1, "action": "Stop and empty the washer", "detail": "Remove all laundry, switch off and wait for the drum to stop."},
                {"step": 2, "action": "Separate odour from immediate danger", "detail": "For burning smell, smoke, sparks or abnormal heat, isolate power safely, do not run the washer and arrange service."},
                {"step": 3, "action": "Clean user-accessible surfaces only", "detail": str(item["en_action"]) + ". Use only products and methods permitted by the model manual."},
                {"step": 4, "action": "Allow the washer to dry", "detail": "Dry the gasket and drawer and leave the door and drawer open when safe and the appliance is not in use."},
                {"step": 5, "action": "Arrange Samsung service for damage", "detail": "Do not use the washer if the gasket is torn, deformed or leaking, or if odour remains after correct cleaning."},
            ]
    value["parts_json"] = []
    assert len(value["title_tag"]) <= 70 and len(value["meta_description"]) <= 165, (item["subject"], len(value["title_tag"]), len(value["meta_description"]))
    return value


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-041-samsung-lc-common-faults-before.json").read_text(encoding="utf-8")); rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {"batch": "041-samsung-lc-common-faults", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://support-cacyber.samsung.com/cacyber/popup/iframe/pop_troubleshooting_fr.jsp?idx=898705&lang=ca&modelcode=WF337AAR%2FXAA",
        "https://www.samsung.com/us/home-appliances/faq/faq-washer/",
        "https://www.samsung.com/uk/support/home-appliances/why-is-my-washing-machine-making-noises-and-how-to-fix/",
        "https://www.samsung.com/us/support/troubleshooting/TSG01108629/",
        "https://www.samsung.com/ca/support/home-appliances/how-to-clean-your-samsung-washer/",
        "https://www.samsung.com/sg/support/home-appliances/how-to-clean-the-drum-and-door-seal-on-my-washing-machine/",
    ], "translations": {}}
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": item["subject"], "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(item, False), "sv": make(item, True)}
    path = BASE_DIR / "data/article_reviews/batch-041-samsung-lc-common-faults-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
