import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as io
import requests
import io
import re

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Louisiana Economic Data Explorer (QCEW)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# REFERENCE DICTIONARIES & METADATA
# ==========================================

# Comprehensive 64 Louisiana Parish FIPS Code Dictionary
LA_PARISH_FIPS = {
    "Statewide (Louisiana Total)": "22000",
    "Acadia Parish": "22001", "Allen Parish": "22003", "Ascension Parish": "22005",
    "Assumption Parish": "22007", "Avoyelles Parish": "22009", "Beauregard Parish": "22011",
    "Bienville Parish": "22013", "Bossier Parish": "22015", "Caddo Parish": "22017",
    "Calcasieu Parish": "22019", "Caldwell Parish": "22021", "Cameron Parish": "22023",
    "Catahoula Parish": "22025", "Claiborne Parish": "22027", "Concordia Parish": "22029",
    "DeSoto Parish": "22031", "East Baton Rouge Parish": "22033", "East Carroll Parish": "22035",
    "East Feliciana Parish": "22037", "Evangeline Parish": "22039",
    "Franklin Parish": "22041", "Grant Parish": "22043", "Iberia Parish": "22045",
    "Iberville Parish": "22047", "Jackson Parish": "22049", "Jefferson Parish": "22051",
    "Jefferson Davis Parish": "22053", "Lafayette Parish": "22055",
    "Lafourche Parish": "22057", "LaSalle Parish": "22059", "Lincoln Parish": "22061",
    "Livingston Parish": "22063", "Madison Parish": "22065", "Morehouse Parish": "22067",
    "Natchitoches Parish": "22069", "Orleans Parish": "22071", "Ouachita Parish": "22073", "Plaquemines Parish": "22075", "Pointe Coupee Parish": "22077",
    "Rapides Parish": "22079", "Red River Parish": "22081", "Richland Parish": "22083",
    "Sabine Parish": "22085", "St. Bernard Parish": "22087", "St. Charles Parish": "22089",
    "St. Helena Parish": "22091", "St. James Parish": "22093", "St. John the Baptist Parish": "22095",
    "St. Landry Parish": "22097", "St. Martin Parish": "22099", "St. Mary Parish": "22101",
    "St. Tammany Parish": "22103", "Tangipahoa Parish": "22105", "Tensas Parish": "22107",
    "Terrebonne Parish": "22109", "Union Parish": "22111", "Vermilion Parish": "22113",
    "Vernon Parish": "22115", "Washington Parish": "22117", "Webster Parish": "22119",
    "West Baton Rouge Parish": "22121", "West Carroll Parish": "22123", "West Feliciana Parish": "22125",
    "Winn Parish": "22127"
}
    
# Here is the complete, regenerated Python code for the **Louisiana Economic Data Explorer** Streamlit application.

# It incorporates all 64 Louisiana parish FIPS codes, complete 6-digit NAICS industry hierarchy support, corrected QCEW ownership mapping, and the updated multi-tab analytical layout.

