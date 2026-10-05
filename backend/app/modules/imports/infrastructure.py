"""Import jobs and deduplication persisted through the existing schema."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    Account, Category, ImportJob, ImportKey, ImportRow, InvestmentPosition, Transaction, User,
)
from app.modules.ledger.ports import LedgerRead
from app.infrastructure.snapshot import snapshot


class SqlImportStore:
    def __init__(self, session: Session, ledger: LedgerRead):
        self.session = session
        self.ledger = ledger

    def job(self, user_id: int, job_id: int) -> dict | None:
        item = self.session.scalar(select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id))
        return snapshot(item) if item else None

    def jobs(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(ImportJob).where(
            ImportJob.user_id == user_id
        ).order_by(ImportJob.id.desc()).limit(20))]

    def rows(self, job_id: int, sheet_name: str | None = None, limit: int | None = None) -> list[dict]:
        query = select(ImportRow).where(ImportRow.job_id == job_id)
        if sheet_name is not None:
            query = query.where(ImportRow.sheet_name == sheet_name)
        query = query.order_by(ImportRow.row_number)
        if limit is not None:
            query = query.limit(limit)
        return [snapshot(item) for item in self.session.scalars(query)]

    def create_job(self, user_id: int, values: dict, sheets: dict) -> dict:
        item = ImportJob(user_id=user_id, **values)
        self.session.add(item)
        self.session.flush()
        for sheet_name, (_, rows) in sheets.items():
            self.session.add_all(ImportRow(
                user_id=user_id, job_id=item.id, sheet_name=sheet_name, row_number=number,
                raw=raw, parsed=None, error=None, dedup_key=None, status="UPLOADED",
            ) for number, raw in rows)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def update_job_and_rows(self, user_id: int, job_id: int, changes: dict, rows: list[dict]) -> dict:
        job = self.session.scalar(select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id))
        for key, value in changes.items():
            setattr(job, key, value)
        for values in rows:
            row = self.session.get(ImportRow, values["id"])
            for key in ("parsed", "error", "dedup_key", "status", "transaction_id"):
                if key in values:
                    setattr(row, key, values[key])
        self.session.commit()
        self.session.refresh(job)
        return snapshot(job)

    def delete_job(self, user_id: int, job_id: int) -> None:
        job = self.session.scalar(select(ImportJob).where(ImportJob.id == job_id, ImportJob.user_id == user_id))
        for row in self.session.scalars(select(ImportRow).where(ImportRow.job_id == job_id)).all():
            self.session.delete(row)
        self.session.delete(job)
        self.session.commit()

    def accounts(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Account).where(Account.user_id == user_id))]

    def categories(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Category).where(Category.user_id == user_id))]

    def existing_keys(self, user_id: int, keys: list[str]) -> set[str]:
        return set(self.session.scalars(select(ImportKey.key).where(
            ImportKey.user_id == user_id, ImportKey.key.in_(keys)
        ))) if keys else set()

    def lock_user(self, user_id: int) -> None:
        self.session.scalar(select(User).where(User.id == user_id).with_for_update())

    def add_imported_movement(self, user_id: int, values: dict, key: str) -> int:
        item = Transaction(user_id=user_id, **values)
        self.session.add(item)
        self.session.flush()
        self.session.add(ImportKey(user_id=user_id, key=key, transaction_id=item.id))
        self.session.flush()
        return item.id

    def investment_costs(self, user_id: int) -> dict:
        return dict(self.session.execute(select(
            InvestmentPosition.account_id, func.sum(InvestmentPosition.cost_basis)
        ).where(InvestmentPosition.user_id == user_id).group_by(InvestmentPosition.account_id)).all())

    def balances(self, user_id: int) -> dict:
        return self.ledger.balances(user_id)

    def transactions(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Transaction).where(
            Transaction.user_id == user_id
        ).order_by(Transaction.date, Transaction.id))]
