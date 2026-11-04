#!/usr/bin/env python3
"""
ysscores.py - scraper for ysscores.com (Yalla Shoot)

Pulls today's fixtures, full-time results, live score updates, news and
transfer news into structured JSON/CSV.

How the site actually works (verified against the live pages):
  * /en/home and /en/news and /en/transfer are server-rendered - the data we
    want is in the initial HTML, so plain GETs are enough for a full snapshot.
  * Dynamic pieces go through internal AJAX endpoints, which we reuse:
      POST /en/match_date_to    - match list for any date + status filter
      GET  /en/get_live_matches - JSON [{id, time, status}] live clock feed
      GET  /en/get_news_more    - paged news JSON
      GET  /en/transfer_more    - paged transfer JSON
  * POST endpoints need the CSRF token from <meta name="_token">, so we warm
    up on /en/home first and keep one session (cookies + token).
  * Match rows carry the data in attributes: match_id, home_name, away_name,
    data-status. Scores sit in .first-team-result / .second-team-result.
  * Championships are grouped by .matches-wrapper[champ_title].
  * data-status codes: 0 scheduled, 1 1st half, 2 half-time, 3 2nd half,
    4 finished, 7/9 extra time, 14 postponed.

Usage:
    python ysscores.py all
    python ysscores.py matches --date 2026-11-05
    python ysscores.py results
    python ysscores.py live --watch --interval 20
    python ysscores.py news --pages 2
    python ysscores.py transfers --pages 3
    python ysscores.py all --out data.json --csv

Requires: pip install requests beautifulsoup4
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.ysscores.com/en/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

STATUS_TEXT = {
    "0": "scheduled",
    "1": "live_1st_half",
    "2": "half_time",
    "3": "live_2nd_half",
    "4": "finished",
    "7": "live_extra_time_1",
    "9": "live_extra_time_2",
    "14": "postponed",
}
LIVE_STATUSES = {"1", "2", "3", "7", "9"}


class ScrapeError(RuntimeError):
    pass


class YSClient:
    """Session wrapper: CSRF handling, throttling, retries, HTML parsing helpers."""

    def __init__(self, delay: float = 1.2, timeout: int = 25, retries: int = 3):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": BASE + "home",
            }
        )
        self._token: str | None = None
        self._last_call = 0.0

    # ---------------------------------------------------------------- plumbing
    def _throttle(self) -> None:
        wait = self.delay + random.uniform(0, self.delay * 0.4)
        elapsed = time.monotonic() - self._last_call
        if elapsed < wait:
            time.sleep(wait - elapsed)
        self._last_call = time.monotonic()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if resp.status_code == 429:
                    raise ScrapeError("rate limited (429)")
                resp.raise_for_status()
                return resp
            except (requests.RequestException, ScrapeError) as exc:
                last_exc = exc
                if attempt == self.retries:
                    break
                time.sleep(2 ** attempt)
        raise ScrapeError(f"{method} {url} failed: {last_exc}")

    def _ensure_token(self) -> str:
        if self._token:
            return self._token
        html = self._request("GET", BASE + "home").text
        match = re.search(r'name="_token"\s+content="([^"]+)"', html)
        if not match:
            raise ScrapeError("CSRF token not found - markup may have changed")
        self._token = match.group(1)
        return self._token

    def get(self, path: str, **kwargs) -> requests.Response:
        return self._request("GET", urljoin(BASE, path), **kwargs)

    def post(self, path: str, data: dict[str, Any], ajax: bool = True) -> requests.Response:
        headers = {"X-CSRF-Token": self._ensure_token()}
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
        return self._request("POST", urljoin(BASE, path), data=data, headers=headers)

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self.get(
            path,
            params=params,
            headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        )
        try:
            return resp.json()
        except ValueError:
            return None

    @staticmethod
    def soup(html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    # ------------------------------------------------------------ date helpers
    @staticmethod
    def site_date(d: date) -> str:
        """Format the way the site's date filter does: 'November 5,2026'."""
        return f"{d.strftime('%B')} {d.day},{d.year}"

    @staticmethod
    def parse_date(value: str | None) -> date:
        if not value:
            return date.today()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%B %d,%Y"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise SystemExit(f"unrecognised date: {value!r} (use YYYY-MM-DD)")

    # ----------------------------------------------------------------- matches
    def _parse_match_list(self, html: str) -> list[dict[str, Any]]:
        soup = self.soup(html)
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
                    "championship": (group.get("champ_title") if group else None),
                    "round": anchor.get("title") or None,
                    "home_team": anchor.get("home_name"),
                    "away_team": anchor.get("away_name"),
                    "status_code": status,
                    "status": STATUS_TEXT.get(status, "unknown"),
                    "is_live": status in LIVE_STATUSES,
                    "home_score": score_home.get_text(strip=True) if score_home else None,
                    "away_score": score_away.get_text(strip=True) if score_away else None,
                    "kickoff": (
                        clock.get_text(" ", strip=True)
                        if clock and score_home is None
                        else None
                    ),
                    "minute": None,
                    "url": urljoin(BASE, anchor["href"]) if anchor.get("href") else None,
                }
            )
        return rows

    def matches(
        self,
        day: date | None = None,
        status: int = 1,
        championship_view: int = 1,
    ) -> list[dict[str, Any]]:
        """Match list for a day. status: 1 all, 2 live, 3 finished, 4 upcoming."""
        target = day or date.today()
        resp = self.post(
            "match_date_to",
            {
                "get_date": self.site_date(target),
                "favorite_status": "champ_display",
                "match_status": str(status),
                "order_status": "1",
                "champs_view": str(championship_view),
                "clear_c": "yes",
            },
        )
        rows = self._parse_match_list(resp.text)
        for row in rows:
            row["date"] = target.isoformat()
        return rows

    def results(self, day: date | None = None) -> list[dict[str, Any]]:
        """Full-time results only."""
        return [r for r in self.matches(day, status=3) if r["status"] == "finished"]

    # -------------------------------------------------------------- live feed
    def live_updates(self, day: date | None = None) -> list[dict[str, Any]]:
        """Live clock feed: [{id, time, status}] straight from the site's own poller."""
        params = {"get_date": self.site_date(day)} if day else {}
        payload = self.get_json("get_live_matches", params)
        if not isinstance(payload, list):
            return []
        out = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", ""))
            out.append(
                {
                    "match_id": str(item.get("id")),
                    "minute": item.get("time"),
                    "status_code": status,
                    "status": STATUS_TEXT.get(status, "unknown"),
                }
            )
        return out

    def live_matches(self, day: date | None = None) -> list[dict[str, Any]]:
        """Live matches with teams/scores, clock merged in from the live feed."""
        rows = [r for r in self.matches(day, status=2) if r["is_live"]]
        clocks = {c["match_id"]: c for c in self.live_updates(day)}
        for row in rows:
            clock = clocks.get(row["match_id"])
            if clock:
                row["minute"] = clock["minute"]
                row["status"] = clock["status"]
        return rows

    # -------------------------------------------------------------------- news
    @staticmethod
    def _parse_news(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        items = []
        for node in soup.select("a.news-item"):
            title = node.select_one(".news-title")
            stamp = node.select_one(".news-date span")
            image = node.select_one("img")
            excerpt = node.select_one(".big-news-lead, .news-item-excerpt span")
            items.append(
                {
                    "title": title.get_text(" ", strip=True) if title else None,
                    "url": urljoin(BASE, node["href"]) if node.get("href") else None,
                    "published": stamp.get_text(strip=True) if stamp else None,
                    "summary": excerpt.get_text(" ", strip=True) if excerpt else None,
                    "image": image.get("src") if image else None,
                }
            )
        return items

    def news(self, pages: int = 1) -> list[dict[str, Any]]:
        seen: dict[str, dict[str, Any]] = {}
        for item in self._parse_news(self.get("news").text):
            if item["url"]:
                seen[item["url"]] = item
        for page in range(2, pages + 1):
            payload = self.get_json("get_news_more", {"page": page})
            items = (payload or {}).get("items") or []
            if isinstance(items, dict):
                items = list(items.values())
            if not items:
                break
            for item in items:
                url = item.get("link")
                if url and url not in seen:
                    seen[url] = {
                        "title": item.get("title"),
                        "url": urljoin(BASE, url),
                        "published": None,
                        "summary": item.get("news_desc"),
                        "image": item.get("image"),
                    }
        return list(seen.values())

    # --------------------------------------------------------------- transfers
    @staticmethod
    def _parse_transfers(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
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
                    "position": position.get_text(" ", strip=True) if position else None,
                    "from_club": from_club.get("alt") if from_club else None,
                    "to_club": to_club.get("alt") if to_club else None,
                    "type": kind.get_text(" ", strip=True) if kind else None,
                    "contract_until": (until.get_text(strip=True) or None) if until else None,
                    "url": urljoin(BASE, node["href"]) if node.get("href") else None,
                }
            )
        return out

    def transfers(self, pages: int = 1, championship: str = "all") -> list[dict[str, Any]]:
        rows = self._parse_transfers(self.get("transfer").text)
        for _ in range(max(0, pages - 1)):
            loaded = [r["transfer_id"] for r in rows if r.get("transfer_id")]
            params: list[tuple[str, str]] = [
                ("champ", championship),
                ("count_trans", str(len(rows))),
            ]
            params += [("loadedIds[]", i) for i in loaded]
            payload = self.get_json("transfer_more?" + "&".join(f"{k}={v}" for k, v in params))
            if payload is None:
                payload = self.get_json(
                    "transfer_more",
                    {"champ": championship, "count_trans": len(rows), "loadedIds[]": loaded},
                )
            new = (payload or {}).get("list") or []
            if not new:
                break
            rows.extend(
                {
                    "transfer_id": str(i.get("id")),
                    "player": i.get("player") or i.get("name"),
                    "position": i.get("position"),
                    "from_club": i.get("from_team") or i.get("from"),
                    "to_club": i.get("to_team") or i.get("to"),
                    "type": i.get("type"),
                    "contract_until": i.get("to_date"),
                    "url": urljoin(BASE, i["link"]) if i.get("link") else None,
                }
                for i in new
                if isinstance(i, dict)
            )
        return rows


