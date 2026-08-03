"""Build reviewed Bosch CL/E17/E18/E36/E42 core content."""
from __future__ import annotations

import json

from config.settings import BASE_DIR
from pipeline import build_p0_batch_040_deterministic as base


ITEMS = {
    163: {"code": "CL", "en_meaning": "Bosch identifies CL as the child lock being active on models that use this display message", "sv_meaning": "Bosch identifierar CL som aktivt barnlås på modeller som använder detta displaymeddelande", "en_action": "Use the exact model manual or the marked key control to deactivate Child Lock because the control sequence varies by model", "sv_action": "Använd manualen för exakt modell eller den markerade nyckelkontrollen för att avaktivera barnlåset eftersom knappsekvensen varierar mellan modeller", "en_causes": ["Child Lock intentionally active", "Child Lock activated accidentally", "Model-specific key control not yet released", "Interface or control fault if CL cannot be cleared as documented"], "sv_causes": ["Barnlåset är avsiktligt aktivt", "Barnlåset aktiverades av misstag", "Modellspecifik nyckelkontroll har inte låsts upp", "Gränssnitts- eller styrfel om CL inte kan tas bort enligt manualen"]},
    165: {"code": "E17", "en_meaning": "Bosch identifies E17 as impaired water supply, including a closed tap, kinked inlet hose, low pressure or a blocked inlet filter", "sv_meaning": "Bosch identifierar E17 som begränsad vattentillförsel, bland annat stängd kran, vikt tilloppsslang, lågt tryck eller blockerat inloppsfilter", "en_action": "Open the tap fully, straighten the visible inlet hose and check household water pressure; clean an accessible inlet filter only as the exact manual specifies", "sv_action": "Öppna kranen helt, räta den synliga tilloppsslangen och kontrollera bostadens vattentryck; rengör åtkomligt inloppsfilter endast enligt exakt manual", "en_causes": ["Water tap closed or not fully open", "Kinked or trapped inlet hose", "Low household water pressure", "Blocked accessible inlet filter or internal inlet fault"], "sv_causes": ["Vattenkranen är stängd eller inte helt öppen", "Vikt eller klämd tilloppsslang", "Lågt vattentryck i bostaden", "Blockerat åtkomligt inloppsfilter eller internt tilloppsfel"]},
    166: {"code": "E18", "en_meaning": "Bosch identifies E18 as a blocked drain pump, drain hose or household waste connection", "sv_meaning": "Bosch identifierar E18 som blockering i avloppspump, avloppsslang eller bostadens avloppsanslutning", "en_action": "Close the tap, switch off and unplug, let hot water cool, then drain and clean the user-accessible pump filter and visible hose as the model manual specifies", "sv_action": "Stäng kranen, stäng av och dra ur kontakten, låt hett vatten svalna och töm samt rengör sedan användaråtkomligt pumpfilter och synlig slang enligt modellmanualen", "en_causes": ["Blocked user-accessible pump filter", "Kinked or blocked drain hose", "Blocked household waste connection", "Internal drain-pump or control fault"], "sv_causes": ["Blockerat användaråtkomligt pumpfilter", "Vikt eller blockerad avloppsslang", "Blockerad avloppsanslutning i bostaden", "Internt pump- eller styrfel"]},
    179: {"code": "E36", "en_meaning": "A standalone E36 display is incomplete for current Bosch guidance, which distinguishes longer values such as E:36/-10 and E:36/-25/-26", "sv_meaning": "En fristående E36-visning är ofullständig enligt aktuell Bosch-vägledning, som skiljer mellan längre värden som E:36/-10 och E:36/-25/-26", "en_action": "Photograph the complete display, record every suffix and use the exact E-Nr manual before choosing a drain-related action", "sv_action": "Fotografera hela displayen, dokumentera varje suffix och använd manualen för exakt E‑Nr innan en tömningsåtgärd väljs", "en_causes": ["Suffix not visible or not recorded", "Pump cap not correctly seated for some E:36/-10 models", "Blocked pump for some E:36/-25/-26 models", "Model-specific drain or control condition"], "sv_causes": ["Suffixet syns inte eller dokumenterades inte", "Pumpkåpan sitter inte korrekt på vissa E:36/-10-modeller", "Blockerad pump på vissa E:36/-25/-26-modeller", "Modellspecifikt tömnings- eller styrtillstånd"]},
    182: {"code": "E42", "en_meaning": "E42 has no universal definition in Bosch's current public washer code table, so the complete display and exact E-Nr manual are required", "sv_meaning": "E42 har ingen universell definition i Bosch aktuella offentliga felkodstabell för tvättmaskiner, så hela displayen och manualen för exakt E‑Nr krävs", "en_action": "Photograph the complete code and contact Bosch with the exact E-Nr; do not infer a motor or control component from E42 alone", "sv_action": "Fotografera hela koden och kontakta Bosch med exakt E‑Nr; dra ingen slutsats om motor- eller styrkomponent från enbart E42", "en_causes": ["Incomplete or misread display", "Model-specific information code", "A longer code or suffix not fully visible", "Internal condition requiring Bosch diagnosis"], "sv_causes": ["Ofullständig eller feltolkad display", "Modellspecifik informationskod", "En längre kod eller suffix syns inte helt", "Internt tillstånd som kräver Bosch-diagnos"]},
}


def make(item: dict[str, object], sv: bool) -> dict[str, object]:
    value = base.make(item, sv)
    value = json.loads(json.dumps(value, ensure_ascii=False).replace("Samsung", "Bosch").replace("samsung", "Bosch"))
    value["parts_json"] = []
    return value


def main() -> None:
    backup = json.loads((BASE_DIR / "data/backups/article_reviews/batch-043-bosch-core-codes-before.json").read_text(encoding="utf-8")); rows = {(row["article_id"], row["locale"]): row for row in backup["rows"]}
    out = {"batch": "043-bosch-core-codes", "status": "proposal_only_not_applied", "article_ids": list(ITEMS), "sources": [
        "https://www.bosch-home.com/us/owner-support/get-support/deactivate-the-child-lock",
        "https://www.bosch-home.com/us/owner-support/error-codes/washers",
        "https://www.bosch-home.com/eg/en/service/get-support/washing-machine-errors",
        "https://media3.bosch-home.com/Documents/9000890428_A.pdf",
        "https://media3.bosch-home.com/Documents/9001710962_C.pdf",
    ], "translations": {}}
    for article_id, item in ITEMS.items():
        out["translations"][str(article_id)] = {"code": item["code"], "preserve": {"en_slug": rows[(article_id, "en")]["slug"], "sv_slug": rows[(article_id, "sv")]["slug"]}, "en": make(item, False), "sv": make(item, True)}
    path = BASE_DIR / "data/article_reviews/batch-043-bosch-core-codes-proposal.json"; path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"); print(path)


if __name__ == "__main__":
    main()
