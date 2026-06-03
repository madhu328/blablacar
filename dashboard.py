import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ══════════════════════════════════════════════════════
#  Page config
# ══════════════════════════════════════════════════════

st.set_page_config(
    page_title="BlaBlaCar Route Analytics",
    page_icon="🚗",
    layout="wide"
)

# ══════════════════════════════════════════════════════
#  Load data
# ══════════════════════════════════════════════════════

@st.cache_data
def load_data():
    con = sqlite3.connect("blablacar_data.db")
    df  = pd.read_sql("SELECT * FROM rides", con)
    con.close()
    df["hour"]  = df["departure"].str[:2].astype(int)
    df["route"] = df["from_city"] + " → " + df["to_city"]
    return df

df = load_data()

# ══════════════════════════════════════════════════════
#  Header
# ══════════════════════════════════════════════════════

st.title("🚗 BlaBlaCar Route Analytics Dashboard")
st.markdown("**Routes:** Hyderabad ↔ Vijayawada · Hyderabad ↔ Warangal · Hyderabad ↔ Kurnool")
st.markdown(f"**Total rides collected:** {len(df)}")
st.divider()

# ══════════════════════════════════════════════════════
#  KPI cards — top row
# ══════════════════════════════════════════════════════

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Rides", len(df))
with col2:
    st.metric("Avg Price / Seat", f"₹{df['price'].mean():.0f}")
with col3:
    st.metric("Cheapest Ride", f"₹{df['price'].min():.0f}")
with col4:
    st.metric("Most Expensive", f"₹{df['price'].max():.0f}")

st.divider()

# ══════════════════════════════════════════════════════
#  Sidebar filter
# ══════════════════════════════════════════════════════

st.sidebar.title("Filters")
all_routes   = sorted(df["route"].unique())
selected     = st.sidebar.multiselect("Select routes", all_routes, default=all_routes)
filtered_df  = df[df["route"].isin(selected)] if selected else df

# ══════════════════════════════════════════════════════
#  TAB layout
# ══════════════════════════════════════════════════════

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Rides by Time",
    "💰 Price Analysis",
    "🕐 Peak Hours",
    "📋 Route Summary",
    "🗂 Raw Data"
])

# ── TAB 1: Rides by time sorted max → least ───────────
with tab1:
    st.subheader("Bookings by Departure Time — Most Rides → Least")

    by_time = (
        filtered_df.groupby(["route", "departure"])
        .agg(total_rides=("price","count"), avg_price=("price","mean"))
        .reset_index()
        .sort_values("total_rides", ascending=False)
    )

    fig = px.bar(
        by_time.head(30),
        x="departure",
        y="total_rides",
        color="route",
        barmode="group",
        title="Number of Rides per Departure Time",
        labels={"departure": "Departure Time", "total_rides": "Number of Rides"},
        text="total_rides",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_time.rename(columns={
            "route":"Route","departure":"Departure",
            "total_rides":"Total Rides","avg_price":"Avg Price (₹)"
        }).style.format({"Avg Price (₹)": "₹{:.0f}"}),
        use_container_width=True
    )

# ── TAB 2: Price analysis ──────────────────────────────
with tab2:
    st.subheader("Average Cost Per Seat by Route")

    avg_cost = (
        filtered_df.groupby("route")["price"]
        .agg(["mean","min","max","std"])
        .round(2)
        .reset_index()
    )
    avg_cost.columns = ["Route","Avg Price","Min Price","Max Price","Std Dev"]

    fig2 = px.bar(
        avg_cost.sort_values("Avg Price", ascending=False),
        x="Route",
        y="Avg Price",
        color="Route",
        text="Avg Price",
        title="Average Price per Seat by Route",
        labels={"Avg Price": "Avg Price (₹)"},
    )
    fig2.update_traces(texttemplate="₹%{text:.0f}", textposition="outside")
    st.plotly_chart(fig2, use_container_width=True)

    # Price distribution box plot
    fig3 = px.box(
        filtered_df,
        x="route",
        y="price",
        color="route",
        title="Price Distribution per Route",
        labels={"price":"Price (₹)","route":"Route"},
        points="all"
    )
    st.plotly_chart(fig3, use_container_width=True)

    st.dataframe(
        avg_cost.style.format({
            "Avg Price":"₹{:.2f}",
            "Min Price":"₹{:.0f}",
            "Max Price":"₹{:.0f}",
            "Std Dev":"₹{:.2f}"
        }),
        use_container_width=True
    )

# ── TAB 3: Peak hours heatmap ──────────────────────────
with tab3:
    st.subheader("Peak Booking Hours per Route")

    peak = (
        filtered_df.groupby(["route","hour"])
        .agg(rides_count=("price","count"))
        .reset_index()
    )

    fig4 = px.bar(
        peak,
        x="hour",
        y="rides_count",
        color="route",
        facet_col="route",
        facet_col_wrap=2,
        title="Rides Count by Hour of Departure",
        labels={"rides_count":"Rides","hour":"Hour"},
    )
    st.plotly_chart(fig4, use_container_width=True)

    # Heatmap
    pivot = peak.pivot_table(
        index="route", columns="hour",
        values="rides_count", fill_value=0
    )
    fig5 = px.imshow(
        pivot,
        title="Heatmap: Route vs Hour",
        labels={"color":"Rides"},
        color_continuous_scale="Blues",
        aspect="auto"
    )
    st.plotly_chart(fig5, use_container_width=True)

# ── TAB 4: Route summary ───────────────────────────────
with tab4:
    st.subheader("Complete Route Summary")

    summary = (
        filtered_df.groupby("route")
        .agg(
            total_rides = ("price","count"),
            avg_price   = ("price","mean"),
            min_price   = ("price","min"),
            max_price   = ("price","max"),
        )
        .round(2)
        .reset_index()
        .sort_values("total_rides", ascending=False)
    )
    summary.columns = ["Route","Total Rides","Avg Price (₹)","Min (₹)","Max (₹)"]

    st.dataframe(
        summary.style.format({
            "Avg Price (₹)":"₹{:.2f}",
            "Min (₹)":"₹{:.0f}",
            "Max (₹)":"₹{:.0f}"
        }).background_gradient(subset=["Total Rides"], cmap="Blues"),
        use_container_width=True
    )

    fig6 = px.pie(
        summary,
        names="Route",
        values="Total Rides",
        title="Share of Total Rides per Route"
    )
    st.plotly_chart(fig6, use_container_width=True)

# ── TAB 5: Raw data + download ─────────────────────────
with tab5:
    st.subheader("Raw Data")
    st.dataframe(filtered_df, use_container_width=True)

    csv = filtered_df.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download CSV",
        data=csv,
        file_name="blablacar_data.csv",
        mime="text/csv"
    )
