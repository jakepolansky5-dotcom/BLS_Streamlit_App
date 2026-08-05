import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io

st.set_page_config(page_title="Louisiana Economic Data Explorer", layout="wide")
st.title("📈 Louisiana Economic & Occupational Explorer (BLS)")

BLS_API_KEY = st.secrets.get("BLS_API_KEY", "")

# Header configuration for BLS Open Data requests to prevent HTTP 403/503 blocks
HTTP_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# -----------------------------------------------------------------------------
# REFERENCE DICTIONARIES & ORGANIZED TAXONOMIES
# -----------------------------------------------------------------------------

# SAE Area Codes
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

# QCEW FIPS Mapping
QCEW_AREAS = {
    "United States (National)": "US000",
    "Louisiana (Statewide)": "22000",
    "Alexandria MSA": "C1002",
    "Baton Rouge MSA": "C1294",
    "Hammond MSA": "C2522",
    "Houma-Thibodaux MSA": "C2638",
    "Lafayette MSA": "C2918",
    "Lake Charles MSA": "C2934",
    "Monroe MSA": "C3374",
    "New Orleans-Metairie MSA": "C3538",
    "Shreveport-Bossier City MSA": "C4334"
}

# QCEW INDUSTRY TAXONOMY
QCEW_AGGREGATES = {
    "10 - Total, All Industries": "10",
    "101 - Goods-Producing Domain": "101",
    "102 - Service-Providing Domain": "102",
    "1011 - Natural Resources & Mining": "1011",
    "1012 - Construction": "1012",
    "1013 - Manufacturing": "1013",
    "1021 - Trade, Transportation, & Utilities": "1021",
    "1022 - Information": "1022",
    "1023 - Financial Activities": "1023",
    "1024 - Professional & Business Services": "1024",
    "1025 - Education & Health Services": "1025",
    "1026 - Leisure & Hospitality": "1026",
    "1027 - Other Services": "1027",
    "1028 - Public Administration": "1028"
}

QCEW_SECTORS_2DIGIT = {
    "11 - Agriculture, Forestry, Fishing": "11",
    "21 - Mining, Quarrying, Oil & Gas": "21",
    "22 - Utilities": "22",
    "23 - Construction": "23",
    "31-33 - Manufacturing (Total)": "31-33",
    "42 - Wholesale Trade": "42",
    "44-45 - Retail Trade": "44-45",
    "48-49 - Transportation & Warehousing": "48-49",
    "51 - Information": "51",
    "52 - Finance & Insurance": "52",
    "53 - Real Estate & Rental/Leasing": "53",
    "54 - Professional, Scientific, Tech": "54",
    "55 - Management of Companies": "55",
    "56 - Admin & Support / Waste Mgmt": "56",
    "61 - Educational Services": "61",
    "62 - Health Care & Social Assistance": "62",
    "71 - Arts, Entertainment, Recreation": "71",
    "72 - Accommodation & Food Services": "72",
    "81 - Other Services": "81",
    "92 - Public Administration": "92"
}

QCEW_MANUFACTURING_SUBSECTORS = {
    "311 - Food Manufacturing": "311",
    "312 - Beverage & Tobacco Products": "312",
    "321 - Wood Products Manufacturing": "321",
    "322 - Paper Manufacturing": "322",
    "324 - Petroleum & Coal Products Manufacturing": "324",
    "325 - Chemical Manufacturing": "325",
    "326 - Plastics & Rubber Products": "326",
    "327 - Nonmetallic Mineral Products": "327",
    "331 - Primary Metal Manufacturing": "331",
    "332 - Fabricated Metal Products": "332",
    "333 - Machinery Manufacturing": "333",
    "334 - Computer & Electronic Products": "334",
    "335 - Electrical Equipment & Appliances": "335",
    "336 - Transportation Equipment (Shipbuilding/Aerospace)": "336"
}

QCEW_MANUFACTURING_DETAILED = {
    "3241 - Petroleum Refineries & Asphalt": "3241",
    "3251 - Basic Chemical Manufacturing": "3251",
    "3252 - Resin, Synthetic Rubber, & Fibers": "3252",
    "3253 - Pesticide, Fertilizer, & Agricultural Chemicals": "3253",
    "3327 - Machine Shops & Turned Products": "3327",
    "3331 - Agriculture, Construction, & Mining Machinery": "3331",
    "3366 - Ship & Boat Building": "3366"
}

