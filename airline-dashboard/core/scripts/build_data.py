"""Build the canonical dashboard datasets consumed by both front ends.

Combines three sources:

* Auto (SEC XBRL company facts): Operating Revenue, Operating Expenses,
  Net Income, Long-Term Debt.
* Filing parser (SEC XBRL instance documents, opt-in via --use-filing-parser):
  Passenger Revenue and Cargo Revenue for tickers with a verified dimensional
  mapping (see sec_pipeline.filing_parser). Expensive -- one filing fetch per
  ticker per quarter/year -- so it is not run by default.
* Manual sheet (``data/manual/``): Passenger Revenue, RPM, ASM, Profit Sharing,
  and the share repurchase / share sale history.
* Derived (here): margins, Load Factor, Yield, TRASM, PRASM,
  CASM.

Outputs to ``data/generated/``:

* ``financials.json`` - one record per airline / year / period with every metric.
* ``buybacks.json``   - share repurchase and share sale history with derived columns.

Where the manual sheet also carries one of the four auto metrics, a mismatch
beyond a relative tolerance is reported so the sources can be reconciled.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from sec_pipeline import config, filing_parser
from sec_pipeline.edgar_client import EdgarClient
from sec_pipeline.xbrl import PASSENGER_REVENUE_LEGACY_CUTOFF_YEAR, extract_financials

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_data")

AUTO_METRICS = [
    "Operating Revenue",
    "Operating Expenses",
    "Operating Income",
    "Net Income",
    "Earnings Per Share",
    "Long-Term Debt",
    "Current Maturities",
    "Cash & Cash Equivalents",
    "Short-Term Investments",
    "Interest Expense",
    "Operating Cash Flow",
    "Capital Expenditures",
]
MANUAL_METRICS = ["Passenger Revenue", "RPM", "ASM", "Profit Sharing"]
# Sourced by sec_pipeline.filing_parser (opt-in, see --use-filing-parser).
# Passenger Revenue overlaps with MANUAL_METRICS as a gap-filler; Cargo
# Revenue has no manual fallback at all.
FILING_PARSER_METRICS = ["Passenger Revenue", "Cargo Revenue"]
MISMATCH_TOLERANCE = 0.02  # 2% relative difference

FINANCIALS_PATH = config.GENERATED_DIR / "financials.json"
BUYBACKS_PATH = config.GENERATED_DIR / "buybacks.json"
DIAGNOSTICS_DIR = config.GENERATED_DIR / "diagnostics"
DIAGNOSTICS_SUMMARY_CSV = DIAGNOSTICS_DIR / "coverage_summary.csv"
DIAGNOSTICS_DETAIL_CSV = DIAGNOSTICS_DIR / "coverage_detail.csv"
DIAGNOSTICS_REPORT_JSON = DIAGNOSTICS_DIR / "coverage_report.json"

MANUAL_XLSX = config.MANUAL_DIR / "airline_financial_data.xlsx"
MANUAL_METRICS_CSV = config.MANUAL_DIR / "manual_metrics.csv"
REPURCHASES_CSV = config.MANUAL_DIR / "share_repurchases.csv"
SHARE_SALES_CSV = config.MANUAL_DIR / "share_sales.csv"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _normalize_quarter(value: Any) -> str:
    s = str(value).strip().upper()
    if s in {"FY", "Q1", "Q2", "Q3", "Q4"}:
        return s
    return f"Q{s}" if s.isdigit() else s


def load_manual() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load manual metrics, repurchases, and share sales.

    Prefers a single multi-sheet ``airline_financial_data.xlsx`` (legacy shape),
    otherwise falls back to individual CSV files. Missing sources yield empty
    frames so the build can still run on auto data alone.
    """
    if MANUAL_XLSX.exists():
        sheets = pd.read_excel(MANUAL_XLSX, sheet_name=None)
        metrics = sheets.get("airline_financials", pd.DataFrame())
        repurchases = sheets.get("share_repurchases", pd.DataFrame())
        sales = sheets.get("share_sales", pd.DataFrame())
    else:
        metrics = pd.read_csv(MANUAL_METRICS_CSV) if MANUAL_METRICS_CSV.exists() else pd.DataFrame()
        repurchases = pd.read_csv(REPURCHASES_CSV) if REPURCHASES_CSV.exists() else pd.DataFrame()
        sales = pd.read_csv(SHARE_SALES_CSV) if SHARE_SALES_CSV.exists() else pd.DataFrame()

    for frame in (metrics, repurchases, sales):
        if not frame.empty and "Quarter" in frame.columns:
            frame["Quarter"] = frame["Quarter"].apply(_normalize_quarter)
    return metrics, repurchases, sales


