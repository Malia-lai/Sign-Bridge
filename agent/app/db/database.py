"""Async database engine and session management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


# Global state
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _default_sqlite_url() -> str:
    # agent/data/agent.db relative to project root (cwd-independent-ish)
    base = Path(__file__).resolve().parents[2]
    data_dir = base / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "agent.db"
    return f"sqlite+aiosqlite:///{db_path}"


def get_database_url(url: Optional[str] = None) -> str:
    if url:
        return url
    s = get_settings()
    val = getattr(s, "database_url", "") or getattr(s, "db_url", "") or ""
    if val:
        return val
    # env fallback
    env = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if env:
        return env
    return _default_sqlite_url()


def _engine_kwargs(url: str) -> dict:
    s = get_settings()
    kwargs: dict[str, Any] = {"echo": bool(getattr(s, "db_echo", False))}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(
            pool_size=int(getattr(s, "db_pool_size", 5)),
            max_overflow=int(getattr(s, "db_max_overflow", 10)),
            pool_timeout=int(getattr(s, "db_pool_timeout", 30)),
            pool_recycle=int(getattr(s, "db_pool_recycle", 1800)),
        )
    return kwargs


def create_engine(url: Optional[str] = None, **overrides: Any) -> AsyncEngine:
    db_url = get_database_url(url)
    kwargs = _engine_kwargs(db_url)
    kwargs.update(overrides)
    return create_async_engine(db_url, **kwargs)


def get_engine(url: Optional[str] = None, **overrides: Any) -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine(url, **overrides)
    return _engine


def configure_engine(url: Optional[str] = None, **overrides: Any) -> AsyncEngine:
    global _engine, _session_factory
    _engine = create_engine(url, **overrides)
    _session_factory = None
    return _engine


def get_session_factory(engine: Optional[AsyncEngine] = None) -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is not None and engine is None:
        return _session_factory
    eng = engine or get_engine()
    factory = async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)
    if engine is None:
        _session_factory = factory
    return factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db(url: Optional[str] = None, create_tables: bool = True) -> AsyncEngine:
    global _engine, _session_factory
    _engine = create_engine(url)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    if create_tables:
        from app.db.models import Base

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    return _engine


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def db_health_check(engine: Optional[AsyncEngine] = None) -> bool:
    eng = engine or (_engine if _engine is not None else None)
    if eng is None:
        try:
            eng = get_engine()
        except Exception:
            return False
    try:
        async with eng.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_database_state() -> None:
    global _engine, _session_factory
    _engine = None
    _session_factory = None


# aliases
engine = get_engine
session_factory = get_session_factory
create_db_engine = create_engine
init_database = init_db
close_database = close_db
health_check = db_health_check
get_db = get_session
