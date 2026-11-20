"""QCEW Open Data access layer.

Data source: https://data.bls.gov/cew/data/api/{year}/{qtr}/{slice}/{code}.csv

Two slices are used:
  * area     - every industry/ownership row for one area (US, state, county, MSA)
  * industry - every area (US, states, counties; no MSAs) for one industry

Files are cached on disk (parquet) and in memory. Periods that BLS can still
revise (the latest two years) are re-downloaded after REVISABLE_MAX_AGE.

All values flagged as not disclosable (disclosure_code == "N") are turned
into NaN, never 0, and every aggregate carries a count of suppressed parts.
"""
from __future__ import annotations

import io
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

from . import config as C

BASE_URL = "https://data.bls.gov/cew/data/api"
TITLES_URL = "https://data.bls.gov/cew/doc/titles/{kind}/{kind}_titles.csv"
CACHE_DIR = Path(os.environ.get("BLS_EXPLORER_CACHE", Path.home() / ".cache" / "bls_explorer")) / "qcew"
REVISABLE_MAX_AGE = 12 * 3600       # seconds
MAX_WORKERS = 8
MIN_YOY_COVERAGE = 0.9   # share of a total whose YoY change must be known
HEADERS = {"User-Agent": "bls-explorer/2.0 (personal research dashboard)"}

_session = requests.Session()
_session.headers.update(HEADERS)
_adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS * 2)
_session.mount("https://", _adapter)


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class Period:
    year: int
    qtr: str  # "1".."4" or "A"

    @property
    def annual(self) -> bool:
        return self.qtr == "A"

    @property
    def label(self) -> str:
        return f"{self.year} Annual" if self.annual else f"{self.year} Q{self.qtr}"

    @property
    def key(self) -> str:
        return f"{self.year}{'A' if self.annual else 'Q' + self.qtr}"

    @property
    def sort(self) -> float:
        return self.year + (0.9 if self.annual else (int(self.qtr) - 1) / 4)

    @property
    def end_date(self) -> pd.Timestamp:
        m = 12 if self.annual else int(self.qtr) * 3
        return pd.Timestamp(self.year, m, 1)

    @property
    def weeks(self) -> int:
        return 52 if self.annual else 13

    def shift_years(self, n: int) -> "Period":
        return Period(self.year + n, self.qtr)

    def prev_quarter(self) -> "Period":
        if self.annual:
            return Period(self.year - 1, "A")
        q = int(self.qtr)
        return Period(self.year - 1, "4") if q == 1 else Period(self.year, str(q - 1))

    @staticmethod
    def parse(s: str) -> "Period":
        s = s.strip().upper().replace(" ", "")
        if s.endswith("A") or s.endswith("ANNUAL"):
            return Period(int(s[:4]), "A")
        return Period(int(s[:4]), s[-1])


def quarter_range(start: Period, end: Period) -> list[Period]:
    out, p = [], start
    while p <= end:
        out.append(p)
        q = int(p.qtr)
        p = Period(p.year + 1, "1") if q == 4 else Period(p.year, str(q + 1))
    return out


def annual_range(start_year: int, end_year: int) -> list[Period]:
    return [Period(y, "A") for y in range(start_year, end_year + 1)]


# ---------------------------------------------------------------------------
# Low-level download + cache
# ---------------------------------------------------------------------------
_mem: "OrderedDict[str, pd.DataFrame | None]" = OrderedDict()
_mem_lock = threading.Lock()
_MEM_MAX = 400
_latest_cache: dict = {}


def url_code(code: str) -> str:
    return code.replace("-", "_")


def _url(slice_: str, p: Period, code: str) -> str:
    q = "a" if p.annual else p.qtr
    return f"{BASE_URL}/{p.year}/{q}/{slice_}/{url_code(code)}.csv"


def _is_revisable(p: Period) -> bool:
    latest_year = _latest_cache.get("year") or date.today().year
    return p.year >= latest_year - 1


