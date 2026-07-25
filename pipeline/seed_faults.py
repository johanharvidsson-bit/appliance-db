"""
pipeline/seed_faults.py

Seeds human-observed faults (symptoms) for a brand + category into the DB.
Faults are brand/category scoped — every model page shows the same list.

After seeding, run map_fault_error_codes.py to link related error codes.

Usage:
    python -m pipeline.seed_faults --brand samsung --category washing-machines
    python -m pipeline.seed_faults --brand lg --category washing-machines
    python -m pipeline.seed_faults --brand samsung --category washing-machines --dry-run
"""

import argparse
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase

console = Console()

# ── Fault definitions ──────────────────────────────────────────────────────────
# Each fault:
#   slug           - URL-safe identifier (unique per brand+category)
#   canonical_name - English symptom description shown in the UI
#   severity       - 'easy' | 'medium' | 'advanced'
#   has_error_code - True if this symptom typically triggers an error code
#   translations   - dict of locale -> {symptom_name, meta_title, meta_description}

FAULT_DATA: dict[tuple[str, str], list[dict]] = {
    ("samsung", "washing-machines"): [
        {
            "slug": "wont-drain",
            "canonical_name": "Washing machine won't drain",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't drain",
                    "meta_title": "Samsung Washing Machine Won't Drain – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that won't drain. Learn what causes drain errors (5E, OE, SC) and how to clear blockages step by step.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen tömmer inte vattnet",
                    "meta_title": "Samsung tvättmaskin tömmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som inte tömmer vattnet. Lär dig vad som orsakar tömningsfel och hur du rensar blockeringar.",
                },
            },
        },
        {
            "slug": "wont-spin",
            "canonical_name": "Washing machine won't spin",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't spin",
                    "meta_title": "Samsung Washing Machine Won't Spin – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that won't spin. Covers unbalanced load errors (UE, Ub), motor faults, and spin cycle problems.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen centrifugerar inte",
                    "meta_title": "Samsung tvättmaskin centrifugerar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som inte centrifugerar. Vi går igenom obalansfel, motorfel och centrifugeringsproblem.",
                },
            },
        },
        {
            "slug": "wont-start",
            "canonical_name": "Washing machine won't start",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't start",
                    "meta_title": "Samsung Washing Machine Won't Start – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that won't turn on or start a cycle. Check the door lock, power supply, and control board.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen startar inte",
                    "meta_title": "Samsung tvättmaskin startar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som inte startar. Kontrollera dörrlås, strömförsörjning och kontrollkort.",
                },
            },
        },
        {
            "slug": "leaking-water",
            "canonical_name": "Washing machine is leaking water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is leaking water",
                    "meta_title": "Samsung Washing Machine Leaking Water – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine leaking water. Covers door seal, hose connections, pump blockages, and leak error codes.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen läcker vatten",
                    "meta_title": "Samsung tvättmaskin läcker vatten – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som läcker. Vi täcker dörrtätning, slanganslutningar och pumphinder.",
                },
            },
        },
        {
            "slug": "wont-fill",
            "canonical_name": "Washing machine won't fill with water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't fill with water",
                    "meta_title": "Samsung Washing Machine Won't Fill – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that won't fill with water. Covers inlet valve, water pressure, hose kinks, and 4E/4C error codes.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen fylls inte med vatten",
                    "meta_title": "Samsung tvättmaskin fylls inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som inte fyller på vatten. Vi går igenom inloppsventil, vattentryck och slangknickar.",
                },
            },
        },
        {
            "slug": "door-wont-open",
            "canonical_name": "Washing machine door won't open",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine door won't open",
                    "meta_title": "Samsung Washing Machine Door Won't Open – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine door that is stuck or won't open. Covers door lock errors (dE, dC, dF), child lock, and water remaining in drum.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinsluckan går inte att öppna",
                    "meta_title": "Samsung tvättmaskin lucka öppnas inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskinslem som sitter fast. Täcker dörrlåsfel, barnlås och kvarvarande vatten i trumman.",
                },
            },
        },
        {
            "slug": "making-loud-noise",
            "canonical_name": "Washing machine is making loud noise",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is making loud noise",
                    "meta_title": "Samsung Washing Machine Making Loud Noise – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine making banging, rattling, or grinding noises. Covers drum bearings, unbalanced load, and foreign objects.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen låter högt",
                    "meta_title": "Samsung tvättmaskin låter högt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin med bankande, skramlande eller malande ljud. Vi täcker lager, obalanserad last och föremål i trumman.",
                },
            },
        },
        {
            "slug": "not-heating-water",
            "canonical_name": "Washing machine not heating water",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine not heating water",
                    "meta_title": "Samsung Washing Machine Not Heating Water – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that isn't heating the water. Covers heating element, thermistor, and temperature sensor error codes (tE, HE).",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen värmer inte vattnet",
                    "meta_title": "Samsung tvättmaskin värmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som inte värmer vattnet. Vi täcker värmeelement, termistor och temperatursensorfel.",
                },
            },
        },
        {
            "slug": "vibrating-excessively",
            "canonical_name": "Washing machine vibrating excessively",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine vibrating excessively",
                    "meta_title": "Samsung Washing Machine Vibrating Too Much – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine with excessive vibration or shaking. Covers levelling feet, transport bolts, drum balance, and floor stability.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen vibrerar kraftigt",
                    "meta_title": "Samsung tvättmaskin vibrerar kraftigt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin med kraftiga vibrationer. Vi täcker nivåfötter, transportbultar och golvstabilitet.",
                },
            },
        },
        {
            "slug": "clothes-still-wet",
            "canonical_name": "Clothes still wet after spin cycle",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Clothes still wet after spin cycle",
                    "meta_title": "Samsung Washing Machine Clothes Still Wet – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine leaving clothes too wet. Covers spin speed settings, unbalanced loads, drainage issues, and spin cycle faults.",
                },
                "sv": {
                    "symptom_name": "Kläderna är fortfarande våta efter centrifugering",
                    "meta_title": "Samsung tvättmaskin – Kläder fortfarande våta – Lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som lämnar kläder för blöta. Vi täcker centrifugeringsinställningar, obalanserade laster och dräneringsproblem.",
                },
            },
        },
        {
            "slug": "bad-smell",
            "canonical_name": "Washing machine has a bad smell",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a bad smell",
                    "meta_title": "Samsung Washing Machine Bad Smell – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine with a bad smell or mould odour. Covers drum cleaning, door seal mould, detergent drawer, and filter maintenance.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar illa",
                    "meta_title": "Samsung tvättmaskin luktar illa – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin med dålig lukt eller mögel. Vi täcker trumrengöring, dörrtätning, tvättmedelslåda och filterunderhåll.",
                },
            },
        },
        {
            "slug": "door-seal-damaged",
            "canonical_name": "Door seal (gasket) is damaged or mouldy",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Door seal is damaged or mouldy",
                    "meta_title": "Samsung Washing Machine Door Seal Damaged – Causes & Fixes",
                    "meta_description": "Fix or replace a Samsung washing machine door seal. Covers mould removal, tear inspection, and step-by-step gasket replacement.",
                },
                "sv": {
                    "symptom_name": "Dörrtätningen är skadad eller möglig",
                    "meta_title": "Samsung tvättmaskin dörrtätning skadad – Orsaker och lösningar",
                    "meta_description": "Åtgärda eller byt dörrtätning på Samsung tvättmaskin. Vi täcker mögelavlägsnande, spricrorkontroll och tätningsbyte.",
                },
            },
        },
        {
            "slug": "drum-not-turning",
            "canonical_name": "Drum is not turning",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Drum is not turning",
                    "meta_title": "Samsung Washing Machine Drum Not Turning – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine where the drum won't rotate. Covers drive belt, motor, carbon brushes, and motor error codes (3E, CE).",
                },
                "sv": {
                    "symptom_name": "Trumman roterar inte",
                    "meta_title": "Samsung tvättmaskin trumma roterar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin där trumman inte roterar. Vi täcker drivrem, motor, kolborstar och motorfelkoder.",
                },
            },
        },
        {
            "slug": "control-panel-unresponsive",
            "canonical_name": "Control panel is unresponsive",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Control panel is unresponsive",
                    "meta_title": "Samsung Washing Machine Control Panel Not Working – Fixes",
                    "meta_description": "Fix a Samsung washing machine with an unresponsive control panel. Covers child lock, power reset, button faults, and control board replacement.",
                },
                "sv": {
                    "symptom_name": "Kontrollpanelen svarar inte",
                    "meta_title": "Samsung tvättmaskin kontrollpanel fungerar inte – Lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin med icke-responsiv kontrollpanel. Vi täcker barnlås, omstart, knappfel och kontrollkortsbyte.",
                },
            },
        },
        {
            "slug": "wont-complete-cycle",
            "canonical_name": "Washing machine won't complete a cycle",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't complete a cycle",
                    "meta_title": "Samsung Washing Machine Stops Mid-Cycle – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that stops or pauses mid-cycle. Covers power supply, error codes, overheating, and door lock faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen slutför inte ett program",
                    "meta_title": "Samsung tvättmaskin stannar mitt i programmet – Lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som stannar mitt i cykeln. Vi täcker strömförsörjning, felkoder, överhettning och dörrlåsfel.",
                },
            },
        },
        {
            "slug": "too-much-foam",
            "canonical_name": "Washing machine producing too much foam",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine producing too much foam",
                    "meta_title": "Samsung Washing Machine Too Much Foam – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine with excessive suds or foam. Covers SUd/5D error codes, detergent type, overloading, and drum cleaning.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen producerar för mycket skum",
                    "meta_title": "Samsung tvättmaskin för mycket skum – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin med för mycket skum eller tvålrester. Vi täcker SUd/5D-felkoder, tvättmedelstyp och överfyllning.",
                },
            },
        },
        {
            "slug": "detergent-not-dispensing",
            "canonical_name": "Detergent not dispensing from the drawer",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Detergent not dispensing from the drawer",
                    "meta_title": "Samsung Washing Machine Detergent Not Dispensing – Fixes",
                    "meta_description": "Fix a Samsung washing machine that isn't dispensing detergent. Covers blocked drawer, water pressure, dispenser clogging, and cleaning steps.",
                },
                "sv": {
                    "symptom_name": "Tvättmedel doseras inte ur lådan",
                    "meta_title": "Samsung tvättmaskin tvättmedel doseras inte – Lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som inte doserar tvättmedel. Vi täcker igentäppt låda, vattentryck och rengöring av tvättmedelsfack.",
                },
            },
        },
        {
            "slug": "trips-electrics",
            "canonical_name": "Washing machine trips the electrics",
            "severity": "advanced",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine trips the electrics",
                    "meta_title": "Samsung Washing Machine Trips Electrics – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine that keeps tripping the circuit breaker or RCD. Covers heating element short, motor fault, wiring, and earth leakage.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen löser ut säkringen",
                    "meta_title": "Samsung tvättmaskin löser ut säkringen – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin som löser ut jordfelsbrytaren. Vi täcker kortslutning i värmeelement, motorfel och jordläckage.",
                },
            },
        },
        {
            "slug": "burning-smell",
            "canonical_name": "Washing machine has a burning smell",
            "severity": "advanced",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a burning smell",
                    "meta_title": "Samsung Washing Machine Burning Smell – Causes & Fixes",
                    "meta_description": "Fix a Samsung washing machine with a burning smell or smoke. Covers motor brushes, drive belt, wiring, and when to stop using the machine immediately.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar bränt",
                    "meta_title": "Samsung tvättmaskin luktar bränt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Samsung tvättmaskin med bränt lukt eller rök. Vi täcker motorkolborstar, drivrem, kablar och när du omedelbart ska sluta använda maskinen.",
                },
            },
        },
    ],

    ("lg", "washing-machines"): [
        {
            "slug": "wont-drain",
            "canonical_name": "Washing machine won't drain",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't drain",
                    "meta_title": "LG Washing Machine Won't Drain – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine that won't drain. Learn what causes OE drain errors and how to clear pump blockages step by step.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen tömmer inte vattnet",
                    "meta_title": "LG tvättmaskin tömmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som inte tömmer vattnet. Lär dig vad som orsakar OE-fel och hur du rensar pumphinder.",
                },
            },
        },
        {
            "slug": "wont-spin",
            "canonical_name": "Washing machine won't spin",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't spin",
                    "meta_title": "LG Washing Machine Won't Spin – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine that won't spin. Covers UE unbalanced load error, motor faults, and spin cycle problems.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen centrifugerar inte",
                    "meta_title": "LG tvättmaskin centrifugerar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som inte centrifugerar. Vi går igenom UE-obalansfel, motorfel och centrifugeringsproblem.",
                },
            },
        },
        {
            "slug": "wont-start",
            "canonical_name": "Washing machine won't start",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't start",
                    "meta_title": "LG Washing Machine Won't Start – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine that won't turn on or start. Covers door errors (dE), power supply, child lock, and control board issues.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen startar inte",
                    "meta_title": "LG tvättmaskin startar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som inte startar. Vi täcker dörrlåsfel (dE), strömförsörjning och barnlås.",
                },
            },
        },
        {
            "slug": "leaking-water",
            "canonical_name": "Washing machine is leaking water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is leaking water",
                    "meta_title": "LG Washing Machine Leaking Water – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine leaking water. Covers FE overflow error, door seal, hose connections, and pump blockages.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen läcker vatten",
                    "meta_title": "LG tvättmaskin läcker vatten – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som läcker. Vi täcker FE-överfyllningsfel, dörrtätning och slangkopplingar.",
                },
            },
        },
        {
            "slug": "wont-fill",
            "canonical_name": "Washing machine won't fill with water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't fill with water",
                    "meta_title": "LG Washing Machine Won't Fill – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine that won't fill with water. Covers IE inlet error, water pressure, inlet valve, and kinked hoses.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen fylls inte med vatten",
                    "meta_title": "LG tvättmaskin fylls inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som inte fyller på vatten. Vi går igenom IE-inloppsfel, vattentryck och inloppsventil.",
                },
            },
        },
        {
            "slug": "door-wont-open",
            "canonical_name": "Washing machine door won't open",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine door won't open",
                    "meta_title": "LG Washing Machine Door Won't Open – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine door that is stuck or won't open. Covers dE door lock errors, water remaining in drum, and child lock.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinsluckan går inte att öppna",
                    "meta_title": "LG tvättmaskin lucka öppnas inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskinslucka som sitter fast. Vi täcker dE-dörrlåsfel, kvarvarande vatten och barnlås.",
                },
            },
        },
        {
            "slug": "making-loud-noise",
            "canonical_name": "Washing machine is making loud noise",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is making loud noise",
                    "meta_title": "LG Washing Machine Making Loud Noise – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine making banging, rattling, or grinding noises. Covers drum bearings, unbalanced load, and foreign objects.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen låter högt",
                    "meta_title": "LG tvättmaskin låter högt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin med höga ljud. Vi täcker lager, obalanserad last och föremål i trumman.",
                },
            },
        },
        {
            "slug": "not-heating-water",
            "canonical_name": "Washing machine not heating water",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine not heating water",
                    "meta_title": "LG Washing Machine Not Heating Water – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine that isn't heating the water. Covers tE thermistor errors, heating element, and temperature sensor faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen värmer inte vattnet",
                    "meta_title": "LG tvättmaskin värmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som inte värmer vattnet. Vi täcker tE-termistorfel, värmeelement och temperatursensorfel.",
                },
            },
        },
        {
            "slug": "vibrating-excessively",
            "canonical_name": "Washing machine vibrating excessively",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine vibrating excessively",
                    "meta_title": "LG Washing Machine Vibrating Too Much – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine with excessive vibration. Covers levelling feet, unbalanced load (UE), transport bolts, and floor stability.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen vibrerar kraftigt",
                    "meta_title": "LG tvättmaskin vibrerar kraftigt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin med kraftiga vibrationer. Vi täcker nivåfötter, obalanserad last (UE) och golvstabilitet.",
                },
            },
        },
        {
            "slug": "drum-not-turning",
            "canonical_name": "Drum is not turning",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Drum is not turning",
                    "meta_title": "LG Washing Machine Drum Not Turning – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine where the drum won't rotate. Covers LE motor lock error, CE motor current fault, drive belt, and carbon brushes.",
                },
                "sv": {
                    "symptom_name": "Trumman roterar inte",
                    "meta_title": "LG tvättmaskin trumma roterar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin där trumman inte roterar. Vi täcker LE-motorlåsfel, CE-motorströmfel och drivrem.",
                },
            },
        },
        {
            "slug": "clothes-still-wet",
            "canonical_name": "Clothes still wet after spin cycle",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Clothes still wet after spin cycle",
                    "meta_title": "LG Washing Machine Clothes Still Wet – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine leaving clothes too wet. Covers spin speed settings, unbalanced load, drain problems, and bearing wear.",
                },
                "sv": {
                    "symptom_name": "Kläderna är fortfarande våta efter centrifugering",
                    "meta_title": "LG tvättmaskin – Kläder fortfarande våta – Lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som lämnar kläder blöta. Vi täcker centrifugeringsinställningar, obalans och lageröslitage.",
                },
            },
        },
        {
            "slug": "bad-smell",
            "canonical_name": "Washing machine has a bad smell",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a bad smell",
                    "meta_title": "LG Washing Machine Bad Smell – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine with a bad smell or mould odour. Covers tub clean cycle (tCL), door seal mould, detergent drawer, and filter.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar illa",
                    "meta_title": "LG tvättmaskin luktar illa – Orsaker och lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin med dålig lukt. Vi täcker trumrengöring (tCL), dörrtätning och tvättmedelslåda.",
                },
            },
        },
        {
            "slug": "child-lock-stuck",
            "canonical_name": "Child lock is active or stuck",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Child lock is active or stuck",
                    "meta_title": "LG Washing Machine Child Lock Active – How to Disable",
                    "meta_description": "Disable or fix a stuck child lock on an LG washing machine. Step-by-step guide to deactivating CL child lock and unlocking the control panel.",
                },
                "sv": {
                    "symptom_name": "Barnlåset är aktiverat eller fastnat",
                    "meta_title": "LG tvättmaskin barnlås aktiverat – Så avaktiverar du det",
                    "meta_description": "Avaktivera eller åtgärda ett fastnat barnlås på LG tvättmaskin. Steg-för-steg-guide för att låsa upp kontrollpanelen.",
                },
            },
        },
        {
            "slug": "error-code-on-display",
            "canonical_name": "An error code is showing on the display",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "An error code is showing on the display",
                    "meta_title": "LG Washing Machine Error Code on Display – What It Means",
                    "meta_description": "Understand LG washing machine error codes on the display. Find out what AE, EE, PE, and PS fault codes mean and how to fix them.",
                },
                "sv": {
                    "symptom_name": "En felkod visas på displayen",
                    "meta_title": "LG tvättmaskin felkod på display – Vad betyder det?",
                    "meta_description": "Förstå LG tvättmaskinens felkoder. Ta reda på vad AE, EE, PE och PS felkoder betyder och hur du åtgärdar dem.",
                },
            },
        },
        {
            "slug": "wont-complete-cycle",
            "canonical_name": "Washing machine won't complete a cycle",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't complete a cycle",
                    "meta_title": "LG Washing Machine Stops Mid-Cycle – Causes & Fixes",
                    "meta_description": "Fix an LG washing machine that stops mid-cycle. Covers power failure (PF), door faults, overheating, and drainage problems.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen slutför inte ett program",
                    "meta_title": "LG tvättmaskin stannar mitt i programmet – Lösningar",
                    "meta_description": "Åtgärda en LG tvättmaskin som stannar under cykeln. Vi täcker strömavbrott (PF), dörrlåsfel och dräneringsproblem.",
                },
            },
        },
    ],

    ("bosch", "washing-machines"): [
        {
            "slug": "wont-drain",
            "canonical_name": "Washing machine won't drain",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't drain",
                    "meta_title": "Bosch Washing Machine Won't Drain – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that won't drain. Learn what causes E20/E25 drain errors and how to clear the pump filter and drain hose step by step.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen tömmer inte vattnet",
                    "meta_title": "Bosch tvättmaskin tömmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som inte tömmer vattnet. Lär dig vad som orsakar E20/E25-fel och hur du rensar pumpen och avloppsslangen.",
                },
            },
        },
        {
            "slug": "wont-spin",
            "canonical_name": "Washing machine won't spin",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't spin",
                    "meta_title": "Bosch Washing Machine Won't Spin – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that won't spin. Covers E50/E52 motor errors, unbalanced load, drive belt, and spin cycle problems.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen centrifugerar inte",
                    "meta_title": "Bosch tvättmaskin centrifugerar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som inte centrifugerar. Vi går igenom E50/E52-motorfel, obalanserad last och drivrem.",
                },
            },
        },
        {
            "slug": "wont-start",
            "canonical_name": "Washing machine won't start",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't start",
                    "meta_title": "Bosch Washing Machine Won't Start – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that won't turn on or start a cycle. Check the door lock, power supply, child lock, and control board.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen startar inte",
                    "meta_title": "Bosch tvättmaskin startar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som inte startar. Kontrollera dörrlås, strömförsörjning och barnlås.",
                },
            },
        },
        {
            "slug": "leaking-water",
            "canonical_name": "Washing machine is leaking water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is leaking water",
                    "meta_title": "Bosch Washing Machine Leaking Water – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine leaking water. Covers door seal, hose connections, pump blockages, and E18/E27 leak-related error codes.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen läcker vatten",
                    "meta_title": "Bosch tvättmaskin läcker vatten – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som läcker. Vi täcker dörrtätning, slanganslutningar och pumphinder.",
                },
            },
        },
        {
            "slug": "wont-fill",
            "canonical_name": "Washing machine won't fill with water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't fill with water",
                    "meta_title": "Bosch Washing Machine Won't Fill – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that won't fill with water. Covers E16/E17 inlet errors, inlet valve, water pressure, and hose kinks.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen fylls inte med vatten",
                    "meta_title": "Bosch tvättmaskin fylls inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som inte fyller på vatten. Vi går igenom E16/E17-inloppsfel, inloppsventil och vattentryck.",
                },
            },
        },
        {
            "slug": "door-wont-open",
            "canonical_name": "Washing machine door won't open",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine door won't open",
                    "meta_title": "Bosch Washing Machine Door Won't Open – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine door that is stuck or won't open. Covers E44/E45 door lock errors, child lock, and water remaining in drum.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinsluckan går inte att öppna",
                    "meta_title": "Bosch tvättmaskin lucka öppnas inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskinslucka som sitter fast. Täcker E44/E45-dörrlåsfel, barnlås och kvarvarande vatten i trumman.",
                },
            },
        },
        {
            "slug": "making-loud-noise",
            "canonical_name": "Washing machine is making loud noise",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is making loud noise",
                    "meta_title": "Bosch Washing Machine Making Loud Noise – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine making banging, rattling, or grinding noises. Covers drum bearings, unbalanced load, worn drive belt, and foreign objects.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen låter högt",
                    "meta_title": "Bosch tvättmaskin låter högt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin med bankande eller malande ljud. Vi täcker lager, obalanserad last och föremål i trumman.",
                },
            },
        },
        {
            "slug": "not-heating-water",
            "canonical_name": "Washing machine not heating water",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine not heating water",
                    "meta_title": "Bosch Washing Machine Not Heating Water – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that isn't heating the water. Covers E60–E69 heating element errors, thermistor, and NTC temperature sensor faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen värmer inte vattnet",
                    "meta_title": "Bosch tvättmaskin värmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som inte värmer vattnet. Vi täcker E60–E69 värmeelement, termistor och temperatursensorfel.",
                },
            },
        },
        {
            "slug": "vibrating-excessively",
            "canonical_name": "Washing machine vibrating excessively",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine vibrating excessively",
                    "meta_title": "Bosch Washing Machine Vibrating Too Much – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine with excessive vibration or shaking. Covers levelling feet, transport bolts, drum balance, and floor stability.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen vibrerar kraftigt",
                    "meta_title": "Bosch tvättmaskin vibrerar kraftigt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin med kraftiga vibrationer. Vi täcker nivåfötter, transportbultar och golvstabilitet.",
                },
            },
        },
        {
            "slug": "clothes-still-wet",
            "canonical_name": "Clothes still wet after spin cycle",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Clothes still wet after spin cycle",
                    "meta_title": "Bosch Washing Machine Clothes Still Wet – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine leaving clothes too wet after spinning. Covers spin speed settings, unbalanced loads, and drainage issues.",
                },
                "sv": {
                    "symptom_name": "Kläderna är fortfarande våta efter centrifugering",
                    "meta_title": "Bosch tvättmaskin – Kläder fortfarande våta – Lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som lämnar kläder för blöta. Vi täcker centrifugeringsinställningar och dräneringsproblem.",
                },
            },
        },
        {
            "slug": "bad-smell",
            "canonical_name": "Washing machine has a bad smell",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a bad smell",
                    "meta_title": "Bosch Washing Machine Bad Smell – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine with a bad smell or mould odour. Covers drum cleaning, door seal mould, detergent drawer, and filter maintenance.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar illa",
                    "meta_title": "Bosch tvättmaskin luktar illa – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin med dålig lukt eller mögel. Vi täcker trumrengöring, dörrtätning och filterunderhåll.",
                },
            },
        },
        {
            "slug": "door-seal-damaged",
            "canonical_name": "Door seal (gasket) is damaged or mouldy",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Door seal is damaged or mouldy",
                    "meta_title": "Bosch Washing Machine Door Seal Damaged – Causes & Fixes",
                    "meta_description": "Fix or replace a Bosch washing machine door seal (gasket). Covers mould removal, tear inspection, and step-by-step gasket replacement.",
                },
                "sv": {
                    "symptom_name": "Dörrtätningen är skadad eller möglig",
                    "meta_title": "Bosch tvättmaskin dörrtätning skadad – Orsaker och lösningar",
                    "meta_description": "Åtgärda eller byt dörrtätning på Bosch tvättmaskin. Vi täcker mögelavlägsnande och steg-för-steg tätningsbyte.",
                },
            },
        },
        {
            "slug": "drum-not-turning",
            "canonical_name": "Drum is not turning",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Drum is not turning",
                    "meta_title": "Bosch Washing Machine Drum Not Turning – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine where the drum won't rotate. Covers E50 motor fault, drive belt, carbon brushes, and drum bearing failure.",
                },
                "sv": {
                    "symptom_name": "Trumman roterar inte",
                    "meta_title": "Bosch tvättmaskin trumma roterar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin där trumman inte roterar. Vi täcker E50-motorfel, drivrem och lager.",
                },
            },
        },
        {
            "slug": "control-panel-unresponsive",
            "canonical_name": "Control panel is unresponsive",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Control panel is unresponsive",
                    "meta_title": "Bosch Washing Machine Control Panel Not Working – Fixes",
                    "meta_description": "Fix a Bosch washing machine with an unresponsive control panel. Covers child lock, power reset, E91/E92 control board errors, and button faults.",
                },
                "sv": {
                    "symptom_name": "Kontrollpanelen svarar inte",
                    "meta_title": "Bosch tvättmaskin kontrollpanel fungerar inte – Lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin med icke-responsiv kontrollpanel. Vi täcker barnlås, omstart och E91/E92-kontrollkortsfel.",
                },
            },
        },
        {
            "slug": "wont-complete-cycle",
            "canonical_name": "Washing machine won't complete a cycle",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't complete a cycle",
                    "meta_title": "Bosch Washing Machine Stops Mid-Cycle – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that stops or pauses mid-cycle. Covers power supply, error codes, overheating, and door lock faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen slutför inte ett program",
                    "meta_title": "Bosch tvättmaskin stannar mitt i programmet – Lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som stannar mitt i cykeln. Vi täcker strömförsörjning, felkoder och dörrlåsfel.",
                },
            },
        },
        {
            "slug": "too-much-foam",
            "canonical_name": "Washing machine producing too much foam",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine producing too much foam",
                    "meta_title": "Bosch Washing Machine Too Much Foam – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine with excessive suds or foam. Covers detergent type, HE detergent requirements, overloading, and drum cleaning.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen producerar för mycket skum",
                    "meta_title": "Bosch tvättmaskin för mycket skum – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin med för mycket skum. Vi täcker tvättmedelstyp, överfyllning och trumrengöring.",
                },
            },
        },
        {
            "slug": "detergent-not-dispensing",
            "canonical_name": "Detergent not dispensing from the drawer",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Detergent not dispensing from the drawer",
                    "meta_title": "Bosch Washing Machine Detergent Not Dispensing – Fixes",
                    "meta_description": "Fix a Bosch washing machine that isn't dispensing detergent. Covers blocked drawer, water pressure, dispenser clogging, and cleaning steps.",
                },
                "sv": {
                    "symptom_name": "Tvättmedel doseras inte ur lådan",
                    "meta_title": "Bosch tvättmaskin tvättmedel doseras inte – Lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som inte doserar tvättmedel. Vi täcker igentäppt låda, vattentryck och rengöring.",
                },
            },
        },
        {
            "slug": "trips-electrics",
            "canonical_name": "Washing machine trips the electrics",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine trips the electrics",
                    "meta_title": "Bosch Washing Machine Trips Electrics – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine that trips the circuit breaker or RCD. Covers E68 earth leakage, heating element short, motor fault, and wiring.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen löser ut säkringen",
                    "meta_title": "Bosch tvättmaskin löser ut säkringen – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin som löser ut jordfelsbrytaren. Vi täcker E68 jordläckage, kortslutning i värmeelement och motorfel.",
                },
            },
        },
        {
            "slug": "burning-smell",
            "canonical_name": "Washing machine has a burning smell",
            "severity": "advanced",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a burning smell",
                    "meta_title": "Bosch Washing Machine Burning Smell – Causes & Fixes",
                    "meta_description": "Fix a Bosch washing machine with a burning smell or smoke. Covers motor brushes, drive belt, wiring faults, and when to stop using the machine immediately.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar bränt",
                    "meta_title": "Bosch tvättmaskin luktar bränt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Bosch tvättmaskin med bränt lukt. Vi täcker motorkolborstar, drivrem och kablar.",
                },
            },
        },
    ],

    ("siemens", "washing-machines"): [
        {
            "slug": "wont-drain",
            "canonical_name": "Washing machine won't drain",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't drain",
                    "meta_title": "Siemens Washing Machine Won't Drain – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that won't drain. Learn what causes E20/E25 drain errors and how to clear the pump filter and drain hose step by step.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen tömmer inte vattnet",
                    "meta_title": "Siemens tvättmaskin tömmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som inte tömmer vattnet. Lär dig vad som orsakar E20/E25-fel och hur du rensar pumpen.",
                },
            },
        },
        {
            "slug": "wont-spin",
            "canonical_name": "Washing machine won't spin",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't spin",
                    "meta_title": "Siemens Washing Machine Won't Spin – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that won't spin. Covers E50/E52 motor errors, unbalanced load, drive belt, and spin cycle problems.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen centrifugerar inte",
                    "meta_title": "Siemens tvättmaskin centrifugerar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som inte centrifugerar. Vi går igenom E50/E52-motorfel, obalanserad last och drivrem.",
                },
            },
        },
        {
            "slug": "wont-start",
            "canonical_name": "Washing machine won't start",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't start",
                    "meta_title": "Siemens Washing Machine Won't Start – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that won't turn on or start a cycle. Check the door lock, power supply, child lock, and control board.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen startar inte",
                    "meta_title": "Siemens tvättmaskin startar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som inte startar. Kontrollera dörrlås, strömförsörjning och barnlås.",
                },
            },
        },
        {
            "slug": "leaking-water",
            "canonical_name": "Washing machine is leaking water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is leaking water",
                    "meta_title": "Siemens Washing Machine Leaking Water – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine leaking water. Covers door seal, hose connections, pump blockages, and E18/E27 leak-related error codes.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen läcker vatten",
                    "meta_title": "Siemens tvättmaskin läcker vatten – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som läcker. Vi täcker dörrtätning, slanganslutningar och pumphinder.",
                },
            },
        },
        {
            "slug": "wont-fill",
            "canonical_name": "Washing machine won't fill with water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't fill with water",
                    "meta_title": "Siemens Washing Machine Won't Fill – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that won't fill with water. Covers E16/E17 inlet errors, inlet valve, water pressure, and hose kinks.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen fylls inte med vatten",
                    "meta_title": "Siemens tvättmaskin fylls inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som inte fyller på vatten. Vi går igenom E16/E17-inloppsfel, inloppsventil och vattentryck.",
                },
            },
        },
        {
            "slug": "door-wont-open",
            "canonical_name": "Washing machine door won't open",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine door won't open",
                    "meta_title": "Siemens Washing Machine Door Won't Open – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine door that is stuck or won't open. Covers E44/E45 door lock errors, child lock, and water remaining in drum.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinsluckan går inte att öppna",
                    "meta_title": "Siemens tvättmaskin lucka öppnas inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskinslucka som sitter fast. Täcker E44/E45-dörrlåsfel, barnlås och kvarvarande vatten.",
                },
            },
        },
        {
            "slug": "making-loud-noise",
            "canonical_name": "Washing machine is making loud noise",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is making loud noise",
                    "meta_title": "Siemens Washing Machine Making Loud Noise – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine making banging, rattling, or grinding noises. Covers drum bearings, unbalanced load, and foreign objects.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen låter högt",
                    "meta_title": "Siemens tvättmaskin låter högt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin med bankande eller malande ljud. Vi täcker lager, obalanserad last och föremål i trumman.",
                },
            },
        },
        {
            "slug": "not-heating-water",
            "canonical_name": "Washing machine not heating water",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine not heating water",
                    "meta_title": "Siemens Washing Machine Not Heating Water – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that isn't heating the water. Covers E60–E69 heating element errors, thermistor, and NTC temperature sensor faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen värmer inte vattnet",
                    "meta_title": "Siemens tvättmaskin värmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som inte värmer vattnet. Vi täcker E60–E69 värmeelement och temperatursensorfel.",
                },
            },
        },
        {
            "slug": "vibrating-excessively",
            "canonical_name": "Washing machine vibrating excessively",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine vibrating excessively",
                    "meta_title": "Siemens Washing Machine Vibrating Too Much – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine with excessive vibration or shaking. Covers levelling feet, transport bolts, drum balance, and floor stability.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen vibrerar kraftigt",
                    "meta_title": "Siemens tvättmaskin vibrerar kraftigt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin med kraftiga vibrationer. Vi täcker nivåfötter, transportbultar och golvstabilitet.",
                },
            },
        },
        {
            "slug": "clothes-still-wet",
            "canonical_name": "Clothes still wet after spin cycle",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Clothes still wet after spin cycle",
                    "meta_title": "Siemens Washing Machine Clothes Still Wet – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine leaving clothes too wet after spinning. Covers spin speed settings, unbalanced loads, and drainage issues.",
                },
                "sv": {
                    "symptom_name": "Kläderna är fortfarande våta efter centrifugering",
                    "meta_title": "Siemens tvättmaskin – Kläder fortfarande våta – Lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som lämnar kläder för blöta. Vi täcker centrifugeringsinställningar och dräneringsproblem.",
                },
            },
        },
        {
            "slug": "bad-smell",
            "canonical_name": "Washing machine has a bad smell",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a bad smell",
                    "meta_title": "Siemens Washing Machine Bad Smell – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine with a bad smell or mould odour. Covers drum cleaning, door seal mould, detergent drawer, and filter maintenance.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar illa",
                    "meta_title": "Siemens tvättmaskin luktar illa – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin med dålig lukt eller mögel. Vi täcker trumrengöring, dörrtätning och filterunderhåll.",
                },
            },
        },
        {
            "slug": "door-seal-damaged",
            "canonical_name": "Door seal (gasket) is damaged or mouldy",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Door seal is damaged or mouldy",
                    "meta_title": "Siemens Washing Machine Door Seal Damaged – Causes & Fixes",
                    "meta_description": "Fix or replace a Siemens washing machine door seal (gasket). Covers mould removal, tear inspection, and step-by-step gasket replacement.",
                },
                "sv": {
                    "symptom_name": "Dörrtätningen är skadad eller möglig",
                    "meta_title": "Siemens tvättmaskin dörrtätning skadad – Orsaker och lösningar",
                    "meta_description": "Åtgärda eller byt dörrtätning på Siemens tvättmaskin. Vi täcker mögelavlägsnande och steg-för-steg tätningsbyte.",
                },
            },
        },
        {
            "slug": "drum-not-turning",
            "canonical_name": "Drum is not turning",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Drum is not turning",
                    "meta_title": "Siemens Washing Machine Drum Not Turning – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine where the drum won't rotate. Covers E50 motor fault, drive belt, carbon brushes, and drum bearing failure.",
                },
                "sv": {
                    "symptom_name": "Trumman roterar inte",
                    "meta_title": "Siemens tvättmaskin trumma roterar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin där trumman inte roterar. Vi täcker E50-motorfel, drivrem och lager.",
                },
            },
        },
        {
            "slug": "control-panel-unresponsive",
            "canonical_name": "Control panel is unresponsive",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Control panel is unresponsive",
                    "meta_title": "Siemens Washing Machine Control Panel Not Working – Fixes",
                    "meta_description": "Fix a Siemens washing machine with an unresponsive control panel. Covers child lock, power reset, E91/E92 control board errors, and button faults.",
                },
                "sv": {
                    "symptom_name": "Kontrollpanelen svarar inte",
                    "meta_title": "Siemens tvättmaskin kontrollpanel fungerar inte – Lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin med icke-responsiv kontrollpanel. Vi täcker barnlås, omstart och E91/E92-kontrollkortsfel.",
                },
            },
        },
        {
            "slug": "wont-complete-cycle",
            "canonical_name": "Washing machine won't complete a cycle",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't complete a cycle",
                    "meta_title": "Siemens Washing Machine Stops Mid-Cycle – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that stops or pauses mid-cycle. Covers power supply, error codes, overheating, and door lock faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen slutför inte ett program",
                    "meta_title": "Siemens tvättmaskin stannar mitt i programmet – Lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som stannar mitt i cykeln. Vi täcker strömförsörjning, felkoder och dörrlåsfel.",
                },
            },
        },
        {
            "slug": "too-much-foam",
            "canonical_name": "Washing machine producing too much foam",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine producing too much foam",
                    "meta_title": "Siemens Washing Machine Too Much Foam – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine with excessive suds or foam. Covers detergent type, HE detergent requirements, overloading, and drum cleaning.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen producerar för mycket skum",
                    "meta_title": "Siemens tvättmaskin för mycket skum – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin med för mycket skum. Vi täcker tvättmedelstyp, överfyllning och trumrengöring.",
                },
            },
        },
        {
            "slug": "detergent-not-dispensing",
            "canonical_name": "Detergent not dispensing from the drawer",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Detergent not dispensing from the drawer",
                    "meta_title": "Siemens Washing Machine Detergent Not Dispensing – Fixes",
                    "meta_description": "Fix a Siemens washing machine that isn't dispensing detergent. Covers blocked drawer, water pressure, dispenser clogging, and cleaning steps.",
                },
                "sv": {
                    "symptom_name": "Tvättmedel doseras inte ur lådan",
                    "meta_title": "Siemens tvättmaskin tvättmedel doseras inte – Lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som inte doserar tvättmedel. Vi täcker igentäppt låda, vattentryck och rengöring.",
                },
            },
        },
        {
            "slug": "trips-electrics",
            "canonical_name": "Washing machine trips the electrics",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine trips the electrics",
                    "meta_title": "Siemens Washing Machine Trips Electrics – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine that trips the circuit breaker or RCD. Covers E68 earth leakage, heating element short, motor fault, and wiring.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen löser ut säkringen",
                    "meta_title": "Siemens tvättmaskin löser ut säkringen – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin som löser ut jordfelsbrytaren. Vi täcker E68 jordläckage, kortslutning och motorfel.",
                },
            },
        },
        {
            "slug": "burning-smell",
            "canonical_name": "Washing machine has a burning smell",
            "severity": "advanced",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a burning smell",
                    "meta_title": "Siemens Washing Machine Burning Smell – Causes & Fixes",
                    "meta_description": "Fix a Siemens washing machine with a burning smell or smoke. Covers motor brushes, drive belt, wiring faults, and when to stop using the machine immediately.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar bränt",
                    "meta_title": "Siemens tvättmaskin luktar bränt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Siemens tvättmaskin med bränt lukt. Vi täcker motorkolborstar, drivrem och kablar.",
                },
            },
        },
    ],

    ("electrolux", "washing-machines"): [
        {
            "slug": "wont-drain",
            "canonical_name": "Washing machine won't drain",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't drain",
                    "meta_title": "Electrolux Washing Machine Won't Drain – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that won't drain. Learn what causes E20/E21/E25 drain errors and how to clear the pump filter and drain hose.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen tömmer inte vattnet",
                    "meta_title": "Electrolux tvättmaskin tömmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som inte tömmer vattnet. Lär dig vad som orsakar E20/E21/E25-fel och hur du rensar pumpen.",
                },
            },
        },
        {
            "slug": "wont-spin",
            "canonical_name": "Washing machine won't spin",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't spin",
                    "meta_title": "Electrolux Washing Machine Won't Spin – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that won't spin. Covers E50/E52/E59 motor errors, unbalanced load, drive belt, and spin cycle problems.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen centrifugerar inte",
                    "meta_title": "Electrolux tvättmaskin centrifugerar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som inte centrifugerar. Vi går igenom E50/E52/E59-motorfel och drivrem.",
                },
            },
        },
        {
            "slug": "wont-start",
            "canonical_name": "Washing machine won't start",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't start",
                    "meta_title": "Electrolux Washing Machine Won't Start – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that won't turn on or start a cycle. Check the door lock (E40/E41), power supply, and control board.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen startar inte",
                    "meta_title": "Electrolux tvättmaskin startar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som inte startar. Kontrollera dörrlås (E40/E41), strömförsörjning och barnlås.",
                },
            },
        },
        {
            "slug": "leaking-water",
            "canonical_name": "Washing machine is leaking water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is leaking water",
                    "meta_title": "Electrolux Washing Machine Leaking Water – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine leaking water. Covers E13 base leak sensor, EF0 overflow, door seal, hose connections, and pump blockages.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen läcker vatten",
                    "meta_title": "Electrolux tvättmaskin läcker vatten – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som läcker. Vi täcker E13-baskälarsensor, EF0 och dörrtätning.",
                },
            },
        },
        {
            "slug": "wont-fill",
            "canonical_name": "Washing machine won't fill with water",
            "severity": "medium",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't fill with water",
                    "meta_title": "Electrolux Washing Machine Won't Fill – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that won't fill with water. Covers E10/E11 inlet errors, inlet valve, water pressure, and hose kinks.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen fylls inte med vatten",
                    "meta_title": "Electrolux tvättmaskin fylls inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som inte fyller på vatten. Vi går igenom E10/E11-inloppsfel, inloppsventil och vattentryck.",
                },
            },
        },
        {
            "slug": "door-wont-open",
            "canonical_name": "Washing machine door won't open",
            "severity": "easy",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine door won't open",
                    "meta_title": "Electrolux Washing Machine Door Won't Open – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine door that is stuck or won't open. Covers E40/E41/E42 door errors, child lock, and water remaining in drum.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinsluckan går inte att öppna",
                    "meta_title": "Electrolux tvättmaskin lucka öppnas inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskinslucka som sitter fast. Täcker E40/E41/E42-dörrlåsfel, barnlås och kvarvarande vatten.",
                },
            },
        },
        {
            "slug": "making-loud-noise",
            "canonical_name": "Washing machine is making loud noise",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine is making loud noise",
                    "meta_title": "Electrolux Washing Machine Making Loud Noise – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine making banging, rattling, or grinding noises. Covers drum bearings, unbalanced load, and foreign objects.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen låter högt",
                    "meta_title": "Electrolux tvättmaskin låter högt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin med bankande eller malande ljud. Vi täcker lager, obalanserad last och föremål i trumman.",
                },
            },
        },
        {
            "slug": "not-heating-water",
            "canonical_name": "Washing machine not heating water",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine not heating water",
                    "meta_title": "Electrolux Washing Machine Not Heating Water – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that isn't heating the water. Covers E60/E61/E62 heating element errors, E71 thermistor, and temperature sensor faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen värmer inte vattnet",
                    "meta_title": "Electrolux tvättmaskin värmer inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som inte värmer vattnet. Vi täcker E60/E61/E62 värmeelement och E71 temperatursensor.",
                },
            },
        },
        {
            "slug": "vibrating-excessively",
            "canonical_name": "Washing machine vibrating excessively",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine vibrating excessively",
                    "meta_title": "Electrolux Washing Machine Vibrating Too Much – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine with excessive vibration or shaking. Covers levelling feet, transport bolts, drum balance, and floor stability.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen vibrerar kraftigt",
                    "meta_title": "Electrolux tvättmaskin vibrerar kraftigt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin med kraftiga vibrationer. Vi täcker nivåfötter, transportbultar och golvstabilitet.",
                },
            },
        },
        {
            "slug": "clothes-still-wet",
            "canonical_name": "Clothes still wet after spin cycle",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Clothes still wet after spin cycle",
                    "meta_title": "Electrolux Washing Machine Clothes Still Wet – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine leaving clothes too wet after spinning. Covers spin speed settings, unbalanced loads, and drainage issues.",
                },
                "sv": {
                    "symptom_name": "Kläderna är fortfarande våta efter centrifugering",
                    "meta_title": "Electrolux tvättmaskin – Kläder fortfarande våta – Lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som lämnar kläder för blöta. Vi täcker centrifugeringsinställningar och dräneringsproblem.",
                },
            },
        },
        {
            "slug": "bad-smell",
            "canonical_name": "Washing machine has a bad smell",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a bad smell",
                    "meta_title": "Electrolux Washing Machine Bad Smell – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine with a bad smell or mould odour. Covers drum cleaning, door seal mould, detergent drawer, and filter maintenance.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar illa",
                    "meta_title": "Electrolux tvättmaskin luktar illa – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin med dålig lukt eller mögel. Vi täcker trumrengöring, dörrtätning och filterunderhåll.",
                },
            },
        },
        {
            "slug": "door-seal-damaged",
            "canonical_name": "Door seal (gasket) is damaged or mouldy",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Door seal is damaged or mouldy",
                    "meta_title": "Electrolux Washing Machine Door Seal Damaged – Causes & Fixes",
                    "meta_description": "Fix or replace an Electrolux washing machine door seal (gasket). Covers mould removal, tear inspection, and step-by-step gasket replacement.",
                },
                "sv": {
                    "symptom_name": "Dörrtätningen är skadad eller möglig",
                    "meta_title": "Electrolux tvättmaskin dörrtätning skadad – Orsaker och lösningar",
                    "meta_description": "Åtgärda eller byt dörrtätning på Electrolux tvättmaskin. Vi täcker mögelavlägsnande och steg-för-steg tätningsbyte.",
                },
            },
        },
        {
            "slug": "drum-not-turning",
            "canonical_name": "Drum is not turning",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Drum is not turning",
                    "meta_title": "Electrolux Washing Machine Drum Not Turning – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine where the drum won't rotate. Covers E50/E51/E54 motor faults, drive belt, carbon brushes, and drum bearing failure.",
                },
                "sv": {
                    "symptom_name": "Trumman roterar inte",
                    "meta_title": "Electrolux tvättmaskin trumma roterar inte – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin där trumman inte roterar. Vi täcker E50/E51/E54-motorfel, drivrem och lager.",
                },
            },
        },
        {
            "slug": "control-panel-unresponsive",
            "canonical_name": "Control panel is unresponsive",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Control panel is unresponsive",
                    "meta_title": "Electrolux Washing Machine Control Panel Not Working – Fixes",
                    "meta_description": "Fix an Electrolux washing machine with an unresponsive control panel. Covers child lock, power reset, E91/E92/E93 control board errors, and button faults.",
                },
                "sv": {
                    "symptom_name": "Kontrollpanelen svarar inte",
                    "meta_title": "Electrolux tvättmaskin kontrollpanel fungerar inte – Lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin med icke-responsiv kontrollpanel. Vi täcker barnlås, omstart och E91/E92/E93-kontrollkortsfel.",
                },
            },
        },
        {
            "slug": "wont-complete-cycle",
            "canonical_name": "Washing machine won't complete a cycle",
            "severity": "medium",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine won't complete a cycle",
                    "meta_title": "Electrolux Washing Machine Stops Mid-Cycle – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that stops or pauses mid-cycle. Covers power supply, error codes, overheating, and door lock faults.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen slutför inte ett program",
                    "meta_title": "Electrolux tvättmaskin stannar mitt i programmet – Lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som stannar mitt i cykeln. Vi täcker strömförsörjning, felkoder och dörrlåsfel.",
                },
            },
        },
        {
            "slug": "too-much-foam",
            "canonical_name": "Washing machine producing too much foam",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine producing too much foam",
                    "meta_title": "Electrolux Washing Machine Too Much Foam – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine with excessive suds or foam. Covers detergent type, HE detergent requirements, overloading, and drum cleaning.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen producerar för mycket skum",
                    "meta_title": "Electrolux tvättmaskin för mycket skum – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin med för mycket skum. Vi täcker tvättmedelstyp, överfyllning och trumrengöring.",
                },
            },
        },
        {
            "slug": "detergent-not-dispensing",
            "canonical_name": "Detergent not dispensing from the drawer",
            "severity": "easy",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Detergent not dispensing from the drawer",
                    "meta_title": "Electrolux Washing Machine Detergent Not Dispensing – Fixes",
                    "meta_description": "Fix an Electrolux washing machine that isn't dispensing detergent. Covers blocked drawer, water pressure, dispenser clogging, and cleaning steps.",
                },
                "sv": {
                    "symptom_name": "Tvättmedel doseras inte ur lådan",
                    "meta_title": "Electrolux tvättmaskin tvättmedel doseras inte – Lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som inte doserar tvättmedel. Vi täcker igentäppt låda, vattentryck och rengöring.",
                },
            },
        },
        {
            "slug": "trips-electrics",
            "canonical_name": "Washing machine trips the electrics",
            "severity": "advanced",
            "has_error_code": True,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine trips the electrics",
                    "meta_title": "Electrolux Washing Machine Trips Electrics – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine that trips the circuit breaker or RCD. Covers E68 earth leakage, heating element short, motor fault, and wiring.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen löser ut säkringen",
                    "meta_title": "Electrolux tvättmaskin löser ut säkringen – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin som löser ut jordfelsbrytaren. Vi täcker E68 jordläckage, kortslutning och motorfel.",
                },
            },
        },
        {
            "slug": "burning-smell",
            "canonical_name": "Washing machine has a burning smell",
            "severity": "advanced",
            "has_error_code": False,
            "translations": {
                "en": {
                    "symptom_name": "Washing machine has a burning smell",
                    "meta_title": "Electrolux Washing Machine Burning Smell – Causes & Fixes",
                    "meta_description": "Fix an Electrolux washing machine with a burning smell or smoke. Covers motor brushes, drive belt, wiring faults, and when to stop using the machine immediately.",
                },
                "sv": {
                    "symptom_name": "Tvättmaskinen luktar bränt",
                    "meta_title": "Electrolux tvättmaskin luktar bränt – Orsaker och lösningar",
                    "meta_description": "Åtgärda en Electrolux tvättmaskin med bränt lukt. Vi täcker motorkolborstar, drivrem och kablar.",
                },
            },
        },
    ],
}


