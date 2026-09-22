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


async def test_get_rivals_is_idempotent_and_only_seeds_missing_ones(session_id):
    # Regression test: _get_rivals used to be "if not rivals: seed all 3", which is
    # only safe if nothing else could race it. It's now "seed whichever rival_ids are
    # missing" so a partially-seeded session (or a real race) can't end up with
    # duplicate rows for the same rival_id.
    async with async_session_maker() as db:
        db.add(diplomacy_service.RivalNation(session_id=session_id, **diplomacy_service.RIVAL_TEMPLATES[0]))
        await db.commit()

    rivals = await diplomacy_service.get_rivals(session_id)
    assert len(rivals) == 3
    assert len({r["rival_id"] for r in rivals}) == 3  # no duplicates

    rivals_again = await diplomacy_service.get_rivals(session_id)
    assert len(rivals_again) == 3


async def test_world_relationships_never_self_pair_even_with_duplicate_rival_rows(session_id):
    # Regression test for a real bug this project shipped: a seeding race left two
    # rows for the same rival_id in the database, and combinations() over a list
    # with repeated ids produced nonsense pairs like ("동쪽 부족 연맹", "동쪽 부족 연맹").
    # _get_relationships must dedupe before pairing regardless of upstream duplicates.
    await diplomacy_service.get_rivals(session_id)  # seeds the normal 3
    async with async_session_maker() as db:
        db.add(diplomacy_service.RivalNation(session_id=session_id, **diplomacy_service.RIVAL_TEMPLATES[0]))
        await db.commit()  # manufacture the duplicate-row bug directly

    relationships = await diplomacy_service.get_world_relationships(session_id)
    assert len(relationships) == 3  # still exactly 3 pairs for 3 rivals, not 6+
    assert all(r["rival_a"] != r["rival_b"] for r in relationships)


async def test_rivals_are_seeded_with_the_correct_personality_per_template(session_id):
    rivals = await diplomacy_service.get_rivals(session_id)
    by_id = {r["rival_id"]: r["personality"] for r in rivals}
    for template in diplomacy_service.RIVAL_TEMPLATES:
        assert by_id[template["rival_id"]] == template["personality"]


async def test_aggressive_personality_raises_effective_aggression_chance(session_id, monkeypatch):
    # Same military ratio, same base chance — only personality differs — so an
    # aggressive rival should end up with a strictly higher aggression_chance than
    # an isolationist one. Verified indirectly: aggressive personality declares war
    # far more often across many trials at a roll that would only clear the
    # aggressive threshold.
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await _set_military(session_id, 10.0)
    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        for r in rivals:
            r.military = 10.0  # equal ratio to the player for every rival
        await db.commit()

    # A roll that clears an aggressive rival's chance but not an isolationist one:
    # base=0.01, ratio=1.0 -> aggressive (x2.5) = 0.025, isolationist (x0.2) = 0.002.
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.01)
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)  # pin stat drift

    nation, rivals, reports, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    eastern = next(r for r in rivals if r["rival_id"] == "eastern_tribes")  # aggressive
    southern = next(r for r in rivals if r["rival_id"] == "southern_city_state")  # isolationist
    assert eastern["relationship"] == "war"
    assert southern["relationship"] == "peace"


async def test_world_war_chance_is_higher_between_two_aggressive_leaning_rivals(session_id, monkeypatch):
    # eastern_tribes (aggressive, x2.0) vs northern_kingdom (economic, x0.5) averages
    # to 1.25x world war chance; a roll placed between the plain and personality-
    # adjusted thresholds should only clear for pairs with a high enough average.
    await diplomacy_service.get_rivals(session_id)
    roll = diplomacy_service.WORLD_WAR_CHANCE_PER_MONTH * 1.1  # clears eastern+northern's 1.25x, not most others
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: roll)
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)

    await diplomacy_service.advance_world(session_id)
    relationships = await diplomacy_service.get_world_relationships(session_id)
    et_nk = next(
        r
        for r in relationships
        if {r["rival_a"], r["rival_b"]} == {"eastern_tribes", "northern_kingdom"}
    )
    assert et_nk["relationship"] == "war"


async def test_advance_world_returns_outcomes_for_ongoing_rival_wars(session_id, monkeypatch):
    await diplomacy_service.get_rivals(session_id)
    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        et = next(r for r in rivals if r.rival_id == "eastern_tribes")
        nk = next(r for r in rivals if r.rival_id == "northern_kingdom")
        et.military = 100.0
        nk.military = 10.0
        rels = await diplomacy_service._get_relationships(db, session_id, [r.rival_id for r in rivals])
        rels[("eastern_tribes", "northern_kingdom")].relationship = "war"
        await db.commit()

    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.99)  # never end/start anything else
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)  # low end for both -> military decides

    news, outcomes = await diplomacy_service.advance_world(session_id)
    assert ("eastern_tribes", "northern_kingdom", "동쪽 부족 연맹", "북방 왕국") in outcomes


async def test_mutual_defense_pulls_an_ally_into_the_players_war(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")

    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        rels = await diplomacy_service._get_relationships(db, session_id, [r.rival_id for r in rivals])
        rels[("eastern_tribes", "northern_kingdom")].relationship = "alliance"
        await db.commit()

    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.0)  # clears any positive chance
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)

    nation, rivals, reports, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    northern = next(r for r in rivals if r["rival_id"] == "northern_kingdom")
    assert northern["relationship"] == "war"
    assert any("동맹국을 지키기 위해 참전" in r for r in reports)


async def test_mutual_defense_never_triggers_without_an_allied_war(session_id, monkeypatch):
    # No alliance exists yet — even a roll that would clear any positive chance must
    # not pull anyone into a war they have no reason to join.
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")

    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)
    # random() still governs the ordinary aggression/exhaustion rolls too — pin it high
    # enough to clear nothing so only the (absent) mutual-defense path is exercised.
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.999)

    nation, rivals, reports, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    northern = next(r for r in rivals if r["rival_id"] == "northern_kingdom")
    assert northern["relationship"] == "peace"
    assert not any("동맹국을 지키기 위해 참전" in r for r in reports)
