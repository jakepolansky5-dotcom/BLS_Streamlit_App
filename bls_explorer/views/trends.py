"""Trend Builder — build any QCEW time series (monthly, quarterly or annual)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .. import config as C
from .. import geo as G
from .. import qcew
from .. import ui

SERIES_METRICS = {
    "emp": "Employment",
    "estabs": "Establishments",
    "wages": "Total wages",
    "avg_wkly_wage": "Avg weekly wage",
}
TRANSFORMS = ["Level", "Index (start = 100)", "Change since start", "YoY change", "YoY %"]


def render():
    ui.header("Trend Builder",
              "Monthly, quarterly or annual QCEW series for any mix of geographies and industries, back to "
              f"{qcew.latest_periods()['earliest_year']}.")
    ui.custom_region_builder("tb")
    info = qcew.latest_periods()
    with st.form("tb_form", border=True):
        c1, c2 = st.columns(2)
        with c1:
            geos = ui.geo_multiselect("Geographies", key="tb_geos",
                                      default=["Watchlist · North LA data center (Richland Parish & neighbors)",
                                               "LA metro · Monroe MSA"])
            split = st.checkbox("Also show each parish inside regions/metros", key="tb_split")
        with c2:
            inds = ui.industry_multiselect("Industries", key="tb_inds", default=["10", "23"], bundle_picker=False)
            own = ui.ownership_select("tb_own", default="5")
        c3, c4, c5, c6 = st.columns(4)
        freq = c3.radio("Frequency", ["Monthly", "Quarterly", "Annual"], key="tb_freq", horizontal=True)
        metric = c4.selectbox("Metric", list(SERIES_METRICS), format_func=SERIES_METRICS.get, key="tb_metric",
                              help="Monthly frequency is available for employment only.")
        transform = c5.selectbox("Transform", TRANSFORMS, key="tb_transform")
        years = c6.slider("Years", info["earliest_year"], info["quarter"].year,
                          (max(info["earliest_year"], info["quarter"].year - 5), info["quarter"].year), key="tb_years")
        submitted = st.form_submit_button("📊 Build chart", type="primary", width="stretch")

    if not geos or not inds:
        st.info("Choose at least one geography and one industry, then press **Build chart**.")
        return
    if not submitted and "tb_ready" not in st.session_state:
        st.info("Adjust the settings above and press **Build chart**.")
        return
    st.session_state["tb_ready"] = True

    if split:
        extra = []
        for g in geos:
            if g.is_composite:
                extra += [G.county(c) for c in g.codes if G.county(c) not in geos]
        geos = geos + list(dict.fromkeys(extra))
    if freq == "Annual":
        periods = qcew.annual_range(years[0], min(years[1], info["annual"].year))
    else:
        periods = qcew.quarter_range(qcew.Period(years[0], "1"), min(qcew.Period(years[1], "4"), info["quarter"]))
    if freq == "Monthly" and metric != "emp":
        st.warning("Monthly values exist only for employment; showing quarterly values instead.")
        freq = "Quarterly"
    n_files = len(periods) * min(len(inds) + 1, sum(len(g.codes) for g in geos))
    if n_files > 400:
        st.caption(f"≈{n_files} files on first load — this can take a minute; afterwards it is cached.")

    df = ui.load(geos, periods, inds, own)
    if df.empty:
        st.warning("No data returned.")
        return
    df = df[df["industry_code"].isin(inds)].copy()
    df["industry"] = df["industry_code"].map(qcew.industry_label)

    if freq == "Monthly":
        d = qcew.monthly(df)
        d["industry"] = d["industry_code"].map(qcew.industry_label)
        d["value"] = d["emp"]
        d["yoy"] = d["emp_chg"]
        xcol = "date"
    else:
        d = df.copy()
        d["value"] = d[metric]
        d["yoy"] = d[{"emp": "emp_chg", "estabs": "estabs_chg", "wages": "wages_chg"}.get(metric, "emp_chg")] \
            if metric != "avg_wkly_wage" else np.nan
        xcol = "date" if freq == "Quarterly" else "year"
    d = d.sort_values(["geo", "industry", xcol])
    grp = d.groupby(["geo", "industry"])["value"]
    first = grp.transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
    if transform == "Index (start = 100)":
        d["plot"] = d["value"] / first * 100
    elif transform == "Change since start":
        d["plot"] = d["value"] - first
    elif transform == "YoY change":
        d["plot"] = d["yoy"] if metric != "avg_wkly_wage" else d["value"] - grp.shift(4 if freq == "Quarterly" else 1)
    elif transform == "YoY %":
        if metric == "avg_wkly_wage":
            d["plot"] = d["wage_pct"]
        else:
            prev = d["value"] - d["yoy"]
            d["plot"] = np.where(prev > 0, d["yoy"] / prev * 100, np.nan)
    else:
        d["plot"] = d["value"]

    multi_geo, multi_ind = d["geo"].nunique() > 1, d["industry"].nunique() > 1
    if multi_geo and multi_ind:
        d["series"] = d["geo"] + " · " + d["industry"].str.split(" – ").str[-1]
    elif multi_ind:
        d["series"] = d["industry"]
    else:
        d["series"] = d["geo"]
    facet = None
    if multi_geo and multi_ind and st.toggle("One panel per industry", value=d["industry"].nunique() <= 4, key="tb_facet"):
        facet, d["series"] = "industry", d["geo"]

    ylab = f"{SERIES_METRICS[metric]} — {transform}"
    fig = px.line(d, x=xcol, y="plot", color="series", facet_row=facet, markers=freq != "Monthly",
                  color_discrete_map=ui.color_map(d["series"].unique().tolist()),
                  labels={"plot": ylab, xcol: "", "series": ""})
    if facet:
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_yaxes(matches=None)
    if transform.startswith(("YoY", "Change")):
        fig.add_hline(y=0, line_color="gray", line_dash="dot")
    fig.update_layout(title=f"{SERIES_METRICS[metric]} · {C.OWNERSHIPS[own]} · {freq.lower()}")
    st.plotly_chart(ui.style_fig(fig, height=480 if not facet else 260 * d["industry"].nunique()),
                    width="stretch")

    sup = d[d["status"].isin(["Suppressed", "Partial"])]
    if not sup.empty:
        st.caption(f"⚠️ {len(sup)} data points are suppressed or partial; gaps in lines are suppressed values.")
        ui.suppression_note()

    st.subheader("Data")
    label_col = "date" if freq != "Annual" else "year"
    tbl = d.copy()
    tbl["when"] = tbl["date"].dt.strftime("%Y-%m") if freq == "Monthly" else (tbl["period"] if freq == "Quarterly" else tbl["year"])
    pivot = tbl.pivot_table(index="series", columns="when", values="plot", aggfunc="first")
    st.dataframe(pivot, width="stretch")
    keep = [c for c in ["geo", "industry_code", "industry", "year", "qtr", "date", "value", "plot", "status"] if c in tbl]
    ui.download(tbl[keep].rename(columns={"value": metric, "plot": transform}), f"trend_{metric}_{freq.lower()}",
                key="dl_tb")
