"""Presentation constants and value formatting shared across the pages.

These mirror the display conventions of the original single-file app so the
rebuilt multipage version renders identical figures, colors, and definitions.
"""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import pandas as pd

AIRLINE_COLORS: dict[str, str] = {
    "AAL":  "#9DA6AB",
    "DAL":  "#C01933",
    "UAL":  "#005daa",
    "ALK":  "#01426a",
    "LUV":  "#f9b612",
    "JBLU": "#0000aa",
    "ULCC": "#248168",
    "HA":   "#4b2d89",
    "SAVE": "#ffec00",
    "ALGT": "#f48220",
    "SNCY": "#f58232",
}

AIRLINE_NAMES: dict[str, str] = {
    "AAL":  "American Airlines",
    "DAL":  "Delta Air Lines",
    "UAL":  "United Airlines",
    "ALK":  "Alaska Airlines",
    "LUV":  "Southwest Airlines",
    "JBLU": "JetBlue Airways",
    "ULCC": "Frontier Airlines",
    "HA":   "Hawaiian Airlines",
    "SAVE": "Spirit Airlines",
    "ALGT": "Allegiant Air",
    "SNCY": "Sun Country Airlines",
}

AIRLINE_LOGO_FILES: dict[str, str] = {
    "AAL":  "logo_AAL.png",
    "DAL":  "logo_DAL.png",
    "UAL":  "logo_UAL.png",
    "ALK":  "logo_ALK.png",
    "LUV":  "logo_LUV.png",
    "JBLU": "logo_JBLU.png",
    "ULCC": "logo_ULCC.png",
    "HA":   "logo_HA.png",
    "SAVE": "logo_SAVE.png",
    "ALGT": "logo_ALGT.png",
    "SNCY": "logo_SNCY.png",
}

AIRLINE_GROUPS = {
    "Major Global Airlines": [
        "AAL",
        "DAL",
        "UAL",
    ],
    "Large National Airlines": [
        "LUV",
    ],
    "Small & Midsize Airlines": [
        "ALK",
        "JBLU",
        "ULCC",
        "HA",
        "SAVE",
        "ALGT",
        "SNCY",
    ],
    "Defunct Airlines": [
        "HA",
        "SAVE",
        "SNCY",
    ],
}

# Metrics reported in dollars; displayed in millions with a currency prefix.
CURRENCY_METRICS = [
    "Operating Revenue",
    "Passenger Revenue",
    "Operating Expenses",
    "Operating Income",
    "Net Income",
    "Long-Term Debt",
    "Profit Sharing",
]

# Metrics scaled into millions for display but shown without a currency symbol.
MILLIONS_METRICS = CURRENCY_METRICS + ["RPM", "ASM"]

# Unit metrics reported in cents.
CENTS_METRICS = ["Yield", "TRASM", "PRASM", "CASM"]

# Metrics reported as percentages.
PERCENT_METRICS = ["Operating Margin", "Net Margin", "Load Factor"]

METRIC_GROUPS = {
    "Earnings": [
        "Operating Revenue",
        "Operating Expenses",
        "Operating Income",
        "Net Income",
        "Operating Margin",
        "Net Margin",
    ],
    "Debt & Liquidity": [
        "Long-Term Debt",
    ],
    "Unit Performance": ["Yield", "TRASM", "PRASM", "CASM"],
}

METRIC_DEFINITIONS: list[tuple[str, str]] = [
    ("Operating Revenue", "Total amount earned from operations."),
    ("Passenger Revenue*", "Revenue primarily composed of passenger ticket sales, loyalty travel awards, and travel-related services performed in conjunction with a passenger's flight."),
    ("Operating Expenses", "Total amount of costs incurred from operations."),
    ("Operating Income", "Income from operations. Operating Revenue minus Operating Expenses."),
    ("Net Income", "Profit."),
    ("Operating Margin", "Operating Income divided by Operating Revenue"),
    ("Net Margin", "Percentage of profit earned for each dollar in revenue. Net Income divided by Operating Revenue."),
    ("Long-Term Debt", "Total long-term debt net of current maturities."),
    ("Profit Sharing*", "Amount of income set aside to fund employee profit sharing programs. NOTE: Quarterly reporting by AAL and UAL of this metric is inconsistent. Data provided may have been obtained from internal sources or estimated by proportioning the annual profit sharing reported by the quarterly operating income reported."),
    ("Revenue Passenger Mile (RPM)*", "A basic measure of sales volume. One RPM represents one passenger flown one mile."),
    ("Available Seat Mile (ASM)*", "A basic measure of production. One ASM represents one seat flown one mile."),
    ("Load Factor*", "The percentage of available seats that are filled with revenue passengers. RPMs divided by ASMs."),
    ("Yield*", "A measure of airline revenue derived by dividing Passenger Revenue by RPMs."),
    ("Total Revenue per Available Seat Mile (TRASM)*", "Operating Revenue divided by ASMs."),
    ("Passenger Revenue per Available Seat Mile (PRASM)*", "Passenger Revenue divided by ASMs."),
    ("Cost per Available Seat Mile (CASM)*", "Operating Expenses divided by ASMs."),
    ("\\*", "Could not be retrieved automatically from SEC filing data. This metric is sourced directly from SEC filings through manual review or derived from filing data collected manually.")
]


