import random
from typing import Dict, Literal

from fastapi import WebSocket

from app.core.game_clock import GameClock
from app.data.rivals import PERSONALITY_TRAITS
from app.services import city_service, map_service, territory_service
from app.services.map_service import RESOURCE_TYPES
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
from app.services import log_service
from app.services.nation_service import (
    advance_nation,
    apply_random_event,
    get_or_create_nation,
    sync_land_capacity,
)
from app.services.tech_service import TECH_BY_ID, advance_research
from app.services.building_service import BUILDING_BY_ID, advance_building
from app.services.wonder_service import WONDER_BY_ID, advance_rival_wonders, advance_wonder
from app.services.trade_service import advance_trade

Speed = Literal["paused", "normal", "fast", "fastest"]

ADVICE_INTERVAL_MONTHS = 3
ADVICE_TIME_LIMIT_SECONDS = 15

# The player's territory now also grows on its own in the background, same formula as
# a rival's organic expansion — just a bit more conservative (x0.6) so buying toward a
# specific tile (a resource, a chokepoint) still feels like a meaningful choice instead
# of the auto-growth beating you to everything nearby.
PLAYER_AUTO_EXPANSION_MULTIPLIER = 0.6


def _trait(personality: str, key: str) -> float:
    return PERSONALITY_TRAITS.get(personality, {}).get(key, 1.0)


def _compute_resource_bonus(map_data: dict, player_cities: list[dict]) -> dict:
    """Sums the bonuses of every resource tile within 1 tile of the capital or any
    founded player city — this is what makes *where* a city gets founded matter
    (a city next to a gold_mine tile pays off every month, one next to nothing doesn't).
    Rivals don't get this (their stats are a single aggregate number, not tied to any
    particular tile), matching the existing simplification for rival mechanics."""
    resources = map_data.get("resources")
    if not resources:
        return {}

    centers = [(map_data["capital"]["x"], map_data["capital"]["y"])]
    centers += [(c["x"], c["y"]) for c in player_cities]

    bonus: dict[str, float] = {}
    for res in resources:
        rx, ry = res["x"], res["y"]
        if any(max(abs(rx - cx), abs(ry - cy)) <= 1 for cx, cy in centers):
            for stat, value in RESOURCE_TYPES[res["type"]]["bonus"].items():
                bonus[stat] = bonus.get(stat, 0.0) + value
    return bonus


