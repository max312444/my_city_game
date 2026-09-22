import pytest

from app.db import async_session_maker
from app.services import city_service, nation_service

CAPITAL = {"x": 10, "y": 10}


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


def _owned_around(cx, cy, radius=10):
    return {(x, y) for x in range(cx - radius, cx + radius + 1) for y in range(cy - radius, cy + radius + 1)}


async def test_found_city_success_deducts_cost_and_appears_in_list(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    owned = _owned_around(*CAPITAL.values())

    nation, cost = await city_service.found_city(
        session_id, 15, 15, "새도시", CAPITAL, {"year": 3, "month": 4}, owned
    )
    assert cost == city_service.CITY_BASE_COST
    assert nation.treasury == 10_000 - cost

    cities = await city_service.get_cities(session_id)
    assert len(cities) == 1
    assert cities[0]["name"] == "새도시"
    assert cities[0]["founded_year"] == 3
    assert cities[0]["founded_month"] == 4


async def test_found_city_cost_grows_with_existing_cities(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)
    owned = _owned_around(*CAPITAL.values())

    _, cost1 = await city_service.found_city(session_id, 15, 15, "도시1", CAPITAL, {"year": 1, "month": 1}, owned)
    _, cost2 = await city_service.found_city(session_id, 5, 15, "도시2", CAPITAL, {"year": 1, "month": 1}, owned)
    assert cost2 > cost1
    assert cost2 == city_service.compute_cost(1)


async def test_found_city_rejects_tile_not_owned(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    with pytest.raises(city_service.CityError):
        await city_service.found_city(session_id, 999, 999, "도시", CAPITAL, {"year": 1, "month": 1}, set())


async def test_found_city_rejects_too_close_to_capital(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    owned = _owned_around(*CAPITAL.values())
    with pytest.raises(city_service.CityError):
        await city_service.found_city(session_id, 11, 10, "도시", CAPITAL, {"year": 1, "month": 1}, owned)


async def test_found_city_rejects_too_close_to_another_city(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)
    owned = _owned_around(*CAPITAL.values())
    await city_service.found_city(session_id, 15, 15, "도시1", CAPITAL, {"year": 1, "month": 1}, owned)
    with pytest.raises(city_service.CityError):
        await city_service.found_city(session_id, 16, 16, "도시2", CAPITAL, {"year": 1, "month": 1}, owned)


async def test_found_city_rejects_insufficient_funds(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 0)
    owned = _owned_around(*CAPITAL.values())
    with pytest.raises(city_service.CityError):
        await city_service.found_city(session_id, 15, 15, "도시", CAPITAL, {"year": 1, "month": 1}, owned)


async def test_found_city_rejects_empty_name(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    owned = _owned_around(*CAPITAL.values())
    with pytest.raises(city_service.CityError):
        await city_service.found_city(session_id, 15, 15, "   ", CAPITAL, {"year": 1, "month": 1}, owned)


async def test_delete_cities_removes_everything(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    owned = _owned_around(*CAPITAL.values())
    await city_service.found_city(session_id, 15, 15, "도시", CAPITAL, {"year": 1, "month": 1}, owned)

    await city_service.delete_cities(session_id)
    assert await city_service.get_cities(session_id) == []


async def test_get_cities_reports_owner(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    owned = _owned_around(*CAPITAL.values())
    await city_service.found_city(session_id, 15, 15, "플레이어시", CAPITAL, {"year": 1, "month": 1}, owned)

    cities = await city_service.get_cities(session_id)
    assert cities[0]["owner"] == "player"


async def test_found_rival_city_success_is_free_and_owned_by_rival(session_id):
    owned = _owned_around(*CAPITAL.values())
    result = await city_service.found_rival_city(session_id, "eastern_tribes", CAPITAL, owned, {"year": 1, "month": 1})
    assert result is not None
    assert max(abs(result["x"] - CAPITAL["x"]), abs(result["y"] - CAPITAL["y"])) >= city_service.MIN_DISTANCE_FROM_OTHER_CITIES

    cities = await city_service.get_cities(session_id)
    assert len(cities) == 1
    assert cities[0]["owner"] == "eastern_tribes"


async def test_found_rival_city_returns_none_when_no_tile_is_far_enough(session_id):
    owned = {(CAPITAL["x"] + 1, CAPITAL["y"])}  # only one tile, too close to its own capital
    result = await city_service.found_rival_city(session_id, "eastern_tribes", CAPITAL, owned, {"year": 1, "month": 1})
    assert result is None
    assert await city_service.get_cities(session_id) == []


async def test_found_rival_city_respects_distance_from_other_cities(session_id):
    owned = _owned_around(*CAPITAL.values())
    first = await city_service.found_rival_city(session_id, "eastern_tribes", CAPITAL, owned, {"year": 1, "month": 1})
    assert first is not None

    # Only tiles right next to the just-founded city remain "too close" — remove them
    # from the candidate set so a second attempt is forced away from that city too.
    near_first_city = {
        (x, y)
        for x in range(first["x"] - 2, first["x"] + 3)
        for y in range(first["y"] - 2, first["y"] + 3)
    }
    remaining = owned - near_first_city
    second = await city_service.found_rival_city(session_id, "eastern_tribes", CAPITAL, remaining, {"year": 1, "month": 2})
    if second is not None:
        distance = max(abs(second["x"] - first["x"]), abs(second["y"] - first["y"]))
        assert distance >= city_service.MIN_DISTANCE_FROM_OTHER_CITIES
