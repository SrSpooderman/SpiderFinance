from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.infrastructure.models.common import TimestampMixin


class Scenario(TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (Index("ix_scenarios_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(String(500))
    changes: Mapped[dict] = mapped_column(JSON)
