"""Motor puro de proyección: aplica flujos fechados sobre saldos iniciales."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class CashEvent:
    date: date
    account_id: int
    amount: Decimal
    key: str
    label: str


@dataclass(frozen=True)
class ForecastDay:
    date: date
    balances: dict[int, Decimal]


def project(initial: dict[int, Decimal], events: list[CashEvent], start: date, end: date) -> list[ForecastDay]:
    if end < start:
        raise ValueError("El fin precede al inicio")
    balances = initial.copy()
    ordered = sorted(events, key=lambda event: (max(event.date, start), event.key))
    for event in ordered:
        if event.account_id not in balances:
            raise ValueError("Suceso de una cuenta desconocida")
    result = []
    index = 0
    day = start
    while day <= end:
        while index < len(ordered) and ordered[index].date <= day:
            event = ordered[index]
            balances[event.account_id] += event.amount
            index += 1
        result.append(ForecastDay(day, balances.copy()))
        day += timedelta(days=1)
    return result
