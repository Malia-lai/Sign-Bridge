import os

os.environ.setdefault("MOCK_MODE", "true")

import pytest
from app.core.agent import Agent
from app.schemas.request import SentenceRequest


@pytest.mark.asyncio
async def test_basic_sentence():
    agent = Agent()
    result = await agent.process(SentenceRequest(words=["me", "water", "want"]))
    assert result.sentence
    assert result.intent == "request"
    assert result.fallback is False


@pytest.mark.asyncio
async def test_unknown_word_flagged():
    agent = Agent()
    result = await agent.process(SentenceRequest(words=["me", "water", "zzzz"]))
    assert "zzzz" in result.unknown_words


@pytest.mark.asyncio
async def test_empty_list():
    agent = Agent()
    result = await agent.process(SentenceRequest(words=[]))
    assert result.fallback is False or result.sentence == ""
    assert result.confidence <= 1.0


@pytest.mark.asyncio
async def test_single_word():
    agent = Agent()
    result = await agent.process(["water"])
    assert result.sentence


@pytest.mark.asyncio
async def test_mock_deterministic():
    agent = Agent()
    r1 = await agent.process(SentenceRequest(words=["me", "water", "want"]))
    r2 = await agent.process(SentenceRequest(words=["me", "water", "want"]))
    assert r1.sentence == r2.sentence
    assert r1.intent == r2.intent
