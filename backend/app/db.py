import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

# Overridable so tests (see tests/conftest.py) can point at a throwaway database
# instead of the real dev save file.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./my_city.db")

# NullPool: no connection reuse across checkouts. SQLite is a single embedded file
# so pooling buys nothing, and this sidesteps event-loop-affinity issues when tests
# run each async test in its own loop (pooled connections are loop-bound).
engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
