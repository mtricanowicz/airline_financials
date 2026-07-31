"""Extract auto-sourceable financial metrics from SEC XBRL company facts.

The extractor supports a broader metric set than the original four-core model,
including cash-flow and liquidity fields where us-gaap tags are available.

Flow metrics use duration contexts, with YTD-aware handling for metrics commonly
reported cumulatively in Q2/Q3 (e.g., Operating Cash Flow and CapEx). Most Q4
flows are derived as ``FY - (Q1 + Q2 + Q3)``. Instant metrics use period-end
contexts. Fact selection prefers matching SEC ``fp`` values when available.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
import logging
from typing import Any

log = logging.getLogger("xbrl")

# Candidate us-gaap tags per metric, tried in priority order.
DURATION_METRICS: dict[str, list[str]] = {
    "Operating Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueServicesNet",
        "SalesRevenueNet",
        "Revenues",
    ],
    "Operating Expenses": [
        "OperatingExpenses",
        "OperatingCostsAndExpenses",
        "CostsAndExpenses",
    ],
    "Net Income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "Earnings Per Share": [
        "EarningsPerShareBasic",
    ],
    "Operating Cash Flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "Capital Expenditures": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
    ],
}

INSTANT_METRICS: dict[str, list[str]] = {
    "Long-Term Debt": [
        "LongTermDebt",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtAndCapitalLeaseObligationsNoncurrent",
        "FinanceLeaseLiabilityNoncurrent",
    ],
    "Current Maturities": [
        "LongTermDebtCurrent",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
        "CurrentPortionOfLongTermDebt",
        "DebtCurrent",
        "FinanceLeaseLiabilityCurrent",
    ],
    "Cash & Cash Equivalents": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "Unrestricted Cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
    ],
    "Restricted Cash": [
        "RestrictedCashAndCashEquivalentsCurrent",
        "RestrictedCashAndCashEquivalentsNoncurrent",
        "RestrictedCashCurrent",
        "RestrictedCashNoncurrent",
    ],
    "Short-Term Investments": [
        "ShortTermInvestments",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "MarketableSecuritiesCurrent",
        "DebtSecuritiesAvailableForSaleCurrent",
    ],
}

ALL_METRICS = tuple(DURATION_METRICS) + tuple(INSTANT_METRICS)

_QUARTER_END_MONTH = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12, "FY": 12}
YTD_DERIVED_METRICS = {"Operating Cash Flow", "Capital Expenditures"}
NON_ADDITIVE_DURATION_METRICS = {"Earnings Per Share"}
METRIC_UNIT_CANDIDATES: dict[str, list[str]] = {
    "Earnings Per Share": ["USD/shares", "USD/share"],
}
EPS_SHARE_TAGS = [
    "WeightedAverageNumberOfSharesOutstandingBasic",
    "WeightedAverageNumberOfCommonSharesOutstandingBasic",
]
EPS_SHARE_UNIT_CANDIDATES = ["shares"]
CAPEX_BROAD_TAGS = [
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsForAdditionsToPropertyPlantAndEquipment",
    "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
]
CAPEX_COMPONENT_TAGS = [
    "PaymentsForFlightEquipment",
    "PaymentsToAcquireOtherProductiveAssets",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
]
CAPEX_RECONCILE_TOLERANCE = 0.05


def _facts_for_tag(
    facts: dict[str, Any],
    tag: str,
    unit_candidates: list[str] | None = None,
) -> list[dict[str, Any]]:
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return []
    units = node.get("units", {})
    if unit_candidates is None:
        unit_candidates = ["USD"]
    out: list[dict[str, Any]] = []
    for unit in unit_candidates:
        out.extend(units.get(unit, []))
    return out


def _fp_candidates(period: str) -> set[str]:
    """Preferred SEC fiscal period labels for a logical period."""
    if period == "Q4":
        # Year-end filings usually carry FY in companyfacts.
        return {"Q4", "FY"}
    return {period}


def _latest_value(candidates: list[dict[str, Any]]) -> float | None:
    """Pick the latest fact by accession when available."""
    if not candidates:
        return None
    best = max(candidates, key=lambda f: (str(f.get("accn", "")), str(f.get("filed", ""))))
    return float(best["val"])


@lru_cache(maxsize=8192)
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


def _pick_duration_window(
    facts_list: list[dict[str, Any]],
    year: int,
    end_month: int,
    min_days: int,
    max_days: int,
    period: str | None = None,
) -> float | None:
    """Pick a duration fact matching year/month and day-count window."""
    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    fp_preferred = _fp_candidates(period) if period else set()
    for f in facts_list:
        end = _parse(f.get("end"))
        days = _duration_days(f)
        if not end or days is None:
            continue
        if end.year != year or end.month != end_month:
            continue
        if not (min_days <= days <= max_days):
            continue
        if period and str(f.get("fp", "")) in fp_preferred:
            preferred.append(f)
        else:
            fallback.append(f)
    preferred_val = _latest_value(preferred)
    if preferred_val is not None:
        return preferred_val
    return _latest_value(fallback)


def _pick_duration(
    facts_list: list[dict[str, Any]], year: int, period: str
) -> float | None:
    """Pick the flow value for a year/period from duration facts."""
    end_month = _QUARTER_END_MONTH[period]
    target_len = (350, 380) if period == "FY" else (80, 105)
    return _pick_duration_window(
        facts_list, year, end_month, target_len[0], target_len[1], period=period
    )


def _pick_instant(
    facts_list: list[dict[str, Any]], year: int, period: str
) -> float | None:
    """Pick the balance value for a year/period from instant facts."""
    end_month = _QUARTER_END_MONTH[period]
    preferred: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    fp_preferred = _fp_candidates(period)
    for f in facts_list:
        end = _parse(f.get("end"))
        if not end or end.year != year or end.month != end_month:
            continue
        if str(f.get("fp", "")) in fp_preferred:
            preferred.append(f)
        else:
            fallback.append(f)
    preferred_val = _latest_value(preferred)
    if preferred_val is not None:
        return preferred_val
    return _latest_value(fallback)


def _extract_ytd_from_tags(
    facts: dict[str, Any],
    tags: list[str],
    year: int,
    period: str,
    unit_candidates: list[str] | None = None,
) -> float | None:
    """Extract duration metric values when Q2/Q3 may be filed as YTD."""

    # Prefer direct quarter fact (~90 days) where present.
    if period in {"Q1", "Q2", "Q3"}:
        for tag in tags:
            direct = _pick_duration(_facts_for_tag(facts, tag, unit_candidates), year, period)
            if direct is not None:
                return direct

    if period == "Q1":
        for tag in tags:
            q1_ytd = _pick_duration_window(
                _facts_for_tag(facts, tag, unit_candidates),
                year,
                3,
                80,
                105,
                period="Q1",
            )
            if q1_ytd is not None:
                return q1_ytd
        return None

    if period == "Q2":
        for tag in tags:
            facts_list = _facts_for_tag(facts, tag, unit_candidates)
            q2_ytd = _pick_duration_window(facts_list, year, 6, 170, 195, period="Q2")
            q1_ytd = _pick_duration_window(facts_list, year, 3, 80, 105, period="Q1")
            if q2_ytd is not None and q1_ytd is not None:
                return q2_ytd - q1_ytd
        return None

    if period == "Q3":
        for tag in tags:
            facts_list = _facts_for_tag(facts, tag, unit_candidates)
            q3_ytd = _pick_duration_window(facts_list, year, 9, 260, 290, period="Q3")
            q2_ytd = _pick_duration_window(facts_list, year, 6, 170, 195, period="Q2")
            if q3_ytd is not None and q2_ytd is not None:
                return q3_ytd - q2_ytd
        return None

    if period == "Q4":
        # Prefer FY - Q3 YTD.
        for tag in tags:
            facts_list = _facts_for_tag(facts, tag, unit_candidates)
            fy = _pick_duration_window(facts_list, year, 12, 350, 380, period="FY")
            q3_ytd = _pick_duration_window(facts_list, year, 9, 260, 290, period="Q3")
            if fy is not None and q3_ytd is not None:
                return fy - q3_ytd

        # Fallback FY - (Q1 + Q2 + Q3).
        fy = _extract_ytd_from_tags(facts, tags, year, "FY")
        parts = [_extract_ytd_from_tags(facts, tags, year, q) for q in ("Q1", "Q2", "Q3")]
        if fy is None or any(p is None for p in parts):
            return None
        return fy - sum(parts)  # type: ignore[arg-type]

    if period == "FY":
        for tag in tags:
            fy = _pick_duration(_facts_for_tag(facts, tag), year, "FY")
            if fy is not None:
                return fy
        return None

    return None


def _extract_ytd_metric(
    facts: dict[str, Any], metric: str, year: int, period: str
) -> float | None:
    """Extract named cash-flow metrics that may be reported YTD in Q2/Q3."""
    return _extract_ytd_from_tags(
        facts,
        DURATION_METRICS[metric],
        year,
        period,
        unit_candidates=METRIC_UNIT_CANDIDATES.get(metric),
    )


def _extract_capex_metric(
    facts: dict[str, Any], year: int, period: str
) -> float | None:
    """Extract CapEx with broad-tag precedence and component-sum fallback."""
    broad_val = _extract_ytd_from_tags(facts, CAPEX_BROAD_TAGS, year, period)

    components = [
        _extract_ytd_from_tags(facts, [tag], year, period)
        for tag in CAPEX_COMPONENT_TAGS
    ]
    component_vals = [v for v in components if v is not None]
    component_sum = sum(component_vals) if component_vals else None

    # Avoid double counting: never add broad + component values together.
    if broad_val is not None:
        if component_sum is None:
            return broad_val

        base = max(abs(broad_val), abs(component_sum), 1.0)
        rel_diff = abs(broad_val - component_sum) / base
        if rel_diff <= CAPEX_RECONCILE_TOLERANCE:
            return broad_val

        # Deterministic mismatch policy: prefer component sum when materially different.
        log.debug(
            "CapEx broad/component mismatch year=%s period=%s broad=%s component_sum=%s rel_diff=%.3f",
            year,
            period,
            broad_val,
            component_sum,
            rel_diff,
        )
        return component_sum

    return component_sum


def _extract_restricted_cash_metric(
    facts: dict[str, Any], year: int, period: str
) -> float | None:
    """Extract restricted cash by summing current/noncurrent components safely."""
    current_tags = [
        "RestrictedCashAndCashEquivalentsCurrent",
        "RestrictedCashCurrent",
    ]
    noncurrent_tags = [
        "RestrictedCashAndCashEquivalentsNoncurrent",
        "RestrictedCashNoncurrent",
    ]

    current_val: float | None = None
    for tag in current_tags:
        current_val = _pick_instant(_facts_for_tag(facts, tag), year, period)
        if current_val is not None:
            break

    noncurrent_val: float | None = None
    for tag in noncurrent_tags:
        noncurrent_val = _pick_instant(_facts_for_tag(facts, tag), year, period)
        if noncurrent_val is not None:
            break

    if current_val is None and noncurrent_val is None:
        return None
    return (current_val or 0.0) + (noncurrent_val or 0.0)


def _extract_eps_q4_fallback(facts: dict[str, Any], year: int) -> float | None:
    """Derive Q4 basic EPS if direct Q4 value is not present.

    Formula:
      net_income_fy = eps_fy * shares_fy
      net_income_q1_3 = sum(eps_q * shares_q)
      shares_q4 = 4*shares_fy - shares_q1 - shares_q2 - shares_q3
      eps_q4 = (net_income_fy - net_income_q1_3) / shares_q4
    """
    eps_tags = DURATION_METRICS["Earnings Per Share"]
    eps_units = METRIC_UNIT_CANDIDATES.get("Earnings Per Share")

    # Direct quarter EPS and FY EPS
    eps_vals: dict[str, float] = {}
    for p in ("Q1", "Q2", "Q3", "FY"):
        v: float | None = None
        for tag in eps_tags:
            v = _pick_duration(_facts_for_tag(facts, tag, eps_units), year, p)
            if v is not None:
                break
        if v is None:
            return None
        eps_vals[p] = v

    # Corresponding weighted-average basic shares
    shares_vals: dict[str, float] = {}
    for p in ("Q1", "Q2", "Q3", "FY"):
        v: float | None = None
        for tag in EPS_SHARE_TAGS:
            v = _pick_duration(
                _facts_for_tag(facts, tag, EPS_SHARE_UNIT_CANDIDATES),
                year,
                p,
            )
            if v is not None:
                break
        if v is None:
            return None
        shares_vals[p] = v

    shares_q4 = (4.0 * shares_vals["FY"]) - shares_vals["Q1"] - shares_vals["Q2"] - shares_vals["Q3"]
    if shares_q4 <= 0:
        return None

    ni_fy = eps_vals["FY"] * shares_vals["FY"]
    ni_q1_3 = (
        eps_vals["Q1"] * shares_vals["Q1"]
        + eps_vals["Q2"] * shares_vals["Q2"]
        + eps_vals["Q3"] * shares_vals["Q3"]
    )
    eps_q4 = (ni_fy - ni_q1_3) / shares_q4
    return round(eps_q4, 2)


def extract_metric(facts: dict[str, Any], metric: str, year: int, period: str) -> float | None:
    """Extract one metric for one year/period, deriving Q4 when needed."""
    if metric in INSTANT_METRICS:
        if metric == "Restricted Cash":
            return _extract_restricted_cash_metric(facts, year, period)
        for tag in INSTANT_METRICS[metric]:
            val = _pick_instant(_facts_for_tag(facts, tag), year, period)
            if val is not None:
                return val
        return None

    if metric in YTD_DERIVED_METRICS:
        if metric == "Capital Expenditures":
            return _extract_capex_metric(facts, year, period)
        return _extract_ytd_metric(facts, metric, year, period)

    tags = DURATION_METRICS[metric]
    unit_candidates = METRIC_UNIT_CANDIDATES.get(metric)
    if period != "Q4":
        for tag in tags:
            val = _pick_duration(_facts_for_tag(facts, tag, unit_candidates), year, period)
            # Revenue and expenses should not be zero for an active airline
            if metric in {"Operating Revenue", "Operating Expenses"}:
                if val is not None and val > 0:
                    return val
            elif val is not None:
                return val
        return None

    if metric in NON_ADDITIVE_DURATION_METRICS:
        # Do not derive non-additive metrics from FY minus quarters.
        for tag in tags:
            val = _pick_duration(_facts_for_tag(facts, tag, unit_candidates), year, period)
            if val is not None:
                return val
        if metric == "Earnings Per Share" and period == "Q4":
            return _extract_eps_q4_fallback(facts, year)
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
    records: list[dict[str, Any]] = []
    for year in years:
        for period in periods:
            row: dict[str, Any] = {"Year": year, "Quarter": period}
            has_any = False
            for metric in ALL_METRICS:
                val = extract_metric(facts, metric, year, period)
                row[metric] = val
                has_any = has_any or val is not None
            if has_any:
                records.append(row)
    return records
