"""Offline parser tests using saved HTML fixtures."""
from pathlib import Path

from football_scraper.scrapers.fixtures import FixturesScraper
from football_scraper.scrapers.news import NewsScraper
from football_scraper.scrapers.standings import StandingsScraper
from football_scraper.main import build_parser

FIX = Path(__file__).parent / "fixtures"


def test_news_urls_are_absolute():
    items = NewsScraper._parse_news((FIX / "news_home.html").read_text())
    assert len(items) == 3
    assert items[0]["url"] == "https://www.ysscores.com/en/news/12345/real-madrid-agreement-manchester-united-gem"
    assert items[0]["image"].startswith("https://www.ysscores.com/")


def test_standings_first_row():
    rows = StandingsScraper._parse_standings((FIX / "standings_ucl.html").read_text())
    assert rows[0]["position"] == 1 and rows[0]["club"] == "Paris-SG" and rows[0]["points"] == "12"


def test_scheduled_match_gets_kickoff_even_with_empty_score_nodes():
    html = """<div id="match_block_list"><div class="matches-wrapper" champ_title="UCL">
    <div class="mb-row-shell"><a class="mb-row" match_id="9" home_name="A" away_name="B" data-status="0">
    <span class="first-team-result"></span><span class="second-team-result"></span>
    <span class="match-date">20:00</span></a></div></div></div>"""
    from datetime import date
    rows = FixturesScraper._parse_match_list(html, date(2026, 11, 5))
    assert rows[0]["kickoff"] == "20:00"


def test_all_command_has_every_argument_it_needs():
    args = build_parser().parse_args(["all"])
    assert args.pages == 1 and args.league_id is None and args.championship == "all"
