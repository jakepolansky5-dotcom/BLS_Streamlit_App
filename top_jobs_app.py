"""LA Top Jobs — student-facing site, served through Streamlit.

Deploy on Streamlit Community Cloud as its own app with this file as the main file path.
Run locally with:  streamlit run top_jobs_app.py

The page itself lives in top_jobs/ (index.html + data.js). This file only shows it full-screen;
it makes no API calls. To refresh the numbers, run `python top_jobs/build_data.py` and commit data.js.
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="LA Top Jobs", page_icon="🧰", layout="wide", initial_sidebar_state="collapsed")

SITE = Path(__file__).parent / "top_jobs"


@st.cache_data
def page_html(index_mtime: float, data_mtime: float) -> str:
    """index.html with data.js inlined (the component iframe can't load sibling files)."""
    html = (SITE / "index.html").read_text(encoding="utf-8")
    data = (SITE / "data.js").read_text(encoding="utf-8")
    tag = '<script src="data.js"></script>'
    if tag not in html:
        raise RuntimeError("top_jobs/index.html no longer loads data.js the expected way")
    return html.replace(tag, "<script>\n" + data.replace("</script", "<\\/script") + "\n</script>")


# Hide Streamlit's own chrome and let the page fill the window; the page scrolls inside its frame.
st.markdown(
    """<style>
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none !important; }
    [data-testid="stMainBlockContainer"], .block-container { padding: 0 !important; max-width: 100% !important; }
    [data-testid="stAppViewContainer"] iframe { height: 100vh !important; height: 100dvh !important; display: block; border: 0; }
    [data-testid="stVerticalBlock"] { gap: 0 !important; }
    </style>""",
    unsafe_allow_html=True,
)

components.html(
    page_html((SITE / "index.html").stat().st_mtime, (SITE / "data.js").stat().st_mtime),
    height=900,
    scrolling=True,
)
