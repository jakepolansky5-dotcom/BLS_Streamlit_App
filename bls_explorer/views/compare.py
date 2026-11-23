"""Compare Regions — side-by-side benchmarking of any set of geographies."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .. import config as C
from .. import monthly_data as md
from .. import qcew
from .. import ui

PRESETS = {
    "Louisiana vs. neighbors": ["Louisiana (statewide)", "State · Texas", "State · Arkansas", "State · Mississippi",
                                "United States"],
    "Louisiana vs. Southern peers": ["Louisiana (statewide)"] + [f"State · {C.STATES[f][0]}" for f in C.SOUTHERN_PEERS],
    "Louisiana metros": ["LA metro · " + v[0] for v in C.LA_METROS.values()],
    "North Louisiana metros": ["LA metro · Monroe MSA", "LA metro · Shreveport-Bossier City MSA",
                               "LA metro · Alexandria MSA", "LA micro · Ruston MicroSA", "Louisiana (statewide)"],
}


def render():
    ui.header("Compare Regions",
              "Benchmark Louisiana against other states, or compare parishes, metros and custom regions.")
    preset = st.segmented_control("Quick sets", list(PRESETS), key="cmp_preset")
    if preset and st.session_state.get("cmp_last_preset") != preset:
        st.session_state["cmp_geos"] = [p for p in PRESETS[preset] if p in ui.geo_catalogue()]
        st.session_state["cmp_last_preset"] = preset
    if "cmp_geos" not in st.session_state:
        st.session_state["cmp_geos"] = PRESETS["Louisiana vs. neighbors"]
    geos = ui.geo_multiselect("Geographies", key="cmp_geos", default=[])
    ui.custom_region_builder("cmp")
    c1, c2 = st.columns(2)
    with c1:
        period = ui.period_select("cmp_period", freq_key="cmp_freq")
    with c2:
        own = ui.ownership_select("cmp_own", default="0")
    if not geos:
        st.info("Pick at least one geography.")
        return

    _monthly_table(geos)
    st.markdown(f"##### 🏗️ Detailed jobs, wages and industries (QCEW · {period.label})")
    df = ui.load(geos, [period], None, own, lq=True)
    if df.empty:
        st.warning("No data for this selection.")
        return
    names = [g.name for g in geos if g.name in set(df["geo"])]
    cmap = ui.color_map(names)

    # ---- headline table -------------------------------------------------------
    tot = df[df["industry_code"] == "10"].set_index("geo").reindex(names).reset_index()
    st.markdown(f"**QCEW headline indicators · {period.label}**")
    st.dataframe(tot[["geo", "emp", "emp_chg", "emp_pct", "estabs", "estabs_pct", "avg_wkly_wage", "wage_pct", "wages"]],
                 hide_index=True, width="stretch",
                 column_config={"geo": "Geography",
                                "emp": st.column_config.NumberColumn("Employment", format="localized"),
                                "emp_chg": st.column_config.NumberColumn("YoY jobs", format="%+d"),
                                "emp_pct": st.column_config.NumberColumn("Jobs YoY %", format="%+.2f%%"),
                                "estabs": st.column_config.NumberColumn("Establishments", format="localized"),
                                "estabs_pct": st.column_config.NumberColumn("Estabs YoY %", format="%+.1f%%"),
                                "avg_wkly_wage": st.column_config.NumberColumn("Avg weekly wage", format="dollar"),
                                "wage_pct": st.column_config.NumberColumn("Wage YoY %", format="%+.1f%%"),
                                "wages": st.column_config.NumberColumn("Total wages", format="dollar")})
    a, b = st.columns(2)
    with a:
        fig = px.bar(tot, x="geo", y="emp_pct", color="geo", color_discrete_map=cmap,
                     labels={"emp_pct": "Jobs YoY %", "geo": ""})
        fig.update_layout(title="Job growth, year over year", showlegend=False)
        st.plotly_chart(ui.style_fig(fig, 360, legend=False), width="stretch")
    with b:
        fig = px.bar(tot, x="geo", y="avg_wkly_wage", color="geo", color_discrete_map=cmap,
                     labels={"avg_wkly_wage": "Avg weekly wage ($)", "geo": ""})
        fig.update_layout(title="Average weekly wage", showlegend=False)
        st.plotly_chart(ui.style_fig(fig, 360, legend=False), width="stretch")

    tabs = st.tabs(["🧩 Industry mix", "🏭 One industry", "📈 Trend"])
    with tabs[0]:
        c1, c2 = st.columns(2)
        lvl_label = c1.selectbox("Industry detail", ["Supersector", "NAICS sector (2-digit)", "NAICS subsector (3-digit)"],
                                 index=1, key="cmp_lvl")
        measure = c2.selectbox("Measure", ["share", "lq", "emp_pct", "avg_wkly_wage", "emp"], format_func=ui.METRICS.get,
                               key="cmp_measure")
        lvl = C.INDUSTRY_LEVELS[lvl_label]
        mix = df[df["industry_code"].map(qcew.industry_level) == lvl].copy()
        mix["industry"] = mix["industry_code"].map(qcew.industry_label)
        piv = mix.pivot_table(index="industry", columns="geo", values=measure, aggfunc="first")
        piv = piv.reindex(columns=[n for n in names if n in piv.columns])
        if lvl == 3:
            keep = mix.groupby("industry")["emp"].max().nlargest(40).index
            piv = piv.loc[piv.index.intersection(keep)]
        if measure in ("emp_pct",):
            scale, mid = "RdBu", 0
        elif measure == "lq":
            scale, mid = "RdBu", 1
        else:
            scale, mid = "Blues", None
        fig = px.imshow(piv, aspect="auto", color_continuous_scale=scale, color_continuous_midpoint=mid,
                        text_auto=".2f" if measure == "lq" else (".1f" if measure in ("share", "emp_pct") else ",.0f"),
                        labels=dict(color=ui.METRICS[measure]))
        if measure == "lq":
            fig.update_coloraxes(cmin=0, cmax=2)
        fig.update_layout(title=f"{ui.METRICS[measure]} by industry", xaxis_title="", yaxis_title="")
        st.plotly_chart(ui.style_fig(fig, height=max(420, 26 * len(piv) + 120), legend=False),
                        width="stretch")
        ui.download(piv.reset_index(), f"compare_mix_{measure}_{period.key}", key="dl_cmp_mix")
    with tabs[1]:
        ind = ui.industry_select("Industry", key="cmp_ind", default="23")
        one = df[df["industry_code"] == ind].set_index("geo").reindex(names).reset_index()
        cols = st.columns(3)
        for i, (m, title) in enumerate([("emp", "Employment"), ("emp_pct", "YoY %"), ("lq", "Location quotient")]):
            fig = px.bar(one, x="geo", y=m, color="geo", color_discrete_map=cmap, labels={m: title, "geo": ""})
            fig.update_layout(title=title, showlegend=False)
            if m == "lq":
                fig.add_hline(y=1, line_dash="dot")
            cols[i].plotly_chart(ui.style_fig(fig, 340, legend=False), width="stretch")
        one["flag"] = one.apply(ui.status_badge, axis=1)
        st.dataframe(one[["geo", "emp", "emp_chg", "emp_pct", "lq", "share", "estabs", "avg_wkly_wage", "flag"]],
                     hide_index=True, width="stretch",
                     column_config={"geo": "Geography",
                                    "emp": st.column_config.NumberColumn("Employment", format="localized"),
                                    "emp_chg": st.column_config.NumberColumn("YoY", format="%+d"),
                                    "emp_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%"),
                                    "lq": st.column_config.NumberColumn("LQ", format="%.2f"),
                                    "share": st.column_config.NumberColumn("Share %", format="%.2f%%"),
                                    "estabs": st.column_config.NumberColumn("Estabs", format="localized"),
                                    "avg_wkly_wage": st.column_config.NumberColumn("Avg wkly wage", format="dollar"),
                                    "flag": "Data note"})
    with tabs[2]:
        _trend(geos, own, period)
    ui.suppression_note()


@st.fragment
def _trend(geos, own, period):
    c1, c2, c3 = st.columns([3, 2, 2])
    ind = c1.selectbox("Industry", ui.industry_options(), index=0, format_func=qcew.industry_label, key="cmp_tr_ind")
    freq = c2.segmented_control("Frequency", ["Annual", "Quarterly"], default="Annual", key="cmp_tr_freq") or "Annual"
    mode = c3.segmented_control("Show", ["Index", "Level", "YoY %"], default="Index", key="cmp_tr_mode") or "Index"
    info = qcew.latest_periods()
    if freq == "Annual":
        periods = qcew.annual_range(info["earliest_year"], info["annual"].year)
    else:
        periods = qcew.quarter_range(qcew.Period(info["quarter"].year - 5, info["quarter"].qtr), info["quarter"])
    st.caption(f"{len(periods)} periods × {len(geos)} geographies. The first run downloads files; later runs are instant.")
    df = ui.load(geos, periods, [ind], own)
    if df.empty:
        st.info("No data.")
        return
    d = df[df["industry_code"] == ind].sort_values("date").copy()
    if mode == "Index":
        first = d.groupby("geo")["emp"].transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
        d["value"] = d["emp"] / first * 100
        y = "Index (first period = 100)"
    elif mode == "YoY %":
        d["value"], y = d["emp_pct"], "YoY %"
    else:
        d["value"], y = d["emp"], "Employment"
    fig = px.line(d, x="period", y="value", color="geo", markers=True,
                  color_discrete_map=ui.color_map(d["geo"].unique().tolist()), labels={"value": y, "period": "", "geo": ""})
    fig.update_layout(title=f"{qcew.industry_label(ind)} · {C.OWNERSHIPS[own]}")
    st.plotly_chart(ui.style_fig(fig, 440), width="stretch")
    ui.download(d, f"compare_trend_{ind}", key="dl_cmp_trend")


def _monthly_table(geos):
    """Latest monthly LAUS + CES side by side: the 'where are we now' comparison."""
    with st.spinner("Loading latest monthly data (LAUS/CES)…"):
        t, msgs = md.conditions_table(geos)
    md.show_messages(msgs)
    if t.empty or t.drop(columns="geo").dropna(how="all").empty:
        return
    months = []
    if "laus_month" in t and t["laus_month"].notna().any():
        months.append(f"unemployment through {t['laus_month'].max():%b %Y}")
    if "ces_month" in t and t["ces_month"].notna().any():
        months.append(f"payroll jobs through {t['ces_month'].max():%b %Y}")
    st.markdown("##### 🗓️ Where things stand now (monthly LAUS/CES)")
    st.caption("Latest BLS monthly data (" + "; ".join(months) + "). Changes vs. the same month a year earlier. "
               "States/U.S. seasonally adjusted; parishes, metros and regions not. Payroll jobs (CES) exist only "
               "for the U.S., states and metros.")
    cols = [c for c in ["geo", "rate", "rate_yoy", "lf", "lf_yoy_pct", "emp_yoy", "jobs", "jobs_yoy", "jobs_yoy_pct"] if c in t]
    st.dataframe(t[cols], hide_index=True, width="stretch",
                 column_config={"geo": "Geography",
                                "rate": st.column_config.NumberColumn("Unemployment %", format="%.1f"),
                                "rate_yoy": st.column_config.NumberColumn("vs. yr ago (pts)", format="%+.1f"),
                                "lf": st.column_config.NumberColumn("Labor force", format="localized"),
                                "lf_yoy_pct": st.column_config.NumberColumn("LF YoY %", format="%+.1f%%"),
                                "emp_yoy": st.column_config.NumberColumn("Employed residents YoY", format="%+,d"),
                                "jobs": st.column_config.NumberColumn("Payroll jobs", format="localized"),
                                "jobs_yoy": st.column_config.NumberColumn("Jobs YoY", format="%+,d"),
                                "jobs_yoy_pct": st.column_config.NumberColumn("Jobs YoY %", format="%+.2f%%")})
    st.divider()
