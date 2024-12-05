import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
import yfinance as yf

# Set custom page configuration including the "About" section
st.set_page_config(
    page_title="US Airline Financial Performance Dashboard",  # Custom title in the browser tab
    page_icon=":airplane:",  # Custom icon for the browser tab
    layout="wide",  # Set the defaul layout for the app
    initial_sidebar_state="auto",  # Sidebar state when app loads
    menu_items={
        "About": """
        ## US Airline Financial Performance Dashboard
        This app enables quick and intuitive comparisons of the financial performance of major US commercial airlines.\n
        The Filtered Comparisons tab provides customizable views of airline financials. Several metrics can be selected for evaluation over chosen reporting periods.\n
        The Most Recent Year and Quarter Summaries tab gives a summary of the most recent annual and quarterly results for easy viewing.\n
        The Share Repurchases tab contains a high level overview of the share buyback programs by the Big 3 airilnes (AAL, DAL, UAL) that were carried out in the 2010s and ended with the onset of the Covid-19 pandemic.\n
        Unless otherwise noted, all metrics are either sourced or calculated from data given in the 10-Q/8-K (quarterly filings) and 10-K (annual filing) forms reported to the SEC and available on the airlines' investor relations sites linked below.\n
        [AAL](https://americanairlines.gcs-web.com/) | [DAL](https://ir.delta.com/) | [UAL](https://ir.united.com/) | [LUV](https://www.southwestairlinesinvestorrelations.com/)\n
        - **Author:** Michael Tricanowicz
        - **License:** MIT
        - **GitHub:** [airline_financials](https://github.com/mtricanowicz/airline_financials)
        """
    }
)

# Streamlit app title
st.title("Explore US Airline Financial Performance")

#CUSTOM CSS ADDITIONS
# Custom CSS to change tab header size
st.markdown("""
    <style>
    [data-testid="stTabs"] button div p {
        font-size: 22px;  /* Change this value to adjust text size */
        /*font-weight: bold;  Optional: Make the text bold */
    }
    </style>
    """, unsafe_allow_html=True)
st.markdown("""
    <style>
    [data-testid="stTabs"]:nth-of-type(2) button div p {
        font-size: 16px;  /* Change this value to adjust text size */
        /*font-weight: bold;  Optional: Make the text bold */
    }
    </style>
    """, unsafe_allow_html=True)
# Custom CSS for styling pills inside containers
st.markdown(
    """
    <style>
    /* Target the pills inside a container*/
    div[data-testid="stExpanderDetails"] div[data-testid="stVerticalBlock"] div[data-testid="stColumn"] div[data-testid="stElementContainer"] div[data-testid="stButtonGroup"] div[data-testid="stPills"] > div {
        font-size: 10px !important;  /* Change font size */
    }
    </style>
    """,
    unsafe_allow_html=True,
)
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


# Color palette to use for visualizaitons
airline_colors = {
    "AAL": "#9DA6AB", # AA Gray/Silver
    "DAL": "#C01933", # Delta Red
    "UAL": "#005daa",
    "ALK": "#00385f",
    "LUV": "#f9b612"
}

