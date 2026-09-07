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
  --airlines AAL DAL UAL LUV ALK JBLU ULCC ALGT RJET SKYW `
  --years 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 `
  --periods Q1 Q2 Q3 Q4 FY `
  --use-filing-parser `
  --overwrite
```
For `airlines`, `years`, and `periods` choose any set of tickers, years, and periods separated by spaces.
`--overwrite` is optional and, if omitted, the build merges only the requested key slice.
`--share-data` is optional and, if passed, writes the full static buybacks/share-sales history to `../data/generated/buybacks.json`.
`--use-filing-parser` is optional and, if passed, additionally fetches Passenger Revenue and Cargo Revenue via per-filing XBRL parsing (`sec_pipeline/filing_parser.py`) for tickers with a verified current or historical mapping. This is expensive (one filing fetch per ticker per quarter/year, versus one company-facts call per ticker without it) and is off by default. Passenger Revenue remains eligible to fall back to the manual sheet; Cargo Revenue has no manual fallback.

The default airline list is the current refresh set. For a development historical backfill, explicitly include former issuers such as `HA`, `SAVE`, `SNCY`, and `VA` in `--airlines`; their absence from the default does not remove existing generated records.

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
API calls. For generation runs, set `EMBEDDING_BACKEND=openai` to use the OpenAI
embeddings API and improve retrieval consistency with the hosted summarization
model. The chat summarization step always uses OpenAI. Keep the local default for
tests and offline development.

## SEC Retrieval and Summarization

The insights pipeline uses a retrieval-augmented generation (RAG) flow:

1. Retrieve the relevant 10-Q, 10-K, and 8-K filings for an airline-period.
2. For each 8-K, retrieve material `EX-99.*` HTML/PDF attachments, including
  earnings releases and investor presentations when present.
3. Parse each filing and selected exhibit into cleaned text and overlapping chunks.
4. Store chunk embeddings and deterministic provenance metadata in Chroma.
5. Run several topic-focused retrieval queries against the collection.
6. Fuse the query results, remove redundant chunks, and assemble a bounded context.
7. Ask the summarization model to select and explain the material developments.

The 8-K cover document is often only an incorporation-by-reference notice. The
attached `EX-99.1` earnings release commonly contains the actual quarterly
discussion, tables, and management guidance, so indexing only the primary 8-K
would leave that material out of retrieval entirely. The exhibit collector admits
only `EX-99.*` HTML/PDF attachments; it skips graphics, XBRL linkbases, extracted
instance XML, and the complete-submission text file.

### Retrieval queries and weights

Queries cover the period overview, financial results, operations, labor, executive
and board activity, route network, commercial strategy, MD&A explanations, unit
economics, fuel, non-GAAP results, legal/risk disclosures, material 8-K events,
and management forward guidance. The material 8-K query is a recall channel for
period-specific events that may not be adequately represented in a 10-Q. The
guidance query targets earnings-release outlooks for the next quarter or full
year. Neither query requires an 8-K item in the final summary.

Each query has a modest priority weight in `sec_pipeline.summarize.QUERY_WEIGHTS`.
The weights affect retrieval ordering only. They do not force a topic into the
output, and they do not override the model's evidence and materiality rules.
The current priorities are:

| Query family | Weight |
| --- | ---: |
| Broad period overview | 0.95 |
| Financial results | 1.00 |
| Capacity, traffic, and fleet | 0.90 |
| Labor | 0.75 |
| Executive and board | 0.45 |
| Route network | 0.95 |
| Commercial strategy and loyalty | 0.90 |
| MD&A causes and offsets | 1.15 |
| Unit economics | 0.95 |
| Fuel | 1.00 |
| Non-GAAP and special items | 0.80 |
| Risk and legal | 0.65 |
| Material 8-K developments | 1.05 |
| Earnings-release guidance and outlook | 1.15 |

### Reciprocal-rank fusion

The same chunk may be returned by multiple queries. Rather than discarding later
matches, the retriever treats repeated discovery as evidence that the passage is
relevant. For a passage `p`, the fused retrieval score is:

$$
S(p) = \sum_{q \in Q_p}
\frac{w_q}{k + r_{p,q}}
$$

where:

- $Q_p$ is the set of queries that returned passage $p$;
- $w_q$ is the configured weight for query $q$;
- $r_{p,q}$ is the zero-based rank of the passage for query $q$;
- $k=60$ is a smoothing constant that prevents rank-zero results from dominating.

Higher scores therefore come from passages that rank well and are supported by
multiple query families. If no weights are supplied by a caller, every query uses
a default weight of `1.0`.

### Passage provenance and deduplication

Every indexed chunk retains deterministic metadata:

- `form`, `accession`, and `filing_date`: filing provenance;
- `source_id`: stable form/accession identity, with an `:EX-99.1` suffix for an
  exhibit so it remains distinguishable from its 8-K cover filing;
- `document_name` and `exhibit_type`: the source filename and `EX-99.*` type;
- `reporting_period`: the requested airline-period, such as `2020Q2`;
- `chunk_index` and `chunk_count`: position within the source filing.

Exact duplicates are keyed by source identity plus normalized text, so identical
language in two filings remains separately attributable. Near-duplicate chunks are
merged only when they come from the same source and have adjacent chunk positions.
This avoids collapsing similar language from different filings while reducing the
effect of overlapping chunk windows within one filing.

Retrieved metadata also records `query_index`, `query_rank`, `query_support`,
`query_indices`, and `retrieval_score`. These fields are internal retrieval
provenance and are not written into the user-facing summary.

### Context assembly

The context builder orders passages by fused retrieval score. Core evidence channels
can contribute multiple passages; secondary channels are limited to one
representative passage so the context does not become a checklist of every topic.
The material 8-K and guidance queries are core channels. Before the general pass,
the builder reserves up to two top-ranked guidance-query passages so detailed
historical financial results cannot crowd management outlook out of the bounded
context. This is targeted recall, not a general form-level preference for 8-Ks;
10-Q and 10-K passages continue to compete by relevance and multi-query support.
The assembled context is bounded by `MAX_CONTEXT_TOKENS` in `summarize.py`.

### Summary selection contract

The model is instructed to produce a useful, relatively complete picture rather
than a fixed number of items. It should merge related facts into business stories,
preserve exact population scope, distinguish quarterly from year-to-date figures,
and assign each story to its primary business section. A figure or named specific
supports specificity but is not by itself sufficient reason to include an item.

The Wrap Up is intentionally self-contained so a reader can understand the central
developments and tension without reading every numbered item. It first recaps the
numbered stories in compressed form. When retrieved excerpts contain management
guidance, it then adds a concise, clearly labeled overview that names the guided
period and the most decision-relevant ranges, targets, or assumptions. Guidance is
explicitly distinguished from reported results and must not replace the recap.

### Completion-length safeguard

The summarizer checks the OpenAI completion `finish_reason` before returning text.
When the initial response ends with `"length"`, it reuses the same retrieved
context once with a compact drafting instruction: no more than eight numbered
items, aggressively merged facts, and a complete concise Wrap Up. A second
length-limited response raises an error and is not persisted, preventing an
incomplete summary from silently overwriting an existing result.

### Filing windows

`PeriodSpec` distinguishes the actual reporting end from the later filing cutoff
used for retrieval. Q1-Q3 filing windows extend roughly one month after period
end. Q4 begins on October 1 and, like FY, extends through March 31 of the next
year so the annual 10-K is available. The prompt and retrieval queries use the
actual reporting end, such as December 31, rather than the padded filing cutoff.
The Q4 window intentionally overlaps October current reports; those filings may
provide relevant context, while the 10-K supplies year-end and fourth-quarter data.

### Summary quality checks

`lint-summaries` measures generated markdown before and after retrieval/prompt
changes. It reports per-summary and aggregate word/item counts, figure density,
banned model-voice phrases, bold/body overlap, causal-attribution signals,
truncation, repeated metric families, Wrap Up figure reuse, and cross-summary
four-gram reuse. Use `--baseline` plus `--compare` for aggregate deltas and
`--discover` to list repeated openers and phrases. These are review signals, not
proof of factual accuracy; in particular, the causal-attribution metric is lexical.

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
| Filing-level XBRL (`--use-filing-parser`) | Passenger Revenue and Cargo Revenue where a verified current or historical mapping exists |
| Manual sheet (`../data/manual/`) | Passenger Revenue fallback, RPM, ASM, Profit Sharing, buybacks and share sales |
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
