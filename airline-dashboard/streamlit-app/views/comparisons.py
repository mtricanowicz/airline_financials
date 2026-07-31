"""Filtered Comparisons page.

Lets the user compare selected metrics across airlines and periods, optionally
against a base airline, with a table and time-series and percent-difference
charts per metric. Rebuilt from the original tab without the manual rerun logic.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from lib.data import load_financials, split_by_period
from lib.formatting import (
    AIRLINE_COLORS,
    AIRLINE_NAMES,
    AIRLINE_GROUPS,
    CENTS_METRICS,
    CURRENCY_METRICS,
    EPS_DOLLAR_METRICS,
    METRIC_DEFINITIONS,
    METRIC_GROUPS,
    MILLIONS_METRICS,
    PERCENT_METRICS,
    color_positive_negative,
    format_metric_value,
    pct_diff,
    airline_label_html,
    scale_metric_for_display,
)

st.header(":material/finance_mode: Filtered Comparisons")


@st.dialog("Metric Definitions", width="large")
def show_metric_definitions() -> None:
    for metric, definition in METRIC_DEFINITIONS:
        st.markdown(f"**{metric}** - {definition}")


financials = load_financials()
if financials.empty:
    st.warning("No financial data found. Run the data build first (see core/README.md).")
    st.stop()

fy_data, q_data = split_by_period(financials)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
with st.expander("Set filters", expanded=True):
    with st.container(border=True):
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            data_type = st.radio("View Full Year or Quarterly data?", ["Full Year", "Quarterly"], horizontal=True)
        data = fy_data if data_type == "Full Year" else q_data

        years = sorted(data["Year"].unique())
        with col2:
            selected_years = st.multiselect("Select Years for comparison:", years, default=years)
        selected_years = selected_years or years

        with col3:
            if data_type == "Quarterly":
                quarters = sorted(data["Quarter"].unique())
                selected_quarters = st.multiselect("Select Quarters for comparison:", quarters, default=quarters)
                selected_quarters = selected_quarters or quarters
            else:
                selected_quarters = ["FY"]

    airlines = sorted(data["Airline"].unique())
    with st.container(border=True):
        col4, col5, col6 = st.columns([1, 3, 1])
        with col4:
            airline_group = st.radio("Select Airlines for comparison:", ["All", *[group for group in AIRLINE_GROUPS if group != "Defunct Airlines"], "Choose from active and defunct airlines"], horizontal=False, index=1)
        if airline_group == "All":
            airline_options = [a for a in airlines if a not in AIRLINE_GROUPS["Defunct Airlines"]]
            default_airlines = airline_options
        elif airline_group in AIRLINE_GROUPS:
            airline_options = [a for a in AIRLINE_GROUPS[airline_group] if a in airlines and a not in AIRLINE_GROUPS["Defunct Airlines"]]
            default_airlines = airline_options
        else:
            airline_options = airlines
            default_airlines = airlines   
        with col5:
            selected_airlines = st.multiselect("Add or remove Airlines to compare:", airline_options, default=default_airlines)
            selected_airlines = selected_airlines or airline_options[:1]
            st.markdown(
                " | ".join([
                    airline_label_html(
                        airline,
                        text=f"{AIRLINE_NAMES.get(airline, airline)} ({airline})",
                        logo_height_em=0.95,
                        logo_before_text=True,
                        gap_rem=0.25
                    ) for airline in selected_airlines
                ]),
                unsafe_allow_html=True
            )
        with col6:
            compare = (
                            st.toggle("Would you like to compare selected airlines' metrics against one of the airlines?", value=len(selected_airlines) > 1)
                            if len(selected_airlines) > 1
                            else False
                        )
            base_airline = (
                st.selectbox("Select Airline to compare against:", selected_airlines)
                if compare
                else selected_airlines[0]
            )

    available_metrics = [
        c for c in data.columns if c not in ("Year", "Quarter", "Airline", "Period")
    ]
    default_metric_group_index = (
        0 if airline_group in ("Major Global Airlines", "Large National Airlines")
        else 1
    )
    with st.container(border=True):
        col7, col8, col9 = st.columns([1, 3, 1])
        with col7:
            metric_group = st.radio("Select Metrics for Comparison:", ["All", *METRIC_GROUPS.keys()], horizontal=False, index=default_metric_group_index)
        if metric_group == "All":
            metric_options = available_metrics
            default_metrics = metric_options
        else:  # metric_group in METRIC_GROUPS:
            metric_options = [m for m in METRIC_GROUPS[metric_group] if m in available_metrics]
            default_metrics = metric_options
        with col8:
            selected_metrics = st.multiselect(
                "Add or remove Metrics to compare:", metric_options, default=default_metrics
            )
            selected_metrics = selected_metrics or metric_options[:1]
        with col9:
            if st.button("Show definitions of the available metrics", icon=":material/dictionary:"):
                show_metric_definitions()

# ---------------------------------------------------------------------------
# Filter and compute
# ---------------------------------------------------------------------------
show_time = False
show_compare = False

mask = (
    data["Airline"].isin(selected_airlines)
    & data["Year"].isin(selected_years)
    & data["Quarter"].isin(selected_quarters)
)
filtered = data[mask].copy().sort_values("Period")
if filtered.empty:
    st.info("No rows match the selected filters.")
    st.stop()

visible_metrics: list[str] = [
    metric
    for metric in selected_metrics
    if metric in filtered.columns and filtered[metric].notna().any()
]
hidden_metrics: list[str] = [
    metric for metric in selected_metrics if metric not in visible_metrics
]

if hidden_metrics:
    st.caption(
        "The following metrics are hidden because there is no data available for the selected airlines/periods: "
        + ", ".join(hidden_metrics)
    )

if not visible_metrics:
    fallback_metrics = [
        metric
        for metric in available_metrics
        if metric in filtered.columns and filtered[metric].notna().any()
    ]
    if fallback_metrics:
        visible_metrics = [fallback_metrics[0]]
        st.info(
            "None of the selected metrics currently have values for this filter set. "
            f"Showing {fallback_metrics[0]} instead. Please adjust your filter selection."
        )
    else:
        st.info("No metrics have available values for the current filters.")
        st.stop()

scaled_metrics: dict[str, tuple[pd.DataFrame, str]] = {}
# Small datasets are faster when scaling from a full-frame copy once per metric.
_SMALL_DATA_FASTPATH_ROWS = 5000
for metric in visible_metrics:
    if len(filtered) <= _SMALL_DATA_FASTPATH_ROWS:
        metric_df = filtered.copy()
    else:
        metric_df = filtered[["Period", "Airline", metric]].copy()
    scaled_metrics[metric] = scale_metric_for_display(metric_df, metric)

periods = sorted(filtered["Period"].unique())
airline_order = sorted(selected_airlines)
show_time = len(selected_years) > 1 or len(selected_quarters) > 1
show_compare = len(selected_airlines) > 1 and compare

tab_time, tab_period = st.tabs(["Metrics Over Time", "Single Period"])

with tab_time:
    for metric in visible_metrics:
        st.subheader(metric, divider="gray")
        plot_df, display_col = scaled_metrics[metric]

        # Lay the table and charts side by side, matching the original layout:
        # table only, table + line, table + bar, or table + line + bar.
        if show_time and show_compare:
            col_table, col_line, col_bar = st.columns(3)
        elif show_time:
            col_table, col_line = st.columns([2, 3])
            col_bar = None
        elif show_compare:
            col_table, col_bar = st.columns(2)
            col_line = None
        else:
            (col_table,) = st.columns(1)
            col_line = col_bar = None

        # Comparison table
        rows = []
        base_series = (
            plot_df[plot_df["Airline"] == base_airline]
            .set_index("Period")[display_col]
            .reindex(periods)
        )
        for airline in selected_airlines:
            series = (
                plot_df[plot_df["Airline"] == airline]
                .set_index("Period")[display_col]
                .reindex(periods)
            )
            diffs = [pct_diff(b, c) for b, c in zip(base_series, series)]
            rows.append(
                pd.DataFrame(
                    {
                        "Period": periods,
                        "Airline": airline,
                        display_col: [format_metric_value(v, metric) for v in series],
                        f"vs {base_airline}": [
                            None if d is None or pd.isna(d) else f"{d}%" for d in diffs
                        ],
                    }
                )
            )
        table = pd.concat(rows).set_index(["Period", "Airline"])
        if not show_compare:
            table = table.drop(columns=[f"vs {base_airline}"])
        table = table.unstack("Airline")
        table.columns = table.columns.swaplevel(0, 1)
        table = table.sort_index(axis=1, level=0)
        with col_table:
            if show_compare:
                table = table.drop(columns=[(base_airline, f"vs {base_airline}")], errors="ignore")
                color_cols = [
                    (a, f"vs {base_airline}")
                    for a in table.columns.get_level_values(0).unique()
                    if (a, f"vs {base_airline}") in table.columns
                ]
                styled = table.style.map(color_positive_negative, subset=color_cols)
                st.dataframe(styled, width="stretch")
            else:
                st.dataframe(table, width="stretch")

        if show_time:
            with col_line:
                fig = px.line(
                    plot_df,
                    x="Period",
                    y=display_col,
                    color="Airline",
                    category_orders={"Period": periods, "Airline": airline_order},
                    color_discrete_map=AIRLINE_COLORS,
                    title=f"{metric} Over Time",
                )
                fig.update_layout(xaxis_title=None, xaxis_tickangle=-45)
                fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.25)
                if metric in CURRENCY_METRICS:
                    hover = "%{x}<br>%{y:$,.0f}"
                elif metric in EPS_DOLLAR_METRICS:
                    hover = "%{x}<br>%{y:$,.2f}"
                elif metric in CENTS_METRICS:
                    hover = "%{x}<br>%{y:.2f}\u00A2"
                elif metric in PERCENT_METRICS:
                    hover = "%{x}<br>%{y:.2f}%"
                else:
                    hover = "%{x}<br>%{y:,.0f}"
                fig.update_traces(hovertemplate=hover)
                st.plotly_chart(fig, width="stretch")

        if show_compare:
            with col_bar:
                diff_rows = []
                for airline in selected_airlines:
                    if airline == base_airline:
                        continue
                    series = (
                        plot_df[plot_df["Airline"] == airline]
                        .set_index("Period")[display_col]
                        .reindex(periods)
                    )
                    diffs = [pct_diff(b, c) for b, c in zip(base_series, series)]
                    diff_rows.append(
                        pd.DataFrame({"Period": periods, "Airline": airline, "Percent Difference": diffs})
                    )
                diff_df = pd.concat(diff_rows)
                fig_bar = px.bar(
                    diff_df,
                    x="Period",
                    y="Percent Difference",
                    color="Airline",
                    barmode="group",
                    category_orders={"Period": periods, "Airline": airline_order},
                    color_discrete_map=AIRLINE_COLORS,
                    title=f"Percent Difference in {metric} vs {base_airline}",
                )
                fig_bar.update_layout(xaxis_title=None, xaxis_tickangle=-45)
                fig_bar.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.75)
                fig_bar.update_traces(hovertemplate="%{x}<br>%{y:.2f}%")
                st.plotly_chart(fig_bar, width="stretch")

with tab_period:
    latest = max(periods)
    st.subheader(f"Summary of {latest}", divider="gray")
    st.caption("When multiple periods are selected, this shows the latest one in the range.")
    metric_order: list[str] = []
    summary_rows = []
    for metric in visible_metrics:
        scaled, display_col = scaled_metrics[metric]
        scaled = scaled[scaled["Period"] == latest]
        metric_order.append(display_col)
        base_val = scaled[scaled["Airline"] == base_airline][display_col]
        base_val = base_val.iloc[0] if not base_val.empty else None
        for airline in selected_airlines:
            cell = scaled[scaled["Airline"] == airline][display_col]
            value = cell.iloc[0] if not cell.empty else None
            d = pct_diff(base_val, value)
            summary_rows.append(
                {
                    "Metric": display_col,
                    "Airline": airline,
                    latest: format_metric_value(value, metric),
                    f"vs {base_airline}": None if d is None or pd.isna(d) else f"{d}%",
                }
            )
    summary = pd.DataFrame(summary_rows).set_index(["Metric", "Airline"])
    if not show_compare:
        summary = summary.drop(columns=[f"vs {base_airline}"])
    summary = summary.unstack("Airline")
    summary.columns = summary.columns.swaplevel(0, 1)
    summary = summary.sort_index(axis=1, level=0)
    summary = summary.reindex(metric_order)
    if show_compare:
        summary = summary.drop(columns=[(base_airline, f"vs {base_airline}")], errors="ignore")
        color_cols = [
            (a, f"vs {base_airline}")
            for a in summary.columns.get_level_values(0).unique()
            if (a, f"vs {base_airline}") in summary.columns
        ]
        st.dataframe(summary.style.map(color_positive_negative, subset=color_cols), width="stretch")
    else:
        st.dataframe(summary, width="stretch")
