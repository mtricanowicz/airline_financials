"""Per-filing extraction for metrics absent from SEC XBRL company facts.

``company facts`` only exposes non-dimensional XBRL facts, so metrics that
filers only report as a dimensional breakout (e.g. Passenger Revenue tagged
against a ProductOrServiceAxis/ContractWithCustomerSalesChannelAxis member) or
that are never tagged at all (ASM, RPM, Profit Sharing -- confirmed absent
from every airline's us-gaap taxonomy, standard or custom) require fetching
and parsing the filing itself, one filing at a time.

This module is the single per-filing extraction point for all four metrics
that ``data/manual/manual_metrics.csv`` currently supplies by hand. Passenger
Revenue is sourced from the XBRL instance document's dimensional facts, which
is precise and machine-checkable wherever a filer's axis/member is known and
verified -- currently AAL, DAL, UAL, LUV, ALK, JBLU, ULCC, SAVE, SNCY, and HA
(see ``PASSENGER_REVENUE_DIMENSIONAL_MAP``, each entry reconciled against the
filing's non-dimensional total). Cargo Revenue uses the same mechanism where
a filer discloses a distinct cargo line (see ``CARGO_REVENUE_DIMENSIONAL_MAP``
-- not every carrier has one; JetBlue and Spirit have no cargo business and
no such tag exists for them). ASM, RPM, and Profit Sharing have no XBRL
representation anywhere and must come from the MD&A "Operating Statistics"
table in the primary filing document; that parser is not yet implemented
(see ``extract_operating_statistics``) and is the next piece of work.

Carriers excluded entirely from the dimensional maps: SKYW and RJET, whose
revenue is contractual capacity-purchase fee revenue from major-airline
partners rather than passenger fares or true cargo revenue (see xbrl.py's
legacy-tag exclusion for the same reasoning); and VA, which has no filings
after 2016 (it merged into Alaska Air Group before the post-2018 dimensional-
tagging cutover, so this module is not applicable -- its pre-2018 periods are
covered by the deprecated-tag path in xbrl.py instead). HA deregistered from
SEC reporting (Form 15-12G, 2024-09-30) after merging into Alaska Air Group;
its last usable filing covers 2024 Q2.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from .edgar_client import EdgarClient, Filing

log = logging.getLogger("filing_parser")

# ---------------------------------------------------------------------------
# Passenger Revenue and Cargo Revenue: verified per-ticker dimensional XBRL
# mappings.
#
# Each entry names the standard us-gaap revenue concept, the axis, and the
# member that isolates the revenue component in that filer's own taxonomy
# extension. Only add a ticker here once verified against an actual filing:
# the member's value, plus the other disaggregated members on the same axis,
# must sum to the filing's non-dimensional total revenue for that period.
# ---------------------------------------------------------------------------
PASSENGER_REVENUE_DIMENSIONAL_MAP: dict[str, dict[str, str]] = {
    "ALK": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "us-gaap:ContractWithCustomerSalesChannelAxis",
        "member": "alk:PassengerRevenueMember",
        "legacy_concepts": ("PassengerRevenue",),
        "legacy_dimensions": (("us-gaap:ProductOrServiceAxis", "alk:PassengerMember"),),
    },
    "JBLU": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
        "legacy_concepts": ("PassengerRevenue",),
        "legacy_dimensions": (("us-gaap:ProductOrServiceAxis", "jblu:PassengerMember"),),
    },
    "ULCC": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
    },
    "AAL": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "aal:PassengerTravelMember",
    },
    "DAL": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
    },
    "UAL": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
        "legacy_concepts": ("PassengerRevenue",),
        "legacy_dimensions": (("us-gaap:ProductOrServiceAxis", "ual:PassengerMember"),),
    },
    "LUV": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
    },
    "SAVE": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "flyy:ProductsAndServicesPassengerMember",
    },
    "SNCY": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
    },
    "HA": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:PassengerMember",
        # Hawaiian deregistered from SEC reporting (Form 15-12G, 2024-09-30)
        # after merging into Alaska Air Group; last filing covers 2024 Q2.
    },
    # SKYW, RJET: intentionally excluded -- capacity-purchase carriers whose
    # revenue is contractual fee revenue from major-airline partners, not
    # passenger fares (see module docstring). VA: no filings after 2016
    # (merged into Alaska before the post-2018 dimensional-tagging cutover),
    # so this tier is not applicable; pre-2018 periods are covered by the
    # deprecated-tag path in xbrl.py. ALGT: also excluded here, but for a
    # different reason -- it reports Passenger Revenue as its own live,
    # non-dimensional us-gaap tag (RevenueFromContractWithCustomerExcluding-
    # AssessedTax with no axis at all), so it never needs this dimensional
    # path and is handled directly in xbrl.py instead.
}

# Cargo Revenue: same mechanism, only where a filer discloses a distinct,
# cargo-only line as a single-axis ProductOrServiceAxis member.
#
# Excluded and why:
# - JBLU, SAVE, ULCC: no cargo business and no cargo-related tag at all.
# - HA: only exposes a combined "Cargo and Other Miscellaneous" bucket
#   (ha:ProductandServiceOtherCargoandOtherMiscellaneousMember) with no
#   finer sub-component anywhere in its revenue disaggregation -- confirmed
#   by listing every dimension/member pair it uses; there is no cargo-only
#   tag to isolate, so using the combined figure would mislabel other
#   revenue as cargo.
# - SKYW, RJET: excluded for the same business-model reason as the passenger
#   map (see module docstring).
CARGO_REVENUE_DIMENSIONAL_MAP: dict[str, dict[str, str]] = {
    "AAL": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:CargoAndFreightMember",
    },
    "ALK": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "alk:CargoServicesMember",
        # ALK's channel-level alk:CargoandOtherRevenueMember bucket combines
        # this cargo-only sub-component with a separate OtherServicesMember
        # ($77M + $86M = $163M for Q2 2026) -- match on the finer product-
        # level member, not the channel-level bucket, to get cargo alone.
    },
    "DAL": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:CargoAndFreightMember",
    },
    "UAL": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:CargoAndFreightMember",
        "legacy_concepts": ("CargoAndFreightRevenue", "CargoRevenue"),
        "legacy_dimensions": (("us-gaap:ProductOrServiceAxis", "ual:CargoAndFreightMember"),),
    },
    "LUV": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:CargoAndFreightMember",
    },
    "SNCY": {
        "concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "axis": "srt:ProductOrServiceAxis",
        "member": "us-gaap:CargoAndFreightMember",
    },
}


# Pre-2019 (pre-Inline XBRL) instance documents explicitly prefix every
# element with "xbrli:" (e.g. <xbrli:context>, <xbrli:startDate>); modern
# ones declare that namespace as the default and leave elements unprefixed.
# Both styles must match, or older filings silently parse to zero contexts.
_CONTEXT_BLOCK_RE = re.compile(r'<(?:xbrli:)?context id="([^"]+)">(.*?)</(?:xbrli:)?context>', re.DOTALL)
_EXPLICIT_MEMBER_RE = re.compile(
    r'<xbrldi:explicitMember dimension="([^"]+)">([^<]+)</xbrldi:explicitMember>'
)
_PERIOD_RE = re.compile(
    r"<(?:xbrli:)?startDate>([^<]+)</(?:xbrli:)?startDate>\s*<(?:xbrli:)?endDate>([^<]+)</(?:xbrli:)?endDate>"
    r"|<(?:xbrli:)?instant>([^<]+)</(?:xbrli:)?instant>"
)


def _parse_contexts(instance_xml: str) -> dict[str, dict[str, Any]]:
    """Map contextId -> {"members": [(axis, member), ...], "start": ..., "end": ...}."""
    contexts: dict[str, dict[str, Any]] = {}
    for cid, body in _CONTEXT_BLOCK_RE.findall(instance_xml):
        members = _EXPLICIT_MEMBER_RE.findall(body)
        period_match = _PERIOD_RE.search(body)
        start = end = None
        if period_match:
            if period_match.group(3):
                start = end = period_match.group(3)
            else:
                start, end = period_match.group(1), period_match.group(2)
        contexts[cid] = {"members": members, "start": start, "end": end}
    return contexts


def _facts_for_concept(instance_xml: str, concept: str) -> list[tuple[str, float]]:
    """Return (contextRef, value) pairs for a namespaced concept, any attribute order."""
    pattern = re.compile(
        rf"<([A-Za-z_][\w.-]*):{concept}([^>]*)>([\-0-9.]+)</\1:{concept}>"
    )
    out: list[tuple[str, float]] = []
    for _, attrs, val in pattern.findall(instance_xml):
        cref_match = re.search(r'contextRef="([^"]+)"', attrs)
        if cref_match:
            out.append((cref_match.group(1), float(val)))
    return out


def _context_matches_period(ctx: dict[str, Any], year: int, period: str) -> bool:
    """Match a context's start/end dates to a logical year/period window."""
    if not ctx["end"]:
        return False
    try:
        end = datetime.strptime(ctx["end"], "%Y-%m-%d")
    except ValueError:
        return False
    if end.year != year:
        return False
    end_month = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12, "FY": 12}[period]
    if end.month != end_month:
        return False
    if period == "FY":
        return ctx["start"] is not None
    if not ctx["start"]:
        return False
    try:
        start = datetime.strptime(ctx["start"], "%Y-%m-%d")
    except ValueError:
        return False
    days = (end - start).days
    return 80 <= days <= 105  # single quarter, not a YTD cumulative period


