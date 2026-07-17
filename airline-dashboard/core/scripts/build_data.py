"""Build the canonical dashboard datasets consumed by both front ends.

Combines three sources:

* Auto (SEC XBRL company facts): Operating Revenue, Operating Expenses,
  Net Income, Long-Term Debt.
* Manual sheet (``data/manual/``): Passenger Revenue, RPM, ASM, Profit Sharing,
  and the share repurchase / share sale history.
* Derived (here): Operating Income, margins, Load Factor, Yield, TRASM, PRASM,
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

from sec_pipeline import config
from sec_pipeline.edgar_client import EdgarClient
from sec_pipeline.xbrl import extract_financials

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_data")

AUTO_METRICS = ["Operating Revenue", "Operating Expenses", "Net Income", "Long-Term Debt"]
MANUAL_METRICS = ["Passenger Revenue", "RPM", "ASM", "Profit Sharing"]
MISMATCH_TOLERANCE = 0.02  # 2% relative difference

FINANCIALS_PATH = config.GENERATED_DIR / "financials.json"
BUYBACKS_PATH = config.GENERATED_DIR / "buybacks.json"

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
    """Fetch XBRL company facts and extract the four auto metrics per airline."""
    client = EdgarClient()
    ciks = client.resolve_ciks(airlines)
    rows: list[dict[str, Any]] = []
    for airline in airlines:
        try:
            facts = client.company_facts(ciks[airline])
        except Exception as exc:  # noqa: BLE001
            log.error("Could not fetch company facts for %s: %s", airline, exc)
            continue
        for rec in extract_financials(facts, years, periods):
            rec["Airline"] = airline
            rows.append(rec)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Merge and derive
# ---------------------------------------------------------------------------
def _report_mismatches(merged: pd.DataFrame) -> None:
    for metric in AUTO_METRICS:
        manual_col = f"{metric}_manual"
        if manual_col not in merged.columns:
            continue
        for _, row in merged.iterrows():
            auto_val, manual_val = row.get(metric), row.get(manual_col)
            if pd.isna(auto_val) or pd.isna(manual_val) or not manual_val:
                continue
            rel = abs(auto_val - manual_val) / abs(manual_val)
            if rel > MISMATCH_TOLERANCE:
                log.warning(
                    "%s %s %s: %s auto=%.0f manual=%.0f (%.1f%%)",
                    row["Airline"], row["Year"], row["Quarter"], metric,
                    auto_val, manual_val, rel * 100,
                )


def merge_sources(auto: pd.DataFrame, manual: pd.DataFrame) -> pd.DataFrame:
    """Merge auto and manual metrics on airline/year/quarter, auto authoritative."""
    keys = ["Airline", "Year", "Quarter"]
    if manual.empty:
        merged = auto.copy()
        for m in MANUAL_METRICS:
            merged[m] = pd.NA
        return merged

    # Rename any auto-metric columns the manual sheet also provides so we can
    # compare rather than silently overwrite.
    overlap = [m for m in AUTO_METRICS if m in manual.columns]
    manual = manual.rename(columns={m: f"{m}_manual" for m in overlap})
    merged = auto.merge(manual, on=keys, how="outer", suffixes=("", "_manual"))
    _report_mismatches(merged)

    # Prefer the auto value; fall back to the manual value where auto is absent.
    for metric in overlap:
        merged[metric] = merged[metric].fillna(merged[f"{metric}_manual"])
    return merged


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the derived metrics using the legacy formulas."""
    def col(name: str) -> pd.Series:
        return pd.to_numeric(df[name], errors="coerce") if name in df.columns else pd.Series(pd.NA, index=df.index)

    op_rev, op_exp = col("Operating Revenue"), col("Operating Expenses")
    net_inc, pax_rev = col("Net Income"), col("Passenger Revenue")
    rpm, asm = col("RPM"), col("ASM")

    df["Operating Income"] = op_rev - op_exp
    df["Operating Margin"] = ((df["Operating Income"] / op_rev) * 100).round(2)
    df["Net Margin"] = ((net_inc / op_rev) * 100).round(2)
    df["Load Factor"] = ((rpm / asm) * 100).round(2)
    df["Yield"] = pax_rev / rpm
    df["TRASM"] = op_rev / asm
    df["PRASM"] = pax_rev / asm
    df["CASM"] = op_exp / asm
    df["Period"] = df["Year"].astype(str) + df["Quarter"].astype(str)
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
    return json.loads(df.astype(object).where(pd.notna(df), None).to_json(orient="records"))


def _write(path: Path, payload: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    log.info("Wrote %s", path)


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


def build(airlines: list[str], years: list[int], periods: list[str], overwrite: bool = False) -> None:
    auto = load_auto(airlines, years, periods)
    manual_metrics, repurchases, sales = load_manual()
    merged = merge_sources(auto, manual_metrics)
    merged = add_derived(merged)

    drop = [c for c in merged.columns if c.endswith("_manual")]
    merged = merged.drop(columns=drop).sort_values(["Airline", "Year", "Quarter"])

    if not overwrite:
        existing_financials = _load_existing_financials()
        merged = _merge_financials(existing_financials, merged)

    _write(FINANCIALS_PATH, _records(merged))

    new_buybacks = build_buybacks(repurchases, sales)
    if overwrite:
        buybacks = new_buybacks
    else:
        existing_buybacks = _load_existing_buybacks()
        buybacks = _merge_buybacks(existing_buybacks, new_buybacks)
    _write(BUYBACKS_PATH, buybacks)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the dashboard datasets.")
    parser.add_argument("--airlines", nargs="+", default=["AAL", "DAL", "UAL", "LUV", "ALK", "JBLU", "ULCC"])
    parser.add_argument("--years", nargs="+", type=int, required=True)
    parser.add_argument("--periods", nargs="+", default=["Q1", "Q2", "Q3", "Q4", "FY"])
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing generated outputs instead of merging with existing data.")
    args = parser.parse_args()
    build(args.airlines, args.years, args.periods, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
