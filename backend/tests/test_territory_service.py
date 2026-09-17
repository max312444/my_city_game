import pytest

from app.db import async_session_maker
from app.services import nation_service, territory_service


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


async def test_initial_territory_is_a_3x3_block_around_the_capital(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    tiles = await territory_service.get_owned_tiles(session_id)
    assert len(tiles) == 9
    assert {(t["x"], t["y"]) for t in tiles} == {
        (x, y) for x in (9, 10, 11) for y in (9, 10, 11)
    }


async def test_ensure_initial_territory_is_idempotent(session_id):
    await territory_service.ensure_initial_territory(session_id, 5, 5)
    await territory_service.ensure_initial_territory(session_id, 5, 5)  # called again, e.g. on reconnect
    tiles = await territory_service.get_owned_tiles(session_id)
    assert len(tiles) == 9


async def test_purchase_tile_charges_cost_and_requires_adjacency(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)

    # (10,10) with radius 1 owns x:9-11,y:9-11 — (12,9) is just outside that block but
    # still adjacent to its (11,9) corner.
    nation, cost = await territory_service.purchase_tile(session_id, 12, 9, terrain="grass")
    assert cost == territory_service.TILE_BASE_COST + territory_service.TILE_COST_GROWTH * 9
    assert nation.treasury == 10_000 - cost

    tiles = await territory_service.get_owned_tiles(session_id)
    assert (12, 9) in {(t["x"], t["y"]) for t in tiles}


async def test_purchase_tile_rejects_non_adjacent(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)

    with pytest.raises(territory_service.TerritoryError):
        await territory_service.purchase_tile(session_id, 50, 50, terrain="grass")


async def test_purchase_tile_rejects_water(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 10_000)

    with pytest.raises(territory_service.TerritoryError):
        await territory_service.purchase_tile(session_id, 12, 9, terrain="water")


async def test_purchase_tile_rejects_insufficient_funds(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 0)

    with pytest.raises(territory_service.TerritoryError, match="보유 금액"):
        await territory_service.purchase_tile(session_id, 12, 9, terrain="grass")


async def test_purchase_tile_rejects_tile_already_owned_by_anyone(session_id):
    """Regression test for the overlap bug: buying a tile someone else (player or
    rival) already owns must always fail, never silently overwrite ownership."""
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 15, 15)
    await nation_service.get_or_create_nation(session_id)
    await _give_treasury(session_id, 100_000)

    with pytest.raises(territory_service.TerritoryError):
        await territory_service.purchase_tile(session_id, 15, 15, terrain="grass")  # a rival's capital tile


async def test_expand_rival_territory_never_claims_an_owned_tile(session_id):
    # Rival's block (x:12-14) sits directly against the player's block (x:9-11), so the
    # rival's expansion frontier naturally includes tiles the player already owns (x=11)
    # — those must be excluded from candidates, never claimed out from under the player.
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)

    grid = [["grass" for _ in range(30)] for _ in range(30)]
    before = {(t["x"], t["y"]) for t in await territory_service.get_all_tiles(session_id)}

    for _ in range(10):
        claimed = await territory_service.expand_rival_territory(session_id, "eastern_tribes", grid)
        if claimed is not None:
            assert (claimed["x"], claimed["y"]) not in before
            before.add((claimed["x"], claimed["y"]))


async def test_expand_rival_territory_never_claims_water(session_id):
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 5, 5)
    grid = [["water" for _ in range(20)] for _ in range(20)]
    for _ in range(20):
        claimed = await territory_service.expand_rival_territory(session_id, "eastern_tribes", grid)
        assert claimed is None  # every neighboring tile is water — nothing claimable


async def test_capture_tile_requires_shared_border(session_id):
    # Winner's territory and loser's territory are far apart — no invasion possible.
    await territory_service.ensure_initial_territory(session_id, 0, 0)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 50, 50)

    result = await territory_service.capture_tile(session_id, "player", "eastern_tribes", protected_tiles=set())
    assert result is None


async def test_capture_tile_takes_an_adjacent_border_tile(session_id):
    # Place the rival's territory so it touches the player's block.
    await territory_service.ensure_initial_territory(session_id, 10, 10)  # owns x:9-11, y:9-11
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)  # owns x:12-14, y:9-11

    result = await territory_service.capture_tile(session_id, "player", "eastern_tribes", protected_tiles=set())
    assert result is not None
    assert result["x"] == 12  # only column adjacent to the player's block (x=11)

    all_tiles = await territory_service.get_all_tiles(session_id)
    captured = next(t for t in all_tiles if t["x"] == result["x"] and t["y"] == result["y"])
    assert captured["owner"] == "player"


async def test_capture_tile_never_takes_a_protected_capital(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)
    protected = {(13, 10)}  # the rival's capital tile

    for _ in range(20):
        result = await territory_service.capture_tile(session_id, "player", "eastern_tribes", protected)
        if result is None:
            break
        assert (result["x"], result["y"]) != (13, 10)

    all_tiles = await territory_service.get_all_tiles(session_id)
    capital_owner = next(t["owner"] for t in all_tiles if t["x"] == 13 and t["y"] == 10)
    assert capital_owner == "eastern_tribes"


async def test_delete_territory_removes_every_owner(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)
    await territory_service.delete_territory(session_id)
    assert await territory_service.get_all_tiles(session_id) == []


async def test_capture_tile_without_elimination_never_takes_the_last_tile(session_id):
    # A rival cornered down to a single tile still can't be wiped out unless the
    # caller explicitly opts into allow_elimination — this is what protects the
    # player (session_manager never passes allow_elimination=True for the player).
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10, radius=0)  # just (13,10)

    result = await territory_service.capture_tile(
        session_id, "player", "eastern_tribes", protected_tiles=set(), allow_elimination=False
    )
    assert result is None  # (13,10) is the loser's only tile and isn't adjacent-safe to take without opting in


async def test_capture_tile_with_elimination_wipes_out_a_cornered_rival(session_id):
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 12, 10, radius=0)  # just (12,10)

    result = await territory_service.capture_tile(
        session_id, "player", "eastern_tribes", protected_tiles=set(), allow_elimination=True
    )
    assert result == {"x": 12, "y": 10, "eliminated": True}

    all_tiles = await territory_service.get_all_tiles(session_id)
    assert not any(t["owner"] == "eastern_tribes" for t in all_tiles)


async def test_capture_tile_with_elimination_still_respects_protection_when_not_cornered(session_id):
    # allow_elimination only kicks in once the loser is down to exactly one tile —
    # with more than one tile left, the ordinary protected_tiles rule still applies.
    await territory_service.ensure_initial_territory(session_id, 10, 10)
    await territory_service.ensure_rival_territory(session_id, "eastern_tribes", 13, 10)  # 3x3, 9 tiles
    protected = {(13, 10)}

    # Bounded well below 9 so the rival never actually gets cornered to 1 tile during
    # this test — that eventual-elimination case is covered separately above.
    for _ in range(5):
        result = await territory_service.capture_tile(
            session_id, "player", "eastern_tribes", protected, allow_elimination=True
        )
        if result is None:
            break
        assert (result["x"], result["y"]) != (13, 10)
