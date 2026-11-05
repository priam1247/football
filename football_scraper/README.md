# Football Scraper

A clean, modular Python web scraper for football (soccer) data from [ysscores.com](https://www.ysscores.com) (Yalla Shoot).

## Project Structure

```
football_scraper/
├── main.py              # CLI entry point
├── config.py            # Site config, paths, constants
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── scrapers/
│   ├── __init__.py
│   ├── base.py          # Session, CSRF, throttling, shared match parser
│   ├── live.py          # Live matches
│   ├── fixtures.py      # Today's fixtures
│   ├── results.py       # Full-time results
│   ├── standings.py     # League standings
│   ├── news.py          # Football news (with images)
│   └── transfers.py     # Transfer news (with images)
├── utils/
│   ├── __init__.py
│   ├── downloader.py    # Image downloader
│   ├── helpers.py       # JSON, date, text helpers
│   └── logger.py        # Logging setup
├── data/
│   ├── live/
│   ├── fixtures/
│   ├── results/
│   ├── standings/
│   ├── news/
│   │   ├── json/        # news.json
│   │   └── images/      # downloaded news images
│   └── transfers/
│       ├── json/        # transfers.json
│       └── images/      # downloaded transfer images
└── output/              # Additional output
```

`scraper.py` in the repository root is a compatibility wrapper that keeps the
original command line working while delegating all work to this package.

## Features

| Command | Description |
|---------|-------------|
| `live` | Currently live matches (teams, score, minute, league) |
| `fixtures` | Today's scheduled fixtures (kickoff, teams, league) |
| `results` | Full-time results for today and yesterday |
| `standings` | League standings for major competitions |
| `news` | Latest football news with downloaded images |
| `transfers` | Transfer news/rumors with downloaded images |
| `all` | Run every scraper |

## Installation

```bash
cd football_scraper
pip install -r requirements.txt
```

## Usage

```bash
# Live matches
python main.py live

# Today's fixtures
python main.py fixtures
python main.py fixtures --date 2026-11-05

# Full-time results
python main.py results
python main.py results --date 2026-11-05

# League standings (all known leagues)
python main.py standings

# Specific league standings
python main.py standings --league-id 943230 --league-name uefa_champions_league

# News (with image downloads)
python main.py news --pages 2
python main.py news --pages 2 --no-download-images

# Transfers (with image downloads)
python main.py transfers --pages 3
python main.py transfers --pages 3 --no-download-images

# Run everything
python main.py all
```

`--date` is optional. Without it the scraper asks the site which day it
considers "today", so the output is correct regardless of the timezone of the
machine running it.

## Output

All scraped data is saved as clean JSON files under `data/`:

- `data/news/json/news.json` — news articles
- `data/news/images/` — downloaded news images
- `data/transfers/json/transfers.json` — transfer items
- `data/transfers/images/` — downloaded transfer images

## How the site works

* `/en/home`, `/en/news` and `/en/transfer` are server rendered, so a plain GET
  returns the data directly.
* League standings live at `/en/rank/<league_id>/<slug>`, e.g.
  `/en/rank/943230/uefa_champions_league`.
* Dynamic pieces go through internal AJAX endpoints:
  * `POST /en/match_date_to` — the match list for any date
  * `GET /en/get_live_matches` — JSON clock feed for the matches in play
  * `GET /en/get_news_more` — paged news JSON
  * `GET /en/transfer_more` — paged transfer JSON
* POST endpoints need the CSRF token from the home page, so the scraper warms
  up on `/en/home` first and keeps one session (cookies + token).
* Match rows carry the data in attributes: `match_id`, `home_name`,
  `away_name`, `data-status`. Scores sit in `.first-team-result` /
  `.second-team-result`, the kick-off time in `.match-date` for matches that
  have not started, and the live clock in `#match-time-<id>`.
* Championships are grouped by `.matches-wrapper[champ_title]`.
* `data-status` codes: `0` scheduled, `1` 1st half, `2` half-time, `3` 2nd
  half, `4` finished, `7`/`9` extra time, `14` postponed.

Two details the site forces on the client:

* The match endpoint returns a bare HTML **fragment** with no
  `#match_block_list` wrapper, so rows are selected with `.mb-row-shell`
  rather than `#match_block_list .mb-row-shell`.
* The server-side status filters (`match_status=2` live, `=3` finished)
  return an empty "no matches" block, so the full list is requested once and
  filtered client side.

## Rules

- Pure web scraping only — no external APIs.
- Images are downloaded and saved locally (not just URLs).
- All data saved as clean JSON.
- Proper headers, delays, retries, and error handling.
- Modular, clean code structure.

## Tests

The offline tests run against HTML captured from the live site:

```bash
pip install pytest
python -m pytest tests/ -q
```

`python debug.py all` runs the same parsers over the captured fixtures for a
quick look without touching the network.

## Requirements

- Python 3.10+
- `requests`
- `beautifulsoup4`
