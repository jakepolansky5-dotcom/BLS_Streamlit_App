"""Region Overview — a Lightcast-style economy overview for any geography."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .. import config as C
from .. import geo as G
from .. import monthly_data as md
from .. import qcew
from .. import ui


def render():
    ui.header("Region Overview",
              "Current labor-market conditions (monthly LAUS/CES), then detailed employment, wages and industry "
              "structure (QCEW) for any Louisiana parish, metro, custom region, or state.")

    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    with c1:
        g = ui.geo_select("Geography", key="ov_geo")
    with c2:
        period = ui.period_select("ov_period", freq_key="ov_freq")
    with c3:
        own = ui.ownership_select("ov_own", default="0")
    with c4:
        level_label = st.selectbox("Industry detail", list(C.INDUSTRY_LEVELS), index=1, key="ov_level")
    ui.custom_region_builder("ov")
    level = C.INDUSTRY_LEVELS[level_label]

    if md.render_strip(g, title=f"Where {g.label} stands now (monthly LAUS/CES)"):
        st.divider()
    st.markdown(f"##### 🏗️ Detailed jobs, wages and industries (QCEW · {period.label})")
    df = ui.load([g], [period], None, own, lq=True)
    if df.empty:
        st.warning(f"No QCEW data for {g.name} in {period.label}. It may not be released yet.")
        return
    tot = df[df["industry_code"] == "10"]
    if tot.empty:
        st.warning("No all-industry total in this file.")
        return
    t = tot.iloc[0]

    # ---- KPIs --------------------------------------------------------------
    emp_label = "Employment (annual avg)" if period.annual else "Employment"
    k = st.columns(5)
    k[0].metric(emp_label, ui.fnum(t["emp"]), delta=f"{ui.fdelta(t['emp_chg'])} ({ui.fpct(t['emp_pct'])}) YoY"
                if pd.notna(t["emp_chg"]) else None, border=True)
    k[1].metric("Avg weekly wage", ui.fmoney(t["avg_wkly_wage"]),
                delta=f"{ui.fpct(t['wage_pct'])} YoY" if pd.notna(t["wage_pct"]) else None, border=True)
    k[2].metric("Establishments", ui.fnum(t["estabs"]),
                delta=f"{ui.fpct(t['estabs_pct'])} YoY" if pd.notna(t["estabs_pct"]) else None, border=True)
    k[3].metric("Total wages", ui.fmoney(t["wages"]),
                delta=f"{ui.fpct(t['wages_pct'])} YoY" if pd.notna(t["wages_pct"]) else None, border=True)
    if g.kind in ("county", "metro", "region") and all(c.startswith("22") for c in g.codes):
        la = ui.load([G.LOUISIANA], [period], ["10"], "0")
        la_emp = la.loc[la["industry_code"] == "10", "emp"].iloc[0] if not la.empty else np.nan
        k[4].metric("Share of Louisiana jobs", ui.fpct(t["tot_emp"] / la_emp * 100, 2, sign=False), border=True)
    else:
        us_share = t["tot_emp"] / t["us_tot_emp"] * 100 if pd.notna(t.get("us_tot_emp")) else np.nan
        k[4].metric("Share of U.S. jobs", ui.fpct(us_share, 2, sign=False), border=True)
    st.caption(f"{g.name} · {period.label} · {C.OWNERSHIPS[own]}"
               + (f" · built from {len(g.codes)} parishes" if g.is_composite else ""))

    # ---- trend + composition ----------------------------------------------
    left, right = st.columns([3, 2])
    with left:
        _trend(g, own, period)
    with right:
        sup = df[df["industry_code"].map(qcew.industry_level) == "super"].copy()
        sup["industry"] = sup["industry_code"].map(qcew.industry_titles())
        sup = sup.dropna(subset=["emp"])
        if not sup.empty:
            fig = px.pie(sup, values="emp", names="industry", hole=0.55,
                         color_discrete_sequence=ui.PALETTE)
            fig.update_traces(textposition="inside", textinfo="percent")
            fig.update_layout(title="Jobs by supersector", showlegend=True,
                              legend=dict(font=dict(size=10)))
            fig = ui.style_fig(fig, height=400, legend=False)
            fig.update_layout(showlegend=True, legend=dict(orientation="v", x=1, y=0.5, font=dict(size=10)))
            st.plotly_chart(fig, width="stretch")

    # ---- industry detail tabs --------------------------------------------
    ind = df[df["industry_code"].map(qcew.industry_level) == level].copy()
    tabs = st.tabs(["🏭 Industries", "📈 Growth & decline", "🎯 Specialization", "🧮 Shift-share"]
                   + (["🗺️ Parishes"] if g.is_composite or g.key == "22000" else []))
    with tabs[0]:
        search = st.text_input("Filter industries", placeholder="type a code or keyword", key="ov_search")
        view = ind.sort_values("emp", ascending=False)
        if search:
            titles = view["industry_code"].map(qcew.industry_titles()).fillna("")
            mask = titles.str.contains(search, case=False) | view["industry_code"].str.startswith(search)
            view = view[mask]
        ui.industry_table(view)
        ui.suppression_note(view)
        ui.download(view.drop(columns=[c for c in view.columns if c.startswith("_")]),
                    f"overview_{g.key}_{period.key}_{level_label[:6]}")
    with tabs[1]:
        movers = ind.dropna(subset=["emp_chg"]).copy()
        movers["industry"] = movers["industry_code"].map(qcew.industry_label)
        n = st.slider("Industries to show", 5, 25, 10, key="ov_nmovers")
        a, b = st.columns(2)
        with a:
            top = movers.nlargest(n, "emp_chg")
            st.plotly_chart(ui.diverging_bar(top, "emp_chg", "industry", f"Largest job gains, YoY ({period.label})",
                                             height=80 + 32 * len(top)), width="stretch")
        with b:
            bot = movers.nsmallest(n, "emp_chg")
            st.plotly_chart(ui.diverging_bar(bot, "emp_chg", "industry", f"Largest job losses, YoY ({period.label})",
                                             height=80 + 32 * len(bot)), width="stretch")
        st.caption("Based on industries whose year-over-year change BLS disclosed.")
    with tabs[2]:
        sp = ind.dropna(subset=["lq", "emp_pct", "emp"]).copy()
        sp = sp[sp["emp"] >= st.number_input("Minimum employment", 0, 100000, 50, 25, key="ov_minemp")]
        sp["industry"] = sp["industry_code"].map(qcew.industry_label)
        sp["emp_pct_c"] = sp["emp_pct"].clip(-50, 100)
        if sp.empty:
            st.info("Not enough disclosed data for this view.")
        else:
            fig = px.scatter(sp, x="emp_pct_c", y="lq", size="emp", hover_name="industry", size_max=55,
                             color="avg_wkly_wage", color_continuous_scale="Viridis",
                             labels={"emp_pct_c": "Employment change YoY (%)", "lq": "Location quotient",
                                     "avg_wkly_wage": "Avg wkly wage"},
                             hover_data={"emp": ":,.0f", "emp_pct": ":.1f", "lq": ":.2f", "emp_pct_c": False})
            fig.add_hline(y=1, line_dash="dot", line_color="gray")
            fig.add_vline(x=0, line_dash="dot", line_color="gray")
            fig.update_layout(title="Specialization vs. growth (bubble size = jobs)")
            st.plotly_chart(ui.style_fig(fig, height=560, legend=False), width="stretch")
            st.caption("Upper right: specialized and growing. Upper left: specialized but declining. "
                       "LQ > 1 means a larger share of local jobs than the U.S. average. Growth clipped at -50% / +100%.")
    with tabs[3]:
        _shift_share(g, period, own, level, ind)
    if len(tabs) > 4:
        with tabs[4]:
            _parish_breakdown(g, period, own)


@st.fragment
def _trend(g, own, period):
    span = st.segmented_control("Trend", ["3 yrs", "5 yrs", "All"], default="3 yrs", key="ov_span") or "3 yrs"
    compare = st.toggle("Index vs. Louisiana & U.S.", value=False, key="ov_trend_idx")
    end = qcew.latest_periods()["quarter"] if period.annual else period
    years = {"3 yrs": 3, "5 yrs": 5, "All": 30}[span]
    start = qcew.Period(max(qcew.latest_periods()["earliest_year"], end.year - years), end.qtr)
    periods = qcew.quarter_range(start, end)
    geos = [g] + ([G.LOUISIANA, G.US] if compare and g.key != "22000" else ([G.US] if compare else []))
    df = ui.load(geos, periods, ["10"], own)
    if df.empty:
        return
    m = qcew.monthly(df[df["industry_code"] == "10"])
    if compare:
        base = m.groupby("geo")["emp"].transform("first")
        m["value"] = m["emp"] / base * 100
        ytitle = f"Index ({m['date'].min():%b %Y} = 100)"
    else:
        m["value"] = m["emp"]
        ytitle = "Employment"
    fig = px.line(m, x="date", y="value", color="geo", color_discrete_map=ui.color_map(m["geo"].unique().tolist()),
                  labels={"value": ytitle, "date": "", "geo": ""})
    fig.update_layout(title=f"Monthly employment ({C.OWNERSHIPS[own].lower()})")
    st.plotly_chart(ui.style_fig(fig, height=360), width="stretch")


def _shift_share(g, period, own, level, ind_now):
    st.markdown("Splits job change into **national growth**, **industry mix** (whether local industries are "
                "fast-growing nationally) and **regional competitiveness** (local performance beyond national trends).")
    opts = [p for p in qcew.available_periods("A" if period.annual else "Q")
            if p.qtr == period.qtr and p.year < period.year]
    if not opts:
        st.info("No earlier comparable period.")
        return
    default = min(len(opts) - 1, 4)
    base = st.selectbox("Base period", opts, index=default, format_func=lambda p: p.label, key="ss_base")
    df0 = ui.load([g], [base], None, own)
    us = ui.load([G.US], [period, base], None, own)
    if df0.empty or us.empty:
        st.info("Base-period data unavailable.")
        return
    us1 = us[us["period_key"] == period.key].set_index("industry_code")["emp"]
    us0 = us[us["period_key"] == base.key].set_index("industry_code")["emp"]
    G_us = us1.get("10") / us0.get("10") - 1
    r0 = df0[df0["industry_code"].map(qcew.industry_level) == level].set_index("industry_code")["emp"]
    r1 = ind_now.set_index("industry_code")["emp"]
    ss = pd.DataFrame({"base": r0, "now": r1, "us0": us0, "us1": us1}).dropna()
    ss = ss[(ss["base"] > 0) & (ss["us0"] > 0)]
    if ss.empty:
        st.info("Not enough disclosed data in both periods.")
        return
    g_us = ss["us1"] / ss["us0"] - 1
    g_r = ss["now"] / ss["base"] - 1
    ss["Actual change"] = ss["now"] - ss["base"]
    ss["National growth"] = ss["base"] * G_us
    ss["Industry mix"] = ss["base"] * (g_us - G_us)
    ss["Competitive effect"] = ss["base"] * (g_r - g_us)
    ss = ss.reset_index().rename(columns={"index": "industry_code"})
    ss["industry"] = ss["industry_code"].map(qcew.industry_label)
    totals = ss[["Actual change", "National growth", "Industry mix", "Competitive effect"]].sum()
    k = st.columns(4)
    for i, (name, v) in enumerate(totals.items()):
        k[i].metric(name, ui.fdelta(v), border=True)
    top = ss.reindex(ss["Competitive effect"].abs().sort_values(ascending=False).index).head(15)
    long = top.melt(id_vars="industry", value_vars=["National growth", "Industry mix", "Competitive effect"],
                    var_name="component", value_name="jobs")
    fig = px.bar(long, y="industry", x="jobs", color="component", orientation="h", barmode="relative",
                 color_discrete_sequence=[ui.US_COLOR, "#F59E0B", ui.LA_COLOR])
    fig.update_layout(title=f"Shift-share, {base.label} → {period.label} (top 15 by competitive effect)",
                      yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(ui.style_fig(fig, height=600), width="stretch")
    st.caption(f"Covers industries disclosed in both periods ({len(ss)} industries). "
               "NAICS revisions between periods can affect detailed codes.")
    ui.download(ss, f"shiftshare_{g.key}_{base.key}_{period.key}", key="dl_ss")


def _parish_breakdown(g, period, own):
    codes = list(C.LA_PARISHES) if g.key == "22000" else list(g.codes)
    parishes = [G.county(c) for c in codes]
    ind = ui.industry_select("Industry", key="ov_parish_ind", default="10")
    df = ui.load(parishes, [period], [ind], own)
    d = df[df["industry_code"] == ind].copy()
    if d.empty:
        st.info("No data.")
        return
    d["area_fips"] = d["geo_key"]
    metric = st.radio("Map metric", ["emp", "emp_chg", "emp_pct", "avg_wkly_wage"], horizontal=True,
                      format_func=ui.METRICS.get, key="ov_parish_metric")
    a, b = st.columns([3, 2])
    with a:
        fig = ui.parish_map(d, metric, f"{qcew.industry_label(ind)} · {ui.METRICS[metric]}",
                            fmt=",.1f" if metric.endswith("pct") else ",.0f", diverging=metric != "emp" and metric != "avg_wkly_wage")
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
    with b:
        d["flag"] = d.apply(ui.status_badge, axis=1)
        st.dataframe(d[["geo", "emp", "emp_chg", "emp_pct", "avg_wkly_wage", "flag"]].sort_values("emp", ascending=False),
                     hide_index=True, width="stretch", height=520,
                     column_config={"geo": "Parish", "emp": st.column_config.NumberColumn("Employment", format="localized"),
                                    "emp_chg": st.column_config.NumberColumn("YoY", format="%+d"),
                                    "emp_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%"),
                                    "avg_wkly_wage": st.column_config.NumberColumn("Avg wkly wage", format="dollar"),
                                    "flag": "Data note"})
