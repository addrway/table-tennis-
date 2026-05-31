# BetsAPI Table Tennis Scraper

This is a Python scraper for BetsAPI table tennis calendar pages.

## Requirements
The script uses:
- `requests`
- `beautifulsoup4`
- `playwright`

## Setup
1. Create a virtual environment and activate it:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   playwright install chromium
   ```

## Usage
Run the script using:
```
python3 scraper.py
```

By default, the script will run in Test Mode, scraping the date `2026-03-24`. When test mode works and is disabled, it will scrape from `2026-03-24` to `2026-05-30`.

The scraper includes a fallback mechanism to Playwright if it gets blocked or encounters JavaScript-rendered content. It also stops automatically if it encounters a 403 error from Cloudflare and logs the issue. Output files will be generated in CSV and JSON formats.