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
