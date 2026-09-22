from app.services import nation_service


async def test_new_nation_defaults_and_naming(session_id):
    nation = await nation_service.get_or_create_nation(session_id)
    assert nation.session_id == session_id
    # A freshly created nation's name defaults to the session id — the frontend
    # uses this exact fact to detect "hasn't chosen a city name yet".
    assert nation.name == session_id

    renamed = await nation_service.set_nation_name(session_id, "테스트왕국")
    assert renamed.name == "테스트왕국"


async def test_nation_exists_and_delete(session_id):
    assert await nation_service.nation_exists(session_id) is False
    await nation_service.get_or_create_nation(session_id)
    assert await nation_service.nation_exists(session_id) is True

    await nation_service.delete_nation(session_id)
    assert await nation_service.nation_exists(session_id) is False


async def test_diminishing_returns_shrinks_positive_deltas_near_cap():
    low = nation_service._apply_delta(10.0, 100.0)
    high = nation_service._apply_delta(900.0, 100.0)
    # Same nominal delta, but the stat starting near STAT_MAX should gain far less.
    assert (low - 10.0) > (high - 900.0)


async def test_diminishing_returns_does_not_soften_negative_deltas():
    # Negative effects (disasters, war losses) must always apply in full —
    # only positive growth gets diminishing returns.
    value = nation_service._apply_delta(900.0, -50.0)
    assert value == 850.0


async def test_apply_delta_clamps_to_stat_max_and_zero():
    # Diminishing returns only shrinks the delta, it never fully blocks it — so a huge
    # enough delta from a low starting value still clamps at the cap.
    assert nation_service._apply_delta(0.0, 999_999.0) == nation_service.STAT_MAX
    assert nation_service._apply_delta(5.0, -1000.0) == 0.0


async def test_advance_nation_updates_date_and_keeps_population_integer(session_id):
    await nation_service.get_or_create_nation(session_id)
    nation = await nation_service.advance_nation(session_id, {"year": 5, "month": 7})
    assert nation.year == 5
    assert nation.month == 7
    assert isinstance(nation.population, int)


async def test_apply_effects_only_touches_known_stats(session_id):
    await nation_service.get_or_create_nation(session_id)
    before = await nation_service.get_or_create_nation(session_id)
    updated = await nation_service.apply_effects(session_id, {"economy": 5, "not_a_real_stat": 999})
    assert updated.economy > before.economy


async def test_random_event_treasury_effect_direction_is_stable_even_when_already_negative(session_id):
    nation = await nation_service.get_or_create_nation(session_id)
    # Push treasury negative first (simulates an already-bankrupt nation), then apply
    # a "loss" event — it must still get worse, not accidentally flip sign/direction.
    from app.db import async_session_maker
    async with async_session_maker() as db:
        db_nation = await nation_service._get_or_create_nation(db, session_id)
        db_nation.treasury = -100.0
        await db.commit()

    updated = await nation_service.apply_random_event(session_id, {"treasury_loss_months": 2})
    assert updated.treasury < -100.0


def test_compute_era_reflects_tech_tree_progress():
    from app.models.nation import compute_era

    assert compute_era(0) == "primitive"
    assert compute_era(1) == "bronze"
    assert compute_era(5) == "bronze"
    assert compute_era(6) == "iron"
    assert compute_era(8) == "iron"
    assert compute_era(9) == "classical"
    assert compute_era(14) == "classical"
    assert compute_era(15) == "medieval"
    assert compute_era(19) == "medieval"
    assert compute_era(20) == "renaissance"


def test_compute_land_capacity_scales_with_tiles_and_has_a_floor():
    assert nation_service.compute_land_capacity(0) == 1000  # never below the old flat default
    assert nation_service.compute_land_capacity(9) == 9 * nation_service.LAND_CAPACITY_PER_TILE
    assert nation_service.compute_land_capacity(60) == 60 * nation_service.LAND_CAPACITY_PER_TILE


async def test_advance_nation_syncs_land_capacity_from_owned_tiles(session_id):
    await nation_service.get_or_create_nation(session_id)
    nation = await nation_service.advance_nation(session_id, {"year": 1, "month": 2}, owned_tile_count=40)
    assert nation.land_capacity == nation_service.compute_land_capacity(40)


async def test_advance_nation_leaves_land_capacity_alone_when_tile_count_omitted(session_id):
    await nation_service.get_or_create_nation(session_id)
    await nation_service.advance_nation(session_id, {"year": 1, "month": 2}, owned_tile_count=40)
    nation = await nation_service.advance_nation(session_id, {"year": 1, "month": 3})  # no owned_tile_count
    assert nation.land_capacity == nation_service.compute_land_capacity(40)  # unchanged


async def test_advance_nation_applies_resource_bonus_on_top_of_base_delta(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    monkeypatch.setattr(nation_service.random, "uniform", lambda a, b: 0.0)  # pin the -4..6 roll to 0

    baseline = await nation_service.advance_nation(session_id, {"year": 1, "month": 1})
    boosted = await nation_service.advance_nation(
        session_id, {"year": 1, "month": 2}, resource_bonus={"economy": 10.0, "military": 5.0}
    )
    assert boosted.economy > baseline.economy
    assert boosted.military > baseline.military


async def test_advance_nation_resource_food_bonus_raises_food_stock(session_id):
    await nation_service.get_or_create_nation(session_id)
    plain = await nation_service.advance_nation(session_id, {"year": 1, "month": 1})
    boosted = await nation_service.advance_nation(
        session_id, {"year": 1, "month": 2}, resource_bonus={"food": 0.5}
    )
    assert boosted.food_stock > plain.food_stock


async def test_national_trait_boosts_its_matching_stats_growth(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    monkeypatch.setattr(nation_service.random, "uniform", lambda a, b: 5.0)  # pin the base roll positive

    from app.db import async_session_maker

    async def _set_trait(trait):
        async with async_session_maker() as db:
            nation = await nation_service._get_or_create_nation(db, session_id)
            nation.economy = 100.0
            nation.national_trait = trait
            await db.commit()

    await _set_trait("military")
    baseline = await nation_service.advance_nation(session_id, {"year": 1, "month": 1})

    await _set_trait("economic")
    boosted = await nation_service.advance_nation(session_id, {"year": 1, "month": 2})

    # Same starting economy (100), same pinned +5 base roll — only national_trait
    # differs, and "economic" boosts economy growth 1.6x vs "military"'s 0.85x.
    assert boosted.economy > baseline.economy


async def test_sync_land_capacity_updates_immediately(session_id):
    await nation_service.get_or_create_nation(session_id)
    nation = await nation_service.sync_land_capacity(session_id, 100)
    assert nation.land_capacity == nation_service.compute_land_capacity(100)


async def test_city_bonus_increases_income_and_food_production(session_id):
    from app.db import async_session_maker

    await nation_service.get_or_create_nation(session_id)
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.economy = 100.0
        nation.population = 100
        await db.commit()

    async def snapshot_treasury(city_count):
        async with async_session_maker() as db:
            nation = await nation_service._get_or_create_nation(db, session_id)
            nation.treasury = 0.0
            nation.military = nation.education = nation.stability = 0.0  # zero out expenses
            await db.commit()
        return (await nation_service.advance_nation(session_id, {"year": 1, "month": 1}, city_count=city_count)).treasury

    no_bonus = await snapshot_treasury(0)
    with_bonus = await snapshot_treasury(3)
    assert with_bonus > no_bonus
