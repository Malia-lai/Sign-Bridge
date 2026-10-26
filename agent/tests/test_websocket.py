import asyncio
import os

os.environ.setdefault("MOCK_MODE", "true")


def test_ws_ping_pong(client):
    with client.websocket_connect("/ws/sentence") as ws:
        ws.send_text('{"type":"ping"}')
        data = ws.receive_json()
        assert data["type"] == "pong"


def test_ws_sentence(client):
    with client.websocket_connect("/ws/sentence") as ws:
        ws.send_text('{"type":"sentence","words":["me","water","want"]}')
        data = ws.receive_json()
        assert data["type"] == "result"
        assert data["data"]["sentence"]
        assert data["data"]["intent"] == "request"


def test_ws_invalid_json(client):
    with client.websocket_connect("/ws/sentence") as ws:
        ws.send_text("{bad json")
        data = ws.receive_json()
        assert data["type"] == "error"


def test_ws_unknown_type(client):
    with client.websocket_connect("/ws/sentence") as ws:
        ws.send_text('{"type":"foo"}')
        data = ws.receive_json()
        assert data["type"] == "error"


def test_ws_stream(client):
    with client.websocket_connect("/ws/sentence") as ws:
        ws.send_text('{"type":"sentence","words":["hello","world"],"stream":true}')
        msgs = []
        # receive until result
        for _ in range(50):
            m = ws.receive_json()
            msgs.append(m)
            if m.get("type") == "result":
                break
        assert any(m.get("type") == "partial" for m in msgs)
        assert msgs[-1]["type"] == "result"


def test_ws_manager():
    from app.api.websocket import ConnectionManager

    m = ConnectionManager()
    assert m.count() == 0
    # send_json to unknown returns False

    class Dummy:
        pass

    d = Dummy()
    loop = asyncio.new_event_loop()
    try:
        assert loop.run_until_complete(m.send_json(d, {"a": 1})) is False
    finally:
        loop.close()


def test_ws_prefixes(client):
    for prefix in ["/api", "/v1"]:
        with client.websocket_connect(f"{prefix}/ws/sentence") as ws:
            ws.send_text('{"type":"ping"}')
            data = ws.receive_json()
            assert data["type"] == "pong"
