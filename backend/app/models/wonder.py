from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WonderClaim(Base):
    """Created once, the instant a wonder is completed by anyone (player or a rival) —
    its mere existence for a given (session_id, wonder_id) means that wonder is gone
    forever for everyone else in that session. See wonder_service for the race/loss
    mechanic this backs."""

    __tablename__ = "wonder_claims"
    __table_args__ = (UniqueConstraint("session_id", "wonder_id", name="uq_wonder_claim_session_wonder"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String, index=True)
    wonder_id: Mapped[str] = mapped_column(String)
    claimed_by: Mapped[str] = mapped_column(String)  # "player" or a rival_id