KEEP_Q = {
    "qtrly_estabs": "estabs", "month1_emplvl": "m1", "month2_emplvl": "m2", "month3_emplvl": "m3",
    "total_qtrly_wages": "wages", "lq_month3_emplvl": "lq_pub",
    "oty_qtrly_estabs_chg": "estabs_chg", "oty_month1_emplvl_chg": "m1_chg",
    "oty_month2_emplvl_chg": "m2_chg", "oty_month3_emplvl_chg": "m3_chg",
    "oty_total_qtrly_wages_chg": "wages_chg",
}
KEEP_A = {
    "annual_avg_estabs": "estabs", "annual_avg_emplvl": "emp_a", "total_annual_wages": "wages",
    "lq_annual_avg_emplvl": "lq_pub", "oty_annual_avg_estabs_chg": "estabs_chg",
    "oty_annual_avg_emplvl_chg": "emp_a_chg", "oty_total_annual_wages_chg": "wages_chg",
}
VALUE_COLS = ["estabs", "emp", "emp_avg", "wages", "m1", "m2", "m3"]
CHG_COLS = ["estabs_chg", "emp_chg", "emp_avg_chg", "wages_chg", "m1_chg", "m2_chg", "m3_chg"]


def _normalize(raw: pd.DataFrame, p: Period) -> pd.DataFrame:
    """Convert a raw QCEW CSV into the app's compact numeric schema."""
    keep = KEEP_A if p.annual else KEEP_Q
    df = pd.DataFrame({
        "area_fips": raw["area_fips"].astype(str),
        "own_code": raw["own_code"].astype(str),
        "industry_code": raw["industry_code"].astype(str),
        "agglvl_code": pd.to_numeric(raw["agglvl_code"], errors="coerce").astype("Int16"),
    })
    size = raw.get("size_code")
    for src, dst in keep.items():
        if src in raw.columns:
            df[dst] = pd.to_numeric(raw[src].astype(str).str.replace(",", ""), errors="coerce")
        else:
            df[dst] = np.nan
    supp = raw["disclosure_code"].fillna("").astype(str).str.strip().eq("N").to_numpy()
    oty_supp = raw.get("oty_disclosure_code", pd.Series("", index=raw.index)).fillna("").astype(str).str.strip().eq("N").to_numpy()

    if p.annual:
        df["emp"] = df["emp_a"]
        df["emp_avg"] = df["emp_a"]
        df["emp_chg"] = df["emp_a_chg"]
        df["emp_avg_chg"] = df["emp_a_chg"]
        for c in ("m1", "m2", "m3", "m1_chg", "m2_chg", "m3_chg"):
            df[c] = np.nan
        df = df.drop(columns=["emp_a", "emp_a_chg"])
    else:
        df["emp"] = df["m3"]
        df["emp_avg"] = df[["m1", "m2", "m3"]].mean(axis=1)
        df["emp_chg"] = df["m3_chg"]
        df["emp_avg_chg"] = df[["m1_chg", "m2_chg", "m3_chg"]].mean(axis=1)

    df.loc[supp, VALUE_COLS + ["lq_pub"]] = np.nan
    # If either this year or last year is suppressed the change is unknown.
    df.loc[supp | oty_supp, CHG_COLS] = np.nan
    df["supp"] = supp.astype("int16")
    df["oty_supp"] = (supp | oty_supp).astype("int16")
    if size is not None:
        df = df[size.astype(str).isin(["0", "0.0"])]
    df["year"] = p.year
    df["qtr"] = p.qtr
    cols = ["area_fips", "own_code", "industry_code", "agglvl_code", "year", "qtr", "supp", "oty_supp",
            *VALUE_COLS, *CHG_COLS, "lq_pub"]
    return df[cols].reset_index(drop=True)


def _download(url: str) -> pd.DataFrame | None:
    last_exc = None
    for attempt in range(4):
        try:
            r = _session.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text), dtype=str)
        except (requests.RequestException, pd.errors.ParserError) as exc:
            last_exc = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to download {url}: {last_exc}")


