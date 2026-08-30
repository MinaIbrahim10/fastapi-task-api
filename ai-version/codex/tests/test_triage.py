import asyncio
import json

import httpx
import pytest

from triage.client import Settings, TriageClient, TriageUnavailable
from triage.models import TriageResult


VALID = {
    "category": "bug",
    "urgency": "high",
    "suggested_team": "engineering",
    "confidence": 0.91,
    "needs_review": False,
    "reason": "The reported crash blocks normal use.",
}


def answer(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 12}})


def test_valid_structured_result_and_separated_roles():
    seen = []

    async def handler(request):
        seen.append(json.loads(request.content))
        return answer(json.dumps(VALID))

    client = TriageClient(Settings(max_retries=0), httpx.MockTransport(handler))
    result = asyncio.run(client.classify("App crashes after login"))
    asyncio.run(client.aclose())
    assert result.model_dump(mode="json") == VALID
    assert [m["role"] for m in seen[0]["messages"]] == ["system", "user"]
    assert seen[0]["response_format"]["type"] == "json_schema"


def test_exactly_one_semantic_repair():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return answer("not json" if calls == 1 else json.dumps(VALID))

    client = TriageClient(Settings(max_retries=0), httpx.MockTransport(handler))
    assert asyncio.run(client.classify("help")).category.value == "bug"
    asyncio.run(client.aclose())
    assert calls == 2


def test_second_invalid_response_fails_safely():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return answer('{"category":"invented"}')

    client = TriageClient(Settings(max_retries=0), httpx.MockTransport(handler))
    with pytest.raises(TriageUnavailable, match="validation failed"):
        asyncio.run(client.classify("help"))
    asyncio.run(client.aclose())
    assert calls == 2


def test_retries_5xx_but_not_400(monkeypatch):
    sleeps, statuses = [], [503, 200]

    async def no_sleep(delay):
        sleeps.append(delay)

    async def handler(request):
        status = statuses.pop(0)
        return answer(json.dumps(VALID)) if status == 200 else httpx.Response(status, headers={"Retry-After": "0"})

    monkeypatch.setattr("triage.client.asyncio.sleep", no_sleep)
    client = TriageClient(Settings(max_retries=1), httpx.MockTransport(handler))
    asyncio.run(client.classify("crash"))
    assert sleeps == [0.0]
    asyncio.run(client.aclose())

    async def bad_request(request):
        return httpx.Response(400)

    client = TriageClient(Settings(max_retries=3), httpx.MockTransport(bad_request))
    with pytest.raises(TriageUnavailable, match="rejected"):
        asyncio.run(client.classify("crash"))
    asyncio.run(client.aclose())


def test_closed_schema_rejects_extra_and_bad_confidence():
    bad = {**VALID, "confidence": 1.1, "extra": "leak"}
    with pytest.raises(ValueError):
        TriageResult.model_validate(bad)
