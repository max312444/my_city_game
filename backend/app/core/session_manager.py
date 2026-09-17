import random
from typing import Dict, Literal

from fastapi import WebSocket

from app.core.game_clock import GameClock
from app.services import city_service, map_service, territory_service
from app.services.diplomacy_service import (
    RIVAL_EXPANSION_CHANCE_CAP,
    RIVAL_EXPANSION_CHANCE_DIVISOR,
    advance_rivals,
    advance_world,
    mark_defeated,
)
from app.services.disaster_service import maybe_trigger_event
from app.services.great_person_service import maybe_spawn_great_person
from app.services.llm_advice_service import generate_advice
from app.services.nation_service import (
    advance_nation,
    apply_random_event,
    get_or_create_nation,
    sync_land_capacity,
)
from app.services.tech_service import advance_research

Speed = Literal["paused", "normal", "fast", "fastest"]

ADVICE_INTERVAL_MONTHS = 3
ADVICE_TIME_LIMIT_SECONDS = 15


async def _resolve_territory_changes(session_id: str, rivals: list[dict], war_outcomes: list[tuple]):
    """Turns this month's rival economies + war results into actual tile ownership
    changes. Lives here (not in diplomacy_service) because it needs both map_service
    and territory_service, and diplomacy_service must stay independent of both — see
    the docstring on diplomacy_service.advance_rivals for why.

    Returns (extra_reports, territory_changed)."""
    extra_reports = []
    territory_changed = False

    map_data = await map_service.get_or_create_map(session_id)
    protected_tiles = {(map_data["capital"]["x"], map_data["capital"]["y"])}
    protected_tiles.update((rc["x"], rc["y"]) for rc in map_data["rival_capitals"])

    for rival in rivals:
        chance = min(RIVAL_EXPANSION_CHANCE_CAP, rival["economy"] / RIVAL_EXPANSION_CHANCE_DIVISOR)
        if random.random() < chance:
            claimed = await territory_service.expand_rival_territory(
                session_id, rival["rival_id"], map_data["tiles"]
            )
            if claimed is not None:
                territory_changed = True

    for winner, loser, rival_name in war_outcomes:
        # Rivals can be wiped out entirely; the player never can (see capture_tile's
        # docstring) — so elimination is only allowed when the loser is a rival.
        captured = await territory_service.capture_tile(
            session_id, winner, loser, protected_tiles, allow_elimination=(loser != "player")
        )
        if captured is not None:
            territory_changed = True
            if captured.get("eliminated"):
                await mark_defeated(session_id, loser)
                extra_reports.append(f"{rival_name}이(가) 멸망했습니다!")
            elif winner == "player":
                extra_reports.append(f"{rival_name}의 국경 지역을 점령했습니다.")
            else:
                extra_reports.append(f"{rival_name}에게 국경 지역을 빼앗겼습니다.")

    if territory_changed:
        # Capital captures never happen to the player, but ordinary border tiles can
        # still change hands either way — keep the population ceiling honest either way.
        player_tiles = await territory_service.get_owned_tiles(session_id)
        await sync_land_capacity(session_id, len(player_tiles))

    return extra_reports, territory_changed


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

        owned_tiles = await territory_service.get_owned_tiles(self.session_id)
        cities = await city_service.get_cities(self.session_id)
        nation = await advance_nation(
            self.session_id, current_date, owned_tile_count=len(owned_tiles), city_count=len(cities)
        )
        await self.broadcast("nation_updated", {"nation": nation.to_dict()})

        nation, completed_tech = await advance_research(self.session_id)
        if completed_tech is not None:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("tech_completed", {"tech_id": completed_tech})

        event = maybe_trigger_event()
        if event is not None:
            nation = await apply_random_event(self.session_id, event)
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("random_event", {"event": event})

        nation, great_person = await maybe_spawn_great_person(self.session_id, nation, current_date)
        if great_person is not None:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast(
                "great_person_appeared", {"person": great_person, "current_date": current_date}
            )

        nation, rivals, war_reports, war_outcomes = await advance_rivals(self.session_id, current_date)
        await self.broadcast("rivals_updated", {"rivals": rivals})

        extra_reports, territory_changed = await _resolve_territory_changes(
            self.session_id, rivals, war_outcomes
        )
        world_news = await advance_world(self.session_id)
        war_reports = war_reports + extra_reports + world_news

        if war_reports:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("war_report", {"reports": war_reports})
        if territory_changed:
            all_tiles = await territory_service.get_all_tiles(self.session_id)
            await self.broadcast("territory_updated", {"all": all_tiles})

        if self.pending_advice is None:
            self.months_since_advice += 1
            if self.months_since_advice >= ADVICE_INTERVAL_MONTHS:
                self.months_since_advice = 0
                advice = await generate_advice(nation.to_dict(), current_date)
                advice["seconds_left"] = ADVICE_TIME_LIMIT_SECONDS
                advice["total_seconds"] = ADVICE_TIME_LIMIT_SECONDS
                self.pending_advice = advice
                await self.broadcast("advice_available", {"advice": self.pending_advice})

    async def tick_advice(self, delta_seconds: float):
        """Advance the advice decision timer, but only while the game clock is actually running."""
        if self.pending_advice is None or self.clock.speed == "paused":
            return
        self.pending_advice["seconds_left"] -= delta_seconds
        if self.pending_advice["seconds_left"] <= 0:
            self.pending_advice = None
            await self.broadcast("advice_available", {"advice": None})


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
