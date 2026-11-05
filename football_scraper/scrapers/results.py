"""Scraper for full-time results."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from football_scraper.config import FINISHED_STATUS
from football_scraper.scrapers.base import BaseScraper


class ResultsScraper(BaseScraper):
    """Fetch full-time finished matches."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.day: date | None = None

    def fetch(self, day: date | None = None) -> list[dict[str, Any]]:
        """Return the finished matches for the given day and the day before it.

        A day that has only just started rarely has any full-time results
        yet, so yesterday is always included as well.
        """
        target = day or self.site_today()
        self.day = target

        all_results: list[dict[str, Any]] = []
        for single_day in (target, target - timedelta(days=1)):
            rows = self.match_rows_for_day(single_day)
            all_results.extend(
                r for r in rows if r.get("status_code") == FINISHED_STATUS
            )
        return all_results
