import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import pydeck as pdk

# ------------------------------------------------------------
# Page config
# ------------------------------------------------------------
st.set_page_config(
    page_title="Listening to NYC: 311 Complaints Story Dashboard",
    page_icon="📞",
    layout="wide",
)

st.markdown("## 📞 Listening to NYC: A 311 Complaints Story Dashboard")
st.caption(
    "A storytelling dashboard that explores *what* New Yorkers report, *when* they report it, "
    "*how fast* issues are resolved, and *where* complaint hotspots appear — with dynamic narratives."
)

# ------------------------------------------------------------
# Data Loading
# ------------------------------------------------------------
@st.cache_data(show_spinner=True)
def load_data():
    # Put your compressed file in the repo root (recommended)
    candidates = [
        "nyc311_12months.csv.gz",
        "nyc311_12months.csv",
        "nyc311_sample.csv.gz",
        "nyc311_sample.csv",
    ]

    df, source = None, None
    for fname in candidates:
        try:
            if fname.endswith(".gz"):
                df = pd.read_csv(fname, compression="gzip", low_memory=False)
            else:
                df = pd.read_csv(fname, low_memory=False)
            source = fname
            break
        except Exception:
            continue

    if df is None:
        raise FileNotFoundError(
            "No local CSV found. Add `nyc311_12months.csv.gz` (or a small sample) to the repo root."
        )

    # Parse datetime fields
    for c in ["created_date", "closed_date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Derived fields
    if {"created_date", "closed_date"}.issubset(df.columns):
        df["hours_to_close"] = (df["closed_date"] - df["created_date"]).dt.total_seconds() / 3600

    if "created_date" in df.columns:
        df["hour"] = df["created_date"].dt.hour
        df["day_of_week"] = df["created_date"].dt.day_name()
        df["month"] = df["created_date"].dt.month_name()

    # Normalize key columns
    for col in ["status", "complaint_type", "borough"]:
        if col in df.columns:
            df[col] = df[col].fillna("Unspecified")

    # Performance: categories reduce memory + speed groupby
    for col in ["borough", "complaint_type", "status", "day_of_week", "month"]:
        if col in df.columns:
            df[col] = df[col].astype("category")

    return df, source


df, source = load_data()
st.success(f"Loaded data from `{source}`")

# ------------------------------------------------------------
# Sidebar Filters
# ------------------------------------------------------------
st.sidebar.header("🔎 Filters")

day_options = ["All"] + sorted(df["day_of_week"].dropna().unique().tolist()) if "day_of_week" in df else ["All"]
day_pick = st.sidebar.selectbox("Day of Week", day_options, index=0)

hour_range = st.sidebar.slider("Hour range (24h)", 0, 23, (0, 23))

boro_options = ["All"] + sorted(df["borough"].dropna().unique().tolist()) if "borough" in df else ["All"]
boro_pick = st.sidebar.multiselect("Borough(s)", boro_options, default=["All"])

top_n = st.sidebar.slider("Top complaint types to show", 5, 30, 15)

map_points = st.sidebar.slider("Map points (performance)", 500, 8000, 3000, step=500)

# ------------------------------------------------------------
# Cached filtering
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def apply_filters(df, day_pick, hour_range, boro_pick):
    df_f = df.copy()

    if day_pick != "All" and "day_of_week" in df_f.columns:
        df_f = df_f[df_f["day_of_week"] == day_pick]

    if "hour" in df_f.columns:
        df_f = df_f[(df_f["hour"] >= hour_range[0]) & (df_f["hour"] <= hour_range[1])]

    if "All" not in boro_pick and "borough" in df_f.columns:
        df_f = df_f[df_f["borough"].isin(boro_pick)]

    return df_f


df_f = apply_filters(df, day_pick, hour_range, tuple(boro_pick))
rows_after = len(df_f)

# ------------------------------------------------------------
# KPIs
# ------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows (after filters)", f"{rows_after:,}")

pct_closed = df_f["status"].eq("Closed").mean() * 100 if ("status" in df_f.columns and rows_after) else 0.0
c2.metric("% Closed", f"{pct_closed:.1f}%")

median_hours = df_f["hours_to_close"].median() if ("hours_to_close" in df_f.columns and rows_after) else np.nan
c3.metric("Median Hours to Close", "-" if np.isnan(median_hours) else f"{median_hours:.1f}")

top_type = df_f["complaint_type"].mode().iat[0] if ("complaint_type" in df_f.columns and rows_after) else "—"
c4.metric("Top Complaint Type", top_type)

# ------------------------------------------------------------
# Dynamic headline narrative (changes with filters)
# ------------------------------------------------------------
def headline_narrative(df_f, pct_closed, median_hours):
    if df_f.empty:
        return "No records match the current filters. Try expanding time/day/borough selections."

    top_type = df_f["complaint_type"].mode().iat[0] if "complaint_type" in df_f.columns else "Unknown"
    top_boro = df_f["borough"].mode().iat[0] if "borough" in df_f.columns else "Unknown"
    peak_hour = int(df_f["hour"].value_counts().idxmax()) if "hour" in df_f.columns else None

    msg = (
        f"**Story headline:** Under the current filters, **{top_type}** is the most common complaint. "
        f"The city closes **{pct_closed:.1f}%** of these requests, and the median time to close is "
        f"**{median_hours:.1f} hours**."
    )
    if peak_hour is not None:
        msg += f" Reports peak around **{peak_hour:02d}:00**."
    msg += f" The highest volume borough in this view is **{top_boro}**."
    return msg


st.info(headline_narrative(df_f, pct_closed, median_hours))

# ------------------------------------------------------------
# Recommendation box (simple decision-support behavior)
# ------------------------------------------------------------
def operational_recommendation(df_f):
    if df_f.empty or "complaint_type" not in df_f.columns:
        return "No recommendation available for the current selection."
    top = str(df_f["complaint_type"].mode().iat[0]).upper()

    if "HEAT" in top:
        return "Increase winter staffing and prioritize heating complaint workflows during cold months."
    if "NOISE" in top:
        return "Allocate late-night and weekend enforcement resources to noise-related complaints."
    if "PARKING" in top:
        return "Consider targeted parking enforcement during peak complaint hours and busy seasons."
    return "Use complaint volume and resolution trends from this view to guide staffing and routing decisions."


st.warning(f"**Operational Recommendation:** {operational_recommendation(df_f)}")

# ------------------------------------------------------------
# Tabs = Chapters (storytelling flow)
# ------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["1) What", "2) When", "3) How fast", "4) Where"])

# Warm palette for some charts
WARM = ["#8B0000", "#B22222", "#DC143C", "#FF4500", "#FF7F50", "#FFA500", "#FFB347", "#FFD580"]


# =========================
# TAB 1: WHAT
# =========================
with tab1:
    st.subheader("📊 What are New Yorkers reporting?")
    st.caption("This section shows the most frequent complaint categories under the current filters.")

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
                f"**Narrative:** The leading complaint is **{lead['Complaint Type']}** with **{int(lead['Count']):,}** requests "
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
                f"**Takeaway:** In this view, complaint demand is concentrated in a few categories, led by "
                f"**{lead['Complaint Type']}**, which can guide targeted staffing and enforcement priorities."
            )
        else:
            st.info("No complaint types found for these filters.")
    else:
        st.info("No data available for these filters.")