def _extract_dimensional_revenue_component(
    instance_xml: str,
    mapping: dict[str, str] | None,
    year: int,
    period: str,
    direct_fallback_concepts: tuple[str, ...] = (),
) -> float | None:
    """A single revenue component from dimensional XBRL facts, given a mapping."""
    if not mapping:
        return None

    contexts = _parse_contexts(instance_xml)
    concepts = (
        mapping["concept"],
        "SalesRevenueServicesNet",
        *mapping.get("legacy_concepts", ()),
    )
    facts = [fact for concept in concepts for fact in _facts_for_concept(instance_xml, concept)]

    candidates: list[tuple[int, float]] = []
    for cref, val in facts:
        ctx = contexts.get(cref)
        if not ctx or not _context_matches_period(ctx, year, period):
            continue
        members = dict(ctx["members"])
        if members.get(mapping["axis"]) != mapping["member"]:
            continue
        # Prefer the context with the fewest additional dimensions, to avoid
        # picking a further sub-breakout (e.g. by geography) instead of the
        # single-axis total for the member.
        candidates.append((len(members), val))

    if candidates:
        candidates.sort(key=lambda c: c[0])
        return candidates[0][1]

    legacy_candidates: list[tuple[int, float]] = []
    for axis, member in mapping.get("legacy_dimensions", ()):
        for cref, val in facts:
            ctx = contexts.get(cref)
            if not ctx or not _context_matches_period(ctx, year, period):
                continue
            members = dict(ctx["members"])
            if members.get(axis) == member:
                legacy_candidates.append((len(members), val))
    if legacy_candidates:
        legacy_candidates.sort(key=lambda c: c[0])
        return legacy_candidates[0][1]

    direct_candidates: list[tuple[int, float]] = []
    for concept in direct_fallback_concepts:
        for cref, val in _facts_for_concept(instance_xml, concept):
            ctx = contexts.get(cref)
            if ctx and _context_matches_period(ctx, year, period):
                direct_candidates.append((len(ctx["members"]), val))
    if direct_candidates:
        direct_candidates.sort(key=lambda c: c[0])
        return direct_candidates[0][1]
    return None


