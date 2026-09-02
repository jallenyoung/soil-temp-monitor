# Pre-Emergent Soil Temp Tracker — Project Context

This file exists to give an AI coding agent (or a future me) full context
on this project without re-deriving it from scratch. Read this before
making changes.

## What this project is

A set of tools for timing lawn pre-emergent herbicide applications based
on soil temperature, since the right timing depends on soil temp trends,
not calendar dates:

- **Fall application** (targets winter annual weeds): apply once soil
  temp at ~5cm depth has held at or below **70°F** for **3 consecutive
  days**. This is a *falling* threshold.
- **Spring application** (targets crabgrass): apply while soil temp at
  ~5cm depth is in the **50–55°F** window, ideally for 3 consecutive
  days. Crabgrass germination begins around 55–60°F, after which a fresh
  application is much less effective. This is a *rising* threshold with
  both a floor and a ceiling.

Both use the **daily minimum** soil temperature (not average or max) as
the tracked value — daily min is the earliest, most conservative signal
of the trend, and it's what OSU's own long-term dataset benchmarks
against (see below).

## Three apps, in the order they were built

### 1. `columbus_oh/` — Ohio State CFAES station scraper

The original, most accurate version. Ohio State's CFAES weather network
has a real physical station in Columbus with a clean daily-data HTML
table at:

```
https://weather.cfaes.osu.edu/dailyinfo_B.asp?location=14&startdate=YYYY-MM-DD&enddate=YYYY-MM-DD
```

The app scrapes the "Min Soil Temp 2\"" and "Min Soil Temp 4\"" columns
(≈5cm/10cm) using `pandas.read_html()`.

**Known gotcha already fixed**: newer pandas requires raw HTML strings to
be wrapped in `io.StringIO()` before `pd.read_html()`, or it tries to
treat the whole HTML blob as a file path and throws a confusing
`FileNotFoundError`. Already fixed in the current `app.py` — don't
regress this if refactoring.

This is real station data, not modeled — the most trustworthy of the
three apps, but only useful near Columbus, OH.

### 2. `erie_pa/` — Erie, PA via Open-Meteo

We initially looked for an Ohio-State-style scrapable station for Erie,
PA. Penn State's equivalent network (PEMN, climate.met.psu.edu) does
have two stations in Erie County (PSU LERGREC / North East, PA, and
Waterford Little League Fields), but the PEMN site loads data via
JavaScript/AJAX rather than a plain HTML table — no stable endpoint was
found to scrape reliably. Rather than guess at a fragile scraper, we
pivoted to **Open-Meteo**, a free, no-auth weather API.

Uses `https://api.open-meteo.com/v1/forecast` with
`hourly=soil_temperature_6cm,soil_temperature_18cm`, then reduces to
daily minimum per depth in Python (to match the OSU app's "daily min"
convention, since Open-Meteo's daily aggregation only offers mean, not
min/max, for soil variables).

**Bug already caught and fixed once**: the first version of this used
`soil_temperature_0_to_7cm` / `soil_temperature_7_to_28cm` (depth-band
average variable names, pulled from archive-API examples found via web
search) instead of the correct `/v1/forecast` point-depth variable names
`soil_temperature_6cm` / `soil_temperature_18cm`. This was caught by the
user testing a real API call and pasting the response back — the wrong
names would have returned a KeyError on every fetch. Verified fixed and
tested against a real response as of the last update to this file. If
you're an agent continuing this work: don't reintroduce the
`_to_` band-name pattern for the `/v1/forecast` endpoint without
re-verifying against a live call first.

**Important caveat baked into the UI**: this is modeled/reanalysis data
(ECMWF-based), not a physical sensor. `soil_temperature_6cm` and
`soil_temperature_18cm` ARE real point-depth values (not band averages),
used as 5cm/10cm-equivalent fields respectively -- 6cm is close to the
5cm target, 18cm is a bigger jump from the 10cm target, worth keeping in
mind. Good for trend-tracking; not lab-grade.

Default coordinates are hardcoded to the city of Erie, PA generally —
see comments in `app.py` for more precise PEMN station coordinates if
needed.

### 3. `any_city/` — generalized version, any city

Same Open-Meteo approach as `erie_pa/`, but adds Open-Meteo's
**Geocoding API** (`https://geocoding-api.open-meteo.com/v1/search`) so
the user can type any city name, disambiguate via a dropdown if there
are multiple matches, and track that location. This is the most
flexible app and effectively supersedes `erie_pa/` — kept both since
`erie_pa/` is simpler/more focused if Erie is the only city that matters.

Each city's readings are stored under a `location_key` (Open-Meteo's
internal geocoding ID) in the same DuckDB file, so multiple cities can
be tracked without colliding. The last-searched city is remembered
across runs (stored in a `settings` table).

## Shared design decisions across all three apps

- **DuckDB** as local storage — single-file, no server, auto-creates
  schema on first run. Each app uses its own `.duckdb` file so they
  don't collide even run from sibling folders.
- **Streamlit** for the UI — each app is a single `app.py`, run with
  `streamlit run app.py`.
- Every app has:
  - A **Fall/Spring mode toggle** (radio button) that changes the
    threshold logic and status messages, sharing the same underlying
    data.
  - A **manual entry form** as a guaranteed-to-work fallback if any
    auto-fetch breaks.
  - An **auto-fetch by date range** control.
  - A **"Fill missing days"** button that checks the latest logged date
    and fetches only the gap through today, so daily use is a single
    click once history exists.
  - A **streak counter** (3 consecutive days) driving a status banner:
    "too early" / "getting close" / "ready to apply" (fall) or the
    additional spring states "above window, closing" / "germination
    likely" (spring).

## Things NOT yet done / possibly worth revisiting

- The `erie_pa/` and `any_city/` auto-fetch logic against
  `api.open-meteo.com` was originally written from search-derived
  documentation and had a real bug (wrong hourly variable names -- see
  the `erie_pa/` section above). It has since been verified against a
  live API response the user pasted back, with the parsing/aggregation
  logic tested against that real payload. The geocoding API call in
  `any_city/` is still unverified against a live response -- worth
  testing that specifically if issues come up there.
- No automated/scheduled fetching exists anywhere — every app requires
  a human to open it and click fetch/fill. A true "no-touch" version
  would need a cron job or scheduled task calling the fetch logic
  headlessly and probably writing to a shared alert (email/text).
- `columbus_oh/app.py`'s scraper is best-effort against OSU's current
  HTML structure — if OSU changes their page layout, the "Min Soil
  Temp 2\"" / "Min Soil Temp 4\"" column-matching logic will need
  updating.
- No tests exist beyond manual verification during the build. Consider
  adding basic unit tests around the parsing/aggregation functions
  (`fetch_osu_range`, `fetch_openmeteo_range`, `geocode_city`) if this
  project grows.
- `browser_artifact_reference.html` (at the project root) is the
  original in-browser manual-entry tracker built before the Streamlit
  apps existed. It's superseded by the Streamlit apps but kept for
  reference — it uses a `window.storage` API specific to the Claude.ai
  artifact environment and won't run standalone in a normal browser.

## Reference numbers used throughout

- Fall threshold: 70°F, 3 consecutive days, falling
- Spring window: 50–55°F, 3 consecutive days, rising; 55–60°F+ = window
  closing / germination underway
- OSU Columbus station ID: 14
- PEMN Erie-area station IDs: ERIE01 (PSU LERGREC), ERIE02 (Waterford
  Little League Fields) — not currently used programmatically, PEMN
  wasn't scrapable, but useful if PEMN ever exposes a better API
