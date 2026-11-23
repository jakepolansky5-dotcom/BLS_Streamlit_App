"""Monthly Data Explorer — LAUS and CES series for any mix of regions, measures and industries."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .. import blsapi
from .. import monthly_data as md
from .. import ui

TRANSFORMS = ["Level", "Index (start = 100)", "12-month change", "12-month % change"]
LAUS_COLS = {"rate": "Unemployment rate (%)", "labor_force": "Labor force", "employed": "Employed residents",
             "unemployed": "Unemployed"}


def _transform(d: pd.DataFrame, value: str, groups: list[str], how: str) -> pd.DataFrame:
    d = d.sort_values([*groups, "date"]).copy()
    g = d.groupby(groups)[value]
    if how == "Index (start = 100)":
        d["plot"] = d[value] / g.transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan) * 100
    elif how == "12-month change":
        prev = d.set_index([*groups, "date"])[value]
        key = list(zip(*[d[c] for c in groups], d["date"] - pd.DateOffset(years=1)))
        d["plot"] = d[value].to_numpy() - prev.reindex(key).to_numpy()
    elif how == "12-month % change":
        prev = d.set_index([*groups, "date"])[value]
        key = list(zip(*[d[c] for c in groups], d["date"] - pd.DateOffset(years=1)))
        p = prev.reindex(key).to_numpy()
        d["plot"] = np.where(p > 0, (d[value].to_numpy() / p - 1) * 100, np.nan)
    else:
        d["plot"] = d[value]
    return d


def _chart(d, color, facet, ylab, title, n_facets):
    fig = px.line(d, x="date", y="plot", color=color, facet_row=facet if n_facets > 1 else None,
                  color_discrete_map=ui.color_map(d[color].unique().tolist()), labels={"plot": ylab, "date": "", color: ""})
    if n_facets > 1:
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_yaxes(matches=None, title_text="")
    fig.update_layout(title=title)
    st.plotly_chart(ui.style_fig(fig, height=460 if n_facets <= 1 else 240 * n_facets + 80), width="stretch")


def render():
    ui.header("Monthly Data Explorer",
              "Monthly BLS data for any mix of regions: unemployment and labor force (LAUS) and payroll jobs by "
              "industry (CES). Use QCEW pages for parish-level industry detail.")
    if not blsapi.api_key():
        st.caption("No BLS API key configured: limited to 25 requests/day. See Data Notes & Help to add one.")
    source = st.segmented_control("Data", ["Payroll jobs (CES)", "Unemployment & labor force (LAUS)", "Any series ID"],
                                  default="Payroll jobs (CES)", key="lab_src") or "Payroll jobs (CES)"
    this_year = date.today().year
    max_years = 20 if blsapi.api_key() else 10

    if source.startswith("Payroll"):
        _ces(this_year, max_years)
    elif source.startswith("Unemployment"):
        _laus(this_year, max_years)
    else:
        _any(this_year)


def _ces(this_year, max_years):
    with st.form("ces_form"):
        c1, c2 = st.columns(2)
        with c1:
            geos = ui.geo_multiselect("Regions (U.S., states, Louisiana metros)", key="ces_geos",
                                      default=["Louisiana (statewide)", "United States", "LA metro · Monroe MSA",
                                               "LA metro · Baton Rouge MSA", "State · Texas"])
        with c2:
            inds = st.multiselect("Industries", list(blsapi.CES_INDUSTRIES), format_func=blsapi.CES_INDUSTRIES.get,
                                  default=["00000000", "20000000", "30000000", "65000000"], key="ces_inds")
        c3, c4, c5 = st.columns(3)
        years = c3.slider("Years", 2000, this_year, (this_year - 6, this_year), key="ces_years")
        how = c4.selectbox("Show", TRANSFORMS, index=3, key="ces_how")
        color_by = c5.radio("Color lines by", ["Region", "Industry"], horizontal=True, key="ces_color")
        go = st.form_submit_button("📥 Load payroll jobs", type="primary", width="stretch")
    skipped = [g.name for g in geos if not md.ces_plan(g)]
    if skipped:
        st.caption("Monthly payroll jobs aren't published for: " + ", ".join(skipped)
                   + ". (CES covers the U.S., states and metro areas; use QCEW pages for parishes.)")
    if not go and "ces_loaded" not in st.session_state:
        st.info("Pick regions and industries, then press **Load payroll jobs**. States and the U.S. are seasonally "
                "adjusted; metros are not.")
        return
    st.session_state["ces_loaded"] = True
    if not geos or not inds:
        st.warning("Choose at least one region and one industry.")
        return
    span = min(years[1] - years[0], max_years - 1) + 1
    with st.spinner("Querying the BLS API…"):
        df, msgs = md.ces_series(geos, inds, years=span + 1)
    md.show_messages(msgs)
    if df.empty:
        st.warning("No data returned.")
        return
    df = df[df["date"].dt.year >= years[0]]
    missing = [(g.name, blsapi.CES_INDUSTRIES[i]) for g in geos for i in inds
               if md.ces_plan(g, [i]) and not ((df["geo_key"] == g.key) & (df["industry_code"] == i)).any()]

    d = _transform(df, "jobs", ["geo", "industry"], how)
    if how == "12-month change" or how == "12-month % change":
        d = d.dropna(subset=["plot"])
    color, facet = ("geo", "industry") if color_by == "Region" else ("industry", "geo")
    ylab = {"Level": "Payroll jobs", "Index (start = 100)": "Index", "12-month change": "Jobs vs. a year earlier",
            "12-month % change": "% change vs. a year earlier"}[how]
    _chart(d, color, facet, ylab, f"Payroll jobs (CES) · {how}", d[facet].nunique())

    lt = md.latest(df, "jobs", ["geo", "industry"])
    a, b = st.columns([3, 2])
    with a:
        piv = lt.pivot_table(index="industry", columns="geo", values="yoy_pct")
        piv = piv.reindex(index=[blsapi.CES_INDUSTRIES[i] for i in inds if blsapi.CES_INDUSTRIES[i] in piv.index],
                          columns=[g.name for g in geos if g.name in piv.columns])
        lim = float(np.nanmax(np.abs(piv.to_numpy()))) if piv.notna().any().any() else 1
        fig = px.imshow(piv, text_auto="+.1f", aspect="auto", color_continuous_scale="RdBu", zmin=-lim, zmax=lim,
                        labels=dict(color="YoY %"))
        fig.update_layout(title="Latest month: job growth vs. a year earlier (%)", xaxis_title="", yaxis_title="")
        st.plotly_chart(ui.style_fig(fig, max(300, 60 * len(piv) + 140), legend=False), width="stretch")
    with b:
        st.dataframe(lt[["geo", "industry", "date", "value", "mom", "yoy", "yoy_pct"]], hide_index=True,
                     width="stretch", height=max(300, 60 * len(piv) + 140),
                     column_config={"geo": "Region", "industry": "Industry",
                                    "date": st.column_config.DateColumn("Month", format="MMM YYYY"),
                                    "value": st.column_config.NumberColumn("Jobs", format="localized"),
                                    "mom": st.column_config.NumberColumn("vs prior month", format="%+d"),
                                    "yoy": st.column_config.NumberColumn("YoY", format="%+d"),
                                    "yoy_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%")})
    if missing:
        st.caption("Not published by BLS: " + "; ".join(f"{g} – {i}" for g, i in missing)
                   + ". Small metros often report only 'Mining, logging, and construction'.")
    ui.download(d[["geo", "industry", "date", "jobs", "plot", "prelim"]].rename(columns={"plot": how}),
                "ces_payroll_jobs", key="dl_ces")


def _laus(this_year, max_years):
    with st.form("laus_form"):
        c1, c2 = st.columns(2)
        with c1:
            geos = ui.geo_multiselect("Regions (U.S., states, parishes, metros, custom regions)", key="laus_geos",
                                      default=["Louisiana (statewide)", "United States", "Parish · Richland Parish",
                                               "LA metro · Monroe MSA"])
        with c2:
            measures = st.multiselect("Measures", list(LAUS_COLS), format_func=LAUS_COLS.get,
                                      default=["rate", "employed"], key="laus_measures")
        c3, c4 = st.columns(2)
        years = c3.slider("Years", 2000, this_year, (this_year - 6, this_year), key="laus_years")
        how = c4.selectbox("Show", TRANSFORMS, index=0, key="laus_how")
        go = st.form_submit_button("📥 Load unemployment data", type="primary", width="stretch")
    skipped = [g.name for g in geos if md.laus_plan(g) is None]
    if skipped:
        st.caption("No LAUS data for: " + ", ".join(skipped))
    if not go and "laus_loaded" not in st.session_state:
        st.info("Pick regions and measures, then press **Load unemployment data**. Custom regions and micro areas "
                "are built by adding up their parishes.")
        return
    st.session_state["laus_loaded"] = True
    if not geos or not measures:
        st.warning("Choose at least one region and one measure.")
        return
    span = min(years[1] - years[0], max_years - 1) + 1
    with st.spinner("Querying the BLS API…"):
        df, msgs = md.laus_series(geos, years=span + 1)
    md.show_messages(msgs)
    if df.empty:
        st.warning("No data returned.")
        return
    df = df[df["date"].dt.year >= years[0]]
    long = df.melt(id_vars=["geo", "date", "seasonal"], value_vars=[m for m in measures if m in df],
                   var_name="measure", value_name="value")
    long["measure"] = long["measure"].map(LAUS_COLS)
    d = _transform(long, "value", ["geo", "measure"], how)
    if how == "12-month % change" and "rate" in measures:
        st.caption("For the unemployment rate, '12-month change' (percentage points) is usually more meaningful "
                   "than % change.")
    _chart(d.dropna(subset=["plot"]), "geo", "measure", how, f"LAUS · {how}", d["measure"].nunique())
    rows = []
    for m in measures:
        if m in df:
            lt = md.latest(df, m, ["geo"])
            lt["measure"] = LAUS_COLS[m]
            rows.append(lt)
    if rows:
        lt = pd.concat(rows)
        st.dataframe(lt[["geo", "measure", "date", "value", "yoy", "yoy_pct"]], hide_index=True, width="stretch",
                     column_config={"geo": "Region", "measure": "Measure",
                                    "date": st.column_config.DateColumn("Month", format="MMM YYYY"),
                                    "value": st.column_config.NumberColumn("Latest", format="localized"),
                                    "yoy": st.column_config.NumberColumn("vs. year earlier", format="%+,.1f"),
                                    "yoy_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%")})
    st.caption("States and the U.S. are seasonally adjusted; parishes, metros and custom regions are not. "
               "A blank YoY means BLS has no value for the same month a year earlier.")
    ui.download(d, "laus_series", key="dl_laus")


def _any(this_year):
    with st.form("any_form"):
        raw = st.text_area("Series IDs (one per line or comma-separated)",
                           value="LASST220000000000003\nSMS22000000000000001\nCUUR0000SA0", key="lab_ids")
        c1, c2 = st.columns(2)
        years = c1.slider("Years", 2000, this_year, (this_year - 9, this_year), key="lab_any_years")
        how = c2.selectbox("Show", TRANSFORMS, key="lab_any_how")
        go = st.form_submit_button("📥 Fetch from BLS", type="primary", width="stretch")
    st.caption("Find IDs with BLS Data Finder (data.bls.gov/dataQuery) or the ID formats in Data Notes & Help.")
    if not go and "any_loaded" not in st.session_state:
        return
    st.session_state["any_loaded"] = True
    ids = tuple(sorted({s.strip().upper() for s in raw.replace(",", "\n").splitlines() if s.strip()}))
    with st.spinner("Querying the BLS API…"):
        df, msgs = blsapi.fetch_series(ids, years[0], years[1])
    md.show_messages(msgs)
    if df.empty:
        st.warning("No data returned.")
        return
    d = _transform(df, "value", ["series_id"], how).dropna(subset=["plot"])
    _chart(d, "series_id", None, how, "BLS series", 1)
    ui.download(d.pivot_table(index="date", columns="series_id", values="plot").reset_index(), "bls_series",
                key="dl_any")
