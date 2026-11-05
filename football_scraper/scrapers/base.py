"""Base scraper with session, CSRF handling, throttling, and retries."""

from __future__ import annotations

import random
import re
import time
from datetime import date, timedelta
from typing import Any
from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from football_scraper.config import (
    BASE_URL,
    CHALLENGE_BACKOFF,
    CHALLENGE_MARKERS,
    HOME_URL,
    LIVE_STATUSES,
    MAX_RETRIES,
    REQUEST_DELAY,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    STATUS_TEXT,
    site_date,
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
        self._home_html: str | None = None
        self._site_today: date | None = None

    # ------------------------------------------------------------------ plumbing
    def _throttle(self) -> None:
        wait = self.delay + random.uniform(0, self.delay * 0.4)
        elapsed = time.monotonic() - self._last_call
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_call = time.monotonic()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_exc: Exception | None = None
        verify = kwargs.pop("verify", True)
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                # Try with SSL verification first; fall back to unverified on SSL errors
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
                if resp.status_code == 403 and self._is_challenge(resp.text):
                    # Cloudflare interlude: back off properly instead of
                    # parsing an empty challenge page as "no matches".
                    raise ScrapeError(
                        "Cloudflare challenge (403) - the site is rate-limiting this client"
                    )
                resp.raise_for_status()
                return resp
            except (requests.RequestException, ScrapeError) as exc:
                last_exc = exc
                if attempt == MAX_RETRIES:
                    break
                backoff = 2**attempt
                if isinstance(exc, ScrapeError) and "Cloudflare" in str(exc):
                    backoff = CHALLENGE_BACKOFF * attempt
                logger.warning(
                    "Request failed (%s/%s) %s %s: %s - retrying in %ss",
                    attempt,
                    MAX_RETRIES,
                    method,
                    url,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
        raise ScrapeError(f"{method} {url} failed: {last_exc}")

    @staticmethod
    def _is_challenge(body: str) -> bool:
        head = body[:4000]
        return any(marker in head for marker in CHALLENGE_MARKERS)

    def home_html(self) -> str:
        """Return the (cached) server-rendered home page HTML."""
        if self._home_html is None:
            self._home_html = self._request("GET", HOME_URL).text
        return self._home_html

    def _ensure_token(self) -> str:
        if self._token:
            return self._token
        html = self.home_html()
        match = re.search(r'name="_token"\s+content="([^"]+)"', html)
        if not match:
            raise ScrapeError("CSRF token not found - markup may have changed")
        self._token = match.group(1)
        return self._token

    # ------------------------------------------------------------- site calendar
    def site_today(self) -> date:
        """The site's current calendar date.

        The site's day boundary is not the machine's local day: ysscores.com
        groups matches by its own calendar and its home page advertises the
        date it considers 'today'. Reading it from the page keeps the scraper
        correct regardless of the machine's timezone.
        """
        if self._site_today is not None:
            return self._site_today
        found = None
        try:
            html = self.home_html()
            match = re.search(r'data-date="(\d{4}-\d{2}-\d{2})', html)
            if match:
                found = date.fromisoformat(match.group(1))
            else:
                # Fallback: the date the site renders into its own filter.
                literal = re.search(
                    r'"([A-Z][a-z]+ \d{1,2},\s*\d{4})"', html
                ) or re.search(r'"([A-Z][a-z]+ \d{1,2},\d{4})"', html)
                if literal:
                    found = date.strptime(
                        literal.group(1).replace(", ", ","), "%B %d,%Y"
                    ).date()
        except (requests.RequestException, ScrapeError, ValueError) as exc:
            logger.warning("Could not read the site's current date: %s", exc)
        self._site_today = found or date.today()
        logger.info("Site's current date: %s", self._site_today.isoformat())
        return self._site_today

    # ------------------------------------------------------------------ requests
    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", urljoin(BASE_URL, path), **kwargs)

    def post(self, path: str, data: dict[str, Any], ajax: bool = True) -> requests.Response:
        headers = {"X-CSRF-Token": self._ensure_token()}
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return self._request(
            "POST", urljoin(BASE_URL, path), data=data, headers=headers
        )

    def get_json(self, path: str, params: Any = None) -> Any:
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

    # -------------------------------------------------------------- match list
    def match_rows_for_day(self, day: date) -> list[dict[str, Any]]:
        """All match rows the site lists for a given day.

        The site's own status filters (match_status=2 live, =3 finished)
        return an empty 'no matches' block, so the full list is requested
        once and filtered client side.
        """
        resp = self.post(
            "match_date_to",
            {
                "get_date": site_date(day),
                "favorite_status": "champ_display",
                "match_status": "1",  # all matches; filtered below
                "order_status": "1",
                "champs_view": "1",
                "clear_c": "yes",
            },
        )
        rows = self.parse_match_rows(resp.text)
        for row in rows:
            row["date"] = day.isoformat()
        return rows

    def current_match_rows(self) -> list[dict[str, Any]]:
        """Match rows for the site's current match day.

        The home page is server rendered with the matches that are in play
        right now; the date endpoint covers the surrounding calendar days.
        Both are merged so a match is found whichever bucket the site files
        it under.
        """
        rows: dict[str, dict[str, Any]] = {}
        try:
            for row in self.parse_match_rows(self.home_html()):
                rows[str(row["match_id"])] = row
        except (requests.RequestException, ScrapeError) as exc:
            logger.warning("Could not read the home page match list: %s", exc)

        today = self.site_today()
        for day in (today, today - timedelta(days=1)):
            try:
                for row in self.match_rows_for_day(day):
                    mid = str(row["match_id"])
                    existing = rows.get(mid)
                    if existing is None:
                        rows[mid] = row
                        continue
                    for key, value in row.items():
                        if existing.get(key) in (None, "") and value not in (None, ""):
                            existing[key] = value
            except (requests.RequestException, ScrapeError) as exc:
                logger.warning("Could not read the match list for %s: %s", day, exc)
        return list(rows.values())

    # ------------------------------------------------------------- match parsing
    @staticmethod
    def parse_match_rows(html: str) -> list[dict[str, Any]]:
        """Parse match rows out of a page or an HTML fragment.

        The match rows are rendered as '.mb-row-shell' > 'a.mb-row'. The
        fragment returned by match_date_to has no '#match_block_list'
        wrapper, so the rows are selected without relying on that ancestor.
        """
        soup = BeautifulSoup(html, "html.parser")
        rows: list[dict[str, Any]] = []
        for shell in soup.select(".mb-row-shell"):
            anchor = shell.select_one("a.mb-row")
            if not anchor or not anchor.get("match_id"):
                continue
            group = shell.find_parent(class_="matches-wrapper")
            status_code = (anchor.get("data-status") or "").strip()
            score_home = anchor.select_one(".first-team-result")
            score_away = anchor.select_one(".second-team-result")
            kickoff_node = anchor.select_one(".match-date")
            live_label = anchor.select_one(".live-match-status")
            result_label = anchor.select_one(".result-status-text:not(.live-match-status)")
            minute_node = anchor.select_one("[id^='match-time-'] span")
            minutes_node = anchor.select_one("[data-minutes]")
            extra_time = anchor.select_one(".extra-time")

            is_live = status_code in LIVE_STATUSES
            status_label = None
            if live_label:
                status_label = live_label.get_text(" ", strip=True)
            elif result_label:
                status_label = result_label.get_text(" ", strip=True)

            minute = minute_node.get_text(strip=True) if minute_node else None
            if not minute and minutes_node:
                minute = minutes_node.get("data-minutes")

            def _score(node) -> str | None:
                if not node:
                    return None
                return node.get_text(strip=True) or None

            # '.match-date' holds the kick-off time for scheduled matches but
            # wraps the score for finished ones, so it is only read as a
            # kick-off for rows that have not started.
            kickoff = None
            if status_code in ("0", "") and kickoff_node:
                kickoff = kickoff_node.get_text(" ", strip=True) or None

            rows.append(
                {
                    "match_id": anchor["match_id"],
                    "url": anchor.get("href") or None,
                    "championship": group.get("champ_title") if group else None,
                    "championship_id": group.get("id") if group else None,
                    "round": anchor.get("title") or None,
                    "home_team": anchor.get("home_name"),
                    "away_team": anchor.get("away_name"),
                    "home_team_image": anchor.get("home_image"),
                    "away_team_image": anchor.get("away_image"),
                    "home_team_link": anchor.get("home_link"),
                    "away_team_link": anchor.get("away_link"),
                    "status_code": status_code,
                    "status": STATUS_TEXT.get(status_code, "unknown"),
                    "status_label": status_label,
                    "is_live": is_live,
                    "home_score": _score(score_home),
                    "away_score": _score(score_away),
                    "kickoff": kickoff,
                    "minute": minute,
                    "extra_time": (
                        extra_time.get_text(strip=True) if extra_time else None
                    ),
                    "date": None,
                }
            )
        return rows
