from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class RivalRelationship(Base):
    """Relationship between two rival (AI) nations, independent of the player —
    the "다른 국가들도 각자 성향에 따라 완전 자율로 발전한다" part of the game's design that
    hadn't been built yet. rival_a/rival_b are always stored in sorted order so a
    pair has exactly one row regardless of which side is queried first."""

    __tablename__ = "rival_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    rival_a: Mapped[str] = mapped_column(String)
    rival_b: Mapped[str] = mapped_column(String)
    relationship: Mapped[str] = mapped_column(String, default="peace")  # peace | war | alliance
