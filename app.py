import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Louisiana Economic Data Explorer", layout="wide")
st.title("📈 Louisiana State & MSA Economic Explorer (BLS)")
st.write("Compare Nonfarm Employment, Earnings, and Hours across Louisiana MSAs, Supersectors, and Detailed Industries.")

BLS_API_KEY = st.secrets.get("BLS_API_KEY", "")

# -----------------------------------------------------------------------------
# REFERENCE MAPPINGS (BLS State & Area Employment - SAE)
# -----------------------------------------------------------------------------

LA_AREAS = {
    "Louisiana (Statewide)": "00000",
    "Alexandria MSA": "10780",
    "Baton Rouge MSA": "12900",
    "Hammond MSA": "25220",
    "Houma-Thibodaux MSA": "26380",
    "Lafayette MSA": "29180",
    "Lake Charles MSA": "29340",
    "Monroe MSA": "33740",
    "New Orleans-Metairie MSA": "35380",
    "Shreveport-Bossier City MSA": "38200"
}

SAE_DATA_TYPES = {
    "All Employees (Thousands)": "01",
    "Average Hourly Earnings ($)": "03",
    "Average Weekly Hours": "07",
    "Average Weekly Earnings ($)": "11"
}

# Major Supersectors & Key Industries
SAE_INDUSTRIES = {
    "Total Nonfarm": "00000000",
    "Total Private": "05000000",
    "Goods Producing": "06000000",
    "Service-Providing": "07000000",
    "Mining, Logging, and Construction": "15000000",
    "Construction": "20000000",
    "Manufacturing": "30000000",
    "Durable Goods": "31000000",
    "Nondurable Goods": "32000000",
    "Trade, Transportation, and Utilities": "40000000",
    "Wholesale Trade": "41000000",
    "Retail Trade": "42000000",
    "Transportation, Warehousing, and Utilities": "43000000",
    "Information": "50000000",
    "Financial Activities": "55000000",
    "Professional and Business Services": "60000000",
    "Education and Health Services": "65000000",
    "Health Care and Social Assistance": "62000000",
    "Leisure and Hospitality": "70000000",
    "Accommodation and Food Services": "72000000",
    "Other Services": "80000000",
    "Government": "90000000",
    "Federal Government": "90910000",
    "State Government": "90920000",
    "Local Government": "90930000"
}

# Inverse lookups for decoding API responses
AREA_LOOKUP = {v: k for k, v in LA_AREAS.items()}
INDUSTRY_LOOKUP = {v: k for k, v in SAE_INDUSTRIES.items()}
DATATYPE_LOOKUP = {v: k for k, v in SAE_DATA_TYPES.items()}

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS FOR BATCH API CALLS
# -----------------------------------------------------------------------------

