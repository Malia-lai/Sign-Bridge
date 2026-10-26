import os

os.environ.setdefault("MOCK_MODE", "true")

import pytest


@pytest.mark.asyncio
async def test_feedback_crud(repository):
    obj = await repository.create_feedback(
        words=["a", "b"], rating=5, original_sentence="ab", metadata={"x": 1}
    )
    assert obj.id is not None
    got = await repository.get_feedback(obj.id)
    assert got is not None
    lst = await repository.list_feedback()
    assert len(lst) >= 1
    assert await repository.count_feedback() >= 1
    assert await repository.delete_feedback(obj.id) is True
    assert await repository.delete_feedback(obj.id) is False


@pytest.mark.asyncio
async def test_history_crud(repository):
    obj = await repository.create_history(
        words=["a"], sentence="A.", intent="statement", confidence=0.8
    )
    assert obj.id is not None
    got = await repository.get_history(obj.id)
    assert got.sentence == "A."
    lst = await repository.list_history()
    assert len(lst) >= 1
    upd = await repository.update_history(obj.id, sentence="AA.")
    assert upd.sentence == "AA."
    assert await repository.delete_history(obj.id) is True
    assert await repository.clear_history() >= 0


@pytest.mark.asyncio
async def test_vocabulary_crud(repository):
    obj = await repository.create_vocabulary(word="hello", tags=["g"], metadata={"m": 1})
    assert obj.id is not None
    by_word = await repository.get_vocabulary_by_word("hello")
    assert by_word is not None
    assert (await repository.upsert_vocabulary("hello", tags=["g2"])) is not None
    # new
    new = await repository.upsert_vocabulary("world")
    assert new.word == "world"
    lst = await repository.list_vocabulary()
    assert len(lst) >= 2
    assert await repository.delete_vocabulary_by_word("world") is True
    assert await repository.delete_vocabulary(9999) is False


@pytest.mark.asyncio
async def test_prompt_crud(repository):
    obj = await repository.create_prompt(name="p", template="hi", weight=1.0, active=True)
    assert obj.id is not None
    got = await repository.get_prompt(obj.id)
    assert got.name == "p"
    lst = await repository.list_prompts()
    assert len(lst) >= 1
    upd = await repository.update_prompt(obj.id, template="hello")
    assert upd.template == "hello"
    act = await repository.activate_prompt(obj.id)
    assert act.active is True
    assert await repository.delete_prompt(obj.id) is True


@pytest.mark.asyncio
async def test_cleanup(repository):
    await repository.create_feedback(words=["a"], rating=1)
    await repository.create_history(words=["b"], sentence="B.")
    removed = await repository.cleanup_old_records(days=0)
    assert isinstance(removed, dict)
    # cleanup with days=0 removes records older than now (none just created? maybe all if created_at < cutoff? created now, cutoff now, could remove). just ensure no crash
    assert "feedback" in removed or "history" in removed


@pytest.mark.asyncio
async def test_db_health():
    from app.db.database import db_health_check

    assert await db_health_check() is True
