"""Scraper for league standings tables."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from football_scraper.config import BIG_LEAGUES, RANK_URL_TEMPLATE, league_slug
from football_scraper.scrapers.base import BaseScraper
from football_scraper.utils.logger import logger


class StandingsScraper(BaseScraper):
    """Fetch league standings tables."""

    BIG_LEAGUES = BIG_LEAGUES

    def fetch(self, league_id: str, league_name: str = "") -> list[dict[str, Any]]:
        """Return standings rows for a league.

        URL pattern: /en/rank/<league_id>/<slug>. The slug is required by the
        route; the league id is what selects the table.
        """
        slug = league_name or league_slug(league_id)
        url = RANK_URL_TEMPLATE.format(league_id=league_id, slug=slug)
        html = self._request("GET", url).text
        table = self._parse_standings(html)
        for row in table:
            row["league_id"] = league_id
            row["league_name"] = league_name or slug
        return table

    def fetch_all_known(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch standings for all known big leagues."""
        results: dict[str, list[dict[str, Any]]] = {}
        for key, league_id in self.BIG_LEAGUES.items():
            if not league_id:
                continue
            try:
                results[key] = self.fetch(league_id, key)
            except Exception as exc:  # noqa: BLE001 - one league must not break the rest
                logger.warning("Failed to fetch standings for %s: %s", key, exc)
        return results

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _parse_standings(html: str) -> list[dict[str, Any]]:
        """Parse a standings page.

        The page renders each club as a '.rank-row' div with '.rank-col'
        children, not as an HTML table.
        """
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        for row_node in soup.select(".rank-row"):
            classes = row_node.get("class") or []
            if "header" in classes:
                continue

            def col(name: str) -> str | None:
                node = row_node.select_one(f".rank-col.{name}")
                if not node:
                    return None
                return node.get_text(" ", strip=True) or None

            club_node = row_node.select_one(".rank-col.name .info")
            club = club_node.get_text(" ", strip=True) if club_node else col("name")
            if not club:
                continue

            logo = row_node.select_one(".rank-col.name .team-name img")
            club_image = logo.get("src") if logo else None
            link = row_node.select_one(".rank-col.name a")

            position_text = col("number")
            try:
                position = int(position_text) if position_text else None
            except (TypeError, ValueError):
                position = None

            rows.append(
                {
                    "position": position,
                    "club": club,
                    "club_image": club_image,
                    "club_link": link.get("href") if link else None,
                    "played": col("played"),
                    "won": col("win"),
                    "drawn": col("equal"),
                    "lost": col("lose"),
                    "goals": col("goals"),
                    "goal_difference": col("diff"),
                    "points": col("points"),
                }
            )
        return rows