def chunk_list(lst, n):
    """Yield successive n-sized chunks from lst (BLS API accepts up to 50 series per call)."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def fetch_bls_batch(series_dict, start_year, end_year, api_key):
    """
    Fetches data for multiple series IDs simultaneously.
    series_dict maps series_id -> dict of metadata (Area, Industry, DataType)
    """
    series_ids = list(series_dict.keys())
    all_records = []
    
    # Split into chunks of 50 series IDs max
    for series_chunk in chunk_list(series_ids, 50):
        url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
        payload = {
            "seriesid": series_chunk,
            "startyear": str(start_year),
            "endyear": str(end_year),
            "registrationkey": api_key
        }
        
        response = requests.post(url, json=payload)
        res_data = response.json()
        
        if res_data.get("status") == "REQUEST_SUCCEEDED":
            for series_item in res_data.get("Results", {}).get("series", []):
                s_id = series_item.get("seriesID")
                meta = series_dict.get(s_id, {})
                for record in series_item.get("data", []):
                    record_copy = record.copy()
                    record_copy.update(meta)
                    all_records.append(record_copy)
        else:
            st.error(f"API Batch Error: {res_data.get('message')}")
            
    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df = df[df['period'].str.startswith('M') & (df['period'] != 'M13')].copy()
    df['Value'] = pd.to_numeric(df['value'], errors='coerce')
    df['Date'] = pd.to_datetime(df['year'] + '-' + df['period'].str.replace('M', ''), format='%Y-%m')
    df['MonthName'] = df['Date'].dt.strftime('%B %Y')
    return df.sort_values('Date').reset_index(drop=True)

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS
# -----------------------------------------------------------------------------

st.sidebar.header("Navigation & Settings")
view_mode = st.sidebar.radio(
    "Choose View Mode:",
    ["Regional Comparison Matrix (Single Month)", "Multi-MSA Trend Analysis (Time Series)"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")

selected_areas = st.sidebar.multiselect(
    "Select Regions / MSAs:",
    options=list(LA_AREAS.keys()),
    default=["Louisiana (Statewide)", "Baton Rouge MSA", "New Orleans-Metairie MSA", "Lafayette MSA"]
)

selected_datatype = st.sidebar.selectbox(
    "Select Metric:",
    options=list(SAE_DATA_TYPES.keys()),
    index=0
)

selected_industries = st.sidebar.multiselect(
    "Select Industry Supersectors / Sub-industries:",
    options=list(SAE_INDUSTRIES.keys()),
    default=["Total Nonfarm", "Construction", "Manufacturing", "Trade, Transportation, and Utilities", "Leisure and Hospitality"]
)

current_year = datetime.now().year

if view_mode == "Regional Comparison Matrix (Single Month)":
    target_year = st.sidebar.number_input("Target Year", min_value=2010, max_value=current_year, value=2024)
    target_month = st.sidebar.selectbox("Target Month", [
        "January", "February", "March", "April", "May", "June", 
        "July", "August", "September", "October", "November", "December"
    ], index=4)
else:
    start_yr = st.sidebar.number_input("Start Year", min_value=2010, max_value=current_year, value=2020)
    end_yr = st.sidebar.number_input("End Year", min_value=2010, max_value=current_year, value=2024)

# -----------------------------------------------------------------------------
# MAIN APP EXECUTION
# -----------------------------------------------------------------------------

if st.sidebar.button("Run Data Extraction"):
    if not BLS_API_KEY:
        st.error("Missing BLS API Key! Please set `BLS_API_KEY` in Streamlit secrets.")
    elif not selected_areas:
        st.warning("Please select at least one Region or MSA.")
    elif not selected_industries:
        st.warning("Please select at least one Industry.")
    else:
        # Build Series Map dynamically
        # SAE Format: SMU + 22 (LA) + Area (5) + Industry (8) + DataType (2)
        dtype_code = SAE_DATA_TYPES[selected_datatype]
        series_map = {}
        
        for area_name in selected_areas:
            area_code = LA_AREAS[area_name]
            for ind_name in selected_industries:
                ind_code = SAE_INDUSTRIES[ind_name]
                s_id = f"SMU22{area_code}{ind_code}{dtype_code}"
                series_map[s_id] = {
                    "Area": area_name,
                    "Industry": ind_name,
                    "Metric": selected_datatype
                }

        # ---------------------------------------------------------------------
        # VIEW MODE 1: COMPARISON MATRIX
        # ---------------------------------------------------------------------
        if view_mode == "Regional Comparison Matrix (Single Month)":
            month_map = {
                "January": "M01", "February": "M02", "March": "M03", "April": "M04",
                "May": "M05", "June": "M06", "July": "M07", "August": "M08",
                "September": "M09", "October": "M10", "November": "M11", "December": "M12"
            }
            target_period = month_map[target_month]
            
            with st.spinner(f"Extracting {selected_datatype} for {target_month} {target_year}..."):
                df_res = fetch_bls_batch(series_map, target_year, target_year, BLS_API_KEY)
                
                if not df_res.empty:
                    # Filter specifically for target month
                    filtered = df_res[(df_res['year'] == str(target_year)) & (df_res['period'] == target_period)]
                    
                    if not filtered.empty:
                        st.subheader(f"📊 {selected_datatype} Comparison ({target_month} {target_year})")
                        
                        # Pivot table: Industries on Rows, Regions on Columns
                        pivot_df = filtered.pivot(index="Industry", columns="Area", values="Value")
                        
                        # Reorder rows to match selection order
                        pivot_df = pivot_df.reindex([i for i in selected_industries if i in pivot_df.index])
                        
                        st.dataframe(
                            pivot_df.style.format("{:,.2f}", na_rep="N/A"),
                            use_container_width=True
                        )
                        
                        st.download_button(
                            label="📥 Download Matrix as CSV",
                            data=pivot_df.to_csv().encode('utf-8'),
                            file_name=f"louisiana_economic_matrix_{target_month}_{target_year}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.warning(f"No data reported by BLS for {target_month} {target_year}. Try selecting an earlier date range.")
                else:
                    st.error("Failed to retrieve data from BLS API.")

        # ---------------------------------------------------------------------
        # VIEW MODE 2: MULTI-MSA TIME SERIES TRENDS
        # ---------------------------------------------------------------------
        else:
            with st.spinner("Fetching historical time series across selected regions..."):
                df_res = fetch_bls_batch(series_map, start_yr, end_yr, BLS_API_KEY)
                
                if not df_res.empty:
                    st.subheader(f"📈 Historical Trends: {selected_datatype}")
                    
                    focus_industry = st.selectbox(
                        "Choose Industry to Plot Across Regions:",
                        options=[i for i in selected_industries if i in df_res['Industry'].unique()]
                    )
                    
                    trend_df = df_res[df_res['Industry'] == focus_industry]
                    chart_pivot = trend_df.pivot(index="Date", columns="Area", values="Value")
                    
                    st.line_chart(chart_pivot)
                    
                    st.subheader("Raw Time Series Table")
                    formatted_table = trend_df[['Date', 'Area', 'Industry', 'Value']].copy()
                    formatted_table['Value'] = formatted_table['Value'].map('{:,.2f}'.format)
                    st.dataframe(formatted_table, use_container_width=True)
                else:
                    st.error("No time series data returned for the selected query.")
