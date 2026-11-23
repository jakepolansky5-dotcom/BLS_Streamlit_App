"""Current conditions from monthly BLS data (LAUS + CES) for any geography.

LAUS (labor force, employed, unemployed, unemployment rate) is published for
the U.S., states, parishes and metros. Custom regions and LA micro/combined
areas are built by summing parish labor force, employed and unemployed, and the
rate is recomputed from those sums (the same way BLS builds area totals).

CES (payroll jobs by industry) exists for the U.S., states and metro areas
only; it is not published for parishes or custom regions.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from . import blsapi
from . import config as C

MEASURES = {"03": "rate", "04": "unemployed", "05": "employed", "06": "labor_force"}


def laus_plan(geo) -> dict | None:
    """{measure: [series ids to sum]} or None if LAUS isn't available."""
    single = blsapi.laus_id(geo, "06") if geo.kind in ("us", "state", "county") else None
    if geo.kind == "metro" and geo.key.replace("LA-", "") in C.LA_METROS:
        single = blsapi.laus_id(geo, "06")
    if single:
        return {m: [blsapi.laus_id(geo, m)] for m in MEASURES}
    if all(c in C.LA_PARISHES for c in geo.codes):
        return {m: [f"LAUCN{c}{'0' * 8}{m}" for c in geo.codes] for m in ("04", "05", "06")}
    return None


def ces_plan(geo, industries=("00000000",)) -> dict:
    """{industry: series id} for geos where CES exists (U.S., states, LA metros)."""
    out = {}
    for ind in industries:
        sid = blsapi.ces_id(geo, ind, seasonal=geo.kind in ("us", "state"))
        if sid:
            out[ind] = sid
    return out


def _fetch(ids: list[str], years: int) -> tuple[pd.DataFrame, list]:
    y1 = date.today().year
    return blsapi.fetch_series(tuple(sorted(set(ids))), y1 - years, y1)


def laus_series(geos: list, years: int = 3) -> tuple[pd.DataFrame, list]:
    """Monthly long frame: geo, date, labor_force, employed, unemployed, rate."""
    plans = {g.key: laus_plan(g) for g in geos}
    ids = [s for p in plans.values() if p for lst in p.values() for s in lst]
    if not ids:
        return pd.DataFrame(), []
    raw, msgs = _fetch(ids, years)
    if raw.empty:
        return pd.DataFrame(), msgs
    raw = raw.set_index("series_id")
    frames = []
    for g in geos:
        plan = plans[g.key]
        if not plan:
            continue
        cols = {}
        n_parts = {}
        for m, sids in plan.items():
            have = [s for s in sids if s in raw.index]
            if not have:
                continue
            part = raw.loc[have].reset_index()
            piv = part.pivot_table(index="date", columns="series_id", values="value")
            cols[MEASURES[m]] = piv.sum(axis=1, min_count=1)
            n_parts[MEASURES[m]] = piv.notna().sum(axis=1)
            cols[MEASURES[m]] = cols[MEASURES[m]].where(n_parts[MEASURES[m]] == len(sids))
        if not cols:
            continue
        f = pd.DataFrame(cols)
        if "rate" not in f and {"unemployed", "labor_force"} <= set(f):
            f["rate"] = (f["unemployed"] / f["labor_force"] * 100).round(1)
        prelim = raw.loc[[s for sids in plan.values() for s in sids if s in raw.index]]
        last_prelim = prelim[prelim["footnotes"].astype(str).str.contains("P")]["date"]
        f["prelim"] = f.index.isin(set(last_prelim))
        f["geo"], f["geo_key"] = g.name, g.key
        f["seasonal"] = "SA" if g.kind in ("us", "state") else "NSA"
        frames.append(f.reset_index().rename(columns={"index": "date"}))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df, msgs


def ces_series(geos: list, industries: list[str], years: int = 3) -> tuple[pd.DataFrame, list]:
    """Monthly long frame: geo, industry, date, jobs (persons)."""
    plans = {g.key: ces_plan(g, industries) for g in geos}
    ids = [s for p in plans.values() for s in p.values()]
    if not ids:
        return pd.DataFrame(), []
    raw, msgs = _fetch(ids, years)
    if raw.empty:
        return pd.DataFrame(), msgs
    rev = {sid: (gk, ind) for gk, p in plans.items() for ind, sid in p.items()}
    names = {g.key: g.name for g in geos}
    raw = raw[raw["series_id"].isin(rev)].copy()
    raw["geo_key"] = raw["series_id"].map(lambda s: rev[s][0])
    raw["geo"] = raw["geo_key"].map(names)
    raw["industry_code"] = raw["series_id"].map(lambda s: rev[s][1])
    raw["industry"] = raw["industry_code"].map(blsapi.CES_INDUSTRIES)
    raw["jobs"] = raw["value"] * 1000
    raw["prelim"] = raw["footnotes"].astype(str).str.contains("P")
    return raw, msgs


