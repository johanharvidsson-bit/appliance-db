"""Build reviewed Siemens safety-fault content for batch 038."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline import build_p0_batch_037_deterministic as base


ITEMS = {
    337: {
        "type": "fault", "subject": "heat",
        "en_title": "Siemens Washing Machine Not Heating Water",
        "sv_title": "Siemens-tvättmaskinen värmer inte vattnet",
        "en_meaning": "Siemens states that a confirmed heating fault is not a user repair and requires a trained service engineer",
        "sv_meaning": "Siemens anger att ett bekräftat uppvärmningsfel inte är en användarreparation och kräver utbildad servicetekniker",
        "en_action": "Confirm the selected programme and temperature in the exact E-Nr manual, record any displayed code and arrange Siemens service if heating is genuinely absent",
        "sv_action": "Bekräfta valt program och temperatur i manualen för exakt E‑Nr, dokumentera eventuell visad kod och boka Siemens-service om uppvärmning verkligen uteblir",
        "en_causes": ["Low-temperature or energy-saving programme", "Normal programme temperature control", "Internal heating-element or temperature-sensor fault", "Internal wiring or control fault"],
        "sv_causes": ["Lågtemperatur- eller energisparprogram", "Normal temperaturstyrning i programmet", "Internt fel i värmare eller temperaturgivare", "Internt kablage- eller styrfel"],
    },
    338: {
        "type": "fault", "subject": "vibration",
        "en_title": "Siemens Washing Machine Vibrating Excessively",
        "sv_title": "Siemens-tvättmaskinen vibrerar för mycket",
        "en_meaning": "Siemens links excessive vibration and movement to the floor, levelling, transport bolts and unbalanced loading",
        "sv_meaning": "Siemens kopplar kraftiga vibrationer och rörelse till golvet, nivelleringen, transportbultar och obalanserad last",
        "en_action": "Stop the washer, redistribute the load and verify a hard stable floor, firm level feet and installation according to the exact E-Nr manual",
        "sv_action": "Stoppa maskinen, fördela om lasten och kontrollera hårt stabilt golv, fasta nivellerade fötter och installation enligt manualen för exakt E‑Nr",
        "en_causes": ["Unbalanced, overloaded or underloaded drum", "Washer not level or feet not firm", "Unsuitable or flexible floor", "Transport bolts remain or an internal suspension fault exists"],
        "sv_causes": ["Obalanserad, överlastad eller underlastad trumma", "Maskinen står inte i nivå eller fötterna är inte fasta", "Olämpligt eller sviktande golv", "Transportbultar sitter kvar eller internt upphängningsfel finns"],
    },
    339: {
        "type": "fault", "subject": "wet clothes",
        "en_title": "Clothes Still Wet After a Siemens Wash Cycle",
        "sv_title": "Kläder fortfarande våta efter Siemens-tvätt",
        "en_meaning": "Siemens identifies a low-spin programme, drainage restriction, unbalanced load or blocked user-accessible filter as common reasons for soaking-wet laundry",
        "sv_meaning": "Siemens anger program med låg centrifugering, tömningshinder, obalanserad last eller blockerat användaråtkomligt filter som vanliga orsaker till genomvåt tvätt",
        "en_action": "Check the programme and spin setting, redistribute the load and inspect the visible drain hose and accessible filter as the E-Nr manual specifies",
        "sv_action": "Kontrollera program och centrifugeringsval, fördela om lasten och kontrollera synlig avloppsslang och åtkomligt filter enligt E‑Nr-manualen",
        "en_causes": ["Low or no-spin programme selection", "Unbalanced load", "Kinked or blocked drain hose", "Blocked accessible filter or internal drain fault"],
        "sv_causes": ["Program med låg eller ingen centrifugering", "Obalanserad last", "Vikt eller blockerad avloppsslang", "Blockerat åtkomligt filter eller internt tömningsfel"],
    },
    342: {
        "type": "fault", "subject": "drum",
        "en_title": "Siemens Washing Machine Drum Is Not Turning",
        "sv_title": "Siemens-tvättmaskinens trumma snurrar inte",
        "en_meaning": "Siemens notes that some programme phases intentionally limit drum movement, while a failed belt, motor or drive requires trained service",
        "sv_meaning": "Siemens uppger att vissa programfaser avsiktligt begränsar trummans rörelse, medan fel i rem, motor eller drivning kräver utbildad service",
        "en_action": "Check whether the selected programme is in a normal low-movement phase and record any code; arrange service if the drum remains stationary when movement is expected",
        "sv_action": "Kontrollera om valt program är i en normal fas med liten rörelse och dokumentera eventuell kod; boka service om trumman förblir stilla när rörelse förväntas",
        "en_causes": ["Normal low-movement programme phase", "Excess foam temporarily limits movement", "Internal belt or motor fault", "Internal drive, sensor or control fault"],
        "sv_causes": ["Normal programfas med liten rörelse", "Överskottsskum begränsar rörelsen tillfälligt", "Internt rem- eller motorfel", "Internt driv-, givar- eller styrfel"],
    },
    343: {
        "type": "fault", "subject": "controls",
        "en_title": "Siemens Washing Machine Control Panel Unresponsive",
        "sv_title": "Siemens-tvättmaskinens kontrollpanel svarar inte",
        "en_meaning": "A key or CL symbol can mean the Siemens child lock has disabled the buttons; a dark display can instead indicate a supply or internal fault",
        "sv_meaning": "En nyckel- eller CL-symbol kan betyda att Siemens barnlås har inaktiverat knapparna; släckt display kan i stället tyda på matnings- eller internt fel",
        "en_action": "Identify whether the display shows a key or CL symbol and use only the exact E-Nr manual to release the child lock; if the display is dark, check the plug and circuit protection from a dry safe position",
        "sv_action": "Kontrollera om displayen visar nyckel- eller CL-symbol och använd endast manualen för exakt E‑Nr för att låsa upp barnlåset; om displayen är släckt, kontrollera kontakt och elskydd från en torr säker plats",
        "en_causes": ["Child lock active", "Door or start input not accepted", "No safe mains supply to the appliance", "Internal interface, wiring or control fault"],
        "sv_causes": ["Barnlås aktivt", "Luck- eller startsignal accepteras inte", "Säker nätspänning saknas till maskinen", "Internt fel i gränssnitt, kablage eller styrning"],
    },
}


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-038-siemens-safety-faults-before.json").read_text(encoding="utf-8"))
    rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {
        "batch": "038-siemens-safety-faults",
        "status": "proposal_only_not_applied",
        "article_ids": list(ITEMS),
        "sources": [
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/not-heating",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/vibrates-moves",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/clothes-wet",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/drum-not-turning",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/child-lock",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/not-turning-on",
        ],
        "translations": {},
    }
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {
            "code": item["subject"],
            "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]},
            "en": base.make(item, False), "sv": base.make(item, True),
        }
    path = BASE_DIR / "data/article_reviews/batch-038-siemens-safety-faults-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
