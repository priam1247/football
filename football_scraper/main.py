"""Command-line entry point for the football scraper."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

# Ensure the project root is on the path so `football_scraper` package imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from football_scraper.scrapers.fixtures import FixturesScraper
from football_scraper.scrapers.live import LiveScraper
from football_scraper.scrapers.news import NewsScraper
from football_scraper.scrapers.results import ResultsScraper
from football_scraper.scrapers.standings import StandingsScraper
from football_scraper.scrapers.transfers import TransfersScraper
from football_scraper.utils.logger import logger


def cmd_live(args: argparse.Namespace) -> int:
    scraper = LiveScraper()
    rows = scraper.fetch()
    print(f"\n=== Live matches ({len(rows)}) ===")
    for row in rows:
        print(
            f"[{row.get('status')}] {row.get('championship')} | "
            f"{row.get('home_team')} {row.get('home_score') or '-'}-"
            f"{row.get('away_score') or '-'} {row.get('away_team')} | "
            f"minute: {row.get('minute') or '-'}"
        )
    return 0


def cmd_fixtures(args: argparse.Namespace) -> int:
    day = date.fromisoformat(getattr(args, "date", None)) if getattr(args, "date", None) else None
    scraper = FixturesScraper()
    rows = scraper.fetch(day)
    print(f"\n=== Today's fixtures ({len(rows)}) ===")
    for row in rows:
        print(
            f"{row.get('kickoff') or '-'} | {row.get('championship')} | "
            f"{row.get('home_team')} vs {row.get('away_team')}"
        )
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    day = date.fromisoformat(getattr(args, "date", None)) if getattr(args, "date", None) else None
    scraper = ResultsScraper()
    rows = scraper.fetch(day)
    print(f"\n=== Full-time results ({len(rows)}) ===")
    for row in rows:
        print(
            f"{row.get('date')} | {row.get('championship')} | "
            f"{row.get('home_team')} {row.get('home_score') or '-'}-"
            f"{row.get('away_score') or '-'} {row.get('away_team')}"
        )
    return 0


def cmd_standings(args: argparse.Namespace) -> int:
    scraper = StandingsScraper()
    if args.league_id:
        rows = scraper.fetch(args.league_id, args.league_name or "")
        print(f"\n=== Standings {args.league_id} ({len(rows)}) ===")
        for row in rows:
            print(
                f"{row.get('position') or '-'}. {row.get('club')} | "
                f"P{row.get('played') or '-'} W{row.get('won') or '-'} "
                f"D{row.get('drawn') or '-'} L{row.get('lost') or '-'} | "
                f"Pts:{row.get('points') or '-'}"
            )
    else:
        all_tables = scraper.fetch_all_known()
        for league, rows in all_tables.items():
            print(f"\n=== Standings: {league} ({len(rows)}) ===")
            for row in rows:
                print(
                    f"{row.get('position') or '-'}. {row.get('club')} | "
                    f"Pts:{row.get('points') or '-'}"
                )
    return 0


def cmd_news(args: argparse.Namespace) -> int:
    scraper = NewsScraper()
    download_images = not getattr(args, "no_download_images", False)
    rows = scraper.fetch(pages=args.pages, download_images=download_images)
    print(f"\n=== News ({len(rows)}) ===")
    for row in rows:
        print(
            f"{row.get('published') or '-'} {row.get('title')}\n"
            f"  caption: {row.get('caption') or row.get('summary') or '-'}\n"
            f"  image: {row.get('image_local') or row.get('image') or '-'}"
        )
    return 0


def cmd_transfers(args: argparse.Namespace) -> int:
    scraper = TransfersScraper()
    download_images = not getattr(args, "no_download_images", False)
    rows = scraper.fetch(
        pages=args.pages,
        championship=args.championship,
        download_images=download_images,
    )
    print(f"\n=== Transfers ({len(rows)}) ===")
    for row in rows:
        print(
            f"{row.get('player')} ({row.get('position') or '-'}) | "
            f"{row.get('from_club')} -> {row.get('to_club')} | "
            f"{row.get('type') or '-'}"
        )
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    logger.info("Running all scrapers...")
    cmd_live(args)
    # fixtures/results need --date; default to today for 'all'
    cmd_fixtures(args)
    cmd_results(args)
    cmd_standings(args)
    cmd_news(args)
    cmd_transfers(args)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Football scraper CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("live", help="Live matches").set_defaults(func=cmd_live)

    p_fix = sub.add_parser("fixtures", help="Today's fixtures")
    p_fix.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p_fix.set_defaults(func=cmd_fixtures)

    p_res = sub.add_parser("results", help="Full-time results")
    p_res.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p_res.set_defaults(func=cmd_results)

    p_stand = sub.add_parser("standings", help="League standings")
    p_stand.add_argument("--league-id", help="League rank id")
    p_stand.add_argument("--league-name", default="", help="League name slug")
    p_stand.set_defaults(func=cmd_standings)

    p_news = sub.add_parser("news", help="Football news")
    p_news.add_argument("--pages", type=int, default=1, help="Number of pages")
    p_news.add_argument(
        "--no-download-images",
        action="store_true",
        help="Skip downloading images",
    )
    p_news.set_defaults(func=cmd_news)

    p_trans = sub.add_parser("transfers", help="Transfer news")
    p_trans.add_argument("--pages", type=int, default=1, help="Number of pages")
    p_trans.add_argument("--championship", default="all", help="Championship filter")
    p_trans.add_argument(
        "--no-download-images",
        action="store_true",
        help="Skip downloading images",
    )
    p_trans.set_defaults(func=cmd_transfers)

    sub.add_parser("all", help="Run all scrapers").set_defaults(func=cmd_all)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
