from sqlalchemy import select

from app.db import async_session_maker
from app.models.city import City
from app.services.nation_service import _get_or_create_nation

CITY_BASE_COST = 2000.0
CITY_COST_GROWTH = 1000.0
MIN_DISTANCE_FROM_OTHER_CITIES = 3  # chebyshev tiles, capital counts as a "city" too


class CityError(Exception):
    pass


async def _get_cities(db, session_id: str) -> list[City]:
    result = await db.execute(select(City).where(City.session_id == session_id))
    return list(result.scalars().all())


async def get_cities(session_id: str) -> list[dict]:
    async with async_session_maker() as db:
        cities = await _get_cities(db, session_id)
        return [
            {"name": c.name, "x": c.x, "y": c.y, "founded_year": c.founded_year, "founded_month": c.founded_month}
            for c in cities
        ]


def compute_cost(existing_city_count: int) -> float:
    return CITY_BASE_COST + CITY_COST_GROWTH * existing_city_count


async def found_city(
    session_id: str, x: int, y: int, name: str, capital: dict, current_date: dict, owned_tiles: set[tuple[int, int]]
):
    name = name.strip()
    if not name:
        raise CityError("도시 이름을 입력해주세요")
    if (x, y) not in owned_tiles:
        raise CityError("자신의 영토 안에만 도시를 세울 수 있습니다")
    if max(abs(x - capital["x"]), abs(y - capital["y"])) < MIN_DISTANCE_FROM_OTHER_CITIES:
        raise CityError("수도와 너무 가깝습니다")

    async with async_session_maker() as db:
        cities = await _get_cities(db, session_id)
        for c in cities:
            if max(abs(x - c.x), abs(y - c.y)) < MIN_DISTANCE_FROM_OTHER_CITIES:
                raise CityError("다른 도시와 너무 가깝습니다")

        cost = compute_cost(len(cities))
        nation = await _get_or_create_nation(db, session_id)
        if nation.treasury < cost:
            raise CityError("보유 금액이 부족합니다")

        nation.treasury -= cost
        city = City(
            session_id=session_id,
            name=name,
            x=x,
            y=y,
            founded_year=current_date["year"],
            founded_month=current_date["month"],
        )
        db.add(city)
        await db.commit()
        await db.refresh(nation)
        return nation, cost


async def delete_cities(session_id: str) -> None:
    async with async_session_maker() as db:
        for city in await _get_cities(db, session_id):
            await db.delete(city)
        await db.commit()
