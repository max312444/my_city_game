from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.data.national_traits import NATIONAL_TRAIT_IDS
from app.db import Base
from app.models.nation import _random_trait


class RivalNation(Base):
    __tablename__ = "rival_nations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    rival_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    economy: Mapped[float] = mapped_column(Float)
    stability: Mapped[float] = mapped_column(Float)
    military: Mapped[float] = mapped_column(Float)
    relationship: Mapped[str] = mapped_column(String, default="peace")  # peace | war | defeated
    war_months: Mapped[int] = mapped_column(Integer, default=0)  # consecutive months of the current war
    personality: Mapped[str] = mapped_column(
        String, default="economic", server_default="economic"
    )  # aggressive | economic | isolationist
    national_trait: Mapped[str] = mapped_column(
        String, default=_random_trait, server_default=NATIONAL_TRAIT_IDS[0]
    )  # military | economic | production | scholarly — stat *growth* specialization

    def to_dict(self):
        return {
            "rival_id": self.rival_id,
            "name": self.name,
            "economy": round(self.economy, 1),
            "stability": round(self.stability, 1),
            "military": round(self.military, 1),
            "relationship": self.relationship,
            "war_months": self.war_months,
            "personality": self.personality,
            "national_trait": self.national_trait,
        }
