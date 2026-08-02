"""Build reviewed Siemens NO and common-fault content for batch 037."""
from __future__ import annotations

import json

from config.settings import BASE_DIR


ITEMS = {
    244: {
        "type": "code",
        "subject": "NO",
        "en_title": "What Does NO Mean on a Siemens Washing Machine?",
        "sv_title": "Vad betyder NO på en Siemens-tvättmaskin?",
        "en_meaning": "NO is not defined as a universal washer error in Siemens' public code table, so the complete display and exact E-Nr are required",
        "sv_meaning": "NO definieras inte som ett universellt tvättmaskinsfel i Siemens offentliga kodtabell, så hela displayen och exakt E‑Nr behövs",
        "en_action": "Photograph every displayed character, confirm whether it is text or a symbol and check the manual for the exact E-Nr",
        "sv_action": "Fotografera varje visat tecken, bekräfta om det är text eller en symbol och kontrollera manualen för exakt E‑Nr",
        "en_causes": ["Incomplete or misread display", "Model-specific status message", "A symbol mistaken for letters", "Internal condition requiring Siemens diagnosis"],
        "sv_causes": ["Ofullständig eller feltolkad display", "Modellspecifikt statusmeddelande", "En symbol som misstolkas som bokstäver", "Internt tillstånd som kräver Siemens-diagnos"],
    },
    330: {
        "type": "fault", "subject": "drain",
        "en_title": "Siemens Washing Machine Won't Drain",
        "sv_title": "Siemens-tvättmaskinen tömmer inte",
        "en_meaning": "A kinked drain hose, blocked user-accessible pump filter or restricted household drain can stop the washer emptying",
        "sv_meaning": "En vikt avloppsslang, blockerat användaråtkomligt pumpfilter eller hindrat avlopp kan stoppa tömningen",
        "en_action": "Close the tap, switch off and unplug, let hot water cool, then inspect the visible hose and drain or clean the accessible filter exactly as the E-Nr manual specifies",
        "sv_action": "Stäng kranen, stäng av och dra ur kontakten, låt hett vatten svalna och kontrollera sedan synlig slang samt töm eller rengör åtkomligt filter exakt enligt E‑Nr-manualen",
        "en_causes": ["Kinked or blocked drain hose", "Blocked user-accessible pump filter", "Restricted household drain connection", "Internal pump or control fault"],
        "sv_causes": ["Vikt eller blockerad avloppsslang", "Blockerat användaråtkomligt pumpfilter", "Hinder i bostadens avloppsanslutning", "Internt pump- eller styrfel"],
    },
    331: {
        "type": "fault", "subject": "spin",
        "en_title": "Siemens Washing Machine Won't Spin",
        "sv_title": "Siemens-tvättmaskinen centrifugerar inte",
        "en_meaning": "Siemens identifies drainage restrictions, a blocked filter and an unbalanced or overloaded drum as common reasons for reduced or absent spinning",
        "sv_meaning": "Siemens anger tömningshinder, blockerat filter och obalanserad eller överlastad trumma som vanliga orsaker till minskad eller utebliven centrifugering",
        "en_action": "Confirm that the programme includes spinning, redistribute the load and check that the washer can drain",
        "sv_action": "Bekräfta att programmet omfattar centrifugering, fördela om lasten och kontrollera att maskinen kan tömma",
        "en_causes": ["Programme without a spin phase", "Unbalanced or overloaded drum", "Drainage restriction or blocked filter", "Internal drive or control fault"],
        "sv_causes": ["Program utan centrifugeringsfas", "Obalanserad eller överlastad trumma", "Tömningshinder eller blockerat filter", "Internt driv- eller styrfel"],
    },
    334: {
        "type": "fault", "subject": "fill",
        "en_title": "Siemens Washing Machine Won't Fill With Water",
        "sv_title": "Siemens-tvättmaskinen fyller inte med vatten",
        "en_meaning": "Siemens recommends checking the water supply, pressure, door closure and external inlet hose when no water enters",
        "sv_meaning": "Siemens rekommenderar kontroll av vattenförsörjning, tryck, luckstängning och yttre tilloppsslang när inget vatten kommer in",
        "en_action": "Open the tap, check for an outage and adequate pressure, close the door firmly and straighten the visible inlet hose",
        "sv_action": "Öppna kranen, kontrollera vattenavbrott och tillräckligt tryck, stäng luckan ordentligt och räta den synliga tilloppsslangen",
        "en_causes": ["Closed tap or water outage", "Low household water pressure", "Kinked inlet hose or accessible filter restriction", "Door-lock, inlet-valve or control fault"],
        "sv_causes": ["Stängd kran eller vattenavbrott", "Lågt vattentryck i bostaden", "Vikt tilloppsslang eller hinder i åtkomligt filter", "Fel i lucklås, inloppsventil eller styrning"],
    },
    336: {
        "type": "fault", "subject": "noise",
        "en_title": "Siemens Washing Machine Making Loud Noise",
        "sv_title": "Siemens-tvättmaskinen låter högt",
        "en_meaning": "Unusual noise can come from transport bolts or packing, poor levelling, an unbalanced load or an internal mechanical fault",
        "sv_meaning": "Ovanligt ljud kan bero på transportbultar eller emballage, felaktig nivellering, obalanserad last eller internt mekaniskt fel",
        "en_action": "Stop the washer, check the load and visible installation, and compare the sound with the exact E-Nr manual without opening any panel",
        "sv_action": "Stoppa maskinen, kontrollera lasten och den synliga installationen och jämför ljudet med manualen för exakt E‑Nr",
        "en_causes": ["Transport bolts or packing remain", "Washer is not level on a stable floor", "Unbalanced load or loose pocket item", "Internal bearing, drive or suspension fault"],
        "sv_causes": ["Transportbultar eller emballage finns kvar", "Maskinen står inte i nivå på stabilt golv", "Obalanserad last eller löst föremål ur en ficka", "Internt lager-, driv- eller upphängningsfel"],
    },
}


