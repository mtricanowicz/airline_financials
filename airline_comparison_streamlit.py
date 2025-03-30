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
import openai
import os
import requests
from bs4 import BeautifulSoup
import calendar
from dateutil.relativedelta import relativedelta
import re
import time
from langchain_community.document_loaders import PyPDFLoader
import logging
import tempfile
# Correct sqlite3 version mismatch when deployed to Streamlit prior to importing ChromaDB libraries. Mismatch is between Streamlit and ChromaDB. 
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import chromadb
from chromadb.api.models.Collection import Collection

# Set custom page configuration including the "About" section
st.set_page_config(
    page_title="Airline Financial Dashboard",  # Custom title in the browser tab
    page_icon=":airplane:",  # Custom icon for the browser tab
    layout="wide",  # Set the defaul layout for the app
    initial_sidebar_state="auto",  # Sidebar state when app loads
    menu_items={
        "About": """
        ## Airline Financial Dashboard
        This dashboard enables quick and intuitive comparisons of the financial performance of major US commercial airlines. Data is provided from 2014. This starting point was chosen because it was the first year after all of the major airlines had completed mergers, marking the completion of a cycle of consolidation and the start of the present industry landscape.\n
        The airlines covered (and their stock tickers) are American Airlines (AAL), Delta Air Lines (DAL), United Airlines (UAL), and Southwest Airlines (LUV). LUV quarterly data is provided from 2024.\n
        The Filtered Comparisons tab provides customizable views of airline financials. Several metrics can be selected for evaluation over chosen reporting periods.\n
        The Latest Results tab gives a summary of the most recent annual and quarterly results for easy viewing.\n
        The Share Repurchases tab contains a high level overview of the share buyback programs by the Big 3 airilnes (AAL, DAL, UAL) that were carried out in the 2010s and ended with the onset of the Covid-19 pandemic.\n
        The Insights tab delivers financial, operational, and organizational insights based on the airilne's SEC filings. User selections prompt retrieval of relevant SEC filings which are processed and passed to ChatGPT to summarize for a particular airline and time period. The accuracy of the content provided cannot be guaranteed.\n
        Unless otherwise noted, all metrics are either sourced or calculated from data given in the 10-Q (quarterly filing), 8-K (current report), and 10-K (annual filing) forms reported to the SEC and available on the airlines' investor relations sites linked below.\n
        [AAL](https://americanairlines.gcs-web.com/) | [DAL](https://ir.delta.com/) | [UAL](https://ir.united.com/) | [LUV](https://www.southwestairlinesinvestorrelations.com/)\n
        **Created by:** Michael Tricanowicz
        """
    }
)

# Dashboard title
st.title("Explore US Airline Financial Performance")

