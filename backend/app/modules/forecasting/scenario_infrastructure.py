"""Scenario persistence over the current scenario and account tables."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import Account, Scenario
from app.infrastructure.snapshot import snapshot


class SqlScenarioStore:
    def __init__(self, session: Session):
        self.session = session

    def active_account_ids(self, user_id: int) -> set[int]:
        return set(self.session.scalars(select(Account.id).where(
            Account.user_id == user_id, Account.active == True
        )))

    def list(self, user_id: int) -> list[dict]:
        return [snapshot(item) for item in self.session.scalars(select(Scenario).where(
            Scenario.user_id == user_id
        ).order_by(Scenario.id.desc()))]

    def get(self, user_id: int, scenario_id: int) -> dict | None:
        item = self.session.scalar(select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == user_id))
        return snapshot(item) if item else None

    def create(self, user_id: int, values: dict) -> dict:
        item = Scenario(user_id=user_id, **values)
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def update(self, user_id: int, scenario_id: int, values: dict) -> dict:
        item = self.session.scalar(select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == user_id))
        for key, value in values.items():
            setattr(item, key, value)
        self.session.commit()
        self.session.refresh(item)
        return snapshot(item)

    def delete(self, user_id: int, scenario_id: int) -> None:
        item = self.session.scalar(select(Scenario).where(Scenario.id == scenario_id, Scenario.user_id == user_id))
        self.session.delete(item)
        self.session.commit()
