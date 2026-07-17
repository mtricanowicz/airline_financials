import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import openai
import os
import requests
from bs4 import BeautifulSoup
import calendar
from dateutil.relativedelta import relativedelta
import re

st.set_page_config(
    page_title="LLM Summarization Testing",  # Custom title in the browser tab
    page_icon=":airplane:",  # Custom icon for the browser tab
    layout="wide",  # Set the defaul layout for the app
    initial_sidebar_state="auto",  # Sidebar state when app loads
)

#####################################################################################
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
#####################################################################################
## DEFINE FUNCTIONS ##
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
        end_date = (datetime(year, end_month, end_day) + relativedelta(months=1)) # add one month to the end date to capture quarterly filings that are released up to a month after end of period
    
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
    
    # Print messages when testing function operation            
    #if skip_count>0:
    #    print(f"Skipped {skip_count} documents on the page more recent than selected time period.")
    #if retrieved_count>0:
    #    print(f"Retrieved {retrieved_count} documents on the page for the selected time period.")
    #if reached_start_date==True:
    #    print("Oldest filing in period reached. Scraping complete.")
    
    return page_links, reached_start_date
#####################################################################################
# Define function to extract and scrape pages with date filtering
def scrape_filing_pages(airline, year, period, sec_filings_url, doc_base_url, container, container_class, filing_group_class):
    if airline not in ["AAL", "UAL"]:
        print(f"Cannot scrape filings for {airline}.")
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

        # Print messages when testing function operation
        with st.popover(f"\nRetrieved {len(all_links)} filing documents for the time period:"):
            for link in all_links:
                st.write(link)
        
        return all_links
#####################################################################################
# Define a function to count to tokens by document
def token_count(corpus):
    sum_tokens = 0
    for i in range(len(corpus)):
        sum_tokens = sum_tokens + token_counter(corpus[i])
    return sum_tokens
#####################################################################################
# Define a function to load documents, generate embeddings, and store for retrieval
import chromadb
from chromadb.api.models.Collection import Collection
from langchain_community.document_loaders import PyPDFLoader
import logging
import tempfile
# Suppress debug or info level logs from ChromaDB
logging.getLogger("chromadb").setLevel(logging.WARNING)

# Load PDFs and Extract Metadata
@st.cache_data
def process_filings(pdfs):
    # Set up ChromaDB elements with a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        #client = chromadb.EphemeralClient()  # Ephemeral ChromaDB (RAM)
        client = chromadb.PersistentClient(path="embeddings")  # Persistent ChromaDB (Disk)
        client.heartbeat() # checks that the ChromaDB client is active and responsive
        collection = client.get_or_create_collection(name="SEC_Filings") # create Chroma collection
        # 🚨 **Clear existing data if exists before adding new documents**
        existing_ids = collection.get()["ids"]
        if existing_ids:
            collection.delete(ids=existing_ids) 
    with st.spinner(text="Loading documents...", show_time=True):

        #Load the PDF documents
        #load_status = st.empty() # initiate status message while loading
        for pdf in pdfs:
            #load_status.write(f"Processing {pdf}...") # updated status message
            loader = PyPDFLoader(pdf)
            documents = loader.load()
            # Extract document text and metadata
            for doc in documents:
                #load_status.write(f"Processing {doc.metadata['title']}-page-{doc.metadata['page_label']} from {pdf}")
                text = doc.page_content
                metadata = doc.metadata
                # Store in ChromaDB with embeddings
                
                collection.add(
                    documents=[text],
                    metadatas=[metadata],
                    ids=[f"{doc.metadata['title']}-page-{doc.metadata['page_label']}"]
                )

        #load_status.empty() # clear status message
        return collection

#####################################################################################

