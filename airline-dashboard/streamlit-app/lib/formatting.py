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
    "LUV":  "#f9b612",
    "ALK":  "#01426a",
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
    "LUV":  "Southwest Airlines",
    "ALK":  "Alaska Airlines",
    "JBLU": "JetBlue Airways",
    "ULCC": "Frontier Airlines",
    "HA":   "Hawaiian Airlines",
    "SAVE": "Spirit Airlines",
    "ALGT": "Allegiant Air",
    "SNCY": "Sun Country Airlines",
}

AIRLINE_IR: dict[str, str] = {
    "AAL":  "https://americanairlines.gcs-web.com/",
    "DAL":  "https://ir.delta.com/",
    "UAL":  "https://ir.united.com/",
    "LUV":  "https://www.southwestairlinesinvestorrelations.com/",
    "ALK":  "https://investor.alaskaair.com/",
    "JBLU": "https://investors.jetblue.com/",
    "ULCC": "https://ir.flyfrontier.com/",
    "HA":   None,
    "SAVE": None,
    "ALGT": "https://ir.allegiantair.com/",
    "SNCY": None,
}

AIRLINE_LOGO_FILES: dict[str, str] = {
    "AAL":  "logo_AAL.png",
    "DAL":  "logo_DAL.png",
    "UAL":  "logo_UAL.png",
    "LUV":  "logo_LUV.png",
    "ALK":  "logo_ALK.png",
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

AIRLINE_DEFUNCT_REASONS: dict[str, str] = {
    "HA":   "Merged with Alaska Airlines on September 18, 2024.",
    "SAVE": "Ceased operations on May 2, 2026.",
    "SNCY": "Merged with Allegiant Air on May 13, 2026.",
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
    font_size: str | None = None,
    logo_alignment: str = "center", # use flex-start to vertically align icons with top of text
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
        f"{f'font-size:{font_size};' if font_size else ''}"
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
        f"align-items:{logo_alignment};"
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


def about_sidebar_html() -> str:
    """Return HTML for the About section in the sidebar."""
    return """
    <div style="font-size: 0.875rem;">
        <p>
            Explore U.S. airline financial performance through clear and accessible
            comparisons and the latest full-year and quarterly metrics.
        </p>
        <p>
            The dashboard covers major U.S. passenger airlines and includes data
            beginning in 2014, a useful starting point for examining the industry
            following the major consolidation cycle of the 2000s and early 2010s when
            the legacy network airlines completed a series of mergers that reshaped
            the industry.
        </p>
        <p>
            The dashboard combines:
        </p>
        <ul>
            <li>Automatically retrieved financial metrics from SEC filings.</li>
            <li>Manually curated financial and operating metrics sourced directly from SEC filings.</li>
            <li>
                Computed performance metrics such as margins, load factor, yield,
                and unit performance derived from the sourced financial and operating data.
            </li>
        </ul>
        <p>Pages:</p>
        <ul>
            <li>
                <strong>Filtered Comparisons:</strong>
                Provides customizable views of airline financial and operating
                performance. Multiple metrics can be selected for evaluation across
                chosen airlines and reporting periods.
            </li>
            <li>
                <strong>Latest Results:</strong>
                Summarizes the most recent annual and quarterly results for easy viewing.
            </li>
            <li>
                <strong>Share Repurchases:</strong>
                Provides a high-level overview of the share repurchase programs
                undertaken by American, Delta, and United during the 2010s before
                ending with the onset of the COVID-19 pandemic.
            </li>
            <li>
                <strong>Insights:</strong>
                Delivers financial, operational, and commercial insights based on
                airline SEC filings. User selections retrieve content for a particular
                airline and reporting period, returning a summarization generated by an
                OpenAI model.
            </li>
        </ul>
        <p>
            Unless otherwise noted, metrics are sourced directly from, or calculated
            using data reported in, airline Forms 10-Q, 8-K, and 10-K filed with the
            SEC. Metrics that cannot be retrieved automatically are collected manually
            from those same filings.
        </p>
    </div>
    """


def get_other_dashboard_link(
    icon_path: Path,
    name: str,
    link: str | None = None,
) -> str:
    """Return an icon and dashboard name, linked only when a URL is provided."""
    safe_name = escape(name)
    try:
        image_data = base64.b64encode(icon_path.read_bytes()).decode("ascii")
        content = (
            f'<img src="data:image/png;base64,{image_data}" '
            f'alt="{safe_name} icon" '
            f'width="24" height="24" '
            f'style="object-fit:contain;" />'
            f"<span>{safe_name}</span>"
        )
    except OSError:
        content = f"<span>{safe_name}</span>"
    shared_style = (
        "text-decoration:none;"
        "display:inline-flex;"
        "align-items:center;" 
        "gap:8px;"
    )
    if link:
        safe_link = escape(link, quote=True)
        return (
            f'<a href="{safe_link}" style="{shared_style}">'
            f"{content}"
            "</a>"
        )
    return (
        f'<span style="{shared_style}">'
        f"{content}"
        "</span>"
    )


def stock_ticker_html(
    quotes: dict[str, dict],
    unavailable_message: str = "Stock prices temporarily unavailable.",
) -> str:
    """Return scrolling financial-news-style stock ticker HTML."""
    items: list[str] = []
    for ticker, quote in quotes.items():
        price = quote.get("price")
        change = quote.get("change")
        change_percent = quote.get("change_percent")
        if price is None:
            continue
        safe_ticker = escape(ticker)
        if change is None or change_percent is None:
            movement_html = ""
        else:
            change = float(change)
            change_percent = float(change_percent)
            if change > 0:
                movement_class = "stock-ticker-positive"
                arrow = "▲"
                sign = "+"
            elif change < 0:
                movement_class = "stock-ticker-negative"
                arrow = "▼"
                sign = ""
            else:
                movement_class = "stock-ticker-neutral"
                arrow = "—"
                sign = ""
            movement_html = (
                f'<span class="{movement_class}">'
                f"{arrow} {sign}{change:,.2f} "
                f"({sign}{change_percent:.2f}%)"
                "</span>"
            )
        items.append(
            f"""
            <span class="stock-ticker-item">
                <strong>{safe_ticker}</strong>
                <span>${float(price):,.2f}</span>
                {movement_html}
            </span>
            """
        )
    if items:
        content = "".join(items)

        ticker_content = f"""
            <div class="stock-ticker-track">
                <div class="stock-ticker-sequence">
                    {content}
                </div>
                <div class="stock-ticker-sequence" aria-hidden="true">
                    {content}
                </div>
            </div>
        """
    else:
        ticker_content = f"""
            <div class="stock-ticker-unavailable">
                {escape(unavailable_message)}
            </div>
        """
    return f"""
    <style>
        .stock-ticker-shell {{
            width: 100%;
            overflow: hidden;
            white-space: nowrap;
            background: #111827;
            color: #ffffff;
            border-top: 1px solid #374151;
            padding: 0.45rem 0;
            font-size: 0.875rem;
        }}
        .stock-ticker-track {{
            display: flex;
            width: max-content;
            animation: stock-ticker-scroll 40s linear infinite;
        }}
        .stock-ticker-shell:hover .stock-ticker-track {{
            animation-play-state: paused;
        }}
        .stock-ticker-sequence {{
            display: inline-flex;
            align-items: center;
        }}
        .stock-ticker-item {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            margin-right: 2rem;
        }}
        .stock-ticker-unavailable {{
            width: 100%;
            text-align: center;
            color: #d1d5db;
        }}
        .stock-ticker-positive {{
            color: #22c55e;
        }}
        .stock-ticker-negative {{
            color: #ef4444;
        }}
        .stock-ticker-neutral {{
            color: #d1d5db;
        }}
        @keyframes stock-ticker-scroll {{
            from {{
                transform: translateX(0);
            }}

            to {{
                transform: translateX(-50%);
            }}
        }}
    </style>
    <div class="stock-ticker-shell">
        {ticker_content}
    </div>
    """


def fixed_stock_ticker_html(
    quotes: dict[str, dict],
    activated: bool,
) -> str:
    ticker_html = stock_ticker_html(quotes) if activated else ""
    return f"""
    <style>
        :root {{
            --stock-ticker-height: 2rem;
        }}
        .fixed-stock-ticker {{
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100vw;
            height: var(--stock-ticker-height);
            overflow: hidden;
            margin: 0;
            padding: 0;

            z-index: 50;

            visibility: {"visible" if activated else "hidden"};
            opacity: {"1" if activated else "0"};
            pointer-events: {"auto" if activated else "none"};

            transition: opacity 150ms ease;
        }}
    </style>
    <div class="fixed-stock-ticker">
        {ticker_html}
    </div>
    """
