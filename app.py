import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Louisiana Economic Data Explorer", layout="wide")
st.title("📈 Louisiana Economic & Occupational Explorer (BLS)")

BLS_API_KEY = st.secrets.get("BLS_API_KEY", "")

# -----------------------------------------------------------------------------
# REFERENCE DICTIONARIES
# -----------------------------------------------------------------------------

# SAE Area Codes (Corrected for BLS)
LA_SAE_AREAS = {
    "Louisiana (Statewide)": "00000",
    "Alexandria MSA": "10780",
    "Baton Rouge MSA": "12940",
    "Hammond MSA": "25220",
    "Houma-Thibodaux MSA": "26380",
    "Lafayette MSA": "29180",
    "Lake Charles MSA": "29340",
    "Monroe MSA": "33740",
    "New Orleans-Metairie MSA": "35380",
    "Shreveport-Bossier City MSA": "43340"
}

SAE_DATA_TYPES = {
    "All Employees (Thousands)": "01",
    "Average Hourly Earnings ($)": "03",
    "Average Weekly Hours": "07",
    "Average Weekly Earnings ($)": "11"
}

SAE_INDUSTRIES = {
    "Total Nonfarm": "00000000",
    "Total Private": "05000000",
    "Mining, Logging, and Construction": "15000000",
    "Construction": "20000000",
    "Manufacturing": "30000000",
    "Trade, Transportation, and Utilities": "40000000",
    "Information": "50000000",
    "Financial Activities": "55000000",
    "Professional and Business Services": "60000000",
    "Education and Health Services": "65000000",
    "Leisure and Hospitality": "70000000",
    "Other Services": "80000000",
    "Government": "90000000"
}

# OEWS Area Mapping
LA_OEWS_AREAS = {
    "Louisiana (Statewide)": ("S", "2200000"),
    "Alexandria MSA": ("M", "0010780"),
    "Baton Rouge MSA": ("M", "0012940"),
    "Hammond MSA": ("M", "0025220"),
    "Houma-Thibodaux MSA": ("M", "0026380"),
    "Lafayette MSA": ("M", "0029180"),
    "Lake Charles MSA": ("M", "0029340"),
    "Monroe MSA": ("M", "0033740"),
    "New Orleans-Metairie MSA": ("M", "0035380"),
    "Shreveport-Bossier City MSA": ("M", "0043340")
}

OEWS_OCCUPATIONS = {
    "All Occupations (Total)": "000000",
    "Management Occupations": "110000",
    "Business and Financial Operations": "130000",
    "Computer and Mathematical": "150000",
    "Architecture and Engineering": "170000",
    "Healthcare Practitioners & Technical": "290000",
    "Healthcare Support": "310000",
    "Construction and Extraction": "470000",
    "Installation, Maintenance, and Repair": "490000",
    "Production Occupations": "510000",
    "Transportation and Material Moving": "530000"
}

OEWS_DATA_TYPES = {
    "Employment Count": "01",
    "Hourly Mean Wage ($)": "03",
    "Annual Mean Wage ($)": "04",
    "Hourly Median Wage ($)": "13",
    "Annual Median Wage ($)": "14"
}

# QCEW FIPS Mapping (5-digit Area FIPS)
QCEW_AREAS = {
    "United States (National)": "US000",
    "Louisiana (Statewide)": "22000",
    "Alexandria MSA": "C1078",
    "Baton Rouge MSA": "C1294",
    "Hammond MSA": "C2522",
    "Houma-Thibodaux MSA": "C2638",
    "Lafayette MSA": "C2918",
    "Lake Charles MSA": "C2934",
    "Monroe MSA": "C3374",
    "New Orleans-Metairie MSA": "C3538",
    "Shreveport-Bossier City MSA": "C4334"
}

