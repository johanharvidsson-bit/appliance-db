"""Build reviewed Bosch noise, vibration, heating, drum and control articles."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    317: "NOISE",
    318: "NO_HEAT",
    319: "VIBRATION",
    323: "DRUM",
    324: "CONTROLS",
}

PROFILES = {
    "NOISE": {
        "en_title": "Bosch Washing Machine Making Loud Noise: Safe Checks",
        "sv_title": "Bosch tvättmaskin låter högt: säkra kontroller",
        "en_h1": "Why Is My Bosch Washing Machine Making Loud Noises?",
        "sv_h1": "Varför låter Bosch-tvättmaskinen högt?",
        "en_desc": "Bosch lists an unbalanced or overloaded load, incorrect levelling, transit bolts and accessible foreign objects among common causes of unusual washer noise.",
        "sv_desc": "Bosch anger obalanserad eller överfull last, fel nivellering, transportbultar och åtkomliga främmande föremål som vanliga orsaker till ovanliga ljud.",
        "en_action": "Pause safely, redistribute the load and check levelling and visible objects according to the exact manual",
        "sv_action": "Pausa säkert, fördela tvätten och kontrollera nivellering och synliga föremål enligt rätt manual",
        "en_causes": [("Unbalanced or overloaded laundry", "Heavy items can gather on one side and create banging during spin."), ("Washer not level or surface unstable", "All feet must stand firmly and lock nuts must be secured as the installation manual describes."), ("Transit bolts on a new installation", "Transport restraints left fitted can cause severe noise and damage."), ("Foreign object or internal fault", "Accessible objects may rattle; persistent grinding, scraping or knocking needs service.")],
        "sv_causes": [("Obalanserad eller överfull tvätt", "Tunga plagg kan samlas på ena sidan och orsaka slag under centrifugering."), ("Maskinen står inte plant", "Alla fötter ska stå stadigt och låsmuttrarna säkras enligt installationsmanualen."), ("Transportbultar på en ny installation", "Kvarlämnade transportsäkringar kan orsaka kraftigt ljud och skada."), ("Främmande föremål eller internt fel", "Åtkomliga föremål kan skramla; kvarstående malande, skrapande eller dunkande ljud kräver service.")],
    },
    "VIBRATION": {
        "en_title": "Bosch Washing Machine Vibrating Too Much: Safe Checks",
        "sv_title": "Bosch tvättmaskin vibrerar för mycket: säkra kontroller",
        "en_h1": "Why Is My Bosch Washing Machine Vibrating Excessively?",
        "sv_h1": "Varför vibrerar Bosch-tvättmaskinen för mycket?",
        "en_desc": "Bosch identifies load imbalance, overloading, incorrect levelling, an unsuitable floor and fitted transit bolts as common causes of excessive vibration.",
        "sv_desc": "Bosch anger lastobalans, överlast, fel nivellering, olämpligt golv och kvarvarande transportbultar som vanliga orsaker till kraftig vibration.",
        "en_action": "Stop the washer if it moves or strikes the cabinet, then redistribute the load and check installation against the exact manual",
        "sv_action": "Stoppa maskinen om den flyttar sig eller slår, fördela därefter lasten och kontrollera installationen mot rätt manual",
        "en_causes": [("Unbalanced load", "One heavy item or tangled laundry can create strong forces during spin."), ("Overloaded drum", "An overfull drum cannot distribute laundry effectively."), ("Incorrect levelling or unstable floor", "All feet need firm contact with a suitable stable surface."), ("Transit bolts or installation fault", "A new washer must have its transport restraints removed exactly as instructed.")],
        "sv_causes": [("Obalanserad last", "Ett tungt plagg eller hoptrasslad tvätt kan skapa stora krafter vid centrifugering."), ("Överfull trumma", "En överfull trumma kan inte fördela tvätten effektivt."), ("Fel nivellering eller instabilt golv", "Alla fötter måste stå stadigt på ett lämpligt stabilt underlag."), ("Transportbultar eller installationsfel", "En ny maskins transportsäkringar ska tas bort exakt enligt anvisningen.")],
    },
    "NO_HEAT": {
        "en_title": "Bosch Washing Machine Not Heating Water: Safe Checks",
        "sv_title": "Bosch tvättmaskin värmer inte vatten: säkra steg",
        "en_h1": "Why Is My Bosch Washing Machine Not Heating the Water?",
        "sv_h1": "Varför värmer inte Bosch-tvättmaskinen vattnet?",
        "en_desc": "A suspected heating problem cannot be confirmed by touching the door; persistent cold washing, a stopped programme or Bosch heating code needs model-specific diagnosis.",
        "sv_desc": "Ett misstänkt värmefel kan inte bekräftas genom att känna på luckan; kvarstående kall tvätt, avstannat program eller Bosch värmekod kräver modellspecifik diagnos.",
        "en_action": "Check the selected programme and displayed code, then stop and arrange Bosch service if the washer repeatedly fails to complete or shows a heating fault",
        "sv_action": "Kontrollera valt program och visad kod, stoppa sedan och boka Bosch-service om maskinen upprepade gånger inte slutför programmet eller visar värmefel",
        "en_causes": [("Programme temperature and energy-efficient operation", "Some programmes use lower temperatures and the door is not a reliable water-temperature test."), ("Documented heating code", "Bosch identifies E19/F19 as heating time exceeded and E20/F20 as unexpected heating."), ("Temperature sensing or heating control", "Persistent incorrect temperature requires internal diagnosis for the exact E-Nr."), ("Internal electrical fault", "Heaters, sensors, wiring and control electronics are not user-serviceable checks.")],
        "sv_causes": [("Programtemperatur och energieffektiv drift", "Vissa program använder lägre temperatur och luckan är inget tillförlitligt temperaturtest."), ("Dokumenterad värmekod", "Bosch anger E19/F19 för överskriden uppvärmningstid och E20/F20 för oväntad uppvärmning."), ("Temperaturmätning eller värmestyrning", "Kvarstående fel temperatur kräver intern diagnos för exakt E‑Nr."), ("Internt elfel", "Värmare, sensorer, kablage och styrelektronik ska inte kontrolleras av användaren.")],
    },
    "DRUM": {
        "en_title": "Bosch Washing Machine Drum Not Turning: What to Do",
        "sv_title": "Bosch tvättmaskinstrumma snurrar inte: säkra steg",
        "en_h1": "Why Is My Bosch Washing Machine Drum Not Turning?",
        "sv_h1": "Varför snurrar inte Bosch-tvättmaskinens trumma?",
        "en_desc": "Bosch says a new washer may still have its transport lock fitted; if an established washer's drum does not turn, Bosch directs the user to service.",
        "sv_desc": "Bosch anger att en ny maskin kan ha transportsäkringen kvar; om en tidigare använd maskins trumma inte snurrar hänvisar Bosch till service.",
        "en_action": "For a new installation, check transport-lock removal in the exact manual; otherwise switch off, unplug and contact Bosch service",
        "sv_action": "På en ny installation kontrollerar du transportsäkringen i rätt manual; annars stänger du av, drar ur kontakten och kontaktar Bosch-service",
        "en_causes": [("Transport lock on a new washer", "Bosch specifically identifies fitted transport restraints as a possible reason on a new appliance."), ("Programme or safety condition", "Record any display message and confirm the door and programme state in the exact manual."), ("Obstruction or mechanical resistance", "Do not force the drum or remove panels to search internally."), ("Drive or electrical fault", "Bosch recommends service when an established washer's drum no longer turns.")],
        "sv_causes": [("Transportsäkring på en ny maskin", "Bosch anger särskilt kvarvarande transportsäkringar som möjlig orsak på en ny maskin."), ("Program- eller säkerhetstillstånd", "Dokumentera displayen och kontrollera luck- och programstatus i rätt manual."), ("Hinder eller mekaniskt motstånd", "Tvinga inte trumman och ta inte bort paneler för intern kontroll."), ("Driv- eller elfel", "Bosch rekommenderar service när en tidigare använd maskins trumma inte längre snurrar.")],
    },
    "CONTROLS": {
        "en_title": "Bosch Washer Control Panel Unresponsive: Safe Checks",
        "sv_title": "Bosch kontrollpanel svarar inte: säkra kontroller",
        "en_h1": "Why Is My Bosch Washing Machine Control Panel Unresponsive?",
        "sv_h1": "Varför svarar inte Bosch-tvättmaskinens kontrollpanel?",
        "en_desc": "Bosch documents energy-saving mode and child lock as normal reasons a display or buttons may appear inactive; a persistent unresponsive panel needs service.",
        "sv_desc": "Bosch dokumenterar energisparläge och barnlås som normala orsaker till att display eller knappar verkar inaktiva; ett kvarstående fel kräver service.",
        "en_action": "Check power, wake energy-saving mode and deactivate child lock only by the exact model-manual method; otherwise switch off and contact Bosch",
        "sv_action": "Kontrollera strömmen, väck energisparläget och avaktivera barnlåset endast enligt rätt modellmanual; stäng annars av och kontakta Bosch",
        "en_causes": [("Energy-saving mode", "Bosch states the display may switch off and can be activated by pressing a button."), ("Child lock", "A key symbol can mean the controls are intentionally disabled; release methods differ by model."), ("Power or programme state", "Confirm the plug, household protection and door/programme state without opening the appliance."), ("Persistent control fault", "An unresponsive display after documented checks needs professional diagnosis.")],
        "sv_causes": [("Energisparläge", "Bosch anger att displayen kan slockna och aktiveras med en knapp."), ("Barnlås", "En nyckelsymbol kan betyda att reglagen avsiktligt är spärrade; upplåsning skiljer sig mellan modeller."), ("Ström- eller programstatus", "Kontrollera stickpropp, elskydd och luck-/programstatus utan att öppna maskinen."), ("Kvarstående styrfel", "En panel som inte svarar efter dokumenterade kontroller kräver professionell diagnos.")],
    },
}


def make(kind: str, sv: bool) -> dict:
    p = PROFILES[kind]
    label = p["sv_h1"] if sv else p["en_h1"]
    meaning = p["sv_desc"] if sv else p["en_desc"]
    action = p["sv_action"] if sv else p["en_action"]
    v = build_sv(label, meaning, action) if sv else build_en(label, meaning, action)
    v["title_tag"] = p["sv_title"] if sv else p["en_title"]
    v["meta_description"] = (("Säkra Bosch-kontroller, verifierade orsaker och tydliga gränser för när tvättmaskinen ska stoppas och lämnas till service." if sv else "Safe Bosch checks, verified causes and clear guidance on when to stop the washing machine and arrange professional service."))
    v["h1"] = p["sv_h1"] if sv else p["en_h1"]
    v["description"] = meaning
    v["quick_fix"] = action + (" (cirka 5–15 minuter)." if sv else " (about 5–15 minutes).")
    v["intro_html"] = (f"<p>{meaning}</p><p>{action}. Följ alltid manualen för exakt E‑Nr och ta inte bort paneler eller testa interna delar.</p>" if sv else f"<p>{meaning}</p><p>{action}. Always follow the manual for the exact E-Nr and do not remove panels or test internal parts.</p>")
    v["causes_json"] = [{"cause": a, "detail": b} for a, b in p["sv_causes" if sv else "en_causes"]]
    v["steps_json"] = ([
        {"step": 1, "action": "Stoppa och observera", "detail": "Pausa säkert, vänta tills trumman står stilla och dokumentera ljud, rörelse, display och programfas."},
        {"step": 2, "action": "Kontrollera E‑Nr och manual", "detail": "Använd bara anvisningar för exakt modell och marknad."},
        {"step": 3, "action": "Gör den säkra yttre kontrollen", "detail": action + "."},
        {"step": 4, "action": "Kontrollera varningssignaler", "detail": "Avbryt vid bränd lukt, rök, läckage, kraftiga slag, skrapande ljud eller utlöst säkring."},
        {"step": 5, "action": "Testa högst en gång", "detail": "Gör bara ett kort test om manualen medger det och maskinen är stabil, torr och utan varningssignaler."},
        {"step": 6, "action": "Boka Bosch-service", "detail": "Boka service om problemet kvarstår eller om Bosch hänvisar symptomet till tekniker. Uppge E‑Nr och observationerna."},
    ] if sv else [
        {"step": 1, "action": "Stop and observe", "detail": "Pause safely, wait for the drum to stop and record the noise, movement, display and programme stage."},
        {"step": 2, "action": "Check the E-Nr and manual", "detail": "Use instructions only for the exact model and market."},
        {"step": 3, "action": "Perform the safe external check", "detail": action + "."},
        {"step": 4, "action": "Check for warning signs", "detail": "Stop for a burning smell, smoke, leakage, heavy impacts, scraping noise or a tripped supply."},
        {"step": 5, "action": "Test at most once", "detail": "Make one short test only if the manual permits it and the washer is stable, dry and has no warning signs."},
        {"step": 6, "action": "Arrange Bosch service", "detail": "Request service if the problem remains or Bosch directs the symptom to a technician. Provide the E-Nr and observations."},
    ])
    v["when_to_call_technician_html"] = ("<p>Boka service om problemet kvarstår efter säkra, dokumenterade yttre kontroller. Avbryt omedelbart vid bränd lukt, rök, läckage, elfel, kraftiga slag eller skrapande ljud.</p><p>Ta inte bort paneler och kontrollera inte motor, värmare, lager, upphängning, kablage eller styrkort själv.</p>" if sv else "<p>Arrange service if the problem remains after safe documented external checks. Stop immediately for burning smell, smoke, leakage, electrical faults, heavy impacts or scraping noise.</p><p>Do not remove panels or inspect the motor, heater, bearings, suspension, wiring or control board yourself.</p>")
    v["prevention_html"] = ("<p>Följ lastgränser och installationsanvisningar, fördela stora och små plagg och håll maskinen stabil och korrekt nivellerad.</p><p>Använd rätt program och utför bara det användarunderhåll som anges i modellmanualen.</p>" if sv else "<p>Follow load limits and installation instructions, mix large and small items and keep the washer stable and correctly levelled.</p><p>Use the correct programme and perform only user maintenance described in the model manual.</p>")
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-009-bosch-noise-controls-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "009-bosch-noise-controls", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.bosch-home.com/us/owner-support/washers",
        "https://www.bosch-home.com/ae/en/customer-service/get-support/washing-machine-makes-noise",
        "https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-machine-drum-doesnt-turn",
        "https://www.bosch-home.com/us/owner-support/error-codes/washers",
        "https://www.bosch-home.com/gh/en/service/get-support/key-symbol-appears-in-display",
    ], "translations": {}}
    for i, kind in ITEMS.items():
        out["translations"][str(i)] = {"code": kind, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": make(kind, False), "sv": make(kind, True)}
    p = BASE_DIR / "data/article_reviews/batch-009-bosch-noise-controls-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
