import pytest

from app.core import session_manager
from app.db import async_session_maker
from app.models.territory import OwnedTile
from app.services import city_service, map_service, nation_service, territory_service


def test_compute_resource_bonus_sums_only_resources_near_capital_or_cities():
    map_data = {
        "capital": {"x": 5, "y": 5},
        "resources": [
            {"x": 5, "y": 6, "type": "gold_mine"},  # adjacent to capital -> counts
            {"x": 20, "y": 20, "type": "iron_ore"},  # far from everything -> ignored
            {"x": 10, "y": 10, "type": "timber"},  # adjacent to the city below -> counts
        ],
    }
    player_cities = [{"x": 10, "y": 11}]

    bonus = session_manager._compute_resource_bonus(map_data, player_cities)
    assert bonus["economy"] == pytest.approx(6.0 + 4.0)
    assert "military" not in bonus  # iron_ore was too far to count


def test_compute_resource_bonus_with_no_resources_returns_empty_dict():
    assert session_manager._compute_resource_bonus({"capital": {"x": 0, "y": 0}}, []) == {}


async def test_resolve_territory_changes_no_war_no_capture(session_id):
    await nation_service.get_or_create_nation(session_id)
    map_data = await map_service.get_or_create_map(session_id)
    rivals = [{"rival_id": rc["rival_id"], "economy": 0.0} for rc in map_data["rival_capitals"]]

    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, rivals, [], [], {"year": 1, "month": 1}
    )
    assert reports == []
    assert changed is False  # 0 economy, 0 player_economy -> 0% expansion chance either way
    assert cities_changed is False  # no rival owns anywhere near enough tiles yet


async def test_resolve_territory_changes_auto_expands_player_territory(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await map_service.get_or_create_map(session_id)
    before = await territory_service.get_owned_tiles(session_id)

    monkeypatch.setattr(session_manager.random, "random", lambda: 0.0)  # clears the player's expansion roll

    _, changed, _ = await session_manager._resolve_territory_changes(
        session_id, [], [], [], {"year": 1, "month": 1}, player_economy=500.0
    )
    assert changed is True
    after = await territory_service.get_owned_tiles(session_id)
    assert len(after) == len(before) + 1


async def test_resolve_territory_changes_player_never_auto_expands_at_zero_economy(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    await map_service.get_or_create_map(session_id)
    before = await territory_service.get_owned_tiles(session_id)

    monkeypatch.setattr(session_manager.random, "random", lambda: 0.0)

    _, changed, _ = await session_manager._resolve_territory_changes(
        session_id, [], [], [], {"year": 1, "month": 1}, player_economy=0.0
    )
    assert changed is False
    after = await territory_service.get_owned_tiles(session_id)
    assert len(after) == len(before)


async def test_resolve_territory_changes_reports_and_broadcasts_capture(session_id):
    # Seed the player and a rival touching borders *before* get_or_create_map ever runs
    # for this session — its own (idempotent) seeding step will then leave these custom
    # positions alone, since ensure_initial_territory/ensure_rival_territory both no-op
    # once an owner already has tiles.
    await nation_service.get_or_create_nation(session_id)
    await territory_service.ensure_initial_territory(session_id, 10, 10)  # owns x:9-11,y:9-11
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)  # owns x:12-14,y:9-11

    war_outcomes = [("player", "eastern_tribes", "테스트라이벌")]
    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, [], war_outcomes, [], {"year": 1, "month": 1}
    )

    assert changed is True
    assert any("테스트라이벌" in r and "점령" in r for r in reports)


async def test_resolve_territory_changes_captures_a_city_on_the_captured_tile(session_id):
    await nation_service.get_or_create_nation(session_id)
    await territory_service.ensure_initial_territory(session_id, 10, 10)  # owns x:9-11,y:9-11
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)  # owns x:12-14,y:9-11
    async with async_session_maker() as db:
        from app.models.city import City

        db.add(
            City(
                session_id=session_id,
                name="언덕마을",
                x=12,
                y=11,
                owner="eastern_tribes",
                founded_year=1,
                founded_month=1,
            )
        )
        await db.commit()

    war_outcomes = [("player", "eastern_tribes", "동쪽 부족 연맹")]
    siege_targets = {"eastern_tribes": (12, 11)}
    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, [], war_outcomes, [], {"year": 1, "month": 1}, siege_targets=siege_targets
    )

    assert changed is True
    assert cities_changed is True
    assert any("언덕마을" in r and "점령" in r for r in reports)
    city = (await city_service.get_cities(session_id))[0]
    assert city["owner"] == "player"
    assert "eastern_tribes" not in siege_targets  # objective reached, cleared automatically


async def test_resolve_territory_changes_falls_back_when_siege_target_unreachable(session_id):
    await nation_service.get_or_create_nation(session_id)
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)

    war_outcomes = [("player", "eastern_tribes", "동쪽 부족 연맹")]
    siege_targets = {"eastern_tribes": (999, 999)}  # nowhere near a valid candidate
    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, [], war_outcomes, [], {"year": 1, "month": 1}, siege_targets=siege_targets
    )

    assert changed is True  # still captures a random border tile instead of doing nothing
    assert siege_targets["eastern_tribes"] == (999, 999)  # unreached target stays put