# CORRECTED QCEW INDUSTRY TAXONOMY
QCEW_INDUSTRIES = {
    # High-Level Aggregates & Supersectors
    "10 Total, All Industries": "10",
    "101 Goods-Producing Domain": "101",
    "1011 Natural Resources & Mining": "1011",
    "1012 Construction": "1012",
    "1013 Manufacturing": "1013",
    "102 Service-Providing Domain": "102",
    "1021 Trade, Transportation, & Utilities": "1021",
    "1022 Information": "1022",
    "1023 Financial Activities": "1023",
    "1024 Professional & Business Services": "1024",
    "1025 Education & Health Services": "1025",
    "1026 Leisure & Hospitality": "1026",
    "1027 Other Services": "1027",
    "1028 Public Administration": "1028",
    
    # Standard 2-Digit NAICS Sectors
    "NAICS 11 Agriculture, Forestry, Fishing": "11",
    "NAICS 21 Mining, Quarrying, Oil & Gas": "21",
    "NAICS 22 Utilities": "22",
    "NAICS 23 Construction": "23",
    "NAICS 31-33 Manufacturing": "31-33",
    "NAICS 42 Wholesale Trade": "42",
    "NAICS 44-45 Retail Trade": "44-45",
    "NAICS 48-49 Transportation & Warehousing": "48-49",
    "NAICS 51 Information": "51",
    "NAICS 52 Finance & Insurance": "52",
    "NAICS 53 Real Estate & Rental/Leasing": "53",
    "NAICS 54 Professional, Scientific, Tech": "54",
    "NAICS 55 Management of Companies": "55",
    "NAICS 56 Admin & Support / Waste Mgmt": "56",
    "NAICS 61 Educational Services": "61",
    "NAICS 62 Health Care & Social Assistance": "62",
    "NAICS 71 Arts, Entertainment, Recreation": "71",
    "NAICS 72 Accommodation & Food Services": "72",
    "NAICS 81 Other Services (ex. Public Admin)": "81",
    "NAICS 92 Public Administration": "92"
}

QCEW_METRICS = {
    "Average Weekly Wage ($)": "avg_wkly_wage",
    "Month 3 Employment Level": "month3_emplvl",
    "Total Quarterly Wages ($)": "total_qtrly_wages",
    "Establishment Count": "qtrly_estabs"
}

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def fetch_bls_batch(series_dict, start_year, end_year, api_key):
    series_ids = list(series_dict.keys())
    all_records = []
    
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
                    record_copy['seriesID'] = s_id
                    all_records.append(record_copy)
                    
    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df['Value'] = pd.to_numeric(df['value'], errors='coerce')
    return df

@st.cache_data(ttl=3600)
def fetch_qcew_area_slice(year, quarter, area_fips):
    """Fetches QCEW area CSV slice directly from BLS Open Data."""
    q_str = "a" if str(quarter).upper() == "A" else str(quarter)
    url = f"https://data.bls.gov/cew/data/api/{year}/{q_str}/area/{area_fips}.csv"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return pd.read_csv(io.StringIO(res.text), dtype={'area_fips': str, 'industry_code': str, 'own_code': str})
    except Exception:
        pass
    return pd.DataFrame()

# -----------------------------------------------------------------------------
# NAVIGATION TABS
# -----------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "📊 State & MSA Industry Data (Monthly)", 
    "💼 Occupational Employment & Wages (OEWS)", 
    "🏢 Quarterly Census of Employment & Wages (QCEW)"
])