def load_auto(airlines: list[str], years: list[int], periods: list[str]) -> pd.DataFrame:
    """Fetch XBRL company facts and extract the auto metrics per airline."""
    client = EdgarClient()
    ciks = client.resolve_ciks(airlines)
    rows: list[dict[str, Any]] = []
    for airline in airlines:
        try:
            facts = client.company_facts(ciks[airline])
        except Exception as exc:  # noqa: BLE001
            log.error("Could not fetch company facts for %s: %s", airline, exc)
            continue
        for rec in extract_financials(facts, years, periods, ticker=airline):
            rec["Airline"] = airline
            rows.append(rec)
    return pd.DataFrame(rows)


def load_filing_parser(airlines: list[str], years: list[int], periods: list[str]) -> pd.DataFrame:
    """Passenger/Cargo Revenue via per-filing dimensional XBRL parsing.

    Expensive (one filing fetch per ticker per quarter/year) -- only called
    when --use-filing-parser is passed. Only covers tickers with a verified
    dimensional mapping and years after the legacy-tag cutoff; everything
    else is left for load_auto/manual to fill as before.
    """
    applicable = [
        a
        for a in airlines
        if a in filing_parser.PASSENGER_REVENUE_DIMENSIONAL_MAP
        or a in filing_parser.CARGO_REVENUE_DIMENSIONAL_MAP
    ]
    eligible_years = [y for y in years if y >= 2018]
    if not applicable or not eligible_years:
        return pd.DataFrame()

    client = EdgarClient()
    ciks = client.resolve_ciks(applicable)
    rows: list[dict[str, Any]] = []
    for airline in applicable:
        for year in eligible_years:
            try:
                year_metrics = filing_parser.extract_year_metrics(client, ciks[airline], airline, year)
            except Exception as exc:  # noqa: BLE001
                log.error("Filing-parser extraction failed for %s %s: %s", airline, year, exc)
                continue
            for period in periods:
                vals = year_metrics.get(period)
                if not vals or all(v is None for v in vals.values()):
                    continue
                rows.append({"Airline": airline, "Year": year, "Quarter": period, **vals})
    return pd.DataFrame(rows)


def _overlay_filing_parser(auto: pd.DataFrame, filing_parser_df: pd.DataFrame) -> pd.DataFrame:
    """Fill Passenger/Cargo Revenue gaps from filing-parser results.

    Both metrics can now come from either source: xbrl.py's legacy tags
    (years <= 2017) or the filing-parser dimensional tier (years >= 2018),
    so both need the same fillna-merge treatment.
    """
    if filing_parser_df.empty:
        return auto
    if auto.empty:
        return filing_parser_df

    keys = ["Airline", "Year", "Quarter"]
    merged = auto.merge(filing_parser_df, on=keys, how="outer", suffixes=("", "_fp"))
    for metric in FILING_PARSER_METRICS:
        fp_col = f"{metric}_fp"
        if fp_col in merged.columns:
            merged[metric] = merged[metric].fillna(merged[fp_col])
            merged = merged.drop(columns=[fp_col])

    for _, rows in merged.groupby(["Airline", "Year"]):
        by_quarter = {merged.at[index, "Quarter"]: index for index in rows.index}
        q4_index = by_quarter.get("Q4")
        if q4_index is None or pd.notna(merged.at[q4_index, "Cargo Revenue"]):
            continue
        component_indexes = [by_quarter.get(period) for period in ("FY", "Q1", "Q2", "Q3")]
        if any(index is None for index in component_indexes):
            continue
        fy_index, q1_index, q2_index, q3_index = component_indexes
        values = [merged.at[index, "Cargo Revenue"] for index in component_indexes]
        if all(pd.notna(value) for value in values):
            merged.at[q4_index, "Cargo Revenue"] = (
                merged.at[fy_index, "Cargo Revenue"]
                - merged.at[q1_index, "Cargo Revenue"]
                - merged.at[q2_index, "Cargo Revenue"]
                - merged.at[q3_index, "Cargo Revenue"]
            )
    return merged


def _scope_frame(
    df: pd.DataFrame,
    airlines: list[str],
    years: list[int],
    periods: list[str],
) -> pd.DataFrame:
    """Return only rows within the requested airline/year/quarter scope."""
    if df.empty:
        return df
    out = df.copy()
    if "Airline" in out.columns:
        out = out[out["Airline"].isin(airlines)]
    if "Year" in out.columns:
        out = out[out["Year"].isin(years)]
    if "Quarter" in out.columns:
        out = out[out["Quarter"].isin(periods)]
    return out


