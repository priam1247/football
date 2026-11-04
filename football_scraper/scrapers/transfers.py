"""Scraper for transfer news with image downloads."""

from __future__ import annotations

from typing import Any

from football_scraper.config import TRANSFERS_IMAGES_DIR, TRANSFERS_JSON_DIR
from football_scraper.scrapers.base import BaseScraper
from football_scraper.utils.downloader import download_image
from football_scraper.utils.helpers import save_json


class TransfersScraper(BaseScraper):
    """Fetch latest transfer news, downloading images locally."""

    def fetch(
        self, pages: int = 1, championship: str = "all", download_images: bool = True
    ) -> list[dict[str, Any]]:
        """Return transfer items, optionally downloading images."""
        rows = self._parse_transfers(self.get("transfer").text)

        loaded_ids = [r["transfer_id"] for r in rows if r.get("transfer_id")]
        for _ in range(max(0, pages - 1)):
            params = [
                ("champ", championship),
                ("count_trans", str(len(rows))),
            ] + [("loadedIds[]", i) for i in loaded_ids]

            payload = self.get_json(
                "transfer_more?" + "&".join(f"{k}={v}" for k, v in params)
            )
            if payload is None:
                payload = self.get_json(
                    "transfer_more",
                    {
                        "champ": championship,
                        "count_trans": len(rows),
                        "loadedIds[]": loaded_ids,
                    },
                )
            new = (payload or {}).get("list") or []
            if not new:
                break
            for i in new:
                if not isinstance(i, dict):
                    continue
                rows.append(
                    {
                        "transfer_id": str(i.get("id")),
                        "player": i.get("player") or i.get("name"),
                        "position": i.get("position"),
                        "from_club": i.get("from_team") or i.get("from"),
                        "to_club": i.get("to_team") or i.get("to"),
                        "type": i.get("type"),
                        "contract_until": i.get("to_date"),
                        "image": i.get("image"),
                        "caption": i.get("caption"),
                    }
                )
            loaded_ids = [r["transfer_id"] for r in rows if r.get("transfer_id")]

        if download_images:
            for item in rows:
                image_url = item.get("image")
                local_path = (
                    download_image(image_url, TRANSFERS_IMAGES_DIR)
                    if image_url
                    else None
                )
                item["image_local"] = local_path
                item["image_url"] = image_url

        save_json(rows, TRANSFERS_JSON_DIR / "transfers.json")
        return rows

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _parse_transfers(html: str) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        out: list[dict[str, Any]] = []
        for node in soup.select("a.transform-item"):
            from_club = node.select_one(".from .club img")
            to_club = node.select_one(".to .club img")
            player = node.select_one(".player h5")
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
                    "image": None,
                    "caption": None,
                }
            )
        return out
