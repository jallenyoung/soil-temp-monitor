# Erie, PA Pre-Emergent Soil Temp Tracker

A sibling to the Columbus, OH tracker, adapted for Erie, PA. Same DuckDB +
Streamlit approach, same fall/spring toggle — different data source.

## Why a different data source

Ohio State's CFAES weather network has a station in Columbus with a clean,
scrapable daily-data page. Penn State's equivalent network (PEMN) does have
two stations in Erie County, but its site loads data via JavaScript/AJAX
rather than a plain HTML table, so there's no reliable page to scrape the
way `dailyinfo_B.asp` works for OSU.

Instead, this app pulls from **Open-Meteo**, a free public weather API
(no key required) that models soil temperature at depth bands using
ECMWF-based weather models. It's the same underlying data source used by
sites like soiltemps.com for Erie-area estimates.

**Important differences from the Columbus app:**

- **Point depths, not exact 5cm/10cm.** Open-Meteo's `/v1/forecast` hourly
  variables are `soil_temperature_6cm` and `soil_temperature_18cm` (real
  point-depth values, not depth-band averages), used here as 5cm/10cm-
  equivalent fields. 6cm is close to 5cm; 18cm is a bigger jump from 10cm,
  worth keeping in mind.
- **Modeled, not measured.** This is a weather-model estimate, not a
  physical thermometer in the ground in Erie. Good for trend-tracking;
  worth a spot-check against a soil thermometer occasionally.
- The default coordinates target the city of Erie, PA generally. Edit
  `LATITUDE` / `LONGITUDE` near the top of `app.py` if you'd rather target
  a specific spot — a couple of PEMN station locations are noted in
  comments there as reference points.

## Setup

```bash
cd soil_temp_app_erie
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Data lives in `soil_temps_erie.duckdb`
in this folder — separate from the Columbus app's database, so the two
don't collide even if you run them from sibling folders.

## Usage

Same as the Columbus app: use "Fetch from Open-Meteo automatically" for a
custom date range, or "Fill missing days" to top up from your last logged
day through today in one click. Manual entry works as a fallback if the
API call ever fails.