# ---------------------------------------------------------------------------
# Merge and derive
# ---------------------------------------------------------------------------
def _report_mismatches(merged: pd.DataFrame) -> None:
    # Passenger Revenue is auto-sourced (legacy tag, ALGT's live tag, or the
    # filing-parser dimensional tier) but still carried in the manual sheet
    # for some airlines, so reconcile it too.
    for metric in AUTO_METRICS + ["Passenger Revenue"]:
        manual_col = f"{metric}_manual"
        if manual_col not in merged.columns:
            continue
        auto_vals = pd.to_numeric(merged[metric], errors="coerce")
        manual_vals = pd.to_numeric(merged[manual_col], errors="coerce")
        valid = auto_vals.notna() & manual_vals.notna() & (manual_vals != 0)
        rel = (auto_vals - manual_vals).abs() / manual_vals.abs()
        bad_mask = valid & (rel > MISMATCH_TOLERANCE)
        if not bad_mask.any():
            continue
        bad_rows = merged.loc[bad_mask, ["Airline", "Year", "Quarter"]].copy()
        bad_rows["auto"] = auto_vals.loc[bad_mask]
        bad_rows["manual"] = manual_vals.loc[bad_mask]
        bad_rows["rel"] = rel.loc[bad_mask] * 100
        for row in bad_rows.itertuples(index=False):
            log.warning(
                "%s %s %s: %s auto=%.0f manual=%.0f (%.1f%%)",
                row.Airline, row.Year, row.Quarter, metric,
                row.auto, row.manual, row.rel,
            )


def merge_sources(auto: pd.DataFrame, manual: pd.DataFrame) -> pd.DataFrame:
    """Merge auto and manual metrics on airline/year/quarter, auto authoritative."""
    keys = ["Airline", "Year", "Quarter"]
    if manual.empty:
        merged = auto.copy()
        for m in MANUAL_METRICS:
            if m not in merged.columns:
                merged[m] = pd.NA
        return merged

    # Rename any auto-metric columns the manual sheet also provides so we can
    # compare rather than silently overwrite.
    overlap = [m for m in (AUTO_METRICS + ["Passenger Revenue"]) if m in manual.columns]
    manual = manual.rename(columns={m: f"{m}_manual" for m in overlap})
    merged = auto.merge(manual, on=keys, how="outer", suffixes=("", "_manual"))
    _report_mismatches(merged)

    # Prefer the auto value; fall back to the manual value where auto is absent.
    for metric in overlap:
        if metric in merged.columns and f"{metric}_manual" in merged.columns:
            merged[metric] = merged[metric].fillna(merged[f"{metric}_manual"])

    return merged


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the derived metrics using the legacy formulas."""
    def col(name: str) -> pd.Series:
        return pd.to_numeric(df[name], errors="coerce") if name in df.columns else pd.Series(pd.NA, index=df.index)

    op_rev, op_exp = col("Operating Revenue"), col("Operating Expenses")
    op_inc = col("Operating Income")
    net_inc, pax_rev = col("Net Income"), col("Passenger Revenue")
    rpm, asm = col("RPM"), col("ASM")
    ltd, curr_mat, cash_eq, unr_cash, r_cash, st_inv = col("Long-Term Debt"), col("Current Maturities"), col("Cash & Cash Equivalents"), col("Unrestricted Cash"), col("Restricted Cash"), col("Short-Term Investments")
    ocf, capex = col("Operating Cash Flow"), col("Capital Expenditures").abs()

    df["Operating Margin"] = ((op_inc / op_rev) * 100).round(2)
    df["Net Margin"] = ((net_inc / op_rev) * 100).round(2)
    df["Load Factor"] = ((rpm / asm) * 100).round(2)
    df["Yield"] = pax_rev / rpm
    df["TRASM"] = op_rev / asm
    df["PRASM"] = pax_rev / asm
    df["CASM"] = op_exp / asm
    df["Period"] = df["Year"].astype(str) + df["Quarter"].astype(str)
    df["Total Debt"] = ltd.fillna(0) + curr_mat.fillna(0)
    df["Cash & Cash Equivalents"] = (cash_eq.combine_first((unr_cash.fillna(0) + r_cash.fillna(0)).where(unr_cash.notna() | r_cash.notna())))
    df["Total Liquidity"] = col("Cash & Cash Equivalents") + st_inv.fillna(0)
    df["Net Debt"] = col("Total Debt") - col("Total Liquidity")
    df["Free Cash Flow"] = ocf - capex

    return _reorder_columns(df)


# Preferred metric order for the final JSON output. Reapplied after merging
# with existing financials.json, since pd.concat otherwise appends any column
# missing from the existing data (e.g. a newly added metric) to the very end.
_PREFERRED_COLUMN_ORDER = [
    "Airline",
    "Year",
    "Quarter",
    "Period",
    "Operating Revenue",
    "Passenger Revenue",
    "Cargo Revenue",
    "Operating Expenses",
    "Operating Income",
    "Net Income",
    "Operating Margin",
    "Net Margin",
    "Earnings Per Share",
    "RPM",
    "ASM",
    "Load Factor",
    "Yield",
    "TRASM",
    "PRASM",
    "CASM",
    "Profit Sharing",
    "Long-Term Debt",
    "Current Maturities",
    "Total Debt",
    "Cash & Cash Equivalents",
    "Short-Term Investments",
    "Total Liquidity",
    "Net Debt",
    "Interest Expense",
    "Operating Cash Flow",
    "Capital Expenditures",
    "Free Cash Flow",
]
_COLUMNS_TO_DROP = ["Unrestricted Cash", "Restricted Cash"]


def _reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reorder columns into the preferred metric order, dropping raw cash parts."""
    preferred = [c for c in _PREFERRED_COLUMN_ORDER if c in df.columns]
    remaining = [c for c in df.columns if c not in preferred]
    return df[preferred + remaining].drop(columns=_COLUMNS_TO_DROP, errors="ignore")

    return df


