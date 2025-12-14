import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import pydeck as pdk

# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(
    page_title="What Do New Yorkers Complain About? | NYC 311 Story",
    page_icon="📞",
    layout="wide",
)

st.title("📞 What Do New Yorkers Complain About?")
st.caption(
    "A story-driven dashboard using NYC 311 service requests (Jan 2024 → Nov 2025). "
    "Use the filters to see how complaint behavior changes across time, boroughs, and categories."
)

DATA_FILE = "nyc311_sample_2024_2025.csv"

# -------------------------------
# Load data
# -------------------------------
@st.cache_data(show_spinner=True)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Parse datetimes
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce")
    df["closed_date"] = pd.to_datetime(df["closed_date"], errors="coerce")

    # Ensure numeric
    for c in ["latitude", "longitude", "hours_to_close"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Normalize some key categoricals
    for c in ["complaint_type", "borough", "status", "agency", "agency_name", "season", "day_of_week"]:
        if c in df.columns:
            df[c] = df[c].fillna("Unspecified").astype(str)

    # Create missing derived fields if needed (your CSV already has them, but this keeps it robust)
    if "hour" not in df.columns and "created_date" in df.columns:
        df["hour"] = df["created_date"].dt.hour

    if "day_of_week" not in df.columns and "created_date" in df.columns:
        df["day_of_week"] = df["created_date"].dt.day_name()

    if "month" not in df.columns and "created_date" in df.columns:
        df["month"] = df["created_date"].dt.month

    return df


df = load_data(DATA_FILE)

# -------------------------------
# Quick validity check
# -------------------------------
if df.empty:
    st.error("Your dataset loaded but is empty. Please re-export the sample CSV.")
    st.stop()

required_cols = ["created_date", "complaint_type", "borough", "status"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {missing}. Recreate the sample CSV with these fields.")
    st.stop()

# -------------------------------
# Sidebar filters
# -------------------------------
st.sidebar.header("🔎 Filters")

# Date range filter
min_date = df["created_date"].min()
max_date = df["created_date"].max()
start_date, end_date = st.sidebar.date_input(
    "Date range",
    value=(min_date.date(), max_date.date()),
    min_value=min_date.date(),
    max_value=max_date.date(),
)

# Hour range filter
hour_range = st.sidebar.slider("Hour range (0–23)", 0, 23, (0, 23))

# Borough filter (exclude 'Unspecified' from options)
boro_options = sorted([b for b in df["borough"].unique() if b.strip().lower() != "unspecified"])
boro_pick = st.sidebar.multiselect("Borough(s)", ["All"] + boro_options, default=["All"])

# Complaint type filter
top_types = df["complaint_type"].value_counts().head(25).index.tolist()
type_pick = st.sidebar.multiselect("Complaint types (optional)", top_types, default=[])

# Map points cap (performance)
map_points = st.sidebar.slider("Map points (performance)", 500, 8000, 3000, step=500)
st.sidebar.caption("This limits how many points are drawn on the map for smooth hover/zoom.")

# -------------------------------
# Apply filters
# -------------------------------
df_f = df.copy()

# Date range
df_f = df_f[
    (df_f["created_date"].dt.date >= start_date) &
    (df_f["created_date"].dt.date <= end_date)
]

# Hour range
df_f = df_f[(df_f["hour"] >= hour_range[0]) & (df_f["hour"] <= hour_range[1])]

# Borough
if "All" not in boro_pick:
    df_f = df_f[df_f["borough"].isin(boro_pick)]

# Complaint types
if len(type_pick) > 0:
    df_f = df_f[df_f["complaint_type"].isin(type_pick)]

rows_after = len(df_f)

# -------------------------------
# KPIs
# -------------------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric("Requests (filtered)", f"{rows_after:,}")

pct_closed = (df_f["status"].eq("Closed").mean() * 100) if rows_after else 0.0
c2.metric("Closed (%)", f"{pct_closed:.1f}%")

median_hours = df_f["hours_to_close"].median() if ("hours_to_close" in df_f.columns and rows_after) else np.nan
c3.metric("Median time to close", "-" if np.isnan(median_hours) else f"{median_hours:.1f} hrs")

top_type = df_f["complaint_type"].mode().iat[0] if rows_after else "—"
c4.metric("Most common complaint", top_type)

# -------------------------------
# Dynamic story summary
# -------------------------------
def story_summary(d: pd.DataFrame) -> str:
    if d.empty:
        return "No records match your current filters. Try widening the date range or selecting more boroughs."
    top_type_local = d["complaint_type"].mode().iat[0]
    top_boro_local = d["borough"].mode().iat[0]
    peak_hour_local = int(d["hour"].value_counts().idxmax())
    close_rate_local = d["status"].eq("Closed").mean() * 100
    med_local = d["hours_to_close"].median() if "hours_to_close" in d.columns else np.nan

    text = (
        f"**Story headline:** In this view, the city is mostly hearing about **{top_type_local}** "
        f"(highest volume), especially in **{top_boro_local}**. "
        f"Reports peak around **{peak_hour_local:02d}:00**, and **{close_rate_local:.1f}%** are marked closed."
    )
    if not np.isnan(med_local):
        text += f" The median time to close is **{med_local:.1f} hours**."
    return text

st.info(story_summary(df_f))

# Optional: quick preview (helps debugging without breaking the app)
with st.expander("Preview filtered data (for debugging)"):
    st.write("Columns:", df_f.columns.tolist())
    st.dataframe(df_f.head(20), use_container_width=True)

# -------------------------------
# Story chapters (tabs)
# -------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["1) What", "2) When", "3) How fast", "4) Where"])

# ========== TAB 1: WHAT ==========
with tab1:
    st.subheader("📊 What are New Yorkers reporting?")
    st.caption("Top complaint categories under the current filters.")

    if rows_after == 0:
        st.warning("No data to display under current filters.")
    else:
        top_n = 15
        counts = df_f["complaint_type"].value_counts().head(top_n).reset_index()
        counts.columns = ["Complaint Type", "Count"]

        lead = counts.iloc[0]
        share = 100 * lead["Count"] / counts["Count"].sum()

        st.markdown(
            f"**Narrative:** **{lead['Complaint Type']}** leads with **{int(lead['Count']):,}** requests "
            f"(~**{share:.1f}%** of the top {top_n})."
        )

        fig = px.bar(
            counts,
            x="Count",
            y="Complaint Type",
            orientation="h",
            text="Count",
            title=f"Top {top_n} Complaint Types (Filtered)"
        )
        fig.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
        fig.update_layout(yaxis=dict(autorange="reversed", title=None), xaxis_title="Requests")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Takeaway:** Complaint demand is concentrated in a small number of categories, which supports targeted planning and staffing.")

# ========== TAB 2: WHEN ==========
with tab2:
    st.subheader("🕒 When do complaints happen?")
    st.caption("Daily trends + day/hour rhythm + animated hourly story.")

    if rows_after == 0:
        st.warning("No data to display under current filters.")
    else:
        # A) Daily time series
        daily = (
            df_f.dropna(subset=["created_date"])
            .set_index("created_date")
            .resample("D")
            .size()
            .rename("Requests")
            .reset_index()
        )

        fig_ts = px.line(
            daily,
            x="created_date",
            y="Requests",
            title="Complaints Over Time (Daily Count)"
        )
        fig_ts.update_layout(xaxis_title="Date", yaxis_title="Requests")
        st.plotly_chart(fig_ts, use_container_width=True)

        if not daily.empty:
            peak_day = daily.sort_values("Requests", ascending=False).iloc[0]
            st.markdown(
                f"**Narrative:** The peak day in this filtered view is **{peak_day['created_date'].date()}** "
                f"with **{int(peak_day['Requests']):,}** requests."
            )

        st.markdown("---")

        # B) Heatmap: Day × Hour
        order_days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        heat = df_f.groupby(["day_of_week", "hour"]).size().reset_index(name="Requests")
        heat["day_of_week"] = pd.Categorical(heat["day_of_week"], categories=order_days, ordered=True)
        heat = heat.sort_values(["day_of_week", "hour"])

        fig_heat = px.density_heatmap(
            heat,
            x="hour",
            y="day_of_week",
            z="Requests",
            color_continuous_scale="YlOrRd",
            title="Requests by Day of Week × Hour"
        )
        fig_heat.update_layout(xaxis_title="Hour (0–23)", yaxis_title="Day of Week")
        st.plotly_chart(fig_heat, use_container_width=True)

        busiest = heat.sort_values("Requests", ascending=False).head(1)
        if len(busiest):
            st.markdown(
                f"**Takeaway:** The busiest window is **{busiest.iloc[0]['day_of_week']} at {int(busiest.iloc[0]['hour']):02d}:00**, "
                f"showing predictable reporting rhythms tied to daily life."
            )

        st.markdown("---")

        # C) Animated bar: Top complaint types by hour
        top6 = df_f["complaint_type"].value_counts().head(6).index
        anim = (
            df_f[df_f["complaint_type"].isin(top6)]
            .groupby(["hour", "complaint_type"])
            .size()
            .reset_index(name="Requests")
            .sort_values("hour")
        )

        fig_anim = px.bar(
            anim,
            x="Requests",
            y="complaint_type",
            color="complaint_type",
            orientation="h",
            animation_frame="hour",
            title="How the Top Complaint Types Evolve Through the Day (Press ▶)"
        )
        fig_anim.update_layout(xaxis_title="Requests", yaxis_title="Complaint Type", showlegend=False)
        st.plotly_chart(fig_anim, use_container_width=True)

# ========== TAB 3: HOW FAST ==========
with tab3:
    st.subheader("⏱️ How fast are requests resolved?")
    st.caption("Resolution time varies by complaint type and operational workflow.")

    if rows_after == 0:
        st.warning("No data to display under current filters.")
    elif "hours_to_close" not in df_f.columns:
        st.error("Column `hours_to_close` is missing.")
    else:
        # Keep plot readable: top 12 complaint types
        top12 = df_f["complaint_type"].value_counts().head(12).index
        df_box = df_f[df_f["complaint_type"].isin(top12)].copy()
        df_box = df_box[df_box["hours_to_close"].notna()]
        df_box = df_box[(df_box["hours_to_close"] >= 0) & (df_box["hours_to_close"] <= 24 * 60)]

        fig_box = px.box(
            df_box,
            x="complaint_type",
            y="hours_to_close",
            points=False,
            title="Resolution Time Distribution (Hours) — Top Complaint Types"
        )
        fig_box.update_layout(xaxis_title=None, yaxis_title="Hours to close", xaxis_tickangle=45)
        st.plotly_chart(fig_box, use_container_width=True)

        med = df_box.groupby("complaint_type")["hours_to_close"].median().sort_values(ascending=False).head(3)
        if len(med):
            slow_txt = " • ".join([f"**{k}** (~{v:.1f}h median)" for k, v in med.items()])
            st.markdown(f"**Narrative:** The slowest categories (median) are: {slow_txt}.")
        st.markdown("**Takeaway:** Resolution time is not uniform; complaint type strongly influences how long closure typically takes.")

# ========== TAB 4: WHERE ==========
with tab4:
    st.subheader("🗺️ Where are complaint hotspots?")
    st.caption("Fast WebGL map (PyDeck). Colors indicate request status.")

    if rows_after == 0:
        st.warning("No data to display under current filters.")
    elif not {"latitude", "longitude"}.issubset(df_f.columns):
        st.error("Latitude/longitude columns are missing.")
    else:
        df_map = df_f.dropna(subset=["latitude", "longitude"]).copy()
        if df_map.empty:
            st.info("No geocoded rows available for the current filters.")
        else:
            df_map = df_map.sample(n=min(map_points, len(df_map)), random_state=42)

            # Status color palette (RGB tuples)
            status_rgb = {
                "Closed": (46, 125, 50),
                "In Progress": (30, 136, 229),
                "Open": (251, 140, 0),
                "Assigned": (142, 36, 170),
                "Pending": (244, 81, 30),
                "Started": (57, 73, 171),
                "Unspecified": (158, 158, 158),
            }

            df_map["status"] = df_map["status"].fillna("Unspecified").astype(str)
            df_map["color"] = df_map["status"].map(lambda s: status_rgb.get(s, status_rgb["Unspecified"])).astype(object)
            df_map["hours_to_close_txt"] = df_map["hours_to_close"].apply(
                lambda x: "N/A" if pd.isna(x) else f"{x:.1f}h"
            )

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=df_map,
                get_position="[longitude, latitude]",
                get_fill_color="color",
                get_radius=30,
                radius_min_pixels=2,
                radius_max_pixels=10,
                pickable=True,
                opacity=0.70
            )

            view_state = pdk.ViewState(latitude=40.7128, longitude=-74.0060, zoom=10.7, pitch=0)

            tooltip = {
                "html": "<b>{complaint_type}</b><br/>"
                        "Borough: {borough}<br/>"
                        "Status: {status}<br/>"
                        "Hours to close: {hours_to_close_txt}<br/>"
                        "Agency: {agency}",
                "style": {"backgroundColor": "white", "color": "black"}
            }

            st.pydeck_chart(
                pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip),
                use_container_width=True
            )

            top_boro_map = df_map["borough"].mode().iat[0] if "borough" in df_map.columns else "Unknown"
            top_type_map = df_map["complaint_type"].mode().iat[0] if "complaint_type" in df_map.columns else "Unknown"

            st.markdown(
                f"**Narrative:** In the mapped sample, complaints cluster most in **{top_boro_map}**, "
                f"and the most common complaint type is **{top_type_map}**."
            )
            st.markdown(
                "**Takeaway:** The map helps identify spatial concentration under your filters, which supports targeted local interventions."
            )

st.markdown("---")
st.caption("Tip: If the dashboard feels slow, reduce map points or narrow the date range.")

