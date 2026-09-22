from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class City(Base):
    """A founded city beyond the capital — the player's own or (autonomously) a
    rival's. Purely a map/flavor feature plus a small nation-wide economic bonus for
    the player — there is no per-city economy simulation, each nation's stats stay a
    single aggregate (see nation_service)."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    x: Mapped[int] = mapped_column(Integer)
    y: Mapped[int] = mapped_column(Integer)
    owner: Mapped[str] = mapped_column(String, default="player", server_default="player")
    founded_year: Mapped[int] = mapped_column(Integer)
    founded_month: Mapped[int] = mapped_column(Integer)
