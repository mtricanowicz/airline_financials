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
| Auto (XBRL) | Operating Revenue, Operating Expenses, Net Income, Long-Term Debt |
| Manual (this folder) | Passenger Revenue, RPM, ASM, Profit Sharing, buybacks, share sales |
| Derived (build_data) | Operating Income, Operating Margin, Net Margin, Load Factor, Yield, TRASM, PRASM, CASM |
