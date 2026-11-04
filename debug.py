#!/usr/bin/env python3
"""
debug.py - offline debug helper for the ysscores scraper.

Loads saved HTML fixtures and runs the parsers directly, so you can iterate
on parsing logic without hitting ysscores.com (and without rate limits).

Usage:
    python debug.py news        # parse tests/fixtures/news_home.html
    python debug.py standings   # parse tests/fixtures/standings_ucl.html
    python debug.py all         # run every available fixture
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from scraper import YSClient, BIG_LEAGUES

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def run_news() -> None:
    html = (FIXTURES / "news_home.html").read_text(encoding="utf-8")
    items = YSClient._parse_news(html)
    print(f"\n=== news ({len(items)}) ===")
    for item in items:
        print(json.dumps(item, ensure_ascii=False))


def run_standings() -> None:
    html = (FIXTURES / "standings_ucl.html").read_text(encoding="utf-8")
    table = YSClient._parse_standings(html)
    print(f"\n=== standings ({len(table)}) ===")
    for row in table:
        print(json.dumps(row, ensure_ascii=False))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python debug.py <news|standings|all>")
        return 1

    command = sys.argv[1]
    if command == "news":
        run_news()
    elif command == "standings":
        run_standings()
    elif command == "all":
        run_news()
        run_standings()
    else:
        print(f"unknown command: {command}")
        print("usage: python debug.py <news|standings|all>")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
