"""Latest Release — what the newest QCEW quarter says about Louisiana."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from .. import config as C
from .. import geo as G
from .. import qcew
from .. import ui


def render():
    info = qcew.latest_periods()
    periods = qcew.available_periods("Q")
    ui.header("Latest QCEW Release",
              "The newest county-level jobs and wages data for Louisiana, its parishes, and every state. "
              "This page picks up new BLS releases automatically.")
    c1, c2 = st.columns([2, 5])
    with c1:
        period = st.selectbox("Quarter", periods, index=0, format_func=lambda p: p.label, key="rel_period")
    with c2:
        upcoming = [(d, p) for d, p in C.RELEASE_SCHEDULE if date.fromisoformat(d) >= date.today()]
        if upcoming:
            d, p = upcoming[0]
            st.info(f"**Next release:** {p} data on {date.fromisoformat(d):%A, %B %d, %Y}. "
                    "After BLS posts it (usually 10:00 a.m. ET), press **🔄 Check for new data now** in the sidebar.",
                    icon="🗓️")

    own = "0"
    states = G.all_states()
    parishes = G.all_la_parishes()
    metros = G.la_metros(include_micro=False)
    df = ui.load([G.US, *states, *parishes, *metros], [period], ["10"], own)
    if df.empty:
        st.warning("No data for this quarter.")
        return
    tot = df[df["industry_code"] == "10"].copy()
    tot["area_fips"] = tot["geo_key"]
    us, la = tot[tot["geo_key"] == "US000"].iloc[0], tot[tot["geo_key"] == "22000"].iloc[0]
    st_df = tot[tot["geo_key"].isin([s.key for s in states])]
    rank = st_df.sort_values("emp_pct", ascending=False).reset_index(drop=True)
    la_rank = int(rank.index[rank["geo_key"] == "22000"][0]) + 1

    k = st.columns(5)
    k[0].metric("Louisiana jobs", ui.fnum(la["emp"]), delta=f"{ui.fdelta(la['emp_chg'])} ({ui.fpct(la['emp_pct'])}) YoY",
                border=True)
    k[1].metric("LA avg weekly wage", ui.fmoney(la["avg_wkly_wage"]), delta=f"{ui.fpct(la['wage_pct'])} YoY", border=True)
    k[2].metric("LA job-growth rank", f"#{la_rank} of {len(rank)}", border=True,
                help="Year-over-year % change in total covered employment, among states + DC + PR.")
    k[3].metric("U.S. jobs YoY", ui.fpct(us["emp_pct"]), delta=f"{ui.fdelta(us['emp_chg'])}", border=True)
    pa = tot[tot["geo_key"].isin(C.LA_PARISHES)]
    k[4].metric("Parishes adding jobs", f"{int((pa['emp_chg'] > 0).sum())} of {len(pa)}", border=True)

    tabs = st.tabs(["🗺️ Parishes", "🏙️ Metros", "🏭 Louisiana industries", "🇺🇸 States", "🎯 My watchlists"])
    with tabs[0]:
        a, b = st.columns([3, 2])
        short = {"emp_pct": "Jobs YoY %", "emp_chg": "Jobs YoY", "avg_wkly_wage": "Avg weekly wage", "wage_pct": "Wage YoY %"}
        metric = a.segmented_control("Map", list(short), default="emp_pct", format_func=short.get,
                                     key="rel_map_metric") or "emp_pct"
        with a:
            fig = ui.parish_map(pa, metric, f"{ui.METRICS[metric]} · {period.label}",
                                fmt=",.1f" if "pct" in metric else ",.0f", diverging=metric in ("emp_pct", "emp_chg", "wage_pct"))
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
        with b:
            by = st.radio("Rank by", ["emp_chg", "emp_pct"], format_func=ui.METRICS.get, horizontal=True, key="rel_rank")
            top = pa.nlargest(8, by)
            bot = pa.nsmallest(8, by)
            st.markdown("**Biggest gains**")
            _mini(top)
            st.markdown("**Biggest declines**")
            _mini(bot)
        ui.download(pa, f"release_parishes_{period.key}", key="dl_rel_p")
    with tabs[1]:
        me = tot[tot["geo_key"].isin([m.key for m in metros])].sort_values("emp_pct")
        fig = px.bar(me, x="emp_pct", y="geo", orientation="h", text=me["emp_chg"].map(lambda v: f"{v:+,.0f} jobs"),
                     color="emp_pct", color_continuous_scale="RdBu", color_continuous_midpoint=0,
                     labels={"emp_pct": "YoY %", "geo": ""})
        fig.add_vline(x=la["emp_pct"], line_dash="dot", annotation_text="Louisiana")
        fig.update_layout(title=f"Metro job growth, {period.label} vs. a year earlier", coloraxis_showscale=False)
        st.plotly_chart(ui.style_fig(fig, 460, legend=False), width="stretch")
    with tabs[2]:
        _la_industries(period)
    with tabs[3]:
        fig = ui.state_map(st_df, "emp_pct", f"Job growth by state, YoY % · {period.label}", fmt=",.2f", diverging=True)
        st.plotly_chart(fig, width="stretch")
        show = rank.copy()
        colors = [ui.LA_COLOR if k == "22000" else ("#F59E0B" if k[:2] in C.LA_NEIGHBORS else "#CBD5E1") for k in show["geo_key"]]
        fig = px.bar(show, x="geo", y="emp_pct", labels={"emp_pct": "YoY %", "geo": ""})
        fig.update_traces(marker_color=colors)
        fig.add_hline(y=us["emp_pct"], line_dash="dot", annotation_text="U.S.")
        fig.update_layout(title="All states ranked (Louisiana blue; TX, AR, MS amber)")
        st.plotly_chart(ui.style_fig(fig, 420, legend=False), width="stretch")
    with tabs[4]:
        _watchlists(period)


def _mini(d):
    st.dataframe(d[["geo", "emp", "emp_chg", "emp_pct"]], hide_index=True, width="stretch",
                 column_config={"geo": "Parish", "emp": st.column_config.NumberColumn("Jobs", format="localized"),
                                "emp_chg": st.column_config.NumberColumn("YoY", format="%+d"),
                                "emp_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%")})


def _la_industries(period):
    lvl_label = st.selectbox("Detail", ["NAICS sector (2-digit)", "NAICS subsector (3-digit)", "Industry group (4-digit)"],
                             key="rel_lvl")
    own = st.selectbox("Ownership", ["5", "0"], format_func=C.OWNERSHIPS.get, key="rel_own")
    lvl = C.INDUSTRY_LEVELS[lvl_label]
    df = ui.load([G.LOUISIANA], [period], None, own, lq=True)
    ind = df[df["industry_code"].map(qcew.industry_level) == lvl].dropna(subset=["emp_chg"]).copy()
    ind["industry"] = ind["industry_code"].map(qcew.industry_label)
    a, b = st.columns(2)
    with a:
        top = ind.nlargest(12, "emp_chg")
        st.plotly_chart(ui.diverging_bar(top, "emp_chg", "industry", "Louisiana: largest job gains (YoY)",
                                         height=110 + 30 * len(top)), width="stretch")
    with b:
        bot = ind.nsmallest(12, "emp_chg")
        st.plotly_chart(ui.diverging_bar(bot, "emp_chg", "industry", "Louisiana: largest job losses (YoY)",
                                         height=110 + 30 * len(bot)), width="stretch")
    ui.industry_table(ind.sort_values("emp_chg", ascending=False), height=420, key="rel_ind_table")


def _watchlists(period):
    lists = G.load_watchlists()
    if not lists:
        st.info("No watchlists yet. Create one on the Project Watch page.")
        return
    rows = []
    for name, wl in lists.items():
        region = G.region(name, wl["parishes"])
        inds = list(dict.fromkeys(["10", *wl["industries"]]))
        df = ui.load([region], [period], inds, "5")
        for _, r in df.iterrows():
            rows.append({"Watchlist": name, "Industry": qcew.industry_label(r["industry_code"]), "Jobs": r["emp"],
                         "YoY": r["emp_chg"], "YoY %": r["emp_pct"], "Avg wkly wage": r["avg_wkly_wage"],
                         "Note": ui.status_badge(r)})
    t = pd.DataFrame(rows)
    st.dataframe(t, hide_index=True, width="stretch", height=min(600, 40 + 35 * len(t)),
                 column_config={"Jobs": st.column_config.NumberColumn(format="localized"),
                                "YoY": st.column_config.NumberColumn(format="%+d"),
                                "YoY %": st.column_config.NumberColumn(format="%+.1f%%"),
                                "Avg wkly wage": st.column_config.NumberColumn(format="dollar")})
    st.caption("Private ownership. Open **Project Watch** for monthly detail, parish breakdowns and benchmarks.")
