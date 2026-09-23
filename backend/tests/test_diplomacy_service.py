import pytest

from app.db import async_session_maker
from app.models.territory import OwnedTile
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

    nation, rivals, reports, war_outcomes, peace_offers = await diplomacy_service.advance_rivals(
        session_id, {"year": 1, "month": 2}
    )
    assert len(rivals) == 3
    assert isinstance(reports, list)
    # Not at war with anyone yet, so no combat outcomes to resolve into tile captures.
    assert war_outcomes == []
    assert peace_offers == []


async def test_advance_rivals_at_war_charges_upkeep_and_reports_result(session_id):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    await _set_military(session_id, 500.0)  # overwhelming military so the outcome is deterministic-ish

    nation, rivals, reports, war_outcomes, _ = await diplomacy_service.advance_rivals(
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
        nation, rivals, reports, _, _ = await diplomacy_service.advance_rivals(
            session_id, {"year": 1, "month": month}
        )
        target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
        assert target["war_months"] == month
        assert target["relationship"] == "war"


async def test_war_exhaustion_sends_a_peace_offer_instead_of_ending_the_war_outright(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")
    # Always below any chance check — also makes the other two (still at peace) rivals
    # declare war on the player this same tick, which is fine: this test only asserts
    # things about eastern_tribes specifically.
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.0)

    nation, rivals, reports, war_outcomes, peace_offers = await diplomacy_service.advance_rivals(
        session_id, {"year": 1, "month": 2}
    )
    target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    # The war does NOT end on its own anymore — it stays "war" until the player
    # actually accepts the offer (see accept_peace_offer / session_manager).
    assert target["relationship"] == "war"
    assert peace_offers == [{"rival_id": "eastern_tribes", "rival_name": "동쪽 부족 연맹"}]
    assert any("평화 협정을 제안" in r for r in reports)
    assert ("player", "eastern_tribes", "동쪽 부족 연맹") not in war_outcomes  # offer pre-empted combat


async def test_accept_peace_offer_ends_the_war(session_id):
    await diplomacy_service.get_rivals(session_id)
    await diplomacy_service.declare_war(session_id, "eastern_tribes")

    rivals = await diplomacy_service.accept_peace_offer(session_id, "eastern_tribes")
    target = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    assert target["relationship"] == "peace"
    assert target["war_months"] == 0


async def test_accept_peace_offer_on_unknown_rival_raises(session_id):
    await diplomacy_service.get_rivals(session_id)
    with pytest.raises(diplomacy_service.DiplomacyError):
        await diplomacy_service.accept_peace_offer(session_id, "not_a_real_rival")


async def test_rival_national_trait_boosts_its_matching_stat_growth(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: 5.0)  # pin the base roll positive
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.99)  # never trigger any war/aggression roll

    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        et = next(r for r in rivals if r.rival_id == "eastern_tribes")
        nk = next(r for r in rivals if r.rival_id == "northern_kingdom")
        et.military, et.national_trait = 100.0, "military"
        nk.military, nk.national_trait = 100.0, "economic"
        await db.commit()

    _, rivals, _, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    eastern = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    northern = next(r for r in rivals if r["rival_id"] == "northern_kingdom")
    # Same starting military (100), same pinned +5 base roll — military-trait eastern
    # should out-grow economic-trait northern on the military stat specifically.
    assert eastern["military"] > northern["military"]


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

    nation, rivals, reports, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
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

    nation, rivals, reports, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
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

    nation, rivals, reports, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
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

    nation, rivals, reports, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    northern = next(r for r in rivals if r["rival_id"] == "northern_kingdom")
    assert northern["relationship"] == "war"
    assert any("동맹국을 지키기 위해 참전" in r for r in reports)


