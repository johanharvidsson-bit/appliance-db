"""
pipeline/seed_error_codes.py

Seeds known error codes for brands where PDF/image extraction is not possible.
After seeding, run enrich_error_codes.py to populate descriptions via Google + Claude.

Usage:
    python -m pipeline.seed_error_codes --brand lg --category washing-machines
    python -m pipeline.seed_error_codes --brand lg --category washing-machines --dry-run
"""

import argparse
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import box

from config.settings import supabase
from scrapers.bsh_error_codes_web import scrape_bsh_error_codes

console = Console()

# Brands that share the BSH error code set (fetched live from the web)
_BSH_BRANDS = {"bosch", "siemens"}

# ── Known error code sets ──────────────────────────────────────────────────────

SEED_DATA: dict[tuple[str, str], list[dict]] = {
    ("lg", "washing-machines"): [
        {"code": "IE",  "display_text": "Water inlet error. Water has not filled to the required level within the set time."},
        {"code": "OE",  "display_text": "Drain error. Water has not drained within the set time."},
        {"code": "UE",  "display_text": "Unbalanced load error. The laundry is not evenly distributed in the drum."},
        {"code": "FE",  "display_text": "Water overflow error. The water level in the tub is too high."},
        {"code": "PE",  "display_text": "Water level sensor error. The pressure sensor is not functioning correctly."},
        {"code": "LE",  "display_text": "Motor locked error. The motor is unable to rotate."},
        {"code": "CE",  "display_text": "Motor current error. Overcurrent has been detected in the motor."},
        {"code": "dE",  "display_text": "Door open error. The door is not closed properly or the door lock has failed."},
        {"code": "dE1", "display_text": "Door open error (variant). The door is not fully latched during the cycle."},
        {"code": "dE2", "display_text": "Door open error during cycle. Door was opened mid-cycle."},
        {"code": "tE",  "display_text": "Heater sensor error. The thermistor is not detecting the correct temperature."},
        {"code": "tE1", "display_text": "NTC temperature sensor error. The main thermistor reading is out of range."},
        {"code": "tE2", "display_text": "Drum temperature sensor error. Secondary thermistor fault detected."},
        {"code": "tE3", "display_text": "Condenser temperature sensor error. Heat exchanger thermistor fault (heat pump models)."},
        {"code": "EE",  "display_text": "EEPROM error. Internal memory of the control board is corrupted or unreadable."},
        {"code": "PF",  "display_text": "Power failure. A power interruption occurred during the wash cycle."},
        {"code": "PS",  "display_text": "Power surge error. Abnormal voltage was detected in the motor circuit."},
        {"code": "CL",  "display_text": "Child lock active. The control panel is locked to prevent accidental use."},
        {"code": "tCL", "display_text": "Tub clean cycle reminder. The drum requires a cleaning cycle."},
        {"code": "E6",  "display_text": "Clutch error (top-load). The clutch assembly is not engaging correctly."},
        {"code": "AE",  "display_text": "Communication error between the main PCB and the sub-board."},
    ],
    ("electrolux", "washing-machines"): [
        # Water inlet
        {"code": "E10", "display_text": "Water inlet error. The machine is not filling with water within the set time. Check the tap, inlet hose, and inlet filter."},
        {"code": "E11", "display_text": "Water fill too slow. Water is entering but taking too long. Check water pressure and inlet filter."},
        {"code": "E13", "display_text": "Water leak in base. Water detected in the base tray, triggering the overflow protection sensor."},
        # Drainage
        {"code": "E20", "display_text": "Drainage error. The machine cannot drain water within the set time. Check the drain filter, hose, and pump."},
        {"code": "E21", "display_text": "Drainage pump fault. The pump is not running correctly. Check for blockage or pump failure."},
        {"code": "E23", "display_text": "Drain pump electronic fault. The pump's electronic components have failed."},
        {"code": "E24", "display_text": "Drain pump triac faulty. Electronic control of the drain pump has failed."},
        {"code": "E25", "display_text": "Drain pump blocked. The pump impeller is obstructed. Check and clean the drain filter and pump."},
        # Pressure sensor
        {"code": "E30", "display_text": "Pressure sensor fault. The water level sensor is not reading correctly."},
        {"code": "E31", "display_text": "Pressure sensor calibration error. Sensor readings are out of expected calibration range."},
        {"code": "E35", "display_text": "Water overfill detected. The water level has exceeded the safe limit. Check the inlet valve and pressure sensor."},
        {"code": "E38", "display_text": "Pressure sensor air trap blocked. The tube connected to the pressure sensor is clogged."},
        # Door
        {"code": "E40", "display_text": "Door sensor error. The door is not closed or the door switch is faulty."},
        {"code": "E41", "display_text": "Door not closed. The door is open or not latched properly. Check the door seal and latch."},
        {"code": "E42", "display_text": "Door lock fault. The door lock mechanism has failed."},
        {"code": "E44", "display_text": "Door sensing error. The control board cannot confirm the door state."},
        {"code": "E45", "display_text": "Door lock relay/triac stuck. Electronic component controlling the door lock has failed."},
        # Motor
        {"code": "E50", "display_text": "Motor fault. General motor error — check for drum obstruction or motor failure."},
        {"code": "E51", "display_text": "Motor triac short circuit. Electronic fault in motor power control."},
        {"code": "E52", "display_text": "Motor speed signal not detected. Tachogenerator is not sending a speed signal."},
        {"code": "E54", "display_text": "Motor relay malfunction. The relay controlling the motor has failed."},
        {"code": "E57", "display_text": "Inverter overcurrent. Excessive current detected in the inverter drive motor circuit."},
        {"code": "E59", "display_text": "No motor tachometer signal. The motor speed sensor is not responding."},
        # Heating
        {"code": "E60", "display_text": "Heating element fault. The water is not heating to the target temperature."},
        {"code": "E61", "display_text": "Heating time too long. The water is heating but too slowly. Check the heating element and NTC sensor."},
        {"code": "E62", "display_text": "Overheating detected. The water temperature has exceeded the set limit. Check the NTC sensor and thermostat."},
        {"code": "E66", "display_text": "Heating element relay fault. The relay controlling the heater has failed."},
        {"code": "E68", "display_text": "Heating element leakage current to earth. Possible heating element breakdown."},
        # Temperature sensor
        {"code": "E71", "display_text": "NTC temperature sensor fault. The drum temperature sensor is giving incorrect readings or is open circuit."},
        # Control board / software
        {"code": "E91", "display_text": "Communication error. The main PCB cannot communicate with the display board or sub-module."},
        {"code": "E92", "display_text": "Control board fault. Internal error detected in the main control board."},
        {"code": "E93", "display_text": "Programme configuration error. The programme settings stored in memory are corrupt."},
        {"code": "E94", "display_text": "Cycle configuration error. The selected cycle cannot be run due to a configuration fault."},
        # Overflow / leak
        {"code": "EF0", "display_text": "Overflow or leak protection triggered. Water detected in the base pan. Check all hoses and connections for leaks."},
        {"code": "EF1", "display_text": "Water pressure in drain hose too high. Check that the drain hose is not blocked or kinked."},
    ],
}


