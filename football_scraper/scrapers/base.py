"""Base scraper with session, CSRF handling, throttling, and retries."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from football_scraper.config import (
    BASE_URL,
    HOME_URL,
    MAX_RETRIES,
    REQUEST_DELAY,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
)
from football_scraper.utils.logger import logger


class ScrapeError(RuntimeError):
    """Raised when scraping fails after retries."""


class BaseScraper:
    """Session wrapper: CSRF handling, throttling, retries, HTML parsing."""

    def __init__(self, delay: float = REQUEST_DELAY, timeout: int = REQUEST_TIMEOUT):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
        self._token: str | None = None
        self._last_call = 0.0

    # ------------------------------------------------------------------ plumbing
    def _throttle(self) -> None:
        wait = self.delay + (self.delay * 0.4) * __import__("random").random()
        elapsed = time.monotonic() - self._last_call
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_call = time.monotonic()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        import random

        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                # Try with SSL verification first; fall back to unverified on SSL errors
                verify = kwargs.pop("verify", True)
                try:
                    resp = self.session.request(
                        method, url, timeout=self.timeout, verify=verify, **kwargs
                    )
                except requests.exceptions.SSLError:
                    if verify:
                        resp = self.session.request(
                            method,
                            url,
                            timeout=self.timeout,
                            verify=False,
                            **kwargs,
                        )
                    else:
                        raise
                if resp.status_code == 429:
                    raise ScrapeError("rate limited (429)")
                resp.raise_for_status()
                return resp
            except (requests.RequestException, ScrapeError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES:
                    break
                time.sleep(2**attempt)
        raise ScrapeError(f"{method} {url} failed: {last_exc}")

    def _ensure_token(self) -> str:
        if self._token:
            return self._token
        html = self._request("GET", HOME_URL).text
        match = re.search(r'name="_token"\s+content="([^"]+)"', html)
        if not match:
            raise ScrapeError("CSRF token not found - markup may have changed")
        self._token = match.group(1)
        return self._token

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", urljoin(BASE_URL, path), **kwargs)

    def post(self, path: str, data: dict[str, Any], ajax: bool = True) -> requests.Response:
        headers = {"X-CSRF-Token": self._ensure_token()}
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return self._request(
            "POST", urljoin(BASE_URL, path), data=data, headers=headers
        )

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.get(
            path,
            params=params,
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")
