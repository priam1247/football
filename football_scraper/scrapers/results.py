"""Scraper for full-time results (today and yesterday)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from football_scraper.config import FINISHED_STATUS, LIVE_STATUSES, STATUS_TEXT
from football_scraper.scrapers.base import BaseScraper


class ResultsScraper(BaseScraper):
    """Fetch full-time finished matches for today and yesterday."""

    def fetch(self, day: date | None = None) -> list[dict[str, Any]]:
        """Return finished match dicts for today and yesterday."""
        target = day or date.today()
        yesterday = target - timedelta(days=1)

        all_results: list[dict[str, Any]] = []
        for single_day in (target, yesterday):
            rows = self._results_for_day(single_day)
            all_results.extend(rows)
        return all_results

    # ------------------------------------------------------------------ internals
    def _results_for_day(self, target: date) -> list[dict[str, Any]]:
        from football_scraper.config import site_date

        resp = self.post(
            "match_date_to",
            {
                "get_date": site_date(target),
                "favorite_status": "champ_display",
                "match_status": "1",  # all, filter finished in Python
                "order_status": "1",
                "champs_view": "1",
                "clear_c": "yes",
            },
        )
        rows = self._parse_match_list(resp.text, target)
        # Keep only finished matches (status code "4")
        return [r for r in rows if r.get("status_code") == FINISHED_STATUS]

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
                        if clock and status in ("0", "")
                        else None
                    ),
                    "minute": None,
                }
            )
        for row in rows:
            row["date"] = target.isoformat()
        return rows
