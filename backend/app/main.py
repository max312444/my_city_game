import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from app.core.session_manager import Speed, session_manager, _compute_resource_bonus
from app.db import init_db
from app.services.nation_service import (
    apply_effects,
    delete_nation,
    get_or_create_nation,
    nation_exists,
    set_nation_name,
)
from app.services import tech_service
from app.services import building_service
from app.services import wonder_service
from app.services import great_person_service
from app.services import diplomacy_service
from app.services import map_service
from app.services import auth_service
from app.services import territory_service
from app.services import city_service
from app.services import log_service
from app.services import trade_service
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


class BuildingRequest(BaseModel):
    building_id: str


class WonderRequest(BaseModel):
    wonder_id: str


class TradeRouteRequest(BaseModel):
    rival_id: str


class SellFoodRequest(BaseModel):
    amount: float


class DiplomacyActionRequest(BaseModel):
    rival_id: str


class PeaceOfferResponseRequest(BaseModel):
    rival_id: str
    accept: bool


class SignupRequest(BaseModel):
    username: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    username: str
    password: str


class NationNameRequest(BaseModel):
    name: str
    difficulty: str | None = None


class TerritoryPurchaseRequest(BaseModel):
    x: int
    y: int


class AttackCityRequest(BaseModel):
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
    await wonder_service.delete_claims(session_id)
    await trade_service.delete_routes(session_id)
    session_manager.remove(session_id)
    return {"ok": True}


@app.post("/api/session/{session_id}/nation/name")
async def set_nation_name_endpoint(session_id: str, body: NationNameRequest):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="이름을 입력해주세요")
    nation = await set_nation_name(session_id, name, body.difficulty)
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


@app.get("/api/session/{session_id}/buildings")
async def get_building_state_endpoint(session_id: str):
    state = await building_service.get_building_state(session_id)
    return {"buildings": building_service.get_building_list(), **state}


@app.post("/api/session/{session_id}/buildings/build")
async def build_building_endpoint(session_id: str, body: BuildingRequest):
    try:
        nation, built = await building_service.start_building(session_id, body.building_id)
    except building_service.BuildingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return {
        "nation": nation.to_dict(),
        "built": built,
        "current_building": nation.current_building or None,
        "current_building_months_left": nation.current_building_months_left,
    }


@app.get("/api/session/{session_id}/wonders")
async def get_wonder_state_endpoint(session_id: str):
    state = await wonder_service.get_wonder_state(session_id)
    return {"wonders": wonder_service.get_wonder_list(), **state}


@app.post("/api/session/{session_id}/wonders/start")
async def start_wonder_endpoint(session_id: str, body: WonderRequest):
    try:
        nation, duration = await wonder_service.start_wonder(session_id, body.wonder_id)
    except wonder_service.WonderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return {
        "nation": nation.to_dict(),
        "current_wonder": nation.current_wonder or None,
        "current_wonder_months_left": nation.current_wonder_months_left,
        "duration": duration,
    }


@app.get("/api/session/{session_id}/great-people")
async def get_great_people_history(session_id: str):
    return {"history": await great_person_service.get_history(session_id)}


@app.get("/api/session/{session_id}/diplomacy")
async def get_diplomacy_state(session_id: str):
    session = await session_manager.get_or_create(session_id)
    rivals = await diplomacy_service.get_rivals(session_id)
    cities = await city_service.get_cities(session_id)
    for r in rivals:
        target = session.siege_targets.get(r["rival_id"])
        city = next((c for c in cities if target and c["x"] == target[0] and c["y"] == target[1]), None)
        r["siege_target_name"] = city["name"] if city else None
    return {"rivals": rivals}


