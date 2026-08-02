"""Build reviewed LG tE1/tE2/tE3/UE and no-drain content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    103: ("tE1", "LG groups tE1 with model-specific temperature-sensor errors; the exact model manual must identify the affected sensor", "LG grupperar tE1 med modellspecifika temperaturgivarfel; exakt modellmanual måste identifiera berörd givare"),
    104: ("tE2", "LG groups tE2 with model-specific temperature-sensor errors; the exact model manual must identify the affected sensor", "LG grupperar tE2 med modellspecifika temperaturgivarfel; exakt modellmanual måste identifiera berörd givare"),
    105: ("tE3", "LG groups tE3 with model-specific temperature-sensor errors; the exact model manual must identify the affected sensor", "LG grupperar tE3 med modellspecifika temperaturgivarfel; exakt modellmanual måste identifiera berörd givare"),
    106: ("UE", "the load remained unbalanced after the washer tried to redistribute it", "lasten förblev obalanserad efter att maskinen försökt fördela om den"),
    148: ("—", "the LG washer cannot drain water from the drum", "LG-tvättmaskinen kan inte tömma vattnet ur trumman"),
}


def make(article_id: int, sv: bool) -> dict:
    code, en_meaning, sv_meaning = ITEMS[article_id]; meaning = sv_meaning if sv else en_meaning
    temp = article_id in (103, 104, 105); ue = article_id == 106
    if temp:
        action = "Stäng av, koppla ur i en minut en gång och boka auktoriserad LG-service om koden återkommer" if sv else "Switch off, unplug for one minute once and arrange authorised LG service if the code returns"
    elif ue:
        action = "Pausa, fördela tvätten jämnt, anpassa lastmängden och kontrollera att maskinen står i nivå" if sv else "Pause, redistribute laundry evenly, correct the load size and check that the washer is level"
    else:
        action = "Kontrollera avloppsslangen och rengör användaråtkomligt pumpfilter exakt enligt modellmanualen efter att vattnet svalnat" if sv else "Check the drain hose and clean the user-accessible pump filter exactly as the model manual specifies after water has cooled"
    v = build_sv(code, meaning, action) if sv else build_en(code, meaning, action)
    if sv:
        title = f"Vad betyder {code} på en LG-tvättmaskin?" if code != "—" else "LG-tvättmaskinen tömmer inte"
        v.update({
            "title_tag": f"LG-tvättmaskin felkod {code}: säkra steg" if code != "—" else "LG-tvättmaskin tömmer inte: säkra kontroller",
            "meta_description": (f"Visar LG-tvättmaskinen {code}? Läs verifierad, modellspecifik betydelse, säkra kontroller och när auktoriserad service krävs." if code != "—" else "Tömmer LG-tvättmaskinen inte? Kontrollera slang och filter säkert enligt manualen och se när auktoriserad service krävs."),
            "h1": title, "description": meaning.capitalize() + ".", "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Öppna inga paneler, mät inga givare eller ledningar och beställ inte en reservdel från koden eller symptomet ensam.</p>",
            "causes_json": ([
                {"cause": "Modellspecifikt temperaturgivarfel", "detail": "LG använder underkoderna på vissa kombi-/torkplattformar; exakt manual avgör givaren."},
                {"cause": "Kontakt- eller givarproblem", "detail": "Detta är internt och kräver utbildad tekniker."},
                {"cause": "Mycket varmt vatten", "detail": "LG anger att varmt vatten i trumman kan utlösa temperaturkod på vissa modeller."},
                {"cause": "Styr- eller kablagefel", "detail": "Koden bekräftar inte vilken komponent som ska bytas."},
            ] if temp else ([
                {"cause": "Tvätten ligger på ena sidan", "detail": "Plagg som klumpar ihop sig hindrar säker centrifugering."},
                {"cause": "För liten eller för stor last", "detail": "Olämplig mängd kan inte fördelas jämnt."},
                {"cause": "Olämpligt tvättgods", "detail": "Tunga enskilda eller olämpliga föremål ger obalans."},
                {"cause": "Maskinen står inte i nivå", "detail": "Ojämna fötter eller instabilt underlag kan utlösa UE."},
            ] if ue else [
                {"cause": "Vikt eller blockerad avloppsslang", "detail": "Begränsat flöde hindrar tömning."},
                {"cause": "Blockerat pumpfilter", "detail": "Ludd eller små föremål kan hindra det åtkomliga filtret."},
                {"cause": "För mycket skum", "detail": "Överdosering kan skapa luftfickor och störa pumpningen."},
                {"cause": "Internt pump- eller tömningsfel", "detail": "Bestående fel efter yttre kontroller kräver service."},
            ])),
            "steps_json": [
                {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
                {"step": 2, "action": "Koppla ur vid kontroll", "detail": "Dra ur kontakten med torra händer före filter, slang eller annan användaråtkomlig kontroll."},
                {"step": 3, "action": "Gör rätt åtgärd", "detail": action + "."},
                {"step": 4, "action": "Testa en gång", "detail": "Gör ett enda test efter korrigerad yttre orsak och endast utan läckage, lukt, värme, rök eller elskada."},
                {"step": 5, "action": "Boka LG-service", "detail": "Boka auktoriserad service om felet återkommer eller om en intern givare, pump, motor eller styrning misstänks."},
            ],
            "when_to_call_technician_html": f"<p>Boka auktoriserad LG-service om {code if code != '—' else 'tömningsfelet'} kvarstår efter säkra yttre kontroller. Temperaturgivare, intern pump, motor och elektronik är inte användarreparationer.</p><p>Koppla ur direkt vid läckage nära el, bränd lukt, rök, gnistor, onormal värme eller utlöst elskydd.</p>",
            "prevention_html": "<p>Följ lastgränser, blanda stora och små plagg, töm fickor, dosera rätt och håll avloppsslang och användaråtkomligt filter rena enligt manualen.</p><p>Håll maskinen i nivå; interna givar-, pump- och elektronikfel kan inte förebyggas genom demontering.</p>",
        })
    else:
        title = f"What Does {code} Mean on an LG Washing Machine?" if code != "—" else "LG Washing Machine Won't Drain"
        v.update({
            "title_tag": f"LG Washing Machine Error {code}: Safe Steps" if code != "—" else "LG Washing Machine Won't Drain: Safe Checks",
            "meta_description": (f"LG washer showing {code}? Read the verified, model-specific meaning, safe checks and when authorised service is required." if code != "—" else "LG washer not draining? Check the hose and filter safely by the manual and see when authorised service is required."),
            "h1": title, "description": meaning[0].upper() + meaning[1:] + ".", "quick_fix": action + " (about 5–30 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Open no panels, measure no sensors or wiring and do not order a part from the code or symptom alone.</p>",
            "causes_json": ([
                {"cause": "Model-specific temperature-sensor error", "detail": "LG uses these subcodes on some combo/dryer platforms; the exact manual identifies the sensor."},
                {"cause": "Sensor or contact problem", "detail": "This is internal and requires a trained technician."},
                {"cause": "Very hot water", "detail": "LG states that hot water in the drum can trigger a temperature code on some models."},
                {"cause": "Control or wiring fault", "detail": "The code does not confirm which component needs replacement."},
            ] if temp else ([
                {"cause": "Laundry gathered on one side", "detail": "Clumped items prevent safe spinning."},
                {"cause": "Load too small or too large", "detail": "An unsuitable amount may not distribute evenly."},
                {"cause": "Unsuitable laundry item", "detail": "A heavy single or unsuitable item can cause imbalance."},
                {"cause": "Washer not level", "detail": "Uneven feet or an unstable floor can trigger UE."},
            ] if ue else [
                {"cause": "Kinked or blocked drain hose", "detail": "Restricted flow prevents draining."},
                {"cause": "Clogged pump filter", "detail": "Lint or small objects can obstruct the accessible filter."},
                {"cause": "Excessive suds", "detail": "Overdosing may create air pockets and interfere with pumping."},
                {"cause": "Internal pump or drainage fault", "detail": "A persistent fault after external checks requires service."},
            ])),
            "steps_json": [
                {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
                {"step": 2, "action": "Unplug for checks", "detail": "Disconnect with dry hands before filter, hose or other user-accessible checks."},
                {"step": 3, "action": "Take the correct action", "detail": action + "."},
                {"step": 4, "action": "Test once", "detail": "Make one test after correcting an external cause and only without leakage, smell, heat, smoke or electrical damage."},
                {"step": 5, "action": "Arrange LG service", "detail": "Request authorised service if the fault returns or an internal sensor, pump, motor or control is suspected."},
            ],
            "when_to_call_technician_html": f"<p>Arrange authorised LG service if {code if code != '—' else 'the drain fault'} remains after safe external checks. Temperature sensors, internal pumps, motors and electronics are not user repairs.</p><p>Unplug immediately for leakage near electricity, burning smell, smoke, sparks, abnormal heat or tripped protection.</p>",
            "prevention_html": "<p>Follow load limits, mix large and small items, empty pockets, dose correctly and keep the drain hose and user-accessible filter clean as the manual specifies.</p><p>Keep the washer level; internal sensor, pump and electronics faults cannot be prevented through dismantling.</p>",
        })
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-021-lg-te1-te3-ue-drain-before.json").read_text(encoding="utf-8")); rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {"batch": "021-lg-te1-te3-ue-drain", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.lg.com/us/support/help-library/lg-washtower-error-code-resolution-guide--20154629492141",
        "https://www.lg.com/us/support/help-library/lg-front-load-washing-machine-error-code-ue-imbalance-error-is-displayed-CT10000012-20154629490038",
        "https://www.lg.com/us/support/help-library/oe-error-code-front-load-washer-CT10000010-1337714738535",
    ], "translations": {}}
    for article_id, (code, _, _) in ITEMS.items():
        out["translations"][str(article_id)] = {"code": code, "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(article_id, False), "sv": make(article_id, True)}
    path = BASE_DIR / "data/article_reviews/batch-021-lg-te1-te3-ue-drain-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
