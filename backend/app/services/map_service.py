import json
import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.game_map import GameMap
from app.data.rivals import RIVAL_TEMPLATES
from app.services.territory_service import ensure_initial_territory, ensure_rival_territory

MAP_WIDTH = 24
MAP_HEIGHT = 16

# Multiple terrain "feels" so the map isn't the same balanced mix every game — one is
# picked at random per new session. Numbers are seeds/size for _grow_cluster, same
# knobs as the original single hardcoded preset.
MAP_PRESETS = [
    {
        "name": "balanced",
        "water": {"seeds": 2, "size": 18},
        "mountain": {"seeds": 3, "size": 10},
        "forest": {"seeds": 4, "size": 14},
        "desert": {"seeds": 2, "size": 10},
    },
    {
        "name": "archipelago",
        "water": {"seeds": 5, "size": 24},
        "mountain": {"seeds": 2, "size": 8},
        "forest": {"seeds": 3, "size": 12},
        "desert": {"seeds": 1, "size": 6},
    },
    {
        "name": "highlands",
        "water": {"seeds": 1, "size": 10},
        "mountain": {"seeds": 5, "size": 14},
        "forest": {"seeds": 4, "size": 12},
        "desert": {"seeds": 1, "size": 6},
    },
    {
        "name": "arid",
        "water": {"seeds": 1, "size": 12},
        "mountain": {"seeds": 2, "size": 8},
        "forest": {"seeds": 1, "size": 8},
        "desert": {"seeds": 5, "size": 20},
    },
    {
        "name": "woodlands",
        "water": {"seeds": 2, "size": 14},
        "mountain": {"seeds": 2, "size": 8},
        "forest": {"seeds": 6, "size": 20},
        "desert": {"seeds": 1, "size": 6},
    },
]

# Resource types tied to specific terrain — each gives a small monthly bonus to a
# nation stat (or food production) when it falls within 1 tile of the capital or a
# founded city, so *where* a city gets founded carries a real, visible tradeoff
# (session_manager._compute_resource_bonus reads this same dict).
RESOURCE_TYPES = {
    "gold_mine": {"name": "금광", "icon": "⛏️", "terrain": ["mountain"], "bonus": {"economy": 6.0}},
    "iron_ore": {"name": "철광", "icon": "⚒️", "terrain": ["mountain"], "bonus": {"military": 6.0}},
    "fertile_soil": {"name": "비옥한 토양", "icon": "🌾", "terrain": ["grass"], "bonus": {"food": 0.15}},
    "timber": {"name": "목재", "icon": "🌲", "terrain": ["forest"], "bonus": {"economy": 4.0}},
    "spice": {"name": "향신료", "icon": "🌶️", "terrain": ["desert"], "bonus": {"economy": 8.0}},
    "horses": {"name": "말", "icon": "🐎", "terrain": ["grass"], "bonus": {"military": 5.0}},
    "fish": {"name": "어장", "icon": "🐟", "terrain": ["water"], "bonus": {"food": 0.2}},
}
RESOURCE_CHANCE_PER_TILE = 0.05

# The capital's position is now randomized per game (previously always dead-center),
# but kept within a central band so it never lands close enough to a rival capital's
# fixed edge/corner band (see _place_rival_capitals) to overlap starting territory.
CAPITAL_X_FRAC_RANGE = (0.35, 0.65)
CAPITAL_Y_FRAC_RANGE = (0.35, 0.65)
MIN_CAPITAL_RIVAL_DISTANCE = 4


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


def _pick_capital_position(width, height, rival_spots):
    for _ in range(30):
        x = int(random.uniform(*CAPITAL_X_FRAC_RANGE) * width)
        y = int(random.uniform(*CAPITAL_Y_FRAC_RANGE) * height)
        x = max(1, min(width - 2, x))
        y = max(1, min(height - 2, y))
        if all(max(abs(x - rx), abs(y - ry)) >= MIN_CAPITAL_RIVAL_DISTANCE for rx, ry in rival_spots):
            return x, y
    return width // 2, height // 2  # fallback if 30 retries somehow all clashed


def _place_resources(grid, width, height, protected_tiles):
    by_terrain: dict[str, list[str]] = {}
    for res_id, info in RESOURCE_TYPES.items():
        for terrain in info["terrain"]:
            by_terrain.setdefault(terrain, []).append(res_id)

    resources = []
    for y in range(height):
        for x in range(width):
            if (x, y) in protected_tiles:
                continue
            candidates = by_terrain.get(grid[y][x])
            if not candidates or random.random() >= RESOURCE_CHANCE_PER_TILE:
                continue
            resources.append({"x": x, "y": y, "type": random.choice(candidates)})
    return resources


def _generate_map(width: int = MAP_WIDTH, height: int = MAP_HEIGHT) -> dict:
    preset = random.choice(MAP_PRESETS)
    grid = [["grass" for _ in range(width)] for _ in range(height)]

    for terrain in ("water", "mountain", "forest", "desert"):
        params = preset[terrain]
        _grow_cluster(grid, width, height, terrain, seeds=params["seeds"], size=params["size"])

    rival_capitals = _place_rival_capitals(width, height, grid)
    capital_x, capital_y = _pick_capital_position(
        width, height, [(rc["x"], rc["y"]) for rc in rival_capitals]
    )
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            x, y = capital_x + dx, capital_y + dy
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = "grass"

    protected_tiles = {(capital_x, capital_y)}
    protected_tiles.update((rc["x"], rc["y"]) for rc in rival_capitals)
    resources = _place_resources(grid, width, height, protected_tiles)

    return {
        "width": width,
        "height": height,
        "tiles": grid,
        "capital": {"x": capital_x, "y": capital_y},
        "rival_capitals": rival_capitals,
        "resources": resources,
        "preset": preset["name"],
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