QCEW_METRICS = {
    "Average Weekly Wage ($)": "avg_wkly_wage",
    "Month 3 Employment Level": "month3_emplvl",
    "Total Quarterly Wages ($)": "total_qtrly_wages",
    "Establishment Count": "qtrly_estabs"
}

QCEW_ANNUAL_METRICS = {
    "Annual Average Employment Level": "annual_avg_emplvl",
    "Average Annual Pay ($)": "avg_annual_pay",
    "Total Annual Wages ($)": "total_annual_wages",
    "Annual Average Establishment Count": "annual_avg_estabs"
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
        
        try:
            response = requests.post(url, json=payload, headers=HTTP_HEADERS, timeout=15)
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
        except Exception:
            pass
                    
    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df['Value'] = pd.to_numeric(df['value'], errors='coerce')
    return df

@st.cache_data(ttl=3600)
def fetch_qcew_area_slice(year, quarter, area_fips):
    """
    Fetches QCEW Area Slice CSV and strips quotes from headers and values.
    Ensures MSA codes are uppercase and handles BLS API layout variances.
    """
    q_str = str(quarter).strip().lower()
    area_clean = str(area_fips).strip().upper()
    url = f"https://data.bls.gov/cew/data/api/{year}/{q_str}/area/{area_clean}.csv"
    
    try:
        res = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        if res.status_code == 200:
            # Read all columns as string first to prevent numeric parsing errors
            df = pd.read_csv(io.StringIO(res.text), dtype=str)
            
            # 1. Clean quote marks and whitespace from headers
            df.columns = [c.replace('"', '').replace("'", '').strip() for c in df.columns]
            
            # 2. Clean quote marks and whitespace from cell values across all text columns
            for col in df.columns:
                df[col] = df[col].astype(str).str.replace('"', '').str.replace("'", '').str.strip()
                
            return df
        else:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# NAVIGATION TABS
# -----------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs([
    "📊 Monthly Employment & Hours (SAE)", 
    "💼 Occupational Wages (OEWS)", 
    "🏢 Detailed Industry Wages & Employment (QCEW)"
])

