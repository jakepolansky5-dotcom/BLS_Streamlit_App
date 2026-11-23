"""BLS Public Data API v2 client (LAUS, CES and any other BLS series).

Without a key BLS allows 25 queries/day, 25 series per query and 10 years per
query. A free key (https://data.bls.gov/registrationEngine/) raises that to
500 queries/day, 50 series and 20 years. Put it in .streamlit/secrets.toml as
BLS_API_KEY = "..." or in the BLS_API_KEY environment variable.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

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


KEY_NAMES = ("BLS_API_KEY", "bls_api_key", "BLS_KEY", "bls_key", "registrationkey", "api_key", "key")


def api_key() -> str | None:
    """BLS key from Streamlit secrets (top level or a [bls] section) or the environment."""
    try:
        secrets = st.secrets
        for name in KEY_NAMES[:5]:
            if name in secrets and str(secrets[name]).strip():
                return str(secrets[name]).strip()
        for section in ("bls", "BLS"):
            if section in secrets:
                for name in KEY_NAMES:
                    if name in secrets[section] and str(secrets[section][name]).strip():
                        return str(secrets[section][name]).strip()
    except Exception:
        pass
    key = os.environ.get("BLS_API_KEY", "").strip()
    return key or None


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
CACHE_DIR = Path(os.environ.get("BLS_EXPLORER_CACHE", Path.home() / ".cache" / "bls_explorer")) / "api"
CACHE_TTL = 12 * 3600


def _parse(body: dict) -> pd.DataFrame:
    rows = []
    for s in body.get("Results", {}).get("series", []):
        for d in s.get("data", []):
            per = d.get("period", "")
            if not per.startswith("M") or per == "M13":
                continue
            try:
                val = float(d["value"])
            except (ValueError, KeyError):
                continue
            notes = ",".join(f.get("code", "") for f in d.get("footnotes", []) if f and f.get("code"))
            rows.append({"series_id": s["seriesID"], "date": pd.Timestamp(int(d["year"]), int(per[1:]), 1),
                         "value": val, "footnotes": notes})
    return pd.DataFrame(rows, columns=["series_id", "date", "value", "footnotes"])


def _fetch_chunk(chunk: list, y0: int, y1: int, key: str | None) -> tuple[pd.DataFrame | None, list]:
    """One API request, cached on disk. Falls back to stale cache if BLS refuses."""
    tag = hashlib.sha1(f"{','.join(sorted(chunk))}|{y0}|{y1}".encode()).hexdigest()[:20]
    path = CACHE_DIR / f"{tag}.parquet"
    stale = None
    if path.exists():
        age = time.time() - path.stat().st_mtime
        cached = pd.read_parquet(path)
        if age < CACHE_TTL:
            return cached, []
        stale = (cached, age)
    payload = {"seriesid": chunk, "startyear": str(y0), "endyear": str(y1)}
    if key:
        payload["registrationkey"] = key
    problem = None
    try:
        r = requests.post(API_URL, json=payload, timeout=60)
        r.raise_for_status()
        body = r.json()
        if body.get("status") == "REQUEST_SUCCEEDED":
            df = _parse(body)
            msgs = [m for m in body.get("message", []) if m]
            try:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                df.to_parquet(path, index=False)
            except OSError:
                pass
            return df, msgs
        problem = "; ".join(body.get("message") or [body.get("status", "Unknown error")])
    except (requests.RequestException, ValueError) as exc:
        problem = f"Request failed: {exc}"
    if stale is not None:
        hours = stale[1] / 3600
        return stale[0], [f"BLS API unavailable ({problem}). Showing saved data from {hours:.0f} hours ago."]
    return None, [problem]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_series(series_ids: tuple, start_year: int, end_year: int) -> tuple[pd.DataFrame, list]:
    """Return (long dataframe, messages). Splits requests to respect API limits."""
    key = api_key()
    max_series = 50 if key else 25
    max_years = 20 if key else 10
    ids = sorted(s for s in dict.fromkeys(series_ids) if s)
    spans, y = [], start_year
    while y <= end_year:
        spans.append((y, min(end_year, y + max_years - 1)))
        y += max_years
    frames, messages = [], []
    for i in range(0, len(ids), max_series):
        for y0, y1 in spans:
            df, msgs = _fetch_chunk(ids[i:i + max_series], y0, y1, key)
            messages += msgs
            if df is not None:
                frames.append(df)
    frames = [f for f in frames if not f.empty]
    df = pd.concat(frames, ignore_index=True) if frames else \
        pd.DataFrame(columns=["series_id", "date", "value", "footnotes"])
    df = df.drop_duplicates(["series_id", "date"]).sort_values(["series_id", "date"]).reset_index(drop=True)
    return df, list(dict.fromkeys(messages))


def requests_needed(n_series: int, n_years: int = 3) -> int:
    per = 50 if api_key() else 25
    span = 20 if api_key() else 10
    return -(-n_series // per) * -(-n_years // span)


def clear_cache():
    """Expire saved API responses so the next request fetches fresh data.

    Files are kept (marked old) so they still serve as a fallback if BLS refuses a request.
    """
    if CACHE_DIR.exists():
        old = time.time() - CACHE_TTL - 60
        for f in CACHE_DIR.glob("*.parquet"):
            os.utime(f, (old, old))
    fetch_series.clear()
