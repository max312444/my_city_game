import math
import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.nation import (
    CITY_ECONOMY_BONUS_PER_CITY,
    EDUCATION_UPKEEP_RATE,
    FOOD_GROWTH_SENSITIVITY,
    FOOD_PER_CAPITA_CONSUMPTION,
    FOOD_PER_CAPITA_PRODUCTION,
    INCOME_PER_ECONOMY_POINT,
    LAND_CAPACITY_PER_TILE,
    MILITARY_UPKEEP_RATE,
    STABILITY_UPKEEP_RATE,
    STAT_MAX,
    Nation,
    compute_land_capacity,
    population_factor,
)

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


async def set_nation_name(session_id: str, name: str) -> Nation:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        nation.name = name
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


async def advance_nation(
    session_id: str, current_date: dict, owned_tile_count: int | None = None, city_count: int = 0
) -> Nation:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)

        if owned_tile_count is not None:
            nation.land_capacity = compute_land_capacity(owned_tile_count)

        city_bonus = 1 + CITY_ECONOMY_BONUS_PER_CITY * city_count

        pop_factor = population_factor(nation.population)
        for stat in STATS:
            value = getattr(nation, stat)
            delta = random.uniform(-4, 6)
            if stat in ("economy", "military") and delta > 0:
                delta *= pop_factor
            setattr(nation, stat, _apply_delta(value, delta))

        # Food surplus/deficit drives population growth (Civ-style): a fed, uncrowded
        # nation grows; a starving one shrinks. Tech (agriculture, irrigation) raises
        # food_bonus, which raises production per capita. Founded cities add a small
        # nation-wide production bonus on top.
        food_production = nation.population * (FOOD_PER_CAPITA_PRODUCTION + nation.food_bonus) * city_bonus
        food_consumption = nation.population * FOOD_PER_CAPITA_CONSUMPTION
        net_food = food_production - food_consumption
        nation.food_stock += net_food

        per_capita_surplus = net_food / max(nation.population, 1.0)
        growth_rate = max(-0.05, min(0.05, per_capita_surplus * FOOD_GROWTH_SENSITIVITY))
        if growth_rate > 0:
            growth_rate *= max(0.0, min(1.0, 2 - nation.population / nation.land_capacity))

        # Population is headcount, not a fraction of a person: bank fractional growth
        # in a buffer and only add/remove whole people once it accumulates to one.
        nation.population_growth_buffer += nation.population * growth_rate
        whole_change = math.trunc(nation.population_growth_buffer)
        if whole_change != 0:
            nation.population = max(1, nation.population + whole_change)
            nation.population_growth_buffer -= whole_change

        income = nation.economy * INCOME_PER_ECONOMY_POINT * pop_factor * city_bonus
        expenses = (
            nation.military * MILITARY_UPKEEP_RATE
            + nation.education * EDUCATION_UPKEEP_RATE
            + nation.stability * STABILITY_UPKEEP_RATE
        )
        nation.treasury += income - expenses
        nation.year = current_date["year"]
        nation.month = current_date["month"]
        await db.commit()
        await db.refresh(nation)
        return nation


async def sync_land_capacity(session_id: str, owned_tile_count: int) -> Nation:
    """Recomputes land_capacity right away (e.g. right after a land purchase or a war
    capture) instead of waiting for the next month's advance_nation tick."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        nation.land_capacity = compute_land_capacity(owned_tile_count)
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


async def apply_random_event(session_id: str, event: dict) -> Nation:
    """Big events (good or bad) hit as a percentage of current stats/population (so a
    stat boost still respects diminishing returns near the cap, same as advice/tech),
    and as a number of months' worth of income/food gained or lost for treasury/food_stock
    (which can already be negative, so a percentage of them would push the wrong way)."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)

        for stat, pct in event.get("stat_effects", {}).items():
            if stat in STATS:
                value = getattr(nation, stat)
                setattr(nation, stat, _apply_delta(value, value * pct))

        if "population_percent" in event:
            nation.population = max(1, int(nation.population * (1 + event["population_percent"])))

        if "treasury_loss_months" in event:
            monthly_income = nation.economy * INCOME_PER_ECONOMY_POINT * population_factor(nation.population)
            nation.treasury -= monthly_income * event["treasury_loss_months"]

        if "food_loss_months" in event:
            monthly_food = nation.population * (FOOD_PER_CAPITA_PRODUCTION + nation.food_bonus)
            nation.food_stock -= monthly_food * event["food_loss_months"]

        await db.commit()
        await db.refresh(nation)
        return nation
