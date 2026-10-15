"""Pricing and cost arithmetic.

Prices are USD per million tokens, from the Claude API pricing table.
Cache writes bill at 1.25x the input rate; cache reads at 0.1x.
"""

from __future__ import annotations

from dataclasses import dataclass

CACHE_WRITE_MULTIPLIER = 1.25
CACHE_READ_MULTIPLIER = 0.10


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float
    note: str = ""


PRICES = {
    "claude-opus-5": Price(5.00, 25.00),
    "claude-sonnet-5": Price(
        2.00, 10.00, "introductory pricing through 2026-08-31 (list: $3 / $15)"
    ),
    "claude-haiku-4-5": Price(1.00, 5.00),
    # Gemini 3.x Flash: introductory pricing through 2026-12-31, doubling to
    # $1.50 / $7.50 on 2027-01-01. Checked against ai.google.dev on 2026-08-21.
    "gemini-3.7-flash": Price(
        0.75, 3.75, "Gemini 3.7 Flash, intro pricing through 2026-12-31 (then $1.50 / $7.50)"
    ),
    "gemini-3.6-flash": Price(
        0.75, 3.75, "Gemini 3.6 Flash, intro pricing through 2026-12-31 (then $1.50 / $7.50)"
    ),
    "gemini-3.5-flash": Price(1.50, 9.00, "Gemini 3.5 Flash ($1.50 / $9.00 per Mtok)"),
    # Retired for new API keys — kept so old run manifests still price correctly.
    "gemini-2.5-flash": Price(0.075, 0.30, "Gemini 2.5 Flash ($0.075 / $0.30 per Mtok)"),
    "gemini-2.5-pro": Price(1.25, 5.00, "Gemini 2.5 Pro ($1.25 / $5.00 per Mtok)"),
    "gemini-1.5-flash": Price(0.075, 0.30, "Gemini 1.5 Flash ($0.075 / $0.30 per Mtok)"),
    "gemini-1.5-pro": Price(1.25, 5.00, "Gemini 1.5 Pro ($1.25 / $5.00 per Mtok)"),
    "gemini-2.0-flash": Price(0.10, 0.40, "Gemini 2.0 Flash ($0.10 / $0.40 per Mtok)"),
}


def price_of(model: str) -> Price:
    if model not in PRICES:
        raise KeyError(f"No price on file for {model!r}. Known: {', '.join(PRICES)}")
    return PRICES[model]


def cost_usd(
    model: str,
    *,
    input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    output_tokens: int = 0,
) -> float:
    p = price_of(model)
    billed_input = (
        input_tokens
        + cache_creation_input_tokens * CACHE_WRITE_MULTIPLIER
        + cache_read_input_tokens * CACHE_READ_MULTIPLIER
    )
    return (
        billed_input * p.input_per_mtok + output_tokens * p.output_per_mtok
    ) / 1_000_000


def cost_from_usage(model: str, usage) -> float:
    """Cost from a Messages API usage object (or an equivalent dict)."""
    get = usage.get if isinstance(usage, dict) else lambda k, d=0: getattr(usage, k, d) or 0
    return cost_usd(
        model,
        input_tokens=get("input_tokens", 0),
        cache_creation_input_tokens=get("cache_creation_input_tokens", 0),
        cache_read_input_tokens=get("cache_read_input_tokens", 0),
        output_tokens=get("output_tokens", 0),
    )


def billed_input_equivalent(usage) -> float:
    """Input tokens at full-price equivalence — the comparable unit across
    cached and uncached calls."""
    get = usage.get if isinstance(usage, dict) else lambda k, d=0: getattr(usage, k, d) or 0
    return (
        get("input_tokens", 0)
        + get("cache_creation_input_tokens", 0) * CACHE_WRITE_MULTIPLIER
        + get("cache_read_input_tokens", 0) * CACHE_READ_MULTIPLIER
    )
