from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class City(Base):
    """A player-founded city beyond the capital. Purely a map/flavor feature plus a
    small nation-wide economic bonus — there is no per-city economy simulation, the
    nation's stats stay a single aggregate (see nation_service)."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    founded_year: Mapped[int] = mapped_column(Integer)
    founded_month: Mapped[int] = mapped_column(Integer)
