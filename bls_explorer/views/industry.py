"""Industry Snapshot — one industry across the U.S., states, Louisiana metros and parishes."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .. import config as C
from .. import geo as G
from .. import qcew
from .. import ui


def render():
    ui.header("Industry Snapshot",
              "Where an industry is concentrated and growing: Louisiana parishes and metros, every state, and the U.S.")
    c1, c2, c3 = st.columns([4, 2, 2])
    with c1:
        ind = ui.industry_select("Industry (NAICS)", key="is_ind", default="23")
    with c2:
        period = ui.period_select("is_period", freq_key="is_freq")
    with c3:
        own = ui.ownership_select("is_own", default="5")

    parishes = G.all_la_parishes()
    metros = G.la_metros(include_micro=True)
    states = G.all_states()
    geos = [G.US] + states + parishes + metros
    df = ui.load(geos, [period], [ind], own, lq=True)
    d = df[df["industry_code"] == ind].copy() if not df.empty else df
    if d.empty:
        st.warning(f"No data for {qcew.industry_label(ind)} in {period.label}.")
        return
    d["area_fips"] = d["geo_key"]
    us = d[d["geo_key"] == "US000"]
    la = d[d["geo_key"] == "22000"]
    st_df = d[d["geo_key"].isin([s.key for s in states])].copy()
    pa_df = d[d["geo_key"].isin([p.key for p in parishes])].copy()
    me_df = d[d["geo_key"].isin([m.key for m in metros])].copy()

    # ---- KPIs --------------------------------------------------------------
    u = us.iloc[0] if not us.empty else None
    l = la.iloc[0] if not la.empty else None
    k = st.columns(5)
    if l is not None:
        k[0].metric("Louisiana employment", ui.fnum(l["emp"]),
                    delta=f"{ui.fdelta(l['emp_chg'])} ({ui.fpct(l['emp_pct'])}) YoY" if pd.notna(l["emp_chg"]) else None,
                    border=True)
        k[1].metric("Louisiana LQ", ui.fnum(l.get("lq"), 2), border=True,
                    help="Share of Louisiana jobs in this industry relative to the U.S. share.")
        k[2].metric("LA avg weekly wage", ui.fmoney(l["avg_wkly_wage"]),
                    delta=(f"{(l['avg_wkly_wage'] / u['avg_wkly_wage'] - 1) * 100:+.0f}% vs U.S."
                           if u is not None and pd.notna(l["avg_wkly_wage"]) else None),
                    delta_color="off", border=True)
        ranked = st_df.dropna(subset=["emp"]).sort_values("emp", ascending=False).reset_index(drop=True)
        rank = ranked.index[ranked["geo_key"] == "22000"]
        grow = st_df.dropna(subset=["emp_pct"]).sort_values("emp_pct", ascending=False).reset_index(drop=True)
        grank = grow.index[grow["geo_key"] == "22000"]
        k[3].metric("LA state rank",
                    f"#{rank[0] + 1 if len(rank) else '—'} / #{grank[0] + 1 if len(grank) else '—'}",
                    help=f"By employment / by YoY growth, among {len(ranked)} states with disclosed data.", border=True)
    else:
        k[0].metric("Louisiana employment", "—", border=True)
    if u is not None:
        k[4].metric("U.S. employment", ui.fnum(u["emp"]),
                    delta=f"{ui.fpct(u['emp_pct'])} YoY" if pd.notna(u["emp_pct"]) else None, border=True)
    if l is not None and l["status"]:
        st.caption(f"Louisiana statewide value: {ui.status_badge(l)}")

    metric = st.segmented_control("Map / ranking metric", ["emp", "emp_chg", "emp_pct", "lq", "avg_wkly_wage"],
                                  default="emp", format_func=ui.METRICS.get, key="is_metric") or "emp"
    fmt = ",.1f" if metric.endswith("pct") else (",.2f" if metric == "lq" else ",.0f")
    div = metric in ("emp_chg", "emp_pct")

    tabs = st.tabs(["🗺️ Louisiana parishes", "🏙️ Louisiana metros", "🇺🇸 States", "📈 Trend", "🔎 Drill down"])
    with tabs[0]:
        a, b = st.columns([3, 2])
        with a:
            fig = ui.parish_map(pa_df, metric, f"{qcew.industry_label(ind)} · {ui.METRICS[metric]}", fmt=fmt, diverging=div)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Map shapes unavailable offline; see table.")
        with b:
            _geo_table(pa_df, "Parish", metric)
        n_supp = int((pa_df["status"] == "Suppressed").sum())
        missing = 64 - len(pa_df)
        st.caption(f"{n_supp} parishes suppressed; {missing} parishes report no establishments in this industry.")
        ui.download(pa_df, f"industry_{ind}_{period.key}_parishes", key="dl_is_p")
    with tabs[1]:
        me = me_df.dropna(subset=[metric]).sort_values(metric)
        fig = px.bar(me, x=metric, y="geo", orientation="h", color=metric,
                     color_continuous_scale="RdBu" if div else "Blues",
                     color_continuous_midpoint=0 if div else None,
                     labels={metric: ui.METRICS[metric], "geo": ""})
        fig.update_layout(title=f"Louisiana metro & micro areas · {ui.METRICS[metric]}", coloraxis_showscale=False)
        st.plotly_chart(ui.style_fig(fig, height=120 + 26 * len(me), legend=False), width="stretch")
        _geo_table(me_df, "Metro / micro area", metric)
        st.caption("Metro areas use current (2023) OMB definitions and are built from parishes, "
                   "so suppressed parishes make some totals partial (minimum values).")
    with tabs[2]:
        fig = ui.state_map(st_df, metric, f"{qcew.industry_label(ind)} by state · {ui.METRICS[metric]}", fmt=fmt,
                           diverging=div)
        st.plotly_chart(fig, width="stretch")
        ranked = st_df.dropna(subset=[metric]).sort_values(metric, ascending=False)
        top_n = st.slider("States to show", 10, 52, 20, key="is_topn")
        show = ranked.head(top_n)
        if "22000" not in show["geo_key"].values:
            show = pd.concat([show, ranked[ranked["geo_key"] == "22000"]])
        hl = set(["22000"] + [f + "000" for f in C.LA_NEIGHBORS])
        colors = [ui.LA_COLOR if k == "22000" else ("#F59E0B" if k in hl else "#CBD5E1") for k in show["geo_key"]]
        fig = px.bar(show, x="geo", y=metric, labels={metric: ui.METRICS[metric], "geo": ""})
        fig.update_traces(marker_color=colors)
        fig.update_layout(title="State ranking (Louisiana in blue, TX/AR/MS in amber)")
        st.plotly_chart(ui.style_fig(fig, height=420, legend=False), width="stretch")
        _geo_table(st_df, "State", metric)
    with tabs[3]:
        _trend(ind, own, period)
    with tabs[4]:
        _drill(ind, own, period)
    ui.suppression_note()


def _geo_table(df, label, metric):
    v = df.copy()
    v["flag"] = v.apply(ui.status_badge, axis=1)
    v = v.sort_values(metric, ascending=False)
    st.dataframe(v[["geo", "emp", "emp_chg", "emp_pct", "lq", "estabs", "avg_wkly_wage", "flag"]],
                 hide_index=True, width="stretch", height=440,
                 column_config={"geo": label,
                                "emp": st.column_config.NumberColumn("Employment", format="localized"),
                                "emp_chg": st.column_config.NumberColumn("YoY", format="%+d"),
                                "emp_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%"),
                                "lq": st.column_config.NumberColumn("LQ", format="%.2f"),
                                "estabs": st.column_config.NumberColumn("Estabs", format="localized"),
                                "avg_wkly_wage": st.column_config.NumberColumn("Avg wkly wage", format="dollar"),
                                "flag": "Data note"})


@st.fragment
def _trend(ind, own, period):
    extra = ui.geo_multiselect("Compare", key="is_trend_geos",
                               default=["Louisiana (statewide)", "State · Texas", "State · Mississippi",
                                        "State · Arkansas", "United States"])
    c1, c2 = st.columns(2)
    years = c1.slider("Years of history", 2, 13, 5, key="is_trend_years")
    mode = c2.segmented_control("Show", ["Index", "Level", "YoY %"], default="Index", key="is_trend_mode") or "Index"
    end = qcew.latest_periods()["quarter"] if period.annual else period
    start = qcew.Period(max(qcew.latest_periods()["earliest_year"], end.year - years), end.qtr)
    df = ui.load(extra, qcew.quarter_range(start, end), [ind], own)
    if df.empty:
        st.info("No data.")
        return
    d = df[df["industry_code"] == ind].sort_values("date")
    if mode == "Index":
        d["value"] = d["emp"] / d.groupby("geo")["emp"].transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan) * 100
        y = f"Index ({d['period'].iloc[0]} = 100)"
    elif mode == "YoY %":
        d["value"] = d["emp_pct"]
        y = "YoY % change"
    else:
        d["value"] = d["emp"]
        y = "Employment (3rd month of quarter)"
    fig = px.line(d, x="date", y="value", color="geo", markers=True,
                  color_discrete_map=ui.color_map(d["geo"].unique().tolist()), labels={"value": y, "date": "", "geo": ""})
    fig.update_layout(title=f"{qcew.industry_label(ind)} · {C.OWNERSHIPS[own]}")
    st.plotly_chart(ui.style_fig(fig, height=440), width="stretch")
    ui.download(d, f"industry_trend_{ind}", key="dl_is_trend")


def _drill(ind, own, period):
    lvl = qcew.industry_level(ind)
    if lvl == 6:
        st.info("This is already the most detailed NAICS level.")
        return
    g = ui.geo_select("Geography", key="is_drill_geo")
    df = ui.load([g], [period], None, own, lq=True)
    if df.empty:
        st.info("No data.")
        return
    if ind == "10":
        child = df[df["industry_code"].map(qcew.industry_level) == 2]
    elif lvl == "super":
        st.info("Pick a NAICS sector or finer code to drill down.")
        return
    else:
        nxt = lvl + 1
        prefixes = tuple(str(x) for x in range(int(ind[:2]), int(ind[-2:]) + 1)) if "-" in ind else (ind,)
        child = df[df["industry_code"].str.startswith(prefixes) & (df["industry_code"].map(qcew.industry_level) == nxt)]
    st.markdown(f"**Sub-industries of {qcew.industry_label(ind)} in {g.name}, {period.label}**")
    ui.industry_table(child.sort_values("emp", ascending=False), height=420, key="is_drill_table")
