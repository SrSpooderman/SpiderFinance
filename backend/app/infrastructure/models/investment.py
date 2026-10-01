from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.infrastructure.models.common import TimestampMixin


class InvestmentContribution(TimestampMixin, Base):
    __tablename__ = "investment_contributions"
    __table_args__ = (Index("ix_investment_contributions_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"), unique=True)


class InvestmentPosition(TimestampMixin, Base):
    __tablename__ = "investment_positions"
    __table_args__ = (
        Index("ix_investment_positions_user_account", "user_id", "account_id"),
        CheckConstraint("units > 0"),
        CheckConstraint("cost_basis >= 0"),
        CheckConstraint("market_value >= 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120))
    symbol: Mapped[str | None] = mapped_column(String(32))
    units: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    valued_on: Mapped[date] = mapped_column(Date)


class NetWorthSnapshot(TimestampMixin, Base):
    __tablename__ = "net_worth_snapshots"
    __table_args__ = (
        Index("ix_net_worth_snapshots_user_date", "user_id", "date"),
        UniqueConstraint("user_id", "date", "currency", name="uq_net_worth_user_date_currency"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    assets: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    liabilities: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    net_worth: Mapped[Decimal] = mapped_column(Numeric(18, 2))