# ---------------------------------------------------------------------------
# Buybacks
# ---------------------------------------------------------------------------
def build_buybacks(repurchases: pd.DataFrame, sales: pd.DataFrame) -> dict[str, Any]:
    """Derive the share repurchase and share sale views."""
    out: dict[str, Any] = {"repurchases": [], "sales": []}
    if not repurchases.empty:
        r = repurchases.copy()
        r["Shares (millions)"] = r["Shares Repurchased"] / 1_000_000
        r["Cost (millions)"] = r["Cost"] / 1_000_000
        r["Average Share Price"] = (r["Cost"] / r["Shares Repurchased"]).fillna(0)
        r["Period"] = r["Year"].astype(str) + r["Quarter"].astype(str)
        out["repurchases"] = _records(r)
    if not sales.empty:
        s = sales.copy()
        s["Shares (millions)"] = s["Shares Sold"] / 1_000_000
        s["Proceeds (millions)"] = s["Proceeds"] / 1_000_000
        s["Average Share Price"] = (s["Proceeds"] / s["Shares Sold"]).fillna(0)
        s["Period"] = s["Year"].astype(str) + s["Quarter"].astype(str)
        out["sales"] = _records(s)
    return out


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a frame to JSON-safe records (NaN -> None)."""
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def _write(path: Path, payload: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    log.info("Wrote %s", path)


def _build_coverage_diagnostics(
    merged: pd.DataFrame,
    auto: pd.DataFrame,
    manual: pd.DataFrame,
    airlines: list[str],
    years: list[int],
    periods: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build coverage diagnostics for requested airline/year/period slice."""
    key_cols = ["Airline", "Year", "Quarter"]
    metric_sources: dict[str, str] = {
        **{metric: "auto_xbrl" for metric in AUTO_METRICS},
        **{metric: "manual_only" for metric in MANUAL_METRICS},
    }

    metrics = [m for m in metric_sources if m in merged.columns]
    expected_keys = [
        (airline, year, period)
        for airline in airlines
        for year in years
        for period in periods
    ]

    merged_idx = merged.set_index(key_cols) if not merged.empty else pd.DataFrame(columns=metrics)
    auto_keys = set(auto[key_cols].itertuples(index=False, name=None)) if not auto.empty else set()
    manual_keys = set(manual[key_cols].itertuples(index=False, name=None)) if not manual.empty else set()

    if config.DIAGNOSTICS_EXCLUDE_FUTURE_PERIODS:
        quarter_rank = {q: i for i, q in enumerate(config.QUARTERS)}

        def _sort_key(key: tuple[str, int, str]) -> tuple[int, int]:
            return (key[1], quarter_rank.get(key[2], 99))

        available_keys = set(auto_keys) | set(manual_keys)
        if not merged.empty:
            available_keys |= set(merged[key_cols].itertuples(index=False, name=None))

        latest_by_airline: dict[str, tuple[int, int]] = {}
        for airline, year, quarter in available_keys:
            if airline not in airlines or year not in years or quarter not in periods:
                continue
            key_rank = _sort_key((airline, year, quarter))
            if key_rank > latest_by_airline.get(airline, (-1, -1)):
                latest_by_airline[airline] = key_rank

        expected_keys = [
            key
            for key in expected_keys
            if key[0] not in latest_by_airline or _sort_key(key) <= latest_by_airline[key[0]]
        ]

    detail_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for airline in airlines:
        airline_expected = [key for key in expected_keys if key[0] == airline]
        expected_count = len(airline_expected)

        for metric in metrics:
            source_type = metric_sources.get(metric, "unknown")
            populated = 0
            missing = 0

            for key in airline_expected:
                value = pd.NA
                if key in merged_idx.index and metric in merged_idx.columns:
                    value = merged_idx.at[key, metric]

                if pd.notna(value):
                    populated += 1
                    continue

                missing += 1
                if source_type == "manual_only":
                    reason = "NO_MANUAL_ROW" if key not in manual_keys else "NO_MANUAL_VALUE"
                elif source_type == "auto_xbrl":
                    reason = "NO_AUTO_ROW" if key not in auto_keys else "NO_AUTO_VALUE"
                else:
                    reason = "MISSING_VALUE"

                detail_rows.append(
                    {
                        "airline": key[0],
                        "year": key[1],
                        "quarter": key[2],
                        "metric": metric,
                        "source_type": source_type,
                        "reason_code": reason,
                    }
                )

            coverage_pct = round((populated / expected_count) * 100, 1) if expected_count else 0.0
            summary_rows.append(
                {
                    "airline": airline,
                    "metric": metric,
                    "source_type": source_type,
                    "expected_periods": expected_count,
                    "populated_periods": populated,
                    "missing_periods": missing,
                    "coverage_pct": coverage_pct,
                }
            )

    summary_df = pd.DataFrame(
        summary_rows,
        columns=[
            "airline",
            "metric",
            "source_type",
            "expected_periods",
            "populated_periods",
            "missing_periods",
            "coverage_pct",
        ],
    )
    detail_df = pd.DataFrame(
        detail_rows,
        columns=[
            "airline",
            "year",
            "quarter",
            "metric",
            "source_type",
            "reason_code",
        ],
    )
    if not summary_df.empty:
        summary_df = summary_df.sort_values(["airline", "source_type", "metric"])
    if not detail_df.empty:
        detail_df = detail_df.sort_values(["airline", "metric", "year", "quarter"])

    reason_counts = (
        detail_df["reason_code"].value_counts().to_dict()
        if not detail_df.empty
        else {}
    )
    report = {
        "requested_airlines": airlines,
        "requested_years": years,
        "requested_periods": periods,
        "exclude_future_periods": config.DIAGNOSTICS_EXCLUDE_FUTURE_PERIODS,
        "summary_rows": int(len(summary_df)),
        "detail_rows": int(len(detail_df)),
        "reason_counts": reason_counts,
    }
    return summary_df, detail_df, report