async def _resolve_territory_changes(
    session_id: str,
    rivals: list[dict],
    war_outcomes: list[tuple],
    world_war_outcomes: list[tuple],
    current_date: dict,
    player_economy: float = 0.0,
    siege_targets: dict[str, tuple[int, int]] | None = None,
):
    """Turns this month's rival economies + war results (player-vs-rival AND, now,
    rival-vs-rival) into actual tile ownership (and city) changes. Lives here (not in
    diplomacy_service) because it needs both map_service and territory_service, and
    diplomacy_service must stay independent of both — see the docstring on
    diplomacy_service.advance_rivals for why.

    `siege_targets` is the caller's own dict (Session.siege_targets) — mutated in
    place (the entry is popped once its exact tile is captured) instead of returned,
    since dicts are passed by reference and there's no other reason to hand back a
    whole new return value just for this.

    Returns (extra_reports, territory_changed, cities_changed)."""
    siege_targets = siege_targets if siege_targets is not None else {}
    extra_reports = []
    territory_changed = False
    cities_changed = False

    map_data = await map_service.get_or_create_map(session_id)
    protected_tiles = {(map_data["capital"]["x"], map_data["capital"]["y"])}
    protected_tiles.update((rc["x"], rc["y"]) for rc in map_data["rival_capitals"])

    # The player no longer has to manually buy every single tile — a small background
    # trickle of automatic growth now happens too (advisor-run nation, not a player-run
    # one), on top of whatever they buy deliberately.
    player_chance = min(
        RIVAL_EXPANSION_CHANCE_CAP, player_economy / RIVAL_EXPANSION_CHANCE_DIVISOR * PLAYER_AUTO_EXPANSION_MULTIPLIER
    )
    if random.random() < player_chance:
        claimed = await territory_service.expand_rival_territory(session_id, "player", map_data["tiles"])
        if claimed is not None:
            territory_changed = True

    for rival in rivals:
        expansion_mult = _trait(rival.get("personality"), "expansion_multiplier")
        chance = min(
            RIVAL_EXPANSION_CHANCE_CAP, rival["economy"] / RIVAL_EXPANSION_CHANCE_DIVISOR * expansion_mult
        )
        if random.random() < chance:
            claimed = await territory_service.expand_rival_territory(
                session_id, rival["rival_id"], map_data["tiles"]
            )
            if claimed is not None:
                territory_changed = True

    for winner, loser, rival_name in war_outcomes:
        # Rivals can be wiped out entirely; the player never can (see capture_tile's
        # docstring) — so elimination is only allowed when the loser is a rival.
        preferred = siege_targets.get(loser) if winner == "player" else None
        captured = await territory_service.capture_tile(
            session_id, winner, loser, protected_tiles, allow_elimination=(loser != "player"), preferred_tile=preferred
        )
        if captured is not None:
            territory_changed = True
            captured_xy = (captured["x"], captured["y"])
            if preferred is not None and captured_xy == preferred:
                siege_targets.pop(loser, None)  # objective reached — clear the focus-fire order

            # A founded city (never a capital — those aren't rows in this table, and
            # stay protected regardless) sitting on the captured tile changes hands too.
            transferred_city = await city_service.transfer_city_at(session_id, captured["x"], captured["y"], winner)
            if transferred_city is not None:
                cities_changed = True

            if captured.get("eliminated"):
                await mark_defeated(session_id, loser)
                extra_reports.append(f"{rival_name}이(가) 멸망했습니다!")
            elif transferred_city is not None:
                if winner == "player":
                    extra_reports.append(f"{rival_name}의 도시 '{transferred_city['name']}'을(를) 점령했습니다!")
                else:
                    extra_reports.append(f"{rival_name}에게 도시 '{transferred_city['name']}'을(를) 빼앗겼습니다!")
            elif winner == "player":
                extra_reports.append(f"{rival_name}의 국경 지역을 점령했습니다.")
            else:
                extra_reports.append(f"{rival_name}에게 국경 지역을 빼앗겼습니다.")

    for winner_id, loser_id, winner_name, loser_name in world_war_outcomes:
        # Neither side is ever the player here, so elimination is always on the table
        # — two rivals can fight to the finish entirely on their own.
        captured = await territory_service.capture_tile(
            session_id, winner_id, loser_id, protected_tiles, allow_elimination=True
        )
        if captured is not None:
            territory_changed = True
            transferred_city = await city_service.transfer_city_at(
                session_id, captured["x"], captured["y"], winner_id
            )
            if transferred_city is not None:
                cities_changed = True

            if captured.get("eliminated"):
                await mark_defeated(session_id, loser_id)
                extra_reports.append(f"{loser_name}이(가) {winner_name}에 의해 멸망했습니다!")
            elif transferred_city is not None:
                extra_reports.append(
                    f"{winner_name}이(가) {loser_name}의 도시 '{transferred_city['name']}'을(를) 점령했습니다."
                )
            else:
                extra_reports.append(f"{winner_name}이(가) {loser_name}의 영토를 침략했습니다.")

    if territory_changed:
        # Capital captures never happen to the player, but ordinary border tiles can
        # still change hands either way — keep the population ceiling honest either way.
        player_tiles = await territory_service.get_owned_tiles(session_id)
        await sync_land_capacity(session_id, len(player_tiles))

    # Rivals autonomously found extra cities too, same as the player — just free,
    # self-chosen, and nudged by personality instead of the player clicking a tile.
    all_cities = await city_service.get_cities(session_id)
    for rival in rivals:
        if rival.get("relationship") == "defeated":
            continue
        rival_id = rival["rival_id"]
        existing_rival_cities = [c for c in all_cities if c["owner"] == rival_id]
        if len(existing_rival_cities) >= city_service.RIVAL_CITY_MAX_EXTRA_CITIES:
            continue
        owned = await territory_service.get_owned_tiles(session_id, owner=rival_id)
        if len(owned) < city_service.RIVAL_CITY_MIN_TILES:
            continue
        capital = next((rc for rc in map_data["rival_capitals"] if rc["rival_id"] == rival_id), None)
        if capital is None:
            continue

        founding_mult = _trait(rival.get("personality"), "city_founding_multiplier")
        if random.random() < city_service.RIVAL_CITY_BASE_CHANCE_PER_MONTH * founding_mult:
            owned_set = {(t["x"], t["y"]) for t in owned}
            founded = await city_service.found_rival_city(session_id, rival_id, capital, owned_set, current_date)
            if founded is not None:
                cities_changed = True
                extra_reports.append(f"{rival['name']}이(가) 새 도시 '{founded['name']}'을(를) 세웠습니다.")

    return extra_reports, territory_changed, cities_changed


