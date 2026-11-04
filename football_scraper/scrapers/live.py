"""Scraper for live football matches."""

from __future__ import annotations

from typing import Any

from football_scraper.config import LIVE_STATUSES, STATUS_TEXT
from football_scraper.scrapers.base import BaseScraper


class LiveScraper(BaseScraper):
    """Fetch currently live matches."""

    def fetch(self) -> list[dict[str, Any]]:
        """Return a list of live match dicts.

        Strategy:
        1. Fetch the fixtures page (server-rendered, contains live matches).
        2. Parse all match rows from the HTML.
        3. Filter for live matches using data-status codes.
        4. Enrich with clock data from the get_live_matches JSON endpoint.
        """
        rows = self._parse_fixtures_page()
        clocks = self._live_clock_feed()

        results: list[dict[str, Any]] = []
        for row in rows:
            if not row.get("is_live"):
                continue
            match_id = row["match_id"]
            clock = clocks.get(match_id)
            if clock:
                row["minute"] = clock.get("minute") or row.get("minute")
                row["status"] = clock.get("status", row.get("status"))
                row["status_code"] = clock.get("status_code", row.get("status_code"))
            results.append(row)
        return results

    # ------------------------------------------------------------------ internals
    def _parse_fixtures_page(self) -> list[dict[str, Any]]:
        """Fetch /en/fixtures and parse all match rows."""
        from datetime import date

        from football_scraper.config import site_date

        target = date.today()
        # Warm up session with the home page to get CSRF token if needed
        self.get("home")
        resp = self.get("fixtures")
        return self._parse_match_list(resp.text, target)

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

    @staticmethod
    def _parse_match_list(html: str, target) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        for shell in soup.select("#match_block_list .mb-row-shell"):
            anchor = shell.select_one("a.mb-row")
            if not anchor or not anchor.get("match_id"):
                continue
            group = shell.find_parent(class_="matches-wrapper")
            status = (anchor.get("data-status") or "").strip()
            score_home = anchor.select_one(".first-team-result")
            score_away = anchor.select_one(".second-team-result")
            clock = anchor.select_one(".match-date")
            rows.append(
                {
                    "match_id": anchor["match_id"],
                    "championship": group.get("champ_title") if group else None,
                    "round": anchor.get("title") or None,
                    "home_team": anchor.get("home_name"),
                    "away_team": anchor.get("away_name"),
                    "status_code": status,
                    "status": STATUS_TEXT.get(status, "unknown"),
                    "is_live": status in LIVE_STATUSES,
                    "home_score": score_home.get_text(strip=True)
                    if score_home
                    else None,
                    "away_score": score_away.get_text(strip=True)
                    if score_away
                    else None,
                    "kickoff": (
                        clock.get_text(" ", strip=True)
                        if clock and score_home is None
                        else None
                    ),
                    "minute": None,
                }
            )
        for row in rows:
            row["date"] = target.isoformat()
        return rows