def get_file(slice_: str, p: Period, code: str) -> pd.DataFrame | None:
    """Return the normalized file, or None if BLS has no such file."""
    key = f"{slice_}_{p.key}_{url_code(code)}"
    with _mem_lock:
        if key in _mem:
            _mem.move_to_end(key)
            return _mem[key]
    path = CACHE_DIR / f"{key}.parquet"
    miss_path = CACHE_DIR / f"{key}.missing"
    df = None
    fresh = None
    if path.exists():
        age = time.time() - path.stat().st_mtime
        if not _is_revisable(p) or age < REVISABLE_MAX_AGE:
            df, fresh = pd.read_parquet(path), True
    elif miss_path.exists() and time.time() - miss_path.stat().st_mtime < 6 * 3600:
        fresh, df = True, None
    if fresh is None:
        raw = _download(_url(slice_, p, code))
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if raw is None:
            df = None
            miss_path.touch()
        else:
            df = _normalize(raw, p)
            try:
                df.to_parquet(path, index=False)
                miss_path.unlink(missing_ok=True)
            except OSError:
                pass
    with _mem_lock:
        _mem[key] = df
        while len(_mem) > _MEM_MAX:
            _mem.popitem(last=False)
    return df


def get_files(requests_: list[tuple[str, Period, str]], progress=None) -> dict:
    """Download many files in parallel. Returns {(slice, period, code): df|None}."""
    out = {}
    uniq = list(dict.fromkeys(requests_))
    if not uniq:
        return out
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(get_file, *r): r for r in uniq}
        for fut in futures:
            r = futures[fut]
            out[r] = fut.result()
            done += 1
            if progress is not None and len(uniq) > 4:
                progress.progress(done / len(uniq), text=f"Downloading QCEW files ({done}/{len(uniq)})")
    if progress is not None:
        progress.empty()
    return out


def clear_caches(revisable_only: bool = True):
    """Drop cached files (all, or only those BLS might still revise)."""
    with _mem_lock:
        _mem.clear()
    _latest_cache.clear()
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            if not revisable_only or f.suffix == ".missing":
                f.unlink(missing_ok=True)
                continue
            try:
                year = int(f.name.split("_")[1][:4])
            except (IndexError, ValueError):
                continue
            if year >= date.today().year - 2:
                f.unlink(missing_ok=True)
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Data availability
# ---------------------------------------------------------------------------
def _exists(p: Period, code: str = "US000") -> bool:
    try:
        r = _session.head(_url("area", p, code), timeout=20)
        return r.status_code == 200
    except requests.RequestException:
        return False


