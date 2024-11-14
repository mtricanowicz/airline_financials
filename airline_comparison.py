import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go

# Set custom page configuration including the "About" section
st.set_page_config(
    page_title="US Airline Financial Metrics Comparison",  # Custom title in the browser tab
    page_icon=":airplane:",  # Custom icon for the browser tab
    layout="wide",  # Set the defaul layout for the app
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

#CUSTOM CSS ADDITIONS
# Custom CSS to style radio buttons horizontally
st.markdown("""
    <style>
        .stRadio > div {display: flex; flex-direction: row;}
        .stRadio > div > label {margin-right: 20px;}
    </style>
    """, unsafe_allow_html=True)
# Custom CSS to reduce padding around the divider
st.markdown("""
    <style>
    .custom-divider {
        border-top: 1px solid #e0e0e0;
        margin-top: 2px;   /* Adjusts the space above */
        margin-bottom: 2px; /* Adjusts the space below */
    }
    </style>
""", unsafe_allow_html=True)


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
#airline_financials_fy["Date"] = pd.to_datetime(airline_financials_fy["Year"].astype(str) + "-12-31") # date ended up not being needed, keeping for future use if necessary

airline_financials_q = airline_financials[airline_financials["Quarter"] != "FY"].copy()
#airline_financials_q["Date"] = pd.to_datetime(airline_financials_q["Year"].astype(str) + "-" + (airline_financials_q["Quarter"]*3).astype(str) + "-01") + pd.offsets.MonthEnd(0) # date ended up not being needed, keeping for future use if necessary

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
data = data.dropna(axis=1, how="all") # drop columns (metrics)
# data = data.dropna(axis=0, how="all") # drop rows (individual airline reporting periods), not applied

# Allow user to select airlines to compare
airlines = data["Airline"].unique()
selected_airlines = st.multiselect("Select Airline(s) for Comparison", airlines, default=["AAL"])
if not selected_airlines:
    selected_airlines=["AAL"] # prevents empty set from triggering an error, displays AAL if none are selected

# Allow user to select a base airline to compare others against
if len(selected_airlines) > 1:
    options_yes_no = ["Yes", "No"]
    compare_yes_no = st.radio("Would you like to compare selected airlines' metrics against one of the airlines?", options_yes_no, index=options_yes_no.index("Yes"))
    if(compare_yes_no=="Yes"):
        base_airline = st.selectbox("Select Airline to Compare Against", selected_airlines)
    else:
        base_airline = selected_airlines[0]
else:
    base_airline = selected_airlines[0]

# Tie base airline selection to a theme color (to be used to dynamically change app interface element colors in future)
#base_color = airline_colors[base_airline]

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
metric_groups = ["Earnings", "Unit Performance", "All", "Custom"]
metric_group_select = st.radio("Select Metrics for Comparison:", metric_groups, index=metric_groups.index("Earnings"))
# Provide preselected groups of metrics and allow user to customize selection
if metric_group_select=="Earnings":
    selected_metrics = ["Total Revenue", "Net Income", "Net Margin"]
elif metric_group_select=="Unit Performance":
    selected_metrics = ["Yield", "TRASM", "PRASM", "CASM"]
elif metric_group_select=="All":
    selected_metrics = available_metrics
elif metric_group_select=="Custom":
    selected_metrics = st.multiselect("Add or Remove Metrics to Compare", available_metrics, default=available_metrics[0])
    if not selected_metrics:
        selected_metrics = [available_metrics[0]] # prevents empty set from triggering an error, displays earnings metrics if none are selected

# Add a toggle to display metric definitions for users who need them
with st.expander("Show definitions of the available metrics."):
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Total Revenue - Total amount earned from sales.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Passenger Revenue - Revenue primarily composed of passenger ticket sales, loyalty travel awards, and travel-related services performed in conjunction with a passenger's flight.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Total Expenses - Total amount of costs incurred.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Net Income - Profit.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Revenue Passenger Mile (RPM) - A basic measure of sales volume. One RPM represents one passenger flown one mile.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Available Seat Mile (ASM) - A basic measure of production. One ASM represents one seat flown one mile.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Long-Term Debt - Total long-term debt net of current maturities.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Profit Sharing - Amount of income set aside to fund employee profit sharing programs.<br>NOTE: AAL's reporting of this metric was inconsistent pre-COVID and has not been reported at all post-COVID. Data provided may have been obtained from internal sources. Additionally, zero profit sharing shown can either indicate no profit sharing or lack of reported data.", unsafe_allow_html=True)
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Net Margin - Percentage of profit earned for each dollar in revenue. Net Income divided by Total Revenue.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Load Factor - The percentage of available seats that are filled with revenue passengers. RPMs divided by ASMs.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Yield - A measure of airline revenue derived by dividing Passenger Revenue by RPMs.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Total Revenue per Available Seat Mile (TRASM) - Total Revenue divided by ASMs.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Passenger Revenue per Available Seat Mile (PRASM) - Passenger Revenue divided by ASMs.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
    st.write("Cost per Available Seat Mile (CASM) - Total Expenses divided by ASMs.")
    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

# Filter data for selected airlines and metrics
filtered_data = data[data["Airline"].isin(selected_airlines)][data["Year"].isin(selected_years)][data["Quarter"].isin(selected_quarters)].copy()

# Define a function to compare values between airlines and output the percent difference
def pct_diff(base, comparison):
    # Handle cases where base is zero to avoid division by zero
    if base == 0:
        return float(np.inf) if comparison != 0 else 0
    # Calculate the percentage difference using absolute values
    percent_change = round(abs((comparison - base) / (base)) * 100, 2)
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
    # Initiate base airline data
    base_values = filtered_data[filtered_data["Airline"] == base_airline].set_index(["Period"])[metric]
    # Initiate all selected airline data and compare to the base airline
    for airline in selected_airlines:
        airline_values = filtered_data[filtered_data["Airline"] == airline].set_index(["Period"])[metric]
        percent_difference = pd.Series([pct_diff(base, comp) for base, comp in zip(base_values, airline_values)])
        comparison_data.append(pd.DataFrame({
            "Period": airline_values.index,
            "Airline": airline,
            "Metric": metric,
            "Value": airline_values.values,
            "Percent Difference": percent_difference.values
            })
        )
comparison_df = pd.concat(comparison_data) # output the comparison dataframe
comparison_df = comparison_df.reset_index(drop=True)

# Display comparison table and sort by "Period" and "Metric". Overall view of the data. Not used because separate tables are shown for each selected metric to improve readability of the data.
#st.write("Airline Comparison")
#st.dataframe(comparison_df.set_index(["Period", "Airline"]).sort_values(by=["Period", "Metric", "Airline"], ascending=True))

tab1, tab2 = st.tabs(["Comparison", "Most Recent Period Summary"])

# Display selected comparison data
with tab1:
    for metric in selected_metrics:
        # Reflect the renamed metrics new names
        if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
            metric_display = metric + " (millions)"
        else:
            metric_display = metric

        # Define function to alter color of the comparison column values based on sign
        def color_positive_negative_zero(val):
            if val is None: # allows function to handle columns that have missing data
                return ""  # no color if the value is None
            try:
                numeric_val = float(val[:-1]) if isinstance(val, str) else val # converts value into float if needed
            except ValueError:
                return ""  # no color if conversion fails
            color = "green" if numeric_val > 0 else "red" if numeric_val < 0 else "" # apply color based on value
            return f"color: {color}"

        # Function to apply color based on the airline code
        def color_airlines(val):
            return f"color: {airline_colors.get(val, '')}" if val in airline_colors else ""

        # Set title for the metric display
        st.header(f"{metric}", divider="gray")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Display table for the metric to allow review of the data
            comparison_display = comparison_df[comparison_df["Metric"] == metric_display] # prepare a copy of the comparison table to be used for display
            comparison_display = comparison_display.rename(columns={"Value":metric_display}) # rename value column to make it more understandable
            comparison_display["Percent Difference"] = comparison_display["Percent Difference"].apply(lambda x: f"{x}%") # reformat percent difference column to show % sign
            #comparison_display = comparison_display.style.set_table_styles([{"subset": ["Percent Difference"], "props": [("text-align", "right")]}])
            comparison_display = comparison_display.rename(columns={"Percent Difference":f"vs {base_airline}"}) # rename percent difference column to make it more understandable
            comparison_display = comparison_display.drop(columns=["Metric"]) # drop metric column as it is redundant for a table concerning only a single metric
            # Column reformatting steps
            if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing"]:
                comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"${x:,.0f}" if x.is_integer() else f"${x:,.2f}") # reformat currency columns to show $ sign
            elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"{x:,.2f}\u00A2") # reformat unit currency columns to show cents sign
            elif metric in ["Net Margin", "Load Factor"]:
                comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"{x:,.2f}%") # reformat percent columns to show % sign
            else:
                comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: f"{x:,.0f}") # ensure any other metric is displayed as a unitless integer for readability
            comparison_display = comparison_display.sort_values(by=["Period", "Airline"], ascending=True) # sort dataframe by the period and airline
            # Column display output
            if len(selected_airlines) <= 1:
                comparison_display = comparison_display.set_index(["Period", "Airline"])
                comparison_display = comparison_display.drop(columns=[f"vs {base_airline}"]) # do not display percent difference column if only 1 airline is selected
                comparison_display = comparison_display.unstack(level="Airline")
                comparison_display.columns = comparison_display.columns.swaplevel(0, 1)
                comparison_display = comparison_display.sort_index(axis=1, level=0)
            elif len(selected_airlines) > 1 and compare_yes_no=="Yes":
                comparison_display = comparison_display.set_index(["Period", "Airline"])
                comparison_display = comparison_display.unstack(level="Airline")
                comparison_display.columns = comparison_display.columns.swaplevel(0, 1)
                comparison_display = comparison_display.sort_index(axis=1, level=0)
                comparison_display = comparison_display.drop(columns=pd.IndexSlice[base_airline, f"vs {base_airline}"])
                conditional_color_columns = [(col, f"vs {base_airline}") for col in comparison_display.columns.levels[0] if (col, f"vs {base_airline}") in comparison_display.columns] # specify the percent difference columns for which to apply conditional color formatting
                comparison_display = comparison_display.style.applymap(color_positive_negative_zero, subset=conditional_color_columns).applymap_index(color_airlines, axis="columns", level="Airline") # map color of comparison column based on its sign and color of airline codes based on code (streamlit doesn't directly support color text in an index)
            elif len(selected_airlines) > 1 and compare_yes_no=="No":
                comparison_display = comparison_display.set_index(["Period", "Airline"])
                comparison_display = comparison_display.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
                comparison_display = comparison_display.unstack(level="Airline")
                comparison_display.columns = comparison_display.columns.swaplevel(0, 1)
                comparison_display = comparison_display.sort_index(axis=1, level=0)
            st.dataframe(comparison_display) 

        with col2:
            # Time series line plot (via plotly) for the metric's change over time if more than one time period (quarter or year) is selected.
            if len(selected_years)>1 or len(selected_quarters)>1:
                # Generate the plot
                fig_line = px.line(
                    filtered_data, 
                    x="Period", 
                    y=metric_display,
                    category_orders={"Period": sorted(data["Period"].unique(), reverse=False)}, # ensure x axis plots in chronological order
                    color="Airline",
                    title=f"{metric} Over Time",
                    color_discrete_map=airline_colors  # Apply custom color mapping
                )
                # Update plot layout features
                fig_line.update_layout(
                    xaxis_title=None,
                    yaxis_title=metric_display,
                    xaxis_tickangle=-45
                )
                # Add a more visible line at zero to more easily visually recognize positive and negative
                fig_line.add_hline(
                    y=0, 
                    line_dash="dot", 
                    line_color="gray",
                    opacity=0.25
                )
                # Adjust the hover over display formatting to improve readability
                if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing"]:
                    fig_line.update_traces(
                        hovertemplate="%{x}<br>$%{y:.0f}"
                    )
                elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                    fig_line.update_traces(
                        hovertemplate="%{x}<br>%{y:.2f}\u00A2"
                    )
                elif metric in ["Net Margin", "Load Factor"]:
                    fig_line.update_traces(
                        hovertemplate="%{x}<br>%{y:.2f}%"
                    )
                else:
                    fig_line.update_traces(
                        hovertemplate="%{x}<br>%{y:.0f}"
                    )
                # Display plot
                st.plotly_chart(fig_line)

        with col3:
            # Bar plot (via plotly) for % difference if more than one airline is selected.
            if len(selected_airlines) > 1 and compare_yes_no=="Yes":
                # Generate the plot
                fig_bar = px.bar(
                    comparison_df[comparison_df["Airline"]!=base_airline][comparison_df["Metric"] == metric_display], 
                    x="Period", 
                    y="Percent Difference",
                    category_orders={"Period": sorted(data["Period"].unique(), reverse=False)}, # ensure x axis plots in chronological order
                    color="Airline",
                    barmode="group",
                    title=f"Percent Difference in {metric} vs {base_airline}",
                    color_discrete_map=airline_colors  # Apply custom color mapping
                    )
                # Update plot layout features
                fig_bar.update_layout(
                    xaxis_title=None,
                    yaxis_title="Percent Difference (%)",
                    xaxis_tickangle=-45
                    )
                # Add a more visible line at zero to more easily visually recognize positive and negative
                fig_bar.add_hline(
                    y=0, 
                    line_dash="dot", 
                    line_color="gray",
                    opacity=.75
                    )
                # Adjust the hover over display formatting to improve readability
                fig_bar.update_traces(
                    hovertemplate="%{x}<br>%{y:.2f}%"
                )
                # Display plot
                st.plotly_chart(fig_bar)

