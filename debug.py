#!/usr/bin/env python3
"""
debug.py - offline debug helper for the ysscores scraper.

Loads the saved HTML fixtures and runs the parsers directly, so you can
iterate on parsing logic without hitting ysscores.com (and without hitting
the site's Cloudflare rate limit).

Usage:
    python debug.py news        # parse tests/fixtures/news_home.html
    python debug.py standings   # parse tests/fixtures/standings_ucl.html
    python debug.py matches     # parse tests/fixtures/matches_fragment.html
    python debug.py all         # run every available fixture
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from football_scraper.scrapers.base import BaseScraper
from football_scraper.scrapers.news import NewsScraper
from football_scraper.scrapers.standings import StandingsScraper

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def emit(rows, label):
    print(f"\n=== {label} ({len(rows)}) ===")
    for row in rows:
        if "club" in row:
            print(
                f"{row.get('position') or '-'}. {row['club']} | "
                f"P{row.get('played') or '-'} W{row.get('won') or '-'} "
                f"D{row.get('drawn') or '-'} L{row.get('lost') or '-'} | "
                f"Pts:{row.get('points') or '-'}"
            )
        elif "home_team" in row:
            print(
                f"[{row.get('status_label') or row.get('status')}] "
                f"{row.get('championship')} | {row['home_team']} "
                f"{row.get('home_score') or '-'}-{row.get('away_score') or '-'} "
                f"{row['away_team']} | kickoff {row.get('kickoff') or '-'} | "
                f"minute {row.get('minute') or '-'}"
            )
        else:
            print(
                f"{row.get('published') or ''} {row.get('title')}\n"
                f"  caption: {row.get('caption') or row.get('summary') or '-'}\n"
                f"  image: {row.get('image') or '-'}"
            )


def run_news() -> None:
    html = (FIXTURES / "news_home.html").read_text(encoding="utf-8")
    emit(NewsScraper._parse_news(html), "news")


def run_standings() -> None:
    html = (FIXTURES / "standings_ucl.html").read_text(encoding="utf-8")
    emit(StandingsScraper._parse_standings(html), "standings")


def run_matches() -> None:
    html = (FIXTURES / "matches_fragment.html").read_text(encoding="utf-8")
    emit(BaseScraper.parse_match_rows(html), "matches")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python debug.py <news|standings|matches|all>")
        return 1

    command = sys.argv[1]
    if command == "news":
        run_news()
    elif command == "standings":
        run_standings()
    elif command == "matches":
        run_matches()
    elif command == "all":
        run_matches()
        run_news()
        run_standings()
    else:
        print(f"unknown command: {command}")
        print("usage: python debug.py <news|standings|matches|all>")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
