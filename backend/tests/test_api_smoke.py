"""End-to-end smoke tests through the real FastAPI app (no server process — httpx
talks to it in-process over ASGI). These exist to catch the class of bug this
project has repeatedly hit only after manual curl/browser testing: wiring
mistakes between main.py and the services, request/response shape drift, etc.

Deliberately skips FastAPI's lifespan (no init_db()/clock_loop startup) — conftest
already calls init_db() once for the whole test session, and none of these tests
depend on the real-time background clock tick."""

from collections import deque

import httpx
import pytest

from app.db import async_session_maker
from app.main import app
from app.services import nation_service


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _give_treasury(session_id, amount):
    async with async_session_maker() as db:
        nation = await nation_service._get_or_create_nation(db, session_id)
        nation.treasury = amount
        await db.commit()


async def test_signup_login_and_duplicate_username(client, session_id):
    res = await client.post(
        "/api/auth/signup",
        json={"username": session_id, "password": "password123", "display_name": "테스터"},
    )
    assert res.status_code == 200
    assert res.json()["username"] == session_id

    dup = await client.post(
        "/api/auth/signup",
        json={"username": session_id, "password": "password123", "display_name": "테스터2"},
    )
    assert dup.status_code == 400

    login = await client.post("/api/auth/login", json={"username": session_id, "password": "password123"})
    assert login.status_code == 200

    bad_login = await client.post("/api/auth/login", json={"username": session_id, "password": "wrong"})
    assert bad_login.status_code == 401

    availability = await client.get("/api/auth/check-username", params={"username": session_id})
    assert availability.json()["available"] is False


async def test_nation_lifecycle_via_http(client, session_id):
    res = await client.get(f"/api/session/{session_id}/nation")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == session_id  # unnamed nation defaults to the session id
    assert data["population"] == 50

    renamed = await client.post(f"/api/session/{session_id}/nation/name", json={"name": "테스트왕국"})
    assert renamed.json()["name"] == "테스트왕국"

    empty_name = await client.post(f"/api/session/{session_id}/nation/name", json={"name": "   "})
    assert empty_name.status_code == 400

    exists = await client.get(f"/api/session/{session_id}/exists")
    assert exists.json()["exists"] is True

    deleted = await client.delete(f"/api/session/{session_id}")
    assert deleted.status_code == 200
    exists_after = await client.get(f"/api/session/{session_id}/exists")
    assert exists_after.json()["exists"] is False


async def test_clock_speed_roundtrip(client, session_id):
    res = await client.post(f"/api/session/{session_id}/clock/speed", json={"speed": "fast"})
    assert res.json()["speed"] == "fast"

    state = await client.get(f"/api/session/{session_id}/clock")
    assert state.json()["speed"] == "fast"