def test_rival_growth_factor_scales_with_tile_count_and_caps():
    assert diplomacy_service.rival_growth_factor(diplomacy_service.RIVAL_STARTING_TILE_COUNT) == 1.0
    assert diplomacy_service.rival_growth_factor(0) == diplomacy_service.rival_growth_factor(1)  # floored at 1 tile
    big = diplomacy_service.rival_growth_factor(diplomacy_service.RIVAL_STARTING_TILE_COUNT * 10_000)
    assert big == diplomacy_service.RIVAL_GROWTH_FACTOR_CAP


async def test_rival_with_more_territory_grows_economy_faster_than_a_small_rival(session_id, monkeypatch):
    # The player's economy/military growth scales with population_factor (itself driven
    # by owned tiles); rivals had no equivalent, letting the player structurally
    # out-grow every rival regardless of territory. eastern_tribes gets a big block of
    # extra tiles, northern_kingdom stays at its starting size — only that should decide
    # who grows economy faster given the same pinned base roll.
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: 4.0)  # pin the base roll positive
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.99)  # never trigger any war/aggression roll

    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        for r in rivals:
            r.economy = 100.0
            r.national_trait = "military"  # same trait for both, so it can't explain the difference
        for i in range(50):
            db.add(OwnedTile(session_id=session_id, x=100 + i, y=100, owner="eastern_tribes"))
        await db.commit()

    _, rivals, _, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    eastern = next(r for r in rivals if r["rival_id"] == "eastern_tribes")  # 50 tiles
    northern = next(r for r in rivals if r["rival_id"] == "northern_kingdom")  # still 0 tracked tiles
    assert eastern["economy"] > northern["economy"]


async def test_difficulty_scales_rival_economy_growth(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: 4.0)  # pin the base roll positive
    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.99)  # never trigger any war/aggression roll

    async def _run(difficulty):
        async with async_session_maker() as db:
            nation = await nation_service._get_or_create_nation(db, session_id)
            nation.difficulty = difficulty
            rivals = await diplomacy_service._get_rivals(db, session_id)
            for r in rivals:
                r.economy = 100.0
            await db.commit()
        _, rivals, _, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
        return next(r for r in rivals if r["rival_id"] == "eastern_tribes")["economy"]

    hell_economy = await _run("hell")
    easy_economy = await _run("easy")
    assert hell_economy > easy_economy


async def test_hell_difficulty_makes_a_rival_strike_first_when_easy_would_not(session_id, monkeypatch):
    # Same military ratio (1.0x, base chance 0.01) for every rival — a roll of 0.015
    # only clears hell's boosted chance (0.01 * 2.2 = 0.022), not easy's (0.01 * 0.5 = 0.005).
    await nation_service.get_or_create_nation(session_id)
    await diplomacy_service.get_rivals(session_id)
    await _set_military(session_id, 10.0)
    async with async_session_maker() as db:
        rivals = await diplomacy_service._get_rivals(db, session_id)
        for r in rivals:
            r.military = 10.0
            r.personality = "neutral"  # not a real personality -> _trait() falls back to 1.0x
        await db.commit()

    monkeypatch.setattr(diplomacy_service.random, "random", lambda: 0.015)
    monkeypatch.setattr(diplomacy_service.random, "uniform", lambda a, b: a)  # pin stat drift

    async def _run(difficulty):
        async with async_session_maker() as db:
            nation = await nation_service._get_or_create_nation(db, session_id)
            nation.difficulty = difficulty
            rivals = await diplomacy_service._get_rivals(db, session_id)
            for r in rivals:
                r.relationship = "peace"
            await db.commit()
        _, rivals, _, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
        return next(r for r in rivals if r["rival_id"] == "eastern_tribes")["relationship"]

    assert await _run("hell") == "war"
    assert await _run("easy") == "peace"


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

    nation, rivals, reports, _, _ = await diplomacy_service.advance_rivals(session_id, {"year": 1, "month": 2})
    northern = next(r for r in rivals if r["rival_id"] == "northern_kingdom")
    assert northern["relationship"] == "peace"
    assert not any("동맹국을 지키기 위해 참전" in r for r in reports)
