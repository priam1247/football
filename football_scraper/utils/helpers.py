"""Helper functions for the football scraper."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from football_scraper.config import site_date  # noqa: F401  (re-exported)

__all__ = ["clean_text", "save_json", "parse_date", "site_date"]


def clean_text(text: str | None) -> str | None:
    """Strip whitespace and normalise a text value."""
    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned or None


def save_json(data: list[dict[str, Any]] | dict[str, Any], path: str | Path) -> None:
    """Save data as a JSON file, creating parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def parse_date(value: str | None) -> date:
    """Parse a date string into a date object. Falls back to today."""
    if not value:
        return date.today()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d,%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return date.today()
