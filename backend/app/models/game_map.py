from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GameMap(Base):
    __tablename__ = "game_maps"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    data: Mapped[str] = mapped_column(Text)
