# Airline Financial Dashboard (v2)
Compare financial and operating metrics for major US airlines.
Live app: https://airline.industryfinancials.com/

## Overview
This repository now centers on the v2 platform under [airline-dashboard](airline-dashboard), which separates data generation, APIs, and front ends into maintainable components.

Financial statement series in the generated dataset starts in 2014, which reflects the post legacy airline consolidation era for major US carriers. Share repurchase history can include earlier periods from manual files to fully cover the 2010s share buyback programs. The current v2 supports the tickers for all of the publicly traded US passenger airlines that were active since 2014, whether currently active or defunct, separated by scale:
- Major Global Airlines
    - AAL
    - DAL
    - UAL
- Large National Airlines
    - LUV
- Small and Midsize Airlines
    - ALGT
    - ALK
    - _HA (defunct)_
    - JBLU
    - _SAVE (defunct)_
    - _SNCY (defunct)_
    - ULCC
    - _VA (defunct)_
- Regional Airlines
    - RJET
    - SKYW

Unless noted, metrics are sourced or derived from SEC filings (10-Q, 8-K, 10-K), with specific operational metrics maintained in a manual sheet and merged in the core data pipeline.

## Architecture
The v2 stack is organized as:
- [airline-dashboard/core](airline-dashboard/core): shared Python data and insights pipeline
- [airline-dashboard/quotes-api](airline-dashboard/quotes-api): FastAPI service for live quote data
- [airline-dashboard/streamlit-app](airline-dashboard/streamlit-app): Primary app entry point Streamlit front end UI
- [airline-dashboard/web](airline-dashboard/web): Next.js web front end (in development target end state UI)
- [airline-dashboard/data](airline-dashboard/data): shared manual and generated data
- [airline-dashboard/deploy](airline-dashboard/deploy): deployment configs and runbooks

Data flow summary:
1. Core pipeline generates canonical JSON in `airline-dashboard/data/generated`.
2. Both front ends read the generated JSON.
3. Live quote views call `quotes-api`.

## Filtered Comparisons
Filtered Comparisons remains a core feature in v2 and supports:
- selecting airlines
- selecting year/period windows
- selecting metric groups or custom metric sets
- viewing tables and trend charts

The v2 implementation moves data prep out of UI runtime and relies on precomputed datasets, which improves performance and reduces rerun overhead.

## Latest Results
Latest Results continues to provide period snapshots for annual and quarterly views, with optional airline-to-airline comparison. In v2 this view is backed by generated JSON rather than in-app spreadsheet transformations.

## Share Repurchases
Share Repurchases is preserved in v2 with the same intent:
- repurchase history
- share sales history
- running net gain/loss views based on market prices

Source data remains curated from filings and merged into generated outputs by the core build process.

## Insights
Insights in v2 are generated through the consolidated SEC pipeline package in [airline-dashboard/core/sec_pipeline](airline-dashboard/core/sec_pipeline):
- SEC EDGAR retrieval
- filing parsing/chunking
- embedding and retrieval
- LLM summarization by airline/year/period

Outputs are written to generated JSON and served to front ends as precomputed content.

## Metric sourcing model
v2 uses a hybrid model:
- Auto (XBRL/company facts): Operating Revenue, Operating Expenses, Net Income, Earnings Per Share, Long-Term Debt, Current Maturities, Cash & Cash Equivalents, Unrestricted Cash, Restricted Cash, Short-Term Investments, Operating Cash Flow, Capital Expenditures
- Manual sheet: Passenger Revenue, RPM, ASM, Profit Sharing, buybacks, share sales
- Derived: Operating Income, margins, Load Factor, Yield, TRASM, PRASM, CASM, Total Debt, Total Liquidity, Net Debt, Free Cash Flow

## Deployment
Current production deployment is based on the v2 components:
- Cloud Run for `quotes-api`
- Cloud Run for `streamlit-app`
- GitHub Actions workflows in [.github/workflows](.github/workflows) for CI, deploy, and data refresh automation

For operational details, see [airline-dashboard/deploy/README.md](airline-dashboard/deploy/README.md).

## Legacy archive
Legacy root-level app assets have been archived for reference in [legacy-archive](legacy-archive).

These files are not the active v2 deployment path.

## Repo guides
Start here for component-level documentation:
- [airline-dashboard/README.md](airline-dashboard/README.md)
- [airline-dashboard/core/README.md](airline-dashboard/core/README.md)
- [airline-dashboard/streamlit-app/README.md](airline-dashboard/streamlit-app/README.md)
- [airline-dashboard/web/README.md](airline-dashboard/web/README.md)
- [airline-dashboard/deploy/README.md](airline-dashboard/deploy/README.md)

## Sources
- SEC EDGAR: https://www.sec.gov/search-filings/
- AAL:  https://americanairlines.gcs-web.com/
- DAL:  https://ir.delta.com/
- UAL:  https://ir.united.com/
- LUV:  https://www.southwestairlinesinvestorrelations.com/
- ALGT: https://ir.allegiantair.com/
- ALK:  https://investor.alaskaair.com/
- JBLU: https://www.investor.jetblue.com/
- ULCC: https://ir.flyfrontier.com/
- RJET: https://investor.rjet.com/
- SKYW: https://inc.skywest.com/


<br>**Created by Michael Tricanowicz**