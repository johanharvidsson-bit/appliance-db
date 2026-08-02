"""Build reviewed Siemens electrical-trip and burning-smell content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline import build_p0_batch_037_deterministic as base


ITEMS = {
    347: {
        "type": "fault", "subject": "electrical trip",
        "en_title": "Siemens Washing Machine Trips the Electrics",
        "sv_title": "Siemens-tvättmaskinen löser ut elskyddet",
        "en_meaning": "Siemens lists the motor, heater, suppressor, shorted wiring or water on an electrical part as possible causes, all of which require qualified diagnosis if the washer trips protection",
        "sv_meaning": "Siemens listar motor, värmare, störningsskydd, kortslutet kablage eller vatten på en elektrisk del som möjliga orsaker, vilka kräver kvalificerad diagnos när maskinen löser ut elskydd",
        "en_action": "Stop using the washer, isolate it only from a dry safe position and arrange Siemens service; ask an electrician to assess the fixed installation when appropriate",
        "sv_action": "Sluta använda maskinen, frånkoppla den endast från en torr säker plats och boka Siemens-service; låt elektriker bedöma den fasta installationen vid behov",
        "en_causes": ["Internal motor or heater fault", "Suppressor or control-electronics fault", "Damaged internal wiring or short circuit", "Water reaching an electrical component or a fixed-installation fault"],
        "sv_causes": ["Internt motor- eller värmarfel", "Fel i störningsskydd eller styrelektronik", "Skadat internt kablage eller kortslutning", "Vatten på elektrisk komponent eller fel i fast installation"],
    },
    348: {
        "type": "fault", "subject": "burning smell",
        "en_title": "Siemens Washing Machine Has a Burning Smell",
        "sv_title": "Siemens-tvättmaskinen luktar bränt",
        "en_meaning": "A burning smell, smoke, sparks or abnormal heat can indicate an electrical or mechanical overheating hazard and is not suitable for user testing",
        "sv_meaning": "Bränd lukt, rök, gnistor eller onormal värme kan tyda på elektrisk eller mekanisk överhettningsrisk och lämpar sig inte för användartest",
        "en_action": "Stop the programme, keep clear of smoke and isolate power only if this can be done safely; do not restart the washer and arrange qualified service",
        "sv_action": "Stoppa programmet, håll avstånd från rök och bryt strömmen endast om det kan göras säkert; starta inte om maskinen och boka kvalificerad service",
        "en_causes": ["Overheated motor or drive component", "Electrical connection, wiring or control fault", "Friction from an internal mechanical fault", "Foreign material or another heat source requiring inspection"],
        "sv_causes": ["Överhettad motor- eller drivkomponent", "Fel i elanslutning, kablage eller styrning", "Friktion från internt mekaniskt fel", "Främmande material eller annan värmekälla som kräver inspektion"],
    },
}


def make(item: dict[str, object], sv: bool) -> dict[str, object]:
    value = base.make(item, sv)
    burning = item["subject"] == "burning smell"
    if sv:
        value.update({
            "quick_fix": ("Stoppa programmet och bryt strömmen endast från en torr säker plats. Starta inte om maskinen; boka kvalificerad service."
                          if burning else "Sluta använda maskinen och frånkoppla den endast från en torr säker plats. Återställ inte för upprepade test; boka Siemens-service."),
            "intro_html": f"<p>{item['sv_meaning']}.</p><p>{item['sv_action']}. Öppna inga paneler, gör inga mätningar och utför inget provprogram.</p>",
            "steps_json": [
                {"step": 1, "action": "Avbryt omedelbart", "detail": "Stoppa användningen. Vid rök eller brandrisk: håll avstånd, utrym vid behov och ring 112 vid akut fara."},
                {"step": 2, "action": "Frånkoppla endast säkert", "detail": "Bryt strömmen från en torr säker plats. Rör inte våt eller skadad utrustning och utsätt dig inte för rök."},
                {"step": 3, "action": "Starta inte om", "detail": "Återställ inte elskyddet för att prova maskinen igen och kör inget testprogram."},
                {"step": 4, "action": "Dokumentera utan beröring", "detail": "Anteckna E‑Nr, programfas, visad kod, var lukten eller ljudet uppstod och vilket elskydd som löste ut."},
                {"step": 5, "action": "Boka rätt fackhjälp", "detail": "Kontakta Siemens-service för maskinen och behörig elektriker om uttag, kabel, elskydd eller fast installation kan vara berörd."},
            ],
            "when_to_call_technician_html": "<p>Den här situationen kräver kvalificerad bedömning innan maskinen används igen. Kontakta Siemens-service; kontakta även behörig elektriker om den fasta installationen eller elskyddet kan vara orsaken.</p><p>Vid aktiv rök, brand, gnistor eller akut fara: håll avstånd, utrym och ring 112.</p>",
            "prevention_html": "<p>Använd jordat uttag och den anslutning som installationsmanualen kräver. Undvik förlängningssladdar, håll nätkabeln oskadad och åtgärda läckage innan användning.</p><p>Interna el- och mekanikfel kan inte förebyggas genom egen demontering eller provning.</p>",
            "faq_json": [
                {"question": "Kan jag starta om maskinen för att kontrollera?", "answer": "Nej. Upprepad utlösning eller bränd lukt ska bedömas innan maskinen används igen."},
                {"question": "Ska jag återställa jordfelsbrytaren?", "answer": "Inte för att prova maskinen igen. Isolera maskinen säkert och låt rätt fackperson bedöma både maskin och installation."},
                {"question": "Kan jag öppna en panel för att hitta felet?", "answer": "Nej. El, värme och möjliga läckage gör intern kontroll olämplig för användaren."},
                {"question": "Vem ska jag kontakta?", "answer": "Siemens-service för maskinen och behörig elektriker om uttag, kabel, elskydd eller fast installation kan vara inblandad."},
            ],
        })
    else:
        value.update({
            "quick_fix": ("Stop the programme and isolate power only from a dry safe position. Do not restart the washer; arrange qualified service."
                          if burning else "Stop using the washer and isolate it only from a dry safe position. Do not reset protection for repeated tests; arrange Siemens service."),
            "intro_html": f"<p>{item['en_meaning']}.</p><p>{item['en_action']}. Open no panels, make no measurements and run no test programme.</p>",
            "steps_json": [
                {"step": 1, "action": "Stop immediately", "detail": "Stop using the washer. For smoke or fire risk, keep clear, evacuate if necessary and call emergency services for immediate danger."},
                {"step": 2, "action": "Isolate only when safe", "detail": "Disconnect power from a dry safe position. Do not touch wet or damaged equipment or expose yourself to smoke."},
                {"step": 3, "action": "Do not restart", "detail": "Do not reset electrical protection to try the washer again and run no test programme."},
                {"step": 4, "action": "Record without touching", "detail": "Note the E-Nr, programme stage, displayed code, where the smell or sound arose and which protection device operated."},
                {"step": 5, "action": "Arrange the right professional help", "detail": "Contact Siemens service for the appliance and a qualified electrician if the socket, cable, protection or fixed installation may be involved."},
            ],
            "when_to_call_technician_html": "<p>This situation requires qualified assessment before the washer is used again. Contact Siemens service; also contact a qualified electrician if the fixed installation or protection may be responsible.</p><p>For active smoke, fire, sparks or immediate danger, keep clear, evacuate and call local emergency services.</p>",
            "prevention_html": "<p>Use an earthed outlet and the connection required by the installation manual. Avoid extension leads, keep the mains cable undamaged and resolve leaks before use.</p><p>Internal electrical and mechanical faults cannot be prevented through user dismantling or testing.</p>",
            "faq_json": [
                {"question": "Can I restart the washer to check it?", "answer": "No. Repeated tripping or a burning smell must be assessed before the appliance is used again."},
                {"question": "Should I reset the RCD?", "answer": "Not to test the washer again. Isolate the appliance safely and have the appliance and installation assessed by the appropriate professional."},
                {"question": "Can I open a panel to find the fault?", "answer": "No. Electricity, heat and possible leakage make internal inspection unsuitable for a user."},
                {"question": "Whom should I contact?", "answer": "Siemens service for the washer and a qualified electrician if the socket, cable, protection or fixed installation may be involved."},
            ],
        })
    return value


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-039-siemens-electrical-burning-before.json").read_text(encoding="utf-8"))
    rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {
        "batch": "039-siemens-electrical-burning",
        "status": "proposal_only_not_applied",
        "article_ids": list(ITEMS),
        "sources": [
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/trips-electrics",
            "https://www.siemens-home.bsh-group.com/se/kundservice/support/felsokning/tvattmaskiner/orsakar-kortslutning",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/not-turning-on",
            "https://www.siemens-home.bsh-group.com/ae/customer-service/support/troubleshooting/washing-machines/",
        ],
        "translations": {},
    }
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {
            "code": item["subject"],
            "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]},
            "en": make(item, False), "sv": make(item, True),
        }
    path = BASE_DIR / "data/article_reviews/batch-039-siemens-electrical-burning-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
