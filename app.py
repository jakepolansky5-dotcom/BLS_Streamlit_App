"""Louisiana BLS Data Explorer — entry point.

Run with:  streamlit run app.py
"""
from datetime import date

import pandas as pd

import streamlit as st

st.set_page_config(page_title="Louisiana BLS Data Explorer", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")

from bls_explorer import blsapi, config as C, qcew  # noqa: E402
from bls_explorer.views import (compare, industry, labor, monthly, notes, overview, release,  # noqa: E402
                                trends, watch)

pages = {
    "Where we are today (monthly)": [
        st.Page(monthly.render, title="Monthly Snapshot", icon="🗓️", url_path="monthly", default=True),
        st.Page(labor.render, title="Monthly Data Explorer", icon="👷", url_path="labor"),
        st.Page(watch.render, title="Project Watch", icon="🎯", url_path="watch"),
    ],
    "Detailed jobs & wages (QCEW)": [
        st.Page(release.render, title="Latest QCEW Release", icon="🆕", url_path="release"),
        st.Page(overview.render, title="Region Overview", icon="🏙️", url_path="region"),
        st.Page(industry.render, title="Industry Snapshot", icon="🏭", url_path="industry"),
        st.Page(compare.render, title="Compare Regions", icon="⚖️", url_path="compare"),
        st.Page(trends.render, title="Trend Builder", icon="📈", url_path="trends"),
    ],
    "Help": [
        st.Page(notes.render, title="Data Notes & Help", icon="📘", url_path="notes"),
    ],
}
nav = st.navigation(pages)

# ---- sidebar: data status ---------------------------------------------------
with st.sidebar:
    with st.spinner("Checking BLS for the latest data…"):
        info = qcew.latest_periods()
    st.markdown("### 📡 Data status")
    try:
        core, _ = blsapi.fetch_series(tuple(sorted(monthly.core_ids())), date.today().year - 3, date.today().year)
        months = core.groupby(core["series_id"].str[:2])["date"].max() if not core.empty else {}
        la_m = months.get("LA") if len(months) else None
        sm_m = months.get("SM") if len(months) else None
    except Exception:
        la_m = sm_m = None
    fmt = lambda d: d.strftime("%b %Y") if d is not None and pd.notna(d) else "unavailable"
    st.markdown(f"**Monthly (latest):**  \n"
                f"Unemployment (LAUS): {fmt(la_m)}  \n"
                f"Payroll jobs (CES): {fmt(sm_m)}")
    st.markdown(f"**Quarterly detail (QCEW):** {info['quarter'].label}  \n"
                f"Annual average: {info['annual'].label} · history from {info['earliest_year']}")
    upcoming = [(d, p) for d, p in C.RELEASE_SCHEDULE if date.fromisoformat(d) >= date.today()]
    if upcoming:
        d, p = upcoming[0]
        days = (date.fromisoformat(d) - date.today()).days
        st.caption(f"🗓️ Next QCEW release: **{p}** on **{date.fromisoformat(d):%b %d, %Y}** "
                f"({'today' if days == 0 else f'in {days} days'}).")
    st.caption(f"Checked {info['checked']}. New data is picked up automatically within the hour.")
    if st.button("🔄 Check for new data now", width="stretch",
                 help="Re-checks BLS for new monthly (LAUS/CES) and quarterly (QCEW) data. Re-downloads recent QCEW "
                      "quarters, which BLS revises with each release."):
        qcew.clear_caches(revisable_only=True)
        blsapi.clear_cache()
        st.rerun()
    st.divider()
    st.caption("BLS API key: " + ("✅ configured" if blsapi.api_key() else
                                  "not set (monthly series limited to 25 requests/day). See Data Notes."))

nav.run()
