"""Build reviewed Electrolux common washing-machine fault content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline.build_p0_batch_002_deterministic import build_en, build_sv


ITEMS = {
    349: "drain",
    350: "spin",
    353: "fill",
    354: "door",
    355: "noise",
}

COPY = {
    "drain": {
        "en": ("Washing Machine Won't Drain", "the washer cannot pump out its water", "Check the drain hose, household drain and the user-accessible pump filter exactly as the model manual describes"),
        "sv": ("Tvättmaskinen tömmer inte", "tvättmaskinen kan inte pumpa ut vattnet", "Kontrollera avloppsslangen, fastighetens avlopp och det användaråtkomliga pumpfiltret exakt enligt modellens manual"),
    },
    "spin": {
        "en": ("Washing Machine Won't Spin", "the washer does not complete its spin phase", "Check the selected option, redistribute the load and confirm that the washer can drain"),
        "sv": ("Tvättmaskinen centrifugerar inte", "tvättmaskinen slutför inte centrifugeringen", "Kontrollera valt tillval, fördela om lasten och bekräfta att maskinen kan tömma"),
    },
    "fill": {
        "en": ("Washing Machine Won't Fill With Water", "the washer receives no water or fills too slowly", "Open the water tap fully and check water flow, the straight inlet hose and accessible inlet filter as the manual describes"),
        "sv": ("Tvättmaskinen fyller inte med vatten", "tvättmaskinen får inget vatten eller fyller för långsamt", "Öppna vattenkranen helt och kontrollera flöde, rak tilloppsslang och åtkomligt inloppsfilter enligt manualen"),
    },
    "door": {
        "en": ("Washing Machine Door Won't Open", "the safety lock has not released, often because the cycle just ended or water remains", "Wait 3–5 minutes, check the lock symbol and drain only by the documented procedure for the exact model"),
        "sv": ("Tvättmaskinens dörr öppnas inte", "säkerhetslåset har inte släppt, ofta för att programmet nyss avslutats eller vatten finns kvar", "Vänta 3–5 minuter, kontrollera låssymbolen och töm bara enligt den dokumenterade proceduren för exakt modell"),
    },
    "noise": {
        "en": ("Washing Machine Making Loud Noise", "excessive noise may come from installation, an unbalanced load or an accessible foreign object", "Stop the washer, redistribute the load and check levelling, clearances and accessible filter areas described in the manual"),
        "sv": ("Tvättmaskinen låter högt", "kraftigt ljud kan bero på installation, obalanserad last eller ett åtkomligt främmande föremål", "Stoppa maskinen, fördela om lasten och kontrollera nivå, frigång och åtkomliga filterområden enligt manualen"),
    },
}


def make(kind: str, sv: bool) -> dict:
    loc = "sv" if sv else "en"
    title, meaning, action = COPY[kind][loc]
    v = build_sv("—", meaning, action) if sv else build_en("—", meaning, action)
    if sv:
        v.update({
            "title_tag": f"Electrolux {title.lower()}: säkra kontroller",
            "meta_description": f"{title}? Se verifierade orsaker, säkra kontroller enligt manualen och tydliga tecken på att auktoriserad service behövs.",
            "h1": title,
            "description": meaning.capitalize() + ".",
            "quick_fix": action + " (cirka 5–30 minuter).",
            "intro_html": f"<p>{meaning.capitalize()}.</p><p>{action}. Stäng av och koppla ur före åtkomlig rengöring och använd aldrig våld.</p>",
        })
    else:
        v.update({
            "title_tag": f"Electrolux {title}: Safe Checks",
            "meta_description": f"{title}? See verified causes, safe manual-based checks and clear signs that authorised service is needed.",
            "h1": title,
            "description": meaning[0].upper() + meaning[1:] + ".",
            "quick_fix": action + " (about 5–30 minutes).",
            "intro_html": f"<p>{meaning[0].upper() + meaning[1:]}.</p><p>{action}. Switch off and unplug before accessible cleaning and never use force.</p>",
        })

    causes = {
        "drain": [("Drain hose restriction", "The hose may be kinked, blocked or installed incorrectly."), ("Blocked household drain", "A sink trap or standpipe can prevent discharge."), ("Blocked accessible pump filter", "Lint or small objects may obstruct the filter on models that provide user access."), ("Internal drain fault", "A pump, level system or internal blockage requires diagnosis.")],
        "spin": [("Unbalanced or unsuitable load", "One heavy item, overloading or a very small load may prevent safe spin."), ("Rinse Hold or no-spin selected", "The programme option can intentionally retain water or omit final spin."), ("Drainage restriction", "The washer normally cannot spin safely while water remains."), ("Internal drive or sensing fault", "Persistent failure requires professional diagnosis.")],
        "fill": [("Water supply closed or weak", "A closed tap or low flow prevents filling."), ("Kinked inlet hose", "A trapped or sharply bent hose restricts water."), ("Blocked accessible inlet filter", "Deposits at the hose connection can reduce flow."), ("Internal inlet or level fault", "A valve, wiring or sensor fault requires service.")],
        "door": [("Normal lock delay", "The lock may remain active for about 3–5 minutes after a cycle."), ("Water remains in the drum", "The safety lock prevents opening while water is present."), ("Water or laundry is too hot", "The lock can remain engaged until conditions are safe."), ("Door-lock or control fault", "A lock that stays engaged after safe checks requires service.")],
        "noise": [("Unbalanced or overloaded load", "A single heavy item or overloaded drum can cause impacts during spin."), ("Installation or levelling", "Transit bolts, uneven feet or contact with furniture can amplify vibration."), ("Accessible foreign object", "Coins, buttons or loose fittings may strike the drum or collect in the filter."), ("Internal mechanical fault", "Grinding, scraping or worsening noise requires professional diagnosis.")],
    }[kind]
    if sv:
        translated = {
            "drain": [("Begränsning i avloppsslangen", "Slangen kan vara vikt, blockerad eller felmonterad."), ("Blockerat fastighetsavlopp", "Vattenlås eller avloppsrör kan hindra tömningen."), ("Blockerat åtkomligt pumpfilter", "Ludd eller små föremål kan hindra filtret på modeller med användaråtkomst."), ("Internt tömningsfel", "Pump, nivåsystem eller intern blockering kräver diagnos.")],
            "spin": [("Obalanserad eller olämplig last", "Ett tungt plagg, överlast eller mycket liten last kan stoppa säker centrifugering."), ("Sköljstopp eller ingen centrifugering", "Valt tillval kan avsiktligt behålla vatten eller hoppa över slutcentrifugering."), ("Tömningshinder", "Maskinen kan normalt inte centrifugera säkert när vatten finns kvar."), ("Internt driv- eller givarfel", "Bestående fel kräver professionell diagnos.")],
            "fill": [("Stängd eller svag vattentillförsel", "Stängd kran eller lågt flöde hindrar fyllning."), ("Vikt tilloppsslang", "En klämd eller kraftigt böjd slang begränsar vattnet."), ("Blockerat åtkomligt inloppsfilter", "Avlagringar vid slanganslutningen kan minska flödet."), ("Internt inlopps- eller nivåfel", "Ventil, kablage eller givare kräver service.")],
            "door": [("Normal låsfördröjning", "Låset kan vara aktivt cirka 3–5 minuter efter programslut."), ("Vatten finns kvar i trumman", "Säkerhetslåset hindrar öppning när vatten finns kvar."), ("Vatten eller tvätt är för varm", "Låset kan förbli aktivt tills förhållandena är säkra."), ("Fel på lucklås eller styrning", "Ett lås som förblir aktivt efter säkra kontroller kräver service.")],
            "noise": [("Obalanserad eller överlastad trumma", "Ett tungt plagg eller överlast kan ge slag under centrifugering."), ("Installation eller nivå", "Transportbultar, ojämna fötter eller kontakt med inredning kan förstärka vibrationer."), ("Åtkomligt främmande föremål", "Mynt, knappar eller lösa detaljer kan slå mot trumman eller fastna i filtret."), ("Internt mekaniskt fel", "Malande, skrapande eller tilltagande ljud kräver professionell diagnos.")],
        }[kind]
        v["causes_json"] = [{"cause": a, "detail": b} for a, b in translated]
    else:
        v["causes_json"] = [{"cause": a, "detail": b} for a, b in causes]

    if sv:
        v["steps_json"] = [
            {"step": 1, "action": "Stoppa säkert", "detail": "Pausa programmet, vänta tills trumman står stilla och tvinga inte luckan."},
            {"step": 2, "action": "Kontrollera yttre förhållanden", "detail": action + "."},
            {"step": 3, "action": "Följ exakt manual", "detail": "Använd produktnumret för rätt instruktion; lossa inga paneler och improvisera ingen nödupplåsning."},
            {"step": 4, "action": "Gör ett kontrollerat test", "detail": "Testa en gång endast när inget läckage, bränd lukt, rök, kraftigt skrapljud eller elfel finns."},
            {"step": 5, "action": "Boka auktoriserad service", "detail": "Avsluta felsökningen om felet återkommer eller om en intern del misstänks."},
        ]
        v["when_to_call_technician_html"] = "<p>Boka auktoriserad service om felet kvarstår efter yttre kontroller, om trumman inte rör sig normalt eller om lås, pump, ventil, givare eller mekanik misstänks.</p><p>Stäng av direkt vid vatten nära el, bränd lukt, rök, onormal värme, utlöst elskydd eller kraftiga malande/skrapande slag.</p>"
        v["prevention_html"] = "<p>Töm fickor, dosera rätt, blanda stora och små plagg, undvik överlast och håll användaråtkomliga filter och slangar rena enligt manualens intervall.</p><p>Kontrollera att maskinen står stadigt och att slangar inte kläms; detta förebygger inte interna komponentfel.</p>"
    else:
        v["steps_json"] = [
            {"step": 1, "action": "Stop safely", "detail": "Pause the programme, wait for the drum to stop and do not force the door."},
            {"step": 2, "action": "Check external conditions", "detail": action + "."},
            {"step": 3, "action": "Follow the exact manual", "detail": "Use the product number for the correct procedure; remove no panels and improvise no emergency release."},
            {"step": 4, "action": "Make one controlled test", "detail": "Test once only when there is no leak, burning smell, smoke, heavy scraping noise or electrical fault."},
            {"step": 5, "action": "Arrange authorised service", "detail": "Stop troubleshooting if the fault returns or an internal component is suspected."},
        ]
        v["when_to_call_technician_html"] = "<p>Arrange authorised service if the fault remains after external checks, if the drum does not move normally or if the lock, pump, valve, sensor or mechanics are suspected.</p><p>Switch off immediately for water near electricity, burning smell, smoke, abnormal heat, tripped protection or severe grinding, scraping or impacts.</p>"
        v["prevention_html"] = "<p>Empty pockets, dose correctly, mix large and small items, avoid overloading and clean user-accessible filters and hoses at the manual's intervals.</p><p>Keep the washer stable and hoses free from pinching; this does not prevent internal component faults.</p>"
    v["parts_json"] = []
    assert len(v["title_tag"]) <= 70 and len(v["meta_description"]) <= 165
    return v


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-016-electrolux-common-faults-before.json").read_text(encoding="utf-8"))
    rows = {(r["article_id"], r["locale"]): r for r in backup["rows"]}
    out = {
        "batch": "016-electrolux-common-faults",
        "status": "proposal_only_not_applied",
        "article_ids": list(ITEMS),
        "sources": [
            "https://support.electrolux.co.uk/support-articles/article/washer-dryer-displays-error-message-e20-or-c2-emits-2-beeps-or-2-flashes",
            "https://support.electrolux.co.uk/support-articles/article/washing-machine-does-not-spin",
            "https://support.electrolux.co.uk/support-articles/article/washing-machine-displays-error-code-e10-e11-c1-or-emits-1-beep-1-flash",
            "https://support.electrolux.co.uk/support-articles/article/the-door-of-the-washing-machine-cannot-be-opened",
            "https://support.electrolux.co.uk/support-articles/article/washing-machine-emits-noises-and-shakes-while-spinning",
        ],
        "translations": {},
    }
    for article_id, kind in ITEMS.items():
        out["translations"][str(article_id)] = {
            "code": "—",
            "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]},
            "en": make(kind, False),
            "sv": make(kind, True),
        }
    path = BASE_DIR / "data/article_reviews/batch-016-electrolux-common-faults-proposal.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
