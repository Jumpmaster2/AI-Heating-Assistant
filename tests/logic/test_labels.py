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
