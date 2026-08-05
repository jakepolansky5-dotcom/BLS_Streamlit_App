import streamlit as st
import requests
import pandas as pd
from datetime import datetime

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

# OEWS Area Mapping (7-digit BLS OEWS Area Codes)
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

# -----------------------------------------------------------------------------
# NAVIGATION TABS
# -----------------------------------------------------------------------------

tab1, tab2 = st.tabs(["📊 State & MSA Industry Data (Monthly)", "💼 Occupational Employment & Wages - OEWS (Annual)"])

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
                            
                            # Apply precision rounding: 1 decimal place for Employment, 2 for Earnings/Hours
                            fmt = "{:,.1f}" if "Employees" in selected_metric else "${:,.2f}" if "$" in selected_metric else "{:,.2f}"
                            st.dataframe(pivot_df.style.format(fmt, na_rep="N/A"), use_container_width=True)
                        else:
                            st.warning(f"No BLS data available for {sae_mo} {sae_yr}.")
                else:
                    df_res = fetch_bls_batch(series_map, sae_start, sae_end, BLS_API_KEY)
                    if not df_res.empty:
                        df_res = df_res[df_res['period'].str.startswith('M') & (df_res['period'] != 'M13')].copy()
                        # Formatted Date without exact days (e.g., May 2024)
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
                # OEWS Series ID Structure:
                # OE + U + AreaType (1) + AreaCode (7) + Industry (000000) + Occupation (6) + DataType (2)
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
