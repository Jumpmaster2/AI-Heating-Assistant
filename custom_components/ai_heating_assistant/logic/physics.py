"""Small physical and calendar helpers."""

from __future__ import annotations

import math
import re
from datetime import date

_DAY_MONTH = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.?\s*$")


def absolute_humidity(temp_c: float, rel_humidity: float) -> float:
    """Return absolute humidity in g/m³ (Magnus formula)."""
    saturation = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    return 216.7 * (rel_humidity / 100.0 * saturation) / (temp_c + 273.15)


def parse_day_month(value: str) -> tuple[int, int]:
    """Parse ``DD.MM.`` into (day, month). Raises ValueError if invalid."""
    match = _DAY_MONTH.match(value or "")
    if not match:
        raise ValueError(f"invalid day.month: {value!r}")
    day, month = int(match.group(1)), int(match.group(2))
    # Validate with a leap year so 29.02. is accepted.
    date(2024, month, day)
    return day, month


def in_season(today: date, start: tuple[int, int], end: tuple[int, int]) -> bool:
    """Return True if ``today`` lies within the season (inclusive, may wrap the year)."""
    key = (today.month, today.day)
    start_key = (start[1], start[0])
    end_key = (end[1], end[0])
    if start_key <= end_key:
        return start_key <= key <= end_key
    return key >= start_key or key <= end_key


def clamp(value: float, low: float, high: float) -> float:
    """Clamp value into [low, high]."""
    return max(low, min(high, value))
