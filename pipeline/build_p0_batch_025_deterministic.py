"""Build reviewed Samsung 3E4/4C/4E/5A/5E content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {30: "3E4", 31: "4C", 32: "4E", 33: "5A", 35: "5E"}


def make(article_id: int, sv: bool) -> dict:
    code = ITEMS[article_id]
    if article_id == 30:
        meaning = ("Samsung groups 3E4 with motor-operation errors; the exact model manual defines the subcode" if not sv else "Samsung grupperar 3E4 med fel i motordriften; exakt modellmanual definierar underkoden")
        action = ("Switch off at the mains for one minute once and arrange Samsung service if 3E4 returns" if not sv else "Stäng av vid nätet i en minut en gång och boka Samsung-service om 3E4 återkommer")
        kind = "motor"
    elif article_id in (31, 32):
        meaning = (f"Samsung identifies {code} as a water-supply error" if not sv else f"Samsung anger att {code} är ett fel i vattentillförseln")
        action = ("Open the water tap fully, check pressure and straighten the external inlet hose; clean the mesh filter only as the manual specifies" if not sv else "Öppna vattenkranen helt, kontrollera tryck och räta den yttre tilloppsslangen; rengör nätfiltret endast enligt manualen")
        kind = "fill"
    elif article_id == 35:
        meaning = ("Samsung identifies 5E as a drainage error" if not sv else "Samsung anger att 5E är ett tömningsfel")
        action = ("Check the drain hose and clean the user-accessible pump filter exactly as the manual specifies after water has cooled" if not sv else "Kontrollera avloppsslangen och rengör det användaråtkomliga pumpfiltret exakt enligt manualen efter att vattnet svalnat")
        kind = "drain"
    else:
        meaning = ("5A is not defined in Samsung's generic public washer code table; confirm the characters and exact model manual before assigning a meaning" if not sv else "5A definieras inte i Samsungs generella offentliga kodtabell för tvättmaskiner; bekräfta tecknen och exakt modellmanual innan betydelse anges")
        action = ("Photograph the full display, verify that 5 has not been confused with S and contact Samsung support with the exact model" if not sv else "Fotografera hela displayen, kontrollera att 5 inte har förväxlats med S och kontakta Samsung-support med exakt modell")
        kind = "unknown"
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    causes_en = {
        "motor": ["Motor operation interrupted", "Overload or obstructed drum movement", "Model-specific motor or sensor signal", "Internal motor, wiring or control fault"],
        "fill": ["Closed tap or water outage", "Low flow or pressure", "Kinked inlet hose", "Blocked mesh filter or internal inlet fault"],
        "drain": ["Kinked or incorrectly installed drain hose", "Clogged pump filter", "Blocked household drain", "Internal pump or drainage fault"],
        "unknown": ["Characters misread on the display", "Model-specific information code", "Temporary control condition", "Internal fault requiring model-specific diagnosis"],
    }[kind]
    causes_sv = {
        "motor": ["Motoroperation avbruten", "Överlast eller blockerad trumrörelse", "Modellspecifik motor- eller givarsignal", "Internt motor-, kablage- eller styrfel"],
        "fill": ["Stängd kran eller vattenavbrott", "Lågt flöde eller tryck", "Vikt tilloppsslang", "Blockerat nätfilter eller internt inloppsfel"],
        "drain": ["Vikt eller felmonterad avloppsslang", "Blockerat pumpfilter", "Blockerat fastighetsavlopp", "Internt pump- eller tömningsfel"],
        "unknown": ["Feltolkade tecken på displayen", "Modellspecifik informationskod", "Tillfälligt styrtillstånd", "Internt fel som kräver modellspecifik diagnos"],
    }[kind]
    if sv:
        v.update({
            "title_tag": f"Samsung-tvättmaskin felkod {code}: säkra steg", "meta_description": f"Visar Samsung-tvättmaskinen {code}? Läs verifierad betydelse, säkra kontroller och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en Samsung-tvättmaskin?", "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–30 minuter).", "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Öppna inga paneler, mät inga interna delar och beställ inte en reservdel från koden ensam.</p>",
            "causes_json": [{"cause": x, "detail": "Detta är en möjlig orsak; exakt modellmanual och professionell diagnos avgör interna fel."} for x in causes_sv],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Dokumentera exakt", "detail": f"Fotografera hela {code}-visningen och notera modellnummer och programfas."},
                {"step": 3, "action": "Gör rätt yttre kontroll", "detail": action + "."},
                {"step": 4, "action": "Testa en gång", "detail": "Starta endast om efter korrigerad yttre orsak och utan läckage, bränd lukt, rök, onormal värme eller elskada."},
                {"step": 5, "action": "Boka Samsung-service", "detail": "Boka auktoriserad service om koden återkommer. Demontera inget och gör inga elektriska mätningar."},
            ],
            "when_to_call_technician_html": f"<p>Boka Samsung-service om {code} återkommer efter säkra yttre kontroller. Motor-, ventil-, pump-, givar- och elektronikfel är inte användarreparationer.</p><p>Koppla ur direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ lastgränser, töm fickor, dosera rätt och håll yttre slangar samt användaråtkomliga filter rena enligt manualen.</p><p>Notera hela koden och modellnumret; interna motor-, pump-, ventil- och elektronikfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"Samsung Washing Machine Error {code}: Safe Steps", "meta_description": f"Samsung washer showing {code}? Read the verified meaning, safe checks and when authorised service is required.",
            "h1": f"What Does {code} Mean on a Samsung Washing Machine?", "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–30 minutes).", "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Open no panels, measure no internal parts and do not order a part from the code alone.</p>",
            "causes_json": [{"cause": x, "detail": "This is a possible cause; the exact model manual and professional diagnosis determine internal faults."} for x in causes_en],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Record exactly", "detail": f"Photograph the complete {code} display and note the model number and programme stage."},
                {"step": 3, "action": "Make the correct external check", "detail": action + "."},
                {"step": 4, "action": "Test once", "detail": "Restart only after correcting an external cause and without leakage, burning smell, smoke, abnormal heat or electrical damage."},
                {"step": 5, "action": "Arrange Samsung service", "detail": "Request authorised service if the code returns. Dismantle nothing and make no electrical measurements."},
            ],
            "when_to_call_technician_html": f"<p>Arrange Samsung service if {code} returns after safe external checks. Motor, valve, pump, sensor and electronics faults are not user repairs.</p><p>Unplug immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow load limits, empty pockets, dose correctly and keep external hoses and user-accessible filters clean as the manual specifies.</p><p>Record the complete code and model number; internal motor, pump, valve and electronics faults cannot be prevented through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-025-samsung-motor-water-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "025-samsung-motor-water", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.samsung.com/uk/support/home-appliances/what-do-the-codes-on-my-washing-machine-mean/",
        "https://www.samsung.com/uk/support/home-appliances/the-4e-error-is-displayed-on-the-panel-of-my-washing-machine-what-can-i-do/",
        "https://www.samsung.com/uk/support/home-appliances/how-to-resolve-a-5e-or-5c-error-code-on-a-washing-machine/",
        "https://www.samsung.com/uk/support/home-appliances/what-to-do-if-your-washing-machine-is-not-spinning/",
    ], "translations": {}}
    for article_id, code in ITEMS.items():
        out["translations"][str(article_id)] = {"code": code, "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-025-samsung-motor-water-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
