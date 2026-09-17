"""End-to-end smoke tests through the real FastAPI app (no server process — httpx
talks to it in-process over ASGI). These exist to catch the class of bug this
project has repeatedly hit only after manual curl/browser testing: wiring
mistakes between main.py and the services, request/response shape drift, etc.

Deliberately skips FastAPI's lifespan (no init_db()/clock_loop startup) — conftest
already calls init_db() once for the whole test session, and none of these tests
depend on the real-time background clock tick."""

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
