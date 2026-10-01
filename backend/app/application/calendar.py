"""Expansión determinista de fechas civiles, sin escribir movimientos."""

from calendar import monthrange
from datetime import date, timedelta


def month_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, monthrange(year, month)[1]))


def next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def income_day(year: int, month: int, rule: str, day_of_month: int | None) -> date:
    if rule == "LAST_DAY_OF_MONTH":
        return month_day(year, month, 31)
    if rule == "FIRST_BUSINESS_DAY":
        result = date(year, month, 1)
        while result.weekday() >= 5:
            result += timedelta(days=1)
        return result
    if rule == "FIXED_DAY" and day_of_month is not None:
        return month_day(year, month, day_of_month)
    raise ValueError("Regla de cobro inválida")


def monthly_dates(start: date, end: date, day: int, active_from: date, active_until: date | None = None) -> list[date]:
    if end < start:
        return []
    year, month = start.year, start.month
    result = []
    while (year, month) <= (end.year, end.month):
        candidate = month_day(year, month, day)
        if start <= candidate <= end and candidate >= active_from and (active_until is None or candidate <= active_until):
            result.append(candidate)
        year, month = next_month(year, month)
    return result


def income_dates(
    start: date, end: date, rule: str, day_of_month: int | None,
    active_from: date, active_until: date | None = None,
) -> list[date]:
    if end < start:
        return []
    year, month = start.year, start.month
    result = []
    while (year, month) <= (end.year, end.month):
        candidate = income_day(year, month, rule, day_of_month)
        if start <= candidate <= end and candidate >= active_from and (active_until is None or candidate <= active_until):
            result.append(candidate)
        year, month = next_month(year, month)
    return result


def recurring_dates(start: date, end: date, frequency: str, active_from: date, active_until: date | None = None) -> list[date]:
    if end < start:
        return []
    if frequency == "MONTHLY":
        return monthly_dates(start, end, active_from.day, active_from, active_until)
    if frequency != "WEEKLY":
        raise ValueError("Frecuencia inválida")
    first = max(start, active_from)
    weeks = (first - active_from).days // 7
    candidate = active_from + timedelta(days=weeks * 7)
    if candidate < first:
        candidate += timedelta(days=7)
    result = []
    while candidate <= end and (active_until is None or candidate <= active_until):
        result.append(candidate)
        candidate += timedelta(days=7)
    return result
