import os

os.environ.setdefault("MOCK_MODE", "true")

from app.services.history_service import HistoryService, get_history_service, reset_history_store


def test_history_add_and_list():
    reset_history_store()
    svc = get_history_service()
    rec = svc.add(words=["me", "water"], sentence="I want water.", intent="request", confidence=0.9)
    assert rec.id >= 1
    assert svc.get(rec.id) is not None
    assert len(svc.list()) == 1


def test_history_from_result(agent):
    reset_history_store()
    svc = get_history_service()
    res = None
    import asyncio

    async def run():
        nonlocal res
        res = await agent.process(["me", "water", "want"])
    asyncio.get_event_loop().run_until_complete(run())
    rec = svc.add(result=res, language="English")
    assert rec.sentence == res.sentence
    assert rec.words == res.raw_words


def test_history_delete_clear():
    reset_history_store()
    svc = get_history_service()
    r1 = svc.add(words=["a"], sentence="A.")
    svc.add(words=["b"], sentence="B.")
    assert svc.delete(r1.id) is True
    assert svc.delete(999) is False
    assert svc.clear() == 1


def test_history_update_stats_export():
    reset_history_store()
    svc = get_history_service()
    rec = svc.add(words=["a"], sentence="A.", fallback=True, emergency=False)
    upd = svc.update(rec.id, sentence="AA.")
    assert upd.sentence == "AA."
    st = svc.stats()
    assert st["total"] == 1
    assert st["fallbacks"] == 1
    data = svc.export()
    assert isinstance(data, list)
    assert svc.import_items([{"words": ["b"], "sentence": "B."}]) == 1


def test_history_reset_and_max_items():
    svc = HistoryService(max_items=2)
    svc.add(words=["a"], sentence="A.")
    svc.add(words=["b"], sentence="B.")
    svc.add(words=["c"], sentence="C.")
    assert len(svc.list()) == 2
    svc.reset()
    assert svc.list() == []
