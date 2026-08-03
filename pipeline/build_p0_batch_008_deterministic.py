"""Build reviewed Bosch F23/F43/NO and no-spin/no-fill content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv
from pipeline.build_p0_batch_003_deterministic import unknown


ITEMS = {204: "F23", 205: "F43", 206: "NO", 312: "WONT_SPIN", 315: "WONT_FILL"}


def f23(sv: bool) -> dict:
    if sv:
        return build_sv("F23", "AquaStop har aktiverats och det kan finnas vatten i bottentråget eller ett läckage", "Stäng vattenkranen omedelbart och använd inte maskinen innan Bosch service har kontrollerat den")
    return build_en("F23", "AquaStop has activated and there may be water in the base or a leak", "Turn off the water tap immediately and do not use the washer until Bosch service has checked it")


def f43(sv: bool) -> dict:
    meaning = ("Bosch anger ingen generell betydelse för enbart F43 i sin aktuella övergripande tvättmaskinslista; exakt modellmanual och E‑Nr krävs" if sv else "Bosch does not provide a universal meaning for bare F43 in its current general washer list; the exact model manual and E-Nr are required")
    return unknown("F43", meaning, sv)


def no_display(sv: bool) -> dict:
    if sv:
        v = build_sv("NO", "luckan inte kan öppnas för omlastning därför att temperaturen eller vattennivån är för hög", "Vänta tills temperaturen sjunker eller vattennivån blir säker och välj Start/Reload för att fortsätta enligt manualen")
        v.update({
            "title_tag": "Bosch tvättmaskin visar NO: luckan kan inte öppnas",
            "meta_description": "Visar Bosch-tvättmaskinen NO? Det betyder normalt att luckan inte kan öppnas ännu. Läs säkra steg för temperatur, vattennivå och fortsatt program.",
            "h1": "Vad betyder NO på en Bosch-tvättmaskin?",
            "description": "I en officiell Bosch-manual betyder NO att luckan inte kan öppnas för omlastning eftersom temperaturen eller vattennivån är för hög.",
            "quick_fix": "Vänta tills temperaturen och vattennivån är säkra, håll luckan stängd och välj Start/Reload enligt manualen (tiden varierar).",
            "intro_html": "<p>NO är i den dokumenterade Bosch-manualen ett statusmeddelande: luckan kan inte öppnas för omlastning eftersom temperaturen eller vattennivån är för hög. Det är inte en reservdelsdiagnos.</p><p>Håll luckan stängd och välj Start/Reload för att fortsätta programmet. Tvinga inte upp luckan och försök inte tömma hett vatten.</p>",
        })
    else:
        v = build_en("NO", "the door cannot be opened for reloading because the temperature or water level is too high", "Wait until temperature or water level is safe and select Start/Reload to continue as described in the manual")
        v.update({
            "title_tag": "Bosch Washing Machine Shows NO: Door Cannot Open",
            "meta_description": "Bosch washer showing NO? It normally means the door cannot open yet. Follow safe steps for temperature, water level and continuing the programme.",
            "h1": "What Does NO Mean on a Bosch Washing Machine?",
            "description": "In an official Bosch manual, NO means the door cannot be opened for reloading because the temperature or water level is too high.",
            "quick_fix": "Wait until temperature and water level are safe, keep the door closed and select Start/Reload as the manual instructs (time varies).",
            "intro_html": "<p>In the documented Bosch manual, NO is a status message: the door cannot open for reloading because the temperature or water level is too high. It is not a replacement-parts diagnosis.</p><p>Keep the door closed and select Start/Reload to continue the programme. Do not force the door or attempt to drain hot water.</p>",
        })
    v["parts_json"] = []
    return v


def fault(kind: str, sv: bool) -> dict:
    spin = kind == "WONT_SPIN"
    code = "centrifugerar inte" if sv and spin else "fyller inte" if sv else "won't spin" if spin else "won't fill"
    if sv:
        meaning = "maskinen kan ha obalanserad tvätt, blockerad pump eller vikt avloppsslang" if spin else "vattenkranen kan vara stängd, tilloppsslangen vikt, inloppsfiltret blockerat, vattentrycket lågt eller luckan inte korrekt stängd"
        action = "Pausa säkert, fördela tvätten och kontrollera avloppsslang och pump endast enligt modellmanualen" if spin else "Kontrollera att kranen är öppen, slangarna raka, luckan stängd och rengör endast inloppsfilter enligt modellmanualen"
        v = build_sv(code, meaning, action)
        v["title_tag"] = "Bosch tvättmaskin centrifugerar inte: säkra kontroller" if spin else "Bosch tvättmaskin fyller inte vatten: säkra kontroller"
        v["meta_description"] = ("Centrifugerar Bosch-tvättmaskinen inte? Kontrollera lastbalans, avlopp och pump säkert och se när Bosch-service behövs." if spin else "Tar Bosch-tvättmaskinen inte in vatten? Kontrollera kran, tryck, slang, filter och lucka säkert och se när service behövs.")
        v["h1"] = "Varför centrifugerar inte Bosch-tvättmaskinen?" if spin else "Varför fyller inte Bosch-tvättmaskinen vatten?"
        v["description"] = ("Bosch anger obalanserad last, blockerat avlopp eller pump som vanliga orsaker när maskinen inte centrifugerar." if spin else "Bosch anger vattenförsörjning, lågt tryck, vikt slang, blockerat inloppsfilter eller ej låst lucka som vanliga orsaker när maskinen inte fyller.")
    else:
        meaning = "the load may be unbalanced or the drain hose or pump may be blocked" if spin else "the tap may be closed, the inlet hose kinked, the inlet filter blocked, water pressure low or the door not properly closed"
        action = "Pause safely, redistribute the laundry and check the drain hose and pump only as the model manual describes" if spin else "Check the tap is open, hoses are straight and the door is closed; clean only inlet filters covered by the model manual"
        v = build_en(code, meaning, action)
        v["title_tag"] = "Bosch Washing Machine Not Spinning: Safe Checks" if spin else "Bosch Washing Machine Not Filling: Safe Checks"
        v["meta_description"] = ("Bosch washer not spinning? Safely check load balance, drainage and the pump, and learn when Bosch service is needed." if spin else "Bosch washer not filling? Safely check the tap, pressure, hose, inlet filter and door, and learn when service is needed.")
        v["h1"] = "Why Is My Bosch Washing Machine Not Spinning?" if spin else "Why Is My Bosch Washing Machine Not Filling with Water?"
        v["description"] = ("Bosch lists an unbalanced load, blocked drainage or a blocked pump among common reasons a washer will not spin." if spin else "Bosch lists the water supply, low pressure, a kinked hose, blocked inlet filters or an unlocked door among common reasons a washer will not fill.")
    if spin:
        v["causes_json"] = ([
            {"cause": "Obalanserad last", "detail": "Ett tungt plagg eller hoptrasslad tvätt kan få maskinen att minska eller avbryta centrifugeringen."},
            {"cause": "Vikt eller blockerat avlopp", "detail": "Maskinen kan inte centrifugera korrekt om den inte kan tömma vattnet."},
            {"cause": "Blockerad pump", "detail": "Bosch beskriver rengöring av användaråtkomlig pump enligt modellmanualen, med risk för hett vatten."},
            {"cause": "Tekniskt drivfel", "detail": "Om säkra kontroller inte hjälper kan motor, drivning eller elektronik kräva Bosch-service."},
        ] if sv else [
            {"cause": "Unbalanced load", "detail": "One heavy item or tangled laundry can make the washer reduce or cancel the spin."},
            {"cause": "Kinked or blocked drainage", "detail": "The washer cannot spin correctly if it cannot drain the water."},
            {"cause": "Blocked pump", "detail": "Bosch describes cleaning a user-accessible pump according to the model manual, with a hot-water scalding risk."},
            {"cause": "Technical drive fault", "detail": "If safe checks do not help, the motor, drive or electronics may need Bosch service."},
        ])
    else:
        v["causes_json"] = ([
            {"cause": "Stängd kran eller lågt tryck", "detail": "Bosch anger att fullt öppnad kran bör ge ungefär 10 liter per minut; lågt installationstryck kräver rörmokare."},
            {"cause": "Vikt tilloppsslang", "detail": "En klämd eller vikt slang hindrar vattenflödet."},
            {"cause": "Blockerat inloppsfilter", "detail": "Bosch beskriver rengöring med liten borste efter att kranen stängts; AquaStop-enheten får inte sänkas i vatten."},
            {"cause": "Luckan är inte låst", "detail": "Tvätt i lucköppningen eller överlast kan hindra låset och därmed vattenintaget."},
        ] if sv else [
            {"cause": "Closed tap or low pressure", "detail": "Bosch states a fully open tap should supply about 10 litres per minute; low installation pressure needs a plumber."},
            {"cause": "Kinked inlet hose", "detail": "A pinched or kinked supply hose restricts the water flow."},
            {"cause": "Blocked inlet filter", "detail": "Bosch describes cleaning it with a small brush after closing the tap; never immerse the AquaStop unit."},
            {"cause": "Door not locked", "detail": "Laundry in the opening or an overloaded drum may prevent locking and therefore water intake."},
        ])
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    b = json.loads((BASE_DIR / "data/backups/article_reviews/batch-008-bosch-f23-wont-fill-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in b["rows"]}
    out = {"batch": "008-bosch-f23-wont-fill", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.bosch-home.com/us/owner-support/get-support/support-selfhelp-washing-error-e23-or-f23-washing-machine",
        "https://www.bosch-home.com/us/owner-support/error-codes/washers",
        "https://media3.bosch-home.com/Documents/9001026001_A.pdf",
        "https://www.bosch-home.com/us/owner-support/washers/troubleshooting/not-spinning",
        "https://www.bosch-home.com/us/owner-support/get-support/water-is-not-running",
    ], "translations": {}}
    for i, code in ITEMS.items():
        en = f23(False) if code == "F23" else f43(False) if code == "F43" else no_display(False) if code == "NO" else fault(code, False)
        sv = f23(True) if code == "F23" else f43(True) if code == "F43" else no_display(True) if code == "NO" else fault(code, True)
        out["translations"][str(i)] = {"code": code, "preserve": {"en_slug": rows[(i, "en")]["slug"], "sv_slug": rows[(i, "sv")]["slug"]}, "en": en, "sv": sv}
    p = BASE_DIR / "data/article_reviews/batch-008-bosch-f23-wont-fill-proposal.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(p)


if __name__ == "__main__":
    main()
