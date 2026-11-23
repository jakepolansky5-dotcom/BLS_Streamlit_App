"""Monthly Snapshot — the latest LAUS (unemployment) and CES (payroll jobs) data for Louisiana.

Series are requested in fixed groups so cached API results stay reusable and
the page fits within the keyless BLS API limit (25 requests/day):
core statewide (1 request), parishes (3), metros (1), all states (5, on demand).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .. import blsapi
from .. import config as C
from .. import geo as G
from .. import monthly_data as md
from .. import ui

LA_CES = [k for k in blsapi.CES_INDUSTRIES if k != "15000000"]
YEARS_BACK = 3


# ---------------------------------------------------------------------------
# Series groups
# ---------------------------------------------------------------------------
def core_ids() -> dict:
    ids = {f"LASST22{'0' * 11}{m}": f"LA {blsapi.LAUS_MEASURES[m].lower()}" for m in ("03", "04", "05", "06")}
    ids.update({"LNS14000000": "US unemployment rate", "LNS11000000": "US labor force", "LNS12000000": "US employment"})
    ids.update({f"SMS2200000{ind}01": f"LA {blsapi.CES_INDUSTRIES[ind]}" for ind in LA_CES})
    ids["CES0000000001"] = "US total nonfarm"
    return ids


def parish_ids() -> dict:
    return {f"LAUCN{f}{'0' * 8}03": f for f in C.LA_PARISHES}


def metro_ids() -> dict:
    out = {}
    for code, (name, _) in C.LA_METROS.items():
        out[f"LAUMT22{code[1:]}0{'0' * 6}03"] = (code, "rate")
        out[f"SMU22{code[1:]}0{'0' * 8}01"] = (code, "jobs")
    return out


def state_ids() -> dict:
    out = {}
    for f in C.STATES:
        out[f"LASST{f}{'0' * 11}03"] = (f, "rate")
        out[f"SMS{f}{'0' * 13}01"] = (f, "jobs")
    return out


def _get(ids, label: str) -> pd.DataFrame:
    y1 = date.today().year
    with st.spinner(f"Loading {label} from the BLS API…"):
        df, msgs = blsapi.fetch_series(tuple(sorted(ids)), y1 - YEARS_BACK, y1)
    for m in msgs:
        if "does not exist" in m or "No Data Available" in m:
            continue
        st.warning(m, icon="⚠️")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """One row per series: latest value, prior month, a year earlier (with fallback), preliminary flag."""
    if df.empty:
        return md.latest(df, "value", ["series_id"])
    df = df.assign(prelim=df["footnotes"].astype(str).str.contains("P"))
    return md.latest(df, "value", ["series_id"])


def _month(ts) -> str:
    return "—" if pd.isna(ts) else pd.Timestamp(ts).strftime("%B %Y")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def render():
    ui.header("Monthly Snapshot",
              "The latest monthly unemployment (LAUS) and payroll jobs (CES) data for Louisiana, its parishes and "
              "metros, compared with the U.S. and other states. More current than QCEW, less industry detail.")
    if not blsapi.api_key():
        st.info("**Add a free BLS API key for this page.** Without one, BLS allows 25 requests a day per "
                "network address, and hosted apps (including Streamlit Community Cloud) share addresses with other "
                "users, so the limit can run out before you visit. Register at data.bls.gov/registrationEngine, then "
                "add `BLS_API_KEY = \"your-key\"` under your Streamlit app's **Settings → Secrets**. Results are "
                "saved for 12 hours, and saved data is shown if BLS refuses a request.", icon="🔑")

    core = _get(core_ids(), "statewide series")
    if core.empty:
        st.error("No data returned from the BLS API. If the daily request limit was reached, try again tomorrow "
                 "or add a free API key (Data Notes & Help).")
        return
    s = summarize(core).set_index("series_id")
    names = core_ids()

    def row(sid):
        return s.loc[sid] if sid in s.index else None

    rate, lf, emp = row(f"LASST22{'0' * 11}03"), row(f"LASST22{'0' * 11}06"), row(f"LASST22{'0' * 11}05")
    us_rate, nf, us_nf = row("LNS14000000"), row("SMS22000000000000001"), row("CES0000000001")

    pills = []
    if rate is not None:
        pills.append(f"Unemployment data: {_month(rate['date'])}{' (preliminary)' if rate['prelim'] else ''}")
    if nf is not None:
        pills.append(f"Payroll jobs: {_month(nf['date'])}{' (preliminary)' if nf['prelim'] else ''}")
    st.markdown("".join(f'<span class="bx-pill">{p}</span>' for p in pills), unsafe_allow_html=True)
    st.write("")

    k = st.columns(5)
    if rate is not None:
        k[0].metric("LA unemployment", f"{rate['value']:.1f}%",
                    delta=f"{rate['mom']:+.1f} pts m/m" if pd.notna(rate["mom"]) else None,
                    delta_color="inverse", border=True, help="Seasonally adjusted.")
    if us_rate is not None and rate is not None:
        k[1].metric("U.S. unemployment", f"{us_rate['value']:.1f}%",
                    delta=f"LA {rate['value'] - us_rate['value']:+.1f} pts", delta_color="off", border=True)
    if nf is not None:
        k[2].metric("LA nonfarm jobs", f"{nf['value'] * 1000:,.0f}",
                    delta=f"{nf['mom'] * 1000:+,.0f} m/m" if pd.notna(nf["mom"]) else None, border=True,
                    help="Seasonally adjusted, CES.")
        k[3].metric("LA jobs YoY", f"{nf['yoy'] * 1000:+,.0f}" if pd.notna(nf["yoy"]) else "—",
                    delta=f"{nf['yoy_pct']:+.1f}% · U.S. {us_nf['yoy_pct']:+.1f}%" if us_nf is not None and pd.notna(nf["yoy_pct"]) else None,
                    delta_color="normal", border=True)
    if lf is not None:
        k[4].metric("LA labor force", f"{lf['value']:,.0f}", help="If BLS has no value for the same month last year, the change uses the latest month that has one.",
                    delta=f"{lf['yoy']:+,.0f} YoY" if pd.notna(lf["yoy"]) else None, border=True)

    if lf is not None and pd.notna(lf["yoy_date"]) and lf["yoy_date"] != lf["date"]:
        st.caption(f"Louisiana LAUS year-over-year changes compare {_month(lf['yoy_date'])} with a year earlier: BLS "
                   f"has no statewide value for the month a year before {_month(lf['date'])}.")
    tabs = st.tabs(["🏭 Jobs by sector", "📉 Unemployment", "🗺️ Parishes", "🏙️ Metros", "🇺🇸 States", "🎯 Watchlists"])
    with tabs[0]:
        _sectors(core, s, names)
    with tabs[1]:
        _unemployment(core)
    with tabs[2]:
        _parishes()
    with tabs[3]:
        _metros()
    with tabs[4]:
        _states(rate, nf)
    with tabs[5]:
        _watchlists()
    st.caption("Sources: BLS Local Area Unemployment Statistics (LAUS) and Current Employment Statistics (CES), via the "
               "BLS Public Data API. State figures are seasonally adjusted; parish and metro figures are not, so they "
               "are compared with the same month a year earlier. P = preliminary.")


def _sectors(core, s, names):
    rows = []
    for ind in LA_CES:
        sid = f"SMS2200000{ind}01"
        if sid in s.index:
            r = s.loc[sid]
            rows.append({"Sector": blsapi.CES_INDUSTRIES[ind], "Jobs": round(r["value"] * 1000),
                         "YoY change": round(r["yoy"] * 1000) if pd.notna(r["yoy"]) else np.nan,
                         "YoY %": r["yoy_pct"],
                         "Month change": round(r["mom"] * 1000) if pd.notna(r["mom"]) else np.nan,
                         "code": ind})
    t = pd.DataFrame(rows)
    if t.empty:
        st.info("No sector data.")
        return
    a, b = st.columns([1, 1])
    with a:
        sec = t[~t["code"].isin(["00000000", "05000000"])].sort_values("YoY change")
        fig = go.Figure(go.Bar(x=sec["YoY change"], y=sec["Sector"], orientation="h",
                               marker_color=np.where(sec["YoY change"] >= 0, ui.POS, ui.NEG),
                               text=sec["YoY %"].map(lambda v: f"{v:+.1f}%"), textposition="outside",
                               hovertemplate="%{y}<br>%{x:+,.0f} jobs<extra></extra>"))
        fig.update_traces(cliponaxis=False)
        fig.update_layout(title="Louisiana jobs by sector: change over the year", margin=dict(r=60))
        st.plotly_chart(ui.style_fig(fig, 460, legend=False), width="stretch")
    with b:
        st.dataframe(t.drop(columns="code"), hide_index=True, width="stretch", height=460,
                     column_config={"Jobs": st.column_config.NumberColumn(format="localized"),
                                    "Month change": st.column_config.NumberColumn(format="%+d"),
                                    "YoY change": st.column_config.NumberColumn(format="%+d"),
                                    "YoY %": st.column_config.NumberColumn(format="%+.1f%%")})
    d = core[core["series_id"].isin(["SMS22000000000000001", "CES0000000001"])].copy()
    d["name"] = d["series_id"].map({"SMS22000000000000001": "Louisiana", "CES0000000001": "United States"})
    base = d.groupby("name")["value"].transform("first")
    d["index"] = d["value"] / base * 100
    fig = px.line(d, x="date", y="index", color="name", color_discrete_map=ui.color_map(["Louisiana", "United States"]),
                  labels={"index": f"Index ({d['date'].min():%b %Y} = 100)", "date": "", "name": ""})
    fig.update_layout(title="Total nonfarm jobs, Louisiana vs. U.S. (seasonally adjusted)")
    st.plotly_chart(ui.style_fig(fig, 360), width="stretch")
    st.caption("Monthly CES estimates are survey-based and get revised; each March they are benchmarked to QCEW counts.")


def _unemployment(core):
    d = core[core["series_id"].isin([f"LASST22{'0' * 11}03", "LNS14000000"])].copy()
    d["name"] = np.where(d["series_id"] == "LNS14000000", "United States", "Louisiana")
    fig = px.line(d, x="date", y="value", color="name", markers=True,
                  color_discrete_map=ui.color_map(["Louisiana", "United States"]),
                  labels={"value": "Unemployment rate (%)", "date": "", "name": ""})
    fig.update_layout(title="Unemployment rate (seasonally adjusted)")
    st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
    lf = core[core["series_id"].isin([f"LASST22{'0' * 11}06", f"LASST22{'0' * 11}05"])].copy()
    lf["name"] = np.where(lf["series_id"].str.endswith("06"), "Labor force", "Employed residents")
    fig = px.line(lf, x="date", y="value", color="name", color_discrete_sequence=[ui.LA_COLOR, "#F59E0B"],
                  labels={"value": "People", "date": "", "name": ""})
    fig.update_layout(title="Louisiana labor force and employed residents (household survey basis)")
    st.plotly_chart(ui.style_fig(fig, 340), width="stretch")


def _parishes():
    ids = parish_ids()
    df = _get(ids, "parish unemployment rates")
    s = summarize(df)
    if s.empty:
        st.info("No parish data returned.")
        return
    s["area_fips"] = s["series_id"].map(ids)
    s["geo"] = s["area_fips"].map(C.LA_PARISHES)
    s["status"] = ""
    month = s["date"].max()
    st.markdown(f"**Parish unemployment rates, {_month(month)}** (not seasonally adjusted"
                f"{', preliminary' if s['prelim'].any() else ''})")
    metric = st.segmented_control("Map", ["value", "yoy"], default="value", key="mo_par_metric",
                                  format_func={"value": "Unemployment rate", "yoy": "Change vs. a year ago (pts)"}.get) or "value"
    a, b = st.columns([3, 2])
    with a:
        if metric == "value":
            fig = ui.parish_map(s, "value", f"Unemployment rate, {_month(month)} (%)", fmt=".1f")
        else:
            # Higher unemployment is bad, so flip the sign for a red = worse map.
            fig = ui.parish_map(s.assign(better=-s["yoy"]), "better",
                                "Change in unemployment rate vs. a year ago (blue = improved)", fmt="+.1f", diverging=True)
        if fig is not None:
            st.plotly_chart(fig, width="stretch")
    with b:
        st.dataframe(s.sort_values("value", ascending=False)[["geo", "value", "yoy", "prev"]], hide_index=True,
                     width="stretch", height=560,
                     column_config={"geo": "Parish", "value": st.column_config.NumberColumn("Rate %", format="%.1f"),
                                    "yoy": st.column_config.NumberColumn("vs. year ago (pts)", format="%+.1f"),
                                    "prev": st.column_config.NumberColumn("Prior month %", format="%.1f")})
    ui.download(s.drop(columns=["status"]), f"parish_unemployment_{month:%Y_%m}", key="dl_mo_par")


def _metros():
    ids = metro_ids()
    df = _get(ids, "metro series")
    s = summarize(df)
    if s.empty:
        st.info("No metro data returned.")
        return
    s["code"] = s["series_id"].map(lambda x: ids[x][0])
    s["kind"] = s["series_id"].map(lambda x: ids[x][1])
    s["Metro"] = s["code"].map(lambda c: C.LA_METROS[c][0].replace(" MSA", ""))
    rate = s[s["kind"] == "rate"].set_index("Metro")
    jobs = s[s["kind"] == "jobs"].set_index("Metro")
    t = pd.DataFrame({"Unemployment rate %": rate["value"], "Rate vs. year ago (pts)": rate["yoy"],
                      "Nonfarm jobs": (jobs["value"] * 1000).round(), "Jobs YoY": (jobs["yoy"] * 1000).round(),
                      "Jobs YoY %": jobs["yoy_pct"]}).reset_index().rename(columns={"index": "Metro"})
    a, b = st.columns(2)
    with a:
        d = t.dropna(subset=["Jobs YoY %"]).sort_values("Jobs YoY %")
        fig = go.Figure(go.Bar(x=d["Jobs YoY %"], y=d["Metro"], orientation="h",
                               marker_color=np.where(d["Jobs YoY %"] >= 0, ui.POS, ui.NEG),
                               text=d["Jobs YoY"].map(lambda v: f"{v:+,.0f}"), textposition="outside", cliponaxis=False))
        fig.update_layout(title=f"Nonfarm job growth vs. a year ago ({_month(jobs['date'].max()) if not jobs.empty else ''})")
        st.plotly_chart(ui.style_fig(fig, 420, legend=False), width="stretch")
    with b:
        d = t.dropna(subset=["Unemployment rate %"]).sort_values("Unemployment rate %")
        fig = px.bar(d, x="Unemployment rate %", y="Metro", orientation="h", color_discrete_sequence=[ui.LA_COLOR])
        fig.update_layout(title=f"Unemployment rate ({_month(rate['date'].max()) if not rate.empty else ''})")
        st.plotly_chart(ui.style_fig(fig, 420, legend=False), width="stretch")
    st.dataframe(t, hide_index=True, width="stretch",
                 column_config={"Unemployment rate %": st.column_config.NumberColumn(format="%.1f"),
                                "Rate vs. year ago (pts)": st.column_config.NumberColumn(format="%+.1f"),
                                "Nonfarm jobs": st.column_config.NumberColumn(format="localized"),
                                "Jobs YoY": st.column_config.NumberColumn(format="%+d"),
                                "Jobs YoY %": st.column_config.NumberColumn(format="%+.1f%%")})
    st.caption("Metro figures are not seasonally adjusted. Metros use current BLS definitions (Monroe includes Richland Parish).")


def _states(rate, nf):
    st.markdown("Rank Louisiana among all states on unemployment and job growth.")
    if not st.toggle("Load all-state rankings", key="mo_states",
                     help=f"Uses {blsapi.requests_needed(len(state_ids()))} API requests on first load; saved for 12 hours."):
        return
    ids = state_ids()
    s = summarize(_get(ids, "state series"))
    if s.empty:
        st.info("No state data returned.")
        return
    s["fips"] = s["series_id"].map(lambda x: ids[x][0])
    s["kind"] = s["series_id"].map(lambda x: ids[x][1])
    s["geo"] = s["fips"].map(lambda f: C.STATES[f][0])
    s["area_fips"] = s["fips"] + "000"
    r = s[s["kind"] == "rate"].sort_values("value").reset_index(drop=True)
    j = s[s["kind"] == "jobs"].sort_values("yoy_pct", ascending=False).reset_index(drop=True)
    la_r = r.index[r["fips"] == "22"]
    la_j = j.index[j["fips"] == "22"]
    k = st.columns(2)
    if len(la_r):
        k[0].metric("LA unemployment rank (1 = lowest)", f"#{la_r[0] + 1} of {len(r)}", border=True)
    if len(la_j):
        k[1].metric("LA job-growth rank (1 = fastest)", f"#{la_j[0] + 1} of {len(j)}", border=True)
    a, b = st.columns(2)
    with a:
        st.plotly_chart(ui.state_map(r, "value", f"Unemployment rate, {_month(r['date'].max())} (%)", fmt=".1f"),
                        width="stretch")
    with b:
        st.plotly_chart(ui.state_map(j, "yoy_pct", f"Nonfarm job growth YoY, {_month(j['date'].max())} (%)",
                                     fmt="+.2f", diverging=True), width="stretch")
    colors = [ui.LA_COLOR if f == "22" else ("#F59E0B" if f in C.LA_NEIGHBORS else "#CBD5E1") for f in j["fips"]]
    fig = px.bar(j, x="geo", y="yoy_pct", labels={"yoy_pct": "Jobs YoY %", "geo": ""})
    fig.update_traces(marker_color=colors)
    fig.update_layout(title="Job growth by state (Louisiana blue; TX, AR, MS amber)")
    st.plotly_chart(ui.style_fig(fig, 400, legend=False), width="stretch")


def _watchlists():
    lists = G.load_watchlists()
    ids = parish_ids()
    df = _get(ids, "parish unemployment rates")
    if df.empty or not lists:
        st.info("No data or no watchlists.")
        return
    name = st.selectbox("Watchlist", list(lists), key="mo_wl")
    parishes = lists[name]["parishes"]
    inv = {v: k for k, v in ids.items()}
    d = df[df["series_id"].isin([inv[p] for p in parishes if p in inv])].copy()
    d["Parish"] = d["series_id"].map(ids).map(C.LA_PARISHES)
    fig = px.line(d, x="date", y="value", color="Parish", color_discrete_sequence=ui.PALETTE,
                  labels={"value": "Unemployment rate (%)", "date": "", "Parish": ""})
    fig.update_layout(title=f"Unemployment rate · {name} (not seasonally adjusted)")
    st.plotly_chart(ui.style_fig(fig, 420), width="stretch")
    s = summarize(d.drop(columns="Parish"))
    s["Parish"] = s["series_id"].map(ids).map(C.LA_PARISHES)
    st.dataframe(s[["Parish", "date", "value", "yago", "yoy"]], hide_index=True, width="stretch",
                 column_config={"date": st.column_config.DateColumn("Month", format="MMM YYYY"),
                                "value": st.column_config.NumberColumn("Rate %", format="%.1f"),
                                "yago": st.column_config.NumberColumn("Year ago %", format="%.1f"),
                                "yoy": st.column_config.NumberColumn("Change (pts)", format="%+.1f")})