# =========================
# TAB 2: WHEN
# =========================
with tab2:
    st.subheader("🔥 When do complaints happen?")
    st.caption("This section highlights daily and hourly reporting rhythms.")

    if rows_after and {"day_of_week", "hour"}.issubset(df_f.columns):
        order_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heat = (
            df_f.groupby(["day_of_week", "hour"])
            .size()
            .reset_index(name="Requests")
        )
        heat["day_of_week"] = pd.Categorical(heat["day_of_week"], categories=order_days, ordered=True)
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
            "**Takeaway:** Complaint reporting follows consistent weekly and hourly cycles, which can help "
            "agencies schedule staffing around predictable peak windows."
        )

        # Animated bar (top 6 categories)
        if "complaint_type" in df_f.columns:
            top6 = df_f["complaint_type"].value_counts().head(6).index
            df_anim = (
                df_f[df_f["complaint_type"].isin(top6)]
                .groupby(["hour", "complaint_type"])
                .size()
                .reset_index(name="Requests")
            )

            fig_anim = px.bar(
                df_anim,
                x="Requests", y="complaint_type",
                color="complaint_type",
                animation_frame="hour",
                orientation="h",
                title="Top complaints through the day (press ▶ to play)",
                color_discrete_sequence=WARM
            )
            fig_anim.update_layout(
                xaxis_title="Requests (count)",
                yaxis_title="Complaint Type",
                showlegend=False,
                title_font=dict(size=18)
            )
            st.plotly_chart(fig_anim, use_container_width=True)

    else:
        st.info("Not enough information to show time patterns for the current filters.")