# =============================================================================
# TAB 1: SAE
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
            sae_end = st.number_input("End Year", min_value=2010, max_value=cur_yr, value=2025, key="sae_e")

        run_sae = st.button("Extract SAE Data", type="primary")

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
# TAB 2: OEWS
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
            
        run_oews = st.button("Extract OEWS Data", type="primary")

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
# TAB 3: ROBUST & FLEXIBLE QCEW INTERFACE
# =============================================================================
with tab3:
    st.header("🏢 Quarterly Census of Employment & Wages (QCEW)")
    st.caption("Deep-dive into granular industry sectors, manufacturing sub-industries, and annual averages.")

    q_col1, q_col2 = st.columns([1, 3])

    with q_col1:
        st.subheader("1. Scope & Frequency")
        time_freq = st.radio("Time Resolution:", ["Annual Averages (Full Year)", "Quarterly Data"], index=0)
        
        st.subheader("2. Select Regions")
        selected_qcew_areas = st.multiselect(
            "Regions / MSAs:",
            options=list(QCEW_AREAS.keys()),
            default=["Baton Rouge MSA", "New Orleans-Metairie MSA", "Lake Charles MSA", "Houma-Thibodaux MSA"]
        )

        st.subheader("3. Select Industry Level")
        taxonomy_level = st.radio(
            "NAICS Detail Level:",
            [
                "Broad Supersectors & Aggregates",
                "2-Digit NAICS Sectors",
                "3-Digit Manufacturing Subsectors",
                "4-Digit Detailed Manufacturing"
            ],
            index=2
        )

        if taxonomy_level == "Broad Supersectors & Aggregates":
            active_dict = QCEW_AGGREGATES
            default_sel = ["10 - Total, All Industries", "1013 - Manufacturing"]
        elif taxonomy_level == "2-Digit NAICS Sectors":
            active_dict = QCEW_SECTORS_2DIGIT
            default_sel = ["31-33 - Manufacturing (Total)", "23 - Construction", "54 - Professional, Scientific, Tech"]
        elif taxonomy_level == "3-Digit Manufacturing Subsectors":
            active_dict = QCEW_MANUFACTURING_SUBSECTORS
            default_sel = ["325 - Chemical Manufacturing", "324 - Petroleum & Coal Products Manufacturing", "336 - Transportation Equipment (Shipbuilding/Aerospace)"]
        else:
            active_dict = QCEW_MANUFACTURING_DETAILED
            default_sel = ["3251 - Basic Chemical Manufacturing", "3241 - Petroleum Refineries & Asphalt", "3366 - Ship & Boat Building"]

        selected_qcew_industries = st.multiselect(
            "Select Industries to Query:",
            options=list(active_dict.keys()),
            default=default_sel
        )

        st.subheader("4. Metrics & Timeframe")
        if time_freq == "Annual Averages (Full Year)":
            selected_qcew_metric = st.selectbox("Select Metric:", list(QCEW_ANNUAL_METRICS.keys()), index=0)
            metric_col = QCEW_ANNUAL_METRICS[selected_qcew_metric]
        else:
            selected_qcew_metric = st.selectbox("Select Metric:", list(QCEW_METRICS.keys()), index=0)
            metric_col = QCEW_METRICS[selected_qcew_metric]

        c_yr1, c_yr2 = st.columns(2)
        cur_year = datetime.now().year
        with c_yr1:
            start_yr_qcew = st.number_input("Start Year", min_value=2012, max_value=cur_year, value=2018)
        with c_yr2:
            end_yr_qcew = st.number_input("End Year", min_value=2012, max_value=cur_year, value=2024)

        with st.expander("⚙️ Advanced Settings (Ownership Sector)"):
            ownership_map = {
                "Private Industry Only (Default)": "5",
                "Total Covered (Private + Govt)": "5",
                "State Government": "2",
                "Local Government": "3",
                "Federal Government": "1"
            }
            selected_ownership_label = st.selectbox("Ownership Sector:", list(ownership_map.keys()), index=0)
            ownership_type = ownership_map[selected_ownership_label]

        run_qcew = st.button("Generate QCEW Analysis", type="primary", use_container_width=True)

    with q_col2:
        if run_qcew:
            combined_qcew = []

            with st.spinner("Fetching QCEW data slices from BLS Open Data..."):
                years_to_fetch = list(range(int(start_yr_qcew), int(end_yr_qcew) + 1))
                periods_to_fetch = ["a"] if time_freq == "Annual Averages (Full Year)" else ["1", "2", "3", "4"]
                ind_codes = [str(active_dict[i]).strip() for i in selected_qcew_industries]

                for area_name in selected_qcew_areas:
                    fips = QCEW_AREAS[area_name]
                    for yr in years_to_fetch:
                        for p_code in periods_to_fetch:
                            df_slice = fetch_qcew_area_slice(yr, p_code, fips)
                            if not df_slice.empty:
                                # Ensure strict string comparison on own_code and industry_code
                                filtered_slice = df_slice[
                                    (df_slice['own_code'] == str(ownership_type)) & 
                                    (df_slice['industry_code'].isin(ind_codes))
                                ].copy()
                                
                                if not filtered_slice.empty:
                                    filtered_slice['Region'] = area_name
                                    filtered_slice['Period'] = f"{yr}" if p_code == "a" else f"{yr} Q{p_code}"
                                    combined_qcew.append(filtered_slice)

            if combined_qcew:
                qcew_df = pd.concat(combined_qcew, ignore_index=True)
                
                if metric_col in qcew_df.columns:
                    qcew_df[metric_col] = pd.to_numeric(qcew_df[metric_col], errors='coerce')

                    inv_ind_map = {v: k for k, v in active_dict.items()}
                    qcew_df['Industry_Label'] = qcew_df['industry_code'].map(inv_ind_map).fillna(qcew_df['industry_code'])

                    st.subheader(f"Results: {selected_qcew_metric}")
                    
                    focus_q_ind = st.selectbox("Filter Chart/Table by Industry:", selected_qcew_industries)
                    sub_df = qcew_df[qcew_df['Industry_Label'] == focus_q_ind]

                    if not sub_df.empty:
                        piv_table = sub_df.pivot(index="Period", columns="Region", values=metric_col)
                        
                        st.line_chart(piv_table)
                        
                        fmt_str = "${:,.2f}" if "$" in selected_qcew_metric or "pay" in metric_col or "wage" in metric_col else "{:,.0f}"
                        st.subheader(f"Data Table: {focus_q_ind}")
                        st.dataframe(piv_table.style.format(fmt_str, na_rep="N/A"), use_container_width=True)
                    else:
                        st.warning("No data returned for the specified industry/year selection.")
                else:
                    st.error(f"Selected metric '{selected_qcew_metric}' is missing from the retrieved dataset.")
            else:
                st.error("No QCEW data retrieved. Verify that data for the requested years has been published by BLS for these regions.")


