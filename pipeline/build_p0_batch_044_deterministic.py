"""Build reviewed Bosch F18 and common-fault content for batch 044."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline import build_p0_batch_041_deterministic as base


ITEMS = {
    202: {"type": "code", "subject": "F18", "en_title": "What Does F18 Mean on a Bosch Washing Machine?", "sv_title": "Vad betyder F18 på en Bosch-tvättmaskin?", "en_meaning": "Bosch identifies F18 as a blocked or kinked drainage hose or a blocked drain pump", "sv_meaning": "Bosch identifierar F18 som en blockerad eller vikt avloppsslang eller blockerad avloppspump", "en_action": "Switch off and unplug, let hot water cool, then check the visible drain hose and clean the user-accessible pump only as the exact model manual specifies", "sv_action": "Stäng av och dra ur kontakten, låt hett vatten svalna och kontrollera sedan synlig avloppsslang samt rengör användaråtkomlig pump endast enligt manualen för exakt modell", "en_causes": ["Kinked or blocked drain hose", "Blocked household waste connection", "Blocked user-accessible drain pump", "Internal pump or control fault"], "sv_causes": ["Vikt eller blockerad avloppsslang", "Blockerad avloppsanslutning i bostaden", "Blockerad användaråtkomlig avloppspump", "Internt pump- eller styrfel"]},
    311: {"type": "fault", "subject": "drain", "en_title": "Bosch Washing Machine Won't Drain", "sv_title": "Bosch-tvättmaskinen tömmer inte", "en_meaning": "Bosch links a washer that will not drain to a kinked or blocked drain hose, household waste connection or blocked pump", "sv_meaning": "Bosch kopplar utebliven tömning till en vikt eller blockerad avloppsslang, bostadens avloppsanslutning eller blockerad pump", "en_action": "Switch off and unplug, allow hot water to cool, then inspect the visible drain hose and clean the user-accessible pump as the exact model manual specifies", "sv_action": "Stäng av och dra ur kontakten, låt hett vatten svalna och kontrollera sedan synlig avloppsslang samt rengör användaråtkomlig pump enligt manualen för exakt modell", "en_causes": ["Kinked or blocked drain hose", "Blocked household waste connection", "Blocked pump or accessible filter", "Internal drain-pump or control fault"], "sv_causes": ["Vikt eller blockerad avloppsslang", "Blockerad avloppsanslutning i bostaden", "Blockerad pump eller åtkomligt filter", "Internt pump- eller styrfel"]},
    313: {"type": "fault", "subject": "start", "en_title": "Bosch Washing Machine Won't Start", "sv_title": "Bosch-tvättmaskinen startar inte", "en_meaning": "Bosch recommends checking the power supply, securely closed door, active controls or settings and any displayed message", "sv_meaning": "Bosch rekommenderar kontroll av strömförsörjning, ordentligt stängd lucka, aktiva kontroller eller inställningar och eventuellt displaymeddelande", "en_action": "From a dry safe position check the plug and circuit protection, close the door until it latches and use the exact model manual for active Child Lock or delay settings", "sv_action": "Kontrollera kontakt och elskydd från en torr och säker plats, stäng luckan tills den låser och använd manualen för exakt modell vid aktivt barnlås eller fördröjd start", "en_causes": ["No safe power supply", "Door not fully closed or load trapped", "Child Lock, delay or another setting active", "Internal door-lock, interface or control fault"], "sv_causes": ["Säker strömförsörjning saknas", "Luckan är inte helt stängd eller tvätt har fastnat", "Barnlås, fördröjning eller annan inställning är aktiv", "Internt lucklås-, gränssnitts- eller styrfel"]},
    314: {"type": "fault", "subject": "leak", "en_title": "Bosch Washing Machine Is Leaking Water", "sv_title": "Bosch-tvättmaskinen läcker vatten", "en_meaning": "Bosch identifies the door seal and trapped laundry, detergent foaming, visible hoses and connections as useful first checks for a leak", "sv_meaning": "Bosch anger lucktätning och fastklämd tvätt, tvättmedelsskum samt synliga slangar och anslutningar som viktiga första kontroller vid läckage", "en_action": "Stop the washer, close the water tap and isolate power only from a dry safe position; do not use it again while leakage remains", "sv_action": "Stoppa maskinen, stäng vattenkranen och bryt strömmen endast från en torr och säker plats; använd den inte igen så länge läckaget kvarstår", "en_causes": ["Laundry or residue compromising the door seal", "Excess or unsuitable detergent causing foam", "Loose, damaged or leaking visible hose connection", "Internal leak requiring Bosch service"], "sv_causes": ["Tvätt eller rester försämrar lucktätningen", "För mycket eller olämpligt tvättmedel orsakar skum", "Lös, skadad eller läckande synlig slanganslutning", "Internt läckage som kräver Bosch-service"]},
    316: {"type": "fault", "subject": "door", "en_title": "Bosch Washing Machine Door Won't Open", "sv_title": "Bosch-tvättmaskinens lucka går inte att öppna", "en_meaning": "A Bosch washer door may remain locked while the drum moves, water is present, the temperature is high or a programme or safety condition is active", "sv_meaning": "Luckan på en Bosch-tvättmaskin kan förbli låst när trumman rör sig, vatten finns kvar, temperaturen är hög eller ett program eller säkerhetstillstånd är aktivt", "en_action": "Do not force the door; wait for the drum to stop and water to cool, then use the model manual's cancel, drain or normal unlock procedure", "sv_action": "Tvinga inte upp luckan; vänta tills trumman stannat och vattnet svalnat och använd sedan modellmanualens procedur för avbrytning, tömning eller normal upplåsning", "en_causes": ["Programme still running or drum moving", "Water remains in the drum", "Water temperature remains unsafe", "Door-lock, drain or control fault"], "sv_causes": ["Programmet körs fortfarande eller trumman rör sig", "Vatten finns kvar i trumman", "Vattentemperaturen är fortfarande osäker", "Fel på lucklås, tömning eller styrning"]},
}


def make(item: dict[str, object], sv: bool) -> dict[str, object]:
    value = base.make(item, sv)
    value = json.loads(json.dumps(value, ensure_ascii=False).replace("Samsung", "Bosch").replace("samsung", "Bosch"))
    value["parts_json"] = []
    if item["subject"] in {"leak", "door"}:
        action = str(item["sv_action"] if sv else item["en_action"])
        value["steps_json"] = ([
            {"step": 1, "action": "Stoppa säkert", "detail": action + "."},
            {"step": 2, "action": "Kontrollera utan demontering", "detail": "Inspektera endast användaråtkomliga delar och följ manualen för exakt E‑Nr."},
            {"step": 3, "action": "Undvik fortsatt användning", "detail": "Kör inte maskinen vid kvarvarande läckage, låst lucka med vatten eller annan säkerhetsrisk."},
            {"step": 4, "action": "Dokumentera symtomet", "detail": "Notera när problemet uppstod och eventuell komplett kod utan att öppna höljet."},
            {"step": 5, "action": "Boka Bosch-service", "detail": "Boka behörig service om problemet kvarstår efter den säkra grundkontrollen."},
        ] if sv else [
            {"step": 1, "action": "Stop safely", "detail": action + "."},
            {"step": 2, "action": "Inspect without dismantling", "detail": "Inspect user-accessible parts only and follow the manual for the exact E-Nr."},
            {"step": 3, "action": "Avoid further use", "detail": "Do not run the washer with a continuing leak, a locked door containing water or another safety risk."},
            {"step": 4, "action": "Record the symptom", "detail": "Note when the problem appeared and any complete code without opening the cabinet."},
            {"step": 5, "action": "Arrange Bosch service", "detail": "Arrange authorised service if the problem remains after the safe basic check."},
        ])
    assert len(value["title_tag"]) <= 70 and len(value["meta_description"]) <= 165
    return value


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-044-bosch-drain-start-leak-door-before.json").read_text(encoding="utf-8"))
    rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {"batch": "044-bosch-drain-start-leak-door", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.bosch-home.com/us/owner-support/error-codes/washers",
        "https://www.bosch-home.com/us/owner-support/get-support/washing-machine-does-not-drain-water",
        "https://www.bosch-home.com/us/owner-support/washing-machines/troubleshooting",
        "https://www.bosch-home.com/us/owner-support/get-support/washing-machine-leaking",
        "https://media3.bosch-home.com/Documents/9001267174_C.pdf",
    ], "translations": {}}
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": item["subject"], "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(item, False), "sv": make(item, True)}
    path = BASE_DIR / "data/article_reviews/batch-044-bosch-drain-start-leak-door-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