#####################################################################################
## DATA IMPORT AND PREP ##
# Load the data from XLSX
airline_financials = pd.read_excel("airline_financial_data.xlsx", sheet_name="airline_financials") # primary financial data and metrics
share_repurchases = pd.read_excel("airline_financial_data.xlsx", sheet_name="share_repurchases") # share repurchase data
# Airline financial data
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
airline_financials_fy = airline_financials[airline_financials["Quarter"] == "FY"].copy() # full year data
#airline_financials_fy["Date"] = pd.to_datetime(airline_financials_fy["Year"].astype(str) + "-12-31") # date ended up not being needed, keeping for future use if necessary
airline_financials_q = airline_financials[airline_financials["Quarter"] != "FY"].copy() # quarterly data
# Share repurchase data
# Add calculated and transformed columns
share_repurchases["Shares (millions)"] = share_repurchases["Shares Repurchased"]/1000000
share_repurchases["Cost (millions)"] = share_repurchases["Cost"]/1000000
share_repurchases["Average Share Cost"] = share_repurchases["Cost"]/share_repurchases["Shares Repurchased"]
share_repurchases["Average Share Cost"] = share_repurchases["Average Share Cost"].replace(np.nan, 0) # for years with zero shares purchased, address the NaN
share_repurchases["Period"] = share_repurchases["Year"].astype(str) + share_repurchases["Quarter"].astype(str)
#####################################################################################
# Definitions of the metrics
metric_definitions = [
    ("Total Revenue", "Total amount earned from sales."),
    ("Passenger Revenue", "Revenue primarily composed of passenger ticket sales, loyalty travel awards, and travel-related services performed in conjunction with a passenger's flight."),
    ("Total Expenses", "Total amount of costs incurred."),
    ("Net Income", "Profit."),
    ("Revenue Passenger Mile (RPM)", "A basic measure of sales volume. One RPM represents one passenger flown one mile."),
    ("Available Seat Mile (ASM)", "A basic measure of production. One ASM represents one seat flown one mile."),
    ("Long-Term Debt", "Total long-term debt net of current maturities.<br>NOTE: Due to inconsistent reporting in quarterly filings between airilnes, this metric is only shown for full year data."),
    ("Profit Sharing", "Amount of income set aside to fund employee profit sharing programs.<br>NOTE: AAL's quarterly reporting of this metric is inconsistent. Data provided may also have been obtained from internal sources. Additionally, zero profit sharing shown can either indicate no profit sharing or lack of reported data."),
    ("Net Margin", "Percentage of profit earned for each dollar in revenue. Net Income divided by Total Revenue."),
    ("Load Factor", "The percentage of available seats that are filled with revenue passengers. RPMs divided by ASMs."),
    ("Yield", "A measure of airline revenue derived by dividing Passenger Revenue by RPMs."),
    ("Total Revenue per Available Seat Mile (TRASM)", "Total Revenue divided by ASMs."),
    ("Passenger Revenue per Available Seat Mile (PRASM)", "Passenger Revenue divided by ASMs."),
    ("Cost per Available Seat Mile (CASM)", "Total Expenses divided by ASMs.")
]

#####################################################################################
#####################################################################################

# Create tabs
# Define top level tabs
tab1, tab2, tab3 = st.tabs(["Filtered Comparisons", "Most Recent Year and Quarter Summaries", "Share Repurchases"])

#####################################################################################
#####################################################################################

## USER FILTERED FINANCIAL COMPARISONS ##
# Display selected comparison data
with tab1:
#####################################################################################
    ## USER INTERACTION ##
    with st.expander("Expand to Set Filters", expanded=False):
        # Allow user to select time periods for comparison
        with st.container(border=True):
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            # Allow users to select full-year or quarterly data
            with filter_col1:
                data_type = st.pills("View Full Year or Quarterly Data?", ["Full Year", "Quarterly"], default="Full Year")
            if data_type == "Full Year":
                data = airline_financials_fy
            else:
                data = airline_financials_q
            # Allow user to select years for comparison
            years = sorted(data["Year"].unique())
            with filter_col2:
                selected_years = st.pills("Select Year(s) for Comparison", years, default=years, selection_mode="multi")
            if not selected_years:
                selected_years=years # prevents empty set from triggering an error, displays all years if none are selected        
            # Allow user to select quarters for comparison
            quarters = sorted(data["Quarter"].unique())
            with filter_col3:
                if data_type == "Quarterly":
                    selected_quarters = st.pills("Select Quarter(s) for Comparison", quarters, default=quarters, selection_mode="multi")
                    if not selected_quarters: # prevents empty set from triggering an error, displays all quarters if none are selected
                        selected_quarters=quarters
                elif data_type == "Full Year":
                    selected_quarters=quarters
        # Remove metrics from the data that do not have data for the chosen reporting period
        data = data.dropna(axis=1, how="all") # drop columns (metrics)        
        # Allow user to select airlines to compare
        airlines = data["Airline"].unique()
        with st.container(border=True):
            filter_col4, filter_col5, filter_col6 = st.columns(3)
            with filter_col4:
                selected_airlines = st.pills("Select Airline(s) for Comparison", airlines, default=["AAL", "DAL", "UAL"], selection_mode="multi")
                if not selected_airlines:
                    selected_airlines=[airlines[0]] # prevents empty set from triggering an error, displays AAL if none are selected        
            # Allow user to select a base airline to compare others against
            with filter_col5:
                if len(selected_airlines) > 1:
                    options_yes_no = ["Yes", "No"]
                    compare_yes_no = st.pills("Would you like to compare selected airlines' metrics against one of the airlines?", options_yes_no, default="Yes")
                    with filter_col6:
                        if(compare_yes_no=="Yes"):
                            base_airline = st.pills("Select Airline to Compare Against", selected_airlines, default=selected_airlines[0])
                        else:
                            base_airline = selected_airlines[0]
                else:
                    base_airline = selected_airlines[0]        
        # Allow user to select metrics to compare with a "Select All" option
        available_metrics = data.columns.drop(["Year", "Quarter", "Airline", "Period"])
        metric_groups = ["All", "Earnings", "Unit Performance", "Custom"]
        with st.container(border=True):
            filter_col7, filter_col8 = st.columns([1, 2])
            # Provide preselected groups of metrics and allow user to customize selection
            with filter_col7:
                metric_group_select = st.pills("Select Metrics for Comparison:", metric_groups, default="All")
                if metric_group_select=="All":
                    selected_metrics = available_metrics
                elif metric_group_select=="Earnings":
                    selected_metrics = ["Total Revenue", "Net Income", "Net Margin"]
                elif metric_group_select=="Unit Performance":
                    selected_metrics = ["Yield", "TRASM", "PRASM", "CASM"]
                elif metric_group_select=="Custom":
                    with filter_col8:
                        selected_metrics = st.pills("Add or Remove Metrics to Compare", available_metrics, default=available_metrics[0], selection_mode="multi")
                        if not selected_metrics:
                            selected_metrics = [available_metrics[0]] # prevents empty set from triggering an error, displays first metric in available metrics if none are selected
            # Add a toggle to display metric definitions for users who need them
            with st.container(border=False):
                definitions = st.checkbox("Show definitions of the available metrics.")
                if definitions:
                    for metric, definition in metric_definitions:
                        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
                        st.write(f"{metric} - {definition}", unsafe_allow_html=True)
                    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
