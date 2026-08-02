"""Build the final three reviewed Samsung P0 washing-machine faults."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline import build_p0_batch_041_deterministic as base


ITEMS = {
    143: {
        "type": "fault", "subject": "cycle",
        "en_title": "Samsung Washing Machine Won't Complete a Cycle",
        "sv_title": "Samsung-tvättmaskinen slutför inte programmet",
        "en_meaning": "Samsung notes that load sensing, an unbalanced load, low water pressure, excess suds or drainage trouble can extend or interrupt a wash cycle",
        "sv_meaning": "Samsung anger att lastavkänning, obalanserad last, lågt vattentryck, överskottsskum eller tömningsproblem kan förlänga eller avbryta ett tvättprogram",
        "en_action": "Record the displayed message and programme stage, redistribute the load, confirm water supply and inspect the visible drain hose",
        "sv_action": "Dokumentera visat meddelande och programfas, fördela om lasten, bekräfta vattenförsörjningen och kontrollera den synliga avloppsslangen",
        "en_causes": ["Normal load-sensing or programmed pause", "Unbalanced or excessive load", "Low water pressure or restricted supply", "Excess detergent and additional rinsing", "Drainage restriction or internal fault"],
        "sv_causes": ["Normal lastavkänning eller programmerad paus", "Obalanserad eller för stor last", "Lågt vattentryck eller begränsad tillförsel", "För mycket tvättmedel och extra sköljningar", "Tömningshinder eller internt fel"],
    },
    144: {
        "type": "fault", "subject": "suds",
        "en_title": "Samsung Washing Machine Producing Too Much Foam",
        "sv_title": "Samsung-tvättmaskinen producerar för mycket skum",
        "en_meaning": "Samsung identifies too much detergent, unsuitable detergent or accumulated detergent residue as common causes of excessive suds",
        "sv_meaning": "Samsung anger för mycket tvättmedel, olämpligt tvättmedel eller ansamlade tvättmedelsrester som vanliga orsaker till överskottsskum",
        "en_action": "Do not add more detergent; let the washer complete its suds-reduction process, then use an empty no-detergent rinse or cleaning cycle specified by the model manual",
        "sv_action": "Tillsätt inget mer tvättmedel; låt maskinen slutföra sin skumreducering och kör sedan tom skölj- eller rengöringscykel utan tvättmedel enligt modellmanualen",
        "en_causes": ["Too much detergent for the load", "Non-HE or unsuitable detergent", "Detergent residue inside the washer", "Very soft water requiring a lower dose", "Dispensing or drainage problem requiring service"],
        "sv_causes": ["För mycket tvättmedel för lasten", "Icke-HE eller olämpligt tvättmedel", "Tvättmedelsrester i maskinen", "Mycket mjukt vatten som kräver lägre dos", "Doserings- eller tömningsproblem som kräver service"],
    },
    145: {
        "type": "fault", "subject": "dispenser",
        "en_title": "Samsung Washer Detergent Drawer Not Dispensing",
        "sv_title": "Samsung-tvättmaskinen doserar inte tvättmedel",
        "en_meaning": "Samsung links dispensing trouble to the wrong compartment or insert, exceeding the MAX line, disabled auto dosing, thick product, poor levelling or drawer residue",
        "sv_meaning": "Samsung kopplar doseringsproblem till fel fack eller insats, överskriden MAX-linje, avstängd automatisk dosering, trögflytande medel, dålig nivellering eller rester i lådan",
        "en_action": "Check the correct compartment, insert, MAX level and auto-dose setting for the exact model, then clean the removable drawer as its manual specifies",
        "sv_action": "Kontrollera rätt fack, insats, MAX-nivå och inställning för automatisk dosering för exakt modell och rengör sedan den löstagbara lådan enligt manualen",
        "en_causes": ["Wrong compartment or missing liquid insert", "Additive above the MAX line or too thick", "Auto dispenser empty or disabled", "Washer not level", "Residue, drawer defect or internal dispensing fault"],
        "sv_causes": ["Fel fack eller saknad insats för flytande medel", "Medel över MAX-linjen eller för trögflytande", "Automatisk doserare tom eller avstängd", "Maskinen står inte i nivå", "Rester, lådfel eller internt doseringsfel"],
    },
}


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-042-samsung-cycle-suds-dispenser-before.json").read_text(encoding="utf-8"))
    rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {
        "batch": "042-samsung-cycle-suds-dispenser",
        "status": "proposal_only_not_applied",
        "article_ids": list(ITEMS),
        "sources": [
            "https://www.samsung.com/in/support/home-appliances/why-does-my-washing-machine-take-so-long-to-complete-a-cycle/",
            "https://www.samsung.com/us/support/troubleshoot/TSG10003485/",
            "https://www.samsung.com/de/support/home-appliances/was-bedeuten-die-fehlermeldungen-sud-sd-oc-of-bei-meiner-samsung-waschmaschine/",
            "https://www.samsung.com/sg/support/home-appliances/when-washing-machine-has-excessive-suds/",
            "https://www.samsung.com/us/support/troubleshoot/TSG10002916/",
            "https://www.samsung.com/uk/support/home-appliances/detergent-drawer-recess-cleaning/",
        ],
        "translations": {},
    }
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {
            "code": item["subject"],
            "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]},
            "en": base.make(item, False), "sv": base.make(item, True),
        }
    path = BASE_DIR / "data/article_reviews/batch-042-samsung-cycle-suds-dispenser-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
