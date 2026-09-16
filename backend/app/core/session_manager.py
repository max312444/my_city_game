import time
from typing import Dict, Literal

from fastapi import WebSocket

from app.core.game_clock import GameClock
from app.services.llm_advice_service import generate_advice
from app.services.nation_service import advance_nation, get_or_create_nation

Speed = Literal["paused", "normal", "fast", "fastest"]

ADVICE_INTERVAL_MONTHS = 3
ADVICE_TIME_LIMIT_SECONDS = 15


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.clock = GameClock()
        self.connections: set[WebSocket] = set()
        self.months_since_advice = 0
        self.pending_advice: dict | None = None

    async def broadcast(self, event_type: str, payload: dict):
        dead = set()
        for ws in self.connections:
            try:
                await ws.send_json({"event_type": event_type, "payload": payload})
            except Exception:
                dead.add(ws)
        self.connections -= dead

    async def on_month_advance(self, current_date: dict):
        await self.broadcast("month_advanced", {"current_date": current_date})
        nation = await advance_nation(self.session_id, current_date)
        await self.broadcast("nation_updated", {"nation": nation.to_dict()})

        if self.pending_advice is not None and time.time() >= self.pending_advice["expires_at"]:
            self.pending_advice = None

        if self.pending_advice is None:
            self.months_since_advice += 1
            if self.months_since_advice >= ADVICE_INTERVAL_MONTHS:
                self.months_since_advice = 0
                advice = await generate_advice(nation.to_dict(), current_date)
                advice["created_at"] = time.time()
                advice["expires_at"] = advice["created_at"] + ADVICE_TIME_LIMIT_SECONDS
                self.pending_advice = advice
                await self.broadcast("advice_available", {"advice": self.pending_advice})


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    async def get_or_create(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            session = Session(session_id)
            nation = await get_or_create_nation(session_id)
            session.clock.current_date = {"year": nation.year, "month": nation.month}
            self._sessions[session_id] = session
        return self._sessions[session_id]

    def remove(self, session_id: str):
        self._sessions.pop(session_id, None)

    def all_sessions(self):
        return list(self._sessions.values())


session_manager = SessionManager()
