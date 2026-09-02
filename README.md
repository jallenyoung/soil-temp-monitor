# Pre-Emergent Soil Temp Tracker

Three Streamlit + DuckDB apps for timing lawn pre-emergent applications
by soil temperature trend rather than calendar date.

**Start here if you're an AI agent picking this up: read `CONTEXT.md`
first.** It has the full history of decisions, known issues, and design
rationale so you don't have to re-derive them.

## Apps

| Folder | Covers | Data source |
|---|---|---|
| `columbus_oh/` | Columbus, OH area | Real OSU CFAES station (scraped) |
| `erie_pa/` | Erie, PA area | Open-Meteo modeled estimate |
| `any_city/` | Any city, worldwide | Open-Meteo modeled estimate + geocoding |

Each folder is self-contained: its own `app.py`, `requirements.txt`, and
`README.md` with setup/run instructions. Each keeps its own local DuckDB
file, so running more than one doesn't cause conflicts.

## Quick start (any app)

```bash
cd <folder>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Also included

`browser_artifact_reference.html` — the original in-chat manual-entry
tracker built before these Streamlit apps existed. Superseded, kept for
reference only. It depends on a `window.storage` API specific to the
Claude.ai artifact environment and will not function if opened as a
plain local HTML file.
