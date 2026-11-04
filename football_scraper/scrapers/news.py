"""Scraper for football news with image downloads."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from football_scraper.config import BASE_URL, NEWS_IMAGES_DIR, NEWS_JSON_DIR
from football_scraper.scrapers.base import BaseScraper
from football_scraper.utils.downloader import download_image
from football_scraper.utils.helpers import save_json


class NewsScraper(BaseScraper):
    """Fetch latest football news, downloading images locally."""

    def fetch(self, pages: int = 1, download_images: bool = True) -> list[dict[str, Any]]:
        """Return news items, optionally downloading images."""
        seen: dict[str, dict[str, Any]] = {}

        # First page (server-rendered)
        html = self.get("news").text
        for item in self._parse_news(html):
            if item.get("url") and item["url"] not in seen:
                seen[item["url"]] = item

        # Additional pages via AJAX
        for page in range(2, pages + 1):
            payload = self.get_json("get_news_more", {"page": page})
            items = payload.get("items") if isinstance(payload, dict) else payload
            items = items or []
            if isinstance(items, dict):
                items = list(items.values())
            if not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = urljoin(BASE_URL, item["link"]) if item.get("link") else None
                if url and url not in seen:
                    seen[url] = {
                        "title": item.get("title"),
                        "url": url,
                        "published": None,
                        "summary": item.get("news_desc"),
                        "image": urljoin(BASE_URL, item["image"]) if item.get("image") else None,
                        "caption": item.get("caption") or item.get("news_caption"),
                    }

        results = list(seen.values())

        if download_images:
            for item in results:
                image_url = item.get("image")
                local_path = download_image(image_url, NEWS_IMAGES_DIR) if image_url else None
                item["image_local"] = local_path
                item["image_url"] = image_url

        # Persist to JSON
        save_json(results, NEWS_JSON_DIR / "news.json")
        return results

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _parse_news(html: str) -> list[dict[str, Any]]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        items: list[dict[str, Any]] = []
        for node in soup.select("a.news-item"):
            title = node.select_one(".news-title")
            stamp = node.select_one(".news-date span")
            image = node.select_one("img")
            excerpt = node.select_one(".big-news-lead, .news-item-excerpt span")
            image_src = image.get("src") if image else None
            href = node.get("href", "")
            items.append(
                {
                    "title": title.get_text(" ", strip=True) if title else None,
                    "url": href,
                    "published": stamp.get_text(strip=True) if stamp else None,
                    "summary": excerpt.get_text(" ", strip=True) if excerpt else None,
                    "image": image_src,
                    "caption": image.get("alt") or image.get("title") if image else None,
                }
            )
        # Make URLs absolute
        for item in items:
            if item.get("url"):
                item["url"] = urljoin(BASE_URL, item["url"])
            if item.get("image"):
                item["image"] = urljoin(BASE_URL, item["image"])
        return items
