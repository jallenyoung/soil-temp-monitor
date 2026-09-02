# Pre-Emergent Tracker — Any City

A generalized version of the Erie/Columbus trackers: type a city name,
pick the right match, and it tracks that location's modeled soil
temperature against the fall or spring pre-emergent thresholds. No fixed
station required — every location comes from Open-Meteo's geocoding +
forecast APIs.

## How city search works

Type a city (e.g. "Erie, PA", "Columbus, OH", "Austin, TX") into the City
field. It queries Open-Meteo's geocoding API and shows matches in a
dropdown — pick the right one if there's more than one place with that
name. Your last-used city search is remembered between runs (stored in
the local database), so you don't have to retype it every time.

Each city's readings are stored separately (keyed by Open-Meteo's
internal location ID), so you can switch between cities and each keeps
its own history — nothing gets overwritten if you check on more than one
location.

## Data source and caveats

Same as the Erie app:

- **Point depths, not exact 5cm/10cm**: `soil_temperature_6cm` and
  `soil_temperature_18cm` are Open-Meteo's real hourly point-depth
  variables (verified against a live response), used here as 5cm/10cm-
  equivalent fields. 6cm is close to 5cm; 18cm is a bigger jump from
  10cm, worth keeping in mind.
- **Modeled, not measured**: an ECMWF-based weather model estimate, not a
  physical thermometer in that city's soil. Good for trend-tracking;
  worth a spot-check against a real soil thermometer occasionally,
  especially for higher-stakes application timing.
- If a specific university/extension station exists for your area (like
  OSU's network for Ohio, or PEMN for Pennsylvania) and exposes a clean
  scrapable data page, that will generally be more accurate than this
  modeled estimate — this app is the fallback for anywhere a station
  like that doesn't exist or isn't easily scrapable.

## Setup

```bash
cd soil_temp_app_anycity
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Data lives in
`soil_temps_anycity.duckdb` in this folder, separate from the
Columbus and Erie apps' databases.
