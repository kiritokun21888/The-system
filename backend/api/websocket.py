"""WebSocket endpoint — real-time event stream to the frontend.

Clients connect to ``/ws``; the server replays recent events, then forwards
every new event from the bus. Inbound messages let the UI drive the brain and
agents over the same socket the dashboard already uses.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.events import event_bus

logger = logging.getLogger("zero.ws")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await event_bus.subscribe()

    # Replay recent history so a freshly-connected client has context.
    for event in event_bus.recent(limit=30):
        await websocket.send_text(json.dumps(event, default=str))
    await event_bus.publish("system.online", {"message": "ZERO ONLINE"})

    async def pump_outbound() -> None:
        while True:
            event = await queue.get()
            await websocket.send_text(json.dumps(event, default=str))

    async def pump_inbound() -> None:
        from agents.background_agent import background_agent_manager
        from agents.voice_agent import voice_agent
        from core.brain import brain

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            action = msg.get("action")
            data = msg.get("data", {})
            if action == "chat":
                result = await brain.think(data.get("message", ""))
                if data.get("speak"):
                    voice_agent.speak(result.get("reply", ""))
            elif action == "run_agent":
                await background_agent_manager.spawn(
                    data.get("agent_type", "research"), data.get("input", "")
                )
            elif action == "speak":
                voice_agent.speak(data.get("text", ""))
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong", "payload": {}}))

    outbound = asyncio.create_task(pump_outbound())
    inbound = asyncio.create_task(pump_inbound())
    try:
        await asyncio.gather(outbound, inbound)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as exc:  # noqa: BLE001
        logger.debug("WebSocket closed: %s", exc)
    finally:
        outbound.cancel()
        inbound.cancel()
        await event_bus.unsubscribe(queue)
