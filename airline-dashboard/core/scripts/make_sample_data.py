"""Generate small illustrative datasets for front-end development.

This does not touch the network. It combines the manual CSVs with a handful of
placeholder auto-metric values and runs the same merge and derive logic as the
real build, then writes ``financials.json``, ``buybacks.json``, and a minimal
``insights.json`` into ``data/generated/``. Use it to run either front end
before the full pipeline has been executed. The auto values are illustrative and
must not be treated as real financials.
"""

from __future__ import annotations

import json

import pandas as pd

from sec_pipeline import config
from scripts.build_data import (
    BUYBACKS_PATH,
    FINANCIALS_PATH,
    add_derived,
    build_buybacks,
    load_manual,
    merge_sources,
)

# Illustrative auto metrics (dollars) keyed by (Airline, Year, Quarter).
_SAMPLE_AUTO = [
    ("AAL", 2024, "FY", 54_000_000_000, 51_000_000_000, 850_000_000, 30_000_000_000),
    ("UAL", 2024, "FY", 57_000_000_000, 52_500_000_000, 2_600_000_000, 28_000_000_000),
    ("AAL", 2024, "Q2", 14_300_000_000, 13_100_000_000, 720_000_000, 30_500_000_000),
    ("UAL", 2024, "Q2", 15_000_000_000, 13_600_000_000, 1_320_000_000, 28_300_000_000),
]


def sample_auto() -> pd.DataFrame:
    cols = ["Airline", "Year", "Quarter", "Operating Revenue", "Operating Expenses", "Net Income", "Long-Term Debt"]
    return pd.DataFrame(_SAMPLE_AUTO, columns=cols)


def main() -> None:
    manual_metrics, repurchases, sales = load_manual()
    merged = add_derived(merge_sources(sample_auto(), manual_metrics))
    drop = [c for c in merged.columns if c.endswith("_manual")]
    merged = merged.drop(columns=drop).sort_values(["Airline", "Year", "Quarter"])

    FINANCIALS_PATH.write_text(
        json.dumps(json.loads(merged.astype(object).where(pd.notna(merged), None).to_json(orient="records")), indent=2),
        encoding="utf-8",
    )
    BUYBACKS_PATH.write_text(json.dumps(build_buybacks(repurchases, sales), indent=2), encoding="utf-8")

    insights = {
        "AAL": {"2024": {"Q2": "### Financial Insights\n1. Sample insight for AAL 2024 Q2.\n\n### Operational Insights\n1. Sample operational note.\n\n### Commercial Strategy Insights\n1. Sample strategy note."}},
        "UAL": {"2024": {"Q2": "### Financial Insights\n1. Sample insight for UAL 2024 Q2.\n\n### Operational Insights\n1. Sample operational note.\n\n### Commercial Strategy Insights\n1. Sample strategy note."}},
    }
    config.SUMMARIES_PATH.write_text(json.dumps(insights, indent=2), encoding="utf-8")

    print(f"Wrote sample data to {config.GENERATED_DIR}")


if __name__ == "__main__":
    main()
