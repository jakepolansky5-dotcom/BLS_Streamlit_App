"""Labor Force & Jobs — monthly LAUS and CES series from the BLS API."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .. import blsapi
from .. import qcew
from .. import ui


def render():
    ui.header("Labor Force & Jobs (monthly)",
              "Unemployment and labor force (LAUS) and nonfarm payroll jobs (CES), more current than QCEW, "
              "plus any BLS series by ID.")
    if not blsapi.api_key():
        st.caption("No BLS API key configured: limited to 25 requests/day and 10 years per request. "
                   "See **Data Notes & Help** to add a free key.")
    source = st.segmented_control("Data", ["Unemployment & labor force (LAUS)", "Payroll jobs (CES)", "Any series ID"],
                                  default="Unemployment & labor force (LAUS)", key="lab_src") \
        or "Unemployment & labor force (LAUS)"
    this_year = date.today().year

    with st.form("lab_form"):
        if source.startswith("Unemployment"):
            geos = ui.geo_multiselect("Geographies (U.S., states, parishes, LA metros & micros)", key="lab_geos",
                                      default=["Louisiana (statewide)", "United States", "Parish · Richland Parish",
                                               "LA metro · Monroe MSA"])
            c1, c2 = st.columns(2)
            measure = c1.selectbox("Measure", list(blsapi.LAUS_MEASURES), format_func=blsapi.LAUS_MEASURES.get,
                                   key="lab_measure")
            years = c2.slider("Years", 2000, this_year, (this_year - 9, this_year), key="lab_years")
            ids = {}
            for g in geos:
                sid = blsapi.laus_id(g, measure)
                if sid:
                    ids[sid] = g.name
        elif source.startswith("Payroll"):
            geos = ui.geo_multiselect("Geographies (U.S., states, LA metros)", key="lab_ces_geos",
                                      default=["Louisiana (statewide)", "LA metro · Monroe MSA",
                                               "LA metro · Shreveport-Bossier City MSA"])
            c1, c2, c3 = st.columns(3)
            ind = c1.selectbox("Industry", list(blsapi.CES_INDUSTRIES), format_func=blsapi.CES_INDUSTRIES.get,
                               key="lab_ces_ind")
            sa = c2.toggle("Seasonally adjusted (U.S. & states)", value=True, key="lab_sa")
            years = c3.slider("Years", 2000, this_year, (this_year - 9, this_year), key="lab_ces_years")
            ids = {}
            for g in geos:
                sid = blsapi.ces_id(g, ind, sa)
                if sid:
                    ids[sid] = g.name
            st.caption("Metro series are not seasonally adjusted. Small metros often publish only "
                       "'Mining, logging, and construction' instead of separate series.")
        else:
            raw = st.text_area("Series IDs (one per line or comma-separated)",
                               value="LASST220000000000003\nSMS22000000000000001\nCUUR0000SA0", key="lab_ids")
            years = st.slider("Years", 2000, this_year, (this_year - 9, this_year), key="lab_any_years")
            ids = {s.strip().upper(): s.strip().upper() for s in raw.replace(",", "\n").splitlines() if s.strip()}
            st.caption("Find IDs with BLS Data Finder (data.bls.gov/dataQuery) or the series-ID formats in Data Notes.")
        transform = st.radio("Show", ["Level", "12-month change", "12-month % change"], horizontal=True, key="lab_tf")
        go = st.form_submit_button("📥 Fetch from BLS", type="primary", width="stretch")

    skipped = [g.name for g in (geos if source != "Any series ID" else []) if g.name not in ids.values()]
    if skipped:
        st.caption("No series of this type for: " + ", ".join(skipped))
    if not go and "lab_last" not in st.session_state:
        st.info("Choose series and press **Fetch from BLS**. Results are cached for 12 hours.")
        return
    if go:
        st.session_state["lab_last"] = (tuple(ids), years[0], years[1], ids, transform)
    sids, y0, y1, ids, transform = st.session_state["lab_last"]
    with st.spinner("Querying the BLS API…"):
        df, messages = blsapi.fetch_series(sids, y0, y1)
    for m in messages:
        if "does not exist" in m or "No Data" in m:
            st.caption("ℹ️ " + m)
        else:
            st.warning(m)
    if df.empty:
        st.warning("No data returned.")
        return
    df["name"] = df["series_id"].map(ids).fillna(df["series_id"])
    df = df.sort_values(["name", "date"])
    if transform != "Level":
        prev = df.groupby("series_id")["value"].shift(12)
        df["value"] = df["value"] - prev if transform == "12-month change" else (df["value"] / prev - 1) * 100
        df = df.dropna(subset=["value"])
    fig = px.line(df, x="date", y="value", color="name", color_discrete_map=ui.color_map(df["name"].unique().tolist()),
                  labels={"value": transform, "date": "", "name": ""})
    if transform != "Level":
        fig.add_hline(y=0, line_dash="dot", line_color="gray")
    st.plotly_chart(ui.style_fig(fig, 460), width="stretch")

    latest = df.groupby("name").tail(1)[["name", "series_id", "date", "value", "footnotes"]]
    latest["date"] = latest["date"].dt.strftime("%b %Y")
    st.dataframe(latest, hide_index=True, width="stretch",
                 column_config={"name": "Series", "series_id": "Series ID", "date": "Latest month",
                                "value": st.column_config.NumberColumn(transform, format="%.1f"),
                                "footnotes": st.column_config.TextColumn("Notes", help="P = preliminary")})
    wide = df.pivot_table(index="date", columns="name", values="value").reset_index()
    ui.download(wide, "bls_api_series", key="dl_lab")