#####################################################################################
# Define base URLs for the SEC filings
sec_filings_url = {"AAL": "https://americanairlines.gcs-web.com/sec-filings", "DAL": "https://ir.delta.com/financials/default.aspx#sec", "UAL": "https://ir.united.com/financial-performance/sec-filings"}
html_doc_base_url = {"AAL": "https://americanairlines.gcs-web.com/node", "DAL": "https://d18rn0p25nwr6d.cloudfront.net/CIK-0000027904", "UAL": "https://ir.united.com/node"}
pdf_doc_base_url = {"AAL": "https://americanairlines.gcs-web.com/static-files", "DAL": None, "UAL": "https://ir.united.com/static-files"}
container = {"AAL": "table", "DAL": "div", "UAL": "table"}
container_class = {"AAL": "nirtable", "DAL": "module-container", "UAL": "nirtable"}
filing_group_class = {"AAL": "views-field views-field-field-nir-sec-form", "DAL": None, "UAL": "views-field views-field-field-nir-sec-form"}
#####################################################################################



#####################################################################################
#####################################################################################
tab1, tab2 = st.tabs(["LLM", "Tab 2"])
with tab1:
#####################################################################################
    ## USER INPUTS ##
    with st.expander("Select an airline, period, and year to see the top insights.", expanded=True):
        st.warning("This is a proof of concept feature. Content is generated by ChatGPT and accuracy cannot be guaranteed.", icon="⚠️")
        llm_col1, llm_col2, llm_col3 = st.columns([1, 1, 2])
        with llm_col1:
            # Select airline
            llm_airline = st.pills("Select Airline", airline_financials["Airline"].unique(), default=None, selection_mode="single")
        with llm_col2:
            # Select period(s)
            llm_quarters = sorted(airline_financials["Quarter"].unique())
            llm_period = st.pills("Select Period", llm_quarters, default=None, selection_mode="single")
        with llm_col3:
            # Select year
            llm_year = st.pills("Select Year", sorted(airline_financials["Year"].unique()), default=None, selection_mode="single")
        # Set up a Run button to prevent processing of documents unless button is clicked.
        if 'clicked' not in st.session_state:
            st.session_state.clicked = False
        def click_button():
            st.session_state.clicked = True
        st.button("Run", on_click=click_button)
#####################################################################################
    ## OUTPUT/DISPLAY ##
    # Check if Run button was clicked
    if st.session_state.clicked:
        if llm_airline==None or llm_period==None or llm_year==None:
            st.write("Please make selections above to generate insights.")
        elif llm_airline not in ["AAL", "UAL"]:
            st.write(f"Cannot scrape filings for {airline}.")
        else:
            st.write(f"Airline: {llm_airline} | Period: {llm_period}{llm_year}")
        
            #with st.spinner(text=f"Fetching {llm_period}{llm_year} SEC filings for {llm_airline}...", show_time=True):
            with st.status(f"Fetching {llm_year}{llm_period} SEC filings for {llm_airline}...", expanded=True) as status:
                # Retrieve links to the pdf documents of the relevant filings
                filing_links = scrape_filing_pages(llm_airline, llm_year, llm_period, sec_filings_url, pdf_doc_base_url, container, container_class, filing_group_class)
                #status_text = st.empty()
                # Load and embed documents from filing links
                #status_text.write(f"Found {len(filing_links)} document links. Processing the documents...")
                status.update(label=f"Found {len(filing_links)} document links. Processing the documents...")
                filing_collection = process_filings(filing_links)
                if isinstance(filing_collection, Collection):
                    # Count tokens retrieved
                    #status_text.write(f"{filing_collection.count()} documents processed and stored. Counting the tokens...")
                    status.update(label=f"{filing_collection.count()} documents processed and stored. Counting the tokens...")
                    token_count = token_count(filing_collection.get(include=["documents"])["documents"])
                    #status_text.empty()
                else:
                    #status_text.write(f"An error occurred: {filing_collection}")
                    status.update(label=f"An error occurred: {filing_collection}")
            st.success(f"Retrieved {len(filing_links)+1} filings with {token_count:,} tokens.")
#####################################################################################