# Display a summary of the latest reporting period's metrics
with tab2:
    comparison_summary = comparison_df[comparison_df["Period"]==max(data["Period"])]
    # Column reformatting steps
    def format_value_based_on_metric(value, metric):
        if metric in ["Total Revenue (millions)", "Passenger Revenue (millions)", "Total Expenses (millions)", "Net Income (millions)", "Long-Term Debt (millions)", "Profit Sharing (millions)"]:
            return f"${value:,.0f}" if value.is_integer() else f"${value:,.2f}" # reformat currency columns to show $ sign
        elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
            return f"{value:,.2f}\u00A2" # reformat unit currency columns to show cents sign
        elif metric in ["Net Margin", "Load Factor"]:
            return f"{value:,.2f}%" # reformat percent columns to show % sign
        else:
            return f"{value:,.0f}" # ensure any other metric is displayed as a unitless integer for readability
    comparison_summary["Value"] = comparison_summary.apply(lambda row: format_value_based_on_metric(row["Value"], row["Metric"]), axis=1)
    comparison_summary["Percent Difference"] = comparison_summary["Percent Difference"].apply(lambda x: f"{x}%") # reformat percent difference column to show % sign
    comparison_summary = comparison_summary.set_index(["Metric", "Airline"], drop=True)
    comparison_summary = comparison_summary.rename(columns={"Percent Difference":f"vs {base_airline}"}) # rename percent difference column
    comparison_summary = comparison_summary.drop(columns=["Period"]) # drop period column as the summary only covers a single period
    comparison_summary = comparison_summary.rename(columns={"Value":f"{max(data["Period"])}"})
    if len(selected_airlines) <= 1:
        comparison_summary = comparison_summary.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
        comparison_summary = comparison_summary.unstack(level="Airline")
        comparison_summary.columns = comparison_summary.columns.swaplevel(0, 1)
        comparison_summary = comparison_summary.sort_index(axis=1, level=0)
    elif compare_yes_no=="Yes":
        comparison_summary = comparison_summary.unstack(level="Airline")
        comparison_summary.columns = comparison_summary.columns.swaplevel(0, 1)
        comparison_summary = comparison_summary.sort_index(axis=1, level=0)
        comparison_summary = comparison_summary.drop(columns=pd.IndexSlice[base_airline, f"vs {base_airline}"])
        conditional_color_columns = [(col, f"vs {base_airline}") for col in comparison_display.columns.levels[0] if (col, f"vs {base_airline}") in comparison_display.columns] # specify the percent difference columns for which to apply conditional color formatting
        comparison_summary = comparison_summary.style.applymap(color_positive_negative_zero, subset=conditional_color_columns).applymap_index(color_airlines, axis="columns", level="Airline") # map color of comparison column based on its sign and color of airline codes based on code (streamlit doesn't directly support color text in an index)
    elif compare_yes_no=="No":
        comparison_summary = comparison_summary.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
        comparison_summary = comparison_summary.unstack(level="Airline")
        comparison_summary.columns = comparison_summary.columns.swaplevel(0, 1)
        comparison_summary = comparison_summary.sort_index(axis=1, level=0)
    st.dataframe(comparison_summary)