async def test_resolve_territory_changes_transfers_a_captured_city_in_a_world_war(session_id):
    await nation_service.get_or_create_nation(session_id)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 10, 10)  # owns x9-11,y9-11
    async with async_session_maker() as db:
        from app.models.city import City

        # northern_kingdom gets exactly two tiles: (12, 11) — adjacent to eastern's
        # block and where its city sits — and a far-away decoy that's NOT adjacent, so
        # (12, 11) is the only valid capture candidate (deterministic) while still
        # keeping northern_kingdom above the 1-tile "last stand" elimination threshold
        # (this test is about the city-transfer message, not elimination).
        db.add(OwnedTile(session_id=session_id, x=12, y=11, owner="northern_kingdom"))
        db.add(OwnedTile(session_id=session_id, x=50, y=50, owner="northern_kingdom"))
        db.add(
            City(
                session_id=session_id,
                name="변경진",
                x=12,
                y=11,
                owner="northern_kingdom",
                founded_year=1,
                founded_month=1,
            )
        )
        await db.commit()

    world_war_outcomes = [("eastern_tribes", "northern_kingdom", "동쪽 부족 연맹", "북방 왕국")]
    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, [], [], world_war_outcomes, {"year": 1, "month": 1}
    )
    assert cities_changed is True
    assert any("변경진" in r for r in reports)


async def test_resolve_territory_changes_handles_world_war_outcomes(session_id):
    await nation_service.get_or_create_nation(session_id)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 10, 10)  # owns x:9-11,y:9-11
    await territory_service.ensure_rival_territory(session_id, "northern_kingdom", 13, 10)  # owns x:12-14,y:9-11

    world_war_outcomes = [("eastern_tribes", "northern_kingdom", "동쪽 부족 연맹", "북방 왕국")]
    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, [], [], world_war_outcomes, {"year": 1, "month": 1}
    )
    assert changed is True
    assert any("북방 왕국" in r and "침략" in r for r in reports)

    all_tiles = await territory_service.get_all_tiles(session_id)
    owners = [t["owner"] for t in all_tiles]
    assert owners.count("eastern_tribes") == 10  # 9 original + 1 captured
    assert owners.count("northern_kingdom") == 8  # 9 original - 1 lost


async def test_resolve_territory_changes_can_found_a_rival_city(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    # get_or_create_map already auto-seeds eastern_tribes' usual radius-1 (9 tile)
    # block at whatever capital position it randomly picks — ensure_rival_territory
    # itself is idempotent and would no-op a second call, so to reach past
    # RIVAL_CITY_MIN_TILES we add the surrounding ring directly instead (radius 2-3,
    # skipping the already-owned inner 3x3 to avoid duplicate tile rows).
    map_data = await map_service.get_or_create_map(session_id)
    eastern_capital = next(rc for rc in map_data["rival_capitals"] if rc["rival_id"] == "eastern_tribes")
    cx, cy = eastern_capital["x"], eastern_capital["y"]
    async with async_session_maker() as db:
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if max(abs(dx), abs(dy)) <= 1:
                    continue  # already seeded by get_or_create_map
                db.add(OwnedTile(session_id=session_id, x=cx + dx, y=cy + dy, owner="eastern_tribes"))
        await db.commit()

    rivals = [
        {
            "rival_id": rc["rival_id"],
            "name": rc["name"],
            "economy": 0.0,
            "relationship": "peace",
            "personality": "economic",
        }
        for rc in map_data["rival_capitals"]
    ]
    monkeypatch.setattr(session_manager.random, "random", lambda: 0.0)  # clears the founding roll

    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, rivals, [], [], {"year": 5, "month": 6}
    )
    assert cities_changed is True
    assert any("새 도시" in r and "동쪽 부족 연맹" in r for r in reports)

    cities = await city_service.get_cities(session_id)
    rival_cities = [c for c in cities if c["owner"] == "eastern_tribes"]
    assert len(rival_cities) == 1


async def test_resolve_territory_changes_caps_rival_extra_cities(session_id, monkeypatch):
    await nation_service.get_or_create_nation(session_id)
    map_data = await map_service.get_or_create_map(session_id)
    eastern_capital = next(rc for rc in map_data["rival_capitals"] if rc["rival_id"] == "eastern_tribes")
    await territory_service.ensure_rival_territory(
        session_id, "eastern_tribes", eastern_capital["x"], eastern_capital["y"], radius=3
    )
    # Already at the cap before this tick runs — each pre-seeded city is spaced at
    # least MIN_DISTANCE_FROM_OTHER_CITIES from both the capital and each other.
    for i in range(city_service.RIVAL_CITY_MAX_EXTRA_CITIES):
        offset = city_service.MIN_DISTANCE_FROM_OTHER_CITIES * (i + 1)
        await city_service.found_rival_city(
            session_id,
            "eastern_tribes",
            eastern_capital,
            {(eastern_capital["x"] + offset, eastern_capital["y"])},
            {"year": 1, "month": 1},
        )

    rivals = [
        {
            "rival_id": rc["rival_id"],
            "name": rc["name"],
            "economy": 0.0,
            "relationship": "peace",
            "personality": "economic",
        }
        for rc in map_data["rival_capitals"]
    ]
    monkeypatch.setattr(session_manager.random, "random", lambda: 0.0)

    reports, changed, cities_changed = await session_manager._resolve_territory_changes(
        session_id, rivals, [], [], {"year": 5, "month": 6}
    )
    assert cities_changed is False  # already at the cap, no third city founded

    cities = await city_service.get_cities(session_id)
    rival_cities = [c for c in cities if c["owner"] == "eastern_tribes"]
    assert len(rival_cities) == city_service.RIVAL_CITY_MAX_EXTRA_CITIES
