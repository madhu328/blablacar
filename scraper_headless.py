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
    print("✅ Database ready: blablacar_data.db")
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

            # ══════════════════════════════════════════════════
            #  SEATS FIX — 3 methods to detect available seats
            # ══════════════════════════════════════════════════

            seats_available = None

            # ── Method 1: search full card text for
            #    "X seat(s) left" or "X seats available" ───────
            card_text = card.get_text(separator=" ", strip=True).lower()
            seat_patterns = [
                r'(\d+)\s*seat[s]?\s*left',
                r'(\d+)\s*seat[s]?\s*available',
                r'(\d+)\s*place[s]?\s*left',
                r'(\d+)\s*place[s]?\s*disponible',
            ]
            for pattern in seat_patterns:
                m = re.search(pattern, card_text)
                if m:
                    seats_available = int(m.group(1))
                    break

            # ── Method 2: look for standalone 1/2/3 in parts
            #    AFTER the destination city ────────────────────
            if seats_available is None:
                dest_idx = next(
                    (j for j, x in enumerate(parts) if x == to_city), 0
                )
                for i, p in enumerate(parts):
                    if i <= dest_idx:
                        continue
                    if re.match(r'^[1-3]$', p):
                        # Skip if it matches the rating value
                        if rating and abs(float(p) - float(rating)) < 0.01:
                            continue
                        seats_available = int(p)
                        break

            # ── Method 3: still None means BlaBlaCar is not
            #    showing count = all 3 seats are available ─────
            if seats_available is None:
                seats_available = 3

            # BlaBlaCar max seats per ride = 3
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


# ══════════════════════════════════════════════════════
#  STEP 3 — Scrape one route (with block detection)
# ══════════════════════════════════════════════════════

def scrape_route(page, from_city, to_city, travel_date):
    url = (f"https://www.blablacar.in/search"
           f"?fn={from_city}&tn={to_city}&db={travel_date}&seats=1")

    print(f"\n  → Scraping {from_city} → {to_city} on {travel_date}")

    try:
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(random.uniform(6, 10))

        # Human-like scrolling
        for _ in range(3):
            page.mouse.wheel(0, 600)
            time.sleep(random.uniform(1.5, 2.5))

        html = page.content()

        # ── Block detection and retry ──────────────────
        if "You have been blocked" in html:
            print(f"  ⚠ Blocked! Retrying after 30s...")
            time.sleep(30)
            page.goto("https://www.blablacar.in", wait_until="domcontentloaded")
            time.sleep(random.uniform(5, 8))
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(random.uniform(8, 12))
            html = page.content()
            if "You have been blocked" in html:
                print(f"  ✗ Still blocked. Skipping.")
                return []

        rides = parse_rides(html, from_city, to_city, travel_date)
        print(f"  ✓ Found {len(rides)} rides")
        return rides

    except Exception as e:
        print(f"  ✗ Error scraping {from_city} → {to_city}: {e}")
        return []


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
#  STEP 5 — Main: run all 6 routes
#  headless=True for GitHub Actions (no screen on server)
# ══════════════════════════════════════════════════════

def main():
    travel_date = date.today().strftime("%Y-%m-%d")
    print(f"\n{'='*55}")
    print(f"  BlaBlaCar Scraper (Headless) — {travel_date}")
    print(f"{'='*55}")

    con   = setup_db()
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,              # True for GitHub server (no screen)
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",   # required on Linux servers
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

        # ── KEY anti-detection: hide webdriver flag ────────
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

            # Random wait between routes to avoid detection
            wait = random.uniform(8, 15)
            print(f"  ↳ Waiting {wait:.0f}s before next route...")
            time.sleep(wait)

        browser.close()

    con.close()

    print(f"\n{'='*55}")
    print(f"✅ DONE! Saved {total} rides to blablacar_data.db")
    print(f"{'='*55}\n")

    # ── Quick summary ──────────────────────────────────
    import pandas as pd
    con2 = sqlite3.connect("blablacar_data.db")
    df = pd.read_sql("""
        SELECT
            from_city,
            to_city,
            COUNT(*)                       as total_rides,
            SUM(seats_total)               as total_capacity,
            SUM(seats_booked)              as total_booked,
            SUM(seats_available)           as total_available,
            ROUND(AVG(price), 0)           as avg_price
        FROM rides
        WHERE travel_date = ?
        GROUP BY from_city, to_city
    """, con2, params=[travel_date])
    con2.close()
    print("TODAY'S SUMMARY:")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
