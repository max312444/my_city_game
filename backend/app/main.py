import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from app.core.session_manager import Speed, session_manager
from app.db import init_db
from app.services.nation_service import (
    apply_effects,
    delete_nation,
    get_or_create_nation,
    nation_exists,
)

TICK_SECONDS = 1.0


async def clock_loop():
    while True:
        await asyncio.sleep(TICK_SECONDS)
        for session in session_manager.all_sessions():
            await session.clock.tick(TICK_SECONDS, session.on_month_advance)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(clock_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpeedRequest(BaseModel):
    speed: Speed


class AdviceChoiceRequest(BaseModel):
    advice_id: str
    choice_id: str


class AdviceDismissRequest(BaseModel):
    advice_id: str


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    session = await session_manager.get_or_create(session_id)
    await websocket.accept()
    session.connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        session.connections.discard(websocket)


@app.post("/api/session/{session_id}/clock/speed")
async def set_clock_speed(session_id: str, body: SpeedRequest):
    session = await session_manager.get_or_create(session_id)
    session.clock.speed = body.speed
    return {"speed": session.clock.speed}


@app.get("/api/session/{session_id}/clock")
async def get_clock(session_id: str):
    session = await session_manager.get_or_create(session_id)
    return {"speed": session.clock.speed, "current_date": session.clock.current_date}


@app.get("/api/session/{session_id}/nation")
async def get_nation(session_id: str):
    nation = await get_or_create_nation(session_id)
    return nation.to_dict()


@app.get("/api/session/{session_id}/exists")
async def check_session_exists(session_id: str):
    return {"exists": await nation_exists(session_id)}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    await delete_nation(session_id)
    session_manager.remove(session_id)
    return {"ok": True}


@app.get("/api/session/{session_id}/advice/pending")
async def get_pending_advice(session_id: str):
    session = await session_manager.get_or_create(session_id)
    return {"advice": session.pending_advice}


@app.post("/api/session/{session_id}/advice/choose")
async def choose_advice(session_id: str, body: AdviceChoiceRequest):
    session = await session_manager.get_or_create(session_id)
    if session.pending_advice is None or session.pending_advice["id"] != body.advice_id:
        raise HTTPException(status_code=404, detail="No matching pending advice")

    effects = next(
        (c["effects"] for c in session.pending_advice["choices"] if c["id"] == body.choice_id),
        None,
    )
    if effects is None:
        raise HTTPException(status_code=400, detail="Invalid choice")

    nation = await apply_effects(session_id, effects)
    session.pending_advice = None
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return nation.to_dict()


@app.post("/api/session/{session_id}/advice/dismiss")
async def dismiss_advice(session_id: str, body: AdviceDismissRequest):
    session = await session_manager.get_or_create(session_id)
    if session.pending_advice is not None and session.pending_advice["id"] == body.advice_id:
        session.pending_advice = None
    return {"ok": True}
