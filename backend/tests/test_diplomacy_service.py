import pytest

from app.db import async_session_maker
from app.services import diplomacy_service, nation_service


async def _set_military(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.military = amount
        await db.commit()


async def test_get_rivals_creates_the_fixed_three_rivals_on_first_call(session_id):
    rivals = await diplomacy_service.get_rivals(session_id)
    assert len(rivals) == 3
    assert {r["rival_id"] for r in rivals} == {t["rival_id"] for t in diplomacy_service.RIVAL_TEMPLATES}
    assert all(r["relationship"] == "peace" for r in rivals)


async def test_declare_war_sets_relationship_and_penalizes_stability(session_id):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)

    nation_before = await nation_service.get_or_create_nation(session_id)
    nation, rivals = await diplomacy_service.declare_war(session_id, "eastern_tribes")

    target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    assert target["relationship"] == "war"
    assert nation.stability <= nation_before.stability


async def test_declare_war_twice_raises(session_id):
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    with pytest.raises(diplomacy_service.DiplomacyError):
        await diplomacy_service.declare_war(session_id, "eastern_tribes")


async def test_declare_war_on_unknown_rival_raises(session_id):
    await diplomacy_service.get_rivals(session_id)
    with pytest.raises(diplomacy_service.DiplomacyError):
        await diplomacy_service.declare_war(session_id, "not_a_real_rival")


async def test_propose_peace_without_war_raises(session_id):
    await diplomacy_service.get_rivals(session_id)
    with pytest.raises(diplomacy_service.DiplomacyError):
        await diplomacy_service.propose_peace(session_id, "eastern_tribes")


async def test_propose_peace_after_war_can_succeed_or_fail_but_never_errors(session_id):
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    accepted, rivals = await diplomacy_service.propose_peace(session_id, "eastern_tribes")
    assert isinstance(accepted, bool)
    target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    assert target["relationship"] == ("peace" if accepted else "war")


async def test_advance_rivals_runs_and_returns_expected_shape(session_id):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)

    nation, rivals, reports, war_outcomes = await diplomacy_service.advance_rivals(
        session_id, {"year": 1, "month": 2}
    )
    assert len(rivals) == 3
    assert isinstance(reports, list)
    # Not at war with anyone yet, so no combat outcomes to resolve into tile captures.
    assert war_outcomes == []


async def test_advance_rivals_at_war_charges_upkeep_and_reports_result(session_id):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    await _set_military(session_id, 500.0)  # overwhelming military so the outcome is deterministic-ish

    nation, rivals, reports, war_outcomes = await diplomacy_service.advance_rivals(
        session_id, {"year": 1, "month": 2}
    )
    assert any("전투" in r for r in reports)
    assert war_outcomes == [("player", "eastern_tribes", "동쪽 부족 연맹")]


async def test_declare_war_resets_war_months(session_id):
    await diplomacy_service.get_rivals(session_id)
    nation, rivals = await diplomacy_service.declare_war(session_id, "eastern_tribes")
    target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    assert target["war_months"] == 0


async def test_war_months_increments_each_month_at_war(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    # Never below any chance check, so the war simply continues each month.
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.99)

    for month in range(1, 4):
        nation, rivals, reports, _ = await diplomacy_service.advance_rivals(
            session_id, {"year": 1, "month": month}
        )
        target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
        assert target["war_months"] == month
        assert target["relationship"] == "war"


async def test_war_exhaustion_can_end_a_long_war_in_peace(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    # Always below any chance check — also makes the other two (still at peace) rivals
    # declare war on the player this same tick, which is fine: this test only asserts
    # things about eastern_tribes specifically.
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.0)

    nation, rivals, reports, war_outcomes = await diplomacy_service.advance_rivals(
        session_id, {"year": 1, "month": 2}
    )
    target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    assert target["relationship"] == "peace"
    assert target["war_months"] == 0
    assert any("지쳐 평화" in r for r in reports)
    assert ("player", "eastern_tribes", "동쪽 부족 연맹") not in war_outcomes  # peace pre-empted combat


async def test_rival_can_declare_war_on_the_player_when_much_stronger(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await _set_military(session_id, 1.0)  # player is weak...
    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        for r in rivals:
            r.military = 1000.0  # ...every rival is overwhelming
        await db.commit()

    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.0)  # always clears the aggression roll

    nation, rivals, reports, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    assert all(r["relationship"] == "war" for r in rivals)
    assert any("선전포고" in r for r in reports)


async def test_rival_never_declares_war_unprompted_when_much_weaker(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await _set_military(session_id, 1000.0)  # player overwhelmingly stronger than every rival
    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        for r in rivals:
            r.military = 0.0  # ratio is exactly zero -> aggression_chance is exactly zero
        await db.commit()

    # 0.0 would trigger any *positive* chance check — proving even that can't start a war here.
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.0)
    # Also pin the monthly stat-drift roll so military stays pinned at 0 instead of
    # drifting upward before the aggression check runs.
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)

    nation, rivals, reports, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    assert all(r["relationship"] == "peace" for r in rivals)
    assert not any("선전포고" in r for r in reports)
