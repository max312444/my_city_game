from app.db import async_session_maker
from app.services.nation_service import STATS, _apply_delta, _get_or_create_nation
from app.services.tech_service import _get_researched_ids

# Each building is unlocked by a specific tech (Civilization-style: research opens up
# what you're *able* to build, but building it is still a separate treasury+time
# investment) — never resource-specific, any building can go up regardless of what's
# nearby. One building under construction at a time, same "single slot" shape as
# research (a second, independent slot — a nation can research a tech and build a
# building in the same month).
BUILDINGS = [
    {
        "id": "farm",
        "name": "농장",
        "description": "농경법을 활용해 전담 농지를 조성하여 식량 생산을 늘린다.",
        "requires_tech": "agriculture",
        "cost": 500,
        "duration_months": 4,
        "effects": {},
        "food_bonus": 0.2,
    },
    {
        "id": "blacksmith",
        "name": "대장간",
        "description": "청동 무기를 전문적으로 벼려 군대의 장비를 개선한다.",
        "requires_tech": "bronze_weapons",
        "cost": 600,
        "duration_months": 4,
        "effects": {"military": 8},
    },
    {
        "id": "school",
        "name": "서당",
        "description": "문자를 가르치는 서당을 세워 백성의 지식 수준을 높인다.",
        "requires_tech": "writing_system",
        "cost": 600,
        "duration_months": 4,
        "effects": {"education": 8},
    },
    {
        "id": "market",
        "name": "시장",
        "description": "화폐 유통을 전담하는 상설 시장을 열어 상업을 활성화한다.",
        "requires_tech": "currency",
        "cost": 900,
        "duration_months": 5,
        "effects": {"economy": 10},
    },
    {
        "id": "ranch",
        "name": "목장",
        "description": "말을 사육하는 목장을 조성해 기동력과 물자 운송을 개선한다.",
        "requires_tech": "horseback_riding",
        "cost": 900,
        "duration_months": 5,
        "effects": {"military": 10},
    },
    {
        "id": "observatory",
        "name": "천문대",
        "description": "하늘을 관측하는 시설을 세워 역법과 항해술 연구를 뒷받침한다.",
        "requires_tech": "astronomy",
        "cost": 900,
        "duration_months": 5,
        "effects": {"education": 10},
    },
    {
        "id": "temple",
        "name": "신전",
        "description": "철학적 사유를 뒷받침하는 신전을 세워 민심을 다독인다.",
        "requires_tech": "philosophy",
        "cost": 1800,
        "duration_months": 7,
        "effects": {"stability": 12},
    },
    {
        "id": "fortress",
        "name": "요새",
        "description": "축성술을 적용한 요새를 쌓아 국경 방비를 크게 강화한다.",
        "requires_tech": "fortification",
        "cost": 2000,
        "duration_months": 7,
        "effects": {"military": 16},
    },
    {
        "id": "government_hall",
        "name": "관공서",
        "description": "관료제를 뒷받침하는 관공서를 세워 국정 운영을 안정시킨다.",
        "requires_tech": "bureaucracy",
        "cost": 2200,
        "duration_months": 8,
        "effects": {"stability": 18},
    },
    {
        "id": "trading_post",
        "name": "상관",
        "description": "교역로 거점에 상관을 세워 먼 나라와의 교역을 상시화한다.",
        "requires_tech": "trade_routes",
        "cost": 2400,
        "duration_months": 8,
        "effects": {"economy": 20},
    },
    {
        "id": "university_building",
        "name": "대학",
        "description": "고등 교육 기관을 세워 학문 발전에 박차를 가한다.",
        "requires_tech": "university",
        "cost": 3200,
        "duration_months": 10,
        "effects": {"education": 24},
    },
    {
        "id": "bank",
        "name": "은행",
        "description": "은행업을 뒷받침하는 금융 기관을 세워 국가 경제를 크게 끌어올린다.",
        "requires_tech": "banking",
        "cost": 3600,
        "duration_months": 10,
        "effects": {"economy": 28},
    },
    {
        "id": "arsenal",
        "name": "조병창",
        "description": "화약 무기를 대량으로 생산하는 조병창을 세운다.",
        "requires_tech": "gunpowder",
        "cost": 4200,
        "duration_months": 12,
        "effects": {"military": 32},
    },
]

BUILDING_BY_ID = {b["id"]: b for b in BUILDINGS}


class BuildingError(Exception):
    pass


def get_building_list() -> list[dict]:
    return BUILDINGS


def _get_built_ids(nation) -> list[str]:
    if not nation.built_buildings:
        return []
    return [b for b in nation.built_buildings.split(",") if b]


def _set_built_ids(nation, ids: list[str]):
    nation.built_buildings = ",".join(ids)


async def get_building_state(session_id: str) -> dict:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        await db.commit()
        return {
            "built": _get_built_ids(nation),
            "researched": _get_researched_ids(nation),
            "current_building": nation.current_building or None,
            "current_building_months_left": nation.current_building_months_left,
        }


async def start_building(session_id: str, building_id: str):
    building = BUILDING_BY_ID.get(building_id)
    if building is None:
        raise BuildingError("알 수 없는 건물입니다")

    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        built = _get_built_ids(nation)
        researched = _get_researched_ids(nation)

        if building_id in built:
            raise BuildingError("이미 건설한 건물입니다")
        if nation.current_building:
            raise BuildingError("이미 건설 중인 건물이 있습니다")
        if building["requires_tech"] not in researched:
            raise BuildingError("선행 기술을 먼저 연구해야 합니다")
        if nation.treasury < building["cost"]:
            raise BuildingError("보유 금액이 부족합니다")

        nation.treasury -= building["cost"]
        nation.current_building = building_id
        nation.current_building_months_left = building["duration_months"]

        await db.commit()
        await db.refresh(nation)
        return nation, built


async def advance_building(session_id: str):
    """Called once per month tick. Returns (nation, completed_building_id | None)."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        completed = None

        if nation.current_building:
            nation.current_building_months_left -= 1
            if nation.current_building_months_left <= 0:
                building_id = nation.current_building
                building = BUILDING_BY_ID[building_id]
                for stat, delta in building["effects"].items():
                    if stat in STATS:
                        value = getattr(nation, stat)
                        setattr(nation, stat, _apply_delta(value, delta))
                nation.food_bonus += building.get("food_bonus", 0)

                built = _get_built_ids(nation)
                built.append(building_id)
                _set_built_ids(nation, built)

                nation.current_building = ""
                nation.current_building_months_left = 0
                completed = building_id

        await db.commit()
        await db.refresh(nation)
        return nation, completed
