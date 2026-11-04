"""Scraper for today's scheduled fixtures."""

from __future__ import annotations

from datetime import date
from typing import Any

from football_scraper.config import LIVE_STATUSES, STATUS_TEXT, site_date
from football_scraper.scrapers.base import BaseScraper


class FixturesScraper(BaseScraper):
    """Fetch today's scheduled fixtures."""

    def fetch(self, day: date | None = None) -> list[dict[str, Any]]:
        """Return a list of fixture dicts for the given day (default today)."""
        target = day or date.today()
        resp = self.post(
            "match_date_to",
            {
                "get_date": site_date(target),
                "favorite_status": "champ_display",
                "match_status": "1",  # all matches
                "order_status": "1",
                "champs_view": "1",
                "clear_c": "yes",
            },
        )
        rows = self._parse_match_list(resp.text, target)
        # Keep only scheduled (non-live, non-finished) matches
        fixtures = [
            r for r in rows if r.get("status_code") == "0" or not r.get("is_live")
        ]
        return fixtures

    # ------------------------------------------------------------------ internals
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
