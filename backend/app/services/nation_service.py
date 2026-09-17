import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.nation import INCOME_PER_ECONOMY_POINT, STAT_MAX, Nation

STATS = ["economy", "stability", "military", "education"]


def _growth_multiplier(value: float) -> float:
    """Diminishing returns as a stat approaches STAT_MAX (e.g. ~0.8x around 100, ~0.01x around 900)."""
    ratio = value / STAT_MAX
    return max(0.0, 1 - ratio) ** 2


def _apply_delta(value: float, delta: float) -> float:
    if delta > 0:
        delta *= _growth_multiplier(value)
    return max(0.0, min(STAT_MAX, value + delta))


async def _get_or_create_nation(db, session_id: str) -> Nation:
    result = await db.execute(select(Nation).where(Nation.session_id == session_id))
    nation = result.scalar_one_or_none()
    if nation is None:
        nation = Nation(session_id=session_id, name=session_id)
        db.add(nation)
    return nation


async def get_or_create_nation(session_id: str) -> Nation:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        await db.commit()
        await db.refresh(nation)
        return nation


async def nation_exists(session_id: str) -> bool:
    async with async_session_maker() as db:
        result = await db.execute(select(Nation).where(Nation.session_id == session_id))
        return result.scalar_one_or_none() is not None


async def delete_nation(session_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(Nation).where(Nation.session_id == session_id))
        nation = result.scalar_one_or_none()
        if nation is not None:
            await db.delete(nation)
            await db.commit()


async def advance_nation(session_id: str, current_date: dict) -> Nation:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        for stat in STATS:
            value = getattr(nation, stat)
            delta = random.uniform(-15, 25)
            setattr(nation, stat, _apply_delta(value, delta))
        nation.treasury += nation.economy * INCOME_PER_ECONOMY_POINT
        nation.year = current_date["year"]
        nation.month = current_date["month"]
        await db.commit()
        await db.refresh(nation)
        return nation


async def apply_effects(session_id: str, effects: dict) -> Nation:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        for stat, delta in effects.items():
            if stat not in STATS:
                continue
            value = getattr(nation, stat)
            setattr(nation, stat, _apply_delta(value, delta))
        await db.commit()
        await db.refresh(nation)
        return nation
