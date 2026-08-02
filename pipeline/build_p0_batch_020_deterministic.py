"""Build reviewed LG LE/OE/PE/PS/tE content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    96: ("LE", "the tub failed to spin because the motor could not operate normally", "trumman kunde inte rotera eftersom motorn inte kunde arbeta normalt"),
    97: ("OE", "the washer could not drain the water used during the cycle", "tvättmaskinen kunde inte tömma vattnet från programmet"),
    98: ("PE", "the water-level sensor is not working properly", "vattennivågivaren fungerar inte korrekt"),
    100: ("PS", "the washer detected a power-supply issue and stopped the programme", "tvättmaskinen upptäckte ett problem med elmatningen och stoppade programmet"),
    102: ("tE", "the washer detected a temperature-sensor or heating error", "tvättmaskinen upptäckte ett temperaturgivar- eller värmefel"),
}


ACTIONS = {
    96: ("Unplug for 5 minutes, reduce an overloaded wash and remove only clearly visible loose objects without reaching into mechanisms", "Koppla ur i 5 minuter, minska en överlastad tvätt och ta endast bort tydligt synliga lösa föremål utan att nå in i mekanismer"),
    97: ("Check the external drain hose and clean the user-accessible pump filter only by the exact manual after water has cooled", "Kontrollera den yttre avloppsslangen och rengör det användaråtkomliga pumpfiltret endast enligt exakt manual efter att vattnet svalnat"),
    98: ("Unplug for 10 seconds once and restart; do not test the level sensor or its wiring", "Koppla ur i 10 sekunder en gång och starta om; prova inte nivågivaren eller dess kablage"),
    100: ("Do not use a power strip; plug directly into a suitable wall outlet, unplug for 60 seconds once and request service if PS returns", "Använd inte grenuttag; anslut direkt till ett lämpligt vägguttag, koppla ur i 60 sekunder en gång och boka service om PS återkommer"),
    102: ("Unplug for 10 seconds once and restart; close the water taps, unplug and request service if tE returns", "Koppla ur i 10 sekunder en gång och starta om; stäng vattenkranarna, koppla ur och boka service om tE återkommer"),
}


CAUSES = {
    96: (["Overloaded drum", "Visible foreign object", "Motor temporarily overloaded", "Internal motor, sensor or drive fault"], ["Överlastad trumma", "Synligt främmande föremål", "Tillfälligt överbelastad motor", "Internt motor-, givar- eller drivfel"]),
    97: (["Kinked drain hose", "Clogged pump filter", "Excess detergent and suds", "Internal pump or drainage fault"], ["Vikt avloppsslang", "Blockerat pumpfilter", "För mycket tvättmedel och skum", "Internt pump- eller tömningsfel"]),
    98: (["Water-level sensing fault", "Temporary control error", "Excessive suds on some models", "Internal sensor, hose, wiring or board fault"], ["Fel på vattennivågivning", "Tillfälligt styrfel", "För mycket skum på vissa modeller", "Internt givar-, slang-, kablage- eller kortfel"]),
    100: (["Unsuitable power strip or extension", "Power-supply interruption", "Outlet or fixed-supply problem", "Internal power or control fault"], ["Olämpligt grenuttag eller förlängning", "Avbrott i elmatningen", "Fel på uttag eller fast installation", "Internt kraft- eller styrfel"]),
    102: (["Temperature-sensor error", "Heating-system error", "Temporary control condition", "Internal wiring or control fault"], ["Fel på temperaturgivaren", "Fel i värmesystemet", "Tillfälligt styrtillstånd", "Internt kablage- eller styrfel"]),
}


def make(article_id: int, sv: bool) -> dict:
    code, en_meaning, sv_meaning = ITEMS[article_id]; meaning = sv_meaning if sv else en_meaning; action = ACTIONS[article_id][1 if sv else 0]
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        v.update({
            "title_tag": f"LG-tvättmaskin felkod {code}: betydelse och säkra steg",
            "meta_description": f"Visar LG-tvättmaskinen {code}? Läs verifierad betydelse, säkra kontroller enligt manualen och när auktoriserad service krävs.",
            "h1": f"Vad betyder {code} på en LG-tvättmaskin?", "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Beställ inte en reservdel från koden ensam och demontera eller mät inga interna komponenter.</p>",
            "causes_json": [{"cause": x, "detail": "Detta är en möjlig orsak; exakt modellmanual och professionell diagnos avgör intern felkälla."} for x in CAUSES[article_id][1]],
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Avbryt programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Koppla ur", "detail": "Dra ur kontakten med torra händer. Hantera inte filtervatten förrän det har svalnat."},
                {"step": 3, "action": "Gör rätt yttre kontroll", "detail": action + "."},
                {"step": 4, "action": "Testa en gång", "detail": "Gör högst en återstart efter korrigerad yttre orsak och endast utan läckage, lukt, värme, rök eller elskada."},
                {"step": 5, "action": "Boka LG-service", "detail": f"Koppla ur och boka auktoriserad service om {code} återkommer. Använd elektriker om uttag eller fast elinstallation misstänks."},
            ],
            "when_to_call_technician_html": f"<p>Boka auktoriserad LG-service om {code} kvarstår eller återkommer. PE, PS och tE pekar mot system som inte ska provas av användaren; LE och OE kräver service när yttre kontroller inte löser felet.</p><p>Koppla ur direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ lastgränser, töm fickor, dosera rätt, håll yttre slangar fria från veck och rengör användaråtkomligt filter enligt modellmanualen.</p><p>Anslut maskinen enligt installationsanvisningen utan olämpligt grenuttag; interna givar-, motor- och elektronikfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        v.update({
            "title_tag": f"LG Washing Machine Error {code}: Meaning and Safe Steps",
            "meta_description": f"LG washer showing {code}? Read the verified meaning, safe manual-based checks and when authorised service is required.",
            "h1": f"What Does {code} Mean on an LG Washing Machine?", "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–30 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Do not order a part from the code alone, dismantle the washer or measure internal components.</p>",
            "causes_json": [{"cause": x, "detail": "This is a possible cause; the exact model manual and professional diagnosis determine an internal fault."} for x in CAUSES[article_id][0]],
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Cancel the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Unplug", "detail": "Disconnect with dry hands. Do not handle filter water until it has cooled."},
                {"step": 3, "action": "Make the correct external check", "detail": action + "."},
                {"step": 4, "action": "Test once", "detail": "Make at most one restart after correcting an external cause and only without leakage, smell, heat, smoke or electrical damage."},
                {"step": 5, "action": "Arrange LG service", "detail": f"Unplug and request authorised service if {code} returns. Use an electrician if the outlet or fixed supply is suspect."},
            ],
            "when_to_call_technician_html": f"<p>Arrange authorised LG service if {code} remains or returns. PE, PS and tE concern systems users must not test; LE and OE require service when external checks do not resolve the fault.</p><p>Unplug immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow load limits, empty pockets, dose correctly, keep external hoses free of kinks and clean the user-accessible filter as the model manual specifies.</p><p>Connect the washer as installed without an unsuitable power strip; internal sensor, motor and electronics faults cannot be prevented through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-020-lg-le-oe-pe-ps-te-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "020-lg-le-oe-pe-ps-te", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.lg.com/us/support/help-library/lg-frontload-washer-why-is-an-le-error-code-displayed-on-my-washing-machine--20152890351149",
        "https://www.lg.com/us/support/help-library/oe-error-code-front-load-washer-CT10000010-1337714738535",
        "https://www.lg.com/us/support/help-library/lg-front-load-washer-error-code-list-CT10000010-20155069413456",
    ], "translations": {}}
    for article_id, (code, _, _) in ITEMS.items():
        out["translations"][str(article_id)] = {"code": code, "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-020-lg-le-oe-pe-ps-te-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
