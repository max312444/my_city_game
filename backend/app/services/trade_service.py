from sqlalchemy import select

from app.db import async_session_maker
from app.models.trade import TradeRoute
from app.services.nation_service import _get_or_create_nation

# Deliberately modest — a nice supplementary income, never the main strategy (same
# tone as everything else in this game: small, steady bonuses rather than a system
# you're forced to optimize around). A route with a similarly-developed peaceful
# neighbor pays a little more than one with a much poorer one.
TRADE_BASE_INCOME = 5.0
TRADE_RATE = 0.05
# Resources near the capital/cities already give a direct stat bonus (see
# session_manager._compute_resource_bonus) — an open trade route lets you also
# "export" a fraction of that as extra income, without doubling the resource's own
# stat effect.
RESOURCE_EXPORT_BONUS_RATE = 0.5

FOOD_SELL_RATE = 2.0  # gold per unit of food sold
FOOD_SELL_MIN_RESERVE = 10.0  # can never sell food stock down below this


class TradeError(Exception):
    pass


async def _get_routes(db, session_id: str) -> list[TradeRoute]:
    result = await db.execute(select(TradeRoute).where(TradeRoute.session_id == session_id))
    return list(result.scalars().all())


def compute_route_income(player_economy: float, rival_economy: float, resource_bonus: dict) -> float:
    income = TRADE_BASE_INCOME + TRADE_RATE * min(player_economy, rival_economy)
    income += RESOURCE_EXPORT_BONUS_RATE * resource_bonus.get("economy", 0.0)
    return round(income, 1)


async def get_trade_state(session_id: str, rivals: list[dict], resource_bonus: dict) -> dict:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        routes = await _get_routes(db, session_id)
        await db.commit()

    by_id = {r["rival_id"]: r for r in rivals}
    route_info = []
    for route in routes:
        rival = by_id.get(route.rival_id)
        if rival is None:
            continue
        route_info.append(
            {
                "rival_id": route.rival_id,
                "rival_name": rival["name"],
                "relationship": rival["relationship"],
                "income": compute_route_income(nation.economy, rival["economy"], resource_bonus)
                if rival["relationship"] == "peace"
                else 0.0,
            }
        )
    return {
        "routes": route_info,
        "food_stock": round(nation.food_stock, 1),
        "food_sell_rate": FOOD_SELL_RATE,
        "food_sell_min_reserve": FOOD_SELL_MIN_RESERVE,
    }


async def establish_route(session_id: str, rival_id: str, rival_relationship: str) -> None:
    if rival_relationship != "peace":
        raise TradeError("평화 상태의 국가와만 교역로를 열 수 있습니다")
    async with async_session_maker() as db:
        existing = await _get_routes(db, session_id)
        if any(r.rival_id == rival_id for r in existing):
            raise TradeError("이미 교역로가 있습니다")
        db.add(TradeRoute(session_id=session_id, rival_id=rival_id))
        await db.commit()


async def close_route(session_id: str, rival_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(
            select(TradeRoute).where(TradeRoute.session_id == session_id, TradeRoute.rival_id == rival_id)
        )
        route = result.scalar_one_or_none()
        if route is not None:
            await db.delete(route)
            await db.commit()


async def sell_food(session_id: str, amount: float):
    if amount <= 0:
        raise TradeError("판매량은 0보다 커야 합니다")
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        if nation.food_stock - amount < FOOD_SELL_MIN_RESERVE:
            raise TradeError(f"최소 {FOOD_SELL_MIN_RESERVE:g} 이상의 비축량은 남겨야 합니다")
        nation.food_stock -= amount
        nation.treasury += amount * FOOD_SELL_RATE
        await db.commit()
        await db.refresh(nation)
        return nation


async def advance_trade(session_id: str, rivals: list[dict], resource_bonus: dict):
    """Called once per month tick. War with a route's rival simply skips that route's
    income this month (no deletion) — peace resumes it automatically. Returns
    (nation, total_income)."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        routes = await _get_routes(db, session_id)

        by_id = {r["rival_id"]: r for r in rivals}
        total_income = 0.0
        for route in routes:
            rival = by_id.get(route.rival_id)
            if rival is None or rival["relationship"] != "peace":
                continue
            income = compute_route_income(nation.economy, rival["economy"], resource_bonus)
            nation.treasury += income
            total_income += income

        await db.commit()
        await db.refresh(nation)
        return nation, round(total_income, 1)


async def delete_routes(session_id: str) -> None:
    async with async_session_maker() as db:
        for route in await _get_routes(db, session_id):
            await db.delete(route)
        await db.commit()
