"""Share Repurchases page.

Summarizes the 2010s Big 3 buyback campaigns, the pandemic-era share sales, and
the current net value of those programs based on live closing prices from the
quotes-api service.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib.data import fetch_history, fetch_quotes, load_buybacks
from lib.formatting import AIRLINE_COLORS, AIRLINE_NAMES, airline_header_html

st.header(":material/paid: Share Repurchases")

buybacks = load_buybacks()
repurchases = pd.DataFrame(buybacks.get("repurchases", []))
sales = pd.DataFrame(buybacks.get("sales", []))

if repurchases.empty:
    st.warning("No buyback data found. Run the data build first (see core/README.md).")
    st.stop()

# Post-pandemic repurchase authorization and resumption, sourced from filings.
AUTHORIZATION = {"AAL": None, "DAL": datetime(2025, 4, 29), "UAL": datetime(2024, 10, 15)}
RESUMPTION = {"AAL": None, "DAL": "2025Q2", "UAL": "2024Q4"}

# Daily gain/loss history starts the quarter after buybacks were paused for Covid.
COVID_START = "2020-04-01"


def _quarter_end(period: str) -> pd.Timestamp:
    """Return the last calendar day of a ``YYYYQn`` period."""
    year = int(period[:4])
    month = int(period[5]) * 3
    return pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)


tickers = tuple(sorted(repurchases["Airline"].unique()))
if st.button("Refresh stock prices", type="primary"):
    fetch_quotes.clear()
    fetch_history.clear()
quotes = fetch_quotes(tickers)

total_shares = repurchases.groupby("Airline")["Shares (millions)"].sum()
total_cost = repurchases.groupby("Airline")["Cost (millions)"].sum()
avg_cost = total_cost / total_shares

if not sales.empty:
    sale_shares = sales.groupby("Airline")["Shares (millions)"].sum()
    sale_proceeds = sales.groupby("Airline")["Proceeds (millions)"].sum()
    avg_sale = sale_proceeds / sale_shares
    sales_2020 = sales[sales["Year"] == 2020]
    sale_shares_2020 = sales_2020.groupby("Airline")["Shares (millions)"].sum()
    sale_proceeds_2020 = sales_2020.groupby("Airline")["Proceeds (millions)"].sum()
    avg_sale_2020 = sale_proceeds_2020 / sale_shares_2020
else:
    sale_shares = sale_proceeds = avg_sale = pd.Series(dtype=float)
    sale_shares_2020 = avg_sale_2020 = pd.Series(dtype=float)

st.subheader("2010s Big 3 Share Buyback Campaign", divider="gray")

# Build the gain/loss history chart up front so it can lead the right column.
history = fetch_history(tickers, COVID_START)

fig_line = None
if not history.empty:
    dates = history.index
    pre_2021 = dates <= pd.Timestamp("2020-12-31")
    in_2021 = (dates > pd.Timestamp("2020-12-31")) & (dates <= pd.Timestamp("2021-12-31"))

    gain = pd.DataFrame(index=history.index)
    for airline in tickers:
        if airline not in history.columns:
            continue
        x = pd.to_numeric(history[airline], errors="coerce")
        ac = float(avg_cost[airline])
        tsr = float(total_shares[airline])
        # 2020-only sales, used to adjust the 2021 share count.
        ss20 = float(sale_shares_2020.get(airline, 0.0))
        sp20 = float(avg_sale_2020.get(airline, ac))
        # All pandemic sales, used once the full program is realized.
        tss = float(sale_shares.get(airline, 0.0))
        tas = float(avg_sale.get(airline, ac))

        pre = ((x - ac) * tsr) / 1000
        mid = (((sp20 - ac) * ss20) + ((x - ac) * (tsr - ss20))) / 1000
        post = (((tas - ac) * tss) + ((x - ac) * (tsr - tss))) / 1000
        gain[airline] = np.select([pre_2021, in_2021], [pre.values, mid.values], default=post.values)

    # Solid line through each resumption date, then dotted afterward. Airlines
    # that have not resumed stay solid across the full window.
    hover = "%{x}<br>%{y:$,.1f} billion"
    fig_line = go.Figure()
    for airline in gain.columns:
        series = gain[airline].dropna()
        if series.empty:
            continue
        color = AIRLINE_COLORS.get(airline)
        resumption = RESUMPTION.get(airline)
        cutoff = _quarter_end(resumption) if resumption else None
        if cutoff is not None:
            solid = series[series.index <= cutoff]
            # Include the cutoff point in both segments so they join seamlessly.
            dotted = series[series.index >= cutoff]
            fig_line.add_trace(go.Scatter(
                x=solid.index, y=solid.values, mode="lines", name=airline,
                legendgroup=airline, line=dict(color=color), hovertemplate=hover,
            ))
            if not dotted.empty:
                fig_line.add_trace(go.Scatter(
                    x=dotted.index, y=dotted.values, mode="lines", name=airline,
                    legendgroup=airline, showlegend=False,
                    line=dict(color=color, dash="dot"), hovertemplate=hover,
                ))
        else:
            fig_line.add_trace(go.Scatter(
                x=series.index, y=series.values, mode="lines", name=airline,
                legendgroup=airline, line=dict(color=color), hovertemplate=hover,
            ))
    fig_line.update_layout(
        title="Gain/Loss of the Share Repurchase Programs Since the Onset of Covid-19",
        xaxis_title=None,
        yaxis_title="Gain/Loss (billions)",
        xaxis_tickangle=-45,
        legend_title_text="Airline",
    )
    fig_line.add_hline(y=0, line_dash="dot", line_color="black", opacity=0.5)

net_values: dict[str, float] = {}
summary_col, table_col = st.columns([1, 2])

with summary_col:
    for airline in tickers:
        st.markdown(
            airline_header_html(airline, f"{AIRLINE_NAMES.get(airline, airline)} ({airline})", heading_level=4, logo_height_em=1.50),
            unsafe_allow_html=True,
        )
        quote = quotes.get(airline)
        close = quote.get("price") if quote else None
        s_shares = float(sale_shares.get(airline, 0.0))
        s_avg = float(avg_sale.get(airline, 0.0))

        if close is None:
            st.warning("Live price unavailable. Start quotes-api or check its URL.")
            continue

        sale_sentence = (
            f"To raise cash during the Covid-19 pandemic, {airline} offered and sold "
            f"**{s_shares:.1f} million** shares generating proceeds of "
            f"**\\${sale_proceeds.get(airline, 0.0) / 1000:.1f} billion**. "
            f"The average share price of sale was **\\${s_avg:.2f}**. "
        ) if s_shares else ""
        auth = AUTHORIZATION.get(airline)
        auth_sentence = (
            f"{airline} authorized its first post-pandemic share repurchase program on "
            f"**{auth.strftime('%B %d, %Y')}** and resumed share repurchases during "
            f"**{RESUMPTION[airline]}**.<br>"
        ) if auth else ""
        st.markdown(
            f"{airline} repurchased **{total_shares[airline]:.1f} million** shares at a total cost of "
            f"**\\${total_cost[airline] / 1000:.1f} billion**. The average share price of repurchase was "
            f"**\\${avg_cost[airline]:.2f}**. "
            f"{sale_sentence}"
            f"{airline} last closed at **${close:.2f}**.<br>"
            f"{auth_sentence}"
            f"Based on the current share price and sales made during the pandemic, "
            f"the repurchase campaign has netted {airline}:",
            unsafe_allow_html=True,
        )

        net = (
            (s_avg - avg_cost[airline]) * s_shares
            + (close - avg_cost[airline]) * (total_shares[airline] - s_shares)
        ) / 1000
        net_values[airline] = round(net, 1)
        color = "green" if round(net, 1) > 0 else "red" if round(net, 1) < 0 else "black"
        ratio = net / total_cost[airline] / 1000
        emoji = (
            "🔥💰🔥" if round(net, 1) < 0
            else "🤷" if round(net, 1) == 0
            else "💸" if ratio < 0.5
            else "💸💸" if ratio <= 1
            else "💸💸💸"
        )
        st.markdown(
            f"<p style='margin-bottom:0;'><h3 style='color:{color};'>"
            f"{'-$' if round(net, 1) < 0 else '$'}{abs(net):,.1f} billion {'&nbsp;' * 10} {emoji}"
            f"</h3></p>",
            unsafe_allow_html=True,
        )

with table_col:
    if fig_line is not None:
        st.plotly_chart(fig_line, width="stretch")
    else:
        st.warning("Live price history unavailable. Start quotes-api or check its URL.")

    if net_values:
        net_df = pd.DataFrame({"Airline": list(net_values), "Net (billions)": list(net_values.values())})
        fig = px.bar(
            net_df,
            x="Airline",
            y="Net (billions)",
            color="Airline",
            color_discrete_map=AIRLINE_COLORS,
            title="Net Value of the Buyback Programs at the Latest Close",
        )
        fig.update_layout(xaxis_title=None, showlegend=False)
        fig.add_hline(y=0, line_dash="dot", line_color="black", opacity=0.5)
        fig.update_traces(hovertemplate="%{x}<br>%{y:$,.2f} billion")
        st.plotly_chart(fig, width="stretch")


def pivot_history(df: pd.DataFrame, value_cols: list[str]) -> pd.DataFrame:
    table = df[["Period", "Airline", *value_cols]].set_index(["Period", "Airline"])
    table = table.unstack("Airline")
    table.columns = table.columns.swaplevel(0, 1)
    return table.sort_index(axis=1, level=0)


with st.expander("Show share repurchase and share sale history tables", expanded=False):
    st.markdown("#### Share Repurchase History")
    r = repurchases.copy()
    r["Shares (millions)"] = r["Shares (millions)"].map(lambda x: f"{x:,.1f}")
    r["Cost (millions)"] = r["Cost (millions)"].map(lambda x: f"${x:,.0f}")
    r["Average Share Price"] = r["Average Share Price"].map(lambda x: f"${x:,.2f}")
    st.dataframe(
        pivot_history(r, ["Shares (millions)", "Cost (millions)", "Average Share Price"]),
        width="stretch",
    )

    if not sales.empty:
        st.markdown("#### Share Sale History")
        s = sales.copy()
        s["Shares (millions)"] = s["Shares (millions)"].map(lambda x: f"{x:,.1f}")
        s["Proceeds (millions)"] = s["Proceeds (millions)"].map(lambda x: f"${x:,.0f}")
        s["Average Share Price"] = s["Average Share Price"].map(lambda x: f"${x:,.2f}")
        st.dataframe(
            pivot_history(s, ["Shares (millions)", "Proceeds (millions)", "Average Share Price"]),
            width="stretch",
        )


