import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the CSV data
file_path = "airline_financial_data.csv"
airline_financials = pd.read_csv(file_path)

# Split data into full-year and quarterly DataFrames
airline_financials_fy = airline_financials[airline_financials["Quarter"] == "FY"].copy()
airline_financials_fy["Period"] = airline_financials_fy["Year"].astype(str) + airline_financials_fy["Quarter"].astype(str)
airline_financials_fy["Date"] = pd.to_datetime(airline_financials_fy["Year"].astype(str) + "-12-31")
airline_financials_fy["Net Margin"] = (airline_financials_fy["Net Income"] / airline_financials_fy["Total Revenue"]) * 100

airline_financials_q = airline_financials[airline_financials["Quarter"] != "FY"].copy()
airline_financials_q["Quarter"] = airline_financials_q["Quarter"].astype(int)
airline_financials_q["Period"] = airline_financials_q["Year"].astype(str) + "Q" + airline_financials_q["Quarter"].astype(str)
airline_financials_q["Date"] = pd.to_datetime(airline_financials_q["Year"].astype(str) + "-" + (airline_financials_q["Quarter"]*3).astype(str) + "-01") + pd.offsets.MonthEnd(0)
airline_financials_q["Net Margin"] = (airline_financials_q["Net Income"] / airline_financials_q["Total Revenue"]) * 100

# Color palette to use for visualizaitons
airline_colors = {
    "AAL": "red",
    "DAL": "purple",
    "UAL": "blue"
}

# Streamlit app interface
st.title("Airline Financial Metrics Comparison")

# Allow users to select full-year or quarterly data
data_type = st.selectbox("Select Data Type", ["Full Year (FY)", "Quarterly"])
if data_type == "Full Year (FY)":
    data = airline_financials_fy
else:
    data = airline_financials_q

# Allow user to select year and quarter
years = data["Year"].unique()
quarters = data["Quarter"].unique()
selected_years = st.multiselect("Select Year(s) for Comparison", years, default=years[:])
if not selected_years:
    selected_years=years
selected_quarters = st.multiselect("Select Quarter(s) for Comparison", quarters, default=quarters[:])
if not selected_quarters:
    selected_quarters=quarters

# Allow user to select airlines to compare
airlines = data["Airline"].unique()
selected_airlines = st.multiselect("Select Airlines for Comparison", airlines, default=airlines[0:1])

# Allow user to select a base airline
base_airline = st.selectbox("Select Baseline Airline", selected_airlines)

# Allow user to select metrics to compare
available_metrics = ["Total Revenue", "Available Seat Miles (ASM)", "Total Revenue per Available Seat Mile (TRASM)", "Net Income", "Net Margin", "Profit Sharing"]
selected_metrics = st.multiselect("Select Metrics to Compare", available_metrics, default=available_metrics)

# Filter data for selected airlines and metrics
filtered_data = data[data["Airline"].isin(selected_airlines)][data["Year"].isin(selected_years)][data["Quarter"].isin(selected_quarters)].copy()

# Calculate percentage difference from the base airline
comparison_data = []
for metric in selected_metrics:
    base_values = filtered_data[filtered_data["Airline"] == base_airline].set_index("Period")[metric]
    for airline in selected_airlines:
        airline_values = filtered_data[filtered_data["Airline"] == airline].set_index("Period")[metric]
        pct_diff = round(((airline_values - base_values) / base_values) * 100, 2) if base_values!=0 else 0
        comparison_data.append(pd.DataFrame({
            "Period": airline_values.index,
            "Airline": airline,
            "Metric": metric,
            "Value": airline_values.values,
            "Percent Difference": pct_diff.values
        }))

comparison_df = pd.concat(comparison_data)

# Display comparison table
st.write("Airline Comparison")
st.write(comparison_df.sort_values(by=["Period", "Metric"], ascending=True))

# Plotting selected metrics over time
for metric in selected_metrics:
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.lineplot(data=filtered_data, x="Date", y=metric, hue="Airline", palette=airline_colors, ax=ax)
    ax.set_title(f"{metric} Over Time")
    ax.set_ylabel(metric)
    ax.legend(title="Airline")
    st.pyplot(fig)

    # Bar plot for % difference if more than one airline is selected
    if len(selected_airlines) > 1:
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(
            data=comparison_df[comparison_df["Metric"] == metric],
            x="Date", y="Percent Difference", hue="Airline", palette=airline_colors, ax=ax
        )
        ax.set_title(f"Percentage Difference in {metric} Compared to {base_airline}")
        ax.set_ylabel("Percentage Difference (%)")
        ax.axhline(0, color="gray", linestyle="--")
        st.pyplot(fig)
