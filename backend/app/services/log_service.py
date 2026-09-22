from sqlalchemy import select

from app.db import async_session_maker
from app.models.game_log import GameLog

MAX_ENTRIES_RETURNED = 300


async def add_log(session_id: str, year: int, month: int, category: str, message: str) -> None:
    async with async_session_maker() as db:
        db.add(GameLog(session_id=session_id, year=year, month=month, category=category, message=message))
        await db.commit()


async def add_logs(session_id: str, year: int, month: int, category: str, messages: list[str]) -> None:
    if not messages:
        return
    async with async_session_maker() as db:
        for message in messages:
            db.add(GameLog(session_id=session_id, year=year, month=month, category=category, message=message))
        await db.commit()


async def get_logs(session_id: str) -> list[dict]:
    """Oldest-first (a chronicle reads like a history book) — the frontend can scroll
    to the bottom to see the latest entry."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(GameLog)
            .where(GameLog.session_id == session_id)
            .order_by(GameLog.id.desc())
            .limit(MAX_ENTRIES_RETURNED)
        )
        rows = list(reversed(result.scalars().all()))
        return [
            {"year": r.year, "month": r.month, "category": r.category, "message": r.message} for r in rows
        ]


async def delete_logs(session_id: str) -> None:
    async with async_session_maker() as db:
        result = await db.execute(select(GameLog).where(GameLog.session_id == session_id))
        for row in result.scalars().all():
            await db.delete(row)
        await db.commit()
