"""Own windows of an area by size.

The opening area decides how fast airing exchanges the air: a balcony door does in
a few minutes what a small window needs much longer for. Every size has a relative
opening area (a medium window is 1); the learned air exchange of a room is kept per
unit of opening area, so it stays right whichever window is opened.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

# area field -> size; ``window_sensors`` (medium) is the field of earlier versions
WINDOW_FIELDS: dict[str, str] = {
    "window_sensors_small": "small",
    "window_sensors": "medium",
    "window_sensors_large": "large",
    "door_sensors": "door",
}
SIZE_OPENING: dict[str, float] = {"small": 0.5, "medium": 1.0, "large": 1.6, "door": 2.5}


def own_windows(cfg: Mapping[str, Any]) -> dict[str, float]:
    """Window entity -> relative opening area. A contact entered in several sizes
    counts with the largest one."""
    windows: dict[str, float] = {}
    for key, size in WINDOW_FIELDS.items():
        for entity_id in cfg.get(key) or ():
            windows[entity_id] = max(windows.get(entity_id, 0.0), SIZE_OPENING[size])
    return windows


def open_area(windows: Mapping[str, float], is_open: Callable[[str], bool]) -> float:
    """Relative opening area of the windows open right now (0 = all closed)."""
    return sum(opening for entity_id, opening in windows.items() if is_open(entity_id))


def largest(windows: Mapping[str, float]) -> tuple[str, float] | None:
    """The window with the largest opening (the one to open for short, intense airing)."""
    if not windows:
        return None
    return max(windows.items(), key=lambda item: item[1])
