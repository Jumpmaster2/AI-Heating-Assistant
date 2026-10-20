"""The panel texts are generated from the translation files."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_labels.py"


def test_labels_js_is_up_to_date() -> None:
    spec = importlib.util.spec_from_file_location("build_labels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TARGET.read_text(encoding="utf-8") == module.render(), (
        "frontend/labels.js is out of date, run python scripts/build_labels.py"
    )


def test_logbook_shows_readable_values() -> None:
    from messages import label_of, text

    msg = text(
        "de",
        "heating_day",
        decision="ja",
        source=label_of("de", "source", "rule_fallback"),
        phase=label_of("de", "phase", "ai_leads"),
        reason="",
    )
    assert "Regel ohne KI" in msg and "KI führt" in msg
    assert label_of("en", "error", "A") == "too cold without heating"
    assert label_of("en", "need", "unclear") == "unclear"
    assert label_of("en", "source", "something_new") == "something_new"  # unknown: as is