class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.clock = GameClock()
        self.connections: set[WebSocket] = set()
        self.months_since_advice = 0
        self.pending_advice: dict | None = None
        self.pending_peace_offer: dict | None = None
        # The player's current "focus fire" target per rival at war (see the
        # attack-city endpoint in main.py) — {rival_id: (x, y)}. In-memory only, same
        # as pending_advice/pending_peace_offer: it's a current-intent hint, not
        # critical state, so it's fine for it to reset if the session object is
        # recreated (server restart, etc.) — the player can just re-target.
        self.siege_targets: dict[str, tuple[int, int]] = {}

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
        map_data = await map_service.get_or_create_map(self.session_id)
        player_cities = [c for c in cities if c["owner"] == city_service.PLAYER_OWNER]
        resource_bonus = _compute_resource_bonus(map_data, player_cities)
        nation = await advance_nation(
            self.session_id,
            current_date,
            owned_tile_count=len(owned_tiles),
            city_count=len(cities),
            resource_bonus=resource_bonus,
        )
        await self.broadcast("nation_updated", {"nation": nation.to_dict()})

        nation, completed_tech = await advance_research(self.session_id)
        if completed_tech is not None:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("tech_completed", {"tech_id": completed_tech})
            tech_name = TECH_BY_ID[completed_tech]["name"]
            await log_service.add_log(
                self.session_id, current_date["year"], current_date["month"], "tech", f"{tech_name} 연구를 완료했습니다."
            )

        nation, completed_building = await advance_building(self.session_id)
        if completed_building is not None:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("building_completed", {"building_id": completed_building})
            building_name = BUILDING_BY_ID[completed_building]["name"]
            await log_service.add_log(
                self.session_id,
                current_date["year"],
                current_date["month"],
                "building",
                f"{building_name} 건설을 완료했습니다.",
            )

        event = maybe_trigger_event()
        if event is not None:
            nation = await apply_random_event(self.session_id, event)
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("random_event", {"event": event})
            await log_service.add_log(
                self.session_id,
                current_date["year"],
                current_date["month"],
                "event",
                f"{event['name']}: {event['description']}",
            )

        nation, great_person = await maybe_spawn_great_person(self.session_id, nation, current_date)
        if great_person is not None:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast(
                "great_person_appeared", {"person": great_person, "current_date": current_date}
            )
            await log_service.add_log(
                self.session_id,
                current_date["year"],
                current_date["month"],
                "great_person",
                f"{great_person['name']}({great_person['title']})이(가) 등장했습니다.",
            )

        nation, rivals, war_reports, war_outcomes, peace_offers = await advance_rivals(
            self.session_id, current_date
        )
        await self.broadcast("rivals_updated", {"rivals": rivals})

        # Rivals get a shot at claiming a wonder first — that way, if a rival finishes
        # the exact wonder the player is mid-construction on this same month, the
        # player's advance_wonder() call right after sees the claim already there and
        # loses the investment, instead of the two racing in an order-dependent way.
        wonder_events = await advance_rival_wonders(self.session_id, rivals)
        for wevent in wonder_events:
            message = f"{wevent['rival_name']}이(가) {wevent['wonder_name']}을(를) 완성했습니다!"
            if wevent["sabotaged_player"]:
                message += " 건설 중이던 계획이 무산되었습니다."
            await log_service.add_log(
                self.session_id, current_date["year"], current_date["month"], "wonder", message
            )
            await self.broadcast("wonder_completed", {**wevent, "message": message})

        nation, completed_wonder = await advance_wonder(self.session_id)
        if completed_wonder is not None:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            wonder_name = WONDER_BY_ID[completed_wonder]["name"]
            player_message = f"{wonder_name} 건설을 완료했습니다!"
            await self.broadcast(
                "wonder_completed", {"wonder_id": completed_wonder, "rival_id": None, "message": player_message}
            )
            await log_service.add_log(
                self.session_id, current_date["year"], current_date["month"], "wonder", player_message
            )

        # Only one offer sits on the table at a time (mirrors pending_advice) — if a
        # second rival also wants to sue for peace this month, it'll offer again (or
        # this same one will) another month; no need to stack popups.
        if self.pending_peace_offer is None and peace_offers:
            self.pending_peace_offer = peace_offers[0]
            await self.broadcast("peace_offer_available", {"offer": self.pending_peace_offer})

        # No win/loss conditions anywhere else in this game — this is the one
        # exception: uniting the whole map (every rival defeated) ends it.
        if rivals and all(r["relationship"] == "defeated" for r in rivals):
            self.clock.speed = "paused"

        nation, trade_income = await advance_trade(self.session_id, rivals, resource_bonus)
        if trade_income > 0:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})

        world_news, world_war_outcomes = await advance_world(self.session_id)

        extra_reports, territory_changed, cities_changed = await _resolve_territory_changes(
            self.session_id, rivals, war_outcomes, world_war_outcomes, current_date, nation.economy, self.siege_targets
        )
        all_war_reports = war_reports + extra_reports

        await log_service.add_logs(self.session_id, current_date["year"], current_date["month"], "war", all_war_reports)
        await log_service.add_logs(self.session_id, current_date["year"], current_date["month"], "world", world_news)

        war_reports = all_war_reports + world_news
        if war_reports:
            await self.broadcast("nation_updated", {"nation": nation.to_dict()})
            await self.broadcast("war_report", {"reports": war_reports})
        if territory_changed:
            all_tiles = await territory_service.get_all_tiles(self.session_id)
            await self.broadcast("territory_updated", {"all": all_tiles})
        if cities_changed:
            cities = await city_service.get_cities(self.session_id)
            await self.broadcast("cities_updated", {"cities": cities})

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
