"""Tests for AI budget, interval, schema validation and prompts."""

import json

import pytest
from logic.ai_policy import (
    Budget,
    Prices,
    cost_usd,
    estimate_cost,
    next_interval_hours,
    overheat_issue,
    update_stable_count,
)
from logic.ai_schema import (
    CHECK_SCHEMA,
    GLOBAL,
    PARAMS,
    AnswerError,
    default_limits,
    validate_check,
    validate_nightly,
)
from logic.prompts import (
    MAX_BLOCK_CHARS,
    MAX_CUSTOM_BLOCKS,
    PROMPTS,
    PromptError,
    block_ids,
    build_system,
    check_messages,
    clean_prompts,
    nightly_messages,
)

PRICES = Prices(input=4.0, output=20.0, cache_write=5.0, cache_read=0.2)


def test_cost_from_usage() -> None:
    usage = {"input_tokens": 1500, "output_tokens": 800, "cache_read_input_tokens": None}
    assert cost_usd(usage, PRICES) == pytest.approx((1500 * 4 + 800 * 20) / 1e6)


def test_estimate_is_upper_bound() -> None:
    assert estimate_cost(3500, 2000, PRICES) == pytest.approx((1000 * 4 + 2000 * 20) / 1e6)


def test_estimate_uses_measured_output() -> None:
    # twice the mean output, at least 1000 tokens, at most the maximum
    assert estimate_cost(3500, 16000, PRICES, 800) == pytest.approx((1000 * 4 + 1600 * 20) / 1e6)
    assert estimate_cost(3500, 16000, PRICES, 100) == pytest.approx((1000 * 4 + 1000 * 20) / 1e6)
    assert estimate_cost(3500, 16000, PRICES, 9000) == pytest.approx((1000 * 4 + 16000 * 20) / 1e6)
    budget = Budget()
    assert budget.avg_output is None
    budget.add(0.1, {"input_tokens": 10, "output_tokens": 300})
    budget.add(0.1, {"input_tokens": 10, "output_tokens": 500})
    assert budget.avg_output == 400


def test_budget_blocks_and_rolls_over() -> None:
    budget = Budget()
    assert budget.roll("2026-10")
    budget.add(4.98, {"input_tokens": 10, "output_tokens": 5})
    assert budget.can_spend(0.01, 5.0)
    assert not budget.can_spend(0.05, 5.0)
    assert budget.blocked
    assert not budget.roll("2026-10")
    assert budget.roll("2026-11")
    assert budget.spent == 0 and not budget.blocked
    assert Budget.from_dict(budget.as_dict()) == budget


def test_adaptive_interval() -> None:
    assert next_interval_hours(4, 48, 0) == 4
    assert next_interval_hours(4, 48, 2) == 16
    assert next_interval_hours(4, 48, 10) == 48
    assert update_stable_count(3, relevant_change=False, comfort_issue=False) == 4
    assert update_stable_count(3, relevant_change=True, comfort_issue=False) == 0
    assert update_stable_count(3, relevant_change=False, comfort_issue=True) == 0
    assert update_stable_count(3, False, False, efficiency_issue=True) == 0


def test_overheat_issue_is_pro_rata() -> None:
    assert not overheat_issue(0.0, 0.0)
    assert overheat_issue(0.5, 1440)  # 0.5 Kh in a day
    assert not overheat_issue(0.4, 1440)
    assert overheat_issue(0.1, 240)  # 4 h allow 0.083 Kh


def test_validate_nightly() -> None:
    d = validate_nightly(
        {"heating_day": True, "confidence": 150, "reason": "kalt", "critical_area": "a1"}
    )
    assert d.heat and d.confidence == 100 and d.critical_area == "a1"
    with pytest.raises(AnswerError):
        validate_nightly({"heating_day": "yes", "confidence": 1})


CURRENT = {
    "a1": {k: p.default for k, p in PARAMS.items() if p.scope == "area"},
    GLOBAL: {"theta": 16.0},
}


def test_validate_check_clamps_and_limits_steps() -> None:
    raw = {
        "adjustments": [
            {"area": "a1", "parameter": "hysteresis_on", "value": 0.5, "reason": "too cold"},
            {"area": "a1", "parameter": "window_delay_min", "value": 100, "reason": "x"},
            {"area": "ignored", "parameter": "theta", "value": 15.5, "reason": "mild"},
            {"area": "a9", "parameter": "puffer", "value": 1.0, "reason": "unknown area"},
            {"area": "a1", "parameter": "bogus", "value": 1.0, "reason": "x"},
            {"area": "a1", "parameter": "sun_factor", "value": 1.0, "reason": "no change"},
        ],
        "summary": "ok",
        "confidence": 70,
    }
    result = validate_check(raw, CURRENT, default_limits())
    by_key = {a.parameter: a for a in result.applied}
    assert by_key["hysteresis_on"].new == pytest.approx(0.3)  # max step 0.1
    assert by_key["hysteresis_on"].clamped
    assert by_key["window_delay_min"].new == 7.0
    assert by_key["theta"].area == GLOBAL and by_key["theta"].new == 15.5
    assert "sun_factor" not in by_key
    assert len(result.rejected) == 2
    assert result.relevant_change