# =============================================================================
# TAB 1: INDUSTRY EMPLOYMENT, HOURS & EARNINGS
# =============================================================================
with tab1:
    st.header("Industry Nonfarm Employment, Hours & Earnings")
    st.caption("Data source: BLS State and Area Employment (SAE)")

    col1, col2 = st.columns([1, 3])

    with col1:
        sae_view = st.radio("View Mode:", ["Single Month Comparison Matrix", "Multi-MSA Historical Trends"])
        
        selected_sae_areas = st.multiselect(
            "Select Regions / MSAs:",
            options=list(LA_SAE_AREAS.keys()),
            default=["Louisiana (Statewide)", "Baton Rouge MSA", "New Orleans-Metairie MSA", "Lafayette MSA"]
        )
        
        selected_metric = st.selectbox("Select Metric:", list(SAE_DATA_TYPES.keys()), index=0)
        
        selected_sae_industries = st.multiselect(
            "Select Industries:",
            options=list(SAE_INDUSTRIES.keys()),
            default=["Total Nonfarm", "Construction", "Manufacturing", "Trade, Transportation, and Utilities"]
        )
        
        cur_yr = datetime.now().year
        if sae_view == "Single Month Comparison Matrix":
            sae_yr = st.number_input("Target Year", min_value=2010, max_value=cur_yr, value=2024, key="sae_yr")
            sae_mo = st.selectbox("Target Month", [
                "January", "February", "March", "April", "May", "June", 
                "July", "August", "September", "October", "November", "December"
            ], index=4)
        else:
            sae_start = st.number_input("Start Year", min_value=2010, max_value=cur_yr, value=2020, key="sae_s")
            sae_end = st.number_input("End Year", min_value=2010, max_value=cur_yr, value=2024, key="sae_e")

        run_sae = st.button("Extract Industry Data")

    with col2:
        if run_sae:
            if not BLS_API_KEY:
                st.error("Missing BLS API Key in Streamlit Secrets!")
            else:
                dtype_code = SAE_DATA_TYPES[selected_metric]
                series_map = {}
                
                for area in selected_sae_areas:
                    area_code = LA_SAE_AREAS[area]
                    for ind in selected_sae_industries:
                        ind_code = SAE_INDUSTRIES[ind]
                        s_id = f"SMU22{area_code}{ind_code}{dtype_code}"
                        series_map[s_id] = {"Area": area, "Industry": ind, "Metric": selected_metric}

                if sae_view == "Single Month Comparison Matrix":
                    mo_map = {"January": "M01", "February": "M02", "March": "M03", "April": "M04", "May": "M05", "June": "M06",
                              "July": "M07", "August": "M08", "September": "M09", "October": "M10", "November": "M11", "December": "M12"}
                    
                    df_res = fetch_bls_batch(series_map, sae_yr, sae_yr, BLS_API_KEY)
                    
                    if not df_res.empty:
                        filtered = df_res[(df_res['year'] == str(sae_yr)) & (df_res['period'] == mo_map[sae_mo])]
                        
                        if not filtered.empty:
                            st.subheader(f"{selected_metric} Matrix ({sae_mo} {sae_yr})")
                            pivot_df = filtered.pivot(index="Industry", columns="Area", values="Value")
                            fmt = "{:,.1f}" if "Employees" in selected_metric else "${:,.2f}" if "$" in selected_metric else "{:,.2f}"
                            st.dataframe(pivot_df.style.format(fmt, na_rep="N/A"), use_container_width=True)
                        else:
                            st.warning(f"No BLS data available for {sae_mo} {sae_yr}.")
                else:
                    df_res = fetch_bls_batch(series_map, sae_start, sae_end, BLS_API_KEY)
                    if not df_res.empty:
                        df_res = df_res[df_res['period'].str.startswith('M') & (df_res['period'] != 'M13')].copy()
                        df_res['Date_Dt'] = pd.to_datetime(df_res['year'] + '-' + df_res['period'].str.replace('M', ''), format='%Y-%m')
                        df_res['Month_Year'] = df_res['Date_Dt'].dt.strftime('%b %Y')
                        df_res = df_res.sort_values('Date_Dt')

                        focus_ind = st.selectbox("Select Industry to Plot Across Regions:", selected_sae_industries)
                        trend_df = df_res[df_res['Industry'] == focus_ind]
                        chart_pivot = trend_df.pivot(index="Month_Year", columns="Area", values="Value")
                        
                        st.line_chart(chart_pivot)
                        st.subheader("Raw Historical Table")
                        fmt = "{:,.1f}" if "Employees" in selected_metric else "{:,.2f}"
                        formatted_df = trend_df[['Month_Year', 'Area', 'Industry', 'Value']].copy()
                        formatted_df['Value'] = formatted_df['Value'].apply(lambda x: fmt.format(x) if pd.notnull(x) else "")
                        st.dataframe(formatted_df, use_container_width=True)