def _write_coverage_diagnostics(
    merged: pd.DataFrame,
    auto: pd.DataFrame,
    manual: pd.DataFrame,
    airlines: list[str],
    years: list[int],
    periods: list[str],
) -> None:
    """Write diagnostics tables and report under data/generated/diagnostics."""
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    summary_df, detail_df, report = _build_coverage_diagnostics(
        merged=merged,
        auto=auto,
        manual=manual,
        airlines=airlines,
        years=years,
        periods=periods,
    )
    summary_df.to_csv(DIAGNOSTICS_SUMMARY_CSV, index=False)
    detail_df.to_csv(DIAGNOSTICS_DETAIL_CSV, index=False)
    DIAGNOSTICS_REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Wrote %s", DIAGNOSTICS_SUMMARY_CSV)
    log.info("Wrote %s", DIAGNOSTICS_DETAIL_CSV)
    log.info("Wrote %s", DIAGNOSTICS_REPORT_JSON)


def _load_existing_financials() -> pd.DataFrame:
    if not FINANCIALS_PATH.exists():
        return pd.DataFrame()
    df = pd.DataFrame(json.loads(FINANCIALS_PATH.read_text(encoding="utf-8")))
    if df.empty:
        return df
    if "Period" not in df.columns:
        df["Period"] = df["Year"].astype(str) + df["Quarter"].astype(str)
    return df


