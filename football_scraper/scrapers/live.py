"""Scraper for live football matches."""

from __future__ import annotations

from typing import Any

from football_scraper.config import STATUS_TEXT
from football_scraper.scrapers.base import BaseScraper


class LiveScraper(BaseScraper):
    """Fetch currently live matches."""

    def fetch(self) -> list[dict[str, Any]]:
        """Return a list of live match dicts.

        Strategy:
        1. Read the server-rendered home page (it carries the matches that
           are in play right now).
        2. Merge it with the date endpoint for the site day and the day
           before it, so a match is found whichever bucket the site files it
           under.
        3. Keep the live rows and enrich them with the clock feed.
        """
        rows = self.current_match_rows()
        clocks = self._live_clock_feed()

        results: list[dict[str, Any]] = []
        for row in rows:
            if not row.get("is_live"):
                continue
            clock = clocks.get(str(row["match_id"]))
            if clock:
                if clock.get("minute"):
                    row["minute"] = clock["minute"]
                status_code = clock.get("status_code")
                if status_code:
                    row["status_code"] = status_code
                    row["status"] = STATUS_TEXT.get(status_code, row.get("status"))
            results.append(row)
        return results

    # ------------------------------------------------------------------ internals
    def _live_clock_feed(self) -> dict[str, dict[str, Any]]:
        """Return {match_id: clock_info} from the live poller endpoint."""
        payload = self.get_json("get_live_matches")
        clocks: dict[str, dict[str, Any]] = {}
        if not isinstance(payload, list):
            return clocks
        for item in payload:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", ""))
            mid = str(item.get("id", ""))
            clocks[mid] = {
                "match_id": mid,
                "minute": item.get("time"),
                "status_code": status,
                "status": STATUS_TEXT.get(status, "unknown"),
            }
        return clocks