# =============================================================================
# TAB 2: OCCUPATIONAL EMPLOYMENT & WAGES (OEWS)
# =============================================================================
with tab2:
    st.header("💼 Occupational Employment & Wage Statistics (OEWS)")
    st.caption("Compare Employment, Median, and Mean Wages across Occupations and Regions over time.")

    o_col1, o_col2 = st.columns([1, 3])

    with o_col1:
        oews_view = st.radio("OEWS Mode:", ["Regional Comparison (Single Year)", "Occupation Trend Over Time"])
        
        selected_oews_areas = st.multiselect(
            "Select MSAs / Statewide:",
            options=list(LA_OEWS_AREAS.keys()),
            default=["Louisiana (Statewide)", "Baton Rouge MSA", "New Orleans-Metairie MSA"],
            key="oews_areas"
        )
        
        selected_oews_metric = st.selectbox("Select Wage/Employment Measure:", list(OEWS_DATA_TYPES.keys()))
        
        selected_occupations = st.multiselect(
            "Select Occupations:",
            options=list(OEWS_OCCUPATIONS.keys()),
            default=["All Occupations (Total)", "Management Occupations", "Healthcare Practitioners & Technical", "Construction and Extraction"]
        )
        
        if oews_view == "Regional Comparison (Single Year)":
            oews_year = st.number_input("Target Year", min_value=2015, max_value=2025, value=2024, key="oews_yr")
        else:
            oews_start_yr = st.number_input("Start Year", min_value=2015, max_value=2025, value=2018, key="oews_s")
            oews_end_yr = st.number_input("End Year", min_value=2015, max_value=2025, value=2025, key="oews_e")
            
        run_oews = st.button("Extract OEWS Data")

    with o_col2:
        if run_oews:
            if not BLS_API_KEY:
                st.error("Missing BLS API Key!")
            else:
                dtype_code = OEWS_DATA_TYPES[selected_oews_metric]
                oews_series_map = {}
                
                for area_name in selected_oews_areas:
                    area_type, area_code = LA_OEWS_AREAS[area_name]
                    for occ_name in selected_occupations:
                        occ_code = OEWS_OCCUPATIONS[occ_name]
                        s_id = f"OEU{area_type}{area_code}000000{occ_code}{dtype_code}"
                        oews_series_map[s_id] = {
                            "Area": area_name,
                            "Occupation": occ_name,
                            "Metric": selected_oews_metric
                        }

                if oews_view == "Regional Comparison (Single Year)":
                    df_oews = fetch_bls_batch(oews_series_map, oews_year, oews_year, BLS_API_KEY)
                    if not df_oews.empty:
                        st.subheader(f"{selected_oews_metric} Matrix ({oews_year})")
                        pivot_oews = df_oews.pivot(index="Occupation", columns="Area", values="Value")
                        fmt = "${:,.2f}" if "$" in selected_oews_metric else "{:,.0f}"
                        st.dataframe(pivot_oews.style.format(fmt, na_rep="N/A"), use_container_width=True)
                    else:
                        st.warning(f"No OEWS data returned for {oews_year}.")
                else:
                    df_oews = fetch_bls_batch(oews_series_map, oews_start_yr, oews_end_yr, BLS_API_KEY)
                    if not df_oews.empty:
                        df_oews = df_oews.sort_values('year')
                        focus_occ = st.selectbox("Select Occupation to Trend Across Regions:", selected_occupations)
                        occ_trend = df_oews[df_oews['Occupation'] == focus_occ]
                        chart_piv = occ_trend.pivot(index="year", columns="Area", values="Value")
                        
                        st.line_chart(chart_piv)
                        st.subheader("Raw Annual Data Table")
                        fmt = "${:,.2f}" if "$" in selected_oews_metric else "{:,.0f}"
                        occ_trend['Value_Formatted'] = occ_trend['Value'].apply(lambda x: fmt.format(x) if pd.notnull(x) else "")
                        st.dataframe(occ_trend[['year', 'Area', 'Occupation', 'Value_Formatted']].rename(columns={'year': 'Year', 'Value_Formatted': 'Value'}), use_container_width=True)

