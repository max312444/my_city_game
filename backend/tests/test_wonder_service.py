import pytest

from app.db import async_session_maker
from app.services import diplomacy_service, nation_service, tech_service, wonder_service


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


async def _finish_tech(session_id, tech_id):
    await tech_service.start_research(session_id, tech_id)
    for _ in range(tech_service.TECH_BY_ID[tech_id]["duration_months"]):
        await tech_service.advance_research(session_id)


def test_wonder_ids_have_no_duplicates():
    ids = [w["id"] for w in wonder_service.WONDERS]
    assert len(ids) == len(set(ids))


async def test_start_wonder_uses_slow_duration_without_the_boost_tech(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)

    nation, duration = await wonder_service.start_wonder(session_id, "stonehenge")
    assert duration == wonder_service.WONDER_BY_ID["stonehenge"]["base_duration_months"]
    assert nation.current_wonder == "stonehenge"


async def test_start_wonder_uses_fast_duration_with_the_boost_tech(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)
    await _finish_tech(session_id, "writing_system")
    await _finish_tech(session_id, "astronomy")  # stonehenge's boost_tech

    nation, duration = await wonder_service.start_wonder(session_id, "stonehenge")
    assert duration == wonder_service.WONDER_BY_ID["stonehenge"]["fast_duration_months"]


async def test_start_wonder_rejects_already_claimed(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)

    async with async_session_maker() as db:
        from app.models.wonder import WonderClaim

        db.add(WonderClaim(session_id=session_id, wonder_id="stonehenge", claimed_by="eastern_tribes"))
        await db.commit()

    with pytest.raises(wonder_service.WonderError, match="이미 다른 국가"):
        await wonder_service.start_wonder(session_id, "stonehenge")


async def test_start_wonder_rejects_second_concurrent_wonder(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)
    await wonder_service.start_wonder(session_id, "stonehenge")
    with pytest.raises(wonder_service.WonderError, match="이미 건설 중"):
        await wonder_service.start_wonder(session_id, "pyramids")


async def test_advance_wonder_completes_and_claims_it_for_the_player(session_id):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)
    await _finish_tech(session_id, "writing_system")
    await _finish_tech(session_id, "astronomy")
    before = await nation_service.get_or_create_nation(session_id)

    _, duration = await wonder_service.start_wonder(session_id, "stonehenge")
    for _ in range(duration - 1):
        nation, completed = await wonder_service.advance_wonder(session_id)
        assert completed is None

    nation, completed = await wonder_service.advance_wonder(session_id)
    assert completed == "stonehenge"
    assert nation.stability > before.stability

    state = await wonder_service.get_wonder_state(session_id)
    assert state["claims"]["stonehenge"] == "player"


async def test_rival_claiming_a_wonder_cancels_the_players_in_progress_attempt(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)
    rivals = await diplomacy_service.get_rivals(session_id)

    await wonder_service.start_wonder(session_id, "stonehenge")

    # Pinned to always succeed, so every still-unclaimed wonder (all 5) gets grabbed
    # this same tick — the assertion only cares about stonehenge specifically, since
    # that's the one the player was mid-construction on.
    monkeypatch.setattr(wonder_service.random, "random", lambda: 0.0)
    events = await wonder_service.advance_rival_wonders(session_id, rivals)

    stonehenge_event = next(e for e in events if e["wonder_id"] == "stonehenge")
    assert stonehenge_event["sabotaged_player"] is True

    nation, completed = await wonder_service.advance_wonder(session_id)
    assert completed is None
    assert nation.current_wonder == ""  # investment lost, not silently kept


async def test_rival_wonder_claim_ignores_defeated_rivals(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    rivals = await diplomacy_service.get_rivals(session_id)
    for r in rivals:
        r["relationship"] = "defeated"

    monkeypatch.setattr(wonder_service.random, "random", lambda: 0.0)
    events = await wonder_service.advance_rival_wonders(session_id, rivals)
    assert events == []


async def test_delete_claims_removes_all_rows_for_the_session(session_id):
    async with async_session_maker() as db:
        from app.models.wonder import WonderClaim

        db.add(WonderClaim(session_id=session_id, wonder_id="stonehenge", claimed_by="player"))
        await db.commit()

    await wonder_service.delete_claims(session_id)
    state = await wonder_service.get_wonder_state(session_id)
    assert state["claims"] == {}
