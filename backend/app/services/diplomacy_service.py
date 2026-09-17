import itertools
import random

from sqlalchemy import select

from app.data.rivals import RIVAL_TEMPLATES
from app.db import async_session_maker
from app.models.rival_nation import RivalNation
from app.models.rival_relationship import RivalRelationship
from app.services.nation_service import STAT_MAX, _apply_delta, _get_or_create_nation

RIVAL_EXPANSION_CHANCE_DIVISOR = 400.0
RIVAL_EXPANSION_CHANCE_CAP = 0.25

WAR_DECLARATION_STABILITY_PENALTY = -0.05
WAR_UPKEEP_BASE = 10.0
WAR_UPKEEP_PER_MILITARY = 0.2

# A rival only ever attacks first when it currently has the upper hand militarily,
# and even then rarely — this should read as an occasional shock, not a threat the
# player needs to actively defend against every month.
RIVAL_AGGRESSION_CHANCE_BASE = 0.01
RIVAL_AGGRESSION_CHANCE_CAP = 0.05

# The longer a war drags on, the harder it gets to sustain (extra stability bleed on
# both sides) and the more likely it just ends in a tired peace on its own — so no
# war can grind on forever unresolved even if the player never intervenes.
WAR_EXHAUSTION_STABILITY_RATE = 0.005
WAR_EXHAUSTION_MONTHS_CAP = 12
WAR_EXHAUSTION_PEACE_CHANCE_PER_MONTH = 0.02
WAR_EXHAUSTION_PEACE_CHANCE_CAP = 0.3

# Rivals also act on each other, independent of the player — the "다른 국가들도 각자
# 성향에 따라 완전 자율로 발전한다" part of the original design brief. Kept deliberately
# lighter-weight than the player-facing war system: no territory changes hands between
# two rivals, and an alliance is flavor only (it does not drag anyone into a war).
WORLD_WAR_CHANCE_PER_MONTH = 0.01
WORLD_ALLIANCE_CHANCE_PER_MONTH = 0.008
WORLD_ALLIANCE_BREAK_CHANCE_PER_MONTH = 0.02
WORLD_WAR_PEACE_CHANCE_PER_MONTH = 0.08


class DiplomacyError(Exception):
    pass


async def _get_rivals(db, session_id: str) -> list[RivalNation]:
    result = await db.execute(select(RivalNation).where(RivalNation.session_id == session_id))
    rivals = list(result.scalars().all())
    if not rivals:
        for template in RIVAL_TEMPLATES:
            rival = RivalNation(session_id=session_id, **template)
            db.add(rival)
            rivals.append(rival)
        await db.flush()
    return rivals


async def get_rivals(session_id: str) -> list[dict]:
    async with async_session_maker() as db:
        rivals = await _get_rivals(db, session_id)
        await db.commit()
        return [r.to_dict() for r in rivals]


async def declare_war(session_id: str, rival_id: str):
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        rivals = await _get_rivals(db, session_id)
        rival = next((r for r in rivals if r.rival_id == rival_id), None)
        if rival is None:
            raise DiplomacyError("알 수 없는 국가입니다")
        if rival.relationship == "war":
            raise DiplomacyError("이미 전쟁 중입니다")
        if rival.relationship == "defeated":
            raise DiplomacyError("이미 멸망한 국가입니다")

        rival.relationship = "war"
        rival.war_months = 0
        nation.stability = _apply_delta(nation.stability, nation.stability * WAR_DECLARATION_STABILITY_PENALTY)

        await db.commit()
        await db.refresh(nation)
        return nation, [r.to_dict() for r in rivals]


async def propose_peace(session_id: str, rival_id: str):
    async with async_session_maker() as db:
        rivals = await _get_rivals(db, session_id)
        rival = next((r for r in rivals if r.rival_id == rival_id), None)
        if rival is None:
            raise DiplomacyError("알 수 없는 국가입니다")
        if rival.relationship != "war":
            raise DiplomacyError("전쟁 중이 아닙니다")

        nation = await _get_or_create_nation(db, session_id)
        # More likely to accept if it is currently the weaker side.
        strength_ratio = rival.military / max(nation.military, 1.0)
        accept_chance = max(0.15, min(0.9, 0.85 - (1 - strength_ratio) * 0.4))
        accepted = random.random() < accept_chance
        if accepted:
            rival.relationship = "peace"
            rival.war_months = 0

        await db.commit()
        return accepted, [r.to_dict() for r in rivals]


