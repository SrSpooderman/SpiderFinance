from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.infrastructure.models.common import TimestampMixin


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"
    __table_args__ = (Index("ix_import_jobs_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(8))
    sheet_names: Mapped[list] = mapped_column(JSON)
    selected_sheet: Mapped[str | None] = mapped_column(String(120))
    headers: Mapped[list] = mapped_column(JSON)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    default_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="RESTRICT"))
    positive_is_income: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="UPLOADED")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)


class ImportRow(TimestampMixin, Base):
    __tablename__ = "import_rows"
    __table_args__ = (Index("ix_import_rows_job_sheet", "job_id", "sheet_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"))
    sheet_name: Mapped[str] = mapped_column(String(120))
    row_number: Mapped[int] = mapped_column(Integer)
    raw: Mapped[dict] = mapped_column(JSON)
    parsed: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    dedup_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="UPLOADED")
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))


class ImportKey(TimestampMixin, Base):
    __tablename__ = "import_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_import_key_user_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
