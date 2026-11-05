"""Scraper for transfer news with image downloads."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from football_scraper.config import BASE_URL, TRANSFERS_IMAGES_DIR, TRANSFERS_JSON_DIR
from football_scraper.scrapers.base import BaseScraper
from football_scraper.utils.downloader import download_image
from football_scraper.utils.helpers import save_json


class TransfersScraper(BaseScraper):
    """Fetch transfer news, downloading images locally."""

    def fetch(
        self, pages: int = 1, championship: str = "all", download_images: bool = True
    ) -> list[dict[str, Any]]:
        """Return transfer items, optionally downloading images."""
        rows = self._parse_transfers(self.get("transfer").text)

        seen = {r["transfer_id"] for r in rows if r.get("transfer_id")}
        loaded_ids = [r["transfer_id"] for r in rows if r.get("transfer_id")]
        for _ in range(max(0, pages - 1)):
            params = [
                ("champ", championship),
                ("count_trans", str(len(rows))),
            ] + [("loadedIds[]", i) for i in loaded_ids]

            payload = self.get_json("transfer_more", params)
            new = self._extract_items(payload)
            if not new:
                break
            added = 0
            for item in new:
                row = self._map_item(item)
                if not row:
                    continue
                if row["transfer_id"] and row["transfer_id"] in seen:
                    continue
                if row["transfer_id"]:
                    seen.add(row["transfer_id"])
                rows.append(row)
                added += 1
            if not added:
                break
            loaded_ids = [r["transfer_id"] for r in rows if r.get("transfer_id")]

        if download_images:
            for item in rows:
                image_url = item.get("image")
                local_path = (
                    download_image(image_url, TRANSFERS_IMAGES_DIR, session=self.session)
                    if image_url
                    else None
                )
                item["image_local"] = local_path
                item["image_url"] = image_url

        save_json(rows, TRANSFERS_JSON_DIR / "transfers.json")
        return rows

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        """The feed returns {'list_important': [...], 'list': [...], 'next': n}."""
        if isinstance(payload, list):
            return [i for i in payload if isinstance(i, dict)]
        if not isinstance(payload, dict):
            return []
        items: list[dict[str, Any]] = []
        for key in ("list_important", "list", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                items.extend(i for i in value if isinstance(i, dict))
        return items

    @staticmethod
    def _map_item(item: dict[str, Any]) -> dict[str, Any] | None:
        """Map one feed record onto the same shape the HTML scraper produces."""
        player = item.get("player_id") or {}
        team_out = item.get("team_out") or {}
        team_in = item.get("team_in") or {}
        if not player and not team_out and not team_in:
            return None
        image = player.get("image")
        return {
            "transfer_id": str(item.get("id")) if item.get("id") is not None else None,
            "player": player.get("title"),
            "position": player.get("position"),
            "from_club": team_out.get("full_title") or team_out.get("title"),
            "to_club": team_in.get("full_title") or team_in.get("title"),
            "type": item.get("trans"),
            "value": item.get("value"),
            "contract_until": item.get("date_to"),
            "transfer_date": item.get("date_from"),
            "image": urljoin(BASE_URL, image) if image else None,
            "caption": player.get("title"),
            "url": player.get("link"),
        }

    @staticmethod
    def _parse_transfers(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        out: list[dict[str, Any]] = []
        for node in soup.select("a.transform-item"):
            from_club = node.select_one(".from .club img")
            to_club = node.select_one(".to .club img")
            player = node.select_one(".player h5")
            photo = node.select_one(".player img")
            position = node.select_one(".player .text span")
            kind = node.select_one(".exch-wrap span")
            until = node.select_one(".to-date")
            out.append(
                {
                    "transfer_id": node.get("data-id"),
                    "player": player.get_text(" ", strip=True) if player else None,
                    "position": position.get_text(" ", strip=True)
                    if position
                    else None,
                    "from_club": from_club.get("alt") if from_club else None,
                    "to_club": to_club.get("alt") if to_club else None,
                    "type": kind.get_text(" ", strip=True) if kind else None,
                    "contract_until": (until.get_text(strip=True) or None)
                    if until
                    else None,
                    "image": urljoin(BASE_URL, photo["src"]) if photo and photo.get("src") else None,
                    "caption": photo.get("alt") if photo else None,
                    "url": node.get("href"),
                }
            )
        return out
