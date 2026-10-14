"""Cost accounting, monthly budget and adaptive check interval for the AI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CHARS_PER_TOKEN = 3.5


@dataclass(slots=True)
class Prices:
    """Prices in EUR per million tokens."""

    input: float
    output: float
    cache_write: float
    cache_read: float


def cost_eur(usage: dict[str, Any], prices: Prices) -> float:
    """Cost of one API call from its usage block."""

    def tokens(key: str) -> float:
        value = usage.get(key)
        return float(value) if isinstance(value, int | float) else 0.0

    total = (
        tokens("input_tokens") * prices.input
        + tokens("output_tokens") * prices.output
        + tokens("cache_creation_input_tokens") * prices.cache_write
        + tokens("cache_read_input_tokens") * prices.cache_read
    )
    return total / 1_000_000


def estimate_cost(prompt_chars: int, max_output_tokens: int, prices: Prices) -> float:
    """Upper estimate of a call before it is made."""
    input_tokens = prompt_chars / CHARS_PER_TOKEN
    return (input_tokens * prices.input + max_output_tokens * prices.output) / 1_000_000


@dataclass
class Budget:
    """Spending of the current month."""

    month: str = ""
    spent: float = 0.0
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    blocked: bool = False

    def roll(self, month: str) -> bool:
        """Start a new month. Returns True if a new month began."""
        if month == self.month:
            return False
        self.month = month
        self.spent = 0.0
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.blocked = False
        return True

    def can_spend(self, estimate: float, limit: float) -> bool:
        """True if the estimated call still fits into the budget."""
        allowed = self.spent + estimate <= limit
        self.blocked = not allowed
        return allowed

    def add(self, cost: float, usage: dict[str, Any]) -> None:
        self.spent = round(self.spent + cost, 6)
        self.calls += 1
        self.input_tokens += int(usage.get("input_tokens") or 0)
        self.output_tokens += int(usage.get("output_tokens") or 0)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Budget:
        budget = cls()
        if data:
            budget.month = str(data.get("month", ""))
            budget.spent = float(data.get("spent", 0.0))
            budget.calls = int(data.get("calls", 0))
            budget.input_tokens = int(data.get("input_tokens", 0))
            budget.output_tokens = int(data.get("output_tokens", 0))
            budget.blocked = bool(data.get("blocked", False))
        return budget


def next_interval_hours(base_hours: float, max_hours: float, stable_count: int) -> float:
    """Interval doubles with every check that changed nothing relevant."""
    return min(max_hours, base_hours * (2 ** max(0, stable_count)))


def update_stable_count(stable_count: int, relevant_change: bool, comfort_issue: bool) -> int:
    """Reset on relevant change or comfort issue, otherwise count up."""
    if relevant_change or comfort_issue:
        return 0
    return stable_count + 1
