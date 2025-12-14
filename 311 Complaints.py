import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import pydeck as pdk

# -------------------------------
# Page setup
# -------------------------------
st.set_page_config(
    page_title="Listening to NYC: 311 Complaints Story Dashboard",
    page_icon="📞",
    layout="wide",
)

st.markdown("## 📞 Listening to NYC: 311 Complaints Story Dashboard")
st.caption(
    "A story-driven dashboard exploring what New Yorkers report, when they report it, "
    "how fast requests are resolved, and where hotspots appear. Narratives update dynamically with your filters."
)

# -------------------------------
# Data loader (robust)
# -------------------------------
@st.cache_data(show_spinner=True)
def load_data():
    for fname in ["nyc311_12months.csv.gz", "nyc311_12months.csv",
                  "nyc311_sample.csv.gz", "nyc311_sample.csv"]:
        try:
            if fname.endswith(".gz"):
                df = pd.read_csv(fname, compression="gzip", low_memory=False)
            else:
                df = pd.read_csv(fname, low_memory=False)
            source = fname
            break
        except Exception:
            df, source = None, None

    if df is None:
        raise FileNotFoundError(
            "No local CSV found. Place `nyc311_12months.csv.gz` (or `nyc311_sample.csv`) beside app.py."
        )

    # Parse datetimes
    for c in ["created_date", "closed_date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Derived fields
    if {"created_date", "closed_date"}.issubset(df.columns):
        df["hours_to_close"] = (df["closed_date"] - df["created_date"]).dt.total_seconds() / 3600

    if "created_date" in df.columns:
        df["hour"] = df["created_date"].dt.hour
        df["day_of_week"] = df["created_date"].dt.day_name()

    # Normalize key columns (keep as strings; avoids categorical edge cases with mapping)
    for col in ["status", "complaint_type", "borough"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unspecified").astype(str)

    return df, source


df, source = load_data()
st.success(f"Loaded data from `{source}`")

# -------------------------------
# Sidebar filters
# -------------------------------
st.sidebar.header("🔎 Filters")

# Day of week
day_options = ["All"] + sorted(df["day_of_week"].dropna().astype(str).unique().tolist()) if "day_of_week" in df.columns else ["All"]
day_pick = st.sidebar.selectbox("Day of Week", day_options, index=0)

# Hour range
hour_range = st.sidebar.slider("Hour range (24h)", 0, 23, (0, 23))

# Borough options (exclude "Unspecified")
if "borough" in df.columns:
    boro_clean = df["borough"].astype(str)
    boro_clean = boro_clean[boro_clean.str.strip().str.lower() != "unspecified"]
    boro_options = ["All"] + sorted(boro_clean.dropna().unique().tolist())
else:
    boro_options = ["All"]

boro_pick = st.sidebar.multiselect("Borough(s)", boro_options, default=["All"])

# Top N complaint types
top_n = st.sidebar.slider("Top complaint types to show", 5, 30, 15)

# Map points cap (performance)
map_points = st.sidebar.slider("Map points (performance)", 500, 8000, 3000, step=500)
st.sidebar.caption(
    "Controls how many sampled records are drawn on the map. "
    "More points = more detail but slower hover/zoom."
)

# -------------------------------
# Apply filters (cached)
# -------------------------------
@st.cache_data(show_spinner=False)
def apply_filters(df, day_pick, hour_range, boro_pick):
    df_f = df.copy()

    if day_pick != "All" and "day_of_week" in df_f.columns:
        df_f = df_f[df_f["day_of_week"].astype(str) == day_pick]

    if "hour" in df_f.columns:
        df_f = df_f[(df_f["hour"] >= hour_range[0]) & (df_f["hour"] <= hour_range[1])]

    if "All" not in boro_pick and "borough" in df_f.columns:
        df_f = df_f[df_f["borough"].astype(str).isin(list(boro_pick))]

    return df_f


df_f = apply_filters(df, day_pick, hour_range, tuple(boro_pick))
rows_after = len(df_f)

# -------------------------------
# KPI row
# -------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows (after filters)", f"{rows_after:,}")

pct_closed = df_f["status"].eq("Closed").mean() * 100 if ("status" in df_f.columns and rows_after) else 0.0
c2.metric("% Closed", f"{pct_closed:.1f}%")

median_hours = df_f["hours_to_close"].median() if ("hours_to_close" in df_f.columns and rows_after) else np.nan
c3.metric("Median Hours to Close", "-" if np.isnan(median_hours) else f"{median_hours:.1f}")

top_type = df_f["complaint_type"].mode().iat[0] if ("complaint_type" in df_f.columns and rows_after) else "—"
c4.metric("Top Complaint Type", top_type)

# -------------------------------
# Dynamic headline narrative
# -------------------------------
def headline_narrative(df_f, pct_closed, median_hours):
    if df_f.empty:
        return "No records match the current filters. Try broadening the day/hour/borough selection."

    top_type = df_f["complaint_type"].mode().iat[0] if "complaint_type" in df_f.columns else "Unknown"
    top_boro = df_f["borough"].mode().iat[0] if "borough" in df_f.columns else "Unknown"
    peak_hour = int(df_f["hour"].value_counts().idxmax()) if "hour" in df_f.columns else None

    msg = (
        f"**Story headline:** In this view, **{top_type}** is the most reported issue. "
        f"The closure rate is **{pct_closed:.1f}%**, and the median closure time is **{median_hours:.1f} hours**."
    )
    if peak_hour is not None:
        msg += f" Reports peak around **{peak_hour:02d}:00**."
    msg += f" Highest volume borough here is **{top_boro}**."
    return msg


st.info(headline_narrative(df_f, pct_closed, median_hours))

# -------------------------------
# Operational recommendation
# -------------------------------
def operational_recommendation(df_f):
    if df_f.empty or "complaint_type" not in df_f.columns:
        return "No recommendation available for the current selection."

    top = str(df_f["complaint_type"].mode().iat[0]).upper()
    if "HEAT" in top:
        return "Increase winter capacity and prioritize heating workflows during cold months."
    if "NOISE" in top:
        return "Allocate late-night and weekend enforcement resources to noise-related complaints."
    if "PARKING" in top:
        return "Target parking enforcement during peak complaint hours and busy seasons."
    return "Use the dominant complaint type and time patterns in this view to guide staffing and routing."


st.warning(f"**Operational Recommendation:** {operational_recommendation(df_f)}")

# -------------------------------
# Tabs (story chapters)
# -------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["1) What", "2) When", "3) How fast", "4) Where"])

WARM = ["#8B0000", "#B22222", "#DC143C", "#FF4500", "#FF7F50", "#FFA500", "#FFB347", "#FFD580"]

# --------------------------------
# TAB 1: WHAT
# --------------------------------
with tab1:
    st.subheader("📊 What are New Yorkers reporting?")
    st.caption("Top complaint categories under the current filters.")

    try:
        if rows_after and "complaint_type" in df_f.columns:
            counts = (
                df_f["complaint_type"]
                .value_counts()
                .head(top_n)
                .rename_axis("Complaint Type")
                .reset_index(name="Count")
            )

            if not counts.empty:
                lead = counts.iloc[0]
                share = 100 * lead["Count"] / counts["Count"].sum()

                st.markdown(
                    f"**Narrative:** **{lead['Complaint Type']}** leads with **{int(lead['Count']):,}** requests "
                    f"(~**{share:.1f}%** of the displayed top categories)."
                )

                fig_bar = px.bar(
                    counts,
                    x="Count",
                    y="Complaint Type",
                    orientation="h",
                    text="Count",
                    color="Count",
                    color_continuous_scale=WARM,
                    title=f"Top {min(top_n, len(counts))} Complaint Types",
                )
                fig_bar.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
                fig_bar.update_layout(
                    yaxis=dict(autorange="reversed", title=None),
                    xaxis_title="Requests (count)",
                    title_font=dict(size=18)
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                st.markdown(
                    f"**Takeaway:** Complaint demand is concentrated in a few categories, led by "
                    f"**{lead['Complaint Type']}**."
                )
            else:
                st.info("No complaint types found for these filters.")
        else:
            st.info("No data available for these filters.")
    except Exception as e:
        st.error(f"Section error (Top Complaint Types): {e}")

# --------------------------------
# TAB 2: WHEN
# --------------------------------
with tab2:
    st.subheader("🔥 When do complaints happen?")
    st.caption("Trends across dates, plus hourly and weekly reporting rhythms.")

    try:
        # ---- A) OVER TIME (date slider) ----
        if rows_after and "created_date" in df_f.columns:
            dft = df_f.dropna(subset=["created_date"]).copy()
            if not dft.empty:
                min_d = dft["created_date"].min().date()
                max_d = dft["created_date"].max().date()

                start_d, end_d = st.slider(
                    "Date range",
                    min_value=min_d,
                    max_value=max_d,
                    value=(min_d, max_d)
                )

                mask = (dft["created_date"].dt.date >= start_d) & (dft["created_date"].dt.date <= end_d)
                dft2 = dft.loc[mask].copy()

                # daily counts
                daily = (
                    dft2.set_index("created_date")
                    .resample("D")
                    .size()
                    .rename("Requests")
                    .reset_index()
                )

                fig_time = px.line(
                    daily,
                    x="created_date",
                    y="Requests",
                    title="Complaints Over Time (Daily Counts)"
                )
                fig_time.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Number of Requests",
                    title_font=dict(size=18)
                )
                st.plotly_chart(fig_time, use_container_width=True)

                peak_day = daily.sort_values("Requests", ascending=False).iloc[0]
                st.markdown(
                    f"**Narrative:** The highest daily volume in this range occurs on **{peak_day['created_date'].date()}** "
                    f"with **{int(peak_day['Requests']):,}** requests."
                )
                st.markdown("**Takeaway:** Complaint volume changes over time and can spike during specific periods, "
                            "supporting proactive planning when demand rises.")
            else:
                st.info("No valid created_date values available for time trends.")

        st.markdown("---")

        # ---- B) HEATMAP Day × Hour ----
        if rows_after and {"day_of_week", "hour"}.issubset(df_f.columns):
            order_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            heat = (
                df_f.groupby(["day_of_week", "hour"])
                .size()
                .reset_index(name="Requests")
            )
            heat["day_of_week"] = pd.Categorical(heat["day_of_week"].astype(str), categories=order_days, ordered=True)
            heat = heat.sort_values(["day_of_week", "hour"])

            fig_heat = px.density_heatmap(
                heat, x="hour", y="day_of_week", z="Requests",
                color_continuous_scale="YlOrRd",
                title="Requests by Hour and Day"
            )
            fig_heat.update_traces(hovertemplate="Hour: %{x}:00<br>Day: %{y}<br>Requests: %{z:,}")
            fig_heat.update_layout(
                xaxis_title="Hour of Day",
                yaxis_title="Day of Week",
                title_font=dict(size=18)
            )
            st.plotly_chart(fig_heat, use_container_width=True)

            hot = heat.sort_values("Requests", ascending=False).head(1)
            if len(hot):
                st.markdown(
                    f"**Narrative:** The busiest time is **{hot.iloc[0]['day_of_week']} at {int(hot.iloc[0]['hour']):02d}:00**, "
                    f"with **{int(hot.iloc[0]['Requests']):,}** requests."
                )

            st.markdown(
                "**Takeaway:** Reporting follows consistent daily and weekly cycles, supporting staffing plans "
                "around predictable peak windows."
            )

        # ---- C) Animated bar (hour) ----
        if rows_after and {"hour", "complaint_type"}.issubset(df_f.columns):
            top6 = df_f["complaint_type"].value_counts().head(6).index
            df_anim = (
                df_f[df_f["complaint_type"].isin(top6)]
                .groupby(["hour", "complaint_type"])
                .size()
                .reset_index(name="Requests")
            )
            df_anim = df_anim.sort_values("hour")

            fig_anim = px.bar(
                df_anim,
                x="Requests", y="complaint_type",
                color="complaint_type",
                animation_frame="hour",
                orientation="h",
                title="How Top Complaints Evolve Through the Day (Press ▶ to Play)",
                color_discrete_sequence=WARM
            )
            fig_anim.update_layout(
                xaxis_title="Requests (count)",
                yaxis_title="Complaint Type",
                showlegend=False,
                title_font=dict(size=18)
            )
            st.plotly_chart(fig_anim, use_container_width=True)

            by_hour = df_anim.groupby("hour")["Requests"].sum().sort_values(ascending=False)
            if len(by_hour):
                st.markdown(f"**Takeaway:** Within the top categories, activity typically peaks around **{int(by_hour.index[0])}:00**.")
    except Exception as e:
        st.error(f"Section error (When): {e}")

# --------------------------------
# TAB 3: HOW FAST
# --------------------------------
with tab3:
    st.subheader("⏱️ How fast are requests resolved?")
    st.caption("Resolution time differs by complaint type and operational workflow.")

    try:
        if rows_after and {"complaint_type", "hours_to_close"}.issubset(df_f.columns):
            top_for_box = df_f["complaint_type"].value_counts().head(15).index
            df_box = df_f[df_f["complaint_type"].isin(top_for_box)].copy()

            # Clean to keep plot stable
            df_box = df_box[df_box["hours_to_close"].notna()]
            df_box = df_box[(df_box["hours_to_close"] >= 0) & (df_box["hours_to_close"] <= 24 * 60)]

            fig_box = px.box(
                df_box, x="complaint_type", y="hours_to_close",
                points=False,
                title="Resolution Time Distribution (Hours) — Top 15 Complaint Types"
            )
            fig_box.update_layout(
                xaxis=dict(title=None, tickangle=45),
                yaxis_title="Hours to Close",
                title_font=dict(size=18)
            )
            st.plotly_chart(fig_box, use_container_width=True)

            med = df_box.groupby("complaint_type")["hours_to_close"].median().sort_values(ascending=False).head(3)
            if len(med):
                bullets = " • ".join([f"**{k}** (~{v:.1f}h median)" for k, v in med.items()])
                st.markdown(f"**Narrative:** Slowest categories (median closure time) → {bullets}.")

            st.markdown(
                "**Takeaway:** Resolution speed varies by complaint type, suggesting that category-aware prioritization "
                "and agency workflows strongly influence outcomes."
            )
        else:
            st.info("Resolution-time analysis is not available for this selection.")
    except Exception as e:
        st.error(f"Section error (How fast): {e}")

# --------------------------------
# TAB 4: WHERE (FAST MAP)
# --------------------------------
with tab4:
    st.subheader("🗺️ Where are complaint hotspots? (Fast Map)")
    st.caption("WebGL map for smooth pan/zoom and fast hover tooltips. Colored by status.")

    try:
        if rows_after and {"latitude", "longitude"}.issubset(df_f.columns):
            df_map = df_f.dropna(subset=["latitude", "longitude"]).copy()
            if df_map.empty:
                st.info("No geocoded rows available under the current filters.")
            else:
                sample_n = min(map_points, len(df_map))
                df_map = df_map.sample(sample_n, random_state=42)

                df_map["hours_to_close_txt"] = df_map.get("hours_to_close", np.nan).apply(
                    lambda x: "N/A" if pd.isna(x) else f"{x:.1f}h"
                )

                status_rgb = {
                    "Closed": (46, 125, 50),
                    "In Progress": (30, 136, 229),
                    "Open": (251, 140, 0),
                    "Assigned": (142, 36, 170),
                    "Pending": (244, 81, 30),
                    "Started": (57, 73, 171),
                    "Unspecified": (158, 158, 158),
                }

                df_map["status"] = df_map["status"].astype(str).fillna("Unspecified")
                df_map["color"] = df_map["status"].map(lambda s: status_rgb.get(s, status_rgb["Unspecified"])).astype(object)

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

                view_state = pdk.ViewState(latitude=40.7128, longitude=-74.0060, zoom=10.8, pitch=0)

                tooltip = {
                    "html": "<b>{complaint_type}</b><br/>"
                            "Borough: {borough}<br/>"
                            "Status: {status}<br/>"
                            "Hours to close: {hours_to_close_txt}",
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
                    "**Takeaway:** Hotspots shift with filters. Use the map to identify where specific complaint types "
                    "concentrate and where response performance may require targeted attention."
                )
        else:
            st.info("No latitude/longitude columns available for mapping.")
    except Exception as e:
        st.error(f"Section error (Where/map): {e}")

st.markdown("---")
st.caption("Tip: If the dashboard feels slow, reduce map points or narrow filters.")
