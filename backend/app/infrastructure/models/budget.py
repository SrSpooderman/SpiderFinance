from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.infrastructure.models.common import TimestampMixin


class Budget(TimestampMixin, Base):
    __tablename__ = "budgets"
    __table_args__ = (Index("ix_budgets_user", "user_id"), CheckConstraint("amount > 0"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    period: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
