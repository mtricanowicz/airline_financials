"""Extract the auto-sourceable financial metrics from SEC XBRL company facts.

Only four metrics are reliably available in the us-gaap financial taxonomy:
Operating Revenue, Operating Expenses, Net Income, and Long-Term Debt. RPM, ASM,
and Profit Sharing are operational or non-standard disclosures and must be
supplied by the manual sheet.

Quarterly values are taken from 10-Q duration facts (~90 days). The unfiled Q4
is derived as ``FY - (Q1 + Q2 + Q3)`` for flow metrics; balance-sheet metrics
(Long-Term Debt) use the period-end instant fact directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

# Candidate us-gaap tags per metric, tried in priority order.
DURATION_METRICS: dict[str, list[str]] = {
    "Operating Revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
    ],
    "Operating Expenses": ["OperatingExpenses", "CostsAndExpenses"],
    "Net Income": ["NetIncomeLoss"],
}

INSTANT_METRICS: dict[str, list[str]] = {
    "Long-Term Debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
    ],
}

_QUARTER_END_MONTH = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12, "FY": 12}


def _facts_for_tag(facts: dict[str, Any], tag: str) -> list[dict[str, Any]]:
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return []
    return node.get("units", {}).get("USD", [])


def _parse(d: str | None) -> datetime | None:
    try:
        return datetime.strptime(d, "%Y-%m-%d") if d else None
    except ValueError:
        return None


def _duration_days(fact: dict[str, Any]) -> int | None:
    start, end = _parse(fact.get("start")), _parse(fact.get("end"))
    if start and end:
        return (end - start).days
    return None


def _pick_duration(
    facts_list: list[dict[str, Any]], year: int, period: str
) -> float | None:
    """Pick the flow value for a year/period from duration facts."""
    end_month = _QUARTER_END_MONTH[period]
    target_len = (350, 380) if period == "FY" else (80, 100)
    best: tuple[str, float] | None = None  # (accn, val), later filings win
    for f in facts_list:
        end = _parse(f.get("end"))
        days = _duration_days(f)
        if not end or days is None:
            continue
        if end.year != year or end.month != end_month:
            continue
        if not (target_len[0] <= days <= target_len[1]):
            continue
        best = (f.get("accn", ""), float(f["val"]))
    return best[1] if best else None


def _pick_instant(
    facts_list: list[dict[str, Any]], year: int, period: str
) -> float | None:
    """Pick the balance value for a year/period from instant facts."""
    end_month = _QUARTER_END_MONTH[period]
    best: float | None = None
    for f in facts_list:
        end = _parse(f.get("end"))
        if not end or end.year != year or end.month != end_month:
            continue
        best = float(f["val"])
    return best


def extract_metric(facts: dict[str, Any], metric: str, year: int, period: str) -> float | None:
    """Extract one metric for one year/period, deriving Q4 when needed."""
    if metric in INSTANT_METRICS:
        for tag in INSTANT_METRICS[metric]:
            val = _pick_instant(_facts_for_tag(facts, tag), year, period)
            if val is not None:
                return val
        return None

    tags = DURATION_METRICS[metric]
    if period != "Q4":
        for tag in tags:
            val = _pick_duration(_facts_for_tag(facts, tag), year, period)
            if val is not None:
                return val
        return None

    # Q4 is not filed separately: derive from FY minus the first three quarters.
    fy = extract_metric(facts, metric, year, "FY")
    parts = [extract_metric(facts, metric, year, q) for q in ("Q1", "Q2", "Q3")]
    if fy is None or any(p is None for p in parts):
        return None
    return fy - sum(parts)  # type: ignore[arg-type]


def extract_financials(
    facts: dict[str, Any], years: list[int], periods: list[str]
) -> list[dict[str, Any]]:
    """Return one record per year/period with the four auto-sourced metrics."""
    all_metrics = list(DURATION_METRICS) + list(INSTANT_METRICS)
    records: list[dict[str, Any]] = []
    for year in years:
        for period in periods:
            row: dict[str, Any] = {"Year": year, "Quarter": period}
            has_any = False
            for metric in all_metrics:
                val = extract_metric(facts, metric, year, period)
                row[metric] = val
                has_any = has_any or val is not None
            if has_any:
                records.append(row)
    return records
