"""Image downloader for news and transfer media."""

from __future__ import annotations

import hashlib
import random
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from football_scraper.config import REQUEST_HEADERS, REQUEST_TIMEOUT
from football_scraper.utils.logger import logger

# Images are hosted on the same origin as the pages, so they are downloaded
# politely: one at a time, with a small delay, using the scraper's session
# (cookies included). Hammering the CDN makes the site serve a Cloudflare
# challenge page, which would otherwise look like a broken image.
MIN_IMAGE_DELAY = 0.4
_last_download = 0.0


def _throttle() -> None:
    global _last_download
    wait = MIN_IMAGE_DELAY + random.uniform(0, MIN_IMAGE_DELAY * 0.4)
    elapsed = time.monotonic() - _last_download
    if elapsed < wait:
        time.sleep(wait - elapsed)
    _last_download = time.monotonic()


def download_image(
    image_url: str | None,
    save_dir: str | Path,
    session: requests.Session | None = None,
) -> str | None:
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
        _throttle()
        getter = session.get if session is not None else requests.get
        resp = getter(
            image_url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        if not resp.headers.get("Content-Type", "image/").startswith("image/"):
            logger.warning(
                "Not an image (%s): %s", resp.headers.get("Content-Type"), image_url
            )
            return None
        dest.write_bytes(resp.content)
        logger.info("Downloaded image: %s -> %s", image_url, dest)
        return str(dest)
    except requests.RequestException as exc:
        logger.warning("Failed to download image %s: %s", image_url, exc)
        return None
