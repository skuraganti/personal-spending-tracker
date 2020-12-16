"""Exact money handling in integer pennies.

The snapshot carries no currency column; GBP is an explicit UK-context assumption,
never verified per row. Amounts are stored as signed integer pennies.

MAX_PENNIES (2**53 - 1, about GBP 90 trillion) bounds every amount and balance and the
gross absolute total of all stored amounts, so SQLite int64 sums and JavaScript numbers
stay exact. It is a numeric-safety range, not a plausibility limit.
"""

from __future__ import annotations

import re
from decimal import Decimal

_AMOUNT_RE = re.compile(r"^\d{1,15}(\.\d{1,2})?$")
MAX_PENNIES = 2**53 - 1


class MoneyError(ValueError):
    """A money string is not a non-negative decimal with at most two places."""


def parse_pennies(text: str) -> int:
    value = text.strip()
    if not value:
        raise MoneyError("empty amount")
    if not _AMOUNT_RE.match(value):
        raise MoneyError("invalid amount")
    exact = int((Decimal(value) * 100).to_integral_value())
    if exact > MAX_PENNIES:
        raise MoneyError("amount exceeds the exact integer-penny range")
    return exact


def parse_optional_pennies(text: str) -> int | None:
    value = text.strip()
    if not value:
        return None
    return parse_pennies(value)


def format_pounds(pennies: int) -> str:
    sign = "-" if pennies < 0 else ""
    pounds, pence = divmod(abs(pennies), 100)
    return f"{sign}{pounds}.{pence:02d}"