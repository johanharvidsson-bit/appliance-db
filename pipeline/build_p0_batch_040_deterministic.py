"""Build reviewed remaining Samsung codes 1E/3E2/5C/AC2/dEi."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    23: {"code": "1E", "en_meaning": "Samsung identifies 1E or 1C as a water-level-sensor problem", "sv_meaning": "Samsung identifierar 1E eller 1C som problem med vattennivågivaren", "en_action": "Switch off at the mains for one minute once and arrange Samsung service if the code returns", "sv_action": "Stäng av vid nätet i en minut en gång och boka Samsung-service om koden återkommer", "en_causes": ["Water-level signal outside range", "Pressure path or level-sensing condition", "Model-specific sensor connection fault", "Internal sensor, wiring or control fault"], "sv_causes": ["Vattennivåsignal utanför området", "Tillstånd i tryckväg eller nivåavkänning", "Modellspecifikt anslutningsfel till givaren", "Internt givar-, kablage- eller styrfel"]},
    28: {"code": "3E2", "en_meaning": "Samsung groups 3E2 with motor-operation errors; the exact model manual defines the subcode", "sv_meaning": "Samsung grupperar 3E2 med fel i motordriften; exakt modellmanual definierar underkoden", "en_action": "Stop the washer, check only for overload or a clearly obstructed load, then power off for one minute once", "sv_action": "Stoppa maskinen, kontrollera endast överlast eller en tydligt hindrad last och stäng sedan av vid nätet i en minut en gång", "en_causes": ["Motor operation interrupted", "Overload or obstructed load", "Model-specific motor-speed signal", "Internal motor, sensor, wiring or control fault"], "sv_causes": ["Motordriften avbruten", "Överlast eller hindrad last", "Modellspecifik signal för motorhastighet", "Internt motor-, givar-, kablage- eller styrfel"]},
    34: {"code": "5C", "en_meaning": "Samsung identifies 5C or 5E as a drainage problem, commonly involving a blocked filter, kinked hose or incorrect hose installation", "sv_meaning": "Samsung identifierar 5C eller 5E som tömningsproblem, ofta orsakat av blockerat filter, vikt slang eller felaktig slanginstallation", "en_action": "Switch off and unplug, allow hot water to cool, then check the visible drain hose and clean the user-accessible filter exactly as the model manual specifies", "sv_action": "Stäng av och dra ur kontakten, låt hett vatten svalna och kontrollera sedan synlig avloppsslang samt rengör användaråtkomligt filter exakt enligt modellmanualen", "en_causes": ["Blocked user-accessible drain filter", "Kinked or blocked drain hose", "Incorrect drain-hose installation", "Internal drain-pump or control fault"], "sv_causes": ["Blockerat användaråtkomligt avloppsfilter", "Vikt eller blockerad avloppsslang", "Felaktig installation av avloppsslangen", "Internt pump- eller styrfel"]},
    37: {"code": "AC2", "en_meaning": "AC2 is model-specific; Samsung legacy support describes an I/O-board communication diagnostic, while current common-code lists use other AC-family communication codes", "sv_meaning": "AC2 är modellspecifik; äldre Samsung-support beskriver en kommunikationsdiagnos för I/O-kort, medan aktuella standardlistor använder andra AC-familjekoder", "en_action": "Photograph the complete display, confirm the exact model code and follow that model's manual; power off once and request service if AC2 returns", "sv_action": "Fotografera hela displayen, bekräfta exakt modellkod och följ modellens manual; stäng av en gång och boka service om AC2 återkommer", "en_causes": ["Model-specific communication diagnostic", "Incomplete or misread display", "Temporary control communication interruption", "Internal board, wiring or communication fault"], "sv_causes": ["Modellspecifik kommunikationsdiagnos", "Ofullständig eller feltolkad display", "Tillfälligt avbrott i styrkommunikation", "Internt kort-, kablage- eller kommunikationsfel"]},
    44: {"code": "dEi", "en_meaning": "dEi is not a universal code in Samsung's current common washer table and must not be assumed to mean dE1 without the exact model manual", "sv_meaning": "dEi är inte en universell kod i Samsungs aktuella standardtabell och får inte antas betyda dE1 utan manualen för exakt modell", "en_action": "Photograph every character, check that the door is fully closed without trapped laundry and use the exact model-code manual", "sv_action": "Fotografera varje tecken, kontrollera att luckan är helt stängd utan fastklämd tvätt och använd manualen för exakt modellkod", "en_causes": ["Incomplete or misread display", "Door not fully closed or laundry trapped", "Model-specific door information code", "Internal door-lock, wiring or control fault"], "sv_causes": ["Ofullständig eller feltolkad display", "Luckan inte helt stängd eller tvätt har fastnat", "Modellspecifik informationskod för luckan", "Internt lucklås-, kablage- eller styrfel"]},
}


def make(item: dict[str, object], sv: bool) -> dict[str, object]:
    code = str(item["code"]); meaning = str(item["sv_meaning" if sv else "en_meaning"]); action = str(item["sv_action" if sv else "en_action"]); causes = item["sv_causes" if sv else "en_causes"]
    value = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        value.update({
            "title_tag": f"Samsung-tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Samsung-tvättmaskinen {code}? Läs verifierad eller modellspecifik betydelse, säkra kontroller och när Samsung-service krävs.",
            "h1": f"Vad betyder {code} på en Samsung-tvättmaskin?", "description": meaning + ".", "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning}.</p><p>{action}. Koden ensam bekräftar ingen reservdel; demontera inget och gör inga elektriska mätningar.</p>",
            "causes_json": [{"cause": cause, "detail": "Detta är en möjlig orsak; exakt modellmanual och professionell diagnos avgör interna fel."} for cause in causes],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Avbryt programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Dokumentera kod och modell", "detail": f"Fotografera hela {code}-visningen och anteckna modellkod och programfas."},
                {"step": 3, "action": "Gör endast rätt yttre kontroll", "detail": action + ". Följ varningarna i exakt modellmanual."},
                {"step": 4, "action": "Testa högst en gång", "detail": "Testa endast efter korrigerad yttre orsak och aldrig vid läckage, bränd lukt, rök, onormal värme, elfel eller kraftigt mekaniskt ljud."},
                {"step": 5, "action": "Boka Samsung-service", "detail": "Boka service om koden kvarstår eller återkommer. Öppna inga paneler och prova inga interna delar."},
            ],
            "when_to_call_technician_html": f"<p>Boka Samsung-service om {code} kvarstår eller återkommer efter de dokumenterade yttre kontrollerna. Givare, motor, pump, lucklås, kablage och elektronik kräver modellspecifik diagnos.</p><p>Avbryt direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ last-, installations- och doseringsanvisningar, töm fickor och håll synliga slangar och användaråtkomliga filter rena enligt modellmanualen.</p><p>Interna givar-, motor-, kommunikations- och elektronikfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        value.update({
            "title_tag": f"Samsung Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Samsung washer showing {code}? Read the verified or model-specific meaning, safe checks and when Samsung service is required.",
            "h1": f"What Does {code} Mean on a Samsung Washing Machine?", "description": meaning + ".", "quick_fix": action + " (about 5–30 minutes).",
            "intro_html": f"<p>{meaning}.</p><p>{action}. The code alone confirms no replacement part; dismantle nothing and make no electrical measurements.</p>",
            "causes_json": [{"cause": cause, "detail": "This is a possible cause; the exact model manual and professional diagnosis determine internal faults."} for cause in causes],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Cancel the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Record code and model", "detail": f"Photograph the complete {code} display and note the model code and programme stage."},
                {"step": 3, "action": "Make only the correct external check", "detail": action + ". Follow every warning in the exact model manual."},
                {"step": 4, "action": "Test no more than once", "detail": "Test only after correcting an external cause, and never with leakage, burning smell, smoke, abnormal heat, electrical fault or severe mechanical noise."},
                {"step": 5, "action": "Arrange Samsung service", "detail": "Request service if the code remains or returns. Open no panels and test no internal parts."},
            ],
            "when_to_call_technician_html": f"<p>Arrange Samsung service if {code} remains or returns after documented external checks. Sensors, motor, pump, door lock, wiring and electronics require model-specific diagnosis.</p><p>Stop immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow load, installation and detergent guidance, empty pockets and keep visible hoses and user-accessible filters clean as the model manual specifies.</p><p>Internal sensor, motor, communication and electronics faults cannot be prevented through dismantling.</p>",
        })
    value = json.loads(json.dumps(value, ensure_ascii=False).replace("Bosch", "Samsung").replace("bosch", "Samsung"))
    value["parts_json"] = []
    assert len(value["title_tag"]) <= 70 and len(value["meta_description"]) <= 165
    return value


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-040-samsung-remaining-codes-before.json").read_text(encoding="utf-8")); rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {"batch": "040-samsung-remaining-codes", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.samsung.com/nl/support/home-appliances/wat-betekent-de-foutcode-op-het-display-van-mijn-wasmachine/",
        "https://www.samsung.com/uk/support/home-appliances/how-to-resolve-a-5e-or-5c-error-code-on-a-washing-machine/",
        "https://www.samsung.com/uk/support/home-appliances/check-out-the-information-codes-on-my-washing-machine/",
        "https://support-cacyber.samsung.com/cacyber/popup/iframe/pop_troubleshooting_fr.jsp?idx=898831&lang=ca&modelcode=WF337AAR%2FXAA",
        "https://www.samsung.com/ua/support/home-appliances/what-are-the-de-de1-de2-errors-on-the-display-of-my-washing-machine/",
    ], "translations": {}}
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": item["code"], "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(item, False), "sv": make(item, True)}
    path = BASE_DIR / "data/article_reviews/batch-040-samsung-remaining-codes-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
