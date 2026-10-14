"""Make the pure logic package importable without Home Assistant."""

import sys
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parents[2] / "custom_components" / "ai_heating_assistant"
if str(INTEGRATION) not in sys.path:
    sys.path.insert(0, str(INTEGRATION))
