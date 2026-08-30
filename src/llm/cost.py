from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CostEstimate:
    input_tokens: int
    output_tokens: int
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


def estimate_tokens(text: str) -> int:
    """
    Provider-independent conservative preflight estimate.

    This is intentionally an estimate rather than a model-specific
    tokenizer. It is used for rejecting obviously oversized prompts
    before making a provider call.

    Rough approximation:
        ~4 UTF-8 characters per token
    with a minimum of 1 token for non-empty input.
    """
    if not text:
        return 0

    return max(
        1,
        (len(text.encode("utf-8")) + 3) // 4,
    )


def calculate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
) -> CostEstimate:
    input_price_per_million = float(
        os.getenv(
            "LLM_INPUT_COST_PER_1M_USD",
            "0",
        )
    )

    output_price_per_million = float(
        os.getenv(
            "LLM_OUTPUT_COST_PER_1M_USD",
            "0",
        )
    )

    input_cost = (
        input_tokens
        / 1_000_000
        * input_price_per_million
    )

    output_cost = (
        output_tokens
        / 1_000_000
        * output_price_per_million
    )

    return CostEstimate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=input_cost + output_cost,
    )


def projected_cost(
    *,
    average_cost_per_request_usd: float,
    requests: int,
) -> float:
    return average_cost_per_request_usd * requests
