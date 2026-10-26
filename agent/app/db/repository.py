"""Async CRUD repository for persisted entities."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Optional, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session_factory
from app.db.models import Feedback, History, Prompt, Vocabulary


class Repository:
    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        session_factory: Any = None,
        engine: Any = None,
        **kwargs: Any,
    ) -> None:
        self.session = session
        self.session_factory = session_factory
        self.engine = engine

    @asynccontextmanager
    async def _session(self) -> AsyncGenerator[AsyncSession, None]:
        if self.session is not None:
            yield self.session
            return
        factory = self.session_factory
        if factory is None:
            factory = get_session_factory(self.engine)
        async with factory() as session:
            yield session

    # ------------------------------------------------------------------ #
    # Feedback
    # ------------------------------------------------------------------ #
    async def create_feedback(self, **kwargs: Any) -> Feedback:
        async with self._session() as session:
            obj = Feedback(**self._filter(Feedback, kwargs))
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def add_feedback(self, **kwargs: Any) -> Feedback:
        return await self.create_feedback(**kwargs)

    async def insert_feedback(self, **kwargs: Any) -> Feedback:
        return await self.create_feedback(**kwargs)

    async def get_feedback(self, item_id: Any) -> Optional[Feedback]:
        async with self._session() as session:
            return await session.get(Feedback, item_id)

    async def get_feedback_by_id(self, item_id: Any) -> Optional[Feedback]:
        return await self.get_feedback(item_id)

    async def list_feedback(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Sequence[Feedback]:
        async with self._session() as session:
            stmt = select(Feedback).order_by(Feedback.id)
            if request_id is not None:
                stmt = stmt.where(Feedback.request_id == request_id)
            if offset:
                stmt = stmt.offset(int(offset))
            if limit is not None:
                stmt = stmt.limit(int(limit))
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_feedbacks(self, *a, **k):
        return await self.list_feedback(*a, **k)

    async def all_feedback(self, *a, **k):
        return await self.list_feedback(*a, **k)

    async def delete_feedback(self, item_id: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(Feedback, item_id)
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True

    async def remove_feedback(self, *a, **k):
        return await self.delete_feedback(*a, **k)

    async def count_feedback(self) -> int:
        async with self._session() as session:
            result = await session.execute(select(Feedback))
            return len(result.scalars().all())

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    async def create_history(self, **kwargs: Any) -> History:
        async with self._session() as session:
            obj = History(**self._filter(History, kwargs))
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def add_history(self, **kwargs: Any) -> History:
        return await self.create_history(**kwargs)

    async def insert_history(self, **kwargs: Any) -> History:
        return await self.create_history(**kwargs)

    async def get_history(self, item_id: Any) -> Optional[History]:
        async with self._session() as session:
            return await session.get(History, item_id)

    async def list_history(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        request_id: Optional[str] = None,
        **kwargs: Any,
    ) -> Sequence[History]:
        async with self._session() as session:
            stmt = select(History).order_by(History.id)
            if request_id is not None:
                stmt = stmt.where(History.request_id == request_id)
            if offset:
                stmt = stmt.offset(int(offset))
            if limit is not None:
                stmt = stmt.limit(int(limit))
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_histories(self, *a, **k):
        return await self.list_history(*a, **k)

    async def all_history(self, *a, **k):
        return await self.list_history(*a, **k)

    async def update_history(self, item_id: Any, **kwargs: Any) -> Optional[History]:
        async with self._session() as session:
            obj = await session.get(History, item_id)
            if obj is None:
                return None
            for key, value in self._filter(History, kwargs).items():
                setattr(obj, key, value)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def delete_history(self, item_id: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(History, item_id)
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True

    async def remove_history(self, *a, **k):
        return await self.delete_history(*a, **k)

    async def clear_history(self) -> int:
        async with self._session() as session:
            result = await session.execute(delete(History))
            await session.commit()
            return result.rowcount or 0

    async def count_history(self) -> int:
        async with self._session() as session:
            result = await session.execute(select(History))
            return len(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Vocabulary
    # ------------------------------------------------------------------ #
    async def create_vocabulary(self, **kwargs: Any) -> Vocabulary:
        async with self._session() as session:
            obj = Vocabulary(**self._filter(Vocabulary, kwargs))
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def add_vocabulary(self, **kwargs: Any) -> Vocabulary:
        return await self.create_vocabulary(**kwargs)

    async def upsert_vocabulary(self, word: str, **kwargs: Any) -> Vocabulary:
        existing = await self.get_vocabulary_by_word(word)
        if existing is not None:
            return await self.update_vocabulary(existing.id, word=word, **kwargs) or existing
        kwargs.setdefault("word", word)
        return await self.create_vocabulary(**kwargs)

    async def get_vocabulary(self, item_id: Any) -> Optional[Vocabulary]:
        async with self._session() as session:
            return await session.get(Vocabulary, item_id)

    async def get_vocabulary_by_word(self, word: str) -> Optional[Vocabulary]:
        async with self._session() as session:
            stmt = select(Vocabulary).where(Vocabulary.word == word)
            result = await session.execute(stmt)
            return result.scalars().first()

    async def get_vocabulary_by_id(self, item_id: Any) -> Optional[Vocabulary]:
        return await self.get_vocabulary(item_id)

    async def list_vocabulary(
        self, limit: Optional[int] = None, offset: int = 0, **kwargs: Any
    ) -> Sequence[Vocabulary]:
        async with self._session() as session:
            stmt = select(Vocabulary).order_by(Vocabulary.id)
            if offset:
                stmt = stmt.offset(int(offset))
            if limit is not None:
                stmt = stmt.limit(int(limit))
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_vocabularies(self, *a, **k):
        return await self.list_vocabulary(*a, **k)

    async def all_vocabulary(self, *a, **k):
        return await self.list_vocabulary(*a, **k)

    async def update_vocabulary(self, item_id: Any, **kwargs: Any) -> Optional[Vocabulary]:
        async with self._session() as session:
            obj = await session.get(Vocabulary, item_id)
            if obj is None:
                return None
            for key, value in self._filter(Vocabulary, kwargs).items():
                setattr(obj, key, value)
            obj.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def delete_vocabulary(self, item_id: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(Vocabulary, item_id)
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True

    async def delete_vocabulary_by_word(self, word: str) -> bool:
        obj = await self.get_vocabulary_by_word(word)
        if obj is None:
            return False
        return await self.delete_vocabulary(obj.id)

    async def remove_vocabulary(self, *a, **k):
        return await self.delete_vocabulary(*a, **k)

    async def count_vocabulary(self) -> int:
        async with self._session() as session:
            result = await session.execute(select(Vocabulary))
            return len(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Prompts
    # ------------------------------------------------------------------ #
    async def create_prompt(self, **kwargs: Any) -> Prompt:
        async with self._session() as session:
            obj = Prompt(**self._filter(Prompt, kwargs))
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def add_prompt(self, **kwargs: Any) -> Prompt:
        return await self.create_prompt(**kwargs)

    async def get_prompt(self, item_id: Any) -> Optional[Prompt]:
        async with self._session() as session:
            return await session.get(Prompt, item_id)

    async def list_prompts(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        active: Optional[bool] = None,
        **kwargs: Any,
    ) -> Sequence[Prompt]:
        async with self._session() as session:
            stmt = select(Prompt).order_by(Prompt.id)
            if active is not None:
                stmt = stmt.where(Prompt.active == bool(active))
            if offset:
                stmt = stmt.offset(int(offset))
            if limit is not None:
                stmt = stmt.limit(int(limit))
            result = await session.execute(stmt)
            return result.scalars().all()

    async def list_prompt(self, *a, **k):
        return await self.list_prompts(*a, **k)

    async def all_prompts(self, *a, **k):
        return await self.list_prompts(*a, **k)

    async def update_prompt(self, item_id: Any, **kwargs: Any) -> Optional[Prompt]:
        async with self._session() as session:
            obj = await session.get(Prompt, item_id)
            if obj is None:
                return None
            for key, value in self._filter(Prompt, kwargs).items():
                setattr(obj, key, value)
            obj.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def activate_prompt(self, item_id: Any) -> Optional[Prompt]:
        # deactivate all, activate target
        async with self._session() as session:
            await session.execute(update(Prompt).values(active=False))
            obj = await session.get(Prompt, item_id)
            if obj is None:
                await session.commit()
                return None
            obj.active = True
            obj.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(obj)
            return obj

    async def delete_prompt(self, item_id: Any) -> bool:
        async with self._session() as session:
            obj = await session.get(Prompt, item_id)
            if obj is None:
                return False
            await session.delete(obj)
            await session.commit()
            return True

    async def remove_prompt(self, *a, **k):
        return await self.delete_prompt(*a, **k)

    async def count_prompts(self) -> int:
        async with self._session() as session:
            result = await session.execute(select(Prompt))
            return len(result.scalars().all())

    # ------------------------------------------------------------------ #
    # Retention / cleanup
    # ------------------------------------------------------------------ #
    async def cleanup_old_records(
        self, days: Optional[int] = None, tables: Optional[list] = None
    ) -> dict:
        if days is None:
            try:
                from app.config import get_settings

                days = int(getattr(get_settings(), "data_retention_days", 30))
            except Exception:
                days = 30
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
        tables = tables or ["feedback", "history"]
        removed = {}
        async with self._session() as session:
            if "feedback" in tables:
                result = await session.execute(delete(Feedback).where(Feedback.created_at < cutoff))
                removed["feedback"] = result.rowcount or 0
            if "history" in tables:
                result = await session.execute(delete(History).where(History.created_at < cutoff))
                removed["history"] = result.rowcount or 0
            await session.commit()
        return removed

    async def cleanup(self, *a, **k):
        return await self.cleanup_old_records(*a, **k)

    async def retention_cleanup(self, *a, **k):
        return await self.cleanup_old_records(*a, **k)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _filter(model: Any, kwargs: dict) -> dict:
        allowed = set()
        try:
            allowed = set(model.__table__.columns.keys())
        except Exception:
            allowed = set(kwargs.keys())
        out = {}
        for key, value in (kwargs or {}).items():
            if key in allowed:
                out[key] = value
        # map metadata -> meta if provided
        if "metadata" in kwargs and "meta" in allowed:
            out["meta"] = kwargs.get("metadata")
        return out


# Entity-specific aliases
FeedbackRepository = Repository
HistoryRepository = Repository
VocabularyRepository = Repository
PromptRepository = Repository
DBRepository = Repository
CrudRepository = Repository


# module-level convenience functions using global session factory
async def get_repository() -> Repository:
    return Repository()


async def create_tables() -> None:
    from app.db.database import init_db

    await init_db()


# aliases
RepositoryFactory = Repository
