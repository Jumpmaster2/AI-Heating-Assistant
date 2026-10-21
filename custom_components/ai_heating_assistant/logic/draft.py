"""Draft from windows of other rooms (cross ventilation).

An area has up to four combinations of windows in other rooms. As soon as every
window of one combination is open, the draft cools this area too; a combination
of a single window triggers on its own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

DRAFT_GROUP_KEYS = tuple(f"draft_group_{i}" for i in range(1, 5))
# version 1.1.0: one list of windows and whether all or any of them must be open
LEGACY_WINDOWS = "draft_window_sensors"
LEGACY_MODE = "draft_mode"


def draft_groups(cfg: dict[str, Any], own_windows: Iterable[str] = ()) -> list[list[str]]:
    """Combinations of an area, without its own windows and without empty ones."""
    if any(key in cfg for key in DRAFT_GROUP_KEYS):
        groups = [list(cfg.get(key) or []) for key in DRAFT_GROUP_KEYS]
    else:
        legacy = list(cfg.get(LEGACY_WINDOWS) or [])
        if cfg.get(LEGACY_MODE) == "any":
            groups = [[w] for w in legacy][: len(DRAFT_GROUP_KEYS)]
        else:
            groups = [legacy]
    own = set(own_windows)
    groups = [[w for w in group if w not in own] for group in groups]
    return [group for group in groups if group]


def has_draft(groups: list[list[str]], is_open: Callable[[str], bool]) -> bool:
    """True while every window of at least one combination is open."""
    return any(all(is_open(w) for w in group) for group in groups)
