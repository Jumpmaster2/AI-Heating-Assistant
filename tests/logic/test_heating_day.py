"""Tests for heating day rule, evaluation, learning and phases."""

import pytest
from logic.heating_day import (
    AiDecision,
    AreaSnapshot,
    DayAreaStats,
    DayRecord,
    EvalSettings,
    Need,
    Phase,
    PhaseSettings,
    RuleSettings,
    error_of,
    evaluate_need,
    final_decision,
    learn_rule,
    next_phase,
    rule_errors,
    rule_proposal,
    should_ask_ai,
    track_virtual,
)

RULE = RuleSettings()
EVAL = EvalSettings()
PHASE = PhaseSettings()


def _areas(*temps):
    return [AreaSnapshot(f"a{i}", f"A{i}", t, 21.0, 0.7) for i, t in enumerate(temps)]


def test_rule_off_when_warm_and_mild() -> None:
    r = rule_proposal(18.5, _areas(22.5, 22.3), 16.0, RULE)
    assert not r.heat and r.sure


def test_rule_heat_when_cold_forecast() -> None:
    r = rule_proposal(12.0, _areas(22.1), 16.0, RULE)
    assert r.heat and r.outdoor_rule and r.sure


def test_rule_heat_when_area_below_puffer() -> None:
    r = rule_proposal(17.0, _areas(21.5, 22.5), 16.0, RULE)
    assert r.heat and r.cold_areas == ["a0"] and not r.sure


def test_rule_unsure_close_to_theta() -> None:
    r = rule_proposal(16.9, _areas(22.17), 16.0, RULE)
    assert not r.heat and not r.sure


def test_rule_without_data_heats() -> None:
    r = rule_proposal(None, _areas(None), 16.0, RULE)
    assert r.heat and not r.sure and r.missing == ["a0"]


def test_should_ask_ai() -> None:
    sure = rule_proposal(12.0, _areas(22.0), 16.0, RULE)
    unsure = rule_proposal(16.5, _areas(22.0), 16.0, RULE)
    assert should_ask_ai(Phase.AI_LEADS, sure, 0, PHASE)
    assert should_ask_ai(Phase.SHARED, sure, 0, PHASE)
    assert not should_ask_ai(Phase.RULE_LEADS, sure, 1, PHASE)
    assert should_ask_ai(Phase.RULE_LEADS, sure, 7, PHASE)
    assert should_ask_ai(Phase.RULE_LEADS, unsure, 0, PHASE)


def test_final_decision_per_phase() -> None:
    rule_off_unsure = rule_proposal(16.5, _areas(22.0), 16.0, RULE)
    rule_off_sure = rule_proposal(20.0, _areas(22.5), 16.0, RULE)
    ai_heat = AiDecision(True, 80, "cold")
    assert final_decision(Phase.AI_LEADS, rule_off_sure, ai_heat) == (True, "ai")
    assert final_decision(Phase.AI_LEADS, rule_off_sure, None) == (False, "rule_fallback")
    assert final_decision(Phase.SHARED, rule_off_sure, ai_heat) == (False, "rule")
    assert final_decision(Phase.SHARED, rule_off_unsure, ai_heat) == (True, "ai")
    assert final_decision(Phase.SHARED, rule_off_unsure, AiDecision(False, 80, "")) == (
        False,
        "agreement",
    )
    assert final_decision(Phase.RULE_LEADS, rule_off_sure, ai_heat) == (True, "ai")
    assert final_decision(Phase.RULE_LEADS, rule_off_sure, None) == (False, "rule")


