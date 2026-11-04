"""Image downloader for news and transfer media."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import requests

from football_scraper.config import REQUEST_HEADERS, REQUEST_TIMEOUT
from football_scraper.utils.logger import logger


def download_image(image_url: str | None, save_dir: str | Path) -> str | None:
    """Download an image and save it to save_dir. Returns the local path or None."""
    if not image_url:
        return None

    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    # Build a deterministic filename from the URL hash
    url_hash = hashlib.md5(image_url.encode("utf-8")).hexdigest()[:12]
    ext = Path(urlparse(image_url).path).suffix or ".jpg"
    if not ext.startswith("."):
        ext = "." + ext
    filename = f"{url_hash}{ext}"
    dest = save_dir / filename

    # Skip if already downloaded
    if dest.exists():
        return str(dest)

    try:
        resp = requests.get(image_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        logger.info("Downloaded image: %s -> %s", image_url, dest)
        return str(dest)
    except requests.RequestException as exc:
        logger.warning("Failed to download image %s: %s", image_url, exc)
        return None
