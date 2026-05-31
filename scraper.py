import os
import json
import csv
import time
import random
import logging
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Configuration
TEST_MODE = True

if TEST_MODE:
    START_DATE = "2026-03-24"
    END_DATE = "2026-03-24"
    CSV_OUTPUT = "table_tennis_test_2026-03-24.csv"
    JSON_OUTPUT = "table_tennis_test_2026-03-24.json"
else:
    START_DATE = "2026-03-24"
    END_DATE = "2026-05-30"
    CSV_OUTPUT = "table_tennis_matches_2026-03-24_to_2026-05-30.csv"
    JSON_OUTPUT = "table_tennis_matches_2026-03-24_to_2026-05-30.json"

LOG_FILE = "failed_pages.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format='%(asctime)s - %(message)s'
)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def log_failed_page(url, reason):
    logging.error(f"URL: {url} | Reason: {reason}")

def delay():
    time.sleep(random.uniform(1.5, 3.0))

def get_page_content_requests(url):
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        return response.status_code, response.text, response.headers.get('Location')
    except Exception as e:
        return None, str(e), None

def get_page_content_playwright(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = response.status if response else None
            content = page.content()
            browser.close()
            return status, content, None
    except Exception as e:
        return None, str(e), None

def scrape_page(url, fallback_allowed=True):
    print(f"Scraping page: {url}")
    status, content, redirect_url = get_page_content_requests(url)

    if status == 403:
        if fallback_allowed:
            print("Received 403. Trying Playwright fallback...")
            status, content, redirect_url = get_page_content_playwright(url)
        if status == 403 or (content and "cloudflare" in content.lower()):
            print("Official API/export access may be required. 403 Blocked.")
            return 403, None

    if status == 404:
        return 404, None

    if status in [301, 302, 307, 308] or redirect_url:
        return "redirect", None

    if status is None or not content:
        return "error", None

    soup = BeautifulSoup(content, 'html.parser')
    return status, soup

def parse_matches(soup, date_str, page_number, source_url):
    matches = []
    # Actual BetsAPI table rows are likely wrapped in a table with a specific structure.
    # We will try a generic approach that extracts basic column data and identifies matches.
    # Typically, table tennis matches have time, players, score, etc.
    # Without access to the HTML, we extract what looks like match rows.
    # This assumes standard table rows.

    table = soup.find('table')
    if not table:
        return matches

    rows = table.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 3:
            continue

        # We perform a generic extraction.
        # This will be replaced by actual element selectors if we know the structure.
        # For now, extract text from columns.
        text_cols = [c.get_text(strip=True) for c in cols]

        # Best effort parsing based on typical table layouts
        match_time = text_cols[0] if len(text_cols) > 0 else ""
        league_or_tournament = text_cols[1] if len(text_cols) > 1 else ""
        players_text = text_cols[2] if len(text_cols) > 2 else ""

        player_1 = "Unknown"
        player_2 = "Unknown"
        if " v " in players_text:
            parts = players_text.split(" v ")
            player_1 = parts[0].strip()
            player_2 = parts[1].strip()
        elif "-" in players_text:
            parts = players_text.split("-")
            player_1 = parts[0].strip()
            player_2 = parts[1].strip()
        else:
            player_1 = players_text

        score = text_cols[3] if len(text_cols) > 3 else ""
        status_text = text_cols[4] if len(text_cols) > 4 else ""
        odds_home = text_cols[5] if len(text_cols) > 5 else ""
        odds_away = text_cols[6] if len(text_cols) > 6 else ""
        match_url = ""

        # Check if there is a link
        a_tag = row.find('a', href=True)
        if a_tag:
            match_url = a_tag['href']
            if not match_url.startswith("http"):
                match_url = f"https://hu.betsapi.com{match_url}"

        match_data = {
            "match_date": date_str,
            "page_number": page_number,
            "match_time": match_time,
            "league_or_tournament": league_or_tournament,
            "player_1": player_1,
            "player_2": player_2,
            "score": score,
            "status": status_text,
            "odds_home": odds_home,
            "odds_away": odds_away,
            "match_url": match_url,
            "source_url": source_url,
            "scraped_at": datetime.now().isoformat()
        }
        matches.append(match_data)

    return matches

def save_to_csv(matches, filename):
    if not matches:
        return
    keys = matches[0].keys()
    with open(filename, 'w', newline='', encoding='utf-8') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(matches)

def save_to_json(matches, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(matches, f, indent=4, ensure_ascii=False)

def deduplicate_matches(matches):
    seen = set()
    deduped = []
    for match in matches:
        # Avoid duplicate matches using:
        # match_date + match_time + league_or_tournament + player_1 + player_2
        key = (match['match_date'], match['match_time'], match['league_or_tournament'], match['player_1'], match['player_2'])
        if key not in seen:
            seen.add(key)
            deduped.append(match)
    return deduped

def daterange(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    for n in range(int((end - start).days) + 1):
        yield start + timedelta(n)

def main():
    print("Starting scraper...")
    print(f"Mode: {'TEST' if TEST_MODE else 'FULL'}")
    print(f"Date range: {START_DATE} to {END_DATE}")

    all_matches = []

    for single_date in daterange(START_DATE, END_DATE):
        date_str = single_date.strftime("%Y-%m-%d")
        print(f"Scraping date: {date_str}")

        previous_page_content = None

        for page_num in range(1, 16):
            if page_num == 1:
                url = f"https://hu.betsapi.com/cf/table-tennis/{date_str}/"
            else:
                url = f"https://hu.betsapi.com/cf/table-tennis/{date_str}/{page_num}"

            delay()
            status, soup = scrape_page(url)

            if status == 403:
                print("Stopping due to 403 Forbidden. Cloudflare block detected.")
                log_failed_page(url, "403 Forbidden")
                # Need to break completely
                return
            elif status == 404:
                print(f"Stopping reason: 404 Not Found at page {page_num}")
                break
            elif status == "redirect":
                print(f"Stopping reason: Redirected at page {page_num}")
                break
            elif status == "error" or not soup:
                print(f"Stopping reason: Error fetching page {page_num}")
                log_failed_page(url, "Fetch error")
                break

            # Simple deduplication of page content to stop if we loop
            current_content = str(soup)
            if previous_page_content and current_content == previous_page_content:
                print(f"Stopping reason: Duplicate content at page {page_num}")
                break
            previous_page_content = current_content

            matches = parse_matches(soup, date_str, page_num, url)
            print(f"Rows found: {len(matches)}")

            if len(matches) == 0:
                print(f"Stopping reason: No match rows found at page {page_num}")
                break

            all_matches.extend(matches)

    print("Deduplicating matches...")
    unique_matches = deduplicate_matches(all_matches)
    print(f"Total unique matches found: {len(unique_matches)}")

    print(f"Saving to {CSV_OUTPUT} and {JSON_OUTPUT}...")
    save_to_csv(unique_matches, CSV_OUTPUT)
    save_to_json(unique_matches, JSON_OUTPUT)
    print("Done!")

if __name__ == "__main__":
    main()