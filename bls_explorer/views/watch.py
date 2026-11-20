"""Project Watch — track a group of parishes and industries against a baseline.

Built for questions like "what has data-center construction done to jobs and
wages in Richland Parish and its neighbors since early 2024?"
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .. import config as C
from .. import geo as G
from .. import qcew
from .. import ui


def _editor(lists: dict) -> tuple[str, dict]:
    names = list(lists) + ["➕ New watchlist…"]
    choice = st.selectbox("Watchlist", names, key="pw_choice")
    if choice != "➕ New watchlist…":
        wl = lists[choice]
        with st.expander("✏️ Edit / save as new", expanded=False):
            _edit_form(choice, wl, existing=True)
        return choice, wl
    _edit_form("", {"parishes": [], "industries": C.INDUSTRY_BUNDLES["Data center construction & operations"],
                    "baseline": "2024Q1", "notes": ""}, existing=False)
    st.stop()


def _edit_form(name, wl, existing):
    with st.form(f"pw_form_{name or 'new'}"):
        new_name = st.text_input("Name", value=name if existing and not wl.get("builtin") else
                                 (f"{name} (copy)" if name else ""))
        parishes = st.multiselect("Parishes", list(C.LA_PARISHES), default=wl["parishes"], format_func=C.LA_PARISHES.get)
        opts = ui.industry_options()
        inds = st.multiselect("Industries", opts, default=[i for i in wl["industries"] if i in opts],
                              format_func=qcew.industry_label)
        periods = qcew.available_periods("Q")
        base_keys = [p.key for p in periods]
        base = st.selectbox("Baseline quarter (before the project)", base_keys,
                            index=base_keys.index(wl["baseline"]) if wl["baseline"] in base_keys else min(8, len(base_keys) - 1))
        notes = st.text_area("Notes", value=wl.get("notes", ""))
        c1, c2 = st.columns(2)
        save = c1.form_submit_button("💾 Save watchlist", type="primary")
        delete = c2.form_submit_button("🗑️ Delete", disabled=not existing or wl.get("builtin", False))
    if save:
        if not new_name or not parishes or not inds:
            st.error("Name, parishes and industries are required.")
        else:
            try:
                G.save_watchlist(new_name, parishes, inds, base, notes)
                st.session_state["pw_choice"] = new_name
                st.success("Saved to watchlists.json.")
                st.rerun()
            except OSError as exc:
                st.error(f"Could not write watchlists.json ({exc}). On read-only hosting, add the watchlist "
                         "to WATCHLIST_PRESETS in bls_explorer/config.py instead.")
    if delete:
        G.delete_watchlist(name)
        st.session_state.pop("pw_choice", None)
        st.rerun()


def render():
    ui.header("Project Watch",
              "Track jobs, establishments and wages in a group of parishes against a pre-project baseline, "
              "benchmarked against Louisiana and the U.S.")
    lists = G.load_watchlists()
    name, wl = _editor(lists)
    if wl.get("notes"):
        st.caption("📝 " + wl["notes"])

    info = qcew.latest_periods()
    latest = info["quarter"]
    baseline = qcew.Period.parse(wl["baseline"])
    c1, c2, c3 = st.columns(3)
    own = c1.selectbox("Ownership", list(C.OWNERSHIPS), index=list(C.OWNERSHIPS).index("5"),
                       format_func=C.OWNERSHIPS.get, key="pw_own")
    lookback = c2.slider("Quarters of history before baseline", 0, 12, 4, key="pw_lookback")
    compare_q = c3.selectbox("Compare latest against", ["Baseline", "Same quarter last year"], key="pw_cmp")
    start = baseline
    for _ in range(lookback):
        start = start.prev_quarter()
    periods = qcew.quarter_range(start, latest)

    parishes = [G.parish(p) for p in wl["parishes"]]
    region = G.region(name, wl["parishes"])
    inds = list(dict.fromkeys(["10", *wl["industries"]]))
    df = ui.load([region, *parishes, G.LOUISIANA, G.US], periods, inds, own)
    if df.empty:
        st.warning("No data.")
        return
    df["industry"] = df["industry_code"].map(qcew.industry_label)
    ref = baseline if compare_q == "Baseline" else latest.shift_years(-1)

    st.markdown(f'<span class="bx-pill">Latest: {latest.label}</span><span class="bx-pill">Reference: {ref.label}</span>'
                f'<span class="bx-pill">{len(parishes)} parishes</span><span class="bx-pill">{C.OWNERSHIPS[own]}</span>',
                unsafe_allow_html=True)

    # ---- headline KPIs ---------------------------------------------------------
    def val(geo_key, ind, p, col="emp"):
        r = df[(df["geo_key"] == geo_key) & (df["industry_code"] == ind) & (df["period_key"] == p.key)]
        return r[col].iloc[0] if not r.empty else np.nan

    k = st.columns(4)
    for i, (ind, label) in enumerate([("10", "All industries"), ("23", "Construction")]):
        if ind not in inds:
            continue
        now, then = val(region.key, ind, latest), val(region.key, ind, ref)
        k[i].metric(f"{label} jobs (region)", ui.fnum(now),
                    delta=f"{ui.fdelta(now - then)} ({ui.fpct((now / then - 1) * 100 if then else np.nan)}) vs {ref.label}"
                    if pd.notna(now) and pd.notna(then) else None, border=True)
    w_now, w_then = val(region.key, "10", latest, "avg_wkly_wage"), val(region.key, "10", ref, "avg_wkly_wage")
    k[2].metric("Avg weekly wage (all industries)", ui.fmoney(w_now),
                delta=f"{ui.fpct((w_now / w_then - 1) * 100)} vs {ref.label}" if w_then else None, border=True)
    e_now, e_then = val(region.key, "10", latest, "estabs"), val(region.key, "10", ref, "estabs")
    k[3].metric("Establishments", ui.fnum(e_now),
                delta=f"{ui.fdelta(e_now - e_then)} vs {ref.label}" if pd.notna(e_then) else None, border=True)

    tabs = st.tabs(["📈 Monthly jobs", "🧱 Parish × industry", "⚖️ vs. Louisiana & U.S.", "💵 Wages", "🆕 Latest quarter"])

    # ---- monthly chart -----------------------------------------------------
    with tabs[0]:
        view = st.segmented_control("View", ["Region by industry", "One industry by parish"], default="Region by industry",
                                    key="pw_view") or "Region by industry"
        m = qcew.monthly(df)
        m["industry"] = m["industry_code"].map(qcew.industry_label)
        if view == "Region by industry":
            sel = st.multiselect("Industries", inds, default=[i for i in inds if i != "10"][:6],
                                 format_func=qcew.industry_label, key="pw_m_inds")
            d = m[(m["geo_key"] == region.key) & m["industry_code"].isin(sel)]
            color = "industry"
        else:
            ind = st.selectbox("Industry", inds, index=inds.index("23") if "23" in inds else 0,
                               format_func=qcew.industry_label, key="pw_m_ind")
            d = m[m["geo_key"].isin([p.key for p in parishes]) & (m["industry_code"] == ind)]
            color = "geo"
        stacked = st.toggle("Stacked area", value=False, key="pw_stack")
        d = d.assign(note=d["status"].replace({"Partial": "partial: excludes suppressed parishes", "": "complete"}))
        fig = (px.area if stacked else px.line)(d, x="date", y="emp", color=color, hover_data={"note": True},
                                                 color_discrete_sequence=ui.PALETTE,
                                                 labels={"emp": "Employment", "date": "", "industry": "", "geo": ""})
        fig.add_vline(x=baseline.end_date, line_dash="dash", line_color="gray")
        fig.add_annotation(x=baseline.end_date, y=1, yref="paper", text="baseline", showarrow=False, yanchor="bottom")
        fig.update_layout(title=f"Monthly employment · {name}")
        st.plotly_chart(ui.style_fig(fig, 480), width="stretch")
        gaps = d[d["status"] == "Suppressed"]["geo"].unique()
        if len(gaps):
            st.caption("Gaps = suppressed values (" + ", ".join(gaps) + ").")
        last = d[d["date"] == d["date"].max()]
        partial = last.loc[last["status"] == "Partial", color].unique()
        if len(partial):
            st.caption("◐ Partial in the latest month (some parishes suppressed, so values are minimums and drops can "
                       "reflect suppression rather than job loss): " + "; ".join(map(str, partial))
                       + ". Hover a line for each point's status, or check the parent industry.")

    # ---- parish × industry matrix ---------------------------------------------
    with tabs[1]:
        measure = st.segmented_control("Cell value", ["Change in jobs", "% change", "Jobs (latest)"], default="Change in jobs",
                                       key="pw_cell") or "Change in jobs"
        geo_keys = [region.key] + [p.key for p in parishes]
        now = df[(df["period_key"] == latest.key) & df["geo_key"].isin(geo_keys)].set_index(["geo", "industry"])
        then = df[(df["period_key"] == ref.key) & df["geo_key"].isin(geo_keys)].set_index(["geo", "industry"])
        mat = pd.DataFrame({"now": now["emp"], "then": then["emp"], "status_now": now["status"],
                            "status_then": then["status"]})
        mat["chg"] = mat["now"] - mat["then"]
        mat["pct"] = np.where(mat["then"] > 0, mat["chg"] / mat["then"] * 100, np.nan)
        col = {"Change in jobs": "chg", "% change": "pct", "Jobs (latest)": "now"}[measure]
        piv = mat[col].unstack("industry")
        order = [g.name for g in [region, *parishes] if g.name in piv.index]
        piv = piv.reindex(order)[[i for i in map(qcew.industry_label, inds) if i in piv.columns]]
        # Cell state: a row with no value is suppressed; no row at all means no establishments.
        supp = (mat["status_now"].eq("Suppressed") | mat["status_then"].eq("Suppressed")).unstack("industry") \
            .reindex_like(piv).fillna(False)
        partial = (mat["status_now"].eq("Partial") | mat["status_then"].eq("Partial")).unstack("industry") \
            .reindex_like(piv).fillna(False)
        text = piv.copy().astype(object)
        for r in piv.index:
            for c in piv.columns:
                v = piv.loc[r, c]
                if pd.isna(v):
                    text.loc[r, c] = "🔒" if supp.loc[r, c] else "—"
                else:
                    text.loc[r, c] = (f"{v:+,.0f}" if col == "chg" else f"{v:+.0f}%" if col == "pct" else f"{v:,.0f}") + \
                                     ("*" if partial.loc[r, c] else "")
        lim = np.nanpercentile(np.abs(piv.to_numpy(dtype=float)), 90) if np.isfinite(piv.to_numpy(dtype=float)).any() else 1
        fig = go.Figure(go.Heatmap(z=piv.to_numpy(dtype=float), x=[c.split(" – ")[0] + " " + c.split(" – ")[-1][:28] for c in piv.columns],
                                   y=piv.index, text=text.to_numpy(), texttemplate="%{text}",
                                   colorscale="RdBu" if col != "now" else "Blues", zmid=0 if col != "now" else None,
                                   zmin=-lim if col != "now" else None, zmax=lim if col != "now" else None,
                                   hovertemplate="%{y}<br>%{x}<br>%{text}<extra></extra>", showscale=False))
        fig.update_layout(title=f"{measure}: {ref.label} → {latest.label}", xaxis_tickangle=-35)
        st.plotly_chart(ui.style_fig(fig, height=140 + 48 * len(piv), legend=False), width="stretch")
        st.caption("🔒 suppressed by BLS · — no establishments · * partial (excludes suppressed ownerships/parishes). "
                   "Suppressed detail often still shows up in the parent industry (e.g. Construction 23).")
        out = mat.reset_index()
        ui.download(out, f"watch_matrix_{latest.key}", key="dl_pw_mat")

    # ---- benchmarks ------------------------------------------------------------
    with tabs[2]:
        rows = []
        for ind in inds:
            r = {"industry": qcew.industry_label(ind)}
            for g in (region, G.LOUISIANA, G.US):
                a, b = val(g.key, ind, latest), val(g.key, ind, ref)
                r[g.name] = (a / b - 1) * 100 if pd.notna(a) and pd.notna(b) and b > 0 else np.nan
            r["Region jobs added"] = val(region.key, ind, latest) - val(region.key, ind, ref)
            rows.append(r)
        bench = pd.DataFrame(rows)
        bench["Region minus LA (pts)"] = bench[region.name] - bench["Louisiana"]
        st.dataframe(bench, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(c + (" %" if c in (region.name, "Louisiana", "United States") else ""),
                                                                     format="%+.1f") for c in bench.columns if c != "industry"} | {"industry": "Industry"})
        ind = st.selectbox("Index chart industry", inds, index=inds.index("23") if "23" in inds else 0,
                           format_func=qcew.industry_label, key="pw_bench_ind")
        d = df[(df["industry_code"] == ind) & df["geo_key"].isin([region.key, "22000", "US000"])].sort_values("date").copy()
        base_vals = d[d["period_key"] == baseline.key].set_index("geo")["emp"]
        d["index"] = d["emp"] / d["geo"].map(base_vals) * 100
        fig = px.line(d, x="date", y="index", color="geo", markers=True,
                      color_discrete_map={region.name: "#F59E0B", "Louisiana": ui.LA_COLOR, "United States": ui.US_COLOR},
                      labels={"index": f"Index ({baseline.label} = 100)", "date": "", "geo": ""})
        fig.add_hline(y=100, line_dash="dot", line_color="gray")
        fig.update_layout(title=f"{qcew.industry_label(ind)} — indexed to baseline")
        st.plotly_chart(ui.style_fig(fig, 420), width="stretch")

    # ---- wages -------------------------------------------------------------------
    with tabs[3]:
        ind = st.selectbox("Industry", inds, index=0, format_func=qcew.industry_label, key="pw_wage_ind")
        geo_opts = [region.key] + [p.key for p in parishes] + ["22000"]
        d = df[(df["industry_code"] == ind) & df["geo_key"].isin(geo_opts)].sort_values("date")
        fig = px.line(d, x="date", y="avg_wkly_wage", color="geo", markers=True, color_discrete_sequence=ui.PALETTE,
                      labels={"avg_wkly_wage": "Average weekly wage ($)", "date": "", "geo": ""})
        fig.add_vline(x=baseline.end_date, line_dash="dash", line_color="gray")
        fig.update_layout(title=f"Average weekly wage · {qcew.industry_label(ind)}")
        st.plotly_chart(ui.style_fig(fig, 440), width="stretch")
        tw = df[(df["industry_code"] == ind) & (df["geo_key"] == region.key)].sort_values("date")
        fig = px.bar(tw, x="period", y="wages", labels={"wages": "Total quarterly wages ($)", "period": ""})
        fig.update_layout(title="Total wages paid in the region (payroll injected into the local economy)")
        st.plotly_chart(ui.style_fig(fig, 340, legend=False), width="stretch")

    # ---- latest quarter -----------------------------------------------------------
    with tabs[4]:
        prev_q = latest.prev_quarter()
        st.markdown(f"What the newest release (**{latest.label}**) shows versus the prior quarter and a year earlier.")
        now = df[df["period_key"] == latest.key]
        pq = df[df["period_key"] == prev_q.key].set_index(["geo_key", "industry_code"])["emp"]
        t = now[now["geo_key"].isin([region.key] + [p.key for p in parishes])].copy()
        t["qoq"] = t["emp"] - t.set_index(["geo_key", "industry_code"]).index.map(pq)
        t["flag"] = t.apply(ui.status_badge, axis=1)
        t = t.sort_values(["geo_key", "industry_code"])
        st.dataframe(t[["geo", "industry", "emp", "qoq", "emp_chg", "emp_pct", "avg_wkly_wage", "wage_pct", "flag"]],
                     hide_index=True, width="stretch", height=520,
                     column_config={"geo": "Geography", "industry": "Industry",
                                    "emp": st.column_config.NumberColumn("Jobs", format="localized"),
                                    "qoq": st.column_config.NumberColumn(f"vs {prev_q.label}", format="%+d"),
                                    "emp_chg": st.column_config.NumberColumn("YoY", format="%+d"),
                                    "emp_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%"),
                                    "avg_wkly_wage": st.column_config.NumberColumn("Avg wkly wage", format="dollar"),
                                    "wage_pct": st.column_config.NumberColumn("Wage YoY %", format="%+.1f%%"),
                                    "flag": "Data note"})
        st.caption("Quarter-over-quarter changes in QCEW include seasonal swings; YoY is the cleaner signal.")
    ui.download(df.drop(columns=[c for c in df.columns if c.startswith("_")]), f"watch_{latest.key}_all",
                label="⬇️ Download all watchlist data (CSV)", key="dl_pw_all")