# ── Seeding logic ──────────────────────────────────────────────────────────────

def seed(brand_slug: str, category_slug: str, dry_run: bool = False) -> int:
    # BSH brands: fetch live from the web instead of hardcoded seed data
    if brand_slug in _BSH_BRANDS:
        console.print(f"[cyan]Fetching BSH error codes from web for {brand_slug}…[/cyan]")
        codes = scrape_bsh_error_codes()
        if not codes:
            console.print("[red]No codes returned from web scrape.[/red]")
            return 0
    else:
        key = (brand_slug, category_slug)
        codes = SEED_DATA.get(key)
        if not codes:
            console.print(f"[yellow]No seed data for {brand_slug}/{category_slug}[/yellow]")
            return 0

    brand = supabase.table("brands").select("id,name").eq("slug", brand_slug).single().execute()
    category = supabase.table("categories").select("id").eq("slug_en", category_slug).single().execute()
    if not brand.data or not category.data:
        console.print(f"[red]Brand '{brand_slug}' or category '{category_slug}' not found[/red]")
        return 0

    brand_id    = brand.data["id"]
    category_id = category.data["id"]
    brand_name  = brand.data["name"]

    # Check what's already in DB
    existing = (
        supabase.table("error_codes")
        .select("code")
        .eq("brand_id", brand_id)
        .eq("category_id", category_id)
        .execute()
    ).data or []
    existing_codes = {r["code"] for r in existing}

    to_insert = [c for c in codes if c["code"] not in existing_codes]
    already   = [c for c in codes if c["code"] in existing_codes]

    # Print plan
    t = Table(title=f"Seed plan - {brand_name} / {category_slug}", box=box.SIMPLE)
    t.add_column("Code",   style="bold", width=8)
    t.add_column("Status", width=10)
    t.add_column("Display text", width=60)
    for c in codes:
        status = "[dim]exists[/dim]" if c["code"] in existing_codes else "[green]new[/green]"
        t.add_row(c["code"], status, (c.get("display_text") or "")[:60])
    console.print(t)
    console.print(f"\n{len(to_insert)} to insert, {len(already)} already exist.")

    if dry_run:
        console.print("[dim]Dry run — no DB writes.[/dim]")
        return 0

    if not to_insert:
        console.print("[dim]Nothing to insert.[/dim]")
        return 0

    rows = [
        {
            "brand_id":    brand_id,
            "category_id": category_id,
            "code":        c["code"],
            "display_text": c.get("display_text"),
            "scrape_status": "pending",
        }
        for c in to_insert
    ]
    supabase.table("error_codes").insert(rows).execute()
    console.print(f"[bold green]Inserted {len(rows)} error codes.[/bold green]")
    console.print("Run [bold]python -m pipeline.enrich_error_codes --brand lg --category washing-machines[/bold] next.")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed known error codes into DB")
    parser.add_argument("--brand",    default="lg")
    parser.add_argument("--category", default="washing-machines")
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()
    seed(args.brand, args.category, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
