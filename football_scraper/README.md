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
│   ├── base.py          # Shared session, CSRF, throttling
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

## Output

All scraped data is saved as clean JSON files under `data/`:

- `data/news/json/news.json` — news articles
- `data/news/images/` — downloaded news images
- `data/transfers/json/transfers.json` — transfer items
- `data/transfers/images/` — downloaded transfer images

## Rules

- Pure web scraping only — no external APIs.
- Images are downloaded and saved locally (not just URLs).
- All data saved as clean JSON.
- Proper headers, delays, retries, and error handling.
- Modular, clean code structure.

## Requirements

- Python 3.10+
- `requests`
- `beautifulsoup4`