# ── Seeding logic ──────────────────────────────────────────────────────────────

def seed(brand_slug: str, category_slug: str, dry_run: bool = False) -> int:
    key = (brand_slug, category_slug)
    faults = FAULT_DATA.get(key)
    if not faults:
        console.print(f"[yellow]No fault data for {brand_slug}/{category_slug}[/yellow]")
        return 0

    brand    = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    if not brand.data or not category.data:
        console.print(f"[red]Brand '{brand_slug}' or category '{category_slug}' not found[/red]")
        return 0

    brand_id    = brand.data["id"]
    category_id = category.data["id"]
    brand_name  = brand.data["name"]

    existing = (
        supabase.table("faults")
        .select("slug")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []
    existing_slugs = {r["slug"] for r in existing}

    to_insert = [f for f in faults if f["slug"] not in existing_slugs]
    already   = [f for f in faults if f["slug"] in existing_slugs]

    t = Table(title=f"Fault seed plan — {brand_name} / {category_slug}", box=box.SIMPLE)
    t.add_column("Slug",       style="bold", width=28)
    t.add_column("Status",     width=10)
    t.add_column("Severity",   width=10)
    t.add_column("Canonical name", width=42)
    for f in faults:
        status = "[dim]exists[/dim]" if f["slug"] in existing_slugs else "[green]new[/green]"
        t.add_row(f["slug"], status, f["severity"], f["canonical_name"])
    console.print(t)
    console.print(f"\n{len(to_insert)} to insert, {len(already)} already exist.")

    if dry_run:
        console.print("[dim]Dry run — no DB writes.[/dim]")
        return 0

    if not to_insert:
        console.print("[dim]Nothing to insert.[/dim]")
        return 0

    inserted = 0
    for f in to_insert:
        # Insert fault row
        result = (
            supabase.table("faults")
            .insert({
                "brand_id":       brand_id,
                "category_id":    category_id,
                "slug":           f["slug"],
                "canonical_name": f["canonical_name"],
                "severity":       f["severity"],
                "has_error_code": f["has_error_code"],
            })
            .execute()
        )
        fault_id = result.data[0]["id"]

        # Insert translations
        translation_rows = [
            {
                "fault_id":         fault_id,
                "locale":           locale,
                "symptom_name":     tr["symptom_name"],
                "meta_title":       tr.get("meta_title"),
                "meta_description": tr.get("meta_description"),
            }
            for locale, tr in f.get("translations", {}).items()
        ]
        if translation_rows:
            supabase.table("fault_translations").insert(translation_rows).execute()

        logger.info(f"  Inserted fault: {f['slug']} (id={fault_id}, {len(translation_rows)} translations)")
        inserted += 1

    console.print(f"[bold green]Inserted {inserted} faults with translations.[/bold green]")
    console.print("Run [bold]python -m pipeline.map_fault_error_codes --brand {brand_slug} --category {category_slug}[/bold] next.")
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed faults into DB")
    parser.add_argument("--brand",    default="samsung")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()
    seed(args.brand, args.category, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
