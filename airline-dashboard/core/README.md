# core: shared SEC data pipeline

`sec_pipeline` is a small, importable Python package that consolidates the five
legacy scraping notebooks into one tested pipeline. It scrapes SEC EDGAR filings,
parses and chunks them, builds a local vector index, and generates period
insights with an LLM. It also extracts the auto-sourceable financial metrics from
XBRL company facts.

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
    xbrl.py          company facts -> four auto-sourced financial metrics
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
python .\airline-dashboard\core\scripts\build_data.py `
  --airlines AAL DAL UAL LUV ALK JBLU ULCC `
  --years 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 `
  --periods Q1 Q2 Q3 Q4 FY `
  --overwrite
```
For ```airlines```, ```years```, and ```periods``` choose any set of tickers, years, and periods separated by spaces. The ```--overwrite``` command is optional and if not passed will only fill for data not present.

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

## Metric sourcing

| Source | Metrics |
| --- | --- |
| Auto (XBRL company facts) | Operating Revenue, Operating Expenses, Net Income, Long-Term Debt |
| Manual sheet (`../data/manual/`) | RPM, ASM, Profit Sharing, buybacks and share sales |
| Derived (build_data) | Operating Income, margins, Load Factor, Yield, TRASM, PRASM, CASM |

RPM, ASM, and Profit Sharing are not part of the us-gaap XBRL taxonomy and must
be supplied manually.

## Tests

```powershell
cd core
pip install -e ".[dev]"
pytest
```

The suite covers chunking, HTML/PDF parsing, the `PeriodSpec` date model, and the
rate limiter. Network-dependent steps are exercised through the runner, not unit
tests.