def _merge_financials(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return new
    if new.empty:
        return existing

    key = ["Airline", "Year", "Quarter"]
    new = new.drop_duplicates(subset=key, keep="last")
    existing = existing.copy()
    existing = existing[~existing.set_index(key).index.isin(new.set_index(key).index)]
    merged = pd.concat([existing, new], ignore_index=True, sort=False)
    if "Period" not in merged.columns:
        merged["Period"] = merged["Year"].astype(str) + merged["Quarter"].astype(str)
    return merged.sort_values(["Airline", "Year", "Quarter"])


def _load_existing_buybacks() -> dict[str, list[dict[str, Any]]]:
    if not BUYBACKS_PATH.exists():
        return {"repurchases": [], "sales": []}
    existing = json.loads(BUYBACKS_PATH.read_text(encoding="utf-8"))
    return {
        "repurchases": existing.get("repurchases", []),
        "sales": existing.get("sales", []),
    }


def _merge_records(existing: list[dict[str, Any]], new: list[dict[str, Any]], key_fields: list[str]) -> list[dict[str, Any]]:
    if not existing:
        return new
    if not new:
        return existing

    new_keys = {tuple(r.get(k) for k in key_fields) for r in new}
    merged = [r for r in existing if tuple(r.get(k) for k in key_fields) not in new_keys]
    merged.extend(new)
    return merged


def _merge_buybacks(existing: dict[str, list[dict[str, Any]]], new: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "repurchases": _merge_records(existing.get("repurchases", []), new.get("repurchases", []), ["Airline", "Year", "Quarter"]),
        "sales": _merge_records(existing.get("sales", []), new.get("sales", []), ["Airline", "Year", "Quarter"]),
    }


def build(
    airlines: list[str],
    years: list[int],
    periods: list[str],
    overwrite: bool = False,
    share_data: bool = False,
    use_filing_parser: bool = False,
) -> None:
    auto = load_auto(airlines, years, periods)
    if use_filing_parser:
        filing_parser_df = load_filing_parser(airlines, years, periods)
        auto = _overlay_filing_parser(auto, filing_parser_df)
    manual_metrics, repurchases, sales = load_manual()
    repurchases_full = repurchases.copy()
    sales_full = sales.copy()

    # Scope manual metrics to the requested slice so subset runs are idempotent.
    manual_metrics = _scope_frame(manual_metrics, airlines, years, periods)

    merged = merge_sources(auto, manual_metrics)
    merged = add_derived(merged)

    drop = [c for c in merged.columns if c.endswith("_manual")]
    merged = merged.drop(columns=drop).sort_values(["Airline", "Year", "Quarter"])

    # Final guard: only requested keys are eligible to update persisted financials.
    merged = _scope_frame(merged, airlines, years, periods)

    # Diagnostics are always produced for the requested slice.
    _write_coverage_diagnostics(
        merged=merged,
        auto=auto,
        manual=manual_metrics,
        airlines=airlines,
        years=years,
        periods=periods,
    )

    if not overwrite:
        existing_financials = _load_existing_financials()
        merged = _merge_financials(existing_financials, merged)
        merged = _reorder_columns(merged)

    _write(FINANCIALS_PATH, _records(merged))

    if share_data:
        buybacks = build_buybacks(repurchases_full, sales_full)
        _write(BUYBACKS_PATH, buybacks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the dashboard datasets.")
    parser.add_argument("--airlines", nargs="+", default=["AAL", "DAL", "UAL", "LUV", "ALK", "JBLU", "ULCC", "ALGT", "RJET", "SKYW"])
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--periods", nargs="+", default=["Q1", "Q2", "Q3", "Q4", "FY"])
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing generated outputs instead of merging with existing data.")
    parser.add_argument("--share-data", action="store_true", help="Optionally write full static share repurchase/sale history from manual files (unscoped). If omitted, existing buybacks.json is left unchanged.")
    parser.add_argument("--use-filing-parser", action="store_true", help="Fetch Passenger Revenue and Cargo Revenue via per-filing dimensional XBRL parsing (sec_pipeline.filing_parser). Expensive -- one filing fetch per ticker per quarter/year -- and only covers tickers with a verified dimensional mapping. Off by default.")
    args = parser.parse_args()
    build(
        args.airlines,
        args.years,
        args.periods,
        overwrite=args.overwrite,
        share_data=args.share_data,
        use_filing_parser=args.use_filing_parser,
    )


if __name__ == "__main__":
    main()
