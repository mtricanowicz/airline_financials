# streamlit-app (Track A: cleanup)

A faithful, faster rebuild of the original single-file Streamlit dashboard. It is
the reference and fallback front end. The primary front end is the Next.js app in
[`../web`](../web).

## What changed from the original

- Each former tab is now a separate page under [`views/`](views), registered
  through `st.navigation` in [`app.py`](app.py). Navigating between pages no
  longer re-executes the others.
- The manual `st.rerun`, `apply_filters`, and `rerun_count` session-state
  workarounds are gone. State is derived directly from widgets.
- All data is read from the precomputed JSON in `../data/generated/` behind
  `@st.cache_data`. The app never scrapes or recomputes at request time.
- Live stock prices come from the separate [`../quotes-api`](../quotes-api)
  service rather than an in-process download.

## Pages

| Page | Source | Description |
| --- | --- | --- |
| Filtered Comparisons | `views/comparisons.py` | Compare metrics across airlines and periods with tables and charts. |
| Latest Results | `views/latest_results.py` | Most recent full-year and quarterly figures. |
| Share Repurchases | `views/share_repurchases.py` | Buyback and share-sale history with net value at the latest close. |
| Insights | `views/insights.py` | Precomputed LLM insights per airline, year, and period. |

## Run locally

First generate the data (from `../core`), then:

```powershell
cd streamlit-app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `DASHBOARD_DATA_DIR` | `../data/generated` | Directory containing `financials.json`, `buybacks.json`, `insights.json`. |
| `QUOTES_API_URL` | `http://localhost:8080` | Base URL of the quotes-api service. |

## Container

```powershell
# Build from the airline-dashboard root so the generated data is in context.
docker build -f streamlit-app/Dockerfile -t airline-streamlit .
docker run -p 8080:8080 -e QUOTES_API_URL=https://quotes.example.run.app airline-streamlit
```
