import sqlite3
import pandas as pd

# ══════════════════════════════════════════════════════
#  Load all data from database
# ══════════════════════════════════════════════════════

con = sqlite3.connect("blablacar_data.db")
df  = pd.read_sql("SELECT * FROM rides", con)
con.close()

if df.empty:
    print("No data found. Run scraper.py first.")
    exit()

print(f"✅ Total rides loaded : {len(df)}")
print(f"   Date range        : {df['travel_date'].min()} → {df['travel_date'].max()}")
print()

# ── Derived columns ────────────────────────────────────
df["hour"]  = df["departure"].str[:2].astype(int)
df["route"] = df["from_city"] + " → " + df["to_city"]

# ── Handle missing seat columns safely ────────────────
# This handles both old DB (no seat cols) and new DB
if "seats_total" not in df.columns:
    df["seats_total"] = 3
if "seats_available" not in df.columns:
    df["seats_available"] = 3
if "seats_booked" not in df.columns:
    df["seats_booked"] = 0

df["seats_total"]     = pd.to_numeric(df["seats_total"],     errors="coerce").fillna(3).astype(int)
df["seats_available"] = pd.to_numeric(df["seats_available"], errors="coerce").fillna(3).astype(int)
df["seats_booked"]    = pd.to_numeric(df["seats_booked"],    errors="coerce").fillna(0).astype(int)


# ══════════════════════════════════════════════════════
#  METRIC 1 — Bookings by time (max rides → least)
# ══════════════════════════════════════════════════════

print("=" * 70)
print("METRIC 1: BOOKINGS BY DEPARTURE TIME (most rides → least)")
print("=" * 70)

by_time = (
    df.groupby(["route", "departure"])
    .agg(
        total_rides     = ("price",           "count"),
        total_capacity  = ("seats_total",     "sum"),
        total_booked    = ("seats_booked",    "sum"),
        total_available = ("seats_available", "sum"),
        avg_price       = ("price",           "mean"),
    )
    .reset_index()
    .sort_values("total_rides", ascending=False)
)
by_time["avg_price"] = by_time["avg_price"].round(0)
print(by_time.head(25).to_string(index=False))


# ══════════════════════════════════════════════════════
#  METRIC 2 — Total capacity per route per day
# ══════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("METRIC 2: TOTAL CAPACITY PER ROUTE PER DAY")
print("=" * 70)

daily_capacity = (
    df.groupby(["travel_date", "route"])
    .agg(
        total_rides     = ("seats_total",     "count"),
        total_capacity  = ("seats_total",     "sum"),
        total_booked    = ("seats_booked",    "sum"),
        total_available = ("seats_available", "sum"),
        avg_price       = ("price",           "mean"),
    )
    .reset_index()
    .sort_values(["travel_date", "route"])
)
daily_capacity["avg_price"]   = daily_capacity["avg_price"].round(0)
daily_capacity["occupancy_%"] = (
    daily_capacity["total_booked"] /
    daily_capacity["total_capacity"] * 100
).round(1)
print(daily_capacity.to_string(index=False))


# ══════════════════════════════════════════════════════
#  METRIC 3 — Average cost per seat per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("METRIC 3: AVERAGE COST PER SEAT PER ROUTE")
print("=" * 70)

avg_cost = (
    df.groupby("route")["price"]
    .mean()
    .round(2)
    .reset_index()
    .rename(columns={"price": "avg_cost_per_seat (₹)"})
    .sort_values("avg_cost_per_seat (₹)", ascending=False)
)
print(avg_cost.to_string(index=False))


# ══════════════════════════════════════════════════════
#  METRIC 4 — Peak booking hours per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("METRIC 4: PEAK BOOKING HOURS PER ROUTE")
print("=" * 70)

peak = (
    df.groupby(["route", "hour"])
    .agg(rides_count=("price", "count"))
    .reset_index()
    .sort_values(["route", "rides_count"], ascending=[True, False])
)

for route in sorted(peak["route"].unique()):
    top = peak[peak["route"] == route].head(3)
    print(f"\n  {route}:")
    for _, row in top.iterrows():
        bar = "█" * int(row["rides_count"])
        print(f"    {int(row['hour']):02d}:00  {bar}  {int(row['rides_count'])} rides")


# ══════════════════════════════════════════════════════
#  METRIC 5 — Price range per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("METRIC 5: PRICE RANGE PER ROUTE")
print("=" * 70)

price_range = (
    df.groupby("route")["price"]
    .agg(["min", "max", "mean", "std"])
    .round(2)
    .reset_index()
)
price_range.columns = ["route", "min_price(₹)", "max_price(₹)",
                        "avg_price(₹)", "std_dev"]
print(price_range.to_string(index=False))


# ══════════════════════════════════════════════════════
#  METRIC 6 — Seat booking analysis
# ══════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("METRIC 6: SEAT AVAILABILITY & BOOKING ANALYSIS")
print("=" * 70)

seat_analysis = (
    df.groupby("route")
    .agg(
        total_rides     = ("seats_total",     "count"),
        total_seats     = ("seats_total",     "sum"),
        seats_booked    = ("seats_booked",    "sum"),
        seats_available = ("seats_available", "sum"),
    )
    .reset_index()
)
seat_analysis["booking_rate_%"] = (
    seat_analysis["seats_booked"] /
    seat_analysis["total_seats"] * 100
).round(1)
seat_analysis = seat_analysis.sort_values("booking_rate_%", ascending=False)
print(seat_analysis.to_string(index=False))
print()
print("  Note: BlaBlaCar only shows seat count when seats are LIMITED.")
print("  If no count shown = assumed all 3 seats available.")


# ══════════════════════════════════════════════════════
#  METRIC 7 — Overall 7-day summary
# ══════════════════════════════════════════════════════

print("\n" + "=" * 70)
print("METRIC 7: OVERALL 7-DAY ROUTE SUMMARY")
print("=" * 70)

summary = (
    df.groupby("route")
    .agg(
        total_rides    = ("price",        "count"),
        total_capacity = ("seats_total",  "sum"),
        seats_booked   = ("seats_booked", "sum"),
        avg_price      = ("price",        "mean"),
        min_price      = ("price",        "min"),
        max_price      = ("price",        "max"),
        avg_rating     = ("rating",       "mean"),
    )
    .round(2)
    .reset_index()
    .sort_values("total_rides", ascending=False)
)
summary.columns = [
    "route", "total_rides", "total_capacity",
    "seats_booked", "avg_price(₹)",
    "min(₹)", "max(₹)", "avg_rating"
]
print(summary.to_string(index=False))

print("\n" + "=" * 70)
print("✅ Analytics Complete!")
print("=" * 70)
print(f"  Total rides analyzed  : {len(df)}")
print(f"  Days covered          : {df['travel_date'].nunique()}")
print(f"  Routes covered        : {df['route'].nunique()}")
print(f"  Overall avg price     : ₹{df['price'].mean():.0f}")
print(f"  Cheapest ride         : ₹{df['price'].min():.0f}")
print(f"  Most expensive ride   : ₹{df['price'].max():.0f}")
print(f"  Total seats collected : {int(df['seats_total'].sum())}")
print(f"  Total seats booked    : {int(df['seats_booked'].sum())}")
print(f"  Overall booking rate  : {(df['seats_booked'].sum()/df['seats_total'].sum()*100):.1f}%")
