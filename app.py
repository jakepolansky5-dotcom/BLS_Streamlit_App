"""Louisiana BLS Data Explorer — entry point.

Run with:  streamlit run app.py
"""
from datetime import date

import streamlit as st

st.set_page_config(page_title="Louisiana BLS Data Explorer", page_icon="📈", layout="wide",
                   initial_sidebar_state="expanded")

from bls_explorer import blsapi, config as C, qcew  # noqa: E402
from bls_explorer.views import (compare, industry, labor, monthly, notes, overview, release,  # noqa: E402
                                trends, watch)

pages = {
    "Explore": [
        st.Page(release.render, title="Latest QCEW Release", icon="🆕", url_path="release", default=True),
        st.Page(monthly.render, title="Monthly Snapshot", icon="🗓️", url_path="monthly"),
        st.Page(overview.render, title="Region Overview", icon="🏙️", url_path="region"),
        st.Page(industry.render, title="Industry Snapshot", icon="🏭", url_path="industry"),
        st.Page(compare.render, title="Compare Regions", icon="⚖️", url_path="compare"),
        st.Page(trends.render, title="Trend Builder", icon="📈", url_path="trends"),
        st.Page(watch.render, title="Project Watch", icon="🎯", url_path="watch"),
    ],
    "More BLS data": [
        st.Page(labor.render, title="Labor Force & Jobs (monthly)", icon="👷", url_path="labor"),
        st.Page(notes.render, title="Data Notes & Help", icon="📘", url_path="notes"),
    ],
}
nav = st.navigation(pages)

# ---- sidebar: data status ---------------------------------------------------
with st.sidebar:
    with st.spinner("Checking BLS for the latest data…"):
        info = qcew.latest_periods()
    st.markdown("### 📡 Data status")
    st.markdown(f"**Latest QCEW quarter:** {info['quarter'].label}  \n"
                f"**Latest annual average:** {info['annual'].label}  \n"
                f"**History from:** {info['earliest_year']}")
    upcoming = [(d, p) for d, p in C.RELEASE_SCHEDULE if date.fromisoformat(d) >= date.today()]
    if upcoming:
        d, p = upcoming[0]
        days = (date.fromisoformat(d) - date.today()).days
        st.info(f"Next QCEW release: **{p}** on **{date.fromisoformat(d):%b %d, %Y}** "
                f"({'today' if days == 0 else f'in {days} days'}).", icon="🗓️")
    st.caption(f"Checked {info['checked']}. New data is picked up automatically within the hour.")
    if st.button("🔄 Check for new data now", width="stretch",
                 help="Re-checks BLS and re-downloads the latest two years (which BLS revises with each release)."):
        qcew.clear_caches(revisable_only=True)
        st.rerun()
    st.divider()
    st.caption("BLS API key: " + ("✅ configured" if blsapi.api_key() else
                                  "not set (monthly series limited to 25 requests/day). See Data Notes."))

nav.run()
