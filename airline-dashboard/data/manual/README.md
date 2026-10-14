# Manual data inputs

This folder holds the metrics that are not available in the SEC XBRL financial
taxonomy and therefore cannot be sourced automatically. `build_data.py` merges
these values with the auto-sourced financials to produce the canonical datasets.

> The CSV files checked in here were exported from `airline_financial_data.xlsx`
> and reflect figures compiled from each airline's 10-Q, 10-K, and 8-K filings.
> Update them as new filings are published.

## Accepted inputs

`build_data.py` prefers a single legacy-style workbook if present, otherwise it
reads the individual CSV files:

1. `airline_financial_data.xlsx` with sheets `airline_financials`,
   `share_repurchases`, and `share_sales`, or
2. `manual_metrics.csv`, `share_repurchases.csv`, and `share_sales.csv`.

Manual financial metrics are considered by default (`--sources auto manual`).
Use `--sources manual` to apply them separately without fetching SEC data, or
`--sources auto` to exclude them from a financial build.
`share_repurchases.csv` and `share_sales.csv` are written to
`data/generated/buybacks.json` only when `--share-data` is passed to
`core/scripts/build_data.py`.

Financial updates are scoped by `--airlines`, `--years`, and `--periods`.
Without `--overwrite`, manual values fill only missing/null stored metrics.
With it, populated supplied values replace stored values only within that
selection; blank cells do not erase existing values, and metrics absent from
the manual input remain unchanged. Derived metrics use the combined values.
The `--share-data` option remains a separate, full-history rebuild, regardless
of financial source selection or airline/year/period filters.

## Schemas

### manual_metrics.csv

| Column | Description |
| --- | --- |
| Airline | Ticker, e.g. `AAL` |
| Year | Fiscal year, e.g. `2024` |
| Quarter | `Q1`, `Q2`, `Q3`, `Q4`, or `FY` |
| Passenger Revenue | Passenger revenue in dollars (needed for Yield and PRASM) |
| RPM | Revenue passenger miles |
| ASM | Available seat miles |
| Profit Sharing | Profit sharing accrual in dollars |

A `Long-Term Debt` column may also be supplied here. When present it is compared
against the XBRL value and a mismatch beyond 2 percent is reported; the XBRL
value remains authoritative.

### share_repurchases.csv

| Column | Description |
| --- | --- |
| Airline | Ticker |
| Year | Fiscal year |
| Quarter | Period, typically `FY` |
| Shares Repurchased | Share count |
| Cost | Total cost in dollars |

### share_sales.csv

| Column | Description |
| --- | --- |
| Airline | Ticker |
| Year | Fiscal year |
| Quarter | Period, typically `FY` |
| Shares Sold | Share count |
| Proceeds | Total proceeds in dollars |

## Metric sourcing summary

| Source | Metrics |
| --- | --- |
| Auto (XBRL company facts) | Operating Revenue, Operating Expenses, Net Income, Earnings Per Share, Long-Term Debt, Current Maturities, Cash & Cash Equivalents, Unrestricted Cash, Restricted Cash, Short-Term Investments, Operating Cash Flow, Capital Expenditures |
| Auto (filing parser, opt-in via `--use-filing-parser`) | Passenger Revenue and Cargo Revenue where a verified current or historical XBRL mapping exists; Cargo Revenue has no manual fallback -- see `core/sec_pipeline/filing_parser.py` |
| Manual (this folder) | Passenger Revenue (fallback), RPM, ASM, Profit Sharing, buybacks, share sales |
| Derived (build_data) | Operating Income, Operating Margin, Net Margin, Load Factor, Yield, TRASM, PRASM, CASM, Total Debt, Total Liquidity, Net Debt, Free Cash Flow |
