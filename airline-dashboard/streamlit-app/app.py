"""Airline Financial Dashboard - Streamlit multipage entry point.

This is the cleanup track: a faithful, faster rebuild of the original single-file
app. Each former tab is now its own page, so navigating between them does not
re-execute the others. Data loading is cached, and the manual rerun and
session-state workarounds of the original have been removed. Streamlit's natural
rerun-on-interaction model is sufficient once state is derived from widgets and
cached loaders.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from lib.data import (
    fetch_live_quotes,
)

from lib.formatting import (
    AIRLINE_NAMES,
    AIRLINE_IR,
    AIRLINE_GROUPS,
    AIRLINE_DEFUNCT_REASONS,
    about_sidebar_html,
    airline_label_html,
    get_other_dashboard_link,
    fixed_stock_ticker_html,
)

_APP_DIR = Path(__file__).parent
_ASSETS_DIR = _APP_DIR.parent / "assets"
_BRANDING_DIR = _ASSETS_DIR / "branding"


def _airline_sidebar_line(airline: str) -> str:
    """Return one formatted airline line for the sidebar list."""
    if airline in AIRLINE_DEFUNCT_REASONS:
        text = f"*{AIRLINE_NAMES.get(airline, airline)} ({airline}) - {AIRLINE_DEFUNCT_REASONS[airline]}*"
    else:
        text = f"{AIRLINE_NAMES.get(airline, airline)} ([{airline}]({AIRLINE_IR.get(airline, '#')}))"
    return airline_label_html(
        airline,
        text=text,
        logo_height_em=1.05,
        logo_before_text=True,
        gap_rem=0.25,
        font_size="0.875rem",
        logo_alignment="flex-start",
    )

st.set_page_config(
    page_title="Airline Financial Dashboard",
    page_icon=str(_BRANDING_DIR / "site_favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": """
        Financial data is assembled from airline SEC filings and standardized into a common quarterly and annual reporting structure. Automatically retrieved XBRL facts are supplemented with manually reviewed filing data where structured values are unavailable or unreliable.

        Derived metrics are calculated from the underlying reported financial and operating data. Historical values may reflect later comparative disclosures, restatements, or issuer-specific reporting practices.

        **Created by:** Michael Tricanowicz
        """
    },
)


# Site logo / title banner, shown on every page.
st.image(
    str(_BRANDING_DIR / "site_title.png"),
    caption="Explore US Airline Financial Performance",
)


# Collapsible sidebar with reference information including sections for About, Airlines Covered, and Other Industry Dashboards
# Sidebar also includes a live stock ticker toggle
st.logo(
    str(_BRANDING_DIR / "site_title.png"),
    link="https://airline.industryfinancials.com",
    icon_image=str(_BRANDING_DIR / "site_favicon.png"),
)
with st.sidebar:
    st.toggle("Activate Stock Ticker", value=True, key="activate_stock_ticker")
    with st.expander("About the Airline Financial Dashboard", expanded=False):
        st.markdown(
            about_sidebar_html(),
            unsafe_allow_html=True
        )
    with st.expander("Airlines Covered", expanded=True):
        for group in (g for g in AIRLINE_GROUPS if g != "Defunct Airlines"):
            st.markdown(f"#### {group}", unsafe_allow_html=True)
            for airline in sorted(AIRLINE_GROUPS[group], key=lambda airline: AIRLINE_NAMES.get(airline, airline)):
                st.markdown(_airline_sidebar_line(airline), unsafe_allow_html=True)
        st.markdown("<small><br>Active airlines<br>*Defunct airlines*</small>", unsafe_allow_html=True)
    with st.expander("Other Industry Dashboards", expanded=True):
        st.markdown(
            get_other_dashboard_link(
                icon_path=_BRANDING_DIR / "site_favicon_steel.png",
                name="Steel Dashboard (Coming Soon)",
                link=None
            ),
            unsafe_allow_html=True
        )


# App page definitions and navigation setup.
# Directory containing the view scripts for the different pages of the app.
_VIEWS = _APP_DIR / "views"

# List of pages for the app.
pages = [
    st.Page(str(_VIEWS / "comparisons.py"), title="Filtered Comparisons", icon=":material/finance_mode:", default=True),
    st.Page(str(_VIEWS / "latest_results.py"), title="Latest Results", icon=":material/calendar_today:"),
    st.Page(str(_VIEWS / "share_repurchases.py"), title="Share Repurchases", icon=":material/paid:"),
    st.Page(str(_VIEWS / "insights.py"), title="Insights", icon=":material/emoji_objects:"),
]

# Register the pages without the sidebar nav, then render a compact link row
# below the logo so the available pages stay visible without the sidebar.
current_page = st.navigation(pages, position="hidden")

# Size each link to its label (plus room for the icon) and push the leftover
# width into a trailing spacer so the links stay grouped and compact.
nav_weights = [len(page.title) + 5 for page in pages]
nav_cols = st.columns([*nav_weights, sum(nav_weights)], gap="small")
for col, page in zip(nav_cols, pages):
    with col:
        st.page_link(page, width="stretch")


# Stock ticker setup and rendering
# Define the list of stock tickers to display, excluding defunct airlines.
STOCK_TICKERS = tuple(
    ticker
    for ticker in AIRLINE_NAMES
    if ticker not in AIRLINE_GROUPS.get("Defunct Airlines", [])
)
# Define the stock ticker rendering function and schedule it to run every 60 seconds.
ticker_placeholder = st.empty()
@st.fragment(run_every="60s")
def render_stock_ticker() -> None:
    activated = st.session_state.get("activate_stock_ticker", True)
    quotes = fetch_live_quotes(STOCK_TICKERS) if activated else {}
    ticker_placeholder.html(
        fixed_stock_ticker_html(
            quotes,
            activated=activated,
        )
    )
# Render the stock ticker with activation controlled by the sidebar toggle.
render_stock_ticker()


# Run the current page.
current_page.run()

