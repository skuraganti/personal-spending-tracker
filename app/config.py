"""Bounded local runtime configuration; the statement has no currency column."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_path: str
    max_import_bytes: int
    max_import_rows: int
    max_diagnostics: int
    currency: str = "GBP"


def _bounded(name: str, default: int, upper: int) -> int:
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= upper:
        raise ValueError(f"{name} must be between 1 and {upper}")
    return value


def get_settings() -> Settings:
    if os.getenv("MONEYVIS_CURRENCY", "GBP") != "GBP":
        raise ValueError("Only assumed GBP is supported")
    db_path = os.getenv("MONEYVIS_DB", os.path.join(os.getcwd(), "data", "app.db"))
    if not db_path or db_path == ":memory:":
        raise ValueError("MONEYVIS_DB must be a persistent local path")
    return Settings(
        db_path=db_path,
        max_import_bytes=_bounded("MONEYVIS_MAX_IMPORT_BYTES", 1_000_000, 10_000_000),
        max_import_rows=_bounded("MONEYVIS_MAX_IMPORT_ROWS", 50_000, 100_000),
        max_diagnostics=_bounded("MONEYVIS_MAX_DIAGNOSTICS", 50, 100),
    )