def extract_dimensional_passenger_revenue(
    instance_xml: str, ticker: str, year: int, period: str
) -> float | None:
    """Passenger Revenue from a filing's dimensional XBRL facts, if mapped."""
    return _extract_dimensional_revenue_component(
        instance_xml,
        PASSENGER_REVENUE_DIMENSIONAL_MAP.get(ticker),
        year,
        period,
    )


def extract_dimensional_cargo_revenue(
    instance_xml: str, ticker: str, year: int, period: str
) -> float | None:
    """Cargo Revenue from a filing's dimensional XBRL facts, if mapped."""
    return _extract_dimensional_revenue_component(
        instance_xml,
        CARGO_REVENUE_DIMENSIONAL_MAP.get(ticker),
        year,
        period,
        ("CargoAndFreightRevenue",) if year <= 2019 else (),
    )



def extract_operating_statistics(
    primary_html: str, ticker: str, year: int, period: str
) -> dict[str, float | None]:
    """ASM, RPM, and Profit Sharing from the MD&A "Operating Statistics" table.

    Not yet implemented. These metrics have no XBRL representation (standard
    or custom taxonomy) for any airline verified so far, so they can only
    come from parsing the filing's rendered HTML. This is a real HTML-table
    layout problem (headers, units, footnotes vary by filer and can change
    year to year) and needs per-ticker verification before being trusted,
    the same way the dimensional Passenger Revenue map was built up.
    """
    raise NotImplementedError(
        "Operating-statistics HTML parsing is not yet implemented; "
        "ASM/RPM/Profit Sharing remain manual until this is built."
    )


