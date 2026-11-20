"""Shared Streamlit widgets, formatting and chart helpers."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from . import config as C
from . import geo as G
from . import qcew

LA_COLOR = "#2563EB"
US_COLOR = "#64748B"
PALETTE = ["#2563EB", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899",
           "#84CC16", "#F97316", "#0EA5E9", "#A855F7", "#14B8A6"]
POS, NEG = "#059669", "#DC2626"

METRICS = {
    "emp": "Employment",
    "emp_chg": "Employment change (YoY)",
    "emp_pct": "Employment change % (YoY)",
    "estabs": "Establishments",
    "estabs_pct": "Establishments change % (YoY)",
    "wages": "Total wages",
    "avg_wkly_wage": "Avg weekly wage",
    "wage_pct": "Avg weekly wage change % (YoY)",
    "lq": "Location quotient",
    "share": "Share of area employment (%)",
}


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def _bad(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x)


def fnum(x, digits=0) -> str:
    return "—" if _bad(x) else f"{x:,.{digits}f}"


def fmoney(x, digits=0) -> str:
    if _bad(x):
        return "—"
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    return f"${x:,.{digits}f}"


def fpct(x, digits=1, sign=True) -> str:
    return "—" if _bad(x) else (f"{x:+,.{digits}f}%" if sign else f"{x:,.{digits}f}%")


def fdelta(x, digits=0) -> str | None:
    return None if _bad(x) else f"{x:+,.{digits}f}"


def status_badge(row) -> str:
    if row.get("status") == "Suppressed":
        return "🔒 suppressed"
    if row.get("status") == "Partial":
        return f"◐ partial ({int(row.get('supp', 0))} of {int(row.get('parts', 0))} suppressed)"
    return ""


# ---------------------------------------------------------------------------
# Page chrome
# ---------------------------------------------------------------------------
CSS = """
<style>
  .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
  div[data-testid="stMetric"] {background: var(--secondary-background-color); border-radius: 10px;
       padding: 0.7rem 0.9rem;}
  div[data-testid="stMetricLabel"] p {font-size: 0.78rem; text-transform: uppercase; letter-spacing: .04em;}
  div[data-testid="stMetricValue"] {font-size: 1.55rem;}
  .bx-sub {color: #64748B; margin-top: -0.6rem; margin-bottom: 1rem; font-size: 0.95rem;}
  .bx-pill {display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem;
            background: rgba(37,99,235,.12); color: #2563EB; margin-right: 6px;}
</style>
"""


def header(title: str, subtitle: str = ""):
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.markdown(f'<div class="bx-sub">{subtitle}</div>', unsafe_allow_html=True)


def suppression_note(df: pd.DataFrame | None = None):
    if df is not None and not df.empty and "status" in df and not df["status"].isin(["Partial", "Suppressed"]).any():
        return
    st.caption("🔒 **Suppressed**: BLS withholds the value to protect employer confidentiality. "
               "◐ **Partial**: a regional or ownership total that excludes suppressed parts, so read it as a "
               "minimum. YoY changes are computed only over parts known in both years.")


# ---------------------------------------------------------------------------
# Pickers
# ---------------------------------------------------------------------------
def _custom_regions() -> dict:
    return st.session_state.setdefault("custom_regions", {})


def geo_catalogue() -> dict:
    """label -> Geo for every pre-built geography."""
    cat = {"United States": G.US}
    cat["Louisiana (statewide)"] = G.LOUISIANA
    for g in G.la_metros(include_micro=False):
        cat[f"LA metro · {g.name}"] = g
    for code in C.LA_MICROS:
        g = G.la_metro(code)
        cat[f"LA micro · {g.name}"] = g
    for code in C.LA_CSAS:
        g = G.la_metro(code)
        cat[f"LA combined · {g.name}"] = g
    for g in G.all_la_parishes():
        cat[f"Parish · {g.name}"] = g
    for name, wl in G.load_watchlists().items():
        cat[f"Watchlist · {name}"] = G.region(name, wl["parishes"])
    for name, codes in _custom_regions().items():
        cat[f"Custom · {name}"] = G.region(name, codes)
    for g in G.all_states():
        if g.codes[0] != "22000":
            cat[f"State · {g.name}"] = g
    for label, g in st.session_state.get("extra_geos", {}).items():
        cat[label] = g
    return cat


def custom_region_builder(key: str):
    with st.popover("➕ Build a region / add any county or metro", width="stretch"):
        tab_r, tab_c = st.tabs(["Custom parish region", "Other state county / metro"])
        with tab_r:
            name = st.text_input("Region name", key=f"{key}_rname", placeholder="e.g. Northeast Delta")
            parishes = st.multiselect("Parishes", list(C.LA_PARISHES), format_func=C.LA_PARISHES.get,
                                      key=f"{key}_rparishes")
            if st.button("Save region", key=f"{key}_rsave", disabled=not (name and parishes)):
                _custom_regions()[name] = list(parishes)
                st.success(f"Added “{name}”. It now appears in geography lists (this session).")
        with tab_c:
            st_fips = st.selectbox("State", [f for f in C.STATES if f != C.LA], format_func=lambda f: C.STATES[f][0],
                                   key=f"{key}_ost")
            kind = st.radio("Type", ["County", "Metro / micro area (BLS-published)"], horizontal=True, key=f"{key}_okind")
            if kind == "County":
                opts = G.counties_in_state(st_fips)
                code = st.selectbox("County", list(opts), format_func=opts.get, key=f"{key}_ocounty")
                g = G.county(code) if code else None
            else:
                opts = G.msas_in_state(C.STATES[st_fips][1])
                code = st.selectbox("Metro area", list(opts), format_func=opts.get, key=f"{key}_omsa")
                g = G.published_msa(code) if code else None
                st.caption("Published metro files can lag on industry detail for the newest quarter.")
            if st.button("Add", key=f"{key}_oadd", disabled=g is None):
                st.session_state.setdefault("extra_geos", {})[f"{'County' if kind == 'County' else 'Metro'} · {g.name}"] = g
                st.success(f"Added {g.name}.")


def geo_select(label: str, key: str, default: str = "Louisiana (statewide)", help=None) -> G.Geo:
    cat = geo_catalogue()
    labels = list(cat)
    idx = labels.index(default) if default in labels else 0
    choice = st.selectbox(label, labels, index=idx, key=key, help=help)
    return cat[choice]


def geo_multiselect(label: str, key: str, default: list[str], max_selections=None) -> list[G.Geo]:
    cat = geo_catalogue()
    labels = list(cat)
    if key in st.session_state:
        st.session_state[key] = [v for v in st.session_state[key] if v in labels]
        chosen = st.multiselect(label, labels, key=key, max_selections=max_selections)
    else:
        default = [d for d in default if d in labels]
        chosen = st.multiselect(label, labels, default=default, key=key, max_selections=max_selections)
    return [cat[c] for c in chosen]


def industry_options(levels=None) -> list[str]:
    titles = qcew.industry_titles()
    codes = [c for c in titles if c == "10" or (qcew.industry_level(c) in ("super", 2, 3, 4, 5, 6))]
    if levels:
        codes = [c for c in codes if qcew.industry_level(c) in levels or c == "10"]

    def sort_key(c):
        lvl = qcew.industry_level(c)
        if lvl == "total":
            return (0, c)
        if lvl == "super":
            return (1, c)
        return (2, c.replace("-", ""))
    return sorted(codes, key=sort_key)


def industry_select(label: str, key: str, default: str = "10", help=None) -> str:
    opts = industry_options()
    idx = opts.index(default) if default in opts else 0
    return st.selectbox(label, opts, index=idx, key=key, format_func=qcew.industry_label, help=help or
                        "Type a NAICS code or any word to search. Supersectors are 10xx codes.")


def industry_multiselect(label: str, key: str, default: list[str], bundle_picker: bool = True) -> list[str]:
    opts = industry_options()
    if bundle_picker:
        bundle = st.selectbox("Start from an industry bundle (optional)", ["—"] + list(C.INDUSTRY_BUNDLES),
                              key=f"{key}_bundle")
        if bundle != "—" and st.session_state.get(f"{key}_last_bundle") != bundle:
            st.session_state[key] = [c for c in C.INDUSTRY_BUNDLES[bundle] if c in opts]
            st.session_state[f"{key}_last_bundle"] = bundle
    if key not in st.session_state:
        st.session_state[key] = [d for d in default if d in opts]
    return st.multiselect(label, opts, key=key, format_func=qcew.industry_label)


def ownership_select(key: str, default: str = "0", label="Ownership") -> str:
    opts = list(C.OWNERSHIPS)
    return st.selectbox(label, opts, index=opts.index(default), key=key, format_func=C.OWNERSHIPS.get,
                        help="QCEW only publishes 'All ownerships' and 'Total government' for the all-industry "
                             "total; for detailed industries the app adds up federal, state, local and private.")


def period_select(key: str, label="Period", freq_key: str | None = None, default_freq="Quarterly") -> qcew.Period:
    freq = default_freq
    if freq_key:
        freq = st.segmented_control("Frequency", ["Quarterly", "Annual"], default=default_freq, key=freq_key) or default_freq
    periods = qcew.available_periods("A" if freq == "Annual" else "Q")
    return st.selectbox(label, periods, index=0, key=f"{key}_{freq}", format_func=lambda p: p.label)


# ---------------------------------------------------------------------------
# Data helpers with progress display
# ---------------------------------------------------------------------------
def load(geos: list, periods: list, industries: list | None, own: str, lq: bool = False) -> pd.DataFrame:
    codes = [c for g in geos for c in g.codes]
    if industries is not None and lq:
        industries = list(dict.fromkeys(["10", *industries]))   # LQ needs the all-industry total
    bar = st.progress(0.0, text="Loading QCEW data…")
    try:
        rows = qcew.load_rows(codes, periods, industries, progress=bar)
    finally:
        bar.empty()
    df = qcew.aggregate(rows, geos, own)
    if lq and not df.empty:
        df = qcew.with_lq(df, own)
    return df


def download(df: pd.DataFrame, name: str, label="⬇️ Download CSV", key=None):
    st.download_button(label, df.to_csv(index=False).encode(), file_name=f"{name}.csv", mime="text/csv",
                       key=key or f"dl_{name}")


# ---------------------------------------------------------------------------
# Tables & charts
# ---------------------------------------------------------------------------
def industry_table(df: pd.DataFrame, height=520, key=None, extra_cols=None):
    cols = ["industry_code", "industry", "emp", "emp_chg", "emp_pct", "share", "lq", "estabs",
            "avg_wkly_wage", "wage_pct", "flag"]
    if extra_cols:
        cols = extra_cols + [c for c in cols if c not in extra_cols]
    view = df.copy()
    view["industry"] = view["industry_code"].map(qcew.industry_titles()).fillna("")
    view["flag"] = view.apply(status_badge, axis=1)
    view = view[[c for c in cols if c in view.columns]]
    max_share = float(view["share"].max()) if "share" in view and view["share"].notna().any() else 100
    st.dataframe(
        view, hide_index=True, width="stretch", height=height, key=key,
        column_config={
            "industry_code": st.column_config.TextColumn("NAICS", width="small"),
            "industry": st.column_config.TextColumn("Industry", width="large"),
            "geo": st.column_config.TextColumn("Geography"),
            "emp": st.column_config.NumberColumn("Employment", format="localized"),
            "emp_chg": st.column_config.NumberColumn("YoY change", format="%+d"),
            "emp_pct": st.column_config.NumberColumn("YoY %", format="%+.1f%%"),
            "share": st.column_config.ProgressColumn("Share of area", format="%.1f%%", min_value=0,
                                                     max_value=max(max_share, 1)),
            "lq": st.column_config.NumberColumn("LQ", format="%.2f",
                                                help="Location quotient vs. U.S. (>1.25 = specialized)"),
            "estabs": st.column_config.NumberColumn("Establishments", format="localized"),
            "avg_wkly_wage": st.column_config.NumberColumn("Avg weekly wage", format="dollar"),
            "wage_pct": st.column_config.NumberColumn("Wage YoY %", format="%+.1f%%"),
            "flag": st.column_config.TextColumn("Data note"),
        },
    )


def style_fig(fig: go.Figure, height=420, legend=True) -> go.Figure:
    n_series = len({t.name for t in fig.data if getattr(t, "showlegend", None) is not False and t.name})
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10),
                      showlegend=legend and n_series > 1,
                      legend=dict(orientation="h", yanchor="top", y=-0.08, x=0, title_text="") if legend else None,
                      hovermode="x unified" if fig.data and fig.data[0].type == "scatter" else "closest",
                      font=dict(size=12), title_font=dict(size=15))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,.25)")
    return fig


def color_map(names: list[str]) -> dict:
    out, i = {}, 0
    for n in names:
        if n == "Louisiana":
            out[n] = LA_COLOR
        elif n == "United States":
            out[n] = US_COLOR
        else:
            while PALETTE[i % len(PALETTE)] == LA_COLOR:
                i += 1
            out[n] = PALETTE[i % len(PALETTE)]
            i += 1
    return out


def diverging_bar(df: pd.DataFrame, x: str, y: str, title: str, fmt=",.0f", height=420):
    d = df.sort_values(x)
    fig = go.Figure(go.Bar(x=d[x], y=d[y], orientation="h",
                           marker_color=np.where(d[x] >= 0, POS, NEG),
                           hovertemplate=f"%{{y}}<br>%{{x:{fmt}}}<extra></extra>"))
    fig.update_layout(title=title)
    return style_fig(fig, height=height, legend=False)


# ---------------------------------------------------------------------------
# Maps
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30 * 86400, show_spinner=False)
def la_geojson():
    try:
        r = requests.get("https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
                         timeout=30)
        r.raise_for_status()
        gj = r.json()
    except (requests.RequestException, ValueError):
        return None
    gj["features"] = [f for f in gj["features"] if str(f.get("id", "")).startswith("22")]
    return gj


def _sample_colorscale(scale: str, values: np.ndarray, vmin: float, vmax: float) -> list:
    from plotly.colors import sample_colorscale
    span = (vmax - vmin) or 1
    pos = np.clip((values - vmin) / span, 0, 1)
    return sample_colorscale(scale, [float(x) for x in pos])


def parish_map(df: pd.DataFrame, value: str, title: str, fmt: str = ",.0f", diverging=False, height=560):
    """Louisiana parish choropleth drawn as SVG polygons.

    Uses plain filled shapes (no map tiles, CDN topojson or WebGL), so it renders in any
    browser or network. df needs `area_fips` and the value column.
    """
    gj = la_geojson()
    if gj is None:
        return None
    vals = df.set_index("area_fips")[value]
    finite = vals.dropna()
    if diverging:
        lim = float(np.nanpercentile(np.abs(finite), 95)) if len(finite) else 1.0
        vmin, vmax, scale = -(lim or 1), (lim or 1), "RdBu"
    else:
        vmin = float(finite.min()) if len(finite) else 0.0
        vmax = float(finite.max()) if len(finite) else 1.0
        scale = "Blues"
    names = df.set_index("area_fips")["geo"] if "geo" in df else pd.Series(C.LA_PARISHES)
    fig = go.Figure()
    status = df.set_index("area_fips")["status"] if "status" in df else pd.Series(dtype=str)
    for feat in gj["features"]:
        fips = feat["id"]
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        xs, ys = [], []
        for poly in polys:
            ring = poly[0]
            xs += [pt[0] for pt in ring] + [None]
            ys += [pt[1] for pt in ring] + [None]
        v = vals.get(fips, np.nan)
        if pd.isna(v):
            color = "#E5E7EB"
            label = "🔒 suppressed" if status.get(fips) == "Suppressed" else "no data"
        else:
            color = _sample_colorscale(scale, np.array([v]), vmin, vmax)[0]
            label = format(v, fmt)
        name = names.get(fips, C.LA_PARISHES.get(fips, fips))
        fig.add_trace(go.Scatter(x=xs, y=ys, fill="toself", fillcolor=color, mode="lines",
                                 line=dict(color="white", width=0.8), hoveron="fills",
                                 name=name, text=f"{name}<br>{label}", hoverinfo="text", showlegend=False))
    # invisible trace that carries the colorbar
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                             marker=dict(colorscale=scale, cmin=vmin, cmax=vmax, color=[vmin],
                                         colorbar=dict(thickness=12, len=0.8, tickformat=fmt.replace(":", "")))))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1 / math.cos(math.radians(31)))
    fig.update_layout(title=title, height=height, margin=dict(l=0, r=0, t=40, b=0),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", hovermode="closest")
    return fig


def state_map(df: pd.DataFrame, value: str, title: str, fmt: str = ",.0f", diverging=False, height=460):
    d = df.copy()
    d["abbr"] = d["area_fips"].str[:2].map(lambda f: C.STATES.get(f, ("", ""))[1])
    kw = dict(color_continuous_scale="Blues")
    if diverging:
        lim = np.nanpercentile(np.abs(d[value].dropna()), 95) if d[value].notna().any() else 1
        kw = dict(color_continuous_scale="RdBu", range_color=(-lim, lim), color_continuous_midpoint=0)
    fig = px.choropleth(d, locations="abbr", locationmode="USA-states", color=value, scope="usa",
                        hover_name="geo", hover_data={value: f":{fmt}", "abbr": False}, **kw)
    fig.update_layout(title=title, height=height, margin=dict(l=0, r=0, t=40, b=0),
                      coloraxis_colorbar=dict(title="", thickness=12))
    return fig
