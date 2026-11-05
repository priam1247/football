"""Scraper for scheduled fixtures."""

from __future__ import annotations

from datetime import date
from typing import Any

from football_scraper.config import SCHEDULED_STATUS
from football_scraper.scrapers.base import BaseScraper


class FixturesScraper(BaseScraper):
    """Fetch the scheduled fixtures for a day."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.day: date | None = None

    def fetch(self, day: date | None = None) -> list[dict[str, Any]]:
        """Return the scheduled fixtures for the given day (default: the site's today).

        The date endpoint returns every match of the day (scheduled, live,
        finished and postponed); only the ones that have not kicked off are
        fixtures.
        """
        target = day or self.site_today()
        self.day = target
        rows = self.match_rows_for_day(target)
        return [r for r in rows if r.get("status_code") == SCHEDULED_STATUS]
