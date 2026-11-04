"""Configuration for the football scraper project."""

from datetime import date, datetime
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

def site_date(d: date) -> str:
    """Format a date the way ysscores.com expects: 'November 5,2026'."""
    return f"{d.strftime('%B')} {d.day},{d.year}"


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
FINISHED_STATUS = "4"

# ---------------------------------------------------------------------------
# Major league standings IDs (observed on ysscores.com)
# ---------------------------------------------------------------------------
BIG_LEAGUES: dict[str, str] = {
    "premier_league": "",
    "la_liga": "",
    "serie_a": "",
    "bundesliga": "",
    "ligue_1": "",
    "uefa_champions_league": "943230",
    "uefa_europa_league": "",
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

# Ensure all data directories exist
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