async def advance_rivals(session_id: str, current_date: dict):
    """Called once per month tick. Returns (nation, rivals, reports, war_outcomes).

    Stays deliberately ignorant of the map/territory — that would need importing
    map_service and territory_service here, and map_service already imports
    RIVAL_TEMPLATES (now from app.data.rivals, not here) to place rival capitals, so
    reaching back into map/territory from this module invites circular imports for
    no real benefit. Territory expansion and war captures both need map tiles anyway,
    so session_manager (which already orchestrates every service each month tick)
    resolves `war_outcomes` into actual tile changes after this returns."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        rivals = await _get_rivals(db, session_id)
        reports = []
        war_outcomes = []  # (winner_owner, loser_owner, rival_name) — resolved into tile captures below

        for rival in rivals:
            if rival.relationship == "defeated":
                continue  # a fallen nation is out of the game — its stats stay frozen

            for stat in ("economy", "stability", "military"):
                value = getattr(rival, stat)
                delta = random.uniform(-4, 6)
                setattr(rival, stat, max(0.0, min(STAT_MAX, value + delta)))

            if rival.relationship == "war":
                rival.war_months += 1

                # War exhaustion: a dragged-out war bleeds extra stability on both sides
                # every month, and gets an ever-larger chance of just ending in a tired
                # peace on its own — so a war never grinds on forever unresolved.
                exhaustion = min(rival.war_months, WAR_EXHAUSTION_MONTHS_CAP)
                nation.stability = _apply_delta(
                    nation.stability, -nation.stability * WAR_EXHAUSTION_STABILITY_RATE * exhaustion
                )
                rival.stability = max(
                    0.0, rival.stability - rival.stability * WAR_EXHAUSTION_STABILITY_RATE * exhaustion
                )

                peace_chance = min(
                    WAR_EXHAUSTION_PEACE_CHANCE_CAP, rival.war_months * WAR_EXHAUSTION_PEACE_CHANCE_PER_MONTH
                )
                if random.random() < peace_chance:
                    rival.relationship = "peace"
                    rival.war_months = 0
                    reports.append(f"{rival.name}과(와) 장기전 끝에 지쳐 평화 협정을 맺었습니다.")
                    continue  # the war ended before any combat happened this month

                player_power = nation.military * random.uniform(0.8, 1.2)
                rival_power = rival.military * random.uniform(0.8, 1.2)

                if player_power >= rival_power:
                    rival.military = max(0.0, rival.military * 0.9)
                    nation.stability = _apply_delta(nation.stability, nation.stability * 0.02)
                    reports.append(f"{rival.name}과(와)의 전투에서 승리했습니다.")
                    war_outcomes.append(("player", rival.rival_id, rival.name))
                else:
                    nation.military = _apply_delta(nation.military, -nation.military * 0.05)
                    nation.stability = _apply_delta(nation.stability, -nation.stability * 0.02)
                    reports.append(f"{rival.name}과(와)의 전투에서 패배했습니다.")
                    war_outcomes.append((rival.rival_id, "player", rival.name))

                nation.treasury -= WAR_UPKEEP_BASE + nation.military * WAR_UPKEEP_PER_MILITARY
            else:
                # At peace: a rival currently stronger than the player has a small,
                # capped chance of striking first — the player is never truly safe from
                # war, but it stays a rare event, not something to brace for every month.
                aggression_chance = min(
                    RIVAL_AGGRESSION_CHANCE_CAP,
                    RIVAL_AGGRESSION_CHANCE_BASE * (rival.military / max(nation.military, 1.0)),
                )
                if random.random() < aggression_chance:
                    rival.relationship = "war"
                    rival.war_months = 0
                    nation.stability = _apply_delta(
                        nation.stability, nation.stability * WAR_DECLARATION_STABILITY_PENALTY
                    )
                    reports.append(f"{rival.name}이(가) 선전포고했습니다!")

        await db.commit()
        await db.refresh(nation)
        rival_dicts = [r.to_dict() for r in rivals]

    return nation, rival_dicts, reports, war_outcomes


async def delete_world_data(session_id: str) -> None:
    """Wipes rivals + rival-rival relationships for this session — used when a player
    restarts the game (see main.py's DELETE /session), so a fresh game doesn't inherit
    a previous playthrough's rival stats, wars, or defeats."""
    async with async_session_maker() as db:
        result = await db.execute(select(RivalNation).where(RivalNation.session_id == session_id))
        for rival in result.scalars().all():
            await db.delete(rival)
        result = await db.execute(select(RivalRelationship).where(RivalRelationship.session_id == session_id))
        for rel in result.scalars().all():
            await db.delete(rel)
        await db.commit()


async def mark_defeated(session_id: str, rival_id: str) -> None:
    """Called by session_manager when a war capture eliminates a rival's last tile."""
    async with async_session_maker() as db:
        rivals = await _get_rivals(db, session_id)
        rival = next((r for r in rivals if r.rival_id == rival_id), None)
        if rival is not None:
            rival.relationship = "defeated"
            rival.war_months = 0
            await db.commit()


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


async def _get_relationships(db, session_id: str, rival_ids: list[str]) -> dict[tuple[str, str], RivalRelationship]:
    result = await db.execute(select(RivalRelationship).where(RivalRelationship.session_id == session_id))
    rows = {(_pair_key(r.rival_a, r.rival_b)): r for r in result.scalars().all()}

    for a, b in itertools.combinations(sorted(rival_ids), 2):
        key = (a, b)
        if key not in rows:
            row = RivalRelationship(session_id=session_id, rival_a=a, rival_b=b, relationship="peace")
            db.add(row)
            rows[key] = row
    await db.flush()
    return rows


async def get_world_relationships(session_id: str) -> list[dict]:
    """Rival-vs-rival relationships, independent of the player."""
    async with async_session_maker() as db:
        rivals = await _get_rivals(db, session_id)
        active_ids = [r.rival_id for r in rivals if r.relationship != "defeated"]
        relationships = await _get_relationships(db, session_id, active_ids)
        await db.commit()
        return [
            {"rival_a": r.rival_a, "rival_b": r.rival_b, "relationship": r.relationship}
            for key, r in relationships.items()
            if key[0] in active_ids and key[1] in active_ids
        ]


async def advance_world(session_id: str) -> list[str]:
    """Called once per month tick, independent of the player: rivals occasionally go
    to war, ally, or make peace with *each other*. Deliberately lightweight — no
    territory changes hands between two rivals, and an alliance is flavor only (it
    never drags a third party into someone else's war). Returns a list of news lines."""
    async with async_session_maker() as db:
        rivals = await _get_rivals(db, session_id)
        by_id = {r.rival_id: r for r in rivals if r.relationship != "defeated"}
        relationships = await _get_relationships(db, session_id, list(by_id.keys()))
        news = []

        for (a, b), rel in relationships.items():
            if a not in by_id or b not in by_id:
                continue  # one side has since been defeated — this pair is moot
            rival_a, rival_b = by_id[a], by_id[b]

            if rel.relationship == "peace":
                if random.random() < WORLD_WAR_CHANCE_PER_MONTH:
                    rel.relationship = "war"
                    news.append(f"{rival_a.name}과(와) {rival_b.name}이(가) 전쟁을 시작했습니다.")
                elif random.random() < WORLD_ALLIANCE_CHANCE_PER_MONTH:
                    rel.relationship = "alliance"
                    news.append(f"{rival_a.name}과(와) {rival_b.name}이(가) 동맹을 맺었습니다.")

            elif rel.relationship == "war":
                power_a = rival_a.military * random.uniform(0.8, 1.2)
                power_b = rival_b.military * random.uniform(0.8, 1.2)
                loser, winner = (rival_a, rival_b) if power_a < power_b else (rival_b, rival_a)
                loser.military = max(0.0, loser.military * 0.92)
                loser.stability = max(0.0, loser.stability * 0.97)

                if random.random() < WORLD_WAR_PEACE_CHANCE_PER_MONTH:
                    rel.relationship = "peace"
                    news.append(f"{rival_a.name}과(와) {rival_b.name}이(가) 전쟁을 끝내고 평화를 맺었습니다.")

            elif rel.relationship == "alliance":
                if random.random() < WORLD_ALLIANCE_BREAK_CHANCE_PER_MONTH:
                    rel.relationship = "peace"
                    news.append(f"{rival_a.name}과(와) {rival_b.name}의 동맹이 깨졌습니다.")

        await db.commit()
        return news
