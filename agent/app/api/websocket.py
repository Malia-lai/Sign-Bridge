"""WebSocket endpoint for sentence generation."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.agent import Agent
from app.schemas.request import SentenceRequest
from app.config import get_settings

router = APIRouter(tags=["websocket"])

WS_MESSAGE_TYPES = {
    "sentence": "Generate a sentence from words",
    "ping": "Heartbeat ping",
    "pong": "Heartbeat pong",
    "result": "Sentence generation result",
    "partial": "Partial sentence update",
    "error": "Error message",
}


class ConnectionManager:
    """Manages active WebSocket connections with backpressure handling."""

    def __init__(self, send_timeout: float = 5.0, max_queue: int = 100) -> None:
        self.active_connections: List[WebSocket] = []
        self._metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self.send_timeout = float(send_timeout)
        self.max_queue = int(max_queue)

    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None, **metadata: Any) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        self._metadata[websocket] = {"client_id": client_id, "connected_at": time.time(), **metadata}

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self._metadata.pop(websocket, None)

    async def send_json(self, websocket: WebSocket, data: Dict[str, Any]) -> bool:
        """Send JSON with backpressure handling. Returns False on failure."""
        if websocket not in self.active_connections:
            return False
        try:
            await asyncio.wait_for(websocket.send_json(data), timeout=self.send_timeout)
            return True
        except Exception:
            self.disconnect(websocket)
            try:
                await websocket.close()
            except Exception:
                pass
            return False

    async def send_text(self, websocket: WebSocket, text: str) -> bool:
        if websocket not in self.active_connections:
            return False
        try:
            await asyncio.wait_for(websocket.send_text(text), timeout=self.send_timeout)
            return True
        except Exception:
            self.disconnect(websocket)
            return False

    async def broadcast(self, data: Dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            await self.send_json(connection, data)

    def count(self) -> int:
        return len(self.active_connections)

    def metadata(self, websocket: WebSocket) -> Dict[str, Any]:
        return dict(self._metadata.get(websocket, {}))


manager = ConnectionManager()


@router.websocket("/ws/sentence")
async def websocket_sentence(websocket: WebSocket) -> None:
    settings = get_settings()
    # WebSocket auth
    if getattr(settings, "api_key", ""):
        token = (
            websocket.query_params.get("token")
            or websocket.query_params.get("api_key")
            or websocket.headers.get("x-api-key")
        )
        if token != settings.api_key:
            await websocket.close(code=1008, reason="unauthorized")
            return

    await manager.connect(websocket)
    agent = Agent()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                ok = await manager.send_json(websocket, {"type": "error", "error": "invalid json"})
                if not ok:
                    break
                continue
            mtype = message.get("type", "sentence")
            if mtype == "ping":
                ok = await manager.send_json(websocket, {"type": "pong"})
                if not ok:
                    break
                continue
            if mtype == "pong":
                continue
            if mtype != "sentence":
                ok = await manager.send_json(websocket, {"type": "error", "error": f"unknown type: {mtype}"})
                if not ok:
                    break
                continue

            words = message.get("words", [])
            language = message.get("language")
            timeout = message.get("timeout")
            stream = bool(message.get("stream", False))
            try:
                req = SentenceRequest(words=words, language=language, timeout=timeout)
                if stream:
                    async for partial in agent.process_stream(req):
                        ok = await manager.send_json(websocket, partial)
                        if not ok:
                            break
                else:
                    result = await agent.process(req)
                    ok = await manager.send_json(websocket, {"type": "result", "data": result.model_dump()})
                    if not ok:
                        break
            except Exception as exc:
                ok = await manager.send_json(websocket, {"type": "error", "error": str(exc)})
                if not ok:
                    break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# aliases
WebSocketManager = ConnectionManager
ConnectionManagerAlias = ConnectionManager