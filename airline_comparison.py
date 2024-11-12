import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load the CSV data
file_path = "airline_financial_data.csv"
airline_financials = pd.read_csv(file_path)

# Split data into full-year and quarterly DataFrames
airline_financials_fy = airline_financials[airline_financials["Quarter"] == "FY"].copy()
airline_financials_fy["Profit Sharing"] = airline_financials_fy["Profit Sharing"].astype(float)
airline_financials_fy["Period"] = airline_financials_fy["Year"].astype(str) + airline_financials_fy["Quarter"].astype(str)
airline_financials_fy["Date"] = pd.to_datetime(airline_financials_fy["Year"].astype(str) + "-12-31")
airline_financials_fy["Net Margin"] = (airline_financials_fy["Net Income"] / airline_financials_fy["Total Revenue"]) * 100

airline_financials_q = airline_financials[airline_financials["Quarter"] != "FY"].copy()
airline_financials_q["Quarter"] = airline_financials_q["Quarter"].astype(int)
airline_financials_q["Profit Sharing"] = airline_financials_q["Profit Sharing"].astype(float)
airline_financials_q["Period"] = airline_financials_q["Year"].astype(str) + "Q" + airline_financials_q["Quarter"].astype(str)
airline_financials_q["Date"] = pd.to_datetime(airline_financials_q["Year"].astype(str) + "-" + (airline_financials_q["Quarter"]*3).astype(str) + "-01") + pd.offsets.MonthEnd(0)
airline_financials_q["Net Margin"] = (airline_financials_q["Net Income"] / airline_financials_q["Total Revenue"]) * 100

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

# Allow user to select metrics to compare
available_metrics = data.columns.drop(["Year", "Quarter", "Airline", "Period", "Date"])
selected_metrics = st.multiselect("Select Metrics to Compare", available_metrics, default=available_metrics)

# Filter data for selected airlines and metrics
filtered_data = data[data["Airline"].isin(selected_airlines)][data["Year"].isin(selected_years)][data["Quarter"].isin(selected_quarters)].copy()

# Define a function to compare values between airlines and output the percent difference
def pct_diff(base, comparison):
    # Handle cases where base is zero to avoid division by zero
    if base == 0:
        return float("inf") if comparison != 0 else 0
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
    base_values = filtered_data[filtered_data["Airline"] == base_airline].set_index("Date")[metric]
    for airline in selected_airlines:
        airline_values = filtered_data[filtered_data["Airline"] == airline].set_index("Date")[metric]
        percent_difference = pd.Series([pct_diff(base, comp) for base, comp in zip(base_values, airline_values)])
        comparison_data.append(pd.DataFrame({
            "Date": airline_values.index,
            "Airline": airline,
            "Metric": metric,
            "Value": airline_values.values,
            "Percent Difference": percent_difference.values
        }))
comparison_df = pd.concat(comparison_data) # output the comparison dataframe
comparison_df = comparison_df.drop(columns=["Period"], errors='ignore')  # ensure dataframe doesn't have a "Period" column prior to the merge operation to add one
comparison_df = pd.merge(comparison_df, filtered_data.drop_duplicates(subset="Date", keep="first")[["Date", "Period"]], on="Date", how="left") # add "Period" column to be used for plotting

# Display comparison table and sort by "Period" and "Metric". Overall view of the data. Not used because separate tables are shown for each selected metric to improve readability of the data.
#st.write("Airline Comparison")
#st.write(comparison_df.set_index("Period").drop(columns=["Date"]).sort_values(by=["Period", "Metric"], ascending=True))

# Display selected data
for metric in selected_metrics:
    
    # Define function to alter color of the comparison column values based on sign
    def color_positive_negative_zero(val):
        color = "green" if float(val[:-1]) > 0 else "red" if float(val[:-1]) < 0 else "black"
        return f"color: {color}"

    # Function to apply color based on the airline code
    def color_airlines(val):
        return f"color: {airline_colors.get(val, '')}" if val in airline_colors else ""

    # Display table for the metric to allow review of the data
    st.title(f"{metric} Comparison")
    comparison_display = comparison_df[comparison_df["Metric"] == metric] # prepare a copy of the comparison table to be used for display
    comparison_display = comparison_display.rename(columns={"Value":metric}) # rename value column to make it more understandable
    comparison_display["Percent Difference"] = comparison_display["Percent Difference"].apply(lambda x: f"{x}%") # reformat percent difference column to show % sign
    #comparison_display = comparison_display.style.set_table_styles([{"subset": ["Percent Difference"], "props": [("text-align", "right")]}])
    comparison_display = comparison_display.rename(columns={"Percent Difference":f"Difference vs {base_airline}"}) # rename percent difference column to make it more understandable
    comparison_display = comparison_display.drop(columns=["Metric"]) # drop metric column as it is redundant for a table concerning only a single metric
    if metric in ["Total Revenue", "Total Revenue per Available Seat Mile (TRASM)", "Net Income", "Profit Sharing"]:
        comparison_display[metric] = comparison_display[metric].apply(lambda x: f"${x:,.0f}" if x.is_integer() else f"${x:,.4f}") # reformat currency columns to show $ sign
    elif metric in ["Net Margin"]:
        comparison_display[metric] = comparison_display[metric].apply(lambda x: f"{x:,.2f}%") # reformat margin columns to show % sign
    else:
        comparison_display[metric] = comparison_display[metric].apply(lambda x: f"{x:,.0f}") # ensure any other metric is displayed as a unitless integer
    comparison_display = comparison_display.drop(columns=["Date"]).sort_values(by=["Period"], ascending=True) # remove date column from display and sort dataframe by the period
    comparison_display = comparison_display.set_index(["Period", "Airline"])
    if len(selected_airlines) <= 1:
        comparison_display = comparison_display.drop(columns=[f"Difference vs {base_airline}"]) # do not display percent difference column if only 1 airline is selected
    if len(selected_airlines) > 1:
        comparison_display = comparison_display.style.applymap_index(color_airlines, level="Airline").applymap(color_positive_negative_zero, subset=[f"Difference vs {base_airline}"]) # map color of comparison column based on its sign and color of airline codes based on code
    st.dataframe(comparison_display) 

    # Time series line plot for the metric's change over time if more than one time period (quarter or year) is selected.
    if len(selected_years)>1 or len(selected_quarters)>1:
        fig, ax = plt.subplots(figsize=(20, 10))
        sns.lineplot(data=filtered_data, x="Period", y=metric, hue="Airline", palette=airline_colors, ax=ax)
        plt.xticks(rotation=45, ha="right", va="top")
        ax.set_title(f"{metric} Over Time")
        ax.set_xlabel(None)
        ax.set_ylabel(metric)
        ax.legend(title="Airline")
        st.pyplot(fig)

    # Bar plot for % difference if more than one airline is selected.
    if len(selected_airlines) > 1:
        fig, ax = plt.subplots(figsize=(20, 10))
        sns.barplot(data=comparison_df[comparison_df["Metric"] == metric], x="Period", y="Percent Difference", hue="Airline", palette=airline_colors, ax=ax)
        plt.xticks(rotation=45, ha="right", va="top")
        ax.set_title(f"Percentage Difference in {metric} Compared to {base_airline}")
        ax.set_xlabel(None)
        ax.set_ylabel("Percentage Difference (%)")
        ax.axhline(0, color="gray", linestyle="--")
        st.pyplot(fig)