```python
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ==============================================================================
# 1. APPLICATION CONFIGURATION & STYLING
# ==============================================================================
st.set_page_config(
    page_title="Louisiana Economic Data Explorer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished metrics and visual aesthetic
st.markdown("""
<style>
    .main-header {
        font-size: 2.25rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F172A;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. REFERENCE DICTIONARIES & MAPPINGS
# ==============================================================================

# Complete 64 Louisiana Parishes (FIPS State Code: 22)
LA_PARISH_FIPS = {
    "Statewide (Louisiana Total)": "22000",
    "Acadia Parish": "22001", "Allen Parish": "22003", "Ascension Parish": "22005",
    "Assumption Parish": "22007", "Avoyelles Parish": "22009", "Beauregard Parish": "22011",
    "Bienville Parish": "22013", "Bossier Parish": "22015", "Caddo Parish": "22017",
    "Calcasieu Parish": "22019", "Caldwell Parish": "22021", "Cameron Parish": "22023",
    "Catahoula Parish": "22025", "Claiborne Parish": "22027", "Concordia Parish": "22029",
    "DeSoto Parish": "22031", "East Baton Rouge Parish": "22033", "East Carroll Parish": "22035",
    "East Feliciana Parish": "22037", "Evangeline Parish": "22039", "Franklin Parish": "22041",
    "Grant Parish": "22043", "Iberia Parish": "22045", "Iberville Parish": "22047",
    "Jackson Parish": "22049", "Jefferson Parish": "22051", "Jefferson Davis Parish": "22053",
    "Lafayette Parish": "22055", "Lafourche Parish": "22057", "LaSalle Parish": "22059",
    "Lincoln Parish": "22061", "Livingston Parish": "22063", "Madison Parish": "22065",
    "Morehouse Parish": "22067", "Natchitoches Parish": "22069", "Orleans Parish": "22071",
    "Ouachita Parish": "22073", "Plaquemines Parish": "22075", "Pointe Coupee Parish": "22077",
    "Rapides Parish": "22079", "Red River Parish": "22081", "Richland Parish": "22083",
    "Sabine Parish": "22085", "St. Bernard Parish": "22087", "St. Charles Parish": "22089",
    "St. Helena Parish": "22091", "St. James Parish": "22093", "St. John the Baptist Parish": "22095",
    "St. Landry Parish": "22097", "St. Martin Parish": "22099", "St. Mary Parish": "22101",
    "St. Tammany Parish": "22103", "Tangipahoa Parish": "22105", "Tensas Parish": "22107",
    "Terrebonne Parish": "22109", "Union Parish": "22111", "Vermilion Parish": "22113",
    "Vernon Parish": "22115", "Washington Parish": "22117", "Webster Parish": "22119",
    "West Baton Rouge Parish": "22121", "West Carroll Parish": "22123", "West Feliciana Parish": "22125",
    "Winn Parish": "22127"
}

# QCEW Ownership Code Mapping
QCEW_OWNERSHIP_MAP = {
    "0": "Total Covered (All Ownerships)",
    "1": "Federal Government",
    "2": "State Government",
    "3": "Local Government",
    "4": "International Government",
    "5": "Private Sector",
    "8": "Total Covered (Excl. Federal)"
}

# Standard NAICS 2-Digit Sectors
NAICS_2DIGIT = {
    "10": "Total, All Industries",
    "11": "Agriculture, Forestry, Fishing and Hunting",
    "21": "Mining, Quarrying, and Oil and Gas Extraction",
    "22": "Utilities",
    "23": "Construction",
    "31-33": "Manufacturing",
    "42": "Wholesale Trade",
    "44-45": "Retail Trade",
    "48-49": "Transportation and Warehousing",
    "51": "Information",
    "52": "Finance and Insurance",
    "53": "Real Estate and Rental and Leasing",
    "54": "Professional, Scientific, and Technical Services",
    "55": "Management of Companies and Enterprises",
    "56": "Administrative and Support and Waste Management",
    "61": "Educational Services",
    "62": "Health Care and Social Assistance",
    "71": "Arts, Entertainment, and Recreation",
    "72": "Accommodation and Food Services",
    "81": "Other Services (except Public Administration)",
    "92": "Public Administration"
}

# Expanded NAICS Codes (Including common 3 to 6-digit codes relevant to LA economy)
NAICS_HIERARCHY = {
    "10": "10 - Total, All Industries",
    "21": "21 - Mining, Quarrying, and Oil & Gas Extraction",
    "211": "211 - Oil and Gas Extraction",
    "2111": "2111 - Oil and Gas Extraction (Group)",
    "21112": "21112 - Crude Petroleum Extraction",
    "21113": "21113 - Natural Gas Extraction",
    "213111": "213111 - Drilling Oil and Gas Wells",
    "213112": "213112 - Support Activities for Oil and Gas Operations",
    "23": "23 - Construction",
    "237120": "237120 - Oil and Gas Pipeline Construction",
    "31-33": "31-33 - Manufacturing",
    "324": "324 - Petroleum and Coal Products Manufacturing",
    "324110": "324110 - Petroleum Refineries",
    "325": "325 - Chemical Manufacturing",
    "325110": "325110 - Petrochemical Manufacturing",
    "48-49": "48-49 - Transportation and Warehousing",
    "486": "486 - Pipeline Transportation",
    "486110": "486110 - Pipeline Transportation of Crude Oil",
    "486210": "486210 - Pipeline Transportation of Natural Gas",
    "62": "62 - Health Care and Social Assistance",
    "622110": "622110 - General Medical and Surgical Hospitals",
    "72": "72 - Accommodation and Food Services",
    "721110": "721110 - Hotels and Motels",
    "722511": "722511 - Full-Service Restaurants"
}

# ==============================================================================
# 3. DATA FETCHING & CACHING PIPELINE (QCEW API)
# ==============================================================================

@st.cache_data(ttl=86400)
def fetch_qcew_area_data(year: int, quarter: str, fips_code: str) -> pd.DataFrame:
    """
    Fetches QCEW data from BLS API by Area (State/Parish), Year, and Quarter.
    API Docs: [https://www.bls.gov/cew/about-data/downloadable-files-api.htm](https://www.bls.gov/cew/about-data/downloadable-files-api.htm)
    """
    url = f"[https://data.bls.gov/cew/data/api/](https://data.bls.gov/cew/data/api/){year}/{quarter}/area/{fips_code}.csv"
    try:
        df = pd.read_csv(url, dtype=str)
        # Standardize numeric columns
        numeric_cols = [
            'month1_emplvl', 'month2_emplvl', 'month3_emplvl',
            'total_qtrly_wages', 'taxable_qtrly_wages', 'qtrly_contributions',
            'avg_wkly_wage', 'lq_avg_wkly_wage', 'lq_month3_emplvl'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error fetching data for FIPS {fips_code}, {year} Q{quarter}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def fetch_qcew_industry_data(year: int, quarter: str, industry_code: str) -> pd.DataFrame:
    """
    Fetches QCEW data across all areas for a specific industry code.
    """
    url = f"[https://data.bls.gov/cew/data/api/](https://data.bls.gov/cew/data/api/){year}/{quarter}/industry/{industry_code}.csv"
    try:
        df = pd.read_csv(url, dtype=str)
        numeric_cols = ['month3_emplvl', 'total_qtrly_wages', 'avg_wkly_wage']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].str.replace(',', ''), errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

# ==============================================================================
# 4. SIDEBAR CONTROLS & FILTER SELECTION
# ==============================================================================

st.sidebar.title("🔍 Explorer Controls")

# Year & Quarter Selection
current_year = datetime.now().year
selected_year = st.sidebar.selectbox("Select Year", list(range(current_year - 1, 2014, -1)), index=1)
selected_quarter = st.sidebar.selectbox("Select Quarter", ["1", "2", "3", "4"], index=0)

# Parish Selection
selected_parish_name = st.sidebar.selectbox(
    "Select Location", 
    options=list(LA_PARISH_FIPS.keys()),
    index=0
)
selected_fips = LA_PARISH_FIPS[selected_parish_name]

# NAICS Selection / Search
industry_option_type = st.sidebar.radio("Industry Selection Mode", ["Standard Sectors (2-Digit)", "Detailed Hierarchy (2-6 Digit)"])

if industry_option_type == "Standard Sectors (2-Digit)":
    selected_naics = st.sidebar.selectbox(
        "Select NAICS Sector",
        options=list(NAICS_2DIGIT.keys()),
        format_func=lambda x: f"{x} - {NAICS_2DIGIT[x]}"
    )
else:
    custom_naics = st.sidebar.text_input("Enter NAICS Code (e.g., 21112, 324110)", value="211")
    selected_naics = custom_naics.strip()

# Ownership Selection
selected_own = st.sidebar.selectbox(
    "Ownership Type",
    options=list(QCEW_OWNERSHIP_MAP.keys()),
    format_func=lambda x: f"{x} - {QCEW_OWNERSHIP_MAP[x]}",
    index=0
)

# Fetch Main Area Dataset
with st.spinner("Fetching QCEW economic data..."):
    df_area = fetch_qcew_area_data(selected_year, selected_quarter, selected_fips)

# ==============================================================================
# 5. MAIN HEADER & SUMMARY METRICS
# ==============================================================================

st.markdown('<div class="main-header">Louisiana Economic Data Explorer</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-header">Quarterly Census of Employment and Wages (QCEW) | {selected_parish_name} | {selected_year} Q{selected_quarter}</div>', unsafe_allow_html=True)

if df_area.empty:
    st.warning("⚠️ No data available for the selected parameters. QCEW data is typically released with a 5-6 month lag.")
    st.stop()

# Filter area dataframe by ownership if specified (0 or 5 are most common)
if selected_own != "0":
    df_filtered_own = df_area[df_area['own_code'] == selected_own]
else:
    df_filtered_own = df_area.copy()

# Calculate Aggregate Metrics (Total across area)
total_row = df_filtered_own[df_filtered_own['industry_code'] == '10']

if not total_row.empty:
    total_emp = int(total_row['month3_emplvl'].values[0])
    total_wages = float(total_row['total_qtrly_wages'].values[0])
    avg_weekly_wage = float(total_row['avg_wkly_wage'].values[0])
else:
    total_emp = df_filtered_own['month3_emplvl'].sum()
    total_wages = df_filtered_own['total_qtrly_wages'].sum()
    avg_weekly_wage = (total_wages / total_emp / 13) if total_emp > 0 else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_emp:,.0f}</div><div class="metric-label">Total Employment (Month 3)</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-value">${total_wages / 1e6:,.2f}M</div><div class="metric-label">Total Quarterly Wages</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-value">${avg_weekly_wage:,.0f}</div><div class="metric-label">Avg Weekly Wage</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{selected_year} Q{selected_quarter}</div><div class="metric-label">Reporting Period</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# 6. TABBED DETAILED ANALYSIS
# ==============================================================================

tab1, tab2, tab3 = st.tabs([
    "📊 Tab 1: Industry Breakdown & Deep Dive",
    "🗺️ Tab 2: Parish / Geographic Explorer",
    "📈 Tab 3: Comparative Analysis & Benchmarking"
])

# ------------------------------------------------------------------------------
# TAB 1: INDUSTRY BREAKDOWN & DEEP DIVE
# ------------------------------------------------------------------------------
with tab1:
    st.subheader(f"Industry Breakdown for {selected_parish_name}")
    
    # Filter for 2-digit major sectors for overview visualization
    df_sectors = df_filtered_own[
        (df_filtered_own['industry_code'].isin(NAICS_2DIGIT.keys())) & 
        (df_filtered_own['industry_code'] != '10')
    ].copy()
    
    df_sectors['industry_title'] = df_sectors['industry_code'].map(NAICS_2DIGIT)
    
    col_t1_left, col_t1_right = st.columns([6, 4])
    
    with col_t1_left:
        st.markdown("#### Top Sectors by Employment")
        if not df_sectors.empty:
            fig_emp = px.bar(
                df_sectors.sort_values(by='month3_emplvl', ascending=True).tail(10),
                x='month3_emplvl',
                y='industry_title',
                orientation='h',
                labels={'month3_emplvl': 'Employment (Month 3)', 'industry_title': 'Sector'},
                color='avg_wkly_wage',
                color_continuous_scale='Blues',
                title="Employment & Avg Weekly Wage by Top Sectors"
            )
            fig_emp.update_layout(height=450, margin=dict(l=0, r=20, t=40, b=0))
            st.plotly_chart(fig_emp, use_container_width=True)
        else:
            st.info("No 2-digit sector data returned for this selection.")

    with col_t1_right:
        st.markdown("#### Selected Code Target Detail")
        selected_ind_data = df_filtered_own[df_filtered_own['industry_code'] == selected_naics]
        
        if not selected_ind_data.empty:
            row = selected_ind_data.iloc[0]
            st.markdown(f"**NAICS Code:** `{selected_naics}`")
            st.markdown(f"**Ownership:** {QCEW_OWNERSHIP_MAP.get(str(row.get('own_code', '0')), 'Other')}")
            st.markdown(f"**Establishment Count:** {int(row.get('qtrly_estabs', 0)):,}")
            st.markdown(f"**Month 3 Employment:** {int(row.get('month3_emplvl', 0)):,}")
            st.markdown(f"**Total Quarterly Wages:** ${float(row.get('total_qtrly_wages', 0)):,.2f}")
            st.markdown(f"**Avg Weekly Wage:** ${float(row.get('avg_wkly_wage', 0)):,.2f}")
            
            lq = float(row.get('lq_month3_emplvl', 0))
            if lq > 0:
                st.markdown(f"**Location Quotient (LQ):** `{lq:.2f}`")
                if lq > 1.2:
                    st.success("High Concentration (Export-oriented sector)")
                elif lq < 0.8:
                    st.info("Low Concentration relative to national baseline")
        else:
            st.warning(f"No specific entry found for NAICS `{selected_naics}` in {selected_parish_name}.")

    # Full Data Table Display
    st.markdown("#### Data Table: Industry Records")
    display_cols = ['industry_code', 'own_code', 'qtrly_estabs', 'month1_emplvl', 'month2_emplvl', 'month3_emplvl', 'total_qtrly_wages', 'avg_wkly_wage']
    valid_cols = [c for c in display_cols if c in df_filtered_own.columns]
    st.dataframe(df_filtered_own[valid_cols].sort_values(by='month3_emplvl', ascending=False), use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 2: PARISH / GEOGRAPHIC EXPLORER
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("Geographic Cross-Parish Comparison")
    st.markdown(f"Analyzing NAICS Industry Code: **`{selected_naics}`** across all 64 Louisiana Parishes.")
    
    with st.spinner(f"Fetching statewide data for NAICS {selected_naics}..."):
        df_ind_statewide = fetch_qcew_industry_data(selected_year, selected_quarter, selected_naics)
    
    if not df_ind_statewide.empty:
        # Filter for Louisiana FIPS codes (22001 - 22127)
        la_fips_list = [v for k, v in LA_PARISH_FIPS.items() if k != "Statewide (Louisiana Total)"]
        df_la_parishes = df_ind_statewide[df_ind_statewide['area_fips'].isin(la_fips_list)].copy()
        
        # Map FIPS to Parish Name
        fips_to_name = {v: k for k, v in LA_PARISH_FIPS.items()}
        df_la_parishes['parish_name'] = df_la_parishes['area_fips'].map(fips_to_name)
        
        col_t2_left, col_t2_right = st.columns([6, 4])
        
        with col_t2_left:
            st.markdown(f"#### Top Parishes for NAICS {selected_naics}")
            top_parishes = df_la_parishes.sort_values(by='month3_emplvl', ascending=False).head(15)
            
            fig_parish = px.bar(
                top_parishes,
                x='month3_emplvl',
                y='parish_name',
                orientation='h',
                color='avg_wkly_wage',
                labels={'month3_emplvl': 'Employment', 'parish_name': 'Parish'},
                title=f"Top Parishes by Employment (NAICS {selected_naics})"
            )
            fig_parish.update_layout(yaxis={'categoryorder': 'total ascending'}, height=480)
            st.plotly_chart(fig_parish, use_container_width=True)
            
        with col_t2_right:
            st.markdown("#### Parish Summary Table")
            summary_df = df_la_parishes[['parish_name', 'month3_emplvl', 'total_qtrly_wages', 'avg_wkly_wage']].sort_values(
                by='month3_emplvl', ascending=False
            )
            st.dataframe(summary_df, height=450, use_container_width=True)
    else:
        st.info("No cross-parish data returned for this NAICS code.")

# ------------------------------------------------------------------------------
# TAB 3: COMPARATIVE ANALYSIS & BENCHMARKING
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("Comparative Analysis & Multi-Year Benchmarking")
    
    col_t3_1, col_t3_2 = st.columns(2)
    with col_t3_1:
        benchmark_parish = st.selectbox(
            "Select Benchmark Location",
            options=[k for k in LA_PARISH_FIPS.keys() if k != selected_parish_name],
            index=0
        )
        benchmark_fips = LA_PARISH_FIPS[benchmark_parish]
    
    with col_t3_2:
        compare_year = st.selectbox("Select Benchmark Year", list(range(current_year - 1, 2014, -1)), index=2)
    
    with st.spinner("Loading comparative datasets..."):
        df_bench_area = fetch_qcew_area_data(selected_year, selected_quarter, benchmark_fips)
        df_hist_area = fetch_qcew_area_data(compare_year, selected_quarter, selected_fips)
    
    # Primary Metrics Comparison
    st.markdown("#### Current vs. Benchmark Comparison")
    
    def get_naics_metrics(df_source, naics):
        row = df_source[df_source['industry_code'] == naics]
        if not row.empty:
            return {
                'emp': int(row['month3_emplvl'].values[0]),
                'wages': float(row['total_qtrly_wages'].values[0]),
                'avg_weekly': float(row['avg_wkly_wage'].values[0])
            }
        return {'emp': 0, 'wages': 0.0, 'avg_weekly': 0.0}

    curr_metrics = get_naics_metrics(df_area, selected_naics)
    bench_metrics = get_naics_metrics(df_bench_area, selected_naics)
    hist_metrics = get_naics_metrics(df_hist_area, selected_naics)
    
    comp_df = pd.DataFrame([
        {"Metric": "Employment (Month 3)", f"{selected_parish_name} ({selected_year})": f"{curr_metrics['emp']:,}", f"{benchmark_parish} ({selected_year})": f"{bench_metrics['emp']:,}", f"{selected_parish_name} ({compare_year})": f"{hist_metrics['emp']:,}"},
        {"Metric": "Total Wages", f"{selected_parish_name} ({selected_year})": f"${curr_metrics['wages']:,.2f}", f"{benchmark_parish} ({selected_year})": f"${bench_metrics['wages']:,.2f}", f"{selected_parish_name} ({compare_year})": f"${hist_metrics['wages']:,.2f}"},
        {"Metric": "Avg Weekly Wage", f"{selected_parish_name} ({selected_year})": f"${curr_metrics['avg_weekly']:,.0f}", f"{benchmark_parish} ({selected_year})": f"${bench_metrics['avg_weekly']:,.0f}", f"{selected_parish_name} ({compare_year})": f"${hist_metrics['avg_weekly']:,.0f}"}
    ])
    
    st.table(comp_df)

# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("---")
st.markdown("💡 **Data Source:** U.S. Bureau of Labor Statistics (BLS) Quarterly Census of Employment and Wages (QCEW) Open API.")
