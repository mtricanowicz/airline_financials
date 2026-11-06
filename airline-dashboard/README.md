# Airline Financial Dashboard (v2)

A rebuild of the airline financial dashboard. The previous single-file
Streamlit application is preserved in `../legacy-archive/`; the active
Streamlit app and its shared data pipeline are in this folder.

## Architecture

The shared data core feeds the tracked Streamlit front end:

```
core/           Shared data core (build once, consume everywhere)
   sec_pipeline/   Python package: scrape SEC EDGAR -> weighted RAG -> LLM summaries
  scripts/        build_data.py: XBRL + manual sheet -> canonical JSON
  notebooks/      run_pipeline.ipynb: thin interactive runner
data/
  manual/         Small manual sheet (RPM, ASM, Profit Sharing, buybacks)
  generated/      Canonical JSON consumed by Streamlit
quotes-api/       Small FastAPI service for live stock closes (Cloud Run)
streamlit-app/    Multipage Streamlit app
deploy/           Dockerfile, Cloud Build config, CI/deploy workflows
```

The local Next.js/Firebase prototype is excluded from version control in
`.gitignore`, so it is not part of a clean checkout or the active deployment.
The deployment workflows conditionally build and deploy it only when its
`web/package-lock.json` is present.

### Data flow

1. `core/sec_pipeline` retrieves periodic SEC filings and material 8-K exhibits,
   builds embeddings, uses weighted multi-query RAG with dedicated material-event
   and forward-guidance recall channels, and writes `data/generated/insights.json`.
2. `core/scripts/build_data.py` merges auto-sourced XBRL financials with the
   manual sheet and writes `data/generated/financials.json`.
   It writes `data/generated/buybacks.json` only when `--share-data` is passed.
3. Streamlit reads the JSON in `data/generated/`. Live stock prices and
   historical closes come from `quotes-api`.

## Metric sourcing (hybrid)

| Source | Metrics |
|---|---|
| Auto (SEC XBRL `companyfacts`) | Operating Revenue, Operating Expenses, Net Income, Earnings Per Share, Long-Term Debt, Current Maturities, Cash & Cash Equivalents, Unrestricted Cash, Restricted Cash, Short-Term Investments, Interest Expense, Operating Cash Flow, Capital Expenditures |
| Auto (filing-level XBRL, opt-in) | Passenger Revenue and Cargo Revenue where a verified dimensional or historical mapping exists |
| Manual sheet | Passenger Revenue fallback, RPM, ASM, Profit Sharing, share repurchases, share sales |
| Derived (computed) | Operating Income, Operating/Net Margin, Load Factor, Yield, TRASM, PRASM, CASM, Total Debt, Total Liquidity, Net Debt, Free Cash Flow |

RPM, ASM, and Profit Sharing are not available in the XBRL financial taxonomy, so
they remain manual. Passenger and Cargo Revenue enrichment is enabled with
`--use-filing-parser`; the build step cross-checks manual financials against XBRL
and reports mismatches.

## Getting started

See `core/README.md` for the pipeline and data build, and
`streamlit-app/README.md` for the active front end.

## Security

Never commit secrets. Create `core/.env` with `SEC_USER_AGENT` and
`OPENAI_API_KEY` for SEC and insights pipeline runs. `.env` is gitignored.
