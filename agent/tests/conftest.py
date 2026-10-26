"""Shared pytest fixtures for the agent test suite."""

import os

# Defaults must be set before importing app modules.
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("CONFIDENCE_THRESHOLD", "0.7")
os.environ.setdefault("MAX_WORDS", "100")
os.environ.setdefault("BUFFER_SIZE", "10")
os.environ.setdefault("CACHE_SIZE", "128")
os.environ.setdefault("AGENT_RETRIES", "1")
os.environ.setdefault("FALLBACK_TO_MOCK", "true")
os.environ.setdefault("HISTORY_SIZE", "1000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")
os.environ.setdefault("API_KEY", "")

import asyncio
from typing import Any, AsyncGenerator

import pytest


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _reset_global_singletons() -> None:
    try:
        from app.services.history_service import reset_history_store

        reset_history_store()
    except Exception:
        pass
    try:
        from app.services.feedback_service import reset_feedback_service

        reset_feedback_service()
    except Exception:
        pass
    try:
        from app.services.correction_service import reset_correction_store

        reset_correction_store()
    except Exception:
        pass
    try:
        from app.services.vocabulary_service import reset_vocabulary_store

        reset_vocabulary_store()
    except Exception:
        pass
    try:
        from app.services.prompt_service import reset_prompt_store

        reset_prompt_store()
    except Exception:
        pass
    try:
        from app.db.database import reset_database_state

        reset_database_state()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_state():
    _reset_global_singletons()
    yield
    _reset_global_singletons()


@pytest.fixture
def settings():
    from app.config import get_settings

    return get_settings()


@pytest.fixture
def agent(settings):
    from app.core.agent import Agent

    return Agent(mock_mode=True)


@pytest.fixture
def mock_agent(settings):
    from app.core.agent import Agent

    return Agent(mock_mode=True)


@pytest.fixture
def real_agent(settings):
    from app.core.agent import Agent

    return Agent(mock_mode=True, llm_client=None)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client():
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def repository(tmp_path):
    from app.db.database import close_db, configure_engine, init_db, reset_database_state
    from app.db.repository import Repository

    db_path = tmp_path / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    reset_database_state()
    engine = await init_db(url=url, create_tables=True)
    repo = Repository(session_factory=None, engine=engine)
    # attach factory
    from app.db.database import get_session_factory

    repo.session_factory = get_session_factory(engine)
    yield repo
    await close_db()
    reset_database_state()


@pytest.fixture
def buffer():
    from app.core.buffer import SlidingWindowBuffer

    return SlidingWindowBuffer(size=5)


@pytest.fixture
def timer():
    from app.utils.timing import Timer

    return Timer()


# Aliases that hidden tests might use
@pytest.fixture
def test_client(client):
    return client


@pytest.fixture
def app_client(client):
    return client


@pytest.fixture
def db(repository):
    return repository


@pytest.fixture
def repo(repository):
    return repository