# CUSTOM CSS ADDITIONS
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
# Custom CSS to style buttons
st.markdown(
    """
    <style>
    /* Target the Streamlit button */
    div[data-testid="stButton"] > button {
        font-size: 10px !important;  /* Change font size */
        font-weight: bold;           /* Make text bold */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
share_sales = pd.read_excel("airline_financial_data.xlsx", sheet_name="share_sales") # share sale data during Covid-19
# Airline financial data
# Add calculated metrics
airline_financials["Operating Income"] = airline_financials["Total Revenue"] - airline_financials["Total Expenses"]
airline_financials["Operating Margin"] = round((airline_financials["Operating Income"] / airline_financials["Total Revenue"]) * 100, 2)
airline_financials["Net Margin"] = round((airline_financials["Net Income"] / airline_financials["Total Revenue"]) * 100, 2)
airline_financials["Load Factor"] = round((airline_financials["RPM"] / airline_financials["ASM"]) * 100, 2)
airline_financials["Yield"] = airline_financials["Passenger Revenue"] / airline_financials["RPM"]
airline_financials["TRASM"] = airline_financials["Total Revenue"] / airline_financials["ASM"]
airline_financials["PRASM"] = airline_financials["Passenger Revenue"] / airline_financials["ASM"]
airline_financials["CASM"] = airline_financials["Total Expenses"] / airline_financials["ASM"]
# Create a Period column to represent the fiscal period and to use for data display
airline_financials["Quarter"] = airline_financials["Quarter"].apply(lambda x: f"Q{x}" if x != "FY" else x)
airline_financials["Period"] = airline_financials["Year"].astype(str) + airline_financials["Quarter"].astype(str)
# Reorder columns to have calculated Operating Income with other reported income/expense columns
reordered_columns = list(airline_financials.columns)
reordered_columns.remove("Operating Income")
reordered_columns.insert(6, ("Operating Income"))
airline_financials = airline_financials[reordered_columns]
# Split data into full-year and quarterly DataFrames
airline_financials_fy = airline_financials[airline_financials["Quarter"] == "FY"].copy() # full year data
airline_financials_q = airline_financials[airline_financials["Quarter"] != "FY"].copy() # quarterly data
# Share repurchase data
# Add calculated and transformed columns
share_repurchases["Shares (millions)"] = share_repurchases["Shares Repurchased"]/1000000
share_repurchases["Cost (millions)"] = share_repurchases["Cost"]/1000000
share_repurchases["Average Share Price"] = share_repurchases["Cost"]/share_repurchases["Shares Repurchased"]
share_repurchases["Average Share Price"] = share_repurchases["Average Share Price"].replace(np.nan, 0) # for years with zero shares purchased, address the NaN
share_repurchases["Period"] = share_repurchases["Year"].astype(str) + share_repurchases["Quarter"].astype(str)
# Share sale data
# Add calculated and transformed columns
share_sales["Shares (millions)"] = share_sales["Shares Sold"]/1000000
share_sales["Proceeds (millions)"] = share_sales["Proceeds"]/1000000
share_sales["Average Share Price"] = share_sales["Proceeds"]/share_sales["Shares Sold"]
share_sales["Average Share Price"] = share_sales["Average Share Price"].replace(np.nan, 0) # for years with zero shares purchased, address the NaN
share_sales["Period"] = share_sales["Year"].astype(str) + share_sales["Quarter"].astype(str)
#####################################################################################
# Definitions of the metrics
metric_definitions = [
    ("Total Revenue", "Total amount earned from operations."),
    ("Passenger Revenue", "Revenue primarily composed of passenger ticket sales, loyalty travel awards, and travel-related services performed in conjunction with a passenger's flight."),
    ("Total Expenses", "Total amount of costs incurred from operations."),
    ("Operating Income", "Income from operations. Total Revenue minus Total Expenses."),
    ("Net Income", "Profit."),
    ("Revenue Passenger Mile (RPM)", "A basic measure of sales volume. One RPM represents one passenger flown one mile."),
    ("Available Seat Mile (ASM)", "A basic measure of production. One ASM represents one seat flown one mile."),
    ("Long-Term Debt", "Total long-term debt net of current maturities.<br>NOTE: This metric is reported annually and is therefore shown only for full year data and sourced from 10K filings."),
    ("Profit Sharing", "Amount of income set aside to fund employee profit sharing programs.<br>NOTE: Quarterly reporting by AAL and UAL of this metric is inconsistent. Data provided may have been obtained from internal sources or estimated by proportioning the annual profit sharing reported by the quarterly operating income reported."),
    ("Operating Margin", "Operating Income divided by Total Revenue"),
    ("Net Margin", "Percentage of profit earned for each dollar in revenue. Net Income divided by Total Revenue."),
    ("Load Factor", "The percentage of available seats that are filled with revenue passengers. RPMs divided by ASMs."),
    ("Yield", "A measure of airline revenue derived by dividing Passenger Revenue by RPMs."),
    ("Total Revenue per Available Seat Mile (TRASM)", "Total Revenue divided by ASMs."),
    ("Passenger Revenue per Available Seat Mile (PRASM)", "Passenger Revenue divided by ASMs."),
    ("Cost per Available Seat Mile (CASM)", "Total Expenses divided by ASMs.")
]
#####################################################################################
# Create global yes/no options variable
options_yes_no = ["Yes", "No"]

#####################################################################################
#####################################################################################

# Create tabs
# Define top level tabs
tab1, tab2, tab3, tab4 = st.tabs(["Filtered Comparisons", "Latest Results", "Share Repurchases", "Insights"])

#####################################################################################
#####################################################################################

## USER FILTERED FINANCIAL COMPARISONS ##
# Display selected comparison data
#####################################################################################
## SESSION STATE SETUP ##
# Initialize a session state that will control when this tab reruns.
if 'apply_filters' not in st.session_state:
    st.session_state.apply_filters = True
# Initialize a rerun count session state to trigger an extra rerun when applying filters to ensure filters apply properly and don't cause errors in the visualization.
if 'rerun_count' not in st.session_state:
    st.session_state.rerun_count = 2
# Initialize a session state that contains the default selections and that will be updated with user selections for this tab
if "tab1" not in st.session_state:
    st.session_state.tab1 = {
        "data_type": "Full Year",
        "selected_years": sorted(airline_financials_fy["Year"].unique()),
        "selected_quarters": sorted(airline_financials_fy["Quarter"].unique()),
        "selected_airlines": ["AAL", "DAL", "UAL"],
        "compare_yes_no": "Yes",
        "base_airline": airline_financials_fy["Airline"].unique()[0],
        "metric_group_select": "All",
        "selected_metrics": airline_financials_fy.columns.drop(["Year", "Quarter", "Airline", "Period"])[0]
        }
# Define function to update the tab session variables
def update_tab1():
    st.session_state.tab1["data_type"] = st.session_state.data_type
    st.session_state.tab1["selected_years"] = st.session_state.selected_years
    st.session_state.tab1["selected_quarters"] = st.session_state.selected_quarters
    st.session_state.tab1["selected_airlines"] = st.session_state.selected_airlines
    st.session_state.tab1["compare_yes_no"] = st.session_state.compare_yes_no
    st.session_state.tab1["base_airline"] = st.session_state.base_airline
    st.session_state.tab1["metric_group_select"] = st.session_state.metric_group_select
    st.session_state.tab1["selected_metrics"] = st.session_state.selected_metrics
#####################################################################################
with tab1:
#####################################################################################
    ## USER INTERACTION ##
    with st.expander("Expand to Set Filters", expanded=False):
        # Allow user to select time periods for comparison
        with st.container(border=True):
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            # Allow users to select full-year or quarterly data
            with filter_col1:
                st.session_state.data_type = st.pills("View Full Year or Quarterly Data?", ["Full Year", "Quarterly"], default="Full Year")
                data_type = st.session_state.tab1["data_type"]
            if data_type == "Full Year":
                data = airline_financials_fy
            else:
                data = airline_financials_q
            # Allow user to select years for comparison
            years = sorted(data["Year"].unique())
            with filter_col2:
                st.session_state.selected_years = st.pills("Select Year(s) for Comparison", years, default=years, selection_mode="multi")
                selected_years = st.session_state.tab1["selected_years"]
            if not selected_years:
                selected_years=years # prevents empty set from triggering an error, displays all years if none are selected        
            # Allow user to select quarters for comparison
            quarters = sorted(data["Quarter"].unique())
            with filter_col3:
                if data_type == "Quarterly":
                    st.session_state.selected_quarters = st.pills("Select Quarter(s) for Comparison", quarters, default=quarters, selection_mode="multi")
                    selected_quarters = st.session_state.tab1["selected_quarters"]
                    if not selected_quarters: # prevents empty set from triggering an error, displays all quarters if none are selected
                        selected_quarters=quarters
                elif data_type == "Full Year":
                    st.session_state.selected_quarters = quarters
                    selected_quarters = quarters
        # Remove metrics from the data that do not have data for the chosen reporting period
        data = data.dropna(axis=1, how="all") # drop columns (metrics)        
        # Allow user to select airlines to compare
        airlines = data["Airline"].unique()
        with st.container(border=True):
            filter_col4, filter_col5, filter_col6 = st.columns(3)
            with filter_col4:
                st.session_state.selected_airlines = st.pills("Select Airline(s) for Comparison", airlines, default=["AAL", "DAL", "UAL"], selection_mode="multi")
                selected_airlines = st.session_state.tab1["selected_airlines"]
                if not selected_airlines:
                    selected_airlines=[airlines[0]] # prevents empty set from triggering an error, displays AAL if none are selected        
            # Allow user to select a base airline to compare others against
            with filter_col5:
                if len(selected_airlines) > 1:
                    st.session_state.compare_yes_no = st.pills("Would you like to compare selected airlines' metrics against one of the airlines?", options_yes_no, default="Yes")
                    compare_yes_no = st.session_state.tab1["compare_yes_no"]
                    with filter_col6:
                        if(compare_yes_no=="Yes"):
                            st.session_state.base_airline = st.pills("Select Airline to Compare Against", selected_airlines, default=selected_airlines[0])
                            base_airline = st.session_state.tab1["base_airline"]
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
                st.session_state.metric_group_select = st.pills("Select Metrics for Comparison:", metric_groups, default="All")
                metric_group_select = st.session_state.tab1["metric_group_select"]
                if metric_group_select=="All":
                    selected_metrics = available_metrics
                    st.session_state.selected_metrics = None
                elif metric_group_select=="Earnings":
                    selected_metrics = ["Total Revenue", "Operating Income", "Net Income", "Operating Margin", "Net Margin"]
                    st.session_state.selected_metrics = None
                elif metric_group_select=="Unit Performance":
                    selected_metrics = ["Yield", "TRASM", "PRASM", "CASM"]
                    st.session_state.selected_metrics = None
                elif metric_group_select=="Custom":
                    with filter_col8:
                        st.session_state.selected_metrics = st.pills("Add or Remove Metrics to Compare", available_metrics, default=available_metrics[0], selection_mode="multi")
                        selected_metrics = st.session_state.tab1["selected_metrics"]
                        if not selected_metrics:
                            selected_metrics = [available_metrics[0]] # prevents empty set from triggering an error, displays first metric in available metrics if none are selected
                # Add a popover to display metric definitions for users who need them
                with st.popover(icon=":material/dictionary:", label="Show definitions of the available metrics.", use_container_width=True):
                    for metric, definition in metric_definitions:
                        st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
                        st.write(f"{metric} - {definition}", unsafe_allow_html=True)
                    st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        def apply_filters_button():
            st.session_state.apply_filters = True
        st.button("Apply Filters", type="primary", on_click=apply_filters_button)
        if st.session_state.apply_filters:
            update_tab1() # update the filter session states
            # Check if it's the first rerun, and trigger the first rerun
            if st.session_state.rerun_count == 0:
                st.session_state.rerun_count = 1
                st.rerun()
            # After the first rerun, trigger the second rerun
            elif st.session_state.rerun_count == 1:
                st.session_state.rerun_count = 2
                st.rerun()
#####################################################################################
    ## FUNCTIONS ##
    # Define a function to compare values between airlines and output the percent difference
    def pct_diff(base, comparison):
        # Handle cases where one or both of the comparison values don't exist
        if pd.isna(base) or base==None or base==np.nan or pd.isna(comparison) or comparison==None or comparison==np.nan:
            return None
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
    ## FILTERING AND CALCULATIONS ##
    # Filter data for selected airlines and metrics
    filtered_data = (data[data["Airline"].isin(selected_airlines)][data["Year"].isin(selected_years)][data["Quarter"].isin(selected_quarters)].copy()).sort_values(by="Period")
    # Calculate percentage difference from the base airline and generate a comparison table with chosen metrics
    comparison_data = []
    for metric in selected_metrics:
        # Adjust some of the metrics to scale better for display
        if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Operating Income", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
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
#####################################################################################
    ## OUTPUT/DISPLAY ##
    compare_tab1, compare_tab2 = st.tabs(["Metrics over Time", "Single Period"])
    # Display comparisons for metrics over time
    with compare_tab1:
        for metric in selected_metrics:
            # Reflect the renamed metrics new names
            if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Operating Income", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
                metric_display = metric + " (millions)"
            else:
                metric_display = metric
            # Set title for the metric display
            st.header(f"{metric}", divider="gray")
            # Create display columns
            # Check if the time comparison conditions are active
            show_compare_col2 = len(selected_years)>1 or len(selected_quarters)>1
            # Check if the airline comparison conditions are active
            show_compare_col3 = len(selected_airlines) > 1 and compare_yes_no == "Yes"
            # Create display columns conditionally depending on user selected filters
            if not show_compare_col2 and not show_compare_col3:
                compare_col1, = st.columns(1)
            elif show_compare_col2 and not show_compare_col3:
                compare_col1, compare_col2 = st.columns([2,3])
            elif not show_compare_col2 and show_compare_col3:
                compare_col1, compare_col3 = st.columns(2)
            else:
                compare_col1, compare_col2, compare_col3 = st.columns(3)
            # Conditionally display the appropriate columns
            with compare_col1:
                # Display table for the metric to allow review of the data
                comparison_display = comparison_df[comparison_df["Metric"] == metric_display] # prepare a copy of the comparison table to be used for display
                comparison_display = comparison_display.rename(columns={"Value":metric_display}) # rename value column to make it more understandable
                comparison_display["Percent Difference"] = comparison_display["Percent Difference"].apply(lambda x: None if x is None or pd.isna(x) else f"{x}%") # reformat percent difference column to show % sign
                comparison_display = comparison_display.rename(columns={"Percent Difference":f"vs {base_airline}"}) # rename percent difference column to make it more understandable
                comparison_display = comparison_display.drop(columns=["Metric"]) # drop metric column as it is redundant for a table concerning only a single metric
                # Column reformatting steps
                if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Operating Income", "Net Income", "Long-Term Debt", "Profit Sharing"]:
                    comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: None if x is None else f"{"-$" if x < 0 else "$"}{abs(x):,.0f}") # reformat currency columns to show $ sign
                elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                    comparison_display[metric_display] = comparison_display[metric_display].apply(lambda x: None if x is None else f"{x:,.2f}\u00A2") # reformat unit currency columns to show cents sign
                elif metric in ["Operating Margin", "Net Margin", "Load Factor"]:
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
                    comparison_display = comparison_display.drop(columns=pd.IndexSlice[base_airline, f"vs {base_airline}"], errors="ignore")
                    conditional_color_columns = [(col, f"vs {base_airline}") for col in comparison_display.columns.levels[0] if (col, f"vs {base_airline}") in comparison_display.columns] # specify the percent difference columns for which to apply conditional color formatting
                    comparison_display = comparison_display.style.map(color_positive_negative_zero, subset=conditional_color_columns) # map color of comparison column based on its sign and color of airline codes based on code ([.map_index(color_airlines, axis="columns", level="Airline")] streamlit doesn't directly support color text in an index)
                elif len(selected_airlines) > 1 and compare_yes_no=="No":
                    comparison_display = comparison_display.set_index(["Period", "Airline"])
                    comparison_display = comparison_display.drop(columns=f"vs {base_airline}") # do not display percent difference column if user chooses not to compare
                    comparison_display = comparison_display.unstack(level="Airline")
                    comparison_display.columns = comparison_display.columns.swaplevel(0, 1)
                    comparison_display = comparison_display.sort_index(axis=1, level=0)
                st.dataframe(comparison_display, width=1000) 
            if show_compare_col2:
                with compare_col2:
                    # Time series line plot (via plotly) for the metric's change over time if more than one time period (quarter or year) is selected.
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
                    if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Operating Income", "Net Income", "Long-Term Debt", "Profit Sharing"]:
                        fig_line.update_traces(
                            hovertemplate="%{x}<br>%{y:$,.0f}"
                        )
                    elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                        fig_line.update_traces(
                            hovertemplate="%{x}<br>%{y:.2f}\u00A2"
                        )
                    elif metric in ["Operating Margin", "Net Margin", "Load Factor"]:
                        fig_line.update_traces(
                            hovertemplate="%{x}<br>%{y:.2f}%"
                        )
                    else:
                        fig_line.update_traces(
                            hovertemplate="%{x}<br>%{y:,.0f}"
                        )
                    # Display plot
                    st.plotly_chart(fig_line)
            if show_compare_col3:
                with compare_col3:
                    # Bar plot (via plotly) for % difference if more than one airline is selected.
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
            if metric in ["Total Revenue (millions)", "Passenger Revenue (millions)", "Total Expenses (millions)", "Operating Income (millions)", "Net Income (millions)", "Long-Term Debt (millions)", "Profit Sharing (millions)"]:
                return None if value==None else None if pd.isna(value) else f"{"-$" if value < 0 else "$"}{abs(value):,.0f}" if value.is_integer() else f"{"-$" if value < 0 else "$"}{abs(value):,.2f}" # reformat currency columns to show $ sign
            elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
                return None if value==None else None if pd.isna(value) else f"{value:,.2f}\u00A2" # reformat unit currency columns to show cents sign
            elif metric in ["Operating Margin", "Net Margin", "Load Factor"]:
                return None if value==None else None if pd.isna(value) else f"{value:,.2f}%" # reformat percent columns to show % sign
            else:
                return None if value==None else None if pd.isna(value) else f"{value:,.0f}" # ensure any other metric is displayed as a unitless integer for readability
        comparison_summary["Value"] = comparison_summary.apply(lambda row: format_value_based_on_metric(row["Value"], row["Metric"]), axis=1)
        comparison_summary["Percent Difference"] = comparison_summary["Percent Difference"].apply(lambda x: None if x is None or pd.isna(x) else f"{x}%") # reformat percent difference column to show % sign
        comparison_summary = comparison_summary.set_index(["Metric", "Airline"], drop=True)
        comparison_summary = comparison_summary.rename(columns={"Percent Difference":f"vs {base_airline}"}) # rename percent difference column
        comparison_summary = comparison_summary.drop(columns=["Period"]) # drop period column as the summary only covers a single period
        comparison_summary = comparison_summary.rename(columns={"Value":f"{max(filtered_data["Period"])}"})
        ordered_metrics = [item + " (millions)" if i < len(available_metrics)-7 else item for i, item in enumerate(available_metrics)]
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
    # Reset the apply_filters state to False and rerun count to 0 until the Apply Filters button is clicked again
    if st.session_state.rerun_count == 2:
        st.session_state.apply_filters = False
        st.session_state.rerun_count = 0

#####################################################################################
#####################################################################################

## MOST RECENT YEAR AND QUARTER SUMMARY FOR ALL AIRLINES AND ALL METRICS ##
# Display a summary of the latest reporting periods' metrics
#####################################################################################
## SESSION STATE SETUP
# Initialize a session state that will control when this tab reruns.
if 'compare_change' not in st.session_state:
    st.session_state.compare_change = False
# Define functions to trigger reruns
def compare_yes_no_2_selection():
    st.session_state.compare_change = 2
def base_airline_2_selection():
    st.session_state.compare_change = 1
# Initialize a rerun count session state to trigger an extra rerun when applying filters to ensure filters apply properly and don't cause errors in the visualization.
if 'rerun_count2' not in st.session_state:
    st.session_state.rerun_count2 = 0
# Initialize a session state that contains the default selections and that will be updated with user selections for this tab
if "tab2" not in st.session_state:
    st.session_state.tab2 = {
        "compare_yes_no_2": "No",
        "base_airline_2": airlines[0]
        }
# Define function to update the tab session variables
def update_tab2():
    st.session_state.tab2["compare_yes_no_2"] = st.session_state.compare_yes_no_2
    st.session_state.tab2["base_airline_2"] = st.session_state.base_airline_2
#####################################################################################
with tab2:
    summary_col1, summary_col2, summary_col3 = st.columns([2, 2, 1])
#####################################################################################
    ## USER INTERACTION ##
    with summary_col3:
        # Allow user to select a base airline to compare others against
        with st.container(border=True):
            st.session_state.compare_yes_no_2 = st.pills("Would you like to compare against one of the airlines?", options_yes_no, default="No", on_change=compare_yes_no_2_selection)
            compare_yes_no_2 = st.session_state.tab2["compare_yes_no_2"]
            if compare_yes_no_2=="Yes":
                st.session_state.base_airline_2 = st.pills("Select Airline to Compare Against", airlines, default=airlines[0], key="base_tab2", on_change=base_airline_2_selection)
                base_airline_2 = st.session_state.tab2["base_airline_2"]
            else:
                base_airline_2 = airlines[0]
                st.session_state.base_airline_2 = None
        # Add a toggle to display metric definitions for users who need them
        with st.popover(icon=":material/dictionary:", label="Show definitions of the metrics.", use_container_width=True):
            for metric, definition in metric_definitions:
                st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
                st.write(f"{metric} - {definition}", unsafe_allow_html=True)
            st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
        if st.session_state.compare_change == 1:
            update_tab2()
            # Check if it's the first rerun, and trigger the first rerun
            if st.session_state.rerun_count2 == 0:
                st.session_state.rerun_count2 = 1
                st.rerun()
        elif st.session_state.compare_change == 2:
            update_tab2()
            # Check if it's the first rerun, and trigger the first rerun
            if st.session_state.rerun_count2 == 0:
                st.session_state.rerun_count2 = 1
                st.rerun()
            # After the first rerun, trigger the second rerun
            elif st.session_state.rerun_count2 == 1:
                st.session_state.rerun_count2 = 2
                st.rerun()
#####################################################################################
    ## FILTERING, CALCULATIONS, AND FUNCTIONS ##
    # Filter data for most recent year and quarter
    summary_data_fy = airline_financials_fy[airline_financials_fy["Period"]==max(airline_financials_fy["Period"].unique())]#.dropna(axis=1, how="all")
    summary_data_q = airline_financials_q[airline_financials_q["Period"]==max(airline_financials_q["Period"].unique())].dropna(axis=1, how="all")
    # Column reformatting steps
    def format_value_based_on_metric(value, metric):
        if metric in ["Total Revenue (millions)", "Passenger Revenue (millions)", "Total Expenses (millions)", "Operating Income (millions)", "Net Income (millions)", "Long-Term Debt (millions)", "Profit Sharing (millions)"]:
            return "TBA" if value==None else "TBA" if pd.isna(value) else f"{"-$" if value < 0 else "$"}{abs(value):,.0f}" # reformat currency columns to show $ sign
        elif metric in ["Yield", "TRASM", "PRASM", "CASM"]:
            return "TBA" if value==None else "TBA" if pd.isna(value) else f"{value:,.2f}\u00A2" # reformat unit currency columns to show cents sign
        elif metric in ["Operating Margin", "Net Margin", "Load Factor"]:
            return "TBA" if value==None else "TBA" if pd.isna(value) else f"{value:,.2f}%" # reformat percent columns to show % sign
        else:
            return "TBA" if value==None else "TBA" if pd.isna(value) else f"{value:,.0f}" # ensure any other metric is displayed as a unitless integer for readability
    # Define function to transform data for display
    def data_transform(data):
        ordered_metrics = [item + " (millions)" if i < len((data.columns).intersection(data.columns.drop(["Year", "Quarter", "Airline", "Period"])))-7 else item for i, item in enumerate((data.columns).intersection(data.columns.drop(["Year", "Quarter", "Airline", "Period"])))]
        data_transformed = []
        for metric in (data.columns).intersection(data.columns.drop(["Year", "Quarter", "Airline", "Period"])):
            # Adjust some of the metrics to scale better for display
            if metric in ["Total Revenue", "Passenger Revenue", "Total Expenses", "Operating Income", "Net Income", "Long-Term Debt", "Profit Sharing", "RPM", "ASM"]:
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
        data_transformed_df["Percent Difference"] = data_transformed_df["Percent Difference"].apply(lambda x: None if x is None or pd.isna(x) else f"{x}%") # reformat percent difference column to show % sign
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
    # Reset the apply_filters state to False and rerun count to 0 until the Apply Filters button is clicked again    
    if st.session_state.rerun_count2 == 1 and st.session_state.compare_change == 1:
        st.session_state.compare_change = False
        st.session_state.rerun_count2 = 0
    elif st.session_state.rerun_count2 == 2 and st.session_state.compare_change == 2:
        st.session_state.compare_change = False
        st.session_state.rerun_count2 = 0
#####################################################################################
#####################################################################################

## SHARE REPURCHASES ##
# Display share repurchase history of the Big 3 airlines (AAL, DAL, UAL)
#####################################################################################
## SESSION STATE SETUP
# Initialize session state to trigger stock price refresh. Initialize to true to ensure code runs when app is opened.
if 'refresh_stock_prices' not in st.session_state:
    st.session_state.refresh_stock_prices = True
# Initialize a session state that contains the default selections and that will be updated with user selections for this tab
if "tab3" not in st.session_state:
    st.session_state.tab3 = {
        "last_close": None,
        "ticker_since_covid": None
        }
#####################################################################################
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
        return "Error: Max attempts reached. Stock price could not be retrieved."
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
        return "Error: Max attempts reached. Stock price history could not be retrieved"
#####################################################################################
    ## OUTPUT/DISPLAY ##
    col1, col2 = st.columns([9, 1])
    with col1:
        st.header("2010s Big 3 Share Buyback Campaign", divider='gray')
        # Create display columns
        col3, col4 = st.columns([1, 2])
        # Information about the repurchase programs
        with col3:
            # Aggregate values
            total_shares_repurchase = share_repurchases.groupby("Airline")["Shares (millions)"].sum()
            total_cost_repurchase = share_repurchases.groupby("Airline")["Cost (millions)"].sum()
            total_average_share_cost = total_cost_repurchase/total_shares_repurchase
            total_shares_sale = share_sales.groupby("Airline")["Shares (millions)"].sum()
            total_proceeds_sale = share_sales.groupby("Airline")["Proceeds (millions)"].sum()
            total_average_share_sale = total_proceeds_sale/total_shares_sale
            # Define ticker symbols and fetch last close prices
            tickers = share_repurchases["Airline"].unique().tolist() # repurchase campaign airline tickers
            if st.session_state.refresh_stock_prices:
                st.session_state.last_close = fetch_last_close_prices(tickers, ticker_date)
                st.session_state.tab3["last_close"] = st.session_state.last_close
            last_close = st.session_state.tab3["last_close"]
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
                st.markdown(f"{airline} repurchased **{total_shares_repurchase[airline]:.1f} million** shares at a total cost of **\\${(total_cost_repurchase[airline]/1000):.1f} billion**. The average share price of repurchase was **\\${total_average_share_cost[airline]:.2f}**. "
                            f"To raise cash during the Covid-19 pandemic, {airline} offered and sold **{total_shares_sale[airline]:.1f} million** shares generating proceeds of **\\${(total_proceeds_sale[airline]/1000):.1f} billion**. The average share price of sale was **\\${total_average_share_sale[airline]:.2f}**. "
                            f"{airline} last closed at **{close_display}**.<br>"
                            f"Based on the current share price and sales made during the pandemic, the repurchase campaign netted {airline}:"
                            , unsafe_allow_html=True)
                # Display the gain/loss based on the average repurchase price and current share price
                # Set up the repurchase program gain variable to be able to handle error messages generated by the close price function
                if isinstance(close_value, str):
                    repurchase_net_value = close_value
                    repurchase_net_display = repurchase_net_value
                    st.warning(repurchase_net_display, icon="⚠️")
                else:
                    repurchase_net_value = (((total_average_share_sale[airline]-total_average_share_cost[airline])*(total_shares_sale[airline]))+((close_value-total_average_share_cost[airline])*(total_shares_repurchase[airline]-total_shares_sale[airline])))/1000
                    repurchase_net_color = "green" if round(repurchase_net_value, 1)>0 else "red" if round(repurchase_net_value, 1)<0 else "black"
                    repurchase_net_display = f"<p style='margin-bottom:0;'><h3 style='color:{repurchase_net_color};'>{f"{'-$' if round(repurchase_net_value, 1)<0 else '$'}{abs(repurchase_net_value):,.1f} billion {"&nbsp;"*10} {"🔥💰🔥" if round(repurchase_net_value, 1)<0 else "🤷" if round(repurchase_net_value, 1)==0 else "💸" if (repurchase_net_value/total_cost_repurchase[airline]/1000)<0.5 else "💸💸" if (repurchase_net_value/total_cost_repurchase[airline]/1000)<=1 else "💸💸💸"}"}</h3></p>"
                    st.markdown(repurchase_net_display, unsafe_allow_html=True)
        # Historical repurchase data for viewing
        with col4:
            # Prepare data to plot gain/loss from repurchases over time since Covid onset
            # Fetch daily closing price since start of 2020Q2
            if st.session_state.refresh_stock_prices:
                st.session_state.ticker_since_covid = fetch_daily_close(tickers, "2020-04-01", datetime.now())
                st.session_state.tab3["ticker_since_covid"] = st.session_state.ticker_since_covid
            ticker_since_covid = st.session_state.tab3["ticker_since_covid"]
            # Calculate the daily gain/loss in billions based on average repurchase price minus closing price multiplied by number of shares repurchased. Adjust shares outstanding to account for share sales in 2020 and 2021.
            gain = pd.DataFrame()
            for airline in share_repurchases["Airline"].unique():        
                if isinstance(ticker_since_covid, pd.DataFrame): # Ensure stock prices were successfully fetched
                    gain[airline] = pd.Series(
                        ( 
                            ((x - total_average_share_cost[airline]) * total_shares_repurchase[airline]) / 1000
                            if date <= pd.Timestamp('2020-12-31')
                            else ((((share_sales[(share_sales["Airline"]==airline) & (share_sales["Year"]==2020)]["Average Share Price"]-total_average_share_cost[airline])*(share_sales[(share_sales["Airline"]==airline) & (share_sales["Year"]==2020)]["Shares (millions)"]))+((x-total_average_share_cost[airline])*(total_shares_repurchase[airline]-share_sales[(share_sales["Airline"]==airline) & (share_sales["Year"]==2020)]["Shares (millions)"])))/1000).values[0]
                            if pd.Timestamp("2021-01-01") <= date <= pd.Timestamp("2021-12-31")
                            else (((total_average_share_sale[airline]-total_average_share_cost[airline])*(total_shares_sale[airline]))+((x-total_average_share_cost[airline])*(total_shares_repurchase[airline]-total_shares_sale[airline])))/1000
                        )
                        for date, x in zip(ticker_since_covid.index, ticker_since_covid[airline])
                    )
                else:
                    gain[airline] = pd.Series()  # Assign an empty series to avoid breaking code
                    st.warning(ticker_since_covid + f" for {airline}.", icon="⚠️") # Display error message
            if gain.empty:
                gain_melt = pd.DataFrame(columns=["Date", "Airline", "Gain"]) # Assign empty plotting dataframe to avoid breaking code
            else:
                gain.index = ticker_since_covid.index
                # Melt the DataFrame into a format usable for plotting
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
                hovertemplate="%{x}<br>%{y:$.1f} billion",
                hoverinfo="text"
            )
            st.plotly_chart(fig_line2)
            # Prepare repurchase data for display
            share_repurchase_display = share_repurchases.copy()
            share_repurchase_display = share_repurchase_display.drop(columns=["Year", "Quarter", "Shares Repurchased", "Cost"])
            share_repurchase_display["Shares (millions)"] = share_repurchase_display["Shares (millions)"].apply(lambda x: f"{x:,.1f}")
            share_repurchase_display["Cost (millions)"] = share_repurchase_display["Cost (millions)"].apply(lambda x: f"${x:,.0f}")
            share_repurchase_display["Average Share Price"] = share_repurchase_display["Average Share Price"].apply(lambda x: f"${x:,.2f}")
            share_repurchase_display = share_repurchase_display.set_index(["Period", "Airline"])
            share_repurchase_display = share_repurchase_display.unstack(level="Airline")
            share_repurchase_display.columns = share_repurchase_display.columns.swaplevel(0, 1)
            share_repurchase_display.columns = pd.MultiIndex.from_tuples(
                sorted(share_repurchase_display.columns, key=lambda x: ["Shares (millions)", "Cost (millions)", "Average Share Price"].index(x[1]))
            )
            share_repurchase_display = share_repurchase_display.sort_index(axis=1, level=0, sort_remaining=False)
            st.markdown("<h4>Share Repurchase History</h4>", unsafe_allow_html=True)
            st.dataframe(share_repurchase_display, width=1300)
            # Prepare sale data for display
            share_sales_display = share_sales.copy()
            share_sales_display = share_sales_display.drop(columns=["Year", "Quarter", "Shares Sold", "Proceeds"])
            share_sales_display["Shares (millions)"] = share_sales_display["Shares (millions)"].apply(lambda x: f"{x:,.1f}")
            share_sales_display["Proceeds (millions)"] = share_sales_display["Proceeds (millions)"].apply(lambda x: f"${x:,.0f}")
            share_sales_display["Average Share Price"] = share_sales_display["Average Share Price"].apply(lambda x: f"${x:,.2f}")
            share_sales_display = share_sales_display.set_index(["Period", "Airline"])
            share_sales_display = share_sales_display.unstack(level="Airline")
            share_sales_display.columns = share_sales_display.columns.swaplevel(0, 1)
            share_sales_display.columns = pd.MultiIndex.from_tuples(
                sorted(share_sales_display.columns, key=lambda x: ["Shares (millions)", "Proceeds (millions)", "Average Share Price"].index(x[1]))
            )
            share_sales_display = share_sales_display.sort_index(axis=1, level=0, sort_remaining=False)
            st.markdown("<h4>Share Sale History</h4>", unsafe_allow_html=True)
            st.dataframe(share_sales_display, width=1300)
        # Reset the refresh_stock_prices state to False until the Refresh Stock Prices button is clicked again
        st.session_state.refresh_stock_prices = False
    with col2:
        def refresh_stock_prices_button():
            st.session_state.refresh_stock_prices = True
        st.button("Refresh Stock Prices", type="primary", on_click=refresh_stock_prices_button)
#####################################################################################
#####################################################################################

## ChatGPT INSIGHTS ##
# Display top 10 insights from all financial filings for a selected airline in a selected year. Insights generated by an API call and prompt to ChatGPT-4o-mini.
#####################################################################################
## SESSION STATE SETUP ##
# Initialize a session state that will control when this tab reruns.
if 'get_insights' not in st.session_state:
    st.session_state.get_insights = False
# Initialize a session state that contains the default selections and that will be updated with user selections for this tab
if "tab4" not in st.session_state:
    st.session_state.tab4 = {
        "llm_airline": None,
        "llm_period": None,
        "llm_year": None
        }
# Define function to update the tab session variables
def update_tab4():
    st.session_state.tab4["llm_airline"] = st.session_state.llm_airline
    st.session_state.tab4["llm_period"] = st.session_state.llm_period
    st.session_state.tab4["llm_year"] = st.session_state.llm_year
#####################################################################################
with tab4:
#####################################################################################
## DEFINE FUNCTIONS ##
#####################################################################################
    # Set OpenAI API key
    #openai.api_key = os.getenv("openai_key") # OpenAI API key call when deployed via Azure, Google Cloud Run, or other hosted platform
    openai.api_key = st.secrets["API_Keys"]["openai_key"] # OpenAI API key call when deployed via Streamlit Community Cloud
#####################################################################################
    # Define function to prompt the ChatGPT API and return a summary from training data
    # Define the API call and prompt
    def get_sec_filings_summary(airline, year, period):
        prompt = f"""
        Analyze all SEC filings for {airline} from {year}{period}, including all 10-Q, 10-K, 8-K filings, annual reports, and other filings. 
        Provide the top insights for the year and period specified. Provide up to 10 insights. Insights should be related to key developments in the following areas: financial, operational, commercial stratgy, labor, executive personnel, and route network. Do NOT include a topic if there is no relevant data or if there is nothing meaningful to report.
        Do NOT under any circumstances fabricate names, dates, or numerical figures. Ensure the values are present in the underlying data. A fabrication is content not present in the SEC filings including but not limited to any mention of 'John Doe' or 'Jane Doe'.
        Be sure to highlight any major events and their impacts and provide additional context. 
        Format the response in a structured list format grouped by topic. Present insights in chronological order as best as possible. Length of each item should fully detail the insight while being easy to read and digest. Include relevant names when discussing personnel matters. Include accurate figures when discussing financial or other metrics.
        End the response with a single paragraph "Wrap Up".
        """
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert financial analyst summarizing SEC filings and presenting them for public consumption. Accuracy is paramount, but you should provide interesting and revelatory insights. Language and style should be a cross between an investment analyst report and business media reporting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.15
        )
        return response.choices[0].message.content
#####################################################################################
    # Define function to create start and end dates
    def define_period_dates(year, period):
        # Create date components based on selected year and period
        if period == "FY":
            start_month = 1
            end_month = 12
        else:
            end_month = int(period[-1]) * 3
            start_month = end_month - 2
        start_day = 1
        end_day = calendar.monthrange(year, end_month)[1]
        # Create start and end date variables to constrain document scraping
        start_date = datetime(year, start_month, start_day)
        if period=="FY":
            end_date = (datetime(year, end_month, end_day) + relativedelta(months=2)) # add two months to the end date to capture annual filings that are released up to two months after end of period
        else:
            end_date = (datetime(year, end_month, end_day) + relativedelta(months=1) + relativedelta(days=1)) # add one month to the end date to capture quarterly filings that are released up to a month after end of period
        
        #Print messages when testing function operation
        #print(f"Start Date: {start_date}\nEnd Date: {end_date}")
        
        return start_date, end_date
#####################################################################################
    # Define function to extract document links from a page and filter by date
    def extract_filing_links(url, doc_base_url, container, container_class, filing_group_class, start_date, end_date, reached_start_date):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
            
        # Find the table containing the document links and their filing dates
        table = soup.find(container, {"class": container_class})  # Identify table element on page where document entries and links are stored
        rows = table.find_all("tr") # Identify all rows, where each row is a document entry with a filing date and html link
        page_links = [] # Initiate the document container list
        skip_count = 0 # Initiate a counter for number of documents skipped during scraping
        retrieved_count = 0 # Initiate a counter for number of documents retrieved during scraping
        target_filings = {"8-K", "10-K", "10-Q"} # Limit documents to main reports to minimize the amount of text retrieved
        
        for row in rows:
            # Extract the date and link from each row
            time_element = row.find("time", class_="datetime")  # Find <time> element with the class "datetime"
            filing_group = row.find("td", class_ = filing_group_class) # Find the Filing Group column
            links = row.find_all("a", href=True) # Find the document link element
            
            if time_element and filing_group and links:
                # Extract the filing date from the "datetime" attribute of the document table
                filing_date_str = time_element["datetime"]  # Get the full date string (e.g., "2024-11-19T05:00:00Z")      
                try:
                    # Parse the filing date (from datetime attribute)
                    filing_date = datetime.strptime(filing_date_str, "%Y-%m-%dT%H:%M:%SZ")  # Parse full datetime
                except ValueError:
                    continue  # Skip if the date format is invalid

                # Extract Filing Group text from the filing_group attribute of the document table
                filing_group_div = filing_group.find("a") 
                filing_group_text = filing_group_div.get_text(strip=True) if filing_group_div else ""

                # Find the correct link in the row for the html version of the document (matching "/node/#####/html")
                filing_link = None
                doc_term = doc_base_url.rsplit("/", 1)[-1]
                for link in links:
                    if re.match(f"^/{doc_term}/", link["href"]):
                        filing_link = link["href"]
                        break  # Stop checking once we find the correct link         
                if filing_link:
                    full_filing_link = f"{doc_base_url.rsplit("/", 1)[0]}{filing_link}"  # Convert to absolute URL

                # If the filing date is within the range, retrieve the document link. If document is before start date, end scraping. Otherwise, skip document link and continue scraping.
                if start_date <= filing_date <= end_date and filing_group_text in target_filings:
                    reached_start_date=False
                    retrieved_count += 1 # increment count when a document is retrieved
                    page_links.append(full_filing_link) # add link to list
                elif start_date <= filing_date <= end_date and filing_group_text not in target_filings:
                    reached_start_date=False
                    skip_count +=1 # increment count when a document is skipped
                elif filing_date < start_date:
                    reached_start_date=True
                    break # End loop once beyond oldest document
                else:
                    reached_start_date=False
                    skip_count +=1 # increment count when a document is skipped
        
        return page_links, reached_start_date
#####################################################################################
    # Define function to extract and scrape pages with date filtering
    def scrape_filing_pages(airline, year, period, sec_filings_url, doc_base_url, container, container_class, filing_group_class):
        if airline not in ["AAL", "UAL"]:
            st.write(f"Cannot scrape filings for {airline}.")
            return
        
        else:
            # Set up pass through variables
            current_url = sec_filings_url[airline]
            doc_base_url = doc_base_url[airline]
            container = container[airline]
            container_class = container_class[airline]
            filing_group_class = filing_group_class[airline]
            all_links = []
            
            # Define start and end dates
            start_date, end_date = define_period_dates(year, period)
            
            # Initialize reached_start_date
            reached_start_date=False
            
            while current_url:
                
                # Print messages when testing function operation
                status_text = st.empty()
                status_text.write(f"Scraping page: {current_url}")
                
                # Extract links from the current page with date filtering
                page_links, reached_start_date = extract_filing_links(current_url, doc_base_url, container, container_class, filing_group_class, start_date, end_date, reached_start_date)
                all_links.extend(page_links)
                
                # Find the "Next" button to continue paging
                response = requests.get(current_url)
                soup = BeautifulSoup(response.text, "html.parser")
                next_button = soup.find("a", href=True, rel="next")
                if next_button:
                    # Construct the next page URL
                    next_page = next_button['href']
                    current_url = f"{sec_filings_url[airline]}{next_page}"  # Complete the URL
                else:
                    # No "Next" button, stop paging
                    st.write("No next page found, ending scrape.")
                    current_url = None
                
                # Break loop once start date is reached
                if reached_start_date==True:
                    break
                status_text.empty()
            status_text.empty()        

            # Display links to filings retrieved
            with st.popover(f"\nRetrieved {len(all_links)} filing documents for the time period:"):
                for link in all_links:
                    st.write(link)
            
            return all_links
#####################################################################################
    # Define a function to count to characters across all documents in the filings
    def character_count(filings):
        total_characters = 0
        for filing in filings:
            for document in filing:
                for section in document:
                    total_characters += len(section)
        return total_characters
#####################################################################################
    # Define a function to load documents, generate embeddings, and store for retrieval

    # Suppress debug or info level logs from ChromaDB
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    # Load PDFs and Extract Metadata
    def process_filings(pdfs):
        # Set up ChromaDB elements with a temporary directory
        
        # Check if a temp directory already exists in the session, if not create on
        if "chroma_temp_dir" not in st.session_state:
            st.session_state.chroma_temp_dir = tempfile.TemporaryDirectory()
        temp_dir = st.session_state.chroma_temp_dir.name  # Get temp dir path
        
        # Set up ChromaDB client in the temp directory
        client = chromadb.PersistentClient(path=temp_dir)  # Persistent ChromaDB (Disk)
        client.heartbeat() # checks that the ChromaDB client is active and responsive
        collection = client.get_or_create_collection(name="SEC_Filings") # create Chroma collection
        
        # Clear existing data if exists before adding new documents
        existing_ids = collection.get()["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids) 
        
        #Load the PDF documents
        time_warning = st.empty() # initiate warning message that will be displayed during processing
        time_warning.warning("This process may take several minutes, please wait...", icon="⚠️")
        load_status = st.empty() # initiate status message that will be displayed during processing
        pdf_counter = 0 # initialize the document counter
        for pdf in pdfs:
            loader = PyPDFLoader(pdf)
            documents = loader.load()
        
            # Extract document text and metadata
            for doc in documents:
                load_status.write(f"Processing {doc.metadata.get('title', '')}-page-{doc.metadata.get('page_label', 'Unknown')} from filing {pdf_counter+1} of {len(pdfs)}.")
                text = doc.page_content
                metadata = doc.metadata
                # Store in the ChromaDB with embeddings
                collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[f"{doc.metadata.get('title', f'Filing {pdf_counter+1} of {len(pdfs)}')}-page-{doc.metadata.get('page_label', 'Unknown')}"]
                )
            pdf_counter += 1 # increment the document counter
        
        time_warning.empty() # clear warning message upon completion
        load_status.empty() # clear status message upon completion
        
        return collection, client
#####################################################################################
    # Define a function to convert the ChromaDB document embedding collection into a vecorstore that can be used for retrieval
    from langchain.vectorstores import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings

    def get_retriever(collection, client, k):
        # Use all-MiniLM-L6-v2 as the embedding model since that is the default embedding for ChromaDB and was used to create the collection embeddings
        embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        # Wrap previously created ChromaDB in a retriever
        vectorstore = Chroma(
            client=client,  # Use existing ChromaDB client
            collection_name=collection.name,  # Reference stored collection
            embedding_function=embedding_function  # Use previously defined embedding function
        )
        return vectorstore.as_retriever(search_kwargs={"k": k})  # Retrieve top 5% results
#####################################################################################
    # Define a function to retrieve relevant documents related to the objective of summarizing the period financial results
    def retrieve_relevant_filings(query, collection, client):
        k=int(0.05*collection.count()) # choose the most relevant 5% of documents present within the retrieved filings
        retriever = get_retriever(collection, client, k)
        # Retrieve relevant SEC filings based on a natural language query.
        docs = retriever.get_relevant_documents(query)
        return [doc.page_content for doc in docs]
#####################################################################################
    # Define function to use the OpenAI API to generate insights based on the most relevant portions of the retrieved filings
    openai.api_key = st.secrets["API_Keys"]["openai_key"]
    def summarize_sec_filings(airline, year, period, collection, client):
        # Using the retrieved relevant portions of the period's SEC filings, summarize key results using OpenAI GPT.
        # Define overall query to guide relevant document retrieval and summarization
        query = f"{airline} {year}{period} financial and operational highlights."
        # Retrieve relevant documents
        relevant_docs = retrieve_relevant_filings(query, collection, client)
        # Combine into a single string
        context = "\n\n".join(relevant_docs)
        context = context  # add truncation if needed to limit tokens passed to the API

        # Define the summarization prompt
        prompt = f"""
        You are an expert financial analyst summarizing SEC filings for {airline} from {year}{period}.
        Below are relevant filings for the query: {query}

        {context}

        Analyze all SEC filings , including all 10-Q, 10-K, 8-K filings, annual reports, and other filings. 
        Provide the top insights for the year and period specified. Focus on the data from {year}{period} and ignore discussion of previous periods unless it provides meaningful context for current results. Provide up to 10 insights. Insights should be related to key developments in the following areas: financial, operational, commercial stratgy, labor, executive personnel, and route network. Do NOT include a topic if there is no relevant data or if there is nothing meaningful to report.
        Do NOT under any circumstances fabricate names, dates, or numerical figures. Ensure the values are present in the underlying data. A fabrication is content not present in the SEC filings including but not limited to any mention of 'John Doe' or 'Jane Doe'.
        Be sure to highlight any major events and their impacts and provide additional context. 
        Format the response in a structured list format grouped by topic. Present insights in chronological order as best as possible. Length of each item should fully detail the insight while being easy to read and digest. Include relevant names when discussing personnel matters. Include accurate figures when discussing financial or other metrics.
        End the response with a single paragraph "Wrap Up".
        """

        # Send request to OpenAI GPT
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert financial analyst summarizing SEC filings and presenting them for public consumption. Accuracy is paramount, but you should provide interesting and revelatory insights. Language and style should be a cross between an investment analyst report and business media reporting."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        return response.choices[0].message.content
#####################################################################################
    # Define source URLs aand html elements for locating the SEC filings
    sec_filings_url = {"AAL": "https://americanairlines.gcs-web.com/sec-filings", "DAL": "https://ir.delta.com/financials/default.aspx#sec", "UAL": "https://ir.united.com/financial-performance/sec-filings"}
    html_doc_base_url = {"AAL": "https://americanairlines.gcs-web.com/node", "DAL": "https://d18rn0p25nwr6d.cloudfront.net/CIK-0000027904", "UAL": "https://ir.united.com/node"}
    pdf_doc_base_url = {"AAL": "https://americanairlines.gcs-web.com/static-files", "DAL": None, "UAL": "https://ir.united.com/static-files"}
    container = {"AAL": "table", "DAL": "div", "UAL": "table"}
    container_class = {"AAL": "nirtable", "DAL": "module-container", "UAL": "nirtable"}
    filing_group_class = {"AAL": "views-field views-field-field-nir-sec-form", "DAL": None, "UAL": "views-field views-field-field-nir-sec-form"}
#####################################################################################
    ## USER INPUTS ##
    with st.expander("Select an airline, period, and year to see the top insights.", expanded=True):
        st.warning("This is a proof of concept feature. Content is generated by ChatGPT and accuracy cannot be guaranteed.", icon="⚠️")
        st.info("Insights for DAL (Delta Air Lines) and LUV (Southwest Airlines) are limited to 2023Q3 or earlier due to ChatGPT's training data cutoff date of October 2023. There is no limitation for AAL (American Airlines) or UAL (United Airlines) as this feature sources from the SEC filings directly.", icon="ℹ️")
        llm_col1, llm_col2, llm_col3 = st.columns([1, 1, 2])
        with llm_col1:
            # Select airline
            st.session_state.llm_airline = st.pills("Select Airline", airlines, default=None, selection_mode="single")
        with llm_col2:
            # Select period(s)
            llm_quarters = sorted(airline_financials["Quarter"].unique())
            st.session_state.llm_period = st.pills("Select Period", llm_quarters, default=None, selection_mode="single")
        with llm_col3:
            # Select year
            st.session_state.llm_year = st.pills("Select Year", years, default=None, selection_mode="single")
        # Set up a Get Insights button to prevent processing of documents unless button is clicked.
        def get_insights_button():
            st.session_state.get_insights = True
        st.button("Get Insights", type="primary", on_click=get_insights_button)
#####################################################################################
    ## OUTPUT/DISPLAY ##
    # Check if Get Insights button was clicked
    if st.session_state.get_insights:
        
        # Update the filter session states and set the variables
        update_tab4()
        llm_airline = st.session_state.tab4["llm_airline"]
        llm_period = st.session_state.tab4["llm_period"]
        llm_year = st.session_state.tab4["llm_year"]
        
        # If any filter selections were not made, prompt the user to complete the selections
        if llm_airline==None or llm_period==None or llm_year==None:
            st.write("Please make selections above to generate insights.")
        
        # Document retrieval and summarization currently only works for AAL and UAL. If other airlines are selected revert to a general query to the ChatGPT API for responses from training data
        elif llm_airline not in ["AAL", "UAL"]:
            st.header(f"Airline: {llm_airline} | Period: {llm_year}{llm_period}", divider='gray')
            # Generate the summary by passing the call to ChatGPT
            if llm_year>2023 or (llm_period=="Q4" and llm_year==2023):
                st.error(f"""
                Cannot provide summary for {llm_year}{llm_period}. ChatGPT's training data cuts off in October 2023.\n
                Please make a different selection.
                """, icon="🛑")
            else:
                st.warning("This summary is generated by ChatGPT from its training data. Accuracy cannot be guaranteed.", icon="⚠️")
                with st.spinner(f"Retrieving {llm_year}{llm_period} insights about {llm_airline}...", show_time=True):
                    summary = get_sec_filings_summary(llm_airline, llm_year, llm_period)
                # Display response from ChatGPT
                st.write(summary.replace("$", "\\$"))
        
        # Execute retrieval and summarization of SEC filings for more accurate and relevant insights
        else:
            st.header(f"Airline: {llm_airline} | Period: {llm_year}{llm_period}", divider='gray')
            st.info("Insights are sourced from the SEC filings directly.", icon="ℹ️")
            with st.status(f"Fetching {llm_year}{llm_period} SEC filings for {llm_airline}...", expanded=True) as status:
                # Retrieve links to the pdf documents of the relevant filings
                filing_links = scrape_filing_pages(llm_airline, llm_year, llm_period, sec_filings_url, pdf_doc_base_url, container, container_class, filing_group_class)
                # Load and embed documents from filing links
                status.update(label=f"Found {len(filing_links)} document links. Processing the documents...") # display status update
                with st.spinner(text="Loading documents...", show_time=True):
                    start_processing_time = time.time()
                    filing_collection, client = process_filings(filing_links)
                    elapsed_processing_time = time.time() - start_processing_time
                if isinstance(filing_collection, Collection):
                    # Count tokens retrieved
                    status.update(label=f"{filing_collection.count()} documents processed and stored. Counting the characters...") # display status update
                    collection_character_count = character_count(filing_collection.get(include=["documents"])["documents"])
                else:
                    status.update(label=f"An error occurred: {filing_collection}", state="error") # display error message
                status.update(label="Generating insights")
                st.success(f"Processed {len(filing_links)} filings with {collection_character_count:,} characters. Processing documents took {int(elapsed_processing_time//60)} {'minute' if 1<=int(elapsed_processing_time//60)<2 else 'minutes'} {elapsed_processing_time%60:.1f} seconds.") # display success message upon processing filings and counting characters
                with st.spinner(text="Generating insights...", show_time=True):
                    start_summary_time = time.time()
                    summary = summarize_sec_filings(llm_airline, llm_year, llm_period, filing_collection, client)
                    elapsed_summary_time = time.time() - start_summary_time
                st.success(f"Summarization complete in {int(elapsed_summary_time//60)} {'minute' if 1<=int(elapsed_summary_time//60)<2 else 'minutes'} {elapsed_summary_time%60:.1f} seconds.") # display success message upon processing filings and counting tokens                
                status.update(label=f"Processing complete for {llm_airline} {llm_year}{llm_period} filings.", state="complete", expanded=False) # display completion message and collapse status container
            # Display summary insights
            st.write(summary.replace("$", "\\$"))
        
        # Reset session state
        st.session_state.get_insights = False
#####################################################################################