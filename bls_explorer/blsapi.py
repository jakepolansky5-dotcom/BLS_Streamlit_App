"""BLS Public Data API v2 client (LAUS, CES and any other BLS series).

Without a key BLS allows 25 queries/day, 25 series per query and 10 years per
query. A free key (https://data.bls.gov/registrationEngine/) raises that to
500 queries/day, 50 series and 20 years. Put it in .streamlit/secrets.toml as
BLS_API_KEY = "..." or in the BLS_API_KEY environment variable.
"""
from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from . import config as C

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

LAUS_MEASURES = {
    "03": "Unemployment rate",
    "04": "Unemployment",
    "05": "Employment",
    "06": "Labor force",
}

CES_INDUSTRIES = {
    "00000000": "Total nonfarm",
    "05000000": "Total private",
    "10000000": "Mining and logging",
    "15000000": "Mining, logging, and construction",
    "20000000": "Construction",
    "30000000": "Manufacturing",
    "40000000": "Trade, transportation, and utilities",
    "50000000": "Information",
    "55000000": "Financial activities",
    "60000000": "Professional and business services",
    "65000000": "Education and health services",
    "70000000": "Leisure and hospitality",
    "80000000": "Other services",
    "90000000": "Government",
}


def api_key() -> str | None:
    try:
        key = st.secrets.get("BLS_API_KEY")
    except Exception:
        key = None
    return key or os.environ.get("BLS_API_KEY") or None


# ---------------------------------------------------------------------------
# Series ID builders
# ---------------------------------------------------------------------------
def laus_id(geo, measure: str = "03") -> str | None:
    """LAUS series for a Geo (state, county/parish, LA metro, U.S.)."""
    if geo.kind == "us":
        return {"03": "LNS14000000", "04": "LNS13000000", "05": "LNS12000000", "06": "LNS11000000"}[measure]
    if geo.kind == "state":
        return f"LASST{geo.codes[0][:2]}{'0' * 11}{measure}"
    if geo.kind == "county":
        return f"LAUCN{geo.codes[0]}{'0' * 8}{measure}"
    if geo.kind in ("metro", "msa"):
        code = geo.key.replace("LA-", "")
        if code.startswith("C") and not code.startswith("CS"):
            st_fips = geo.codes[0][:2] if geo.kind == "metro" else "22"
            prefix = "LAUMT" if code in C.LA_METROS or geo.kind == "msa" else "LAUMC"
            return f"{prefix}{st_fips}{code[1:]}0{'0' * 6}{measure}"
    return None


def ces_id(geo, industry: str = "00000000", seasonal: bool = True) -> str | None:
    """CES series: national (CE), state/metro (SM). Data type 01 = all employees."""
    if geo.kind == "us":
        return f"CE{'S' if seasonal else 'U'}{industry}01"
    if geo.kind == "state":
        return f"SM{'S' if seasonal else 'U'}{geo.codes[0][:2]}00000{industry}01"
    if geo.kind == "metro":
        code = geo.key.replace("LA-", "")
        if code in C.LA_METROS:
            return f"SMU22{code[1:]}0{industry}01"
    return None


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
@st.cache_data(ttl=12 * 3600, show_spinner=False)
def fetch_series(series_ids: tuple, start_year: int, end_year: int) -> tuple[pd.DataFrame, list]:
    """Return (long dataframe, messages). Splits requests to respect API limits."""
    key = api_key()
    max_series = 50 if key else 25
    max_years = 20 if key else 10
    frames, messages = [], []
    ids = [s for s in dict.fromkeys(series_ids) if s]
    spans = []
    y = start_year
    while y <= end_year:
        spans.append((y, min(end_year, y + max_years - 1)))
        y += max_years
    for i in range(0, len(ids), max_series):
        chunk = ids[i:i + max_series]
        for y0, y1 in spans:
            payload = {"seriesid": chunk, "startyear": str(y0), "endyear": str(y1)}
            if key:
                payload["registrationkey"] = key
            try:
                r = requests.post(API_URL, json=payload, timeout=60)
                r.raise_for_status()
                body = r.json()
            except (requests.RequestException, ValueError) as exc:
                messages.append(f"Request failed: {exc}")
                continue
            if body.get("status") != "REQUEST_SUCCEEDED":
                messages.extend(body.get("message") or [body.get("status", "Unknown error")])
                continue
            messages.extend(m for m in body.get("message", []) if m)
            for s in body.get("Results", {}).get("series", []):
                rows = []
                for d in s.get("data", []):
                    per = d.get("period", "")
                    if not per.startswith("M") or per == "M13":
                        continue
                    try:
                        val = float(d["value"])
                    except (ValueError, KeyError):
                        continue
                    notes = ",".join(f.get("code", "") for f in d.get("footnotes", []) if f and f.get("code"))
                    rows.append({"series_id": s["seriesID"],
                                 "date": pd.Timestamp(int(d["year"]), int(per[1:]), 1),
                                 "value": val, "footnotes": notes})
                if rows:
                    frames.append(pd.DataFrame(rows))
    df = pd.concat(frames, ignore_index=True).sort_values(["series_id", "date"]) if frames else \
        pd.DataFrame(columns=["series_id", "date", "value", "footnotes"])
    df = df.drop_duplicates(["series_id", "date"])
    return df, messages
