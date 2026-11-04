"""Scraper for league standings tables."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from football_scraper.config import BASE_URL, BIG_LEAGUES
from football_scraper.scrapers.base import BaseScraper


class StandingsScraper(BaseScraper):
    """Fetch league standings tables."""

    BIG_LEAGUES = BIG_LEAGUES

    def fetch(self, league_id: str, league_name: str = "") -> list[dict[str, Any]]:
        """Return standings rows for a league.

        URL pattern: /en/rank/<league_id>/<league_name>
        """
        path = f"rank/{league_id}/{league_name}" if league_name else f"rank/{league_id}"
        html = self.get(path).text
        table = self._parse_standings(html)
        for row in table:
            row["league_id"] = league_id
            row["league_name"] = league_name
        return table

    def fetch_all_known(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch standings for all known big leagues."""
        results: dict[str, list[dict[str, Any]]] = {}
        for key, league_id in self.BIG_LEAGUES.items():
            if not league_id:
                continue
            try:
                results[key] = self.fetch(league_id, key)
            except Exception as exc:  # noqa: BLE001
                from football_scraper.utils.logger import logger

                logger.warning("Failed to fetch standings for %s: %s", key, exc)
        return results

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _parse_standings(html: str) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        for row in soup.select("table tr"):
            cells = row.select("td, th")
            if not cells:
                continue
            if cells[0].name == "th":
                continue
            texts = [c.get_text(" ", strip=True) for c in cells]
            if len(texts) < 2:
                continue
            club_node = row.select_one("td a, .club-name, .club")
            club = club_node.get_text(" ", strip=True) if club_node else texts[1]
            club_img = row.select_one("td img, .club img")
            club_image = (
                urljoin(BASE_URL, club_img["src"]) if club_img and club_img.get("src") else None
            )
            try:
                position = int(texts[0])
            except (ValueError, IndexError):
                position = None

            def _num(idx: int) -> str | None:
                try:
                    return texts[idx] if texts[idx] else None
                except IndexError:
                    return None

            rows.append(
                {
                    "position": position,
                    "club": club,
                    "club_image": club_image,
                    "played": _num(2),
                    "won": _num(3),
                    "drawn": _num(4),
                    "lost": _num(5),
                    "goals": _num(6),
                    "goal_difference": _num(7),
                    "points": _num(8),
                }
            )
        return rows
