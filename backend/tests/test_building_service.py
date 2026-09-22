import pytest

from app.db import async_session_maker
from app.services import building_service, nation_service, tech_service


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


async def _finish_tech(session_id, tech_id):
    await tech_service.start_research(session_id, tech_id)
    for _ in range(tech_service.TECH_BY_ID[tech_id]["duration_months"]):
        await tech_service.advance_research(session_id)


def test_building_list_ids_all_reference_a_real_tech():
    tech_ids = {t["id"] for t in tech_service.TECH_TREE}
    for building in building_service.BUILDINGS:
        assert building["requires_tech"] in tech_ids


def test_building_ids_have_no_duplicates():
    ids = [b["id"] for b in building_service.BUILDINGS]
    assert len(ids) == len(set(ids))


async def test_start_building_rejects_without_the_required_tech(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    with pytest.raises(building_service.BuildingError, match="선행 기술"):
        await building_service.start_building(session_id, "market")  # requires currency


async def test_start_building_succeeds_once_tech_is_researched(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await _finish_tech(session_id, "agriculture")

    nation, built = await building_service.start_building(session_id, "farm")
    assert nation.current_building == "farm"
    assert built == []


async def test_start_building_rejects_insufficient_funds(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await _finish_tech(session_id, "agriculture")
    await _give_treasury(session_id, 0)  # zero out *after* affording the tech itself
    with pytest.raises(building_service.BuildingError, match="보유 금액"):
        await building_service.start_building(session_id, "farm")


async def test_start_building_rejects_second_concurrent_building(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await _finish_tech(session_id, "agriculture")
    await _finish_tech(session_id, "writing_system")
    await building_service.start_building(session_id, "farm")
    with pytest.raises(building_service.BuildingError, match="이미 건설 중"):
        await building_service.start_building(session_id, "school")


async def test_advance_building_completes_after_duration_and_applies_effects(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await _finish_tech(session_id, "bronze_weapons")
    before = await nation_service.get_or_create_nation(session_id)

    await building_service.start_building(session_id, "blacksmith")  # duration 4, +military 8
    for _ in range(3):
        nation, completed = await building_service.advance_building(session_id)
        assert completed is None

    nation, completed = await building_service.advance_building(session_id)
    assert completed == "blacksmith"
    assert nation.current_building == ""
    assert nation.military > before.military

    state = await building_service.get_building_state(session_id)
    assert "blacksmith" in state["built"]


async def test_cannot_build_the_same_building_twice(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await _finish_tech(session_id, "agriculture")
    await building_service.start_building(session_id, "farm")
    for _ in range(building_service.BUILDING_BY_ID["farm"]["duration_months"]):
        await building_service.advance_building(session_id)

    with pytest.raises(building_service.BuildingError, match="이미 건설"):
        await building_service.start_building(session_id, "farm")
