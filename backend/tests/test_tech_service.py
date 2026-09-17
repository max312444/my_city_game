import pytest

from app.db import async_session_maker
from app.services import nation_service, tech_service


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


async def test_start_research_deducts_cost_and_sets_progress(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)

    nation, researched = await tech_service.start_research(session_id, "agriculture")
    assert nation.treasury == 10_000 - 300
    assert nation.current_research == "agriculture"
    assert nation.current_research_months_left == 3
    assert researched == []


async def test_start_research_rejects_insufficient_funds(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 0)
    with pytest.raises(tech_service.TechError):
        await tech_service.start_research(session_id, "agriculture")


async def test_start_research_enforces_prerequisites(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    # irrigation requires agriculture first
    with pytest.raises(tech_service.TechError):
        await tech_service.start_research(session_id, "irrigation")


async def test_start_research_rejects_second_concurrent_research(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await tech_service.start_research(session_id, "agriculture")
    with pytest.raises(tech_service.TechError):
        await tech_service.start_research(session_id, "writing_system")


async def test_advance_research_completes_after_duration_and_applies_effects(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    before = await nation_service.get_or_create_nation(session_id)
    await tech_service.start_research(session_id, "agriculture")  # duration_months = 3

    nation, completed = await tech_service.advance_research(session_id)
    assert completed is None
    assert nation.current_research_months_left == 2

    nation, completed = await tech_service.advance_research(session_id)
    assert completed is None
    assert nation.current_research_months_left == 1

    nation, completed = await tech_service.advance_research(session_id)
    assert completed == "agriculture"
    assert nation.current_research == ""
    assert nation.economy > before.economy  # agriculture's stat effects were applied

    state = await tech_service.get_research_state(session_id)
    assert "agriculture" in state["researched"]


async def test_cannot_research_same_tech_twice(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)
    await tech_service.start_research(session_id, "agriculture")
    for _ in range(3):
        await tech_service.advance_research(session_id)

    with pytest.raises(tech_service.TechError):
        await tech_service.start_research(session_id, "agriculture")
