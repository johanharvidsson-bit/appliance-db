"""Build reviewed Bosch E92/END/F16/F17/F21 content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {198: "E92", 199: "END", 200: "F16", 201: "F17", 203: "F21"}

EN = {
    "E92": ("the complete Bosch code E:92/-01 means low water pressure or blocked water-inlet filters", "Record the complete code, check that the tap is fully open and inspect only the inlet hose and user-cleanable inlet filters described in the model manual"),
    "END": ("END normally indicates that the washing programme has finished; it is not an error code", "Wait for the door to unlock, remove the laundry and switch the appliance off as described in the manual"),
    "F16": ("Bosch identifies F16 as the door being open or not locked properly", "Remove laundry trapped between the door and housing, reduce an overfull load and close the door until it clicks"),
    "F17": ("Bosch identifies F17 as the permitted water-supply time being exceeded", "Make sure the water tap is fully open and the supply hose is not kinked; follow the exact manual for cleaning user-accessible inlet filters"),
    "F21": ("an official Bosch washer manual identifies F21 as a motor fault", "Stop using the washer, switch it off and unplug it; Bosch instructs the user to contact after-sales service"),
}

SV = {
    "E92": ("den fullständiga Bosch-koden E:92/-01 betyder lågt vattentryck eller blockerade filter i vatteninloppet", "Dokumentera hela koden, kontrollera att kranen är helt öppen och kontrollera endast inloppsslang och användarrengörbara inloppsfilter enligt modellmanualen"),
    "END": ("END betyder normalt att tvättprogrammet är klart och är inte en felkod", "Vänta tills luckan låses upp, ta ut tvätten och stäng av maskinen enligt manualen"),
    "F16": ("Bosch anger att F16 betyder att luckan är öppen eller inte korrekt låst", "Ta bort tvätt som fastnat mellan luckan och höljet, minska en överfull last och stäng luckan tills den klickar"),
    "F17": ("Bosch anger att F17 betyder att den tillåtna tiden för vattenintag har överskridits", "Kontrollera att vattenkranen är helt öppen och att tilloppsslangen inte är vikt; följ rätt manual för rengöring av användaråtkomliga inloppsfilter"),
    "F21": ("en officiell Bosch-manual anger att F21 är ett motorfel", "Sluta använda maskinen, stäng av och dra ur kontakten; Bosch hänvisar användaren till service"),
}


def article(code: str, sv: bool = False) -> dict:
    meaning, action = (SV if sv else EN)[code]
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v["title_tag"] = f"Bosch tvättmaskin {code}: betydelse och säkra steg"
        v["meta_description"] = f"Visar Bosch-tvättmaskinen {code}? Läs Boschs verifierade betydelse, säkra kontroller och när du ska avbryta och kontakta service."
        v["h1"] = f"Vad betyder {code} på en Bosch-tvättmaskin?"
        v["description"] = meaning.capitalize() + "."
        v["quick_fix"] = action + " (cirka 5–15 minuter)."
        v["intro_html"] = f"<p>{meaning.capitalize()}. Rådet bygger på Boschs egen support eller modellmanual.</p><p>{action}. Ta inte bort paneler, förbikoppla säkerhetssystem eller beställ en reservdel från koden ensam.</p>"
    else:
        v["title_tag"] = f"Bosch Washing Machine {code}: Meaning and Safe Steps"
        v["meta_description"] = f"Bosch washer showing {code}? Check Bosch's verified meaning, safe user checks and when to stop and contact service."
        v["h1"] = f"What Does {code} Mean on a Bosch Washing Machine?"
        v["description"] = meaning[0].upper() + meaning[1:] + "."
        v["quick_fix"] = action + " (about 5–15 minutes)."
        v["intro_html"] = f"<p>{meaning[0].upper() + meaning[1:]}. This guidance is based on Bosch support or an official model manual.</p><p>{action}. Do not remove panels, bypass safety devices or order a part from the code alone.</p>"

    normal = code == "END"
    service_only = code == "F21"
    if sv:
        v["causes_json"] = ([
            {"cause": "Normalt programslut", "detail": "END visas när det valda programmet har slutförts."},
            {"cause": "Luckan låses upp med fördröjning", "detail": "Luckan kan förbli låst tills trumman står stilla och temperatur och vattennivå är säkra."},
            {"cause": "Energisparläge", "detail": "Displayen kan slockna efter programslut och aktiveras igen med en knapp enligt manualen."},
            {"cause": "Separat symptom", "detail": "Om tvätten är våt, vatten står kvar eller luckan inte öppnas ska det symptomet felsökas enligt exakt modellmanual."},
        ] if normal else [
            {"cause": "Boschs verifierade kodbetydelse", "detail": meaning.capitalize() + "."},
            {"cause": "Modellens exakta utförande", "detail": "Tillåtna kontroller och komponenternas placering kan skilja sig. E‑Nr identifierar rätt manual."},
            {"cause": "Ett kvarstående tillstånd", "detail": "Om koden återkommer efter dokumenterade användarkontroller krävs vidare diagnos, inte upprepade återställningar."},
            {"cause": "Internt fel som kräver service", "detail": "Koden ensam bekräftar inte vilken del som ska bytas. Intern el-, lås-, ventil- eller motorservice ska utföras av tekniker."},
        ])
        v["steps_json"] = [
            {"step": 1, "action": "Dokumentera hela displayen", "detail": f"Fotografera {code}, inklusive skiljetecken och eventuellt suffix, och notera E‑Nr från typskylten."},
            {"step": 2, "action": "Stoppa säkert", "detail": "Vänta tills trumman står stilla. Tvinga inte upp en låst lucka och hantera inte vatten som fortfarande är varmt."},
            {"step": 3, "action": "Följ Bosch-rådet", "detail": action + "."},
            {"step": 4, "action": "Använd rätt modellmanual", "detail": "Följ endast de yttre kontroller och det underhåll som Bosch anger för exakt E‑Nr."},
            {"step": 5, "action": "Gör högst en dokumenterad omstart", "detail": "Starta om endast om manualen medger det. Återställ inte upprepade gånger ett kvarstående fel."},
            {"step": 6, "action": "Boka service vid behov", "detail": "Kontakta Bosch om koden kvarstår, om manualen hänvisar till service eller om maskinen inte kan användas säkert."},
        ]
        v["when_to_call_technician_html"] = ("<p>END kräver normalt ingen service. Boka service om luckan förblir låst, vatten står kvar, programmet inte har slutförts eller ett annat fel visas efter att modellmanualens användarsteg följts.</p>" if normal else "<p>Boka Bosch-service om koden återkommer efter de uttryckligen tillåtna användarkontrollerna. F21 är ett motorfel som Bosch hänvisar till service.</p>") + "<p>Avbryt direkt vid bränd lukt, rök, läckage, onormal värme eller utlöst säkring. Ta inte bort paneler eller testa interna delar.</p>"
        v["prevention_html"] = "<p>Följ installations-, last- och underhållsanvisningarna för exakt E‑Nr. Håll lucköppningen fri, undvik vikt slang och rengör bara användaråtkomliga filter enligt manualen.</p><p>Dokumentera en återkommande kod och boka diagnos i stället för att återställa maskinen upprepade gånger.</p>"
    else:
        v["causes_json"] = ([
            {"cause": "Normal programme completion", "detail": "END is shown when the selected programme has completed."},
            {"cause": "Delayed door release", "detail": "The door may stay locked until the drum has stopped and temperature and water level are safe."},
            {"cause": "Energy-saving mode", "detail": "The display may turn off after programme end and can be reactivated as described in the manual."},
            {"cause": "A separate symptom", "detail": "If laundry is wet, water remains or the door will not open, troubleshoot that symptom using the exact model manual."},
        ] if normal else [
            {"cause": "Bosch's verified code meaning", "detail": meaning[0].upper() + meaning[1:] + "."},
            {"cause": "The exact model design", "detail": "Permitted checks and component locations differ. The E-Nr identifies the correct manual."},
            {"cause": "A persistent condition", "detail": "If the code returns after documented user checks, it needs diagnosis rather than repeated resets."},
            {"cause": "An internal condition requiring service", "detail": "The code alone does not confirm a replacement part. Internal electrical, lock, valve or motor work belongs with a technician."},
        ])
        v["steps_json"] = [
            {"step": 1, "action": "Record the complete display", "detail": f"Photograph {code}, including punctuation and any suffix, and note the E-Nr from the rating plate."},
            {"step": 2, "action": "Stop safely", "detail": "Wait for the drum to stop. Do not force a locked door or handle water that may still be hot."},
            {"step": 3, "action": "Follow Bosch's instruction", "detail": action + "."},
            {"step": 4, "action": "Use the exact model manual", "detail": "Perform only the external checks and maintenance Bosch specifies for the exact E-Nr."},
            {"step": 5, "action": "Make at most one documented restart", "detail": "Restart only if the manual permits it. Do not repeatedly reset a persistent fault."},
            {"step": 6, "action": "Arrange service when required", "detail": "Contact Bosch if the code remains, the manual directs you to service or the washer cannot be used safely."},
        ]
        v["when_to_call_technician_html"] = ("<p>END normally needs no service. Arrange service if the door stays locked, water remains, the programme has not completed or another fault appears after following the model manual.</p>" if normal else "<p>Arrange Bosch service if the code returns after the explicitly permitted user checks. F21 is a motor fault that Bosch directs to after-sales service.</p>") + "<p>Stop immediately for a burning smell, smoke, leakage, abnormal heat or a tripped supply. Do not remove panels or test internal parts.</p>"
        v["prevention_html"] = "<p>Follow the installation, load and maintenance instructions for the exact E-Nr. Keep the door opening clear, prevent hose kinks and clean only user-accessible filters described in the manual.</p><p>Record a recurring code and request diagnosis instead of repeatedly resetting the washer.</p>"

    v["parts_json"] = []
    if service_only:
        v["quick_fix"] = ("Stäng av, dra ur kontakten och boka Bosch-service; försök inte reparera motorn själv (cirka 5 minuter)." if sv else "Switch off, unplug and arrange Bosch service; do not attempt a motor repair yourself (about 5 minutes).")
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    assert 4 <= len(v["causes_json"]) <= 6 and 5 <= len(v["steps_json"]) <= 7
    assert 4 <= len(v["faq_json"]) <= 5 and v["parts_json"] == []
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-007-bosch-e92-end-f21-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {
        "batch": "007-bosch-e92-end-f21",
        "status": "proposal_only_not_applied",
        "article_ids": list(ITEMS),
        "sources": [
            "https://www.bosch-home.com/us/owner-support/error-codes/washers",
            "https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e16-or-f16-washing-machine",
            "https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e17-or-f17-washing-machine",
            "https://media3.bosch-home.com/Documents/9001027431_B.pdf",
            "https://media3.bosch-home.com/Documents/9000963105_D.pdf",
        ],
        "translations": {},
    }
    for article_id, code in ITEMS.items():
        out["translations"][str(article_id)] = {
            "code": code,
            "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]},
            "en": article(code),
            "sv": article(code, True),
        }
    path = BASE_DIR / "data/article_reviews/batch-007-bosch-e92-end-f21-proposal.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
