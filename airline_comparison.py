import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Set custom page configuration including the "About" section
st.set_page_config(
    page_title="US Airline Financial Metrics Comparison",  # Custom title in the browser tab
    page_icon=":airplane:",  # Custom icon for the browser tab
    layout="centered",  # Use a wide layout for the app
    initial_sidebar_state="auto",  # Sidebar state when app loads
    menu_items={
        "About": """
        ## US Airline Financial Metrics Comparison App
        This app enables quick and intuitive comparisons of the financial performance of major US commercial airlines. Several selected metrics can be evaluated over chosen reporting periods. Unless otherwise noted, all metrics are either sourced or calculated from data given in the 10-Q/8-K (quarterly filings) and 10-K (annual filing) forms reported to the SEC and available on the airlines' investor relations sites linked below.\n
        [AAL](https://americanairlines.gcs-web.com/) | [DAL](https://ir.delta.com/) | [UAL](https://ir.united.com/)
        - **Version:** 1.0.0
        - **Author:** Michael Tricanowicz
        - **License:** MIT
        - **GitHub:** [airline_financials](https://github.com/mtricanowicz/airline_financials)
        """
    }
)

# Load the CSV data
file_path = "airline_financial_data.csv"
airline_financials = pd.read_csv(file_path)

# Add calculated metrics
airline_financials["Net Margin"] = round((airline_financials["Net Income"] / airline_financials["Total Revenue"]) * 100, 2)
airline_financials["Load Factor"] = round((airline_financials["RPM"] / airline_financials["ASM"]) * 100, 2)
airline_financials["Yield"] = airline_financials["Passenger Revenue"] / airline_financials["RPM"]
airline_financials["TRASM"] = airline_financials["Total Revenue"] / airline_financials["ASM"]
airline_financials["PRASM"] = airline_financials["Passenger Revenue"] / airline_financials["ASM"]
airline_financials["CASM"] = airline_financials["Total Expenses"] / airline_financials["ASM"]

# Create a Period column to represent the fiscal period and to use for data display
airline_financials["Quarter"] = airline_financials["Quarter"].apply(lambda x: f"Q{x}" if x != "FY" else x)
airline_financials["Period"] = airline_financials["Year"].astype(str) + airline_financials["Quarter"].astype(str)

# Split data into full-year and quarterly DataFrames
airline_financials_fy = airline_financials[airline_financials["Quarter"] == "FY"].copy()
#airline_financials_fy["Date"] = pd.to_datetime(airline_financials_fy["Year"].astype(str) + "-12-31") # date ended up not being needed

airline_financials_q = airline_financials[airline_financials["Quarter"] != "FY"].copy()
#airline_financials_q["Date"] = pd.to_datetime(airline_financials_q["Year"].astype(str) + "-" + (airline_financials_q["Quarter"]*3).astype(str) + "-01") + pd.offsets.MonthEnd(0) # date ended up not being needed

# Color palette to use for visualizaitons
airline_colors = {
    "AAL": "#A5B5BE",
    "DAL": "#9B1631",
    "UAL": "#005daa",
    "ALK": "#00385f",
    "LUV": "#f9b612"
}

# Streamlit app title
st.title("Airline Financial Metrics Comparison")

# Allow users to select full-year or quarterly data
data_type = st.selectbox("View Full Year or Quarterly Data?", ["Full Year", "Quarterly"])
if data_type == "Full Year":
    data = airline_financials_fy
else:
    data = airline_financials_q

# Remove metrics from the data that do not have data for the chosen reporting period
data = data.dropna(axis=1, how="all")

# Allow user to select airlines to compare
airlines = data["Airline"].unique()
selected_airlines = st.multiselect("Select Airline(s) for Comparison", airlines, default=["AAL"])
if not selected_airlines:
    selected_airlines=["AAL"] # prevents empty set from triggering an error, displays AAL if none are selected

# Allow user to select a base airline to compare others against
if len(selected_airlines) > 1:
    base_airline = st.selectbox("Select Airline to Compare Against", selected_airlines)
else:
    base_airline = selected_airlines[0]

# Tie base airline selection to a theme color (to be used to dynamically change app interface element colors in future)
base_color = airline_colors[base_airline]

# Allow user to select years for comparison
years = data["Year"].unique()
selected_years = st.multiselect("Select Year(s) for Comparison", years, default=years)
if not selected_years:
    selected_years=years # prevents empty set from triggering an error, displays all years if none are selected