#####################################################################################
    ## FILTERING, CALCULATIONS, AND FUNCTIONS ##
    # Filter data for selected airlines and metrics
    filtered_data = (data[data["Airline"].isin(selected_airlines)][data["Year"].isin(selected_years)][data["Quarter"].isin(selected_quarters)].copy()).sort_values(by="Period")
    # Define a function to compare values between airlines and output the percent difference
    def pct_diff(base, comparison):
        # Handle cases where base is zero to avoid division by zero
        if base == 0:
            return float(np.inf) if comparison != 0 else 0
        if pd.isna(base) or base==None or pd.isna(comparison) or comparison==None:
            return None
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
        base_values = base_values.reindex(filtered_data["Period"].unique())
        base_values = base_values.replace({np.nan: None})
        # Initiate all selected airline data and compare to the base airline
        for airline in selected_airlines:
            airline_values = filtered_data[filtered_data["Airline"] == airline].set_index(["Period"])[metric]
            airline_values = airline_values.reindex(filtered_data["Period"].unique())
            airline_values = airline_values.replace({np.nan: None})
            percent_difference = pd.Series([pct_diff(base, comp) for base, comp in zip(base_values, airline_values)]) # calculate percent difference between each airline and base airline
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

    # Define function to apply color based on the airline code
    def color_airlines(val):
        return f"color: {airline_colors.get(val, '')}" if val in airline_colors else ""
