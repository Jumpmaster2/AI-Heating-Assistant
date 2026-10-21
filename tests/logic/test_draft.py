"""Tests for the draft from windows of other rooms."""

from logic.draft import draft_groups, has_draft

KIDS, BATH, BED, OWN = "kids", "bath", "bed", "own"


def test_combinations_without_own_windows_and_empty_ones() -> None:
    cfg = {
        "draft_group_1": [KIDS, BATH],
        "draft_group_2": [],
        "draft_group_3": [KIDS, BED, OWN],
    }
    assert draft_groups(cfg, [OWN]) == [[KIDS, BATH], [KIDS, BED]]
    # only an own window: nothing left
    assert draft_groups({"draft_group_1": [OWN]}, [OWN]) == []
    assert draft_groups({}) == []


def test_combinations_of_version_1_1_0() -> None:
    old = {"draft_window_sensors": [KIDS, BED]}
    assert draft_groups({**old, "draft_mode": "all"}) == [[KIDS, BED]]
    assert draft_groups(old) == [[KIDS, BED]]
    assert draft_groups({**old, "draft_mode": "any"}) == [[KIDS], [BED]]
    many = {"draft_window_sensors": list("abcdef"), "draft_mode": "any"}
    assert len(draft_groups(many)) == 4
    # the new fields win over the old ones
    assert draft_groups({**old, "draft_group_1": [BATH]}) == [[BATH]]


def test_draft_needs_every_window_of_one_combination() -> None:
    groups = [[KIDS, BATH], [KIDS, BED]]

    def opened(*windows: str):
        return lambda w: w in windows

    assert not has_draft(groups, opened(BED, BATH))
    assert not has_draft(groups, opened(KIDS))
    assert has_draft(groups, opened(KIDS, BATH))
    assert has_draft(groups, opened(KIDS, BED))
    assert has_draft([[BED]], opened(BED))
    assert not has_draft([], opened(KIDS, BATH, BED))
