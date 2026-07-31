# core: shared SEC data pipeline

`sec_pipeline` is a small, importable Python package that consolidates the five
legacy scraping notebooks into one tested pipeline. It scrapes SEC EDGAR filings,
parses and chunks them, builds a local vector index, and generates period
insights with an LLM. It also extracts the auto-sourceable financial metrics from
XBRL company facts, including liquidity and cash flow tags plus an EPS fallback
for Q4 when needed.

Both front ends (the Streamlit cleanup track and the Next.js track) consume the
JSON this package writes to `../data/generated/`.

## Layout

```
core/
  sec_pipeline/
    config.py        paths, environment settings, the PeriodSpec model
    edgar_client.py  rate-limited, cached SEC EDGAR REST client
    parse.py         HTML/PDF filing -> clean text
    chunk.py         text -> overlapping chunks
    embed.py         embeddings + Chroma vector store (no LangChain)
    summarize.py     retrieval + OpenAI summarization of a period
    xbrl.py          company facts -> auto-sourced financial metrics
    pipeline.py      orchestrator (scrape -> chunk -> embed -> summarize)
  notebooks/
    run_pipeline.ipynb  thin runner for interactive use
  tests/             pytest suite for the deterministic parts
  scripts/           build_data.py (Phase 2) and other entry points
```

## Setup

```powershell
cd core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .            # add ".[local-embeddings]" for offline embeddings
copy .env.example .env      # then fill in SEC_USER_AGENT and OPENAI_API_KEY
```

All secrets are read from `core/.env`, which is git-ignored. Never commit
credentials.

## Running

### Build Data (financials.json & buybacks.json)

```powershell
python .\scripts\build_data.py `
  --airlines AAL DAL UAL LUV ALK JBLU ULCC `
  --years 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 `
  --periods Q1 Q2 Q3 Q4 FY `
  --overwrite
```
For `airlines`, `years`, and `periods` choose any set of tickers, years, and periods separated by spaces.
`--overwrite` is optional and, if omitted, the build merges only the requested key slice.
`--share-data` is optional and, if passed, writes the full static buybacks/share-sales history to `../data/generated/buybacks.json`.

### SEC Pipeline (insights.json)

Command line:

```powershell
sec-pipeline --airlines AAL UAL --years 2023 2024 --periods Q1 Q2 Q3 Q4 FY
```

Python:

```python
from sec_pipeline.pipeline import run
run(airlines=["AAL", "UAL"], years=[2024], periods=["Q2"])
```

Output is written incrementally to `../data/generated/insights.json` shaped as
`{airline: {year: {period: markdown}}}`. Runs are idempotent: already-summarized
periods are skipped unless `--overwrite` is passed.

## Embedding backends

`EMBEDDING_BACKEND=local` (default) uses `sentence-transformers` and requires no
API calls. `EMBEDDING_BACKEND=openai` uses the OpenAI embeddings API. The chat
summarization step always uses OpenAI.

## XBRL period matching behavior

Auto-metric extraction uses a two-stage period matcher:

1. Calendar window matching (existing behavior): select facts by expected year/end-month and duration window.
2. FP fallback matching (default on): if no value is found in stage 1, retry using SEC fiscal-period labels (`fp`) for the requested period in the same year.

This improves coverage for filers whose quarter boundaries do not align cleanly to calendar quarter months.

Environment switches:

| Variable | Default | Effect |
| --- | --- | --- |
| `XBRL_ENABLE_FP_FALLBACK` | `true` | Enables the stage-2 `fp` fallback when calendar matching misses. Set to `false` to preserve strict calendar-only extraction. |
| `DIAGNOSTICS_EXCLUDE_FUTURE_PERIODS` | `true` | In coverage diagnostics, excludes tail periods beyond the latest available row per airline (reduces not-yet-filed noise). Set to `false` to score every requested period strictly. |

## Metric sourcing

| Source | Metrics |
| --- | --- |
| Auto (XBRL company facts) | Operating Revenue, Operating Expenses, Net Income, Earnings Per Share, Long-Term Debt, Current Maturities, Cash & Cash Equivalents, Unrestricted Cash, Restricted Cash, Short-Term Investments, Operating Cash Flow, Capital Expenditures |
| Manual sheet (`../data/manual/`) | Passenger Revenue, RPM, ASM, Profit Sharing, buybacks and share sales |
| Derived (build_data) | Operating Income, margins, Load Factor, Yield, TRASM, PRASM, CASM, Total Debt, Total Liquidity, Net Debt, Free Cash Flow |

RPM, ASM, and Profit Sharing are not part of the us-gaap XBRL taxonomy and must
be supplied manually.

## Diagnostics output

Each `build_data.py` run writes coverage diagnostics for the requested run slice to:

- `../data/generated/diagnostics/coverage_summary.csv`
- `../data/generated/diagnostics/coverage_detail.csv`
- `../data/generated/diagnostics/coverage_report.json`

By default, diagnostics suppress future not-yet-filed tail periods per airline. Disable that with `DIAGNOSTICS_EXCLUDE_FUTURE_PERIODS=false`.

## Tests

```powershell
cd core
pip install -e ".[dev]"
pytest
```

The suite covers chunking, HTML/PDF parsing, the `PeriodSpec` date model, and the
rate limiter. Network-dependent steps are exercised through the runner, not unit
tests.
