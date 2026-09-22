from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GameLog(Base):
    """A persistent chronicle entry — tech completed, wars, disasters, great people,
    city foundings, world news between rivals. Deliberately excludes routine tile
    purchases and passive monthly stat drift (too frequent to be worth reading back)."""

    __tablename__ = "game_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String)  # tech | event | great_person | war | world | city
    message: Mapped[str] = mapped_column(String)
