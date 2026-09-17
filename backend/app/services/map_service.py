import json
import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.game_map import GameMap
from app.data.rivals import RIVAL_TEMPLATES
from app.services.territory_service import ensure_initial_territory, ensure_rival_territory

MAP_WIDTH = 24
MAP_HEIGHT = 16


def _place_rival_capitals(width, height, grid):
    # The left/right ~250px of the screen are covered top-to-bottom by fixed UI side
    # panels, so anything placed near those edges gets its label clipped. Keep rivals
    # inside the middle horizontal band and spread them out vertically instead.
    spots = [
        (width * 0.5, height * 0.12),
        (width * 0.33, height * 0.88),
        (width * 0.67, height * 0.88),
    ]
    random.shuffle(spots)
    positions = []
    for i, template in enumerate(RIVAL_TEMPLATES):
        base_x, base_y = spots[i % len(spots)]
        x = int(max(1, min(width - 2, base_x + random.randint(-2, 2))))
        y = int(max(1, min(height - 2, base_y + random.randint(-2, 2))))
        grid[y][x] = "grass"
        positions.append({"rival_id": template["rival_id"], "name": template["name"], "x": x, "y": y})
    return positions


def _grow_cluster(grid, width, height, terrain, seeds, size):
    for _ in range(seeds):
        start = (random.randint(0, width - 1), random.randint(0, height - 1))
        frontier = [start]
        visited = set()
        cluster_size = random.randint(size // 2, size)
        while frontier and len(visited) < cluster_size:
            x, y = frontier.pop(random.randrange(len(frontier)))
            if (x, y) in visited or not (0 <= x < width and 0 <= y < height):
                continue
            visited.add((x, y))
            grid[y][x] = terrain
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                frontier.append((x + dx, y + dy))


def _generate_map(width: int = MAP_WIDTH, height: int = MAP_HEIGHT) -> dict:
    grid = [["grass" for _ in range(width)] for _ in range(height)]

    _grow_cluster(grid, width, height, "water", seeds=2, size=18)
    _grow_cluster(grid, width, height, "mountain", seeds=3, size=10)
    _grow_cluster(grid, width, height, "forest", seeds=4, size=14)
    _grow_cluster(grid, width, height, "desert", seeds=2, size=10)

    capital_x, capital_y = width // 2, height // 2
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = capital_x + dx, capital_y + dy
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = "grass"

    rival_capitals = _place_rival_capitals(width, height, grid)

    return {
        "width": width,
        "height": height,
        "tiles": grid,
        "capital": {"x": capital_x, "y": capital_y},
        "rival_capitals": rival_capitals,
    }


async def delete_map(session_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(GameMap).where(GameMap.session_id == session_id))
        game_map = result.scalar_one_or_none()
        if game_map is not None:
            await db.delete(game_map)
            await db.commit()


async def get_or_create_map(session_id: str) -> dict:
    async with async_session_maker() as db:
        result = await db.execute(select(GameMap).where(GameMap.session_id == session_id))
        game_map = result.scalar_one_or_none()
        if game_map is None:
            data = _generate_map()
            game_map = GameMap(session_id=session_id, data=json.dumps(data))
            db.add(game_map)
            await db.commit()
        else:
            data = json.loads(game_map.data)

    await ensure_initial_territory(session_id, data["capital"]["x"], data["capital"]["y"])
    for rc in data["rival_capitals"]:
        await ensure_rival_territory(session_id, rc["rival_id"], rc["x"], rc["y"])
    return data
