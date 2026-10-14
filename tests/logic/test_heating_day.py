"""Tests for heating day rule, evaluation, learning and phases."""

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
    rule_proposal,
    should_ask_ai,
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
    assert evaluate_need({"a": DayAreaStats(too_cold_min=20)}, EVAL) == Need.YES
    assert (
        evaluate_need({"a": DayAreaStats(relay_min=20), "b": DayAreaStats(relay_min=15)}, EVAL)
        == Need.YES
    )
    assert evaluate_need({"a": DayAreaStats(relay_min=5)}, EVAL) == Need.NO
    assert evaluate_need({"a": DayAreaStats(relay_min=20)}, EVAL) == Need.UNCLEAR
    assert evaluate_need({"a": DayAreaStats(emergency=True)}, EVAL) == Need.YES
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
    assert theta == 15.5


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


def test_day_stats_roundtrip() -> None:
    s = DayAreaStats(too_cold_min=3, relay_min=4, window_min=5, emergency=True)
    assert DayAreaStats.from_dict(s.as_dict()) == s
    record = DayRecord("2026-10-14", True, "ai", False, True)
    assert DayRecord.from_dict(record.as_dict()) == record
