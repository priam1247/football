"""Configuration for the football scraper project."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Site configuration
# ---------------------------------------------------------------------------
BASE_URL = "https://www.ysscores.com/en/"
HOME_URL = BASE_URL + "home"
NEWS_URL = BASE_URL + "news"
TRANSFER_URL = BASE_URL + "transfer"
MATCH_DATE_ENDPOINT = BASE_URL + "match_date_to"
LIVE_MATCHES_ENDPOINT = BASE_URL + "get_live_matches"
NEWS_MORE_ENDPOINT = BASE_URL + "get_news_more"
TRANSFER_MORE_ENDPOINT = BASE_URL + "transfer_more"
RANK_URL_TEMPLATE = BASE_URL + "rank/{league_id}/{slug}"

# ---------------------------------------------------------------------------
# HTTP settings
# ---------------------------------------------------------------------------
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL + "home",
}
REQUEST_TIMEOUT = 25
MAX_RETRIES = 3
REQUEST_DELAY = 1.2  # seconds between requests

# The site sits behind Cloudflare and starts serving a "Just a moment..."
# challenge page (HTTP 403) when a client hammers it. Detect it so the
# scraper can back off instead of silently scraping an empty page.
CHALLENGE_MARKERS = ("Just a moment...", "challenges.cloudflare.com", "cf-challenge")
CHALLENGE_BACKOFF = 8  # seconds to wait before retrying a challenge page


def site_date(d: date) -> str:
    """Format a date the way ysscores.com expects: 'November 5,2026'."""
    return f"{d.strftime('%B')} {d.day},{d.year}"


def league_slug(title: str) -> str:
    """Build the URL slug ysscores.com uses for a league: 'UEFA Europa League'
    -> 'uefa_europa_league'."""
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", (title or "").strip().lower())
    return slug.strip("_") or "league"


# ---------------------------------------------------------------------------
# Match status codes (from ysscores.com)
# ---------------------------------------------------------------------------
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
SCHEDULED_STATUS = "0"
FINISHED_STATUS = "4"
POSTPONED_STATUS = "14"

# ---------------------------------------------------------------------------
# Major league standings IDs (observed on ysscores.com)
# ---------------------------------------------------------------------------
BIG_LEAGUES: dict[str, str] = {
    "uefa_champions_league": "943230",
    "uefa_europa_league": "943229",
    "uefa_europa_conference_league": "943231",
    "saudi_pro_league": "941825",
    "afc_champions_league_two": "944055",
    "copa_del_rey": "950451",
    "egypt_cup": "62474482",
    "iraq_stars_league": "3680601",
    "campeonato_brasileiro_serie_a": "916145",
    "oman_professional_league": "943388",
    "persian_gulf_pro_league": "942681",
    "argentine_primera_division": "905256",
}

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = Path(__file__).resolve().parent

DATA_DIR = PROJECT_DIR / "data"
LIVE_DIR = DATA_DIR / "live"
FIXTURES_DIR = DATA_DIR / "fixtures"
RESULTS_DIR = DATA_DIR / "results"
STANDINGS_DIR = DATA_DIR / "standings"
NEWS_DIR = DATA_DIR / "news"
NEWS_JSON_DIR = NEWS_DIR / "json"
NEWS_IMAGES_DIR = NEWS_DIR / "images"
TRANSFERS_DIR = DATA_DIR / "transfers"
TRANSFERS_JSON_DIR = TRANSFERS_DIR / "json"
TRANSFERS_IMAGES_DIR = TRANSFERS_DIR / "images"

OUTPUT_DIR = PROJECT_DIR / "output"


def ensure_dirs() -> None:
    """Create the data/output directory tree."""
    for directory in (
        DATA_DIR,
        LIVE_DIR,
        FIXTURES_DIR,
        RESULTS_DIR,
        STANDINGS_DIR,
        NEWS_DIR,
        NEWS_JSON_DIR,
        NEWS_IMAGES_DIR,
        TRANSFERS_DIR,
        TRANSFERS_JSON_DIR,
        TRANSFERS_IMAGES_DIR,
        OUTPUT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
