from app.db import async_session_maker
from app.services.nation_service import STATS, _apply_delta, _get_or_create_nation

TECH_TREE = [
    {
        "id": "agriculture",
        "name": "농경법",
        "description": "체계적인 농사법을 도입해 식량 생산을 늘리고 경제 기반을 다진다.",
        "cost": 300,
        "duration_months": 3,
        "prereqs": [],
        "effects": {"economy": 6, "stability": 3},
        "food_bonus": 0.3,
    },
    {
        "id": "writing_system",
        "name": "문자 체계",
        "description": "문자를 정립해 지식을 기록하고 전달하며 사회를 안정시킨다.",
        "cost": 300,
        "duration_months": 3,
        "prereqs": [],
        "effects": {"education": 6, "stability": 3},
    },
    {
        "id": "bronze_weapons",
        "name": "청동 무기",
        "description": "청동을 다뤄 더 나은 무기와 도구를 만들어 국방과 생산 모두를 개선한다.",
        "cost": 400,
        "duration_months": 4,
        "prereqs": [],
        "effects": {"military": 6, "economy": 3},
    },
    {
        "id": "irrigation",
        "name": "관개 시설",
        "description": "물길을 다스려 식량 생산력을 크게 높인다.",
        "cost": 1200,
        "duration_months": 7,
        "prereqs": ["agriculture"],
        "effects": {"economy": 10, "stability": 4},
        "food_bonus": 0.5,
    },
    {
        "id": "code_of_law",
        "name": "율법",
        "description": "성문법을 제정해 사회 질서를 확립하고 교육 제도를 정비한다.",
        "cost": 1200,
        "duration_months": 7,
        "prereqs": ["writing_system"],
        "effects": {"stability": 10, "education": 4},
    },
    {
        "id": "iron_weapons",
        "name": "철제 무기",
        "description": "철을 제련해 훨씬 강력한 무기를 만들고 교역로를 지킨다.",
        "cost": 1500,
        "duration_months": 8,
        "prereqs": ["bronze_weapons"],
        "effects": {"military": 12, "economy": 4},
    },
    # --- 2단계 확장: 경제/학문/군사 세 갈래를 더 깊게, 서로 교차하는 선행조건으로 연장 ---
    {
        "id": "currency",
        "name": "화폐 주조",
        "description": "표준화된 화폐를 만들어 교역을 촉진하고 상업을 크게 발전시킨다.",
        "cost": 1300,
        "duration_months": 7,
        "prereqs": ["agriculture"],
        "effects": {"economy": 14, "stability": 3},
    },
    {
        "id": "horseback_riding",
        "name": "기마술",
        "description": "말을 길들여 기동력을 확보하고 교역과 전쟁 모두에 활용한다.",
        "cost": 1400,
        "duration_months": 7,
        "prereqs": ["bronze_weapons"],
        "effects": {"military": 14, "economy": 3},
    },
    {
        "id": "astronomy",
        "name": "천문학",
        "description": "하늘의 움직임을 관측하고 기록해 역법과 학문을 발전시킨다.",
        "cost": 1300,
        "duration_months": 7,
        "prereqs": ["writing_system"],
        "effects": {"education": 14, "stability": 3},
    },
    {
        "id": "philosophy",
        "name": "철학",
        "description": "존재와 사회에 대한 깊은 사유가 학문 전반의 기틀을 다진다.",
        "cost": 2600,
        "duration_months": 10,
        "prereqs": ["code_of_law"],
        "effects": {"education": 18, "stability": 6},
    },
    {
        "id": "road_network",
        "name": "도로망",
        "description": "국토를 잇는 도로를 놓아 물자와 사람의 이동을 크게 빠르게 한다.",
        "cost": 2500,
        "duration_months": 10,
        "prereqs": ["currency"],
        "effects": {"economy": 18, "stability": 5},
    },
    {
        "id": "fortification",
        "name": "축성술",
        "description": "성벽과 요새를 쌓아 국경을 굳건히 지킨다.",
        "cost": 2700,
        "duration_months": 10,
        "prereqs": ["iron_weapons"],
        "effects": {"military": 20, "stability": 5},
    },
    {
        "id": "bureaucracy",
        "name": "관료제",
        "description": "체계적인 행정 조직을 갖춰 국가 운영의 효율을 높인다.",
        "cost": 2800,
        "duration_months": 11,
        "prereqs": ["code_of_law", "currency"],
        "effects": {"stability": 22, "education": 5},
    },
    {
        "id": "trade_routes",
        "name": "교역로",
        "description": "먼 나라까지 이어지는 교역로를 개척해 상업을 크게 번성시킨다.",
        "cost": 3000,
        "duration_months": 11,
        "prereqs": ["road_network"],
        "effects": {"economy": 24, "stability": 3},
    },
    {
        "id": "cavalry_tactics",
        "name": "기병 전술",
        "description": "기마 부대를 체계적으로 운용하는 전술을 확립한다.",
        "cost": 3000,
        "duration_months": 11,
        "prereqs": ["horseback_riding", "fortification"],
        "effects": {"military": 22, "economy": 4},
    },
    {
        "id": "university",
        "name": "대학",
        "description": "학문을 전문적으로 가르치고 연구하는 고등 교육 기관을 세운다.",
        "cost": 4200,
        "duration_months": 14,
        "prereqs": ["philosophy", "astronomy"],
        "effects": {"education": 28, "economy": 6},
    },
    {
        "id": "banking",
        "name": "은행업",
        "description": "자본을 모으고 굴리는 금융 체계가 국가 경제를 한 단계 끌어올린다.",
        "cost": 4400,
        "duration_months": 14,
        "prereqs": ["trade_routes", "bureaucracy"],
        "effects": {"economy": 34, "stability": 6},
    },
    {
        "id": "steel_weapons",
        "name": "강철 무기",
        "description": "강철을 벼려 이전과는 비교할 수 없는 무기와 갑주를 만든다.",
        "cost": 4500,
        "duration_months": 14,
        "prereqs": ["fortification", "cavalry_tactics"],
        "effects": {"military": 30, "economy": 6},
    },
    {
        "id": "printing_press",
        "name": "인쇄술",
        "description": "지식을 대량으로 인쇄해 퍼뜨리며 학문의 대중화를 이끈다.",
        "cost": 5200,
        "duration_months": 16,
        "prereqs": ["university"],
        "effects": {"education": 36, "economy": 10},
    },
    {
        "id": "gunpowder",
        "name": "화약",
        "description": "화약 무기를 개발해 전쟁의 양상을 근본적으로 바꾼다.",
        "cost": 5600,
        "duration_months": 16,
        "prereqs": ["steel_weapons"],
        "effects": {"military": 40, "stability": 6},
    },
]

