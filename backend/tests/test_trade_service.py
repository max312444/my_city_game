import pytest

from app.db import async_session_maker
from app.services import diplomacy_service, nation_service, trade_service


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


async def _set_food_stock(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.food_stock = amount
        await db.commit()


def test_compute_route_income_scales_with_the_weaker_side_and_resources():
    plain = trade_service.compute_route_income(100.0, 50.0, {})
    assert plain == trade_service.TRADE_BASE_INCOME + trade_service.TRADE_RATE * 50.0

    with_resources = trade_service.compute_route_income(100.0, 50.0, {"economy": 10.0})
    assert with_resources > plain


async def test_establish_route_requires_peace(session_id):
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    with pytest.raises(trade_service.TradeError, match="평화 상태"):
        await trade_service.establish_route(session_id, "eastern_tribes", "war")


async def test_establish_route_rejects_duplicate(session_id):
    await trade_service.establish_route(session_id, "eastern_tribes", "peace")
    with pytest.raises(trade_service.TradeError, match="이미 교역로"):
        await trade_service.establish_route(session_id, "eastern_tribes", "peace")


async def test_close_route_removes_it(session_id):
    await trade_service.establish_route(session_id, "eastern_tribes", "peace")
    await trade_service.close_route(session_id, "eastern_tribes")
    # closing again should be a harmless no-op, not an error
    await trade_service.close_route(session_id, "eastern_tribes")

    async with async_session_maker() as db:
        assert await trade_service._get_routes(db, session_id) == []


async def test_advance_trade_pays_income_only_for_peaceful_routes(session_id):
    await nation_service.get_or_create_nation(session_id)
    await trade_service.establish_route(session_id, "eastern_tribes", "peace")
    await trade_service.establish_route(session_id, "northern_kingdom", "peace")
    before = await nation_service.get_or_create_nation(session_id)

    rivals = [
        {"rival_id": "eastern_tribes", "name": "동쪽 부족 연맹", "economy": 50.0, "relationship": "peace"},
        {"rival_id": "northern_kingdom", "name": "북방 왕국", "economy": 50.0, "relationship": "war"},
    ]
    nation, income = await trade_service.advance_trade(session_id, rivals, {})
    assert income == trade_service.compute_route_income(before.economy, 50.0, {})
    assert nation.treasury == pytest.approx(before.treasury + income)


async def test_sell_food_converts_to_treasury(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 0)
    await _set_food_stock(session_id, 100.0)

    nation = await trade_service.sell_food(session_id, 50.0)
    assert nation.food_stock == 50.0
    assert nation.treasury == 50.0 * trade_service.FOOD_SELL_RATE


async def test_sell_food_rejects_dropping_below_reserve(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _set_food_stock(session_id, 15.0)
    with pytest.raises(trade_service.TradeError):
        await trade_service.sell_food(session_id, 10.0)  # would leave only 5, below the 10 reserve


async def test_sell_food_rejects_non_positive_amount(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _set_food_stock(session_id, 100.0)
    with pytest.raises(trade_service.TradeError):
        await trade_service.sell_food(session_id, 0)


async def test_get_trade_state_reports_zero_income_for_routes_at_war(session_id):
    await nation_service.get_or_create_nation(session_id)
    await trade_service.establish_route(session_id, "eastern_tribes", "peace")
    rivals = [{"rival_id": "eastern_tribes", "name": "동쪽 부족 연맹", "economy": 50.0, "relationship": "war"}]

    state = await trade_service.get_trade_state(session_id, rivals, {})
    assert state["routes"][0]["income"] == 0.0
    assert state["routes"][0]["relationship"] == "war"


async def test_delete_routes_removes_everything(session_id):
    await trade_service.establish_route(session_id, "eastern_tribes", "peace")
    await trade_service.delete_routes(session_id)
    async with async_session_maker() as db:
        assert await trade_service._get_routes(db, session_id) == []