def test_evaluate_need() -> None:
    seen = {"observed_min": 600}
    assert evaluate_need({"a": DayAreaStats(too_cold_min=20, **seen)}, EVAL) == Need.YES
    # nothing heated and nothing was cold
    assert evaluate_need({"a": DayAreaStats(**seen)}, EVAL) == Need.NO
    assert evaluate_need({"a": DayAreaStats(too_cold_min=5, **seen)}, EVAL) == Need.UNCLEAR
    # heating ran: the virtual room without heating decides, not the relay minutes
    cold_virtual = DayAreaStats(relay_min=30, virtual_temp=19.5, virtual_cold_min=20, **seen)
    assert evaluate_need({"a": cold_virtual}, EVAL) == Need.YES
    warm_virtual = DayAreaStats(relay_min=30, virtual_temp=20.8, **seen)
    assert evaluate_need({"a": warm_virtual}, EVAL) == Need.NO
    some_virtual = DayAreaStats(relay_min=30, virtual_temp=20.4, virtual_cold_min=5, **seen)
    assert evaluate_need({"a": some_virtual}, EVAL) == Need.UNCLEAR
    # heating ran but the virtual room is not known yet: unclear unless really cold
    assert evaluate_need({"a": DayAreaStats(relay_min=30, **seen)}, EVAL) == Need.UNCLEAR
    assert (
        evaluate_need({"a": DayAreaStats(relay_min=30, too_cold_min=20, **seen)}, EVAL) == Need.YES
    )
    unknown, cold = DayAreaStats(relay_min=30, **seen), DayAreaStats(too_cold_min=20, **seen)
    assert evaluate_need({"a": unknown, "b": cold}, EVAL) == Need.YES
    # thermostats off or no temperature all day: nothing was seen
    assert evaluate_need({"a": DayAreaStats(), "b": DayAreaStats()}, EVAL) == Need.UNCLEAR
    assert evaluate_need({"a": DayAreaStats(), "b": DayAreaStats(**seen)}, EVAL) == Need.NO
    assert evaluate_need({"a": DayAreaStats(emergency=True)}, EVAL) == Need.YES
    assert evaluate_need({"a": DayAreaStats(manual_heat=True)}, EVAL) == Need.YES
    assert evaluate_need({}, EVAL) == Need.UNCLEAR


def test_error_of() -> None:
    assert error_of(False, Need.YES) == "A"
    assert error_of(True, Need.NO) == "B"
    assert error_of(True, Need.YES) is None
    assert error_of(None, Need.YES) is None
    assert error_of(False, Need.UNCLEAR) is None


def test_learn_error_a_raises_theta_and_puffer() -> None:
    rule = rule_proposal(17.0, _areas(22.0, 22.0), 16.0, RULE)
    stats = {"a0": DayAreaStats(too_cold_min=30), "a1": DayAreaStats()}
    theta, puffers, changes = learn_rule(16.0, {"a0": 0.7, "a1": 0.7}, rule, Need.YES, stats, EVAL)
    assert theta == 17.0 and puffers == {"a0": 0.9, "a1": 0.7}
    assert "theta" in changes and "puffer:a0" in changes


def test_learn_error_b_outdoor_rule_lowers_theta() -> None:
    rule = rule_proposal(15.0, _areas(22.0), 16.0, RULE)
    theta, _, _ = learn_rule(16.0, {"a0": 0.7}, rule, Need.NO, {"a0": DayAreaStats()}, EVAL)
    assert theta == 15.0


def test_learn_error_b_area_rule_lowers_puffer_and_clamps() -> None:
    rule = rule_proposal(18.0, _areas(21.05), 16.0, RULE)
    _, puffers, _ = learn_rule(16.0, {"a0": 0.05}, rule, Need.NO, {"a0": DayAreaStats()}, EVAL)
    assert puffers["a0"] == 0.0


def _history(n, agree=True, rule_err=None):
    return [
        DayRecord(
            date=f"d{i}",
            final=False,
            source="ai",
            rule=False,
            ai=(not agree),
            need=Need.NO,
            err_rule=rule_err,
        )
        for i in range(n)
    ]


def test_phase_advances() -> None:
    assert next_phase(Phase.AI_LEADS, _history(13), 13, PHASE) == Phase.AI_LEADS
    assert next_phase(Phase.AI_LEADS, _history(14), 14, PHASE) == Phase.SHARED
    assert next_phase(Phase.SHARED, _history(30), 20, PHASE) == Phase.SHARED
    assert next_phase(Phase.SHARED, _history(30), 21, PHASE) == Phase.RULE_LEADS