# =========================
# TAB 3: HOW FAST
# =========================
with tab3:
    st.subheader("⏱️ How fast are requests resolved?")
    st.caption("This section focuses on resolution time and potential delay patterns.")

    if rows_after and {"complaint_type", "hours_to_close"}.issubset(df_f.columns):
        top_for_box = df_f["complaint_type"].value_counts().head(15).index
        df_box = df_f[df_f["complaint_type"].isin(top_for_box)].copy()
        df_box = df_box[df_box["hours_to_close"].notna()]
        df_box = df_box[(df_box["hours_to_close"] >= 0) & (df_box["hours_to_close"] <= 24 * 60)]  # keep sane range

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
            "**Takeaway:** Resolution speed varies significantly by complaint type, suggesting that category-aware "
            "prioritization and agency workflow differences strongly affect response performance."
        )
    else:
        st.info("Resolution-time analysis is not available for the current selection.")


# =========================
# TAB 4: WHERE (FAST MAP)
# =========================
with tab4:
    st.subheader("🗺️ Where are complaint hotspots? (Fast WebGL Map)")
    st.caption("This map uses WebGL for smooth interaction and fast hover tooltips.")

    if rows_after and {"latitude", "longitude"}.issubset(df_f.columns):
        df_map = df_f.dropna(subset=["latitude", "longitude"]).copy()
        if df_map.empty:
            st.info("No geocoded rows available under the current filters.")
        else:
            # Sample for speed
            sample_n = min(map_points, len(df_map))
            df_map = df_map.sample(sample_n, random_state=42)

            df_map["hours_to_close_txt"] = df_map.get("hours_to_close", np.nan).apply(
                lambda x: "N/A" if pd.isna(x) else f"{x:.1f}h"
            )

            # Status -> RGB color
            status_rgb = {
                "Closed": [46, 125, 50],
                "In Progress": [30, 136, 229],
                "Open": [251, 140, 0],
                "Assigned": [142, 36, 170],
                "Pending": [244, 81, 30],
                "Started": [57, 73, 171],
                "Unspecified": [158, 158, 158],
            }
            df_map["status"] = df_map["status"].fillna("Unspecified")
            df_map["color"] = df_map["status"].apply(lambda s: status_rgb.get(str(s), status_rgb["Unspecified"]))

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

            view_state = pdk.ViewState(
                latitude=40.7128,
                longitude=-74.0060,
                zoom=10.8,
                pitch=0
            )

            tooltip = {
                "html": "<b>{complaint_type}</b><br/>"
                        "Borough: {borough}<br/>"
                        "Status: {status}<br/>"
                        "Hours to close: {hours_to_close_txt}",
                "style": {"backgroundColor": "white", "color": "black"}
            }

            st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip),
                            use_container_width=True)

            # “Hotspot narrative”: top borough + top complaint in mapped sample
            top_boro_map = df_map["borough"].mode().iat[0] if "borough" in df_map.columns else "Unknown"
            top_type_map = df_map["complaint_type"].mode().iat[0] if "complaint_type" in df_map.columns else "Unknown"

            st.markdown(
                f"**Narrative:** Within the mapped sample, complaints cluster most in **{top_boro_map}**, "
                f"and the most common mapped complaint type is **{top_type_map}**."
            )

            st.markdown(
                "**Takeaway:** Location patterns help identify where demand concentrates, supporting targeted field deployment "
                "and neighborhood-level planning."
            )

            with st.expander("Show sample rows used on the map"):
                st.dataframe(
                    df_map[["created_date", "complaint_type", "borough", "status", "hours_to_close"]]
                    .sort_values("created_date", ascending=False)
                    .head(50),
                    use_container_width=True
                )
    else:
        st.info("No latitude/longitude columns available for mapping.")

st.markdown("---")
st.caption("Tip: If the dashboard feels slow, reduce map points or narrow filters.")
