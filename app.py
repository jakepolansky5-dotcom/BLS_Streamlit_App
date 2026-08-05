import streamlit as st
import requests
import pandas as pd

# Set up app page title
st.set_page_config(page_title="BLS Data Explorer", layout="wide")
st.title("📈 BLS Economic Data Explorer")
st.write("Fetch real-time economic indicators directly from the Bureau of Labor Statistics.")

# Get BLS API Key securely from Streamlit secrets
BLS_API_KEY = st.secrets.get("BLS_API_KEY", "")

# Sidebar inputs
st.sidebar.header("Query Settings")
series_choice = st.sidebar.selectbox(
    "Select Economic Indicator:",
    options=["Unemployment Rate (LNS14000000)", "Consumer Price Index / CPI (CUUR0000SA0)"]
)

# Map friendly selection to actual BLS Series ID
series_id = "LNS14000000" if "Unemployment" in series_choice else "CUUR0000SA0"

start_year = st.sidebar.text_input("Start Year", "2020")
end_year = st.sidebar.text_input("End Year", "2024")

if st.sidebar.button("Fetch Data"):
    if not BLS_API_KEY:
        st.error("Missing BLS API Key! Please set it in your Streamlit secrets.")
    else:
        with st.spinner("Fetching data from BLS..."):
            url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
            payload = {
                "seriesid": [series_id],
                "startyear": start_year,
                "endyear": end_year,
                "registrationkey": BLS_API_KEY
            }
            
            response = requests.post(url, json=payload)
            data = response.json()
            
            if data.get("status") == "REQUEST_SUCCEEDED" and data['Results']['series'][0]['data']:
                # Extract records
                records = data['Results']['series'][0]['data']
                df = pd.DataFrame(records)
                
                # Clean up date column and numerical values
                df['Value'] = pd.to_numeric(df['value'])
                df['Date'] = pd.to_datetime(df['year'] + '-' + df['period'].str.replace('M', ''))
                df = df.sort_values('Date').reset_index(drop=True)
                
                # Display line chart
                st.subheader(f"Trend for Series: {series_id}")
                st.line_chart(df, x="Date", y="Value")
                
                # Display data table
                st.subheader("Raw Data Table")
                st.dataframe(df[['year', 'periodName', 'value']], use_container_width=True)
            else:
                st.error("Failed to retrieve data. Check your series ID and date range.")
