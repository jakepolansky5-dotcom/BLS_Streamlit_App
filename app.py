import streamlit as st
import requests
import pandas as pd

# Set up app page title
st.set_page_config(page_title="Louisiana Economic Explorer", layout="wide")
st.title("📈 Louisiana Economic Data Explorer")
st.write("Fetch historical economic indicators for Louisiana State, MSAs, and Parishes via BLS.")

# Get BLS API Key securely from Streamlit secrets
BLS_API_KEY = st.secrets.get("BLS_API_KEY", "")

# -----------------------------------------------------------------------------
# FIPS & GEOGRAPHY DATA MAPPING FOR LOUISIANA
# -----------------------------------------------------------------------------

# Louisiana 64 Parishes (3-digit FIPS)
LA_PARISHES = {
    "Acadia Parish": "001", "Allen Parish": "003", "Ascension Parish": "005", "Assumption Parish": "007",
    "Avoyelles Parish": "009", "Beauregard Parish": "011", "Bienville Parish": "013", "Bossier Parish": "015",
    "Caddo Parish": "017", "Calcasieu Parish": "019", "Caldwell Parish": "021", "Cameron Parish": "023",
    "Catahoula Parish": "025", "Claiborne Parish": "027", "Concordia Parish": "029", "De Soto Parish": "031",
    "East Baton Rouge Parish": "033", "East Carroll Parish": "035", "East Feliciana Parish": "037", "Evangeline Parish": "039",
    "Franklin Parish": "041", "Grant Parish": "043", "Iberia Parish": "045", "Iberville Parish": "047",
    "Jackson Parish": "049", "Jefferson Parish": "051", "Jefferson Davis Parish": "053", "Lafayette Parish": "055",
    "Lafourche Parish": "057", "La Salle Parish": "059", "Lincoln Parish": "061", "Livingston Parish": "063",
    "Madison Parish": "065", "Morehouse Parish": "067", "NatchitochesTo adapt your app for Louisiana parishes, MSAs, and statewide data, you need to account for how the **Bureau of Labor Statistics (BLS)** constructs its Series IDs and handles sub-state metrics.

### Key Technical Details to Keep in Mind

1. **Local Area Unemployment Statistics (LAUS):**
   * Unemployment rates for state, MSA, and county/parish levels come from the **LAUS** program.
   * **Statewide LA:** `LAUST220000000000003`
   * **Parishes:** Follow the pattern `LAUCN22XXX0000000003` (where `22` is Louisiana's state FIPS code and `XXX` is the 3-digit Parish FIPS code).
   * **MSAs:** Follow the pattern `LAUMT22XXXXX0000003` (where `XXXXX` is the 5-digit MSA code).

2. **CPI Limitations for Sub-State Areas:**
   * BLS does **not** publish CPI data at the Parish level, nor does it publish CPI for most individual MSAs in Louisiana. 
   * The closest granular CPI indicators available are the **South Region Urban CPI** (`CUUR0400SA0`) or the **US City Average CPI** (`CUUR0000SA0`).

3. **BLS API 10-Year Request Limit:**
   * The BLS API limits single queries to a maximum 10-year window. For complete historical retrieval, requests spanning longer ranges need to be split into multi-year chunks.

---

### Updated Streamlit Code

Here is the complete refactored app with pre-populated lookups for all Louisiana parishes, major MSAs, and historical chunking support:

```python
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Louisiana Economic Data Explorer", layout="wide")
st.title("📈 Louisiana Economic Data Explorer (BLS)")
st.write("Analyze Unemployment Rates across Louisiana Parishes/MSAs alongside Consumer Price Index metrics.")

BLS_API_KEY = st.secrets.get("BLS_API_KEY", "")

# --- Reference Mappings for Louisiana ---
LA_PARISHES = {
    "Acadia Parish": "001", "Allen Parish": "003", "Ascension Parish": "005", "Assumption Parish": "007",
    "Avoyelles Parish": "009", "Beauregard Parish": "011", "Bienville Parish": "013", "Bossier Parish": "015",
    "Caddo Parish": "017", "Calcasieu Parish": "019", "Caldwell Parish": "021", "Cameron Parish": "023",
    "Catahoula Parish": "025", "Claiborne Parish": "027", "Concordia Parish": "029", "De Soto Parish": "031",
    "East Baton Rouge Parish": "033", "East Carroll Parish": "035", "East Feliciana Parish": "037",
    "Evangeline Parish": "039", "Franklin Parish": "041", "Grant Parish": "043", "Iberia Parish": "045",
    "Iberville Parish": "047", "Jackson Parish": "049", "Jefferson Parish": "051", "Jefferson Davis Parish": "053",
    "Lafayette Parish": "055", "Lafourche Parish": "057", "LaSalle Parish": "059", "Lincoln Parish": "061",
    "Livingston Parish": "063", "Madison Parish": "065", "Morehouse Parish": "067", "Natchitoches Parish": "069",
    "Orleans Parish": "071", "Ouachita Parish": "073", "Plaquemines Parish": "075", "Pointe Coupee Parish": "077",
    "Rapides Parish": "079", "Red River Parish": "081", "Richland Parish": "083", "Sabine Parish": "085",
    "St. Bernard Parish": "087", "St. Charles Parish": "089", "St. Helena Parish": "091", "St. James Parish": "093",
    "St. John the Baptist Parish": "095", "St. Landry Parish": "097", "St. Martin Parish": "099",
    "St. Mary Parish": "101", "St. Tammany Parish": "103", "Tangipahoa Parish": "105", "Tensas Parish": "107",
    "Terrebonne Parish": "109", "Union Parish": "111", "Vermilion Parish": "113", "Vernon Parish": "115",
    "Washington Parish": "117", "Webster Parish": "119", "West Baton Rouge Parish": "121",
    "West Carroll Parish": "123", "West Feliciana Parish": "125", "Winn Parish": "127"
}

LA_MSAS = {
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

CPI_OPTIONS = {
    "South Region Urban CPI (CUUR0400SA0)": "CUUR0400SA0",
    "U.S. City Average CPI (CUUR0000SA0)": "CUUR0000SA0"
}

# --- Sidebar Controls ---
st.sidebar.header("Query Settings")

indicator_type = st.sidebar.radio("Select Category:", ["Unemployment Rate (LAUS)", "Consumer Price Index (CPI)"])

series_id = ""
selected_label = ""

if indicator_type == "Unemployment Rate (LAUS)":
    geo_level = st.sidebar.selectbox("Geographic Level:", ["Statewide (Louisiana)", "Parish", "Metropolitan Statistical Area (MSA)"])
    
    if geo_level == "Statewide (Louisiana)":
        series_id = "LAUST220000000000003"
        selected_label = "Louisiana Statewide Unemployment Rate"
    elif geo_level == "Parish":
        parish = st.sidebar.selectbox("Select Parish:", list(LA_PARISHES.keys()))
        fips = LA_PARISHES[parish]
        series_id = f"LAUCN22{fips}0000000003"
        selected_label = f"{parish} Unemployment Rate"
    else:
        msa = st.sidebar.selectbox("Select MSA:", list(LA_MSAS.keys()))
        msa_code = LA_MSAS[msa]
        series_id = f"LAUMT22{msa_code}00000003"
        selected_label = f"{msa} Unemployment Rate"

else:
    cpi_choice = st.sidebar.selectbox("Select CPI Index:", list(CPI_OPTIONS.keys()))
    series_id = CPI_OPTIONS[cpi_choice]
    selected_label = cpi_choice
    st.sidebar.info("Note: BLS does not publish Parish/MSA-level CPI. Regional and National indices are shown above.")

start_year = int(st.sidebar.number_input("Start Year", min_value=1990, max_value=datetime.now().year, value=2015))
end_year = int(st.sidebar.number_input("End Year", min_value=1990, max_value=datetime.now().year, value=2024))

def fetch_bls_series(series_id, start_yr, end_yr, api_key):
    """Fetches data across multi-year chunks to bypass the BLS 10-year limit."""
    all_records = []
    chunk_size = 10
    
    for yr in range(start_yr, end_yr + 1, chunk_size):
        chunk_end = min(yr + chunk_size - 1, end_yr)
        
        url = "[https://api.bls.gov/publicAPI/v2/timeseries/data/](https://api.bls.gov/publicAPI/v2/timeseries/data/)"
        payload = {
            "seriesid": [series_id],
            "startyear": str(yr),
            "endyear": str(chunk_end),
            "registrationkey": api_key
        }
        
        response = requests.post(url, json=payload)
        res_data = response.json()
        
        if res_data.get("status") == "REQUEST_SUCCEEDED":
            series_list = res_data.get("Results", {}).get("series", [])
            if series_list and series_list[0].get("data"):
                all_records.extend(series_list[0]["data"])
        else:
            st.error(f"API Error during period {yr}-{chunk_end}: {res_data.get('message')}")
            break
            
    return all_records

if st.sidebar.button("Fetch Data"):
    if not BLS_API_KEY:
        st.error("Missing BLS API Key! Please configure it in Streamlit secrets.")
    elif start_year > end_year:
        st.error("Start Year must be less than or equal to End Year.")
    else:
        with st.spinner(f"Fetching historical data for {selected_label}..."):
            records = fetch_bls_series(series_id, start_year, end_year, BLS_API_KEY)
            
            if records:
                df = pd.DataFrame(records)
                
                # Filter out annual averages (M13) if present
                df = df[df['period'].str.startswith('M') & (df['period'] != 'M13')].copy()
                
                # Format numerical data and datetime
                df['Value'] = pd.to_numeric(df['value'], errors='coerce')
                df['Date'] = pd.to_datetime(df['year'] + '-' + df['period'].str.replace('M', ''), format='%Y-%m')
                df = df.sort_values('Date').reset_index(drop=True)
                
                st.subheader(f"{selected_label}")
                st.caption(f"BLS Series ID: `{series_id}`")
                
                st.line_chart(df, x="Date", y="Value")
                
                st.subheader("Raw Data Table")
                st.dataframe(
                    df[['year', 'periodName', 'value']].rename(
                        columns={'year': 'Year', 'periodName': 'Month', 'value': 'Value'}
                    ),
                    use_container_width=True
                )
            else:
                st.error("No data returned for the selected series and timeframe.")
