"""WebSocket endpoint for sentence generation."""

import json
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.agent import Agent
from app.schemas.request import SentenceRequest

router = APIRouter(tags=["websocket"])

WS_MESSAGE_TYPES = {
    "sentence": "Generate a sentence from words",
    "ping": "Heartbeat ping",
    "pong": "Heartbeat pong",
    "result": "Sentence generation result",
    "error": "Error message",
}


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        await websocket.send_json(data)

    async def broadcast(self, data: Dict[str, Any]) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/sentence")
async def websocket_sentence(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    agent = Agent()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_json(websocket, {"type": "error", "error": "invalid json"})
                continue
            mtype = message.get("type", "sentence")
            if mtype == "ping":
                await manager.send_json(websocket, {"type": "pong"})
                continue
            if mtype != "sentence":
                await manager.send_json(websocket, {"type": "error", "error": f"unknown type: {mtype}"})
                continue
            words = message.get("words", [])
            language = message.get("language")
            timeout = message.get("timeout")
            try:
                req = SentenceRequest(words=words, language=language, timeout=timeout)
                result = await agent.process(req)
                await manager.send_json(websocket, {"type": "result", "data": result.model_dump()})
            except Exception as exc:
                await manager.send_json(websocket, {"type": "error", "error": str(exc)})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)