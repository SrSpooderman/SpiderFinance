from enum import StrEnum


class AccountType(StrEnum):
    CHECKING = "CHECKING"
    SAVINGS = "SAVINGS"
    CASH = "CASH"
    INVESTMENT = "INVESTMENT"
    CARD = "CARD"
    OTHER = "OTHER"


class TransactionType(StrEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionStatus(StrEnum):
    CLEARED = "CLEARED"
    PENDING = "PENDING"
