"""Centralized token-cost estimation for model-assisted telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class TokenPricing:
    """USD prices per one million input and output tokens."""

    input_usd_per_million: Decimal
    output_usd_per_million: Decimal


# Pricing is intentionally offline and centralized. Models absent from this
# table produce an unknown (None) estimate rather than an invented cost.
MODEL_PRICING_USD_PER_MILLION: dict[tuple[str, str], TokenPricing] = {}
LOCAL_PROVIDERS = frozenset({"local", "tesseract"})


def estimate_inference_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Return a deterministic estimate, zero for local, or None if unknown."""

    normalized_provider = str(provider or "").strip().casefold()
    if normalized_provider in LOCAL_PROVIDERS:
        return 0.0
    if input_tokens is None or output_tokens is None:
        return None
    pricing = MODEL_PRICING_USD_PER_MILLION.get(
        (normalized_provider, str(model or "").strip())
    )
    if pricing is None:
        return None
    total = (
        Decimal(input_tokens) * pricing.input_usd_per_million
        + Decimal(output_tokens) * pricing.output_usd_per_million
    ) / Decimal(1_000_000)
    return float(total)
