from playwright.sync_api import sync_playwright
from flask import Flask, jsonify

import os
import json
from datetime import datetime, timedelta

CACHE_FILE = "broadway_cache.json"
CACHE_DURATION = timedelta(hours=24)

def is_cache_valid():
    if not os.path.exists(CACHE_FILE):
        return False
    modified_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
    return datetime.now() - modified_time < CACHE_DURATION

def load_cache():
    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

app = Flask(__name__)

@app.route("/broadway")
def get_broadway():
    if is_cache_valid():
        return jsonify(load_cache())
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15")
        page = context.new_page()
        page.goto("https://www.broadwayworld.com/grosses.cfm", timeout=60000)

        # Wait for the table to load
        page.wait_for_selector("div.table")
        page.wait_for_timeout(1000)

        # Click the "Gross" column header twice to sort descending
        page.click('div[data-sort="gross"]')
        page.wait_for_timeout(500)
        page.click('div[data-sort="gross"]')
        page.wait_for_timeout(2000)  # allow time for resorting

        html = page.content()
        browser.close()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", id="grosses-container")

    if not container:
        return jsonify({"error": "Grosses container not found"}), 500

    rows = container.find_all("div", class_="row")[0:10] 

    results = []
    for row in rows:
        cells = row.find_all("div", class_="cell")
        if len(cells) < 7:
            continue

        results.append({
            "rank": len(results) + 1,
            "show": cells[0].text.strip(),
            "gross": cells[1].text.strip(),
            "capacity": cells[6].text.strip(),
            "avg_ticket": cells[4].text.strip()
        })

    save_cache(results)
    return jsonify(results)