# =============================================================================
# TAB 3: QUARTERLY CENSUS OF EMPLOYMENT & WAGES (QCEW)
# =============================================================================
with tab3:
    st.header("🏢 Quarterly Census of Employment & Wages (QCEW)")
    st.caption("Compare establishments, employment levels, and weekly wages across US, Louisiana, and MSAs.")

    q_col1, q_col2 = st.columns([1, 3])

    with q_col1:
        data_source = st.radio("Data Source Mode:", ["API Fetch (Automated)", "Manual CSV Upload"])
        
        selected_qcew_areas = st.multiselect(
            "Select Regions to Compare:",
            options=list(QCEW_AREAS.keys()),
            default=["United States (National)", "Louisiana (Statewide)", "Baton Rouge MSA", "New Orleans-Metairie MSA"]
        )
        
        selected_qcew_industries = st.multiselect(
            "Select Industries:",
            options=list(QCEW_INDUSTRIES.keys()),
            default=["10 Total, All Industries", "1012 Construction", "1013 Manufacturing", "1024 Professional & Business Services"]
        )
        
        selected_qcew_metric = st.selectbox("Select Metric:", list(QCEW_METRICS.keys()))
        metric_col = QCEW_METRICS[selected_qcew_metric]

        start_yr_qcew = st.number_input("Start Year", min_value=2015, max_value=2025, value=2021, key="qcew_start")
        end_yr_qcew = st.number_input("End Year", min_value=2015, max_value=2025, value=2024, key="qcew_end")
        
        # Ownership mapping dictionary to ensure correct value handling
        ownership_map = {
            "Total Covered (All)": "5",
            "Private": "5",
            "State Govt": "2",
            "Local Govt": "3",
            "Federal Govt": "1"
        }
        selected_ownership_label = st.selectbox("Ownership Sector:", list(ownership_map.keys()), index=0)
        ownership_type = ownership_map[selected_ownership_label]

        uploaded_files = None
        if data_source == "Manual CSV Upload":
            uploaded_files = st.file_uploader("Upload QCEW Area CSV Files:", type=["csv"], accept_multiple_files=True)
            
        run_qcew = st.button("Generate QCEW Comparison")

    with q_col2:
        if run_qcew:
            combined_qcew = []

            if data_source == "API Fetch (Automated)":
                with st.spinner("Fetching QCEW data slices from BLS..."):
                    years_to_fetch = list(range(int(start_yr_qcew), int(end_yr_qcew) + 1))
                    quarters = ["1", "2", "3", "4"]

                    inv_area_map = {v: k for k, v in QCEW_AREAS.items()}
                    ind_codes = [QCEW_INDUSTRIES[i] for i in selected_qcew_industries]
                    
                    for area_name in selected_qcew_areas:
                        fips = QCEW_AREAS[area_name]
                        for yr in years_to_fetch:
                            for qtr in quarters:
                                df_slice = fetch_qcew_area_slice(yr, qtr, fips)
                                if not df_slice.empty:
                                    # Filter by ownership code and selected industry codes
                                    filtered_slice = df_slice[
                                        (df_slice['own_code'].astype(str) == ownership_type) & 
                                        (df_slice['industry_code'].astype(str).isin(ind_codes))
                                    ].copy()
                                    
                                    if not filtered_slice.empty:
                                        filtered_slice['Region'] = area_name
                                        filtered_slice['Period'] = f"{yr} Q{qtr}"
                                        combined_qcew.append(filtered_slice)

            elif data_source == "Manual CSV Upload" and uploaded_files:
                for file in uploaded_files:
                    df_up = pd.read_csv(file, dtype={'area_fips': str, 'industry_code': str, 'own_code': str})
                    combined_qcew.append(df_up)

            if combined_qcew:
                qcew_df = pd.concat(combined_qcew, ignore_index=True)
                qcew_df[metric_col] = pd.to_numeric(qcew_df[metric_col], errors='coerce')

                # Code to Label mapping
                inv_ind_map = {v: k for k, v in QCEW_INDUSTRIES.items()}
                qcew_df['Industry_Label'] = qcew_df['industry_code'].map(inv_ind_map).fillna(qcew_df['industry_code'])

                st.subheader(f"Comparison Matrix: {selected_qcew_metric}")
                
                # Filter selection for charting
                focus_q_ind = st.selectbox("Filter Chart/Table by Industry:", selected_qcew_industries)
                sub_df = qcew_df[qcew_df['Industry_Label'] == focus_q_ind]

                if not sub_df.empty:
                    piv_table = sub_df.pivot(index="Period", columns="Region", values=metric_col)
                    
                    st.line_chart(piv_table)
                    
                    fmt_str = "${:,.2f}" if "$" in selected_qcew_metric else "{:,.0f}"
                    st.subheader(f"Data Summary: {focus_q_ind}")
                    st.dataframe(piv_table.style.format(fmt_str, na_rep="N/A"), use_container_width=True)
                else:
                    st.warning("No data found for the selected combination.")
            else:
                st.error("No QCEW data retrieved. Check selected years/regions or uploaded files.")
