import random

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

INCOME_PER_ECONOMY_POINT = 10
STAT_MAX = 1000.0


def _initial_stat() -> float:
    return random.uniform(5, 10)


class Nation(Base):
    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, default="플레이어 국가")
    economy: Mapped[float] = mapped_column(Float, default=_initial_stat)
    stability: Mapped[float] = mapped_column(Float, default=_initial_stat)
    military: Mapped[float] = mapped_column(Float, default=_initial_stat)
    education: Mapped[float] = mapped_column(Float, default=_initial_stat)
    treasury: Mapped[float] = mapped_column(Float, default=0.0)
    year: Mapped[int] = mapped_column(Integer, default=1)
    month: Mapped[int] = mapped_column(Integer, default=1)

    def to_dict(self):
        return {
            "name": self.name,
            "economy": round(self.economy, 1),
            "stability": round(self.stability, 1),
            "military": round(self.military, 1),
            "education": round(self.education, 1),
            "monthly_income": round(self.economy * INCOME_PER_ECONOMY_POINT, 1),
            "treasury": round(self.treasury, 1),
        }