@st.cache_data(ttl=3600, show_spinner=False)
def latest_periods() -> dict:
    """Probe BLS for the newest quarterly and annual data and the earliest year served."""
    today = date.today()
    latest_q = None
    for back in range(0, 10):
        q_index = today.year * 4 + (today.month - 1) // 3 - back
        p = Period(q_index // 4, str(q_index % 4 + 1))
        if _exists(p):
            latest_q = p
            break
    latest_a = None
    for y in range(today.year, today.year - 4, -1):
        if _exists(Period(y, "A")):
            latest_a = Period(y, "A")
            break
    earliest = 2014
    for y in range(2013, 1989, -1):
        if _exists(Period(y, "1")):
            earliest = y
        else:
            break
    if latest_q is None:
        latest_q = Period(today.year - 1, "1")
    if latest_a is None:
        latest_a = Period(latest_q.year - 1, "A")
    _latest_cache["year"] = latest_q.year
    return {"quarter": latest_q, "annual": latest_a, "earliest_year": earliest,
            "checked": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}


def available_periods(freq: str = "Q") -> list[Period]:
    info = latest_periods()
    if freq == "A":
        return annual_range(info["earliest_year"], info["annual"].year)[::-1]
    return quarter_range(Period(info["earliest_year"], "1"), info["quarter"])[::-1]


# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30 * 86400, show_spinner=False)
def industry_titles() -> dict:
    try:
        raw = _download(TITLES_URL.format(kind="industry"))
    except RuntimeError:
        raw = None
    titles = {}
    if raw is not None:
        for code, title in zip(raw["industry_code"], raw["industry_title"]):
            t = str(title)
            for prefix in (f"NAICS {code} ", f"{code} ", "NAICS07 ", "NAICS "):
                if t.startswith(prefix):
                    t = t[len(prefix):]
                    break
            titles.setdefault(str(code), t.strip())
    titles.update(C.SUPERSECTORS)
    titles["10"] = "Total, all industries"
    return titles


@st.cache_data(ttl=30 * 86400, show_spinner=False)
def area_titles() -> dict:
    try:
        raw = _download(TITLES_URL.format(kind="area"))
    except RuntimeError:
        return {}
    raw = raw.drop_duplicates("area_fips")
    return dict(zip(raw["area_fips"].astype(str), raw["area_title"].astype(str)))


def industry_level(code: str):
    """'total', 'super', or the NAICS digit level (2-6)."""
    if code == "10":
        return "total"
    if code.startswith("10") and len(code) in (3, 4):
        return "domain" if len(code) == 3 else "super"
    if "-" in code:
        return 2
    return len(code)


def industry_label(code: str) -> str:
    t = industry_titles().get(code, "")
    return f"{code} – {t}" if t else code


def parent_sector(code: str) -> str | None:
    if industry_level(code) in ("total", "super", "domain"):
        return None
    two = code[:2]
    for rng in ("31-33", "44-45", "48-49"):
        lo, hi = rng.split("-")
        if lo <= two <= hi:
            return rng
    return two


# ---------------------------------------------------------------------------
# Ownership handling
# ---------------------------------------------------------------------------
CUR_COLS = ["_cur_estabs", "_cur_emp", "_cur_emp_avg", "_cur_wages"]


def _ensure_cur(df: pd.DataFrame) -> pd.DataFrame:
    """Add current-period levels restricted to rows whose YoY change is known.

    Summing these alongside the changes keeps YoY % on a matched base when
    some components of an aggregate are suppressed.
    """
    if "_cur_emp" in df.columns:
        return df
    df = df.copy()
    for c in ["estabs", "emp", "emp_avg", "wages"]:
        df[f"_cur_{c}"] = df[c].where(df[f"{c}_chg"].notna())
    return df


def select_ownership(rows: pd.DataFrame, own: str) -> pd.DataFrame:
    """Pick one ownership per (area, period, industry).

    QCEW publishes combined ownerships (0 = all, 8 = all government) only for
    the all-industry total. For any other industry we sum the component
    ownership rows and count suppressed components.
    """
    rows = _ensure_cur(rows)
    keys = ["area_fips", "year", "qtr", "industry_code"]
    direct = rows[rows["own_code"] == own].copy()
    direct["parts"] = 1
    if own not in C.OWNERSHIP_PARTS:
        return direct
    parts = rows[rows["own_code"].isin(C.OWNERSHIP_PARTS[own])]
    synth = _sum_rows(parts, keys)
    if not direct.empty and not synth.empty:
        have = pd.MultiIndex.from_frame(direct[keys])
        synth = synth[~pd.MultiIndex.from_frame(synth[keys]).isin(have)]
    out = pd.concat([direct, synth], ignore_index=True)
    out["own_code"] = own
    return out


def _sum_rows(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    cols = VALUE_COLS + CHG_COLS + CUR_COLS
    if df.empty:
        return pd.DataFrame(columns=keys + cols + ["supp", "oty_supp", "parts", "lq_pub"])
    df = _ensure_cur(df)
    g = df.groupby(keys, sort=False, observed=True)
    vals = g[cols].sum(min_count=1)
    flags = g[["supp", "oty_supp"]].sum()
    parts = g["parts"].sum() if "parts" in df.columns else g.size().rename("parts")
    out = pd.concat([vals, flags, parts.rename("parts")], axis=1).reset_index()
    out["lq_pub"] = np.nan
    return out


# ---------------------------------------------------------------------------
# Geography-aware loading
# ---------------------------------------------------------------------------
AREA_COST = {"us": 1.0, "state": 0.6, "county": 0.12, "msa": 0.2}


def _industry_cost(code: str) -> float:
    lvl = industry_level(code)
    if lvl == "total":
        return 3.6
    if lvl in ("super", "domain", 2):
        return 1.1
    if lvl == 3:
        return 0.8
    return 0.35


def code_kind(code: str) -> str:
    if code == "US000":
        return "us"
    if code.startswith("C"):
        return "msa"
    if code.endswith("000"):
        return "state"
    return "county"


def load_rows(codes: list[str], periods: list[Period], industries: list[str] | None,
              progress=None) -> pd.DataFrame:
    """Raw normalized rows for the given area codes/periods/industries (all ownerships)."""
    codes = list(dict.fromkeys(codes))
    use_industry = False
    if industries is not None and not any(code_kind(c) == "msa" for c in codes):
        area_cost = sum(AREA_COST[code_kind(c)] for c in codes)
        ind_cost = sum(_industry_cost(i) for i in industries)
        use_industry = ind_cost < area_cost
    reqs = ([("industry", p, i) for p in periods for i in industries] if use_industry
            else [("area", p, c) for p in periods for c in codes])
    files = get_files(reqs, progress)
    frames = []
    code_set = set(codes)
    ind_set = set(industries) if industries is not None else None
    for (slice_, p, code), df in files.items():
        if df is None:
            continue
        if slice_ == "industry":
            df = df[df["area_fips"].isin(code_set)]
        elif ind_set is not None:
            df = df[df["industry_code"].isin(ind_set)]
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def missing_periods(codes: list[str], periods: list[Period]) -> list[Period]:
    files = get_files([("area", p, codes[0]) for p in periods])
    return [p for (s, p, c), df in files.items() if df is None]


def aggregate(rows: pd.DataFrame, geos: list, own: str) -> pd.DataFrame:
    """Aggregate raw rows into one record per (geo, period, industry).

    `geos` are objects with .key, .name and .codes (component area codes).
    """
    if rows.empty:
        return pd.DataFrame()
    sel = select_ownership(rows, own)
    totals = rows[(rows["industry_code"] == "10") & (rows["own_code"] == "0")]
    frames = []
    for g in geos:
        part = sel[sel["area_fips"].isin(g.codes)]
        if part.empty:
            continue
        tot = (totals[totals["area_fips"].isin(g.codes)]
               .groupby(["year", "qtr"], as_index=False)[["emp", "wages"]].sum(min_count=1)
               .rename(columns={"emp": "tot_emp", "wages": "tot_wages"}))
        if len(g.codes) == 1:
            agg = part.copy()
            agg["n_areas"] = 1
        else:
            keys = ["year", "qtr", "industry_code"]
            n_areas = part.groupby(keys, sort=False).size().rename("n_areas").reset_index()
            agg = _sum_rows(part, keys).merge(n_areas, on=keys, how="left")
        agg = agg.merge(tot, on=["year", "qtr"], how="left") if not tot.empty else agg.assign(tot_emp=np.nan, tot_wages=np.nan)
        agg["geo_key"] = g.key
        agg["geo"] = g.name
        frames.append(agg)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return add_metrics(out)


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    annual = df["qtr"].eq("A")
    weeks = np.where(annual, 52, 13)
    df["period"] = np.where(annual, df["year"].astype(str) + " Annual",
                            df["year"].astype(str) + " Q" + df["qtr"].astype(str))
    df["period_key"] = np.where(annual, df["year"].astype(str) + "A",
                                df["year"].astype(str) + "Q" + df["qtr"].astype(str))
    qn = pd.to_numeric(df["qtr"].where(~annual, "4"), errors="coerce")
    df["date"] = pd.to_datetime(dict(year=df["year"], month=(qn * 3).astype(int), day=1))
    df["avg_wkly_wage"] = df["wages"] / df["emp_avg"] / weeks
    df["avg_annual_pay"] = df["avg_wkly_wage"] * 52
    # When parts of a total have unknown YoY change (suppressed last year or this
    # year), the change is computed over the known parts only. If those parts are
    # under 90% of the total, the change would mislead, so treat it as unknown.
    for c in ["estabs", "emp", "emp_avg", "wages"]:
        coverage = df[f"_cur_{c}"] / df[c]
        weak = (coverage < MIN_YOY_COVERAGE) | df[f"_cur_{c}"].isna()
        df.loc[weak, f"{c}_chg"] = np.nan
        df.loc[weak, f"_cur_{c}"] = np.nan
    if "m1_chg" in df:
        df.loc[df["emp_chg"].isna(), ["m1_chg", "m2_chg", "m3_chg"]] = np.nan
    for c in ["estabs", "emp", "wages"]:
        prev = df[f"_cur_{c}"] - df[f"{c}_chg"]
        df[f"{c}_prev"] = prev
        df[f"{c}_pct"] = np.where(prev > 0, df[f"{c}_chg"] / prev * 100, np.nan)
    prev_wage = (df["_cur_wages"] - df["wages_chg"]) / (df["_cur_emp_avg"] - df["emp_avg_chg"]) / weeks
    cur_wage_m = df["_cur_wages"] / df["_cur_emp_avg"] / weeks
    df["wage_pct"] = np.where(prev_wage > 0, (cur_wage_m / prev_wage - 1) * 100, np.nan)
    df["status"] = np.select(
        [df["emp"].isna(), df["supp"] > 0],
        ["Suppressed", "Partial"], default="")
    return df


def with_lq(df: pd.DataFrame, own: str) -> pd.DataFrame:
    """Add location quotients relative to the U.S. (BLS method).

    LQ = (industry employment / all-ownership total employment in the area)
       / (same ratio for the U.S.), using the selected ownership for the
    industry numerator. Matches published QCEW LQs. Requires the area's
    industry-10 total, which area-slice loads include automatically.
    """
    if df.empty:
        return df
    periods = sorted({Period(int(y), str(q)) for y, q in df[["year", "qtr"]].drop_duplicates().itertuples(index=False)})
    us_rows = load_rows(["US000"], periods, None)
    if us_rows.empty:
        return df.assign(lq=np.nan, lq_wages=np.nan, share=np.nan)
    us = select_ownership(us_rows, own)[["year", "qtr", "industry_code", "emp", "wages"]] \
        .rename(columns={"emp": "us_emp", "wages": "us_wages"})
    us_tot = us_rows[(us_rows["industry_code"] == "10") & (us_rows["own_code"] == "0")][["year", "qtr", "emp", "wages"]] \
        .rename(columns={"emp": "us_tot_emp", "wages": "us_tot_wages"})
    out = df.drop(columns=[c for c in ("us_emp", "us_wages", "us_tot_emp", "us_tot_wages") if c in df.columns])
    out = out.merge(us, on=["year", "qtr", "industry_code"], how="left").merge(us_tot, on=["year", "qtr"], how="left")
    out["lq"] = (out["emp"] / out["tot_emp"]) / (out["us_emp"] / out["us_tot_emp"])
    out["lq_wages"] = (out["wages"] / out["tot_wages"]) / (out["us_wages"] / out["us_tot_wages"])
    out["share"] = out["emp"] / out["tot_emp"] * 100
    return out


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Explode quarterly records into monthly employment records."""
    q = df[df["qtr"] != "A"]
    if q.empty:
        return pd.DataFrame(columns=["geo", "geo_key", "industry_code", "date", "emp", "emp_chg", "status"])
    parts = []
    for i, m in enumerate(["m1", "m2", "m3"]):
        part = q[["geo", "geo_key", "industry_code", "year", "qtr", m, f"{m}_chg", "status"]].rename(
            columns={m: "emp", f"{m}_chg": "emp_chg"})
        part["month"] = (part["qtr"].astype(int) - 1) * 3 + i + 1
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    out["date"] = pd.to_datetime(dict(year=out["year"], month=out["month"], day=1))
    return out.sort_values(["geo", "industry_code", "date"]).reset_index(drop=True)
