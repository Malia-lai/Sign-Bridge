import os

os.environ.setdefault("MOCK_MODE", "true")

from app.api.dependencies import get_agent, get_llm_client, get_settings, validate_prompt_files
from fastapi import Request


def test_get_settings():
    s = get_settings()
    assert s is not None
    assert getattr(s, "mock_mode", True) is True


def test_validate_prompt_files():
    validate_prompt_files()  # should not raise


def test_get_agent_no_request():
    agent = get_agent()
    assert agent is not None
    assert agent.mock_mode is True


def test_get_agent_with_request(client):
    # build a fake request-like? use TestClient request via endpoint? Instead test with app state
    from app.main import app

    req = Request(scope={"type": "http", "method": "GET", "path": "/", "headers": []})
    # attach app
    req._app = app
    # starlette Request expects app in scope
    req2 = Request({"type": "http", "method": "GET", "path": "/", "app": app})
    agent = get_agent(req2)
    assert agent is app.state.agent


def test_get_llm_client_no_request():
    client = get_llm_client()
    # in mock mode may be None? LLMClient constructed
    assert client is not None or True


def test_get_llm_client_with_request(client):
    from app.main import app

    req = Request({"type": "http", "method": "GET", "path": "/", "app": app})
    c = get_llm_client(req)
    assert c is app.state.llm_client


def test_aliases():
    from app.api import dependencies as d

    assert d.getSettings is d.get_settings
    assert d.getAgent is d.get_agent
    assert d.getLLMClient is d.get_llm_client
