"""Offline parser tests using markup captured from ysscores.com."""
from pathlib import Path

from bs4 import BeautifulSoup

from football_scraper.main import build_parser
from football_scraper.scrapers.base import BaseScraper
from football_scraper.scrapers.fixtures import FixturesScraper
from football_scraper.scrapers.news import NewsScraper
from football_scraper.scrapers.standings import StandingsScraper
from football_scraper.scrapers.transfers import TransfersScraper

FIX = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------- match rows
def test_fragment_rows_are_parsed_without_match_block_list():
    """The match_date_to response is a bare fragment with no #match_block_list.

    Selecting '#match_block_list .mb-row-shell' silently matched nothing and
    made every scraper report zero matches.
    """
    html = (FIX / "matches_fragment.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert len(soup.select("#match_block_list .mb-row-shell")) == 0
    assert len(soup.select(".mb-row-shell")) == 4

    rows = BaseScraper.parse_match_rows(html)
    assert len(rows) == 4
    assert {r["status_code"] for r in rows} == {"0", "1", "4", "14"}


def test_home_page_rows_are_parsed():
    rows = BaseScraper.parse_match_rows((FIX / "matches_home.html").read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert all(r["match_id"] for r in rows)
    assert all(r["championship"] for r in rows)


def test_live_row_carries_clock_status_and_scores():
    rows = BaseScraper.parse_match_rows((FIX / "matches_fragment.html").read_text(encoding="utf-8"))
    live = [r for r in rows if r["is_live"]]
    assert len(live) == 1
    row = live[0]
    assert row["status_code"] == "1"
    assert row["status"] == "live_1st_half"
    assert row["status_label"] == "First Half"
    assert row["home_score"] == "0"
    assert row["away_score"] == "0"
    assert row["minute"] == "8:27"


def test_finished_row_has_scores_but_no_kickoff():
    """For a finished match '.match-date' wraps the score, not the kick-off."""
    rows = BaseScraper.parse_match_rows((FIX / "matches_fragment.html").read_text(encoding="utf-8"))
    finished = [r for r in rows if r["status_code"] == "4"]
    assert len(finished) == 1
    row = finished[0]
    assert row["status_label"] == "Ended"
    assert row["home_score"] == "2"
    assert row["away_score"] == "3"
    assert row["kickoff"] is None


def test_scheduled_row_has_kickoff_and_no_scores():
    rows = BaseScraper.parse_match_rows((FIX / "matches_fragment.html").read_text(encoding="utf-8"))
    scheduled = [r for r in rows if r["status_code"] == "0"]
    assert len(scheduled) == 1
    row = scheduled[0]
    assert row["kickoff"] == "12:45 pm"
    assert row["home_score"] is None
    assert row["away_score"] is None
    assert row["is_live"] is False


def test_postponed_row_is_not_treated_as_scheduled_or_live():
    rows = BaseScraper.parse_match_rows((FIX / "matches_fragment.html").read_text(encoding="utf-8"))
    postponed = [r for r in rows if r["status_code"] == "14"]
    assert len(postponed) == 1
    assert postponed[0]["status"] == "postponed"
    assert postponed[0]["is_live"] is False


def test_scheduled_match_gets_kickoff_even_with_empty_score_nodes():
    html = """<div id="match_block_list"><div class="matches-wrapper" champ_title="UCL">
    <div class="mb-row-shell"><a class="mb-row" match_id="9" home_name="A" away_name="B" data-status="0">
    <span class="first-team-result"></span><span class="second-team-result"></span>
    <span class="match-date">20:00</span></a></div></div></div>"""
    rows = BaseScraper.parse_match_rows(html)
    assert rows[0]["kickoff"] == "20:00"
    assert rows[0]["home_score"] is None


# ---------------------------------------------------------------------- news
def test_news_urls_are_absolute():
    items = NewsScraper._parse_news((FIX / "news_home.html").read_text(encoding="utf-8"))
    assert len(items) == 3
    assert items[0]["url"].startswith("https://www.ysscores.com/en/news/")
    assert items[0]["image"].startswith("https://imgs.ysscores.com/")


def test_news_items_have_title_date_and_caption():
    items = NewsScraper._parse_news((FIX / "news_home.html").read_text(encoding="utf-8"))
    assert items[0]["title"] == "Real Madrid reaches agreement with Manchester United gem"
    assert items[0]["published"] == "2026-11-04"
    assert items[0]["caption"]
    assert items[0]["summary"]


def test_news_feed_date_is_extracted_from_php_style_dict():
    raw = "{'date': '2026-11-05 00:27:30.000000', 'timezone_type': 3, 'timezone': 'UTC'}"
    assert NewsScraper._extract_date(raw) == "2026-11-05"
    assert NewsScraper._extract_date(None) is None


# ----------------------------------------------------------------- standings
def test_standings_first_row():
    rows = StandingsScraper._parse_standings(
        (FIX / "standings_ucl.html").read_text(encoding="utf-8")
    )
    assert rows[0]["position"] == 1 and rows[0]["club"] == "Paris-SG" and rows[0]["points"] == "12"


def test_standings_skip_the_header_row():
    rows = StandingsScraper._parse_standings(
        (FIX / "standings_ucl.html").read_text(encoding="utf-8")
    )
    assert len(rows) == 3
    assert all(r["club"] for r in rows)
    assert all(r["position"] for r in rows)


# ----------------------------------------------------------------- transfers
def test_transfer_feed_items_are_mapped():
    payload = {
        "list_important": [
            {
                "id": 983412,
                "team_out": {"title": "Al-Gharafa", "full_title": "Al-Gharafa SC"},
                "player_id": {
                    "title": "Muntari",
                    "position": "Center Forward",
                    "image": "https://imgs.ysscores.com/player/48/17872872467087.png",
                    "link": "https://www.ysscores.com/en/player/431151/Mohammed-Muntari",
                },
                "team_in": {"title": "Al-Sadd", "full_title": "Al-Sadd SC"},
                "value": "0",
                "trans": "Free Transfer",
                "date_from": "2026-11-04",
                "date_to": "2028-06-30",
            }
        ],
        "list": [],
        "next": 1,
    }
    items = TransfersScraper._extract_items(payload)
    assert len(items) == 1

    row = TransfersScraper._map_item(items[0])
    assert row["player"] == "Muntari"
    assert row["position"] == "Center Forward"
    assert row["from_club"] == "Al-Gharafa SC"
    assert row["to_club"] == "Al-Sadd SC"
    assert row["type"] == "Free Transfer"
    assert row["contract_until"] == "2028-06-30"


# ---------------------------------------------------------------------- cli
def test_all_command_has_every_argument_it_needs():
    args = build_parser().parse_args(["all"])
    assert args.pages == 1 and args.league_id is None and args.championship == "all"


def test_invalid_date_is_rejected():
    from football_scraper.main import _requested_date

    class Args:
        date = "not-a-date"

    try:
        _requested_date(Args())
    except SystemExit:
        return
    raise AssertionError("invalid date should be rejected")
