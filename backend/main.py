"""Z.E.R.O backend entrypoint.

Boots the FastAPI app, initialises the database, starts the scheduler and
voice agent, and exposes the REST + WebSocket API on localhost:8000.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents.reminder_agent import reminder_agent
from agents.voice_agent import voice_agent
from api.routes import router as rest_router
from api.websocket import router as ws_router
from core.config import settings
from core.database import init_db
from core.events import event_bus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
)
logger = logging.getLogger("zero")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Z.E.R.O backend starting up…")
    await init_db()
    reminder_agent.start()
    voice_agent.start(asyncio.get_running_loop())
    await event_bus.publish("system.online", {"message": "ZERO ONLINE"})
    # Mirror the JARVIS-style greeting through TTS if voice is enabled.
    if settings.voice_enabled:
        voice_agent.speak("Z.E.R.O online. How can I serve?")
    logger.info("Z.E.R.O online at http://%s:%s", settings.host, settings.port)
    try:
        yield
    finally:
        logger.info("Z.E.R.O shutting down…")
        voice_agent.stop()
        reminder_agent.shutdown()


app = FastAPI(title="Z.E.R.O", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-only desktop app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rest_router)
app.include_router(ws_router)


@app.get("/")
async def root() -> dict:
    return {"name": "Z.E.R.O", "tagline": "Zero-latency Executive Reasoning Operator",
            "status": "online"}


def run() -> None:
    uvicorn.run("main:app", host=settings.host, port=settings.port,
                reload=settings.debug, log_level="info")


if __name__ == "__main__":
    run()
