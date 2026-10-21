"""Build frontend/labels.js for the panel from the translation files.

Field names and help texts come from the options dialog and the heating area
dialog, so both stay in one place. Run after changing a translation:

    python scripts/build_labels.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "ai_heating_assistant"
TARGET = COMPONENT / "frontend" / "labels.js"
LANGUAGES = ("de", "en")
OPTION_STEPS = ("general", "vacation", "rules", "ventilation", "ai", "decision")
HEADER = (
    "// Generated from the translation files by scripts/build_labels.py, do not edit by hand.\n"
)


def _add(fields: dict[str, list[str]], step: dict[str, Any]) -> None:
    descriptions = step.get("data_description", {})
    for key, name in step.get("data", {}).items():
        fields.setdefault(key, [name, descriptions.get(key, "")])


def labels(translation: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, list[str]] = {}
    options = translation["options"]["step"]
    for step in OPTION_STEPS:
        _add(fields, options[step])
        for sec in options[step].get("sections", {}).values():
            _add(fields, sec)
    setup_ai = translation["config"]["step"]["ai"]
    fields["api_key"] = [
        setup_ai["data"]["api_key"],
        setup_ai.get("data_description", {}).get("api_key", ""),
    ]
    area = translation["config_subentries"]["heating_area"]["step"]["user"]
    _add(fields, area)
    for sec in area["sections"].values():
        _add(fields, sec)
    # an existing area shows its learned values instead of the start values
    learned_section = translation["config_subentries"]["heating_area"]["step"]["reconfigure"][
        "sections"
    ]["learned_values"]
    learned: dict[str, list[str]] = {}
    _add(learned, learned_section)
    entity = translation["entity"]
    limits = options["ai_limits"]["sections"]
    return {
        "fields": fields,
        "learned": learned,
        "sections": {
            **{k: [v["name"], v.get("description", "")] for k, v in area["sections"].items()},
            "learned_values": [learned_section["name"], learned_section.get("description", "")],
        },
        "limits": {k: v["name"] for k, v in limits.items()},
        "limit_columns": next(iter(limits.values()))["data"],
        "errors": translation["options"]["error"],
        "area_errors": translation["config_subentries"]["heating_area"]["error"],
        "states": {
            "status": entity["sensor"]["status"]["state"],
            "ventilation": entity["sensor"]["ventilation"]["state"],
            "phase": entity["sensor"]["decision_phase"]["state"],
            "override": entity["select"]["heating_day_override"]["state"],
        },
        "effort": translation["selector"]["effort"]["options"],
        "heating_type": translation["selector"]["heating_type"]["options"],
        "draft_mode": translation["selector"]["draft_mode"]["options"],
    }


def render() -> str:
    data = {}
    for language in LANGUAGES:
        path = COMPONENT / "translations" / f"{language}.json"
        data[language] = labels(json.loads(path.read_text(encoding="utf-8")))
    return f"{HEADER}export const LABELS = {json.dumps(data, ensure_ascii=False, indent=1)};\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if TARGET.read_text(encoding="utf-8") != content:
            print(f"{TARGET} is out of date, run python scripts/build_labels.py")
            return 1
        return 0
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