# Allow user to select quarters for comparison
quarters = data["Quarter"].unique()
if data_type == "Quarterly":
    selected_quarters = st.multiselect("Select Quarter(s) for Comparison", quarters, default=quarters)
    if not selected_quarters: # prevents empty set from triggering an error, displays all quarters if none are selected
        selected_quarters=quarters
elif data_type == "Full Year":
    selected_quarters=quarters

# Allow user to select metrics to compare with a "Select All" option
available_metrics = data.columns.drop(["Year", "Quarter", "Airline", "Period"])
select_all = st.checkbox("Select All Metrics")
if select_all:
    selected_metrics = st.multiselect("Add or Remove Metrics to Compare", available_metrics, default=available_metrics)
else:
    selected_metrics = st.multiselect("Add or Remove Metrics to Compare", available_metrics, default=["Total Revenue", "Net Income", "Net Margin"])
if not selected_metrics:
    selected_metrics=["Total Revenue", "Net Income", "Net Margin"] # prevents empty set from triggering an error, displays default metrics if none are selected


# Add a toggle to display metric definitions for users who need them
show_definitions = st.checkbox("Show definitions of the available metrics.")
if show_definitions:
    st.write("Total Revenue - Total amount of money earned from sales.")
    st.write("Passenger Revenue - Revenue primarily composed of passenger ticket sales, loyalty travel awards, and travel-related services performed in conjunction with a passenger's flight.")
    st.write("Total Expenses - Total amount of costs incurred.")
    st.write("Net Income - Profit. Total Revenue minus Total Expenses.")
    st.write("Revenue Passenger Mile (RPM) - A basic measure of sales volume. One RPM represents one passenger flown one mile.")
    st.write("Available Seat Mile (ASM) - A basic measure of production. One ASM represents one seat flown one mile.")
    st.write("Long-Term Debt - Total long-term debt net of current maturities.")
    st.write("Profit Sharing - Amount of income set aside to fund employee profit sharing programs. NOTE: AAL's reporting of this metric was inconsistent pre-COVID and has not been reported at all post-COVID. Data provided may have been obtained from internal sources.")
    st.write("Net Margin - Percentage of profit earned for each dollar in revenue.")
    st.write("Load Factor - The percentage of available seats that are filled with revenue passengers. RPMs divided by ASMs.")
    st.write("Yield - A measure of airline revenue derived by dividing Passenger Revenue by RPMs.")
    st.write("Total Revenue per Available Seat Mile (TRASM) - Total Revenue divided by ASMs.")
    st.write("Passenger Revenue per Available Seat Mile (PRASM) - Passenger Revenue divided by ASMs.")
    st.write("Cost per Available Seat Mile (CASM) - Total Expenses divided by ASMs.")

# Filter data for selected airlines and metrics
filtered_data = data[data["Airline"].isin(selected_airlines)][data["Year"].isin(selected_years)][data["Quarter"].isin(selected_quarters)].copy()

# Define a function to compare values between airlines and output the percent difference
def pct_diff(base, comparison):
    # Handle cases where base is zero to avoid division by zero
    if base == 0:
        return float(np.inf) if comparison != 0 else 0
    # Calculate the percentage difference using absolute values
    percent_change = round(abs((comparison - base) / abs(base)) * 100, 2)
    # Determine if the change should be considered positive or negative
    if base < 0 < comparison:
        return percent_change
    elif base > 0 > comparison:
        return -percent_change
    elif base > comparison:
        return -percent_change
    else:
        return percent_change

# Calculate percentage difference from the base airline and generate a comparison table with chosen metrics
comparison_data = []
for metric in selected_metrics:

    # Adjust some of the metrics to scale better for display
    if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
        filtered_data[metric] = filtered_data[metric] / 1000000
        filtered_data.rename(columns={metric:f"{metric} (millions)"}, inplace=True)
        metric = metric + " (millions)" 
    elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
        filtered_data[metric] = filtered_data[metric] * 100
    # Incoporate base airline
    base_values = filtered_data[filtered_data["Airline"] == base_airline].set_index(["Period"])[metric]
    # Incorporate other selected airlines
    for airline in selected_airlines:
        airline_values = filtered_data[filtered_data["Airline"] == airline].set_index(["Period"])[metric]
        percent_difference = pd.Series([pct_diff(base, comp) for base, comp in zip(base_values, airline_values)])
        comparison_data.append(pd.DataFrame({
            "Period": airline_values.index,
            "Airline": airline,
            "Metric": metric,
            "Value": airline_values.values,
            "Percent Difference": percent_difference.values
        }))