#####################################################################################
    ## OUTPUT/DISPLAY ##
    compare_tab1, compare_tab2 = st.tabs(["Metrics over Time", "Single Period"])
    # Display comparisons for metrics over time
    with compare_tab1:
        for metric in selected_metrics:
            # Reflect the renamed metrics new names
            if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
                metric_display = metric + " (millions)"
            else:
                metric_display = metric
            # Set title for the metric display
            st.header(f"{metric}", divider="gray")
            # Create display columns
            compare_col1, compare_col2, compare_col3 = st.columns(3)
            with compare_col1:
                # Display table for the metric to allow review of the data
                comparison_display = comparison_df[comparison_df["Metric"] == metric_display] # prepare a copy of the comparison table to be used for display
                comparison_display = comparison_display.rename(columns={"Value":metric_display}) # rename value column to make it more understandable
                comparison_display["Percent Difference"] = comparison_display["Percent Difference"].apply(lambda x: None if x is None or pd.isna(x) else f"{x}%") # reformat percent difference column to show % sign
                #comparison_display = comparison_display.style.set_table_styles([{"subset": ["Percent Difference"], "props": [("text-align", "right")]}])
                comparison_display = comparison_display.rename(columns={"Percent Difference":f"vs {base_airline}"}) # rename percent difference column to make it more understandable
                comparison_display = comparison_display.drop(columns=["Metric"]) # drop metric column as it is redundant for a table concerning only a single metric
                # Column reformatting steps
                if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing"]:
                    comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: None if x is None else f"{"-$" if x < 0 else "$"}{abs(x):,.0f}" if x.is_integer() else f"{"-$" if x < 0 else "$"}{abs(x):,.2f}") # reformat currency columns to show $ sign
                elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                    comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: None if x is None else f"{x:,.2f}\u00A2") # reformat unit currency columns to show cents sign
                elif metric in ["Net Margin", "Load Factor"]:
                    comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: None if x is None else f"{x:,.2f}%") # reformat percent columns to show % sign
                else:
                    comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: None if x is None else f"{x:,.0f}") # ensure any other metric is displayed as a unitless integer for readability
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
                    comparison_display = comparison_display.style.map(color_positive_negative_zero, subset=conditional_color_columns) # map color of comparison column based on its sign and color of airline codes based on code ([.map_index(color_airlines, axis="columns", level="Airline")] streamlit doesn't directly support color text in an index)
                elif len(selected_airlines) > 1 and compare_yes_no=="No":
                    comparison_display = comparison_display.set_index(["Period", "Airline"])
                    comparison_display = comparison_display.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
                    comparison_display = comparison_display.unstack(level="Airline")
                    comparison_display.columns = comparison_display.columns.swaplevel(0, 1)
                    comparison_display = comparison_display.sort_index(axis=1, level=0)
                st.dataframe(comparison_display, width=750) 
            with compare_col2:
                # Time series line plot (via plotly) for the metric's change over time if more than one time period (quarter or year) is selected.
                if len(selected_years)>1 or len(selected_quarters)>1:
                    # Generate the plot
                    fig_line = px.line(
                        filtered_data, 
                        x="Period", 
                        y=metric_display,
                        category_orders={"Period": sorted(filtered_data["Period"].unique(), reverse=False), "Airline": sorted(filtered_data["Airline"].unique(), reverse=False)}, # ensure x axis plots in chronological order
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
                            hovertemplate="%{x}<br>$%{y:,.0f}"
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
                            hovertemplate="%{x}<br>%{y:,.0f}"
                        )
                    # Display plot
                    st.plotly_chart(fig_line)
            with compare_col3:
                # Bar plot (via plotly) for % difference if more than one airline is selected.
                if len(selected_airlines) > 1 and compare_yes_no=="Yes":
                    # Generate the plot
                    fig_bar = px.bar(
                        comparison_df[comparison_df["Airline"]!=base_airline][comparison_df["Metric"] == metric_display], 
                        x="Period", 
                        y="Percent Difference",
                        category_orders={"Period": sorted(filtered_data["Period"].unique(), reverse=False), "Airline": sorted(filtered_data["Airline"].unique(), reverse=False)}, # ensure x axis plots in chronological order
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
    # Display a summary of the selected metrics for the selected airlines in the latest reporting period in the selected range
    with compare_tab2:
        st.header(f"Summary of {max(filtered_data["Period"])} Metrics", divider='gray')
        st.write("NOTE: If multiple years and/or quarters are selected, this summary table shows for the last period in the range.")
        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        comparison_summary = comparison_df[comparison_df["Period"]==max(filtered_data["Period"])]
        # Column reformatting steps
        def format_value_based_on_metric(value, metric):
            if metric in ["Total Revenue (millions)", "Passenger Revenue (millions)", "Total Expenses (millions)", "Net Income (millions)", "Long-Term Debt (millions)", "Profit Sharing (millions)"]:
                return f"{"-$" if value < 0 else "$"}{abs(value):,.0f}" if value.is_integer() else f"{"-$" if value < 0 else "$"}{abs(value):,.2f}" # reformat currency columns to show $ sign
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
        comparison_summary = comparison_summary.rename(columns={"Value":f"{max(filtered_data["Period"])}"})
        ordered_metrics = [item + " (millions)" if i < len(available_metrics)-6 else item for i, item in enumerate(available_metrics)]
        if len(selected_airlines) <= 1:
            comparison_summary = comparison_summary.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
            comparison_summary = comparison_summary.unstack(level="Airline")
            comparison_summary.columns = comparison_summary.columns.swaplevel(0, 1)
            comparison_summary = comparison_summary.sort_index(axis=1, level=0)
            comparison_summary = comparison_summary.reindex([item for item in ordered_metrics if item in comparison_summary.index])
        elif compare_yes_no=="Yes":
            comparison_summary = comparison_summary.unstack(level="Airline")
            comparison_summary.columns = comparison_summary.columns.swaplevel(0, 1)
            comparison_summary = comparison_summary.sort_index(axis=1, level=0)
            comparison_summary = comparison_summary.drop(columns=pd.IndexSlice[base_airline, f"vs {base_airline}"])
            comparison_summary = comparison_summary.reindex([item for item in ordered_metrics if item in comparison_summary.index])
            conditional_color_columns = [(col, f"vs {base_airline}") for col in comparison_display.columns.levels[0] if (col, f"vs {base_airline}") in comparison_display.columns] # specify the percent difference columns for which to apply conditional color formatting
            comparison_summary = comparison_summary.style.map(color_positive_negative_zero, subset=conditional_color_columns) # map color of comparison column based on its sign and color of airline codes based on code ([.map_index(color_airlines, axis="columns", level="Airline")] streamlit doesn't directly support color text in an index)
        elif compare_yes_no=="No":
            comparison_summary = comparison_summary.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
            comparison_summary = comparison_summary.unstack(level="Airline")
            comparison_summary.columns = comparison_summary.columns.swaplevel(0, 1)
            comparison_summary = comparison_summary.sort_index(axis=1, level=0)
            comparison_summary = comparison_summary.reindex([item for item in ordered_metrics if item in comparison_summary.index])
        st.dataframe(comparison_summary, width=1250, height=(len(selected_metrics)+2)*35+3)

#####################################################################################
#####################################################################################

## MOST RECENT YEAR AND QUARTER SUMMARY FOR ALL AIRLINES AND ALL METRICS ##
# Display a summary of the latest reporting periods' metrics
with tab2:
    summary_col1, summary_col2, summary_col3 = st.columns([2, 2, 1])
#####################################################################################
    ## USER INTERACTION ##
    with summary_col3:
        # Allow user to select a base airline to compare others against
        with st.container(border=True):
            compare_yes_no_2 = st.pills("Would you like to compare against one of the airlines?", options_yes_no, default="No")
            if(compare_yes_no_2=="Yes"):
                base_airline_2 = st.pills("Select Airline to Compare Against", airlines, default=airlines[0], key="base_tab2")
            else:
                base_airline_2 = airlines[0]
        # Add a toggle to display metric definitions for users who need them
        with st.expander("Show definitions of the metrics.", expanded=False):
            for metric, definition in metric_definitions:
                st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
                st.write(f"{metric} - {definition}", unsafe_allow_html=True)
            st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
#####################################################################################
    ## FILTERING, CALCULATIONS, AND FUNCTIONS ##
    # Filter data for most recent year and quarter
    summary_data_fy = airline_financials_fy[airline_financials_fy["Period"]==max(airline_financials_fy["Period"].unique())].dropna(axis=1, how="all")
    summary_data_q = airline_financials_q[airline_financials_q["Period"]==max(airline_financials_q["Period"].unique())].dropna(axis=1, how="all")
    # Column reformatting steps
    def format_value_based_on_metric(value, metric):
        if metric in ["Total Revenue (millions)", "Passenger Revenue (millions)", "Total Expenses (millions)", "Net Income (millions)", "Long-Term Debt (millions)", "Profit Sharing (millions)"]:
            return f"{"-$" if value < 0 else "$"}{abs(value):,.0f}" if value.is_integer() else f"{"-$" if value < 0 else "$"}{abs(value):,.2f}" # reformat currency columns to show $ sign
        elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
            return f"{value:,.2f}\u00A2" # reformat unit currency columns to show cents sign
        elif metric in ["Net Margin", "Load Factor"]:
            return f"{value:,.2f}%" # reformat percent columns to show % sign
        else:
            return f"{value:,.0f}" # ensure any other metric is displayed as a unitless integer for readability
    # Define function to transform data for display
    def data_transform(data):
        ordered_metrics = [item + " (millions)" if i < len((data.columns).intersection(data.columns.drop(["Year", "Quarter", "Airline", "Period"])))-6 else item for i, item in enumerate((data.columns).intersection(data.columns.drop(["Year", "Quarter", "Airline", "Period"])))]
        data_transformed = []
        for metric in (data.columns).intersection(data.columns.drop(["Year", "Quarter", "Airline", "Period"])):
            # Adjust some of the metrics to scale better for display
            if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
                data[metric] = data[metric] / 1000000
                data.rename(columns={metric:f"{metric} (millions)"}, inplace=True)
                metric = metric + " (millions)"
            elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                data[metric] = data[metric] * 100
            # Initiate base airline data
            base_values = data[data["Airline"] == base_airline_2].set_index(["Period"])[metric]
            base_values = base_values.reindex(data["Period"].unique())
            base_values = base_values.replace({np.nan: None})
            # Initiate all selected airline data and compare to the base airline
            for airline in data["Airline"].unique():
                airline_values = data[data["Airline"] == airline].set_index(["Period"])[metric]
                airline_values = airline_values.reindex(data["Period"].unique())
                airline_values = airline_values.replace({np.nan: None})
                percent_difference = pd.Series([pct_diff(base, comp) for base, comp in zip(base_values, airline_values)]) # calculate percent difference between each airline and base airline
                data_transformed.append(pd.DataFrame({
                    "Period": airline_values.index,
                    "Airline": airline,
                    "Metric": metric,
                    "Value": airline_values.values,
                    "Percent Difference": percent_difference.values
                    })
                )
        data_transformed_df = pd.concat(data_transformed) # output the comparison dataframe
        data_transformed_df = data_transformed_df.reset_index(drop=True)
        data_transformed_df["Value"] = data_transformed_df.apply(lambda row: format_value_based_on_metric(row["Value"], row["Metric"]), axis=1)
        data_transformed_df["Percent Difference"] = data_transformed_df["Percent Difference"].apply(lambda x: f"{x}%") # reformat percent difference column to show % sign
        data_transformed_df = data_transformed_df.set_index(["Metric", "Airline"], drop=True)
        data_transformed_df = data_transformed_df.rename(columns={"Percent Difference":f"vs {base_airline_2}"}) # rename percent difference column
        data_transformed_df = data_transformed_df.drop(columns=["Period"]) # drop period column as the summary only covers a single period
        data_transformed_df = data_transformed_df.rename(columns={"Value":f"{max(data["Period"])}"})
        if compare_yes_no_2=="Yes":
            data_transformed_df = data_transformed_df.unstack(level="Airline")
            data_transformed_df.columns = data_transformed_df.columns.swaplevel(0, 1)
            data_transformed_df = data_transformed_df.sort_index(axis=1, level=0)
            data_transformed_df = data_transformed_df.drop(columns=pd.IndexSlice[base_airline_2, f"vs {base_airline_2}"])
            data_transformed_df = data_transformed_df.reindex([item for item in ordered_metrics])# if item in data_transformed_df.index], axis=0)
            conditional_color_columns_2 = [(col, f"vs {base_airline_2}") for col in data_transformed_df.columns.levels[0] if (col, f"vs {base_airline_2}") in data_transformed_df.columns] # specify the percent difference columns for which to apply conditional color formatting
            data_transformed_df = data_transformed_df.style.map(color_positive_negative_zero, subset=conditional_color_columns_2) # map color of comparison column based on its sign and color of airline codes based on code ([.map_index(color_airlines, axis="columns", level="Airline")] streamlit doesn't directly support color text in an index)
        elif compare_yes_no_2=="No":
            data_transformed_df = data_transformed_df.drop(columns=f"vs {base_airline_2}") # do not display percent difference column if user chooses not to compare
            data_transformed_df = data_transformed_df.unstack(level="Airline")
            data_transformed_df.columns = data_transformed_df.columns.swaplevel(0, 1)
            data_transformed_df = data_transformed_df.sort_index(axis=1, level=0)
            data_transformed_df = data_transformed_df.reindex([item for item in ordered_metrics if item in data_transformed_df.index], axis=0)
        return data_transformed_df
#####################################################################################
    ## OUTPUT/DISPLAY ##
    with summary_col1:
        st.header(f"Most Recent Full Year: {max(summary_data_fy["Period"])}", divider='gray')
        summary_fy = data_transform(summary_data_fy)
        st.dataframe(summary_fy, width=1000, height=(len(summary_fy.index)+2)*35+3)
    with summary_col2:
        st.header(f"Most Recent Quarter: {max(summary_data_q["Period"])}", divider='gray')
        summary_q = data_transform(summary_data_q)
        st.dataframe(summary_q, width=1000, height=(len(summary_q.index)+2)*35+3)

#####################################################################################
#####################################################################################

## SHARE REPURCHASES ##
# Display share repurchase history of the Big 3 airlines (AAL, DAL, UAL)
with tab3:
#####################################################################################
    ## FILTERING, CALCULATIONS, AND FUNCTIONS ##
    # Define function to fetch most recent close prices of a set of tickers
    # Date variable to ensure most recent close date is used to fetch latest closing price of the airlines' stock
    ticker_date = (datetime.now(pytz.timezone("America/New_York"))-timedelta(days=1)) if datetime.now(pytz.timezone("America/New_York")).hour<16 else datetime.now(pytz.timezone("America/New_York")) # set date for closing price (yesterday if market is still open else today) since yfinance's Close data is the latest price when the market is open
    # Function
    def fetch_last_close_prices(tickers, ticker_date, max_retries=31):
        retries = 0
        while retries < max_retries: # continuing trying to pull close price for 31 days prior to current day if request doesn't return price data
            try:
                close_prices = yf.Tickers(tickers).history(period="1d", start=ticker_date, end=ticker_date)["Close"]
                if not close_prices.empty:  # Check if no data was returned
                    return close_prices # if data fetched return the close prices
                ticker_date -= timedelta(days=1) # otherwise go back one day and try again (intended to deal with days the market isn't open when yfinance seems to have no price data)
            except Exception as e: # Handle exceptions and return an error message
                return f"Error fetching stock price: {e}"
            retries += 1
        return "Max attempts reached. Stock price could not be retrieved."
    # Define function to fetch daily close prices since the start of 2020Q2 (first quarter after share buybacks were ceased due to Covid-19)
    def fetch_daily_close(tickers, start_date, end_date, max_retries=10):
        retries = 0
        while retries < max_retries:
            try:
                close_history = yf.Tickers(tickers).history(period="1d", start=start_date, end=end_date)["Close"]
                if not close_history.empty:  # Check if no data was returned
                    return close_history # if data fetched return the close prices
            except Exception as e: # Handle exceptions and return an error message
                return f"Error fetching stock price: {e}"
            retries += 1
        return "Max attempts reached. Stock price could not be retrieved."
#####################################################################################
    ## OUTPUT/DISPLAY ##
    st.header("2010s Big 3 Share Buyback Campaign", divider='gray')
    # Create display columns
    col1, col2 = st.columns([1, 2])
    # Information about the repurchase programs
    with col1:
        # Aggregate values
        total_shares_repurchase = share_repurchases.groupby("Airline")["Shares (millions)"].sum()
        total_cost_repurchase = share_repurchases.groupby("Airline")["Cost (millions)"].sum()
        total_average_share_cost = total_cost_repurchase/total_shares_repurchase
        # Define ticker symbols and fetch last close prices
        tickers = share_repurchases["Airline"].unique().tolist() # repurchase campaign airline tickers
        last_close = fetch_last_close_prices(tickers, ticker_date)
        # Repurchase program summaries for each airline
        for airline in share_repurchases["Airline"].unique():
            # Display airline ticker for identification
            st.markdown(f"<h4>{airline}</h4>", unsafe_allow_html=True)
            # Set up the last close price variable to be able to handle error messages generated by the close price function
            if isinstance(last_close, str):
                close_value = last_close
                close_display = close_value
            else:
                close_value = last_close[airline].iloc[0]
                close_display = f"${close_value:.2f}" 
            # Display information about the airline's repurchase program
            st.markdown(f"{airline} repurchased **{total_shares_repurchase[airline]:.1f} million** shares at a total cost of **\${(total_cost_repurchase[airline]/1000):.1f} billion**.<br>"
                        f"The average share price of repurchase was **\${total_average_share_cost[airline]:.2f}**. {airline} last closed at **{close_display}**.<br>"
                        f"Based on the current share price, the repurchase campaign netted {airline}:"
                        , unsafe_allow_html=True)
            # Display the gain/loss based on the average repurchase price and current share price
            # Set up the repurchase program gain variable to be able to handle error messages generated by the close price function
            if isinstance(close_value, str):
                repurchase_net_value = close_value
                repurchase_net_display = repurchase_net_value
            else:
                repurchase_net_value = ((close_value-total_average_share_cost[airline])/1000)*total_shares_repurchase[airline]
                repurchase_net_color = "green" if repurchase_net_value > 0 else "black" if repurchase_net_value==0 else "red"
                repurchase_net_display = f"<p style='margin-bottom:0;'><h3 style='color:{repurchase_net_color};'>{f"{'-$' if repurchase_net_value < 0 else '$'}{abs(repurchase_net_value):,.1f} billion {"&nbsp;"*10} {"🔥💰🔥" if repurchase_net_value<0 else "🤷" if repurchase_net_value==0 else "💸💸💸"}"}</h3></p>"
            st.markdown(repurchase_net_display, unsafe_allow_html=True)
    # Historical repurchase data for viewing
    with col2:
        # Prepare data for display
        shares_display = share_repurchases.copy()
        shares_display = shares_display.drop(columns=["Year", "Quarter", "Shares Repurchased", "Cost"])
        shares_display["Shares (millions)"] = shares_display["Shares (millions)"].apply(lambda x: f"{x:,.1f}")
        shares_display["Cost (millions)"] = shares_display["Cost (millions)"].apply(lambda x: f"${x:,.0f}")
        shares_display["Average Share Cost"] = shares_display["Average Share Cost"].apply(lambda x: f"${x:,.2f}")
        shares_display = shares_display.set_index(["Period", "Airline"])
        shares_display = shares_display.unstack(level="Airline")
        shares_display.columns = shares_display.columns.swaplevel(0, 1)
        shares_display.columns = pd.MultiIndex.from_tuples(
            sorted(shares_display.columns, key=lambda x: ["Shares (millions)", "Cost (millions)", "Average Share Cost"].index(x[1]))
        )
        shares_display = shares_display.sort_index(axis=1, level=0, sort_remaining=False)
        st.markdown("<h4>Share Repurchase History</h4>", unsafe_allow_html=True)
        st.dataframe(shares_display)
        # Prepare data to plot gain/loss from repurchases over time since Covid onset
        # Fetch daily closing price since start of 2020Q2
        ticker_since_covid = fetch_daily_close(tickers, "2020-04-01", datetime.now())
        # Calculate the daily gain/loss in billions based on average repurchase price minus closing price multiplied by number of shares repurchased
        gain = pd.DataFrame()
        for airline in share_repurchases["Airline"].unique():
            gain[airline] = ticker_since_covid[airline].apply(lambda x: (x - total_average_share_cost[airline])*total_shares_repurchase[airline]/1000)
        gain_melt = pd.melt(gain.reset_index(), id_vars="Date", var_name="Airline", value_name="Gain")
        # Generate a line plot for each airline's gain/loss over time
        fig_line2 = px.line(
            gain_melt, 
            x="Date", 
            y="Gain",
            color="Airline",
            title="Gain/Loss of the Share Repurchase Programs Since the Onset of Covid-19",
            color_discrete_map=airline_colors  # Apply custom color mapping
        )
        # Update plot layout features
        fig_line2.update_layout(
            xaxis_title=None,
            yaxis_title="Gain/Loss (billions)",
            xaxis_tickangle=-45
        )
        # Add a more visible line at zero to more easily visually recognize positive and negative
        fig_line2.add_hline(
            y=0, 
            line_dash="dot", 
            line_color="black",
            opacity=0.5
        )
        # Adjust the hover over display formatting to improve readability
        fig_line2.update_traces(
            hovertemplate="%{x}<br>%{y:.1f} billion", #"%{x}<br>$%{y:.1f}"
            hoverinfo="text"
        )
        st.plotly_chart(fig_line2)
#####################################################################################