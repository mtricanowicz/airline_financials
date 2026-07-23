"""Insights page.

Displays the precomputed, LLM-generated insights for a selected airline, year,
and period. Summaries are produced offline by the core pipeline and read here
from static JSON, so no API calls happen at view time.
"""

from __future__ import annotations

import streamlit as st

from lib.data import load_financials, load_insights
from lib.formatting import AIRLINE_NAMES, airline_header_html

st.header(":material/emoji_objects: Insights")
st.info(
    "Insights are extracted from the airlines' SEC filings and summarized by an "
    "AI model. Summaries may contain inaccuracies.",
    icon=":material/info:",
)

insights = load_insights()
financials = load_financials()

if not insights:
    st.warning("No insights found. Run the insights pipeline first (see core/README.md).")
    st.stop()

airlines = sorted(insights.keys())

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    airline = st.selectbox("Airline", airlines, index=None, placeholder="Select")
with col2:
    years = sorted(insights.get(airline, {}).keys(), reverse=True) if airline else []
    year = st.selectbox("Year", years, index=None, placeholder="Select")
with col3:
    periods = sorted(insights.get(airline, {}).get(year, {}).keys()) if airline and year else []
    period = st.selectbox("Period", periods, index=None, placeholder="Select")

if not (airline and year and period):
    st.caption("Select an airline, year, and period to view insights.")
    st.stop()

name = AIRLINE_NAMES.get(airline, airline)
st.markdown(
    airline_header_html(
        airline,
        f"{name} ({airline}) | {year}{period}",
        heading_level=3,
        logo_height_em=2.00,
        logo_before_text=True,
        gap_rem=0.55,
    ),
    unsafe_allow_html=True,
)
st.markdown("<div style='border-bottom:1px solid rgba(49, 51, 63, 0.2); margin:0 0 1rem 0;'></div>", unsafe_allow_html=True)

summary = insights.get(airline, {}).get(year, {}).get(period)
if summary:
    st.markdown(summary)
else:
    st.error("No summary is available for the selected period.", icon=":material/report:")