# --------------------------------------------------------------------- output
def emit(rows: list[dict[str, Any]], label: str, as_json: bool = False) -> None:
    if as_json:
        return
    print(f"\n=== {label} ({len(rows)}) ===")
    for row in rows:
        if "home_team" in row:
            score = f"{row['home_score'] or '-'}-{row['away_score'] or '-'}"
            minute = f" {row['minute']}'" if row.get("minute") else ""
            print(
                f"[{row['status']}{minute}] {row['championship']} | "
                f"{row['home_team']} {score} {row['away_team']}"
            )
        elif "player" in row:
            print(
                f"{row['player']} ({row['position']}): {row['from_club']} -> "
                f"{row['to_club']} [{row['type']}]"
            )
        else:
            print(f"{row['published'] or ''} {row['title']} -> {row['url']}")


def write_output(rows: Iterable[dict[str, Any]], path: str, csv_path: str | None) -> None:
    rows = list(rows)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, ensure_ascii=False)
    print(f"\nsaved {len(rows)} records to {path}")
    if not csv_path or not rows:
        return
    fields = sorted({key for row in rows for key in row})
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved CSV to {csv_path}")


# ------------------------------------------------------------------------ cli
def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape ysscores.com")
    parser.add_argument(
        "command",
        choices=["all", "matches", "results", "live", "news", "transfers"],
    )
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--pages", type=int, default=1, help="news/transfer pages")
    parser.add_argument("--delay", type=float, default=1.2, help="seconds between requests")
    parser.add_argument("--watch", action="store_true", help="live: keep polling")
    parser.add_argument("--interval", type=float, default=30.0, help="live poll seconds")
    parser.add_argument("--championship", default="all", help="transfer championship id")
    parser.add_argument("--out", help="write JSON to this file")
    parser.add_argument(
        "--csv",
        nargs="?",
        const="output.csv",
        default=None,
        help="also write CSV here (default: output.csv)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    args = parser.parse_args()

    client = YSClient(delay=args.delay)
    day = client.parse_date(args.date) if args.date else date.today()
    bucket: list[dict[str, Any]] = []

    try:
        if args.command == "live" and args.watch:
            seen: set[str] = set()
            print(f"polling live matches every {args.interval:g}s - Ctrl+C to stop")
            while True:
                for row in client.live_matches(day):
                    key = f"{row['match_id']}:{row['home_score']}:{row['away_score']}"
                    if key not in seen:
                        seen.add(key)
                        print(
                            f"{datetime.now():%H:%M:%S} {row['minute'] or ''} "
                            f"{row['home_team']} {row['home_score']}-{row['away_score']} "
                            f"{row['away_team']}"
                        )
                time.sleep(args.interval)

        if args.command in ("all", "matches"):
            rows = client.matches(day)
            bucket += rows
            emit(rows, f"matches {day}", args.json)

        if args.command in ("all", "results"):
            rows = client.results(day)
            bucket += rows
            emit(rows, f"full-time results {day}", args.json)

        if args.command in ("all", "live"):
            rows = client.live_matches(day)
            bucket += rows
            emit(rows, "live matches", args.json)

        if args.command in ("all", "news"):
            rows = client.news(pages=max(1, args.pages))
            bucket += rows
            emit(rows, "news", args.json)

        if args.command in ("all", "transfers"):
            rows = client.transfers(pages=max(1, args.pages), championship=args.championship)
            bucket += rows
            emit(rows, "transfers", args.json)

    except KeyboardInterrupt:
        print("\nstopped")
    except ScrapeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(bucket, indent=2, ensure_ascii=False))
    if args.out:
        write_output(bucket, args.out, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
