"""Data Notes & Help."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config as C
from .. import qcew
from .. import ui


def render():
    ui.header("Data Notes & Help", "What the numbers mean, where they come from, and their limits.")
    info = qcew.latest_periods()

    st.subheader("Sources")
    st.markdown(f"""
* **QCEW (Quarterly Census of Employment and Wages)**: a near-census of jobs covered by unemployment
  insurance (about 95% of U.S. jobs), by county, NAICS industry (down to 6 digits) and ownership. Data come
  from the BLS QCEW Open Data files at `data.bls.gov/cew/data/api`, which go back to **{info['earliest_year']}**.
  The newest quarter is **{info['quarter'].label}**, published about 5–6 months after the quarter ends.
* **LAUS (Local Area Unemployment Statistics)** and **CES (Current Employment Statistics)**: monthly
  series from the BLS Public Data API v2, shown on **Monthly Snapshot**, **Monthly Data Explorer**, Project Watch, Region Overview and Compare Regions. They are more
  current but less detailed. State data come out about three weeks after the month ends; parish and metro data
  about two weeks after that. API results are saved for 12 hours, and saved data is reused if the daily request
  limit is reached.
""")

    st.subheader("Key definitions")
    st.markdown("""
| Term | Meaning |
|---|---|
| **Employment** | Quarterly views use **third-month** employment (e.g. March for Q1), as BLS's county news release does. Annual views use the **annual average**. Monthly charts use all three months of each quarter. |
| **Avg weekly wage** | Total wages ÷ average monthly employment ÷ 13 weeks (52 for annual). Matches the published BLS figures. |
| **YoY** | Change from the same quarter a year earlier, using BLS's published over-the-year changes. |
| **Location quotient (LQ)** | (Industry share of all-ownership area jobs) ÷ (same share for the U.S.). Matches BLS's method. Above 1.25 is usually read as a specialization. |
| **Ownership** | Private, federal, state and local government. BLS publishes *All ownerships* and *Total government* only for the all-industry total, so the app adds up the component ownerships for detailed industries. |
| **Shift-share** | Splits job change into national growth, industry mix and a regional competitive effect. |
""")

    st.subheader("Confidentiality suppression")
    st.markdown("""
BLS withholds cells that could reveal an individual employer, which is common for detailed industries in small
parishes. The app **never treats a suppressed value as zero** (the original version did).

* 🔒 **Suppressed**: BLS withheld the value.
* ◐ **Partial**: a total built from several parts (parishes in a metro, or ownerships in an industry) where
  some parts are suppressed. Read it as a **minimum**.
* A suppressed detailed industry usually still shows up in its parent. If *236220 Commercial building
  construction* is hidden in Richland Parish, its jobs are still counted in *2362*, *236* and *23 Construction*.
""")

    st.subheader("Louisiana metro areas")
    st.markdown("""
Metro, micro and combined areas use the **current (2023) OMB definitions**. They are built by adding up their
parishes, which gives a consistent history back to the start of the data. BLS's own published MSA series
switched to the new definitions in 2024, which breaks earlier comparisons. The parish lists below match
BLS's published totals exactly for every quarter since 2024 Q1.
""")
    rows = []
    for table, kind in ((C.LA_METROS, "Metropolitan"), (C.LA_MICROS, "Micropolitan"), (C.LA_CSAS, "Combined")):
        for code, (name, parishes) in table.items():
            rows.append({"Area": name, "Type": kind, "BLS code": code,
                         "Parishes": ", ".join(C.LA_PARISHES.get(p, "Pearl River Co., MS").replace(" Parish", "")
                                               for p in parishes)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.subheader("Release timing")
    st.markdown("""
* QCEW county data are released quarterly. When a release lands, the app detects it within an hour, or right
  away if you press **🔄 Check for new data now** in the sidebar. That button also re-downloads the latest two
  years, because BLS revises earlier quarters of the year with each release.
* Upcoming release dates live in `RELEASE_SCHEDULE` in `bls_explorer/config.py`. Add dates there as BLS
  publishes its schedule.
""")

    st.subheader("Setup tips")
    st.markdown("""
* **BLS API key** (free, for the monthly LAUS/CES page): register at
  `https://data.bls.gov/registrationEngine/`, then create `.streamlit/secrets.toml` with
  `BLS_API_KEY = "your-key"`, or set the `BLS_API_KEY` environment variable.
* **Watchlists** you save on the Project Watch page are written to `watchlists.json` in the app folder.
  To make one permanent in the code (for example on read-only hosting), add it to `WATCHLIST_PRESETS` in
  `bls_explorer/config.py`.
* **Industry bundles** (shortcuts in industry pickers) are in `INDUSTRY_BUNDLES` in the same file.
* **Cache**: downloaded QCEW files are stored in `~/.cache/bls_explorer/qcew` (or `$BLS_EXPLORER_CACHE`),
  so repeat views are instant.
* **Series ID formats** (for the Any series ID option):
  LAUS parish `LAUCN{5-digit FIPS}00000000{03 rate|04 unemployed|05 employed|06 labor force}`;
  LAUS state `LASST{2-digit FIPS}00000000000{measure}`;
  CES state `SMS{FIPS}00000{8-digit industry}01`; CES metro `SMU22{CBSA}{8-digit industry}01`.
""")
