#!/usr/bin/env python3
"""
scraper.py - compatibility wrapper around the football_scraper package.

This file used to hold the original single-file implementation. It was
superseded by the modular `football_scraper/` package, but the old copy was
left in the tree and kept returning zero matches because its parsers still
looked for rows inside a '#match_block_list' wrapper that the site's match
endpoint does not send.

Rather than maintain two divergent scrapers, this wrapper keeps the original
command line working while all parsing and requesting is done by the package.

Usage:
    python scraper.py all
    python scraper.py matches --date 2026-11-05
    python scraper.py results
    python scraper.py live --watch --interval 20
    python scraper.py news --pages 2
    python scraper.py transfers --pages 3
    python scraper.py standings --league-id 943230 --league-name uefa_champions_league
    python scraper.py all --out data.json --csv

Requires: pip install requests beautifulsoup4
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from football_scraper.scrapers.base import BaseScraper, ScrapeError
from football_scraper.scrapers.live import LiveScraper
from football_scraper.scrapers.news import NewsScraper
from football_scraper.scrapers.results import ResultsScraper
from football_scraper.scrapers.standings import StandingsScraper
from football_scraper.scrapers.transfers import TransfersScraper
from football_scraper.utils.helpers import parse_date


def emit(rows: list[dict[str, Any]], label: str, as_json: bool = False) -> None:
    if as_json:
        return
    print(f"\n=== {label} ({len(rows)}) ===")
    for row in rows:
        if "home_team" in row:
            score = f"{row['home_score'] or '-'}-{row['away_score'] or '-'}"
            minute = f" {row['minute']}'" if row.get("minute") else ""
            status = row.get("status_label") or row.get("status")
            print(
                f"[{status}{minute}] {row.get('championship')} | "
                f"{row['home_team']} {score} {row['away_team']}"
            )
        elif "player" in row:
            print(
                f"{row['player']} ({row['position']}): {row['from_club']} -> "
                f"{row['to_club']} [{row['type']}]"
            )
        elif "club" in row:
            print(
                f"{row.get('position') or '-'}. {row['club']} | "
                f"P{row.get('played') or '-'} W{row.get('won') or '-'} "
                f"D{row.get('drawn') or '-'} L{row.get('lost') or '-'} | "
                f"{row.get('goals') or '-'} GD:{row.get('goal_difference') or '-'} "
                f"Pts:{row.get('points') or '-'}"
            )
        else:
            caption = row.get("caption") or row.get("summary") or ""
            image = row.get("image") or ""
            print(f"{row.get('published') or ''} {row['title']}\n  caption: {caption}\n  image: {image}")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape ysscores.com")
    parser.add_argument(
        "command",
        choices=["all", "matches", "results", "live", "news", "transfers", "standings"],
    )
    parser.add_argument("--date", help="YYYY-MM-DD (default: the site's today)")
    parser.add_argument("--pages", type=int, default=1, help="news/transfer pages")
    parser.add_argument("--league-id", help="standings: league id for /en/rank/<id>/<name>")
    parser.add_argument("--league-name", default="", help="standings: league name slug")
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

    delay = args.delay
    day = parse_date(args.date) if args.date else None
    bucket: list[dict[str, Any]] = []

    def client(cls):
        return cls(delay=delay)

    try:
        if args.command == "live" and args.watch:
            seen: set[str] = set()
            print(f"polling live matches every {args.interval:g}s - Ctrl+C to stop")
            while True:
                for row in client(LiveScraper).fetch():
                    key = f"{row['match_id']}:{row['home_score']}:{row['away_score']}"
                    if key not in seen:
                        seen.add(key)
                        print(
                            f"{datetime.now():%H:%M:%S} {row.get('minute') or ''} "
                            f"{row['home_team']} {row['home_score']}-{row['away_score']} "
                            f"{row['away_team']}"
                        )
                time.sleep(args.interval)

        if args.command in ("all", "matches"):
            base = client(BaseScraper)
            target = day or base.site_today()
            rows = base.match_rows_for_day(target)
            bucket += rows
            emit(rows, f"matches {target.isoformat()}", args.json)

        if args.command in ("all", "results"):
            rows = client(ResultsScraper).fetch(day)
            bucket += rows
            emit(rows, "full-time results", args.json)

        if args.command in ("all", "live"):
            rows = client(LiveScraper).fetch()
            bucket += rows
            emit(rows, "live matches", args.json)

        if args.command in ("all", "news"):
            rows = client(NewsScraper).fetch(pages=max(1, args.pages))
            bucket += rows
            emit(rows, "news", args.json)

        if args.command in ("all", "transfers"):
            rows = client(TransfersScraper).fetch(
                pages=max(1, args.pages), championship=args.championship
            )
            bucket += rows
            emit(rows, "transfers", args.json)

        if args.command == "standings":
            if not args.league_id:
                print(
                    "error: standings requires --league-id (and optionally --league-name)",
                    file=sys.stderr,
                )
                return 1
            rows = client(StandingsScraper).fetch(args.league_id, args.league_name)
            bucket += rows
            emit(rows, f"standings {args.league_id}", args.json)

    except KeyboardInterrupt:
        print("\nstopped")
    except ScrapeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(bucket, indent=2, ensure_ascii=False))
    if args.out or args.csv:
        write_output(bucket, args.out or "output.json", args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