def latest(df: pd.DataFrame, value: str, by: list[str]) -> pd.DataFrame:
    """Latest month per group with prior-month and year-ago values.

    If BLS has no value for the same month a year earlier (it skipped some months,
    e.g. state LAUS for October 2025), the year-over-year change falls back to the
    most recent month that does have a year-earlier value; `yoy_date` says which.
    """
    cols = [*by, "date", "value", "prev", "yago", "prelim", "yoy_date"]
    if df.empty or value not in df:
        return pd.DataFrame(columns=[*cols, "mom", "yoy", "yoy_pct"])
    rows = []
    for key, g in df.dropna(subset=[value]).groupby(by):
        g = g.set_index("date").sort_index()
        ser = g[value]
        last = ser.index.max()
        r = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        r.update({"date": last, "value": ser[last], "prev": ser.get(last - pd.DateOffset(months=1), np.nan),
                  "prelim": bool(g.loc[last].get("prelim", False)), "yago": np.nan, "yoy_date": pd.NaT,
                  "yoy_now": np.nan})
        for d in ser.index[::-1][:6]:
            ya = ser.get(d - pd.DateOffset(years=1), np.nan)
            if pd.notna(ya):
                r.update({"yago": ya, "yoy_date": d, "yoy_now": ser[d]})
                break
        rows.append(r)
    out = pd.DataFrame(rows)
    out["mom"] = out["value"] - out["prev"]
    out["yoy"] = out["yoy_now"] - out["yago"]
    out["yoy_pct"] = np.where(out["yago"] > 0, out["yoy"] / out["yago"] * 100, np.nan)
    return out.drop(columns="yoy_now")


def conditions_table(geos: list, years: int = 2) -> tuple[pd.DataFrame, list]:
    """One row per geo: unemployment rate, labor force, employed and payroll jobs, latest + YoY."""
    laus, m1 = laus_series(geos, years)
    ces, m2 = ces_series(geos, ["00000000"], years)
    rows = {g.key: {"geo": g.name} for g in geos}
    if not laus.empty:
        for col, label in (("rate", "rate"), ("labor_force", "lf"), ("employed", "emp")):
            lt = latest(laus, col, ["geo_key"]).set_index("geo_key")
            for k, r in lt.iterrows():
                rows[k][f"{label}"] = r["value"]
                rows[k][f"{label}_yoy"] = r["yoy"]
                rows[k][f"{label}_yoy_pct"] = r["yoy_pct"]
                rows[k]["laus_month"] = r["date"]
                if pd.notna(r["yoy_date"]) and r["yoy_date"] != r["date"]:
                    rows[k]["laus_yoy_month"] = r["yoy_date"]
        sa = laus.groupby("geo_key")["seasonal"].first()
        for k, v in sa.items():
            rows[k]["seasonal"] = v
    if not ces.empty:
        lt = latest(ces, "jobs", ["geo_key"]).set_index("geo_key")
        for k, r in lt.iterrows():
            rows[k].update({"jobs": r["value"], "jobs_yoy": r["yoy"], "jobs_yoy_pct": r["yoy_pct"],
                            "jobs_mom": r["mom"], "ces_month": r["date"]})
    return pd.DataFrame(rows.values()), list(dict.fromkeys(m1 + m2))


def show_messages(msgs):
    for m in msgs:
        if "does not exist" in m or "No Data Available" in m:
            continue
        st.warning(m, icon="⚠️")


def _m(ts) -> str:
    return "—" if ts is None or pd.isna(ts) else pd.Timestamp(ts).strftime("%b %Y")


def render_strip(geo, title: str = "Current conditions (monthly)"):
    """KPI row from LAUS + CES for one geography. Returns True if anything was shown."""
    if laus_plan(geo) is None and not ces_plan(geo):
        return False
    with st.spinner("Loading latest monthly data (LAUS/CES)…"):
        t, msgs = conditions_table([geo])
    show_messages(msgs)
    if t.empty or t.drop(columns="geo").dropna(how="all").empty:
        return False
    r = t.iloc[0]
    when = []
    if pd.notna(r.get("laus_month")):
        when.append(f"unemployment: {_m(r['laus_month'])}"
                    + (" (seasonally adjusted)" if r.get("seasonal") == "SA" else " (not seasonally adjusted)"))
    if pd.notna(r.get("ces_month")):
        when.append(f"payroll jobs: {_m(r['ces_month'])}")
    yoy_note = ""
    if pd.notna(r.get("laus_yoy_month")):
        yoy_note = f" Unemployment changes use {_m(r['laus_yoy_month'])} (BLS has no value for the same month a year before {_m(r['laus_month'])})."
    st.markdown(f"##### 🗓️ {title}")
    st.caption("Latest BLS monthly data, " + "; ".join(when) + ". Changes are vs. the same month a year earlier." + yoy_note)
    k = st.columns(4)
    if pd.notna(r.get("rate")):
        k[0].metric("Unemployment rate", f"{r['rate']:.1f}%",
                    delta=f"{r['rate_yoy']:+.1f} pts YoY" if pd.notna(r.get("rate_yoy")) else None,
                    delta_color="inverse", border=True)
    if pd.notna(r.get("lf")):
        k[1].metric("Labor force", f"{r['lf']:,.0f}",
                    delta=f"{r['lf_yoy_pct']:+.1f}% YoY" if pd.notna(r.get("lf_yoy_pct")) else None, border=True)
    if pd.notna(r.get("emp")):
        k[2].metric("Employed residents", f"{r['emp']:,.0f}",
                    delta=f"{r['emp_yoy']:+,.0f} YoY" if pd.notna(r.get("emp_yoy")) else None, border=True)
    if pd.notna(r.get("jobs")):
        k[3].metric("Payroll jobs (CES)", f"{r['jobs']:,.0f}",
                    delta=f"{r['jobs_yoy']:+,.0f} ({r['jobs_yoy_pct']:+.1f}%) YoY" if pd.notna(r.get("jobs_yoy")) else None,
                    border=True)
    else:
        k[3].metric("Payroll jobs (CES)", "n/a", border=True,
                    help="BLS publishes monthly payroll jobs for states and metro areas, not parishes or custom "
                         "regions. Use QCEW below for parish-level jobs.")
    return True
