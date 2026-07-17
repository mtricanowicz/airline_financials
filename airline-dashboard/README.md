# Airline Financial Dashboard (v2)

A self-contained rebuild of the airline financial dashboard. This folder is
independent of the legacy Streamlit application at the repository root and can be
developed, tested, and deployed on its own.

## Architecture

A single shared data core feeds two independent front ends:

```
core/           Shared data core (build once, consume everywhere)
  sec_pipeline/   Python package: scrape SEC EDGAR -> RAG -> LLM summaries
  scripts/        build_data.py: XBRL + manual sheet -> canonical JSON
  notebooks/      run_pipeline.ipynb: thin interactive runner
data/
  manual/         Small manual sheet (RPM, ASM, Profit Sharing, buybacks)
  generated/      Canonical JSON consumed by both front ends
quotes-api/       Small FastAPI service for live stock closes (Cloud Run)
streamlit-app/    Track A: modernized multipage Streamlit app
web/              Track B: Next.js static site (primary front end)
deploy/           Dockerfiles, Firebase config, CI workflows
```

### Data flow

1. `core/sec_pipeline` retrieves SEC filings, builds embeddings, runs RAG, and
   writes `data/generated/insights.json`.
2. `core/scripts/build_data.py` merges auto-sourced XBRL financials with the
   manual sheet and writes `data/generated/financials.json` and
   `data/generated/buybacks.json`.
3. Both front ends read the JSON in `data/generated/`. Live stock closes come
   from `quotes-api`.

## Metric sourcing (hybrid)

| Source | Metrics |
|---|---|
| Auto (SEC XBRL `companyfacts`) | Operating Revenue, Operating Expenses, Net Income, Long-Term Debt |
| Manual sheet | RPM, ASM, Profit Sharing, share repurchases, share sales |
| Derived (computed) | Operating Income, Operating/Net Margin, Load Factor, Yield, TRASM, PRASM, CASM |

RPM, ASM, and Profit Sharing are not available in the XBRL financial taxonomy, so
they remain manual. The build step cross-checks manual financials against XBRL
and reports mismatches.

## Getting started

See `core/README.md` for the pipeline and data build, `streamlit-app/README.md`
for Track A, and `web/README.md` for Track B.

## Security

Never commit secrets. Copy `core/.env.example` to `core/.env` and set values
there. `.env` is gitignored.
