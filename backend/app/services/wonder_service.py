import random

from sqlalchemy import select

from app.db import async_session_maker
from app.models.wonder import WonderClaim
from app.services.nation_service import STATS, _apply_delta, _get_or_create_nation
from app.services.tech_service import _get_researched_ids

# World wonders (Civilization-style): unlike a regular building, a wonder is a race —
# within one session, at most ONE of {player, rival x3} can ever finish each wonder.
# `boost_tech` never gates the attempt (anyone can start one anytime), it only decides
# how long it takes: already researched it -> fast_duration_months, otherwise the
# slower base_duration_months.
WONDERS = [
    {
        "id": "stonehenge",
        "name": "스톤헨지",
        "description": "천체의 움직임을 새긴 거대한 열석 구조물 — 완성한 국가에 오랜 안정을 가져다준다.",
        "boost_tech": "astronomy",
        "base_duration_months": 16,
        "fast_duration_months": 10,
        "cost": 3000,
        "effects": {"stability": 30},
    },
    {
        "id": "hanging_gardens",
        "name": "궁중정원",
        "description": "계단식으로 쌓아 올린 화려한 정원 — 풍요를 상징하며 식량 생산을 크게 늘린다.",
        "boost_tech": "irrigation",
        "base_duration_months": 16,
        "fast_duration_months": 10,
        "cost": 3000,
        "effects": {},
        "food_bonus": 0.4,
    },
    {
        "id": "pyramids",
        "name": "피라미드",
        "description": "거대한 석조 무덤 — 국가 행정력의 상징으로 경제 전반을 끌어올린다.",
        "boost_tech": "bureaucracy",
        "base_duration_months": 18,
        "fast_duration_months": 12,
        "cost": 3800,
        "effects": {"economy": 30},
    },
    {
        "id": "great_wall",
        "name": "만리장성",
        "description": "국경을 따라 이어지는 거대한 성벽 — 압도적인 방어력을 상징한다.",
        "boost_tech": "fortification",
        "base_duration_months": 18,
        "fast_duration_months": 12,
        "cost": 3800,
        "effects": {"military": 35},
    },
    {
        "id": "great_library",
        "name": "대도서관",
        "description": "세상의 모든 지식을 모으는 대도서관 — 학문 발전의 정점을 상징한다.",
        "boost_tech": "university",
        "base_duration_months": 20,
        "fast_duration_months": 13,
        "cost": 4500,
        "effects": {"education": 35},
    },
]

WONDER_BY_ID = {w["id"]: w for w in WONDERS}

# Rivals have no tech tree of their own (existing, documented simplification), so they
# can't get the boost_tech speedup the player gets — instead each active rival just
# rolls a small flat chance per unclaimed wonder per month, representing progress
# happening off-screen. Kept low: wonders should feel like a rare, tense race, not
# something that resolves itself in a year regardless of what the player does.
RIVAL_WONDER_CHANCE_PER_MONTH = 0.01


class WonderError(Exception):
    pass


def get_wonder_list() -> list[dict]:
    return WONDERS


async def _get_claims(db, session_id: str) -> dict[str, str]:
    result = await db.execute(select(WonderClaim).where(WonderClaim.session_id == session_id))
    return {c.wonder_id: c.claimed_by for c in result.scalars().all()}


async def get_wonder_state(session_id: str) -> dict:
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        claims = await _get_claims(db, session_id)
        await db.commit()
        return {
            "claims": claims,
            "current_wonder": nation.current_wonder or None,
            "current_wonder_months_left": nation.current_wonder_months_left,
        }


async def start_wonder(session_id: str, wonder_id: str):
    wonder = WONDER_BY_ID.get(wonder_id)
    if wonder is None:
        raise WonderError("알 수 없는 문화유산입니다")

    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        claims = await _get_claims(db, session_id)

        if wonder_id in claims:
            raise WonderError("이미 다른 국가가 완성한 문화유산입니다")
        if nation.current_wonder:
            raise WonderError("이미 건설 중인 문화유산이 있습니다")
        if nation.treasury < wonder["cost"]:
            raise WonderError("보유 금액이 부족합니다")

        researched = _get_researched_ids(nation)
        duration = (
            wonder["fast_duration_months"] if wonder["boost_tech"] in researched else wonder["base_duration_months"]
        )

        nation.treasury -= wonder["cost"]
        nation.current_wonder = wonder_id
        nation.current_wonder_months_left = duration

        await db.commit()
        await db.refresh(nation)
        return nation, duration


async def advance_wonder(session_id: str):
    """Called once per month tick, AFTER advance_rival_wonders (see session_manager) so
    a rival claim from this same month is already visible here. Returns
    (nation, completed_wonder_id | None)."""
    async with async_session_maker() as db:
        nation = await _get_or_create_nation(db, session_id)
        completed = None

        if nation.current_wonder:
            claims = await _get_claims(db, session_id)
            if nation.current_wonder in claims:
                # A rival beat us to it this very month — the whole investment (treasury
                # already spent, months already waited) is simply lost. No refund; this
                # is the intended risk of racing for a wonder.
                nation.current_wonder = ""
                nation.current_wonder_months_left = 0
            else:
                nation.current_wonder_months_left -= 1
                if nation.current_wonder_months_left <= 0:
                    wonder_id = nation.current_wonder
                    wonder = WONDER_BY_ID[wonder_id]
                    for stat, delta in wonder["effects"].items():
                        if stat in STATS:
                            value = getattr(nation, stat)
                            setattr(nation, stat, _apply_delta(value, delta))
                    nation.food_bonus += wonder.get("food_bonus", 0)

                    db.add(WonderClaim(session_id=session_id, wonder_id=wonder_id, claimed_by="player"))
                    nation.current_wonder = ""
                    nation.current_wonder_months_left = 0
                    completed = wonder_id

        await db.commit()
        await db.refresh(nation)
        return nation, completed


async def advance_rival_wonders(session_id: str, rivals: list[dict]) -> list[dict]:
    """Called once per month tick, independent of the player, BEFORE advance_wonder so
    a claim made here can still cancel the player's own in-progress attempt on the same
    wonder this same month. Returns a list of
    {"wonder_id", "wonder_name", "rival_id", "rival_name", "sabotaged_player"}."""
    async with async_session_maker() as db:
        claims = await _get_claims(db, session_id)
        events = []

        for wonder in WONDERS:
            if wonder["id"] in claims:
                continue
            for rival in rivals:
                if rival.get("relationship") == "defeated":
                    continue
                if random.random() < RIVAL_WONDER_CHANCE_PER_MONTH:
                    db.add(WonderClaim(session_id=session_id, wonder_id=wonder["id"], claimed_by=rival["rival_id"]))
                    claims[wonder["id"]] = rival["rival_id"]

                    nation = await _get_or_create_nation(db, session_id)
                    events.append(
                        {
                            "wonder_id": wonder["id"],
                            "wonder_name": wonder["name"],
                            "rival_id": rival["rival_id"],
                            "rival_name": rival["name"],
                            "sabotaged_player": nation.current_wonder == wonder["id"],
                        }
                    )
                    break  # claimed for this tick — no other rival can also grab it

        await db.commit()
        return events


async def delete_claims(session_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(WonderClaim).where(WonderClaim.session_id == session_id))
        for row in result.scalars().all():
            await db.delete(row)
        await db.commit()
