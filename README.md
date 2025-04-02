# Airline Financial Dashboard
Compare financial metrics for US airlines.<br>
Explore the dashboard at: [https://www.airlinefinancialdashboard.com/](https://www.airlinefinancialdashboard.com/)

## Overview
This dashboard enables quick and intuitive comparisons of the financial performance of major US commercial airlines. Data is provided from 2014. This starting point was chosen because it was the first year after all of the major airlines had completed mergers, marking the completion of a cycle of consolidation and the start of the present industry landscape.<br>
The airlines covered (and their stock tickers) are American Airlines (AAL), Delta Air Lines (DAL), United Airlines (UAL), and Southwest Airlines (LUV). LUV quarterly data is provided from 2024.<br>
Unless otherwise noted, all metrics are either sourced or calculated from data given in the 10-Q (quarterly filing), 8-K (current report), and 10-K (annual filing) forms reported to the SEC and available on the airlines' investor relations sites.<br>
The dashboard is deployed using [Streamlit](https://streamlit.io/) and is hosted with [Google Cloud Run](https://cloud.google.com/run).

## Filtered Comparisons
The Filtered Comparisons tab provides customizable views of airline financials. Several metrics can be selected for evaluation over chosen reporting periods.<br>
<br>
Metrics covered:
- **Total Revenue:** Total amount earned from operations. Also called Operating Revenue.
- **Passenger Revenue:** Revenue primarily composed of passenger ticket sales, loyalty travel awards, and travel-related services performed in conjunction with a passenger's flight.
- **Total Expenses:** Total amount of costs incurred from operations. Also called Operating Expenses.
- **Operating Income:** Income from operations. Total Revenue minus Total Expenses.
- **Net Income:** Profit.
- **Revenue Passenger Mile (RPM):** A basic measure of sales volume. One RPM represents one passenger flown one mile.
- **Available Seat Mile (ASM):** A basic measure of production. One ASM represents one seat flown one mile.
- **Long-Term Debt:** Total long-term debt net of current maturities.<br>
    NOTE: This metric is reported annually and is therefore shown only for full year data and sourced from 10-K filings.
- **Profit Sharing:** Amount of income set aside to fund employee profit sharing programs.<br>
    NOTE: Quarterly reporting by AAL and UAL of this metric is inconsistent. Data provided may have been obtained from internal sources or estimated by proportioning the annual profit sharing reported by the quarterly operating income reported.
- **Operating Margin:** Operating Income divided by Total Revenue
- **Net Margin:** Percentage of profit earned for each dollar in revenue. Net Income divided by Total Revenue.
- **Load Factor:** The percentage of available seats that are filled with revenue passengers. RPMs divided by ASMs.
- **Yield:** A measure of airline revenue derived by dividing Passenger Revenue by RPMs.
- **Total Revenue per Available Seat Mile (TRASM):** Total Revenue divided by ASMs.
- **Passenger Revenue per Available Seat Mile (PRASM):** Passenger Revenue divided by ASMs.
- **Cost per Available Seat Mile (CASM):** Total Expenses divided by ASMs.
<br><br>

These metrics are manually identified and recorded on a quaterly basis from the 10-Q form for Q1-Q3, from the 8-K form for Q4, and from the 10-K form for FY and stored in [a xlsx file](https://github.com/mtricanowicz/airline_financials/blob/main/airline_financial_data.xlsx "airline_financial_data.xlsx") within this repo. This xslx file is used as the basis of all calculations, tables, and visualizations in the Filtered Comparison and Latest Results tabs.<br>
Throughout this app, data manipulation and visualization is accomplished primarily through the use of the [pandas](https://pandas.pydata.org/) and [plotly](https://plotly.com/python/) libraries.

## Latest Results
The Latest Results tab gives a summary of the most recent annual and quarterly results for easy viewing. The summaries show all airlines and all metrics, but give the user the option of displaying comparisons against one airline.<br>

## Share Repurchases
The Share Repurchases tab contains a high level overview of the share buyback programs by the Big 3 airilnes (AAL, DAL, UAL) that were carried out in the 2010s and ended with the onset of the Covid-19 pandemic.<br>
Stock price data is retrieved using the [yfinance](https://pypi.org/project/yfinance/) Python library which uses the Yahoo Finance API to fetch the requested ticker information.<br>
Share repurchase data during the repurchase program is manually identified and recorded from the 10-Q, 8-K, and 10-K forms. Share sales occurred during the Covid-19 crisis and sale data is manually identified and recorded primarily from 8-K filings, but also from 10-Q forms. This data is also stored in the [same xlsx file](https://github.com/mtricanowicz/airline_financials/blob/main/airline_financial_data.xlsx "airline_financial_data.xlsx") as the primary metrics.<br>
The net gain/loss of the repurchases is calculated by determining how many repurchases shares are still held. The difference between the repurchase price of these shares and the current share price gives a running unrealized gain/loss added to the realized gain/loss from the total amount spent to repurchase less the total amount raised from sales of the number of shares sold.

## Insights
The Insights tab delivers financial, operational, and commercial insights based on the airilne's SEC filings. User selections prompt retrieval of content for a particular airline and time period with summarization provided by ChatGPT.<br>
For American Airlines (AAL) and United Airlines (UAL), this dashboard uses a function to scrape the airline investor relations sites for the relevant 10-Q, 8-K, and 10-K documents contained within selected period by using html functions of [Beautiful Soup](https://beautiful-soup-4.readthedocs.io/en/latest/). These documents are then extracted as pdfs using [langchain's PDF Loader](https://python.langchain.com/docs/integrations/document_loaders/pypdfloader/ "PyPDFLoader"). These pdf files are then parsed to have embeddings created and stored within a [ChromaDB](https://docs.trychroma.com/docs/overview) collection. The collection of embeddings is converted to a vectorstore using [langchain](https://python.langchain.com/docs/concepts/vectorstores/ "Vector stores") to enable a retrieval augmented generation (RAG) funciton to extract a subset of the most relevant documents usnig [langchain](https://python.langchain.com/api_reference/core/retrievers/langchain_core.retrievers.BaseRetriever.html#langchain_core.retrievers.BaseRetriever, "BaseRetriever") to pass to ChatGPT for summarization. Finally, the [Open AI API](https://openai.com/api/) is used to pass the extracted text with a prompt to ChatGPT to generate relevant and meaningful insights related the airline's financial, operational, and commercial performance.<br>
At this time, scraping the SEC filings directly from the investor relations sites is still a work in progress for Delta Air Lines (DAL) and Southwest Airlines (LUV). For this reason, the Insights feature simply passes a prompt to ChatGPT via the OpenAI API to generate a summary from ChatGPT's training data. Because the training data cuts off in October 2023, insights for these airlines can only be generated through 2023Q3. Additionally, the content generated is significantly less accurate and more prone to hallucinations. Use extra caution if using any of the insights obtained. 

## Sources
[AAL](https://americanairlines.gcs-web.com/ "AAL IR") | [DAL](https://ir.delta.com/ "DAL IR") | [UAL](https://ir.united.com/ "UAL IR") | [LUV](https://www.southwestairlinesinvestorrelations.com/ "LUV IR")<br>
<br>


**Created by:**<br>
Michael Tricanowicz

