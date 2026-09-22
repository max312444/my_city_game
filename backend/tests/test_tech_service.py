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


def test_tech_tree_has_no_duplicate_ids():
    ids = [t["id"] for t in tech_service.TECH_TREE]
    assert len(ids) == len(set(ids))


def test_tech_tree_prereqs_all_reference_real_techs():
    ids = {t["id"] for t in tech_service.TECH_TREE}
    for tech in tech_service.TECH_TREE:
        for prereq in tech["prereqs"]:
            assert prereq in ids, f"{tech['id']} lists unknown prereq {prereq}"


def test_tech_tree_has_no_cycles():
    # A topological sort must be possible — walk prereqs, marking each tech visited
    # only after all of its prereqs are; a cycle would make some tech unreachable.
    by_id = {t["id"]: t for t in tech_service.TECH_TREE}
    resolved = set()

    def resolve(tech_id, stack):
        if tech_id in resolved:
            return
        assert tech_id not in stack, f"cycle detected involving {tech_id}"
        stack.add(tech_id)
        for prereq in by_id[tech_id]["prereqs"]:
            resolve(prereq, stack)
        stack.remove(tech_id)
        resolved.add(tech_id)

    for tech_id in by_id:
        resolve(tech_id, set())
    assert resolved == set(by_id)


def test_original_six_techs_are_unchanged_for_backward_compatibility():
    # These 6 existed before the tree was expanded — real saves already have some of
    # them in researched_techs (a plain comma-joined id string), so their id/cost/
    # duration/effects must never change, only new nodes get added around them.
    originals = {
        "agriculture": {"cost": 300, "duration_months": 3, "prereqs": []},
        "writing_system": {"cost": 300, "duration_months": 3, "prereqs": []},
        "bronze_weapons": {"cost": 400, "duration_months": 4, "prereqs": []},
        "irrigation": {"cost": 1200, "duration_months": 7, "prereqs": ["agriculture"]},
        "code_of_law": {"cost": 1200, "duration_months": 7, "prereqs": ["writing_system"]},
        "iron_weapons": {"cost": 1500, "duration_months": 8, "prereqs": ["bronze_weapons"]},
    }
    for tech_id, expected in originals.items():
        tech = tech_service.TECH_BY_ID[tech_id]
        assert tech["cost"] == expected["cost"]
        assert tech["duration_months"] == expected["duration_months"]
        assert tech["prereqs"] == expected["prereqs"]


async def test_can_research_a_deep_chain_all_the_way_to_a_tier4_tech(session_id):
    # agriculture -> currency -> road_network -> trade_routes, then paired with
    # bureaucracy (code_of_law + currency) to reach banking (tier 4).
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 1_000_000)

    chain = [
        "agriculture",
        "writing_system",
        "code_of_law",
        "currency",
        "road_network",
        "trade_routes",
        "bureaucracy",
        "banking",
    ]
    for tech_id in chain:
        nation, _ = await tech_service.start_research(session_id, tech_id)
        duration = tech_service.TECH_BY_ID[tech_id]["duration_months"]
        for _ in range(duration):
            nation, completed = await tech_service.advance_research(session_id)
        assert completed == tech_id

    state = await tech_service.get_research_state(session_id)
    assert set(chain) <= set(state["researched"])
