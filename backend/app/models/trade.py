from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TradeRoute(Base):
    """A route's existence means "established" — no separate active/inactive flag.
    War with that rival simply suspends its monthly income (see trade_service.
    advance_trade); peace resumes it automatically, no need to re-establish."""

    __tablename__ = "trade_routes"
    __table_args__ = (UniqueConstraint("session_id", "rival_id", name="uq_trade_route_session_rival"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    rival_id: Mapped[str] = mapped_column(String)
