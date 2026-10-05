"""Unit tests for rules that depend on facts from another domain."""

from decimal import Decimal

import pytest

from app.modules.ledger.application import Ledger, LedgerError
from app.modules.planning.write_application import Planning


class LedgerStoreStub:
    def __init__(self):
        self.writes = []

    def account(self, user_id, account_id):
        return {"id": account_id, "user_id": user_id, "type": "INVESTMENT", "currency": "EUR",
                "initial_balance": Decimal("100"), "name": "Fondo", "active": True}

    def category(self, user_id, category_id):
        return {"id": category_id, "user_id": user_id}

    def transaction(self, user_id, transaction_id):
        return {"id": transaction_id, "user_id": user_id}

    def update_account(self, user_id, account_id, changes):
        self.writes.append(("update_account", account_id, changes))

    def delete_category(self, user_id, category_id):
        self.writes.append(("delete_category", category_id))

    def delete_transaction(self, user_id, transaction_id):
        self.writes.append(("delete_transaction", transaction_id))


class LedgerPoliciesStub:
    def account_references(self, user_id, account_id):
        return True, False, False

    def category_references(self, category_id):
        return True

    def linked_transaction(self, transaction_id):
        return True


def test_account_with_investments_rejects_balance_change_before_write():
    store = LedgerStoreStub()
    service = Ledger(store, LedgerPoliciesStub())

    with pytest.raises(LedgerError) as error:
        service.update_account(7, 4, {"initial_balance": Decimal("200")})

    assert error.value.status == 409
    assert store.writes == []


def test_category_referenced_by_another_domain_cannot_be_deleted():
    store = LedgerStoreStub()
    service = Ledger(store, LedgerPoliciesStub())

    with pytest.raises(LedgerError) as error:
        service.delete_category(7, 5)

    assert error.value.status == 409
    assert store.writes == []


def test_linked_transaction_cannot_be_deleted():
    store = LedgerStoreStub()
    service = Ledger(store, LedgerPoliciesStub())

    with pytest.raises(LedgerError) as error:
        service.delete_transaction(7, 9)

    assert error.value.status == 409
    assert store.writes == []


def test_deleting_income_source_cleans_savings_rules_in_same_operation():
    events = []

    class PlanningStoreStub:
        def get(self, kind, user_id, item_id):
            return {"id": item_id}

        def delete_related(self, kind, user_id, field, item_id):
            events.append(("delete_related", kind, user_id, field, item_id))

        def delete(self, kind, user_id, item_id):
            events.append(("delete", kind, user_id, item_id))

    class SavingsStub:
        def delete_rules_for_source(self, user_id, source_id):
            events.append(("delete_savings_rules", user_id, source_id))

    Planning(PlanningStoreStub(), SavingsStub()).delete_income(7, 3)

    assert events == [
        ("delete_related", "receipt", 7, "source_id", 3),
        ("delete_savings_rules", 7, 3),
        ("delete", "income", 7, 3),
    ]