def format_metric_value(value: float | None, metric: str) -> str | None:
    """Format one scaled value for display according to its metric type.

    Currency and millions metrics are assumed to already be divided by 1e6 and
    cents metrics already multiplied by 100 by the caller.
    """
    if value is None or pd.isna(value):
        return None
    base = metric.replace(" (millions)", "")
    if base in CURRENCY_METRICS:
        sign = "-$" if value < 0 else "$"
        return f"{sign}{abs(value):,.0f}"
    if base in CENTS_METRICS:
        return f"{value:,.2f}\u00A2"
    if base in PERCENT_METRICS:
        return f"{value:,.2f}%"
    return f"{value:,.0f}"


def color_positive_negative(value: object) -> str:
    """Style helper: green for positive, red for negative, else no color."""
    if value is None:
        return ""
    try:
        numeric = float(value[:-1]) if isinstance(value, str) else float(value)
    except (ValueError, TypeError):
        return ""
    if numeric > 0:
        return "color: green"
    if numeric < 0:
        return "color: red"
    return ""


def pct_diff(base: float | None, comparison: float | None) -> float | None:
    """Signed percentage difference of ``comparison`` relative to ``base``."""
    if base is None or comparison is None or pd.isna(base) or pd.isna(comparison):
        return None
    if base == 0:
        return float("inf") if comparison != 0 else 0.0
    magnitude = round(abs((comparison - base) / base) * 100, 2)
    if base < 0 < comparison:
        return magnitude
    if base > 0 > comparison:
        return -magnitude
    if base > comparison:
        return -magnitude
    return magnitude


def get_airline_logo_path(airline: str) -> Path | None:
    """Return a local logo path for an airline ticker, or ``None`` if missing."""
    filename = AIRLINE_LOGO_FILES.get(airline)
    if not filename:
        return None
    logo_path = Path(__file__).resolve().parents[2] / "assets" / "logos" / filename
    return logo_path if logo_path.exists() else None


def airline_label_html(
    airline: str,
    text: str | None = None,
    logo_height_em: float = 1.05,
    logo_before_text: bool = True,
    gap_rem: float = 0.28,
    font_weight: int | str = 400,
) -> str:
    """Return normal inline text with the airline logo beside it."""
    display_text = text or airline
    logo_path = get_airline_logo_path(airline)
    image_html = ""
    if logo_path is not None:
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        image_html = (
            f"<img src='data:image/png;base64,{encoded}' "
            f"alt='{escape(airline)} logo' "
            f"style='"
            f"height:{logo_height_em:.2f}em;"
            f"width:auto;"
            f"display:block;"
            f"object-fit:contain;"
            f"flex:0 0 auto;"
            f"'/>"
        )
    text_html = (
        f"<span style='"
        f"margin:0;"
        f"padding:0;"
        f"line-height:1.2;"
        f"font-weight:{font_weight};"
        f"'>"
        f"{escape(display_text)}"
        f"</span>"
    )
    if logo_before_text:
        content_html = f"{image_html}{text_html}"
    else:
        content_html = f"{text_html}{image_html}"
    return (
        f"<span style='"
        f"display:inline-flex;"
        f"align-items:center;"
        f"gap:{gap_rem:.2f}rem;"
        f"vertical-align:middle;"
        f"'>"
        f"{content_html}"
        f"</span>"
    )


def airline_header_html(
    airline: str,
    text: str,
    heading_level: int = 4,
    logo_height_em: float = 1.05,
    logo_before_text: bool = False,
    gap_rem: float = 0.28,
) -> str:
    """Return inline header HTML with a centered airline logo and title text."""
    heading_level = min(max(heading_level, 1), 6)
    logo_path = get_airline_logo_path(airline)
    image_html = ""
    if logo_path is not None:
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        image_html = (
            f"<img src='data:image/png;base64,{encoded}' "
            f"alt='{escape(airline)} logo' "
            f"style='height:{logo_height_em:.2f}em;width:auto;display:block;object-fit:contain;flex:0 0 auto;'/>"
        )
    heading_tag = f"h{heading_level}"
    if logo_before_text:
        content_html = f"{image_html}<{heading_tag} style='margin:0;padding:0;line-height:1.2;'>{escape(text)}</{heading_tag}>"
    else:
        content_html = f"<{heading_tag} style='margin:0;padding:0;line-height:1.2;'>{escape(text)}</{heading_tag}>{image_html}"
    return (
        f"<div style='display:flex;align-items:center;gap:{gap_rem:.2f}rem;margin:0.05rem 0 0.12rem 0;'>"
        f"{content_html}"
        "</div>"
    )
