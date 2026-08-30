from unittest.mock import patch

import pytest

from src.llm import client as llm_client
from src.llm.cost import (
    calculate_cost,
    estimate_tokens,
    projected_cost,
)


def test_token_estimate_empty():
    assert estimate_tokens("") == 0


def test_token_estimate_is_positive():
    assert estimate_tokens(
        "hello world"
    ) > 0


def test_cost_zero_for_local_ollama(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_INPUT_COST_PER_1M_USD",
        "0",
    )
    monkeypatch.setenv(
        "LLM_OUTPUT_COST_PER_1M_USD",
        "0",
    )

    result = calculate_cost(
        input_tokens=1000,
        output_tokens=500,
    )

    assert result.total_cost_usd == 0


def test_paid_provider_cost_math(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_INPUT_COST_PER_1M_USD",
        "2",
    )
    monkeypatch.setenv(
        "LLM_OUTPUT_COST_PER_1M_USD",
        "8",
    )

    result = calculate_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )

    assert result.input_cost_usd == 2
    assert result.output_cost_usd == 8
    assert result.total_cost_usd == 10


def test_projection_math():
    assert projected_cost(
        average_cost_per_request_usd=0.01,
        requests=1000,
    ) == pytest.approx(10)


def test_preflight_rejects_oversized_prompt(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_MAX_INPUT_TOKENS",
        "1",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "fake",
    )

    with patch(
        "src.llm.client.build_provider"
    ) as provider:
        with pytest.raises(
            ValueError,
            match="token budget exceeded",
        ):
            llm_client._call_model(
                system_prompt=(
                    "This prompt is far larger "
                    "than one estimated token."
                ),
                user_message="hello",
                repair_count=0,
            )

        provider.assert_not_called()