def make(item: dict[str, object], sv: bool) -> dict[str, object]:
    title = str(item["sv_title" if sv else "en_title"])
    meaning = str(item["sv_meaning" if sv else "en_meaning"])
    action = str(item["sv_action" if sv else "en_action"])
    causes = item["sv_causes" if sv else "en_causes"]
    code = item["type"] == "code"
    if sv:
        title_tag = "Siemens felkod NO: betydelse och säkra steg" if code else f"{title}: säkra kontroller"
        meta = ("Siemens-tvättmaskin visar NO? Se vad Siemens offentliga kodtabell faktiskt stöder, säkra kontroller och när service krävs."
                if code else f"{title}? Se Siemens verifierade orsaker, säkra yttre kontroller och när auktoriserad service krävs.")
        return {
            "title_tag": title_tag, "meta_description": meta, "h1": title,
            "description": meaning + ".", "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning}.</p><p>{action}. Demontera inget och gör inga elektriska mätningar.</p>",
            "causes_json": [{"cause": cause, "detail": "Detta är en möjlig orsak; använd endast yttre kontroller i manualen för exakt E‑Nr."} for cause in causes],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Dokumentera symptom och E‑Nr", "detail": "Fotografera hela displayen, anteckna programfasen och maskinens exakta E‑Nr."},
                {"step": 3, "action": "Gör säkra yttre kontroller", "detail": action + ". Följ varningarna i E‑Nr-manualen."},
                {"step": 4, "action": "Testa högst en gång", "detail": "Testa endast efter korrigerad yttre orsak och aldrig vid läckage, bränd lukt, rök, onormal värme, elfel eller kraftigt skrapljud."},
                {"step": 5, "action": "Boka Siemens-service", "detail": "Boka service om problemet kvarstår eller återkommer; öppna inga paneler och prova inga interna delar."},
            ],
            "when_to_call_technician_html": "<p>Boka Siemens-service om problemet kvarstår efter dokumenterade yttre kontroller eller om pump, ventil, lucklås, drivning, lager, kablage eller elektronik misstänks.</p><p>Avbryt direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme, utlöst elskydd eller kraftigt malande/skrapande ljud.</p>",
            "prevention_html": "<p>Följ installations- och lastanvisningar, töm fickor, dosera rätt och håll synliga slangar och användaråtkomliga filter rena enligt manualen.</p><p>Håll maskinen i nivå; interna komponentfel kan inte förebyggas genom demontering.</p>",
            "faq_json": [
                {"question": "Kan jag fortsätta använda maskinen?", "answer": "Endast om den återgår till helt normal drift efter en säker yttre korrigering och inga varningssymptom finns."},
                {"question": "Ska jag öppna en panel?", "answer": "Nej. Begränsa kontrollen till delar som manualen uttryckligen anger som användaråtkomliga."},
                {"question": "Behöver jag beställa en reservdel?", "answer": "Inte från symptomet ensamt. Interna fel kräver diagnos för exakt E‑Nr."},
                {"question": "När behövs Siemens-service?", "answer": "När felet kvarstår eller återkommer, eller om ett internt, elektriskt, läckage- eller mekaniskt fel misstänks."},
            ], "parts_json": [],
        }
    title_tag = "Siemens Error NO: Meaning and Safe Steps" if code else f"{title}: Safe Checks"
    meta = ("Siemens washer showing NO? See what the public Siemens code table supports, safe checks and when service is required."
            if code else f"{title}? See verified Siemens causes, safe external checks and when authorised service is required.")
    return {
        "title_tag": title_tag, "meta_description": meta, "h1": title,
        "description": meaning + ".", "quick_fix": action + " (about 5–30 minutes).",
        "intro_html": f"<p>{meaning}.</p><p>{action}. Dismantle nothing and make no electrical measurements.</p>",
        "causes_json": [{"cause": cause, "detail": "This is a possible cause; use only external checks in the exact E-Nr manual."} for cause in causes],
        "steps_json": [
            {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
            {"step": 2, "action": "Record symptoms and E-Nr", "detail": "Photograph the complete display and note the programme stage and exact appliance E-Nr."},
            {"step": 3, "action": "Make safe external checks", "detail": action + ". Follow every warning in the E-Nr manual."},
            {"step": 4, "action": "Test no more than once", "detail": "Test only after correcting an external cause, and never with leakage, burning smell, smoke, abnormal heat, an electrical fault or severe scraping."},
            {"step": 5, "action": "Arrange Siemens service", "detail": "Request service if the issue remains or returns; open no panels and test no internal parts."},
        ],
        "when_to_call_technician_html": "<p>Arrange Siemens service if the issue remains after documented external checks or if the pump, valve, door lock, drive, bearing, wiring or electronics are suspected.</p><p>Stop immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat, tripped protection or severe grinding or scraping.</p>",
        "prevention_html": "<p>Follow installation and load guidance, empty pockets, dose correctly and keep visible hoses and user-accessible filters clean as the manual specifies.</p><p>Keep the washer level; internal component faults cannot be prevented through dismantling.</p>",
        "faq_json": [
            {"question": "Can I keep using the washer?", "answer": "Only if it returns to completely normal operation after a safe external correction and no warning symptom is present."},
            {"question": "Should I open an appliance panel?", "answer": "No. Limit checks to parts the manual explicitly identifies as user-accessible."},
            {"question": "Should I order a replacement part?", "answer": "Not from the symptom alone. Internal faults require diagnosis for the exact E-Nr."},
            {"question": "When is Siemens service required?", "answer": "When the issue remains or returns, or when an internal, electrical, leakage or mechanical fault is suspected."},
        ], "parts_json": [],
    }


def main() -> None:
    backup_path = BASE_DIR / "data/backups/article_reviews/batch-037-siemens-no-common-faults-before.json"
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {
        "batch": "037-siemens-no-common-faults",
        "status": "proposal_only_not_applied",
        "article_ids": list(ITEMS),
        "sources": [
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/error-codes-symbols",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/not-draining",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/not-spinning",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/no-water",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/noise-new-appliances",
        ],
        "translations": {},
    }
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {
            "code": item["subject"],
            "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]},
            "en": make(item, False), "sv": make(item, True),
        }
    path = BASE_DIR / "data/article_reviews/batch-037-siemens-no-common-faults-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