async def test_tech_research_via_http(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")  # ensure nation exists
    await _give_treasury(session_id, 10_000)

    tree = await client.get(f"/api/session/{session_id}/tech")
    assert any(t["id"] == "agriculture" for t in tree.json()["tree"])

    started = await client.post(f"/api/session/{session_id}/tech/research", json={"tech_id": "agriculture"})
    assert started.status_code == 200
    assert started.json()["current_research"] == "agriculture"

    invalid = await client.post(f"/api/session/{session_id}/tech/research", json={"tech_id": "does_not_exist"})
    assert invalid.status_code == 400


async def test_diplomacy_via_http(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")

    rivals = await client.get(f"/api/session/{session_id}/diplomacy")
    assert len(rivals.json()["rivals"]) == 3

    war = await client.post(
        f"/api/session/{session_id}/diplomacy/declare-war", json={"rival_id": "eastern_tribes"}
    )
    assert war.status_code == 200
    assert any(
        r["rival_id"] == "eastern_tribes" and r["relationship"] == "war" for r in war.json()["rivals"]
    )

    unknown = await client.post(
        f"/api/session/{session_id}/diplomacy/declare-war", json={"rival_id": "nonexistent"}
    )
    assert unknown.status_code == 400


async def test_trade_route_via_http(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    await client.get(f"/api/session/{session_id}/diplomacy")  # seeds the 3 rivals

    establish = await client.post(
        f"/api/session/{session_id}/trade/establish", json={"rival_id": "eastern_tribes"}
    )
    assert establish.status_code == 200

    state = (await client.get(f"/api/session/{session_id}/trade")).json()
    assert len(state["routes"]) == 1
    assert state["routes"][0]["rival_id"] == "eastern_tribes"
    assert state["routes"][0]["income"] > 0  # at peace by default

    duplicate = await client.post(
        f"/api/session/{session_id}/trade/establish", json={"rival_id": "eastern_tribes"}
    )
    assert duplicate.status_code == 400

    closed = await client.post(f"/api/session/{session_id}/trade/close", json={"rival_id": "eastern_tribes"})
    assert closed.status_code == 200
    state_after = (await client.get(f"/api/session/{session_id}/trade")).json()
    assert state_after["routes"] == []


async def test_sell_food_via_http(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    await _give_treasury(session_id, 0)

    from app.db import async_session_maker
    from app.services import nation_service as nation_service_module

    async with async_session_maker() as db:
        nation = await nation_service_module._get_or_create_nation(db, session_id)
        nation.food_stock = 100.0
        await db.commit()

    resp = await client.post(f"/api/session/{session_id}/trade/sell-food", json={"amount": 50.0})
    assert resp.status_code == 200
    data = resp.json()["nation"]
    assert data["food_stock"] == 50.0
    assert data["treasury"] == 50.0 * 2.0  # FOOD_SELL_RATE

    too_much = await client.post(f"/api/session/{session_id}/trade/sell-food", json={"amount": 1000.0})
    assert too_much.status_code == 400


async def test_attack_city_via_http_declares_war_and_sets_siege_target(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    await client.get(f"/api/session/{session_id}/diplomacy")  # seeds the 3 rivals

    from app.db import async_session_maker
    from app.models.city import City
    from app.models.territory import OwnedTile

    async with async_session_maker() as db:
        db.add(OwnedTile(session_id=session_id, x=500, y=500, owner="eastern_tribes"))
        db.add(
            City(
                session_id=session_id,
                name="언덕마을",
                x=500,
                y=500,
                owner="eastern_tribes",
                founded_year=1,
                founded_month=1,
            )
        )
        await db.commit()

    resp = await client.post(f"/api/session/{session_id}/diplomacy/attack-city", json={"x": 500, "y": 500})
    assert resp.status_code == 200
    data = resp.json()
    assert data["city_name"] == "언덕마을"
    assert data["rival_id"] == "eastern_tribes"

    rivals = (await client.get(f"/api/session/{session_id}/diplomacy")).json()["rivals"]
    eastern = next(r for r in rivals if r["rival_id"] == "eastern_tribes")
    assert eastern["relationship"] == "war"
    assert eastern["siege_target_name"] == "언덕마을"


async def test_attack_city_rejects_empty_tile(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    resp = await client.post(f"/api/session/{session_id}/diplomacy/attack-city", json={"x": 0, "y": 0})
    assert resp.status_code == 400


async def test_attack_city_rejects_own_territory(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    territory = (await client.get(f"/api/session/{session_id}/territory")).json()
    own_tile = territory["tiles"][0]
    resp = await client.post(
        f"/api/session/{session_id}/diplomacy/attack-city", json={"x": own_tile["x"], "y": own_tile["y"]}
    )
    assert resp.status_code == 400


async def test_territory_purchase_via_http(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    territory = await client.get(f"/api/session/{session_id}/territory")
    assert territory.status_code == 200
    assert len(territory.json()["tiles"]) == 9  # seeded 3x3 starting block

    map_data = await client.get(f"/api/session/{session_id}/map")
    capital = map_data.json()["capital"]
    tiles_grid = map_data.json()["tiles"]

    # Find a tile adjacent to the capital block that isn't water, to buy.
    target = None
    for dx, dy in ((2, 0), (0, 2), (-2, 0), (0, -2)):
        tx, ty = capital["x"] + dx, capital["y"] + dy
        if 0 <= ty < len(tiles_grid) and 0 <= tx < len(tiles_grid[0]) and tiles_grid[ty][tx] != "water":
            target = (tx, ty)
            break
    assert target is not None, "expected at least one non-water adjacent tile in a freshly generated map"

    await _give_treasury(session_id, 10_000)
    purchase = await client.post(
        f"/api/session/{session_id}/territory/purchase", json={"x": target[0], "y": target[1]}
    )
    assert purchase.status_code == 200
    assert target in [(t["x"], t["y"]) for t in purchase.json()["tiles"]]

    out_of_bounds = await client.post(
        f"/api/session/{session_id}/territory/purchase", json={"x": -1, "y": -1}
    )
    assert out_of_bounds.status_code == 400


async def test_city_founding_via_http_logs_a_chronicle_entry(client, session_id):
    await client.get(f"/api/session/{session_id}/nation")
    await _give_treasury(session_id, 100_000)

    map_data = (await client.get(f"/api/session/{session_id}/map")).json()
    capital = map_data["capital"]
    tiles_grid = map_data["tiles"]
    height, width = len(tiles_grid), len(tiles_grid[0])
    territory = (await client.get(f"/api/session/{session_id}/territory")).json()
    owned_by_other = {(t["x"], t["y"]) for t in territory["all"] if t["owner"] != "player"}
    owned_by_player = {(t["x"], t["y"]) for t in territory["tiles"]}

    # The map is now randomized per game (varying terrain presets and capital
    # position), so a fixed offset like "5 tiles east" can no longer be assumed to
    # exist, be land, or be reachable by land. BFS over free non-water, non-rival
    # tiles (8-directional, matching purchase_tile's adjacency rule) to a tile far
    # enough from the capital to found a city on (MIN_DISTANCE_FROM_OTHER_CITIES == 3),
    # then buy every not-yet-owned tile on that path in order (the path may pass
    # through the capital's own starting 3x3 block, which is already owned).
    start = (capital["x"], capital["y"])
    visited = {start}
    parent = {}
    queue = deque([start])
    target = None
    while queue:
        cx, cy = queue.popleft()
        if (cx, cy) != start and max(abs(cx - start[0]), abs(cy - start[1])) >= 3:
            target = (cx, cy)
            break
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < width
                    and 0 <= ny < height
                    and (nx, ny) not in visited
                    and tiles_grid[ny][nx] != "water"
                    and (nx, ny) not in owned_by_other
                ):
                    visited.add((nx, ny))
                    parent[(nx, ny)] = (cx, cy)
                    queue.append((nx, ny))
    assert target is not None

    path = []
    node = target
    while node != start:
        path.append(node)
        node = parent[node]
    path.reverse()

    for x, y in path:
        if (x, y) in owned_by_player:
            continue
        resp = await client.post(f"/api/session/{session_id}/territory/purchase", json={"x": x, "y": y})
        assert resp.status_code == 200
        owned_by_player.add((x, y))

    found = await client.post(
        f"/api/session/{session_id}/cities", json={"x": target[0], "y": target[1], "name": "새도시"}
    )
    assert found.status_code == 200
    assert found.json()["cities"][0]["name"] == "새도시"

    log = await client.get(f"/api/session/{session_id}/log")
    assert any("새도시" in e["message"] and e["category"] == "city" for e in log.json()["entries"])
