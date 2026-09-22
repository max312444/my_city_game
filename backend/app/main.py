import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from app.core.session_manager import Speed, session_manager
from app.db import init_db
from app.services.nation_service import (
    apply_effects,
    delete_nation,
    get_or_create_nation,
    nation_exists,
    set_nation_name,
)
from app.services import tech_service
from app.services import great_person_service
from app.services import diplomacy_service
from app.services import map_service
from app.services import auth_service
from app.services import territory_service
from app.services import city_service
from app.services import log_service
from app.services.nation_service import sync_land_capacity

TICK_SECONDS = 1.0


async def clock_loop():
    while True:
        await asyncio.sleep(TICK_SECONDS)
        for session in session_manager.all_sessions():
            await session.clock.tick(TICK_SECONDS, session.on_month_advance)
            await session.tick_advice(TICK_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(clock_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpeedRequest(BaseModel):
    speed: Speed


class AdviceChoiceRequest(BaseModel):
    advice_id: str
    choice_id: str


class AdviceDismissRequest(BaseModel):
    advice_id: str


class TechResearchRequest(BaseModel):
    tech_id: str


class DiplomacyActionRequest(BaseModel):
    rival_id: str


class SignupRequest(BaseModel):
    username: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class NationNameRequest(BaseModel):
    name: str


class TerritoryPurchaseRequest(BaseModel):
    x: int
    y: int


class CityFoundRequest(BaseModel):
    x: int
    y: int
    name: str


@app.get("/api/auth/check-username")
async def check_username_endpoint(username: str):
    return {"available": await auth_service.username_available(username.strip())}


@app.post("/api/auth/signup")
async def signup_endpoint(body: SignupRequest):
    try:
        user = await auth_service.signup(body.username, body.password, body.display_name)
    except auth_service.AuthError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return user


@app.post("/api/auth/login")
async def login_endpoint(body: LoginRequest):
    try:
        user = await auth_service.login(body.username, body.password)
    except auth_service.AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return user


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    session = await session_manager.get_or_create(session_id)
    await websocket.accept()
    session.connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        session.connections.discard(websocket)


@app.post("/api/session/{session_id}/clock/speed")
async def set_clock_speed(session_id: str, body: SpeedRequest):
    session = await session_manager.get_or_create(session_id)
    session.clock.speed = body.speed
    return {"speed": session.clock.speed}


@app.get("/api/session/{session_id}/clock")
async def get_clock(session_id: str):
    session = await session_manager.get_or_create(session_id)
    return {"speed": session.clock.speed, "current_date": session.clock.current_date}


@app.get("/api/session/{session_id}/nation")
async def get_nation(session_id: str):
    nation = await get_or_create_nation(session_id)
    return nation.to_dict()


@app.get("/api/session/{session_id}/exists")
async def check_session_exists(session_id: str):
    return {"exists": await nation_exists(session_id)}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    await delete_nation(session_id)
    await map_service.delete_map(session_id)
    await territory_service.delete_territory(session_id)
    await city_service.delete_cities(session_id)
    await diplomacy_service.delete_world_data(session_id)
    await great_person_service.delete_history(session_id)
    await log_service.delete_logs(session_id)
    session_manager.remove(session_id)
    return {"ok": True}


@app.post("/api/session/{session_id}/nation/name")
async def set_nation_name_endpoint(session_id: str, body: NationNameRequest):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요")
    nation = await set_nation_name(session_id, name)
    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return nation.to_dict()


@app.get("/api/session/{session_id}/advice/pending")
async def get_pending_advice(session_id: str):
    session = await session_manager.get_or_create(session_id)
    return {"advice": session.pending_advice}


@app.post("/api/session/{session_id}/advice/choose")
async def choose_advice(session_id: str, body: AdviceChoiceRequest):
    session = await session_manager.get_or_create(session_id)
    if session.pending_advice is None or session.pending_advice["id"] != body.advice_id:
        raise HTTPException(status_code=404, detail="No matching pending advice")

    effects = next(
        (c["effects"] for c in session.pending_advice["choices"] if c["id"] == body.choice_id),
        None,
    )
    if effects is None:
        raise HTTPException(status_code=400, detail="Invalid choice")

    nation = await apply_effects(session_id, effects)
    session.pending_advice = None
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return nation.to_dict()


@app.post("/api/session/{session_id}/advice/dismiss")
async def dismiss_advice(session_id: str, body: AdviceDismissRequest):
    session = await session_manager.get_or_create(session_id)
    if session.pending_advice is not None and session.pending_advice["id"] == body.advice_id:
        session.pending_advice = None
    return {"ok": True}


@app.get("/api/session/{session_id}/tech")
async def get_tech_state(session_id: str):
    state = await tech_service.get_research_state(session_id)
    return {"tree": tech_service.get_tech_tree(), **state}


@app.post("/api/session/{session_id}/tech/research")
async def research_tech_endpoint(session_id: str, body: TechResearchRequest):
    try:
        nation, researched = await tech_service.start_research(session_id, body.tech_id)
    except tech_service.TechError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return {
        "nation": nation.to_dict(),
        "researched": researched,
        "current_research": nation.current_research or None,
        "current_research_months_left": nation.current_research_months_left,
    }


@app.get("/api/session/{session_id}/great-people")
async def get_great_people_history(session_id: str):
    return {"history": await great_person_service.get_history(session_id)}


@app.get("/api/session/{session_id}/diplomacy")
async def get_diplomacy_state(session_id: str):
    return {"rivals": await diplomacy_service.get_rivals(session_id)}


@app.post("/api/session/{session_id}/diplomacy/declare-war")
async def declare_war_endpoint(session_id: str, body: DiplomacyActionRequest):
    try:
        nation, rivals = await diplomacy_service.declare_war(session_id, body.rival_id)
    except diplomacy_service.DiplomacyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    await session.broadcast("rivals_updated", {"rivals": rivals})
    return {"nation": nation.to_dict(), "rivals": rivals}


@app.post("/api/session/{session_id}/diplomacy/propose-peace")
async def propose_peace_endpoint(session_id: str, body: DiplomacyActionRequest):
    try:
        accepted, rivals = await diplomacy_service.propose_peace(session_id, body.rival_id)
    except diplomacy_service.DiplomacyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = await session_manager.get_or_create(session_id)
    await session.broadcast("rivals_updated", {"rivals": rivals})
    return {"accepted": accepted, "rivals": rivals}


@app.get("/api/session/{session_id}/map")
async def get_map(session_id: str):
    return await map_service.get_or_create_map(session_id)


@app.get("/api/session/{session_id}/territory")
async def get_territory_endpoint(session_id: str):
    await map_service.get_or_create_map(session_id)  # ensures rival territory is seeded too
    return {
        "tiles": await territory_service.get_owned_tiles(session_id),
        "all": await territory_service.get_all_tiles(session_id),
    }


@app.post("/api/session/{session_id}/territory/purchase")
async def purchase_territory_endpoint(session_id: str, body: TerritoryPurchaseRequest):
    map_data = await map_service.get_or_create_map(session_id)
    if not (0 <= body.x < map_data["width"] and 0 <= body.y < map_data["height"]):
        raise HTTPException(status_code=400, detail="지도 범위를 벗어났습니다")
    terrain = map_data["tiles"][body.y][body.x]

    try:
        nation, cost = await territory_service.purchase_tile(session_id, body.x, body.y, terrain)
    except territory_service.TerritoryError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tiles = await territory_service.get_owned_tiles(session_id)
    all_tiles = await territory_service.get_all_tiles(session_id)
    nation = await sync_land_capacity(session_id, len(tiles))  # reflect the bigger population cap right away

    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    await session.broadcast("territory_updated", {"all": all_tiles})
    return {"nation": nation.to_dict(), "tiles": tiles, "all": all_tiles, "cost": cost}


@app.get("/api/session/{session_id}/diplomacy/world")
async def get_world_relationships_endpoint(session_id: str):
    return {"relationships": await diplomacy_service.get_world_relationships(session_id)}


@app.get("/api/session/{session_id}/cities")
async def get_cities_endpoint(session_id: str):
    return {"cities": await city_service.get_cities(session_id)}


@app.post("/api/session/{session_id}/cities")
async def found_city_endpoint(session_id: str, body: CityFoundRequest):
    map_data = await map_service.get_or_create_map(session_id)
    if not (0 <= body.x < map_data["width"] and 0 <= body.y < map_data["height"]):
        raise HTTPException(status_code=400, detail="지도 범위를 벗어났습니다")

    session = await session_manager.get_or_create(session_id)
    owned = await territory_service.get_owned_tiles(session_id)
    owned_set = {(t["x"], t["y"]) for t in owned}

    try:
        nation, cost = await city_service.found_city(
            session_id,
            body.x,
            body.y,
            body.name,
            map_data["capital"],
            session.clock.current_date,
            owned_set,
        )
    except city_service.CityError as e:
        raise HTTPException(status_code=400, detail=str(e))

    cities = await city_service.get_cities(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    await session.broadcast("cities_updated", {"cities": cities})
    await log_service.add_log(
        session_id,
        session.clock.current_date["year"],
        session.clock.current_date["month"],
        "city",
        f"새 도시 '{body.name}'을(를) 세웠습니다.",
    )
    return {"nation": nation.to_dict(), "cities": cities, "cost": cost}


@app.get("/api/session/{session_id}/log")
async def get_game_log_endpoint(session_id: str):
    return {"entries": await log_service.get_logs(session_id)}
