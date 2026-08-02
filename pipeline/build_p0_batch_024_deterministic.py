"""Build reviewed Samsung 1LC and 3C/3E motor-family content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {24: "1LC", 25: "3C", 26: "3E", 27: "3E1", 29: "3E3"}


def make(article_id: int, sv: bool) -> dict:
    code = ITEMS[article_id]; motor = article_id != 24
    if motor:
        meaning = (f"Samsung groups {code} with motor-operation errors; the exact model manual defines the subcode" if not sv else f"Samsung grupperar {code} med fel i motordriften; exakt modellmanual definierar underkoden")
        action = ("Switch off at the mains, wait one minute and start one new programme; arrange Samsung service if the code returns" if not sv else "Stäng av vid nätet, vänta en minut och starta ett nytt program en gång; boka Samsung-service om koden återkommer")
    else:
        meaning = ("1LC is model-specific; Samsung's public guide groups LC/LC1-family codes with low-water-level or drain-hose conditions" if not sv else "1LC är modellspecifik; Samsungs offentliga guide grupperar LC-/LC1-familjen med låg vattennivå eller avloppsslangens läge")
        action = ("Stop the washer, check for visible leakage and confirm the external drain hose position from the exact model manual" if not sv else "Stoppa maskinen, kontrollera synligt läckage och bekräfta den yttre avloppsslangens läge i exakt modellmanual")
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"Samsung-tvättmaskin felkod {code}: säkra steg",
            "meta_description": f"Visar Samsung-tvättmaskinen {code}? Läs verifierad, modellspecifik betydelse, säkra kontroller och när service krävs.",
            "h1": f"Vad betyder {code} på en Samsung-tvättmaskin?", "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–15 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Koden bekräftar inte en viss reservdel; öppna inga paneler och mät inte motor, givare, kablage eller styrkort.</p>",
            "causes_json": ([
                {"cause": "Modellspecifikt LC-tillstånd", "detail": "Hela koden och exakt modellmanual krävs för rätt tolkning."},
                {"cause": "Avloppsslang för lågt eller felplacerad", "detail": "Fel höjd kan ge självdränering och låg vattennivå."},
                {"cause": "Synligt eller internt läckage", "detail": "Stoppa användningen vid vatten runt maskinen."},
                {"cause": "Internt nivå- eller styrfel", "detail": "Återkommande kod kräver Samsung-service."},
            ] if not motor else [
                {"cause": "Motoroperation avbruten", "detail": f"Samsung listar {code} i motorfamiljen."},
                {"cause": "Överlast eller blockerad trumrörelse", "detail": "För stor last kan hindra normal motoroperation."},
                {"cause": "Modellspecifik motor- eller givarsignal", "detail": "Underkoden ska inte översättas till en viss del utan rätt manual."},
                {"cause": "Internt motor-, kablage- eller styrfel", "detail": "Detta kräver utbildad tekniker."},
            ]),
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Avbryt programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Dokumentera kod och modell", "detail": f"Fotografera hela {code}-visningen och notera modellnummer och programfas."},
                {"step": 3, "action": "Gör endast yttre kontroll", "detail": action + "."},
                {"step": 4, "action": "Testa en gång", "detail": "Starta bara om en gång och endast utan läckage, bränd lukt, rök, onormal värme, elfel eller kraftigt mekaniskt ljud."},
                {"step": 5, "action": "Boka Samsung-service", "detail": "Boka auktoriserad service om koden återkommer. Demontera inget och gör inga elektriska mätningar."},
            ],
            "when_to_call_technician_html": f"<p>Boka Samsung-service om {code} återkommer efter en avstängning. Motorfamiljens underkoder och bestående LC-tillstånd kräver modellspecifik professionell diagnos.</p><p>Koppla ur direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ lastgränser, töm fickor, håll maskinen i nivå och montera avloppsslangen enligt exakt installationsmanual.</p><p>Interna motor-, givar-, kommunikations- och elektronikfel kan inte förebyggas eller diagnostiseras säkert genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"Samsung Washing Machine Error {code}: Safe Steps",
            "meta_description": f"Samsung washer showing {code}? Read the verified, model-specific meaning, safe checks and when service is required.",
            "h1": f"What Does {code} Mean on a Samsung Washing Machine?", "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–15 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. The code does not confirm a particular part; open no panels and measure no motor, sensor, wiring or board.</p>",
            "causes_json": ([
                {"cause": "Model-specific LC condition", "detail": "The complete code and exact model manual are required for interpretation."},
                {"cause": "Drain hose too low or misplaced", "detail": "Incorrect height can cause siphoning and a low water level."},
                {"cause": "Visible or internal leakage", "detail": "Stop using the washer when water is present around it."},
                {"cause": "Internal level or control fault", "detail": "A recurring code requires Samsung service."},
            ] if not motor else [
                {"cause": "Motor operation interrupted", "detail": f"Samsung lists {code} in the motor-error family."},
                {"cause": "Overload or obstructed drum movement", "detail": "An excessive load can prevent normal motor operation."},
                {"cause": "Model-specific motor or sensor signal", "detail": "Do not translate the subcode into a specific part without the correct manual."},
                {"cause": "Internal motor, wiring or control fault", "detail": "This requires a trained technician."},
            ]),
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Cancel the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Record code and model", "detail": f"Photograph the complete {code} display and note the model number and programme stage."},
                {"step": 3, "action": "Make external checks only", "detail": action + "."},
                {"step": 4, "action": "Test once", "detail": "Restart once only without leakage, burning smell, smoke, abnormal heat, electrical fault or severe mechanical noise."},
                {"step": 5, "action": "Arrange Samsung service", "detail": "Request authorised service if the code returns. Dismantle nothing and make no electrical measurements."},
            ],
            "when_to_call_technician_html": f"<p>Arrange Samsung service if {code} returns after one shutdown. Motor-family subcodes and a persistent LC condition require model-specific professional diagnosis.</p><p>Unplug immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow load limits, empty pockets, keep the washer level and install the drain hose according to the exact installation manual.</p><p>Internal motor, sensor, communication and electronics faults cannot be safely prevented or diagnosed through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-024-samsung-1lc-motor-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "024-samsung-1lc-motor", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.samsung.com/uk/support/home-appliances/check-out-the-information-codes-on-my-washing-machine/",
        "https://www.samsung.com/uk/support/home-appliances/what-do-the-codes-on-my-washing-machine-mean/",
        "https://www.samsung.com/uk/support/home-appliances/what-to-do-if-your-washing-machine-is-not-spinning/",
    ], "translations": {}}
    for article_id, code in ITEMS.items():
        out["translations"][str(article_id)] = {"code": code, "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-024-samsung-1lc-motor-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
