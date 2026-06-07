# This version runs headless=True for GitHub Actions (no screen on server)
# Imports everything from scraper.py but overrides browser launch

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sqlite3
import time
import random
import re
from datetime import date, datetime

ROUTES = [
    ("Hyderabad",  "Vijayawada"),
    ("Hyderabad",  "Warangal"),
    ("Hyderabad",  "Kurnool"),
    ("Vijayawada", "Hyderabad"),
    ("Warangal",   "Hyderabad"),
    ("Kurnool",    "Hyderabad"),
]

def setup_db():
    con = sqlite3.connect("blablacar_data.db")
    con.execute("""
        CREATE TABLE IF NOT EXISTS rides (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            scraped_at       TEXT,
            travel_date      TEXT,
            from_city        TEXT,
            to_city          TEXT,
            departure        TEXT,
            arrival          TEXT,
            price            REAL,
            driver           TEXT,
            rating           REAL,
            seats_available  INTEGER,
            seats_total      INTEGER DEFAULT 3,
            seats_booked     INTEGER
        )
    """)
    con.commit()
    print("✅ Database ready")
    return con

def parse_rides(html, from_city, to_city, travel_date):
    soup = BeautifulSoup(html, "html.parser")
    ride_links = soup.find_all("a", href=re.compile(r"/trip\?source=CARPOOLING"))
    rides = []
    skip_words = {"Hyderabad","Vijayawada","Warangal","Kurnool",
                  "Instant","Booking","Verified","Today","Show","Sort"}

    for link in ride_links:
        try:
            card  = link.parent.parent
            parts = [p.strip() for p in
                     card.get_text(separator="|", strip=True).split("|")
                     if p.strip()]

            times = [p for p in parts
                     if re.match(r'^([01]?\d|2[0-3]):[0-5]\d$', p)]

            price = None
            for i, p in enumerate(parts):
                if '₹' in p and i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if re.match(r'^\d{3,4}$', nxt):
                        price = float(nxt)
                        break

            driver = None
            found_dest = False
            for p in parts:
                if p == to_city:
                    found_dest = True
                    continue
                if found_dest and re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)*$', p):
                    if p not in skip_words:
                        driver = p
                        break

            rating = None
            if driver:
                didx = next((i for i, p in enumerate(parts) if p == driver), None)
                if didx is not None:
                    for p in parts[didx: didx + 5]:
                        m = re.match(r'^(\d(\.\d)?)$', p)
                        if m and float(p) <= 5.0:
                            rating = float(p)
                            break

            seats_available = None

# Method 1: search full text for "X seat(s) left"
card_text = card.get_text(separator=" ", strip=True).lower()
seat_patterns = [
    r'(\d+)\s*seat[s]?\s*left',
    r'(\d+)\s*seat[s]?\s*available',
    r'(\d+)\s*place[s]?\s*left',
]
for pattern in seat_patterns:
    m = re.search(pattern, card_text)
    if m:
        seats_available = int(m.group(1))
        break

# Method 2: standalone number after destination
if seats_available is None:
    dest_idx = next(
        (j for j, x in enumerate(parts) if x == to_city), 0
    )
    for i, p in enumerate(parts):
        if i <= dest_idx:
            continue
        if re.match(r'^[1-3]$', p):
            if rating and abs(float(p) - float(rating)) < 0.01:
                continue
            seats_available = int(p)
            break

# Method 3: nothing found = all 3 seats available
if seats_available is None:
    seats_available = 3

seats_total  = 3
seats_booked = seats_total - seats_available
            if len(times) >= 2 and price:
                rides.append({
                    "travel_date":     travel_date,
                    "from_city":       from_city,
                    "to_city":         to_city,
                    "departure":       times[0],
                    "arrival":         times[1],
                    "price":           price,
                    "driver":          driver or "N/A",
                    "rating":          rating,
                    "seats_available": seats_available,
                    "seats_total":     seats_total,
                    "seats_booked":    seats_booked,
                })
        except Exception:
            continue
    return rides

def save_rides(con, rides):
    now = datetime.now().isoformat()
    for r in rides:
        con.execute("""
            INSERT INTO rides
                (scraped_at, travel_date, from_city, to_city,
                 departure, arrival, price, driver, rating,
                 seats_available, seats_total, seats_booked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now, r["travel_date"], r["from_city"], r["to_city"],
              r["departure"], r["arrival"], r["price"],
              r["driver"], r["rating"],
              r["seats_available"], r["seats_total"], r["seats_booked"]))
    con.commit()

def main():
    travel_date = date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"  BlaBlaCar Scraper (Headless) — {travel_date}")
    print(f"{'='*55}")

    con   = setup_db()
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,           # ← True for GitHub server
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",    # needed on Linux servers
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page.set_default_timeout(60000)

        print("\nVisiting homepage first...")
        page.goto("https://www.blablacar.in", wait_until="domcontentloaded")
        time.sleep(random.uniform(4, 6))

        for from_city, to_city in ROUTES:
            url = (f"https://www.blablacar.in/search"
                   f"?fn={from_city}&tn={to_city}&db={travel_date}&seats=1")
            print(f"\n  → Scraping {from_city} → {to_city}")
            try:
                page.goto(url, wait_until="domcontentloaded")
                time.sleep(random.uniform(6, 10))
                for _ in range(3):
                    page.mouse.wheel(0, 600)
                    time.sleep(random.uniform(1.5, 2.5))

                html  = page.content()

                # Check if blocked
                if "You have been blocked" in html:
                    print(f"  ⚠ Blocked on {from_city}→{to_city}, skipping")
                    continue

                rides = parse_rides(html, from_city, to_city, travel_date)
                save_rides(con, rides)
                total += len(rides)
                print(f"  ✓ Found {len(rides)} rides")

            except Exception as e:
                print(f"  ✗ Error: {e}")
                continue

            wait = random.uniform(8, 15)
            print(f"  ↳ Waiting {wait:.0f}s...")
            time.sleep(wait)

        browser.close()

    con.close()
    print(f"\n✅ DONE! Saved {total} rides to blablacar_data.db")

if __name__ == "__main__":
    main()
