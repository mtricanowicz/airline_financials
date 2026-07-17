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

_APP_DIR = Path(__file__).parent
_ASSETS_DIR = _APP_DIR.parent / "assets"
_BRANDING_DIR = _ASSETS_DIR / "branding"

st.set_page_config(
    page_title="Airline Financial Dashboard",
    page_icon=str(_BRANDING_DIR / "site_favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "About": """
        ## Airline Financial Dashboard
        Explore recent US airline financial performance with easy-to-read comparisons and the latest full-year and quarterly metrics.

        This dashboard covers major US carriers and combines:
        - auto-derived metrics from SEC filings,
        - manually curated operating metrics,
        - and computed performance metrics like margins, yield, and unit costs.

        Pages:
        - The **Filtered Comparisons** tab provides customizable views of airline financials. Several metrics can be selected for evaluation over chosen reporting periods.\n
        - The **Latest Results** tab gives a summary of the most recent annual and quarterly results for easy viewing.\n
        - The **Share Repurchases** tab contains a high level overview of the share buyback programs by the three major legacy airilnes (AAL, DAL, UAL) that were carried out in the 2010s and ended with the onset of the Covid-19 pandemic.\n
        - The **Insights** tab delivers financial, operational, and commercial insights based on the airilne's SEC filings. User selections prompt retrieval of content for a particular airline and time period with summarization provided by an OpenAI LLM.\n

        Investor relations links:
        [AAL](https://americanairlines.gcs-web.com/) | 
        [DAL](https://ir.delta.com/) | 
        [UAL](https://ir.united.com/) | 
        [LUV](https://www.southwestairlinesinvestorrelations.com/) | 
        [ALK](https://investor.alaskaair.com/) | 
        [JBLU](https://investors.jetblue.com/) | 
        [ULCC](https://ir.flyfrontier.com/)

        **Created by:** Michael Tricanowicz
        """
    },
)

# Site logo / title banner, shown on every page.
st.image(
    str(_BRANDING_DIR / "site_title.png"),
    caption="Explore US Airline Financial Performance",
)

_VIEWS = _APP_DIR / "views"

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
        st.page_link(page, use_container_width=True)

current_page.run()

