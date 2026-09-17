from app.services import map_service, territory_service


async def test_get_or_create_map_is_idempotent_and_seeds_territory(session_id):
    first = await map_service.get_or_create_map(session_id)
    second = await map_service.get_or_create_map(session_id)
    assert first["tiles"] == second["tiles"]
    assert first["capital"] == second["capital"]
    assert first["rival_capitals"] == second["rival_capitals"]

    # get_or_create_map is also responsible for lazily seeding everyone's starting
    # territory, so a second call must not re-seed / duplicate it.
    player_tiles = await territory_service.get_owned_tiles(session_id)
    assert len(player_tiles) == 9


async def test_capital_is_at_map_center(session_id):
    data = await map_service.get_or_create_map(session_id)
    assert data["capital"] == {"x": data["width"] // 2, "y": data["height"] // 2}


async def test_rival_capitals_are_within_bounds_and_each_seeded(session_id):
    data = await map_service.get_or_create_map(session_id)
    assert len(data["rival_capitals"]) == 3

    all_tiles = await territory_service.get_all_tiles(session_id)
    owners = {t["owner"] for t in all_tiles}

    for rc in data["rival_capitals"]:
        assert 0 <= rc["x"] < data["width"]
        assert 0 <= rc["y"] < data["height"]
        assert rc["rival_id"] in owners


async def test_capital_area_is_never_water(session_id):
    data = await map_service.get_or_create_map(session_id)
    cx, cy = data["capital"]["x"], data["capital"]["y"]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            assert data["tiles"][cy + dy][cx + dx] != "water"
