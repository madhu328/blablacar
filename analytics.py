import sqlite3
import pandas as pd

# ══════════════════════════════════════════════════════
#  Load data from database
# ══════════════════════════════════════════════════════

con = sqlite3.connect("blablacar_data.db")
df  = pd.read_sql("SELECT * FROM rides", con)
con.close()

print(f"Total rides loaded: {len(df)}\n")

# Convert departure to sortable hour
df["hour"] = df["departure"].str[:2].astype(int)
df["route"] = df["from_city"] + " → " + df["to_city"]

# ══════════════════════════════════════════════════════
#  METRIC 1 — Bookings by time (max rides → least)
# ══════════════════════════════════════════════════════

print("=" * 60)
print("METRIC 1: BOOKINGS BY TIME (most rides → least)")
print("=" * 60)

by_time = (
    df.groupby(["route", "departure"])
    .agg(
        total_rides     = ("price", "count"),
        avg_price       = ("price", "mean"),
    )
    .reset_index()
    .sort_values("total_rides", ascending=False)
)
print(by_time.head(20).to_string(index=False))

# ══════════════════════════════════════════════════════
#  METRIC 2 — Total capacity per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("METRIC 2: TOTAL RIDES & CAPACITY PER ROUTE")
print("=" * 60)

capacity = (
    df.groupby("route")
    .agg(
        total_rides     = ("price", "count"),
        avg_price       = ("price", "mean"),
        min_price       = ("price", "min"),
        max_price       = ("price", "max"),
    )
    .reset_index()
    .sort_values("total_rides", ascending=False)
)
capacity["avg_price"] = capacity["avg_price"].round(2)
print(capacity.to_string(index=False))

# ══════════════════════════════════════════════════════
#  METRIC 3 — Average cost per seat per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("METRIC 3: AVERAGE COST PER SEAT PER ROUTE")
print("=" * 60)

avg_cost = (
    df.groupby("route")["price"]
    .mean()
    .round(2)
    .reset_index()
    .rename(columns={"price": "avg_cost_per_seat"})
    .sort_values("avg_cost_per_seat", ascending=False)
)
print(avg_cost.to_string(index=False))

# ══════════════════════════════════════════════════════
#  METRIC 4 — Peak booking hours per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("METRIC 4: PEAK HOURS (most rides listed per hour)")
print("=" * 60)

peak = (
    df.groupby(["route", "hour"])
    .agg(rides_count = ("price", "count"))
    .reset_index()
    .sort_values(["route", "rides_count"], ascending=[True, False])
)

# Show top 3 peak hours per route
for route in peak["route"].unique():
    r = peak[peak["route"] == route].head(3)
    print(f"\n{route}:")
    for _, row in r.iterrows():
        print(f"   {int(row['hour']):02d}:00  →  {int(row['rides_count'])} rides")

# ══════════════════════════════════════════════════════
#  METRIC 5 — Price range per route
# ══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("METRIC 5: PRICE RANGE PER ROUTE")
print("=" * 60)

price_range = (
    df.groupby("route")["price"]
    .agg(["min", "max", "mean", "std"])
    .round(2)
    .reset_index()
)
price_range.columns = ["route", "min_price", "max_price", "avg_price", "std_dev"]
print(price_range.to_string(index=False))

print("\n✅ Analytics complete!")
