import streamlit as st
import duckdb
import pandas as pd
from datetime import date, timedelta
from io import StringIO
import requests

DB_PATH = "soil_temps.duckdb"
STATION_ID = 14
FALL_THRESHOLD = 70.0
FALL_STREAK_TARGET = 3
SPRING_LOW = 50.0
SPRING_HIGH = 55.0
SPRING_GERMINATION = 60.0
SPRING_STREAK_TARGET = 3

st.set_page_config(
    page_title="Fall Pre-Emergent Tracker", page_icon="🌱", layout="centered"
)


def get_conn():
    conn = duckdb.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            reading_date DATE PRIMARY KEY,
            temp_5cm DOUBLE,
            temp_10cm DOUBLE,
            source VARCHAR
        )
        """)
    return conn


def upsert_reading(conn, d, t5, t10, source="manual"):
    conn.execute(
        """
        INSERT INTO readings (reading_date, temp_5cm, temp_10cm, source)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (reading_date) DO UPDATE SET
            temp_5cm = excluded.temp_5cm,
            temp_10cm = excluded.temp_10cm,
            source = excluded.source
        """,
        [d, t5, t10, source],
    )


def load_readings(conn):
    return conn.execute("SELECT * FROM readings ORDER BY reading_date").df()


def latest_reading_date(conn):
    row = conn.execute("SELECT MAX(reading_date) FROM readings").fetchone()
    return row[0] if row and row[0] is not None else None


def delete_reading(conn, d):
    conn.execute("DELETE FROM readings WHERE reading_date = ?", [d])


def fetch_osu_range(start_d, end_d):
    """Best-effort scrape of OSU's daily min soil temps.

    NOTE: this parses OSU's dailyinfo_B.asp table by looking for columns
    containing 'Min Soil Temp 2"' and 'Min Soil Temp 4"'. If OSU changes
    their page layout, this will raise an error rather than silently
    returning wrong data -- fall back to manual entry in that case.
    """
    url = (
        "https://weather.cfaes.osu.edu/dailyinfo_B.asp"
        f"?location={STATION_ID}&startdate={start_d}&enddate={end_d}"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    tables = pd.read_html(StringIO(resp.text))
    target = None
    for t in tables:
        cols = [str(c) for c in t.columns]
        if any("Min Soil Temp 2" in c for c in cols):
            target = t
            break
    if target is None:
        raise ValueError(
            "Couldn't find the soil temp table on OSU's page -- "
            "they may have changed their layout. Use manual entry instead."
        )

    col5 = [c for c in target.columns if "Min Soil Temp 2" in str(c)][0]
    col10 = [c for c in target.columns if "Min Soil Temp 4" in str(c)][0]
    date_col = [c for c in target.columns if str(c).strip().lower() == "date"][0]

    out = target[[date_col, col5, col10]].copy()
    out.columns = ["date", "temp_5cm", "temp_10cm"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    out = out.dropna(subset=["date"])
    out = out[pd.to_numeric(out["temp_5cm"], errors="coerce").notna()]
    return out


st.title("🌱 Pre-Emergent Tracker")

season = st.radio(
    "Tracking mode",
    [
        "Fall (post-emergent window closing, target ≤ 70°F)",
        "Spring (crabgrass, target 50–55°F)",
    ],
    horizontal=True,
)
is_spring = season.startswith("Spring")

if is_spring:
    st.caption(
        "Columbus, OH — OSU CFAES station soil temps, tracked against the "
        "50–55°F spring crabgrass pre-emergent window (germination begins ~55–60°F)"
    )
else:
    st.caption(
        "Columbus, OH — OSU CFAES station soil temps, tracked against the 70°F fall threshold"
    )

conn = get_conn()

with st.expander("Fetch from OSU automatically"):
    c1, c2 = st.columns(2)
    start_d = c1.date_input("Start date", value=date.today() - timedelta(days=7))
    end_d = c2.date_input("End date", value=date.today())
    if st.button("Fetch OSU data"):
        try:
            df_new = fetch_osu_range(start_d, end_d)
            for _, row in df_new.iterrows():
                upsert_reading(
                    conn,
                    row["date"],
                    row["temp_5cm"],
                    row["temp_10cm"],
                    source="osu_auto",
                )
            st.success(f"Imported {len(df_new)} day(s) from OSU.")
        except Exception as e:
            st.error(f"Auto-fetch failed: {e}")

last_date = latest_reading_date(conn)
if last_date is None:
    fill_label = "Fill missing days (no history yet — pulls last 7 days)"
    fill_start = date.today() - timedelta(days=7)
elif last_date >= date.today():
    fill_label = "Fill missing days (already up to date)"
    fill_start = None
else:
    fill_label = f"Fill missing days ({last_date + timedelta(days=1)} → today)"
    fill_start = last_date + timedelta(days=1)

fill_disabled = fill_start is None
if st.button(fill_label, disabled=fill_disabled):
    try:
        df_new = fetch_osu_range(fill_start, date.today())
        for _, row in df_new.iterrows():
            upsert_reading(
                conn, row["date"], row["temp_5cm"], row["temp_10cm"], source="osu_auto"
            )
        st.success(f"Filled {len(df_new)} day(s), through {date.today()}.")
        st.rerun()
    except Exception as e:
        st.error(f"Fill failed: {e}")

st.subheader("Log a reading")
with st.form("manual_entry", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    d = c1.date_input("Date", value=date.today())
    t5 = c2.number_input(
        "5cm (°F)", min_value=0.0, max_value=120.0, step=0.1, format="%.1f"
    )
    t10 = c3.number_input(
        "10cm (°F, optional)",
        min_value=0.0,
        max_value=120.0,
        step=0.1,
        format="%.1f",
        value=0.0,
    )
    submitted = st.form_submit_button("Add reading")
    if submitted:
        upsert_reading(conn, d, t5, t10 if t10 > 0 else None, source="manual")
        st.success(f"Logged {d}.")

df = load_readings(conn)

if df.empty:
    st.info("No readings yet — fetch from OSU or log one manually above.")
else:
    df = df.sort_values("reading_date")
    latest = df.iloc[-1]

    if is_spring:
        # Streak of consecutive days (ending at the latest) within the 50-55F window
        streak = 0
        for _, row in df.sort_values("reading_date", ascending=False).iterrows():
            if SPRING_LOW <= row["temp_5cm"] <= SPRING_HIGH:
                streak += 1
            else:
                break

        t5 = latest["temp_5cm"]
        if t5 < SPRING_LOW:
            st.info(
                f"Latest 5cm reading ({latest['reading_date']}): **{t5:.1f}°F** — "
                f"still below {SPRING_LOW:.0f}°F, too early yet."
            )
        elif t5 > SPRING_GERMINATION:
            st.error(
                f"Latest 5cm reading ({latest['reading_date']}): **{t5:.1f}°F** — "
                f"above {SPRING_GERMINATION:.0f}°F, crabgrass germination is likely underway. "
                "If pre-emergent isn't down yet, effectiveness will be reduced."
            )
        elif t5 > SPRING_HIGH:
            st.warning(
                f"Latest 5cm reading ({latest['reading_date']}): **{t5:.1f}°F** — "
                f"above the {SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F window. Germination window is closing; "
                "apply now if you haven't."
            )
        elif streak >= SPRING_STREAK_TARGET:
            st.success(
                f"**In the application window.** 5cm has held in the {SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F "
                f"range for {streak} consecutive logged days."
            )
        else:
            st.info(
                f"Getting close — 5cm is at {t5:.1f}°F, {streak} consecutive day(s) in the "
                f"{SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F range (need {SPRING_STREAK_TARGET})."
            )
    else:
        streak = 0
        for _, row in df.sort_values("reading_date", ascending=False).iterrows():
            if row["temp_5cm"] <= FALL_THRESHOLD:
                streak += 1
            else:
                break

        if latest["temp_5cm"] > FALL_THRESHOLD:
            st.warning(
                f"Latest 5cm reading ({latest['reading_date']}): "
                f"**{latest['temp_5cm']:.1f}°F** — still above 70°F."
            )
        elif streak >= FALL_STREAK_TARGET:
            st.success(
                f"**Ready to apply.** 5cm has held at/below 70°F for {streak} consecutive logged days."
            )
        else:
            st.info(
                f"Getting close — 5cm is at {latest['temp_5cm']:.1f}°F, "
                f"{streak} consecutive day(s) at/below 70°F (need {FALL_STREAK_TARGET})."
            )

    st.subheader("Trend")
    chart_df = df.set_index("reading_date")[["temp_5cm", "temp_10cm"]]
    st.line_chart(chart_df)
    if is_spring:
        st.caption(
            f"Target window: {SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F · germination begins ~{SPRING_GERMINATION:.0f}°F"
        )
    else:
        st.caption(f"Target threshold: ≤ {FALL_THRESHOLD:.0f}°F")

    st.subheader("History")
    display_df = df.sort_values("reading_date", ascending=False).copy()
    if is_spring:

        def spring_status(t):
            if t < SPRING_LOW:
                return "below window"
            if t <= SPRING_HIGH:
                return "in window"
            if t <= SPRING_GERMINATION:
                return "above window"
            return "germination likely"

        display_df["status"] = display_df["temp_5cm"].apply(spring_status)
    else:
        display_df["status"] = display_df["temp_5cm"].apply(
            lambda t: "at/below 70" if t <= FALL_THRESHOLD else "above 70"
        )
    st.dataframe(
        display_df[["reading_date", "temp_5cm", "temp_10cm", "status", "source"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Manage entries")
    del_date = st.selectbox("Delete a reading", options=df["reading_date"].tolist())
    if st.button("Delete selected"):
        delete_reading(conn, del_date)
        st.rerun()
