import streamlit as st
import duckdb
import pandas as pd
from datetime import date, timedelta
import requests

DB_PATH = "soil_temps_erie.duckdb"

# Default: city of Erie, PA. Adjust if you'd rather target a specific PEMN
# station location more precisely:
#   PSU LERGREC (North East, PA):     42.2143, -79.8412
#   Waterford Little League Fields:   41.9448, -79.9756
LATITUDE = 42.1292
LONGITUDE = -80.0851
TIMEZONE = "America/New_York"

FALL_THRESHOLD = 70.0
FALL_STREAK_TARGET = 3
SPRING_LOW = 50.0
SPRING_HIGH = 55.0
SPRING_GERMINATION = 60.0
SPRING_STREAK_TARGET = 3

st.set_page_config(page_title="Erie Pre-Emergent Tracker", page_icon="🌱", layout="centered")


def get_conn():
    conn = duckdb.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS readings (
            reading_date DATE PRIMARY KEY,
            temp_5cm DOUBLE,
            temp_10cm DOUBLE,
            source VARCHAR
        )
        """
    )
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


def fetch_openmeteo_range(start_d, end_d, lat=LATITUDE, lon=LONGITUDE):
    """Pull hourly soil temperature (6cm and 18cm point depths) from
    Open-Meteo's forecast API (which seamlessly blends recent history with
    today/future) and reduce to a daily MINIMUM per depth -- matching the
    same "daily min" convention used in the OSU/Columbus tracker.

    NOTE: soil_temperature_6cm and soil_temperature_18cm are the verified
    hourly variable names for the /v1/forecast endpoint (confirmed against
    a live response) -- these are point-depth values, not depth-band
    averages. 6cm is used as the 5cm-equivalent field; 18cm as the
    10cm-equivalent field (a somewhat larger gap from 10cm than 6cm is
    from 5cm, worth keeping in mind).
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "soil_temperature_6cm,soil_temperature_18cm",
        "start_date": str(start_d),
        "end_date": str(end_d),
        "timezone": TIMEZONE,
        "temperature_unit": "fahrenheit",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    if "hourly" not in payload:
        raise ValueError(f"Unexpected response from Open-Meteo: {payload}")

    hourly = payload["hourly"]
    df = pd.DataFrame(
        {
            "time": pd.to_datetime(hourly["time"]),
            "temp_5cm": hourly["soil_temperature_6cm"],
            "temp_10cm": hourly["soil_temperature_18cm"],
        }
    )
    df["date"] = df["time"].dt.date

    daily = df.groupby("date").agg(temp_5cm=("temp_5cm", "min"), temp_10cm=("temp_10cm", "min")).reset_index()
    daily = daily.dropna(subset=["temp_5cm"])
    return daily


st.title("🌱 Erie, PA Pre-Emergent Tracker")

season = st.radio(
    "Tracking mode",
    ["Fall (post-emergent window closing, target ≤ 70°F)", "Spring (crabgrass, target 50–55°F)"],
    horizontal=True,
)
is_spring = season.startswith("Spring")

if is_spring:
    st.caption(
        "Erie, PA — modeled daily minimum soil temp (Open-Meteo), tracked against the "
        "50–55°F spring crabgrass pre-emergent window (germination begins ~55–60°F)"
    )
else:
    st.caption(
        "Erie, PA — modeled daily minimum soil temp (Open-Meteo), tracked against the 70°F fall threshold"
    )

st.caption(
    "⚠️ Data source: Open-Meteo modeled soil temperature at 6cm (5cm-equivalent) and "
    "18cm (10cm-equivalent) point depths — not a physical station sensor. See chat for details."
)

conn = get_conn()

