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


async def test_capital_is_within_the_randomized_central_safe_zone(session_id):
    data = await map_service.get_or_create_map(session_id)
    cx, cy = data["capital"]["x"], data["capital"]["y"]
    x_lo = int(map_service.CAPITAL_X_FRAC_RANGE[0] * data["width"]) - 1
    x_hi = int(map_service.CAPITAL_X_FRAC_RANGE[1] * data["width"]) + 1
    y_lo = int(map_service.CAPITAL_Y_FRAC_RANGE[0] * data["height"]) - 1
    y_hi = int(map_service.CAPITAL_Y_FRAC_RANGE[1] * data["height"]) + 1
    assert x_lo <= cx <= x_hi
    assert y_lo <= cy <= y_hi

    for rc in data["rival_capitals"]:
        assert max(abs(cx - rc["x"]), abs(cy - rc["y"])) >= map_service.MIN_CAPITAL_RIVAL_DISTANCE


async def test_capital_position_varies_across_sessions():
    positions = set()
    for i in range(8):
        data = await map_service.get_or_create_map(f"capital-variety-{i}")
        positions.add((data["capital"]["x"], data["capital"]["y"]))
    assert len(positions) > 1


async def test_map_preset_varies_across_sessions():
    presets = set()
    for i in range(10):
        data = await map_service.get_or_create_map(f"preset-variety-{i}")
        presets.add(data["preset"])
    assert len(presets) > 1


async def test_resources_are_placed_on_matching_terrain_and_avoid_capitals(session_id):
    data = await map_service.get_or_create_map(session_id)
    capital_spots = {(data["capital"]["x"], data["capital"]["y"])}
    capital_spots.update((rc["x"], rc["y"]) for rc in data["rival_capitals"])

    assert len(data["resources"]) > 0
    for res in data["resources"]:
        assert (res["x"], res["y"]) not in capital_spots
        terrain = data["tiles"][res["y"]][res["x"]]
        assert terrain in map_service.RESOURCE_TYPES[res["type"]]["terrain"]


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