def test_phase_needs_agreement() -> None:
    assert next_phase(Phase.AI_LEADS, _history(14, agree=False), 14, PHASE) == Phase.AI_LEADS


def test_phase_falls_back_on_errors() -> None:
    history = _history(20) + _history(2, rule_err="A")
    assert next_phase(Phase.RULE_LEADS, history, 30, PHASE) == Phase.SHARED
    assert next_phase(Phase.SHARED, history, 30, PHASE) == Phase.AI_LEADS


def test_manual_days_do_not_count_as_rule_errors() -> None:
    history = _history(20) + _history(2, rule_err="A")
    for record in history[-2:]:
        record.manual = True
    assert rule_errors(history, 7) == 0
    assert next_phase(Phase.RULE_LEADS, history, 30, PHASE) == Phase.RULE_LEADS


def test_day_stats_roundtrip() -> None:
    s = DayAreaStats(
        too_cold_min=3,
        relay_min=4,
        window_min=5,
        emergency=True,
        virtual_temp=20.5,
        virtual_cold_min=6,
    )
    assert DayAreaStats.from_dict(s.as_dict()) == s
    assert DayAreaStats.from_dict({"too_cold_min": 1}).virtual_temp is None
    record = DayRecord("2026-10-14", True, "ai", False, True, manual=True)
    assert DayRecord.from_dict(record.as_dict()) == record


def test_learn_error_a_raises_puffer_when_virtual_unknown_but_room_cold() -> None:
    rule = rule_proposal(17.0, _areas(22.0), 16.0, RULE)
    stats = {"a0": DayAreaStats(too_cold_min=30, relay_min=60, observed_min=600)}
    theta, puffers, _ = learn_rule(16.0, {"a0": 0.7}, rule, Need.YES, stats, EVAL)
    assert theta == 17.0 and puffers["a0"] == 0.9


def test_track_virtual_cools_with_the_model_and_counts_cold_minutes() -> None:
    s = DayAreaStats()
    kw = {"target": 21.0, "margin": 0.5, "ready": True, "counting": True, "airing": False}
    track_virtual(s, 21.0, 1.0, lambda t: 0.6, **{**kw, "ready": False})
    assert s.virtual_temp is None  # the model does not know enough yet
    for _ in range(50):
        track_virtual(s, 21.0, 1.0, lambda t: 0.6, **kw)  # 0.01 K per minute
    assert s.virtual_temp == pytest.approx(20.5)
    assert s.virtual_cold_min == 0
    for _ in range(30):
        track_virtual(s, 21.0, 1.0, lambda t: 0.6, **kw)
    assert s.virtual_temp == pytest.approx(20.2)
    assert s.virtual_cold_min == 30
    assert s.cold_min == 0  # nothing heated: the real room counts
    s.relay_min = 10
    assert s.cold_min == 30


def test_track_virtual_follows_the_real_room_down_except_while_airing() -> None:
    s = DayAreaStats(virtual_temp=20.9)
    kw = {"target": 21.0, "margin": 0.5, "ready": True, "counting": False}
    track_virtual(s, 20.3, 1.0, lambda t: 0.0, airing=False, **kw)
    assert s.virtual_temp == 20.3  # never warmer than the real room
    track_virtual(s, 19.0, 1.0, lambda t: 0.0, airing=True, **kw)
    assert s.virtual_temp == 20.3  # an airing dip is not inherited


def test_track_virtual_stays_unknown_once_heating_ran() -> None:
    s = DayAreaStats(relay_min=10)
    kw = {"target": 21.0, "margin": 0.5, "ready": True, "counting": True, "airing": False}
    track_virtual(s, 21.0, 1.0, lambda t: 0.5, **kw)
    assert s.virtual_temp is None and s.cold_min is None
