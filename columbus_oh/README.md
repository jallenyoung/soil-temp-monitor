# Fall Pre-Emergent Soil Temp Tracker

A small local app (Streamlit + DuckDB) for tracking OSU CFAES soil temperature
readings against the 70°F fall pre-emergent threshold.

## Setup

```bash
cd soil_temp_app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

This opens the app in your browser at `http://localhost:8501`. Leave the
terminal running while you use it; close it (Ctrl+C) when you're done.

## How it works

- **Fetch from OSU automatically**: pulls the daily minimum soil temp at
  2" (~5cm) and 4" (~10cm) depth from OSU's Columbus station for a date
  range and stores it in a local DuckDB file (`soil_temps.duckdb`, created
  automatically next to `app.py`).
- **Log a reading manually**: fallback/override if auto-fetch isn't
  working, or if you want to log a reading OSU hasn't published yet.
- The app tracks your **streak** of consecutive days at or below 70°F at
  5cm and tells you once you've hit 3 in a row — the general application
  window for fall pre-emergent.

## If auto-fetch breaks

OSU occasionally tweaks their page layout. If you see an error on fetch,
open the URL directly in a browser to check the table still has "Min Soil
Temp 2"" and "Min Soil Temp 4"" columns:

```
https://weather.cfaes.osu.edu/dailyinfo_B.asp?location=14&startdate=YYYY-MM-DD&enddate=YYYY-MM-DD
```

Manual entry will always work regardless.

## Your data

Everything lives in `soil_temps.duckdb` in this folder — nothing leaves
your machine. Back that file up or delete it to reset.
