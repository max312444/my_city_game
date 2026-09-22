import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.territory import OwnedTile
from app.services.nation_service import _get_or_create_nation

# Raised after player feedback that buying up land was too easy/cheap even at scale
# — the old flat linear growth (80 + 12*owned) barely outpaced a growing treasury.
# Now grows with a quadratic term too, so the *marginal* tile gets noticeably more
# expensive the more you already own (early expansion stays roughly as affordable as
# before; buying up dozens of tiles gets genuinely expensive).
TILE_BASE_COST = 100
TILE_COST_LINEAR = 20
TILE_COST_QUADRATIC = 1.0
PLAYER_OWNER = "player"


class TerritoryError(Exception):
    pass


async def _get_owned(db, session_id: str, owner: str | None = None) -> list[OwnedTile]:
    query = select(OwnedTile).where(OwnedTile.session_id == session_id)
    if owner is not None:
        query = query.where(OwnedTile.owner == owner)
    result = await db.execute(query)
    return list(result.scalars().all())


async def _seed_block(db, session_id: str, owner: str, cx: int, cy: int, radius: int = 1):
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            db.add(OwnedTile(session_id=session_id, x=cx + dx, y=cy + dy, owner=owner))


async def ensure_initial_territory(session_id: str, capital_x: int, capital_y: int):
    async with async_session_maker() as db:
        owned = await _get_owned(db, session_id, owner=PLAYER_OWNER)
        if owned:
            return
        await _seed_block(db, session_id, PLAYER_OWNER, capital_x, capital_y, radius=1)
        await db.commit()


async def ensure_rival_territory(session_id: str, rival_id: str, capital_x: int, capital_y: int, radius: int = 1):
    async with async_session_maker() as db:
        owned = await _get_owned(db, session_id, owner=rival_id)
        if owned:
            return
        await _seed_block(db, session_id, rival_id, capital_x, capital_y, radius=radius)
        await db.commit()


async def get_owned_tiles(session_id: str, owner: str = PLAYER_OWNER) -> list[dict]:
    async with async_session_maker() as db:
        owned = await _get_owned(db, session_id, owner=owner)
        return [{"x": t.x, "y": t.y} for t in owned]


async def get_all_tiles(session_id: str) -> list[dict]:
    async with async_session_maker() as db:
        owned = await _get_owned(db, session_id)
        return [{"x": t.x, "y": t.y, "owner": t.owner} for t in owned]


async def owner_at(session_id: str, x: int, y: int) -> str | None:
    async with async_session_maker() as db:
        result = await db.execute(
            select(OwnedTile).where(OwnedTile.session_id == session_id, OwnedTile.x == x, OwnedTile.y == y)
        )
        tile = result.scalar_one_or_none()
        return tile.owner if tile else None


async def delete_territory(session_id: str) -> None:
    async with async_session_maker() as db:
        for tile in await _get_owned(db, session_id):
            await db.delete(tile)
        await db.commit()


def compute_cost(owned_count: int) -> float:
    return TILE_BASE_COST + TILE_COST_LINEAR * owned_count + TILE_COST_QUADRATIC * owned_count**2


async def purchase_tile(session_id: str, x: int, y: int, terrain: str):
    """Player-only: spends treasury to claim a tile adjacent to the player's own territory."""
    if terrain == "water":
        raise TerritoryError("물 위에는 영토를 확장할 수 없습니다")
    async with async_session_maker() as db:
        all_owned = await _get_owned(db, session_id)
        all_owned_set = {(t.x, t.y) for t in all_owned}
        if (x, y) in all_owned_set:
            raise TerritoryError("이미 다른 세력이 소유한 영토입니다")

        own_tiles = [t for t in all_owned if t.owner == PLAYER_OWNER]
        adjacent = any(abs(t.x - x) <= 1 and abs(t.y - y) <= 1 for t in own_tiles)
        if not adjacent:
            raise TerritoryError("기존 영토와 인접한 칸만 구매할 수 있습니다")

        cost = compute_cost(len(own_tiles))
        nation = await _get_or_create_nation(db, session_id)
        if nation.treasury < cost:
            raise TerritoryError("보유 금액이 부족합니다")
        nation.treasury -= cost
        db.add(OwnedTile(session_id=session_id, x=x, y=y, owner=PLAYER_OWNER))
        await db.commit()
        await db.refresh(nation)
        return nation, cost


async def expand_rival_territory(session_id: str, rival_id: str, tiles_grid: list[list[str]]) -> dict | None:
    """Rivals grow the same tile-by-tile way the player does, just without a cash cost.
    Claims one random empty, non-water tile adjacent to the rival's own frontier, if any exists."""
    height = len(tiles_grid)
    width = len(tiles_grid[0]) if height else 0

    async with async_session_maker() as db:
        all_owned = await _get_owned(db, session_id)
        all_owned_set = {(t.x, t.y) for t in all_owned}
        own_tiles = [(t.x, t.y) for t in all_owned if t.owner == rival_id]

        candidates = set()
        for ox, oy in own_tiles:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = ox + dx, oy + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if (nx, ny) in all_owned_set:
                        continue
                    if tiles_grid[ny][nx] == "water":
                        continue
                    candidates.add((nx, ny))

        if not candidates:
            return None

        x, y = random.choice(list(candidates))
        db.add(OwnedTile(session_id=session_id, x=x, y=y, owner=rival_id))
        await db.commit()
        return {"x": x, "y": y}


async def capture_tile(
    session_id: str,
    winner: str,
    loser: str,
    protected_tiles: set[tuple[int, int]],
    allow_elimination: bool = False,
    preferred_tile: tuple[int, int] | None = None,
) -> dict | None:
    """War outcome: the winner seizes one of the loser's border tiles that touches the
    winner's own territory — an invasion has to come from a shared border. Capital tiles
    are normally protected so a war can never wipe out a side's home city — unless
    `allow_elimination` is set AND the loser is already down to that one last tile, in
    which case it falls too and the loser is wiped out. Callers only ever pass
    allow_elimination=True when the loser is a rival, never the player — rivals can
    fall in this game, the player never can (see diplomacy_service docs).

    `preferred_tile` is the player's current siege target (see diplomacy attack-city
    flow) — if it's among this month's valid candidates, the capture lands there
    instead of a random border tile; otherwise this falls back to random exactly like
    before, so an out-of-reach target just means "not yet", not an error."""
    async with async_session_maker() as db:
        all_owned = await _get_owned(db, session_id)
        winner_tiles = {(t.x, t.y) for t in all_owned if t.owner == winner}
        loser_tiles = [t for t in all_owned if t.owner == loser]

        last_stand = allow_elimination and len(loser_tiles) == 1
        candidates = [
            t
            for t in loser_tiles
            if (last_stand or (t.x, t.y) not in protected_tiles)
            and any(abs(t.x - wx) <= 1 and abs(t.y - wy) <= 1 for wx, wy in winner_tiles)
        ]
        if not candidates:
            return None

        target = None
        if preferred_tile is not None:
            target = next((t for t in candidates if (t.x, t.y) == preferred_tile), None)
        if target is None:
            target = random.choice(candidates)
        target.owner = winner
        await db.commit()
        return {"x": target.x, "y": target.y, "eliminated": last_stand}