@app.post("/api/session/{session_id}/diplomacy/attack-city")
async def attack_city_endpoint(session_id: str, body: AttackCityRequest):
    owner = await territory_service.owner_at(session_id, body.x, body.y)
    if owner is None or owner == "player":
        raise HTTPException(status_code=400, detail="적국의 도시가 아닙니다")

    rivals = await diplomacy_service.get_rivals(session_id)
    rival = next((r for r in rivals if r["rival_id"] == owner), None)
    if rival is None or rival["relationship"] == "defeated":
        raise HTTPException(status_code=400, detail="공격할 수 없는 대상입니다")

    map_data = await map_service.get_or_create_map(session_id)
    rival_capital = next((rc for rc in map_data["rival_capitals"] if rc["rival_id"] == owner), None)
    is_capital = rival_capital is not None and rival_capital["x"] == body.x and rival_capital["y"] == body.y
    cities = await city_service.get_cities(session_id)
    target_city = next((c for c in cities if c["x"] == body.x and c["y"] == body.y and c["owner"] == owner), None)
    if not is_capital and target_city is None:
        raise HTTPException(status_code=400, detail="해당 위치에 도시가 없습니다")
    city_name = rival_capital["name"] if is_capital else target_city["name"]

    session = await session_manager.get_or_create(session_id)
    nation = None
    if rival["relationship"] != "war":
        nation, rivals = await diplomacy_service.declare_war(session_id, owner)
        await session.broadcast("nation_updated", {"nation": nation.to_dict()})
        await session.broadcast("rivals_updated", {"rivals": rivals})

    session.siege_targets[owner] = (body.x, body.y)
    await log_service.add_log(
        session_id,
        session.clock.current_date["year"],
        session.clock.current_date["month"],
        "war",
        f"{rival['name']}의 도시 '{city_name}'을(를) 목표로 공격을 개시했습니다.",
    )
    return {"rivals": rivals, "city_name": city_name, "rival_id": owner}


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


@app.get("/api/session/{session_id}/diplomacy/peace-offer")
async def get_peace_offer(session_id: str):
    session = await session_manager.get_or_create(session_id)
    return {"offer": session.pending_peace_offer}


@app.post("/api/session/{session_id}/diplomacy/peace-offer/respond")
async def respond_peace_offer_endpoint(session_id: str, body: PeaceOfferResponseRequest):
    session = await session_manager.get_or_create(session_id)
    offer = session.pending_peace_offer
    if offer is None or offer["rival_id"] != body.rival_id:
        raise HTTPException(status_code=404, detail="제안이 이미 처리되었습니다")

    session.pending_peace_offer = None
    await session.broadcast("peace_offer_available", {"offer": None})

    if body.accept:
        rivals = await diplomacy_service.accept_peace_offer(session_id, body.rival_id)
        await session.broadcast("rivals_updated", {"rivals": rivals})
        await log_service.add_log(
            session_id,
            session.clock.current_date["year"],
            session.clock.current_date["month"],
            "war",
            f"{offer['rival_name']}과(와) 평화 협정을 맺었습니다.",
        )
        return {"accepted": True, "rivals": rivals}

    return {"accepted": False}


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


@app.get("/api/session/{session_id}/trade")
async def get_trade_state_endpoint(session_id: str):
    rivals = await diplomacy_service.get_rivals(session_id)
    map_data = await map_service.get_or_create_map(session_id)
    cities = await city_service.get_cities(session_id)
    player_cities = [c for c in cities if c["owner"] == city_service.PLAYER_OWNER]
    resource_bonus = _compute_resource_bonus(map_data, player_cities)
    return await trade_service.get_trade_state(session_id, rivals, resource_bonus)


@app.post("/api/session/{session_id}/trade/establish")
async def establish_trade_route_endpoint(session_id: str, body: TradeRouteRequest):
    rivals = await diplomacy_service.get_rivals(session_id)
    rival = next((r for r in rivals if r["rival_id"] == body.rival_id), None)
    if rival is None:
        raise HTTPException(status_code=400, detail="알 수 없는 국가입니다")
    try:
        await trade_service.establish_route(session_id, body.rival_id, rival["relationship"])
    except trade_service.TradeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@app.post("/api/session/{session_id}/trade/close")
async def close_trade_route_endpoint(session_id: str, body: TradeRouteRequest):
    await trade_service.close_route(session_id, body.rival_id)
    return {"ok": True}


@app.post("/api/session/{session_id}/trade/sell-food")
async def sell_food_endpoint(session_id: str, body: SellFoodRequest):
    try:
        nation = await trade_service.sell_food(session_id, body.amount)
    except trade_service.TradeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    session = await session_manager.get_or_create(session_id)
    await session.broadcast("nation_updated", {"nation": nation.to_dict()})
    return {"nation": nation.to_dict()}


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
