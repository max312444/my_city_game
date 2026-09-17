import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.great_person import GreatPersonAppearance
from app.services.nation_service import apply_random_event

GREAT_PERSON_CHANCE_PER_MONTH = 0.03

GREAT_PEOPLE = [
    {
        "id": "merchant_hayun",
        "category": "economy",
        "name": "대상인 하윤",
        "title": "대상인",
        "description": "뛰어난 상재를 지닌 상인이 나타나 새로운 교역로를 개척했습니다.",
        "stat_effects": {"economy": 0.15},
        "treasury_loss_months": -2,
    },
    {
        "id": "merchant_soyoung",
        "category": "economy",
        "name": "거상 소영",
        "title": "거상",
        "description": "수완 좋은 거상이 등장해 시장에 활기를 불어넣었습니다.",
        "stat_effects": {"economy": 0.15},
        "treasury_loss_months": -2,
    },
    {
        "id": "general_dogyeom",
        "category": "military",
        "name": "명장 도겸",
        "title": "명장",
        "description": "뛰어난 명장이 나타나 군을 재정비하고 사기를 끌어올렸습니다.",
        "stat_effects": {"military": 0.18},
    },
    {
        "id": "general_haesol",
        "category": "military",
        "name": "장군 해솔",
        "title": "장군",
        "description": "용맹한 장군이 등장해 국경의 방비를 크게 강화했습니다.",
        "stat_effects": {"military": 0.18},
    },
    {
        "id": "scholar_dain",
        "category": "education",
        "name": "현자 다인",
        "title": "현자",
        "description": "박식한 현자가 나타나 학문 발전에 큰 획을 그었습니다.",
        "stat_effects": {"education": 0.18},
    },
    {
        "id": "scholar_mujin",
        "category": "education",
        "name": "학자 무진",
        "title": "학자",
        "description": "뛰어난 학자가 등장해 새로운 지식을 널리 퍼뜨렸습니다.",
        "stat_effects": {"education": 0.18},
    },
    {
        "id": "statesman_seojun",
        "category": "stability",
        "name": "명재상 서준",
        "title": "재상",
        "description": "지혜로운 재상이 나타나 국정을 안정시켰습니다.",
        "stat_effects": {"stability": 0.18},
    },
    {
        "id": "statesman_haeun",
        "category": "stability",
        "name": "지도자 하은",
        "title": "지도자",
        "description": "덕망 높은 지도자가 등장해 민심을 하나로 모았습니다.",
        "stat_effects": {"stability": 0.18},
    },
]

GREAT_PEOPLE_BY_ID = {p["id"]: p for p in GREAT_PEOPLE}
CATEGORY_STAT = {"economy": "economy", "military": "military", "education": "education", "stability": "stability"}


async def _get_used_ids(session_id: str) -> set[str]:
    async with async_session_maker() as db:
        result = await db.execute(
            select(GreatPersonAppearance.person_id).where(GreatPersonAppearance.session_id == session_id)
        )
        return {row[0] for row in result.all()}


async def delete_history(session_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(
            select(GreatPersonAppearance).where(GreatPersonAppearance.session_id == session_id)
        )
        for row in result.scalars().all():
            await db.delete(row)
        await db.commit()


async def get_history(session_id: str) -> list[dict]:
    async with async_session_maker() as db:
        result = await db.execute(
            select(GreatPersonAppearance)
            .where(GreatPersonAppearance.session_id == session_id)
            .order_by(GreatPersonAppearance.id)
        )
        rows = result.scalars().all()
        history = []
        for row in rows:
            person = GREAT_PEOPLE_BY_ID.get(row.person_id)
            if person is None:
                continue
            history.append(
                {
                    "id": person["id"],
                    "name": person["name"],
                    "title": person["title"],
                    "category": person["category"],
                    "description": person["description"],
                    "year": row.year,
                    "month": row.month,
                }
            )
        return history


async def maybe_spawn_great_person(session_id: str, nation, current_date: dict):
    """Returns (nation, spawned_person | None). Never summoned by the player."""
    if random.random() >= GREAT_PERSON_CHANCE_PER_MONTH:
        return nation, None

    used_ids = await _get_used_ids(session_id)
    available = [p for p in GREAT_PEOPLE if p["id"] not in used_ids]
    if not available:
        return nation, None

    weights = [max(0.1, getattr(nation, CATEGORY_STAT[p["category"]])) for p in available]
    person = random.choices(available, weights=weights, k=1)[0]

    nation = await apply_random_event(session_id, person)

    async with async_session_maker() as db:
        db.add(
            GreatPersonAppearance(
                session_id=session_id,
                person_id=person["id"],
                year=current_date["year"],
                month=current_date["month"],
            )
        )
        await db.commit()

    return nation, person
