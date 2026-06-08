import sqlite3
import os

# ── All your database files ────────────────────────────
DB_FILES = [
    "blablacar_day1-day5.db",   # manual day1-day5, old schema
    "blablacar_day3.db",         # github day3, old schema
    "blablacar_day4.db",         # github day4, old schema
    "blablacar_day5.db",         # github day5, old schema
    "blablacar_day6.db",         # github day6, new schema
    "blablacar_day7.db",         # github day7, new schema
    "blablacar_data.db",         # manual day6+day7, new schema
]

# ── Create final combined database ────────────────────
final_con = sqlite3.connect("blablacar_FINAL.db")
final_con.execute("""
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
        seats_available  INTEGER DEFAULT 3,
        seats_total      INTEGER DEFAULT 3,
        seats_booked     INTEGER DEFAULT 0
    )
""")

total = 0

for db_file in DB_FILES:
    if not os.path.exists(db_file):
        print(f"⚠ Skipping {db_file} — file not found")
        continue

    con = sqlite3.connect(db_file)

    # Get columns available in this DB
    cols_info = con.execute("PRAGMA table_info(rides)").fetchall()
    col_names = [c[1] for c in cols_info]
    print(f"\n📂 {db_file}")
    print(f"   Columns: {col_names}")

    # Build SELECT based on available columns
    # Handle old schema (no seats columns)
    select_cols = [
        "scraped_at", "travel_date", "from_city", "to_city",
        "departure", "arrival", "price", "driver", "rating"
    ]

    if "seats_available" in col_names:
        select_cols += ["seats_available", "seats_total", "seats_booked"]
        rows = con.execute(f"""
            SELECT scraped_at, travel_date, from_city, to_city,
                   departure, arrival, price, driver, rating,
                   seats_available, seats_total, seats_booked
            FROM rides
        """).fetchall()
    else:
        # Old schema - fill seats with defaults
        rows = con.execute(f"""
            SELECT scraped_at, travel_date, from_city, to_city,
                   departure, arrival, price, driver, rating,
                   3 as seats_available,
                   3 as seats_total,
                   0 as seats_booked
            FROM rides
        """).fetchall()

    con.close()

    # Insert into final DB
    final_con.executemany("""
        INSERT INTO rides
            (scraped_at, travel_date, from_city, to_city,
             departure, arrival, price, driver, rating,
             seats_available, seats_total, seats_booked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    final_con.commit()

    print(f"   ✅ Imported {len(rows)} rides")
    total += len(rows)

# ── Remove duplicates ──────────────────────────────────
print(f"\n🔄 Removing duplicate entries...")
before = final_con.execute("SELECT COUNT(*) FROM rides").fetchone()[0]

final_con.execute("""
    DELETE FROM rides WHERE id NOT IN (
        SELECT MIN(id) FROM rides
        GROUP BY travel_date, from_city, to_city,
                 departure, price, driver
    )
""")
final_con.commit()
after = final_con.execute("SELECT COUNT(*) FROM rides").fetchone()[0]
print(f"   Before: {before} | After dedup: {after} | Removed: {before-after}")

# ── Final summary ──────────────────────────────────────
print(f"\n{'='*55}")
print(f"✅ FINAL DATABASE READY: blablacar_FINAL.db")
print(f"   Total unique rides: {after}")
print(f"{'='*55}\n")

import pandas as pd
df = pd.read_sql("""
    SELECT travel_date, COUNT(*) as rides
    FROM rides
    GROUP BY travel_date
    ORDER BY travel_date
""", final_con)
print("RIDES PER DAY:")
print(df.to_string(index=False))

df2 = pd.read_sql("""
    SELECT from_city, to_city, COUNT(*) as rides,
           ROUND(AVG(price),0) as avg_price
    FROM rides
    GROUP BY from_city, to_city
    ORDER BY from_city, to_city
""", final_con)
print("\nROUTE SUMMARY:")
print(df2.to_string(index=False))

final_con.close()