comparison_df = pd.concat(comparison_data) # output the comparison dataframe
comparison_df = comparison_df.reset_index(drop=True)

# Display comparison table and sort by "Period" and "Metric". Overall view of the data. Not used because separate tables are shown for each selected metric to improve readability of the data.
#st.write("Airline Comparison")
#st.dataframe(comparison_df.set_index(["Period", "Airline"]).sort_values(by=["Period", "Metric", "Airline"], ascending=True))

# Display selected data
for metric in selected_metrics:

    # Reflect the renamed metrics new names
    if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
        metric_display = metric + " (millions)"
    else:
        metric_display = metric

    # Define function to alter color of the comparison column values based on sign
    def color_positive_negative_zero(val):
        color = "green" if float(val[:-1]) > 0 else "red" if float(val[:-1]) < 0 else "black"
        return f"color: {color}"

    # Function to apply color based on the airline code
    def color_airlines(val):
        return f"color: {airline_colors.get(val, '')}" if val in airline_colors else ""

    # Display table for the metric to allow review of the data
    st.title(f"{metric}")
    comparison_display = comparison_df[comparison_df["Metric"] == metric_display] # prepare a copy of the comparison table to be used for display
    comparison_display = comparison_display.rename(columns={"Value":metric_display}) # rename value column to make it more understandable
    comparison_display["Percent Difference"] = comparison_display["Percent Difference"].apply(lambda x: f"{x}%") # reformat percent difference column to show % sign
    #comparison_display = comparison_display.style.set_table_styles([{"subset": ["Percent Difference"], "props": [("text-align", "right")]}])
    comparison_display = comparison_display.rename(columns={"Percent Difference":f"Difference vs {base_airline}"}) # rename percent difference column to make it more understandable
    comparison_display = comparison_display.drop(columns=["Metric"]) # drop metric column as it is redundant for a table concerning only a single metric
    if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing"]:
        comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"${x:,.0f}" if x.is_integer() else f"${x:,.2f}") # reformat currency columns to show $ sign
    elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
        comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"{x:,.2f}\u00A2") # reformat unit currency columns to show cents sign
    elif metric in ["Net Margin", "Load Factor"]:
        comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"{x:,.2f}%") # reformat margin columns to show % sign
    else:
        comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"{x:,.0f}") # ensure any other metric is displayed as a unitless integer for readability
    comparison_display = comparison_display.sort_values(by=["Period", "Airline"], ascending=True) # sort dataframe by the period and airline
    comparison_display = comparison_display.set_index(["Period", "Airline"])
    if len(selected_airlines) <= 1:
        comparison_display = comparison_display.drop(columns=[f"Difference vs {base_airline}"]) # do not display percent difference column if only 1 airline is selected
    if len(selected_airlines) > 1:
        comparison_display = comparison_display.style.applymap_index(color_airlines, level="Airline").applymap(color_positive_negative_zero, subset=[f"Difference vs {base_airline}"]) # map color of comparison column based on its sign and color of airline codes based on code (streamlit doesn't directly support color text in an index)
    st.dataframe(comparison_display) 

    # Time series line plot for the metric's change over time if more than one time period (quarter or year) is selected.
    if len(selected_years)>1 or len(selected_quarters)>1:
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.lineplot(data=filtered_data, x="Period", y=metric_display, hue="Airline", palette=airline_colors, ax=ax)
        plt.xticks(rotation=45, ha="right", va="top")
        ax.set_title(f"{metric} Over Time")
        ax.set_xlabel(None)
        ax.set_ylabel(metric_display)
        ax.legend(title="Airline")
        ax.axhline(0, color="gray", linestyle="--")
        st.pyplot(fig)

    # Bar plot for % difference if more than one airline is selected.
    if len(selected_airlines) > 1:
        fig, ax = plt.subplots(figsize=(12, 6))
        sns.barplot(data=comparison_df[comparison_df["Metric"] == metric_display], x="Period", y="Percent Difference", hue="Airline", palette=airline_colors, ax=ax)
        plt.xticks(rotation=45, ha="right", va="top")
        ax.set_title(f"Percentage Difference in {metric} Compared to {base_airline}")
        ax.set_xlabel(None)
        ax.set_ylabel("Percentage Difference (%)")
        ax.axhline(0, color="gray", linestyle="--")
        st.pyplot(fig)