TECH_BY_ID = {tech["id"]: tech for tech in TECH_TREE}


class TechError(Exception):
    pass


def get_tech_tree() -> list[dict]:
    return TECH_TREE


def _get_researched_ids(nation) -> list[str]:
    if not nation.researched_techs:
        return []
    return [t for t in nation.researched_techs.split(",") if t]


def _set_researched_ids(nation, ids: list[str]):
    nation.researched_techs = ",".join(ids)


async def get_research_state(session_id: str) -> dict:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        await db.commit()
        return {
            "researched": _get_researched_ids(nation),
            "current_research": nation.current_research or None,
            "current_research_months_left": nation.current_research_months_left,
        }


async def start_research(session_id: str, tech_id: str):
    tech = TECH_BY_ID.get(tech_id)
    if tech is None:
        raise TechError("알 수 없는 기술입니다")

    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        researched = _get_researched_ids(nation)

        if tech_id in researched:
            raise TechError("이미 연구한 기술입니다")
        if nation.current_research:
            raise TechError("이미 연구 중인 기술이 있습니다")
        if not all(p in researched for p in tech["prereqs"]):
            raise TechError("선행 기술을 먼저 연구해야 합니다")
        if nation.treasury < tech["cost"]:
            raise TechError("보유 금액이 부족합니다")

        nation.treasury -= tech["cost"]
        nation.current_research = tech_id
        nation.current_research_months_left = tech["duration_months"]

        await db.commit()
        await db.refresh(nation)
        return nation, _get_researched_ids(nation)


async def advance_research(session_id: str):
    """Called once per month tick. Returns (nation, completed_tech_id | None)."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        completed = None

        if nation.current_research:
            nation.current_research_months_left -= 1
            if nation.current_research_months_left <= 0:
                tech_id = nation.current_research
                tech = TECH_BY_ID[tech_id]
                for stat, delta in tech["effects"].items():
                    if stat in STATS:
                        value = getattr(nation, stat)
                        setattr(nation, stat, _apply_delta(value, delta))
                nation.food_bonus += tech.get("food_bonus", 0)

                researched = _get_researched_ids(nation)
                researched.append(tech_id)
                _set_researched_ids(nation, researched)

                nation.current_research = ""
                nation.current_research_months_left = 0
                completed = tech_id

        await db.commit()
        await db.refresh(nation)
        return nation, completed
