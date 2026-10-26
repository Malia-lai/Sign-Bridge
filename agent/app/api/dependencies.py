"""FastAPI dependency providers for the agent service."""

from pathlib import Path
from typing import Optional

from fastapi import Request

from app.config import Settings
from app.config import get_settings as _config_get_settings
from app.config import settings as _settings
from app.core.agent import PROMPTS_DIR, Agent
from app.llm.client import LLMClient


def get_settings() -> Settings:
    # Re-read env-derived settings? Keep singleton but allow override via env at import.
    try:
        return _config_get_settings()
    except Exception:
        return _settings


def _prompt_paths() -> list[Path]:
    return [
        PROMPTS_DIR / "system_prompt.txt",
        PROMPTS_DIR / "vocabulary.json",
        PROMPTS_DIR / "examples.json",
    ]


def validate_prompt_files() -> None:
    """Fail fast if required prompt files are missing."""
    missing = [str(p) for p in _prompt_paths() if not p.exists()]
    if missing:
        raise RuntimeError(f"Missing required prompt files: {', '.join(missing)}")


def validate_startup() -> None:
    validate_prompt_files()


def get_llm_client(request: Optional[Request] = None) -> LLMClient:
    if request is not None:
        client = getattr(getattr(request, "app", None), "state", None)
        if client is not None:
            c = getattr(client, "llm_client", None)
            if c is not None:
                return c
    # build from provider settings
    from app.llm.client import LLMClient as _LLMClient

    return _LLMClient()


def get_agent(request: Optional[Request] = None) -> Agent:
    if request is not None:
        app = getattr(request, "app", None)
        state = getattr(app, "state", None)
        if state is not None:
            ag = getattr(state, "agent", None)
            if ag is not None:
                return ag
    s = get_settings()
    agent = Agent(mock_mode=s.mock_mode)
    # attach shared services if available
    try:
        from app.services.correction_service import get_correction_service
        from app.services.history_service import get_history_service
        from app.services.prompt_service import get_prompt_service
        from app.services.vocabulary_service import get_vocabulary_service

        agent.history_service = get_history_service()
        agent.correction_service = get_correction_service()
        agent.vocabulary_service = get_vocabulary_service()
        agent.prompt_service = get_prompt_service()
        from app.services.feedback_service import get_feedback_service

        agent.feedback_service = get_feedback_service()
        for svc in (
            agent.history_service,
            agent.correction_service,
            agent.vocabulary_service,
            agent.prompt_service,
        ):
            try:
                svc.agent = agent
            except Exception:
                pass
    except Exception:
        pass
    return agent


# aliases
getSettings = get_settings
getAgent = get_agent
getLLMClient = get_llm_client
get_llm = get_llm_client
