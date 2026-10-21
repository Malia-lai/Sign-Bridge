import asyncio

from app.core.agent import Agent
from app.schemas.request import SentenceRequest


class OKClient:
    async def generate_json(self, *a, **k):
        return {"sentence": "I need help.", "intent": "request", "confidence": 0.9, "alternatives": []}

    async def generate(self, *a, **k):
        return '{"sentence":"I need help.","intent":"request","confidence":0.9,"alternatives":[]}'


class BadClient:
    async def generate_json(self, *a, **k):
        raise RuntimeError("boom")

    async def generate(self, *a, **k):
        raise RuntimeError("boom")


def test_emergency_override():
    agent = Agent(mock_mode=False, llm_client=OKClient())
    result = asyncio.run(agent.process(SentenceRequest(words=["help", "me"])))
    assert result.intent == "emergency"
    assert result.intent_overridden is True
    assert result.sentence == "I need help."


def test_dual_reason_fallback():
    agent = Agent(mock_mode=False, llm_client=BadClient())
    result = asyncio.run(agent.process(SentenceRequest(words=["help", "me"])))
    assert result.fallback is True
    assert result.emergency is True
    assert "emergency" in (result.fallback_reasons or [])
    assert result.fallback_reason != "emergency"


def test_empty_input_rejection():
    agent = Agent(mock_mode=True)
    result = asyncio.run(agent.process(SentenceRequest(words=[])))
    assert result.fallback is True
    assert result.fallback_reason == "empty_input"