def extract_filing_metrics(
    client: EdgarClient,
    cik: str,
    filing: Filing,
    ticker: str,
    year: int,
    period: str,
) -> dict[str, float | None]:
    """Extract whichever manual metrics this filing can supply for one period.

    Tries the precise, verified dimensional-XBRL paths for Passenger and
    Cargo Revenue first; falls through to None (manual CSV wins for
    Passenger Revenue; Cargo Revenue and RPM/ASM/Profit Sharing have no
    manual fallback) for anything unresolved.
    """
    result: dict[str, float | None] = {
        "Passenger Revenue": None,
        "Cargo Revenue": None,
        "RPM": None,
        "ASM": None,
        "Profit Sharing": None,
    }

    if ticker in PASSENGER_REVENUE_DIMENSIONAL_MAP or ticker in CARGO_REVENUE_DIMENSIONAL_MAP:
        try:
            instance_xml = client.fetch_instance_document(cik, filing)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch instance document for %s %s: %s", ticker, filing.accession, exc)
            instance_xml = None
        if instance_xml:
            result["Passenger Revenue"] = extract_dimensional_passenger_revenue(
                instance_xml, ticker, year, period
            )
            result["Cargo Revenue"] = extract_dimensional_cargo_revenue(
                instance_xml, ticker, year, period
            )

    return result


_QUARTER_END_MONTH_DAY = {"Q1": (3, 31), "Q2": (6, 30), "Q3": (9, 30), "FY": (12, 31)}


def _filing_search_window(year: int, period: str) -> tuple[datetime, datetime]:
    """Filing-date window sized to real-world 10-Q/10-K filing timelines.

    ``config.PeriodSpec.date_window()`` pads only ~1 month past quarter-end,
    which is too tight: airlines often file 10-Qs 25-45 days after quarter
    close, right at or past that boundary. That mismatch caused the window
    to miss the correct filing (or pick up the prior quarter's, filed early
    in the window) for many periods. Use a wider, filing-timeline-based
    window instead, independent of PeriodSpec's original (different) use.

    The lower bound stays small: DAL is the fastest observed filer, filing
    10-Qs as early as 9 days after period end.
    """
    month, day = _QUARTER_END_MONTH_DAY[period]
    period_end = datetime(year, month, day)
    if period == "FY":
        return period_end + timedelta(days=15), period_end + timedelta(days=100)
    return period_end + timedelta(days=5), period_end + timedelta(days=70)


def extract_year_metrics(
    client: EdgarClient, cik: str, ticker: str, year: int
) -> dict[str, dict[str, float | None]]:
    """Passenger/Cargo Revenue for every period in one year, deriving Q4.

    Fetches one filing per quarter (10-Q) plus the 10-K for FY -- this is the
    expensive per-filing tier, so call it only for tickers with at least one
    verified dimensional mapping. Q4 is derived as FY - (Q1 + Q2 + Q3), same
    as the company-facts extraction in xbrl.py, since airlines do not file a
    standalone Q4 report.
    """
    metrics = ("Passenger Revenue", "Cargo Revenue")
    applicable = {
        m
        for m, mapping in (
            ("Passenger Revenue", PASSENGER_REVENUE_DIMENSIONAL_MAP),
            ("Cargo Revenue", CARGO_REVENUE_DIMENSIONAL_MAP),
        )
        if ticker in mapping
    }
    result: dict[str, dict[str, float | None]] = {
        p: {m: None for m in metrics} for p in ("Q1", "Q2", "Q3", "Q4", "FY")
    }
    if not applicable:
        return result

    for period in ("Q1", "Q2", "Q3", "FY"):
        start, end = _filing_search_window(year, period)
        form = "10-K" if period == "FY" else "10-Q"
        filings = [f for f in client.filings_in_window(cik, start, end, (form,)) if f.form == form]
        if not filings:
            log.warning("No %s filing found for %s %s%s in window %s..%s", form, ticker, year, period, start.date(), end.date())
            continue
        # Earliest match in the window is the filing covering this period;
        # a later match would be the next period's filing.
        filing = min(filings, key=lambda f: f.filing_date)
        try:
            instance_xml = client.fetch_instance_document(cik, filing)
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch instance document for %s %s %s: %s", ticker, year, period, exc)
            continue
        if "Passenger Revenue" in applicable:
            result[period]["Passenger Revenue"] = extract_dimensional_passenger_revenue(
                instance_xml, ticker, year, period
            )
        if "Cargo Revenue" in applicable:
            result[period]["Cargo Revenue"] = extract_dimensional_cargo_revenue(
                instance_xml, ticker, year, period
            )

    for metric in applicable:
        fy = result["FY"][metric]
        parts = [result[p][metric] for p in ("Q1", "Q2", "Q3")]
        if fy is not None and all(p is not None for p in parts):
            result["Q4"][metric] = fy - sum(parts)  # type: ignore[operator]

    return result