def test_validate_check_respects_configured_limits() -> None:
    limits = default_limits()
    limits["hysteresis_on"] = {"min": 0.1, "max": 0.25, "step": 0.5}
    raw = {
        "adjustments": [{"area": "a1", "parameter": "hysteresis_on", "value": 0.6, "reason": ""}],
        "summary": "",
        "confidence": 1,
    }
    result = validate_check(raw, CURRENT, limits)
    assert result.applied[0].new == 0.25


def test_validate_check_rejects_bad_structure() -> None:
    with pytest.raises(AnswerError):
        validate_check({"summary": "x"}, CURRENT, default_limits())


def test_schema_lists_all_parameters() -> None:
    enum = CHECK_SCHEMA["properties"]["adjustments"]["items"]["properties"]["parameter"]["enum"]
    assert set(enum) == set(PARAMS)


def test_prompts_are_compact_json() -> None:
    system, user = nightly_messages({"b": 1, "a": [1.234]}, "de")
    assert "German" in system
    assert user == '{"a":[1.234],"b":1}'
    system, user = check_messages({"x": 1}, "en")
    assert "hysteresis_on" in system and json.loads(user) == {"x": 1}
    # the check aims at saving heat with comfort as a hard limit
    assert "over_kh" in system and "on_per_kh" in system and "history" in system
    assert "hard limit" in system
    assert "over_kh" in nightly_messages({}, "en")[0]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("de", "in German."),
        ("de-CH", "in German."),
        ("en-GB", "in English."),
        ("fr", "in the language with the code 'fr'."),
    ],
)
def test_prompt_language_follows_home_assistant(language: str, expected: str) -> None:
    system, _ = nightly_messages({}, language)
    assert system.endswith(expected)


def test_value_outside_narrowed_limits_ends_inside() -> None:
    """Limits narrowed below the current value: the step limit must not keep it outside."""
    limits = default_limits()
    limits["hysteresis_on"] = {"min": 0.1, "max": 0.25, "step": 0.05}
    current = {"a1": {**CURRENT["a1"], "hysteresis_on": 0.5}, GLOBAL: CURRENT[GLOBAL]}
    raw = {
        "adjustments": [{"area": "a1", "parameter": "hysteresis_on", "value": 0.45, "reason": ""}],
        "summary": "",
        "confidence": 1,
    }
    assert validate_check(raw, current, limits).applied[0].new == 0.25


def test_prompt_blocks_without_changes_give_the_standard_prompt() -> None:
    for kind, spec in PROMPTS.items():
        expected = " ".join([spec.head, *(b.text for b in spec.blocks), spec.tail])
        assert build_system(kind) == expected
        assert build_system(kind, {}) == expected
        assert all(b.text in expected for b in spec.blocks)
    # one id per block and call
    assert all(len(set(block_ids(k))) == len(PROMPTS[k].blocks) for k in PROMPTS)


def test_prompt_blocks_disable_reword_and_add() -> None:
    config = {
        "disabled": ["learn"],
        "overrides": {"goal": "  Comfort first, always.  "},
        "custom": [
            {"text": "Abends brennt meist der Kaminofen.", "enabled": True},
            {"text": "Switched off block.", "enabled": False},
            {"text": "   "},
        ],
    }
    system = build_system("nightly", config)
    spec = PROMPTS["nightly"]
    assert "Learn from recent errors" not in system
    assert "Comfort first, always. " in system and "cool_kph is the learned" not in system
    assert "- Abends brennt meist der Kaminofen." in system
    assert "Switched off block" not in system
    # task first, answer format last; own blocks after the standard blocks
    assert system.startswith(spec.head) and system.endswith(spec.tail)
    assert system.index("Kaminofen") > system.index("Comfort first")
    system, _ = nightly_messages({}, "de", {"nightly": config})
    assert "Kaminofen" in system and system.endswith("in German.")
    system, _ = check_messages({}, "en", {"nightly": config})
    assert "Kaminofen" not in system


def test_clean_prompts() -> None:
    standard = PROMPTS["check"].blocks[0].text
    clean = clean_prompts(
        {
            "check": {
                "disabled": ["levers", "types"],
                "overrides": {"types": standard, "stats": " Own text "},
                "custom": [{"text": " a ", "enabled": False}, {"text": ""}],
            },
            "nightly": {"disabled": [], "overrides": {}, "custom": []},
        }
    )
    # standard order, unchanged wording and empty blocks dropped, unchanged calls left out
    assert clean == {
        "check": {
            "disabled": ["types", "levers"],
            "overrides": {"stats": "Own text"},
            "custom": [{"text": "a", "enabled": False}],
        }
    }
    assert clean_prompts({}) == {}
    for value, code in (
        ([], "invalid_value"),
        ({"other": {}}, "invalid_value"),
        ({"check": {"disabled": ["unknown"]}}, "invalid_value"),
        ({"check": {"overrides": {"unknown": "x"}}}, "invalid_value"),
        ({"check": {"custom": ["text"]}}, "invalid_value"),
        ({"check": {"custom": [{"text": 5}]}}, "invalid_value"),
        ({"check": {"custom": [{"text": "x" * (MAX_BLOCK_CHARS + 1)}]}}, "text_too_long"),
        ({"check": {"custom": [{"text": "x"}] * (MAX_CUSTOM_BLOCKS + 1)}}, "too_many_blocks"),
    ):
        with pytest.raises(PromptError, match=code):
            clean_prompts(value)