with st.expander("Fetch from Open-Meteo automatically"):
    c1, c2 = st.columns(2)
    start_d = c1.date_input("Start date", value=date.today() - timedelta(days=7))
    end_d = c2.date_input("End date", value=date.today())
    if st.button("Fetch Open-Meteo data"):
        try:
            df_new = fetch_openmeteo_range(start_d, end_d)
            for _, row in df_new.iterrows():
                upsert_reading(conn, row["date"], row["temp_5cm"], row["temp_10cm"], source="openmeteo_auto")
            st.success(f"Imported {len(df_new)} day(s) from Open-Meteo.")
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
        df_new = fetch_openmeteo_range(fill_start, date.today())
        for _, row in df_new.iterrows():
            upsert_reading(conn, row["date"], row["temp_5cm"], row["temp_10cm"], source="openmeteo_auto")
        st.success(f"Filled {len(df_new)} day(s), through {date.today()}.")
        st.rerun()
    except Exception as e:
        st.error(f"Fill failed: {e}")

st.subheader("Log a reading")
with st.form("manual_entry", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    d = c1.date_input("Date", value=date.today())
    t5 = c2.number_input("5cm-equivalent (°F)", min_value=0.0, max_value=120.0, step=0.1, format="%.1f")
    t10 = c3.number_input("10cm-equivalent (°F, optional)", min_value=0.0, max_value=120.0, step=0.1, format="%.1f", value=0.0)
    submitted = st.form_submit_button("Add reading")
    if submitted:
        upsert_reading(conn, d, t5, t10 if t10 > 0 else None, source="manual")
        st.success(f"Logged {d}.")

df = load_readings(conn)

if df.empty:
    st.info("No readings yet — fetch from Open-Meteo or log one manually above.")
else:
    df = df.sort_values("reading_date")
    latest = df.iloc[-1]

    if is_spring:
        streak = 0
        for _, row in df.sort_values("reading_date", ascending=False).iterrows():
            if SPRING_LOW <= row["temp_5cm"] <= SPRING_HIGH:
                streak += 1
            else:
                break

        t5 = latest["temp_5cm"]
        if t5 < SPRING_LOW:
            st.info(
                f"Latest 5cm-equivalent reading ({latest['reading_date']}): **{t5:.1f}°F** — "
                f"still below {SPRING_LOW:.0f}°F, too early yet."
            )
        elif t5 > SPRING_GERMINATION:
            st.error(
                f"Latest 5cm-equivalent reading ({latest['reading_date']}): **{t5:.1f}°F** — "
                f"above {SPRING_GERMINATION:.0f}°F, crabgrass germination is likely underway. "
                "If pre-emergent isn't down yet, effectiveness will be reduced."
            )
        elif t5 > SPRING_HIGH:
            st.warning(
                f"Latest 5cm-equivalent reading ({latest['reading_date']}): **{t5:.1f}°F** — "
                f"above the {SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F window. Germination window is closing; "
                "apply now if you haven't."
            )
        elif streak >= SPRING_STREAK_TARGET:
            st.success(
                f"**In the application window.** 5cm-equivalent has held in the "
                f"{SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F range for {streak} consecutive logged days."
            )
        else:
            st.info(
                f"Getting close — 5cm-equivalent is at {t5:.1f}°F, {streak} consecutive day(s) in the "
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
                f"Latest 5cm-equivalent reading ({latest['reading_date']}): "
                f"**{latest['temp_5cm']:.1f}°F** — still above 70°F."
            )
        elif streak >= FALL_STREAK_TARGET:
            st.success(
                f"**Ready to apply.** 5cm-equivalent has held at/below 70°F for {streak} consecutive logged days."
            )
        else:
            st.info(
                f"Getting close — 5cm-equivalent is at {latest['temp_5cm']:.1f}°F, "
                f"{streak} consecutive day(s) at/below 70°F (need {FALL_STREAK_TARGET})."
            )

    st.subheader("Trend")
    chart_df = df.set_index("reading_date")[["temp_5cm", "temp_10cm"]]
    st.line_chart(chart_df)
    if is_spring:
        st.caption(f"Target window: {SPRING_LOW:.0f}–{SPRING_HIGH:.0f}°F · germination begins ~{SPRING_GERMINATION:.0f}°F")
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
