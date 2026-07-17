"""Latest Results page.

Shows the most recent full-year and quarterly figures for all airlines and all
metrics, optionally compared against a base airline.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lib.data import load_financials, split_by_period
from lib.formatting import (
    CENTS_METRICS,
    METRIC_DEFINITIONS,
    MILLIONS_METRICS,
    color_positive_negative,
    format_metric_value,
    pct_diff,
)

st.header(":material/calendar_today: Latest Results")


@st.dialog("Metric definitions", width="large")
def show_metric_definitions() -> None:
    for metric, definition in METRIC_DEFINITIONS:
        st.markdown(f"**{metric}** - {definition}")


financials = load_financials()
if financials.empty:
    st.warning("No financial data found. Run the data build first (see core/README.md).")
    st.stop()

fy_data, q_data = split_by_period(financials)
airlines = sorted(financials["Airline"].unique())

col_a, col_b = st.columns([4, 1])
with col_b:
    default_airlines = [a for a in ["AAL", "DAL", "UAL"] if a in airlines] or airlines[:1]
    selected_airlines = st.multiselect("Airline(s)", airlines, default=default_airlines)
    selected_airlines = selected_airlines or airlines[:1]
    compare = (
        st.toggle("Compare against a base airline", value=False)
        if len(selected_airlines) > 1
        else False
    )
    base_airline = st.selectbox("Base airline", selected_airlines) if compare else selected_airlines[0]
    if st.button("Show definitions of the metrics.", icon=":material/dictionary:", use_container_width=True):
        show_metric_definitions()


def build_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Build a formatted, optionally compared summary of the latest period."""
    latest = max(data["Period"])
    snapshot = data[data["Period"] == latest].copy()
    metrics = [c for c in snapshot.columns if c not in ("Year", "Quarter", "Airline", "Period")]
    metric_order: list[str] = []
    rows = []
    for metric in metrics:
        scaled = snapshot.copy()
        display_col = metric
        if metric in MILLIONS_METRICS:
            scaled[metric] = pd.to_numeric(scaled[metric], errors="coerce") / 1_000_000
            display_col = f"{metric} (millions)"
        elif metric in CENTS_METRICS:
            scaled[metric] = pd.to_numeric(scaled[metric], errors="coerce") * 100
        metric_order.append(display_col)
        base_cell = scaled[scaled["Airline"] == base_airline][metric]
        base_val = base_cell.iloc[0] if not base_cell.empty else None
        for airline in scaled["Airline"].unique():
            cell = scaled[scaled["Airline"] == airline][metric]
            value = cell.iloc[0] if not cell.empty else None
            d = pct_diff(base_val, value)
            rows.append(
                {
                    "Metric": display_col,
                    "Airline": airline,
                    latest: format_metric_value(value, metric) or "TBA",
                    f"vs {base_airline}": None if d is None or pd.isna(d) else f"{d}%",
                }
            )
    summary = pd.DataFrame(rows).set_index(["Metric", "Airline"])
    if not compare:
        summary = summary.drop(columns=[f"vs {base_airline}"])
    summary = summary.unstack("Airline")
    summary.columns = summary.columns.swaplevel(0, 1)
    summary = summary.sort_index(axis=1, level=0)
    summary = summary.reindex(metric_order)
    if compare:
        summary = summary.drop(columns=[(base_airline, f"vs {base_airline}")], errors="ignore")
    return summary


def render(data: pd.DataFrame, title: str) -> None:
    if data.empty:
        st.info(f"No data available for {title}.")
        return
    latest = max(data["Period"])
    st.subheader(f"{title}: {latest}", divider="gray")
    summary = build_summary(data)
    if compare:
        color_cols = [
            (a, f"vs {base_airline}")
            for a in summary.columns.get_level_values(0).unique()
            if (a, f"vs {base_airline}") in summary.columns
        ]
        st.dataframe(summary.style.map(color_positive_negative, subset=color_cols), use_container_width=True)
    else:
        st.dataframe(summary, use_container_width=True)


with col_a:
    #left, right = st.columns(2)
    #with left:
        render(q_data[q_data["Airline"].isin(selected_airlines)], "Most recent quarter")
    #with right:
        render(fy_data[fy_data["Airline"].isin(selected_airlines)], "Most recent full year")
