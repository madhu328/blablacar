from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sqlite3
import time
import random
import re
from datetime import date, datetime

# ══════════════════════════════════════════════════════
#  CONFIG — all 6 routes
# ══════════════════════════════════════════════════════

ROUTES = [
    ("Hyderabad",  "Vijayawada"),
    ("Hyderabad",  "Warangal"),
    ("Hyderabad",  "Kurnool"),
    ("Vijayawada", "Hyderabad"),
    ("Warangal",   "Hyderabad"),
    ("Kurnool",    "Hyderabad"),
]

# ══════════════════════════════════════════════════════
#  STEP 1 — Setup SQLite database
# ══════════════════════════════════════════════════════

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
    print("Database ready: blablacar_data.db")
    return con


# ══════════════════════════════════════════════════════
#  STEP 2 — Parse rides from HTML
# ══════════════════════════════════════════════════════

def parse_rides(html, from_city, to_city, travel_date):
    soup = BeautifulSoup(html, "html.parser")
    ride_links = soup.find_all("a", href=re.compile(r"/trip\?source=CARPOOLING"))

    rides = []
    skip_words = {"Hyderabad", "Vijayawada", "Warangal", "Kurnool",
                  "Instant", "Booking", "Verified", "Today", "Show", "Sort"}

    for link in ride_links:
        try:
            card  = link.parent.parent
            parts = [p.strip() for p in
                     card.get_text(separator="|", strip=True).split("|")
                     if p.strip()]

            # ── Times ─────────────────────────────────────────
            times = [p for p in parts
                     if re.match(r'^([01]?\d|2[0-3]):[0-5]\d$', p)]

            # ── Price — number right after ₹ ──────────────────
            price = None
            for i, p in enumerate(parts):
                if '₹' in p and i + 1 < len(parts):
                    nxt = parts[i + 1]
                    if re.match(r'^\d{3,4}$', nxt):
                        price = float(nxt)
                        break

            # ── Driver — first proper name after destination ───
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

            # ── Rating — decimal ≤ 5.0 after driver ──────────
            rating = None
            if driver:
                didx = next((i for i, p in enumerate(parts) if p == driver), None)
                if didx is not None:
                    for p in parts[didx: didx + 5]:
                        m = re.match(r'^(\d(\.\d)?)$', p)
                        if m and float(p) <= 5.0:
                            rating = float(p)
                            break

            # ── Seats available ────────────────────────────────
            # BlaBlaCar shows "1", "2", or "3" seats left
            # It appears as a standalone number in parts
            seats_available = None
            price_idx = None

            # Find where price is in parts to avoid confusing
            # price digits with seat digits
            for i, p in enumerate(parts):
                if '₹' in p:
                    price_idx = i
                    break

            for i, p in enumerate(parts):
                # Only look AFTER the destination city
                # and BEFORE or AFTER price
                if re.match(r'^[1-3]$', p):
                    # Make sure it's not the rating we already found
                    if rating and p == str(int(rating)):
                        continue
                    seats_available = int(p)
                    break

            # Total seats BlaBlaCar allows per car = 3 (platform standard)
            seats_total  = 3
            seats_booked = (seats_total - seats_available) if seats_available is not None else None

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


# ══════════════════════════════════════════════════════
#  STEP 3 — Scrape one route
# ══════════════════════════════════════════════════════

def scrape_route(page, from_city, to_city, travel_date):
    url = (f"https://www.blablacar.in/search"
           f"?fn={from_city}&tn={to_city}&db={travel_date}&seats=1")

    print(f"\n  → Scraping {from_city} → {to_city} on {travel_date}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(random.uniform(6, 10))

    # Scroll to load all cards
    for _ in range(3):
        page.mouse.wheel(0, 600)
        time.sleep(random.uniform(1.5, 2.5))

    html  = page.content()
    rides = parse_rides(html, from_city, to_city, travel_date)
    print(f"  ✓ Found {len(rides)} rides")
    return rides


# ══════════════════════════════════════════════════════
#  STEP 4 — Save rides to database
# ══════════════════════════════════════════════════════

def save_rides(con, rides):
    now = datetime.now().isoformat()
    for r in rides:
        con.execute("""
            INSERT INTO rides
                (scraped_at, travel_date, from_city, to_city,
                 departure, arrival, price, driver, rating,
                 seats_available, seats_total, seats_booked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now,
            r["travel_date"], r["from_city"],  r["to_city"],
            r["departure"],   r["arrival"],    r["price"],
            r["driver"],      r["rating"],
            r["seats_available"], r["seats_total"], r["seats_booked"]
        ))
    con.commit()


# ══════════════════════════════════════════════════════
#  STEP 5 — Main: run all routes
# ══════════════════════════════════════════════════════

def main():
    travel_date = date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"  BlaBlaCar Scraper — {travel_date}")
    print(f"{'='*55}")

    con   = setup_db()
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
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

        # Visit homepage first like a real user
        print("\nVisiting homepage first...")
        page.goto("https://www.blablacar.in", wait_until="domcontentloaded")
        time.sleep(random.uniform(4, 6))

        # Scrape all 6 routes
        for from_city, to_city in ROUTES:
            rides = scrape_route(page, from_city, to_city, travel_date)
            save_rides(con, rides)
            total += len(rides)

            wait = random.uniform(8, 15)
            print(f"  ↳ Waiting {wait:.0f}s before next route...")
            time.sleep(wait)

        browser.close()

    con.close()

    print(f"\n{'='*55}")
    print(f"DONE! Saved {total} rides to blablacar_data.db")
    print(f"{'='*55}\n")

    # ── Quick summary ──────────────────────────────────────
    print("QUICK SUMMARY:")
    import pandas as pd
    con2 = sqlite3.connect("blablacar_data.db")
    df = pd.read_sql("""
        SELECT from_city, to_city,
               COUNT(*)            as total_rides,
               ROUND(AVG(price),0) as avg_price,
               SUM(seats_total)    as total_capacity,
               ROUND(AVG(seats_available),1) as avg_seats_free
        FROM rides
        WHERE travel_date = ?
        GROUP BY from_city, to_city
    """, con2, params=[travel_date])
    con2.close()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
