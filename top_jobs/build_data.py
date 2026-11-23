"""Build top_jobs/data.js for the LA Top Jobs site.

Merges three things:
  1. content.json: the kid-friendly copy (edit this by hand)
  2. LA Works long-term occupational projections, statewide (openings, growth)
  3. BLS OEWS Louisiana wages (25th percentile = "starting pay", median = "typical pay")

Run from the repo root:
    python top_jobs/build_data.py

Set BLS_API_KEY in the environment for higher BLS API limits (optional).
"""
from __future__ import annotations

import io
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).parent
PROJ_YEARS = "20242034"
PROJ_URL = f"https://www.laworks.net/Downloads/LMI/{PROJ_YEARS}Occupations_AllProjStatewide.xlsx"
PROJ_PAGE = "https://www.laworks.net/LaborMarketInfo/LMI_OccAllProj.asp?years=" + PROJ_YEARS
BLS_API = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Plain-language demand labels. Thresholds are average job openings per year, statewide.
DEMAND_LEVELS = [(1000, "Very high demand"), (400, "High demand"), (0, "Steady demand")]
FAST_GROWTH = 0.10  # 10-year growth at or above this earns a "Growing fast" tag


def load_projections() -> pd.DataFrame:
    r = requests.get(PROJ_URL, timeout=120)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), header=5)
    df = df.rename(columns={df.columns[0]: "soc", df.columns[1]: "title", df.columns[2]: "emp_base",
                            df.columns[3]: "emp_proj", df.columns[4]: "growth", df.columns[11]: "openings_10yr",
                            df.columns[13]: "median_annual", df.columns[18]: "education"})
    df = df[df["soc"].astype(str).str.match(r"^\d\d-\d{4}$")]
    return df.set_index("soc")


def load_wages(socs: list[str], start_socs: list[str]) -> tuple[dict, str]:
    """Median (13) annual wage for every code, plus the 25th percentile (12) for `start_socs`."""
    ids = {f"OEUS2200000000000{s.replace('-', '')}13": (s, "13") for s in socs}
    ids.update({f"OEUS2200000000000{s.replace('-', '')}12": (s, "12") for s in start_socs})
    payload = {"seriesid": list(ids)}
    if os.environ.get("BLS_API_KEY"):
        payload["registrationkey"] = os.environ["BLS_API_KEY"]
    out: dict = {s: {} for s in set(socs) | set(start_socs)}
    year = ""
    keys = list(ids)
    for i in range(0, len(keys), 25):
        payload["seriesid"] = keys[i:i + 25]
        j = requests.post(BLS_API, json=payload, timeout=60).json()
        if j.get("status") != "REQUEST_SUCCEEDED":
            raise SystemExit(f"BLS API: {j.get('status')} {j.get('message')}")
        for s in j.get("Results", {}).get("series", []):
            if not s["data"] or not s["data"][0]["value"].replace(".", "").isdigit():
                continue  # no data, or suppressed ("-")
            soc, d = ids[s["seriesID"]]
            latest = s["data"][0]
            year = max(year, latest["year"])
            out[soc]["start" if d == "12" else "typical"] = int(float(latest["value"]))
    return out, year


EDU_ORDER = ["After high school", "Certificate or 2-year degree", "4-year degree or more"]
# Groups listed first; the rest follow in order of total openings.
GROUP_ORDER_FIRST = ["Skilled Trades & Related", "Healthcare"]


def build_groups(occ: pd.DataFrame, proj: pd.DataFrame, wages: dict) -> list[dict]:
    """One record per sheet row. Combined rows add up openings and use an openings-weighted average wage."""
    rows = []
    for r in occ.itertuples():
        codes = [c.strip() for c in r.soc_codes.split(",")]
        opens, pay_w = [], []
        for c in codes:
            p = proj.loc[c]
            o = float(p["openings_10yr"]) / 10
            w = wages.get(c, {}).get("typical") or int(float(p["median_annual"]))  # LA Works median as fallback
            opens.append(o)
            pay_w.append(w)
        total = sum(opens)
        pay = sum(o * w for o, w in zip(opens, pay_w)) / total if total else None
        rows.append({"name": r.occupation, "soc": codes, "group": r.group, "subgroup": r.subgroup or None,
                     "education": EDU_ORDER.index(r.education), "openings": int(round(total)),
                     "pay": int(round(pay, -2)) if pay else None})
    groups = {}
    for row in rows:
        groups.setdefault(row.pop("group"), []).append(row)
    order = GROUP_ORDER_FIRST + sorted((g for g in groups if g not in GROUP_ORDER_FIRST),
                                       key=lambda g: -sum(x["openings"] for x in groups[g]))
    return [{"name": g, "careers": sorted(groups[g], key=lambda x: -x["openings"])} for g in order]


def main() -> None:
    content = json.loads((HERE / "content.json").read_text())
    socs = [j["soc"] for s in content["sectors"] for j in s["jobs"]]
    occ = pd.read_csv(HERE / "occupations.csv", dtype=str).fillna("")
    all_codes = sorted({c.strip() for v in occ["soc_codes"] for c in v.split(",")} | set(socs))
    proj = load_projections()
    wages, wage_year = load_wages(all_codes, socs)
    content["groups"] = build_groups(occ, proj, wages)
    content["education_levels"] = EDU_ORDER

    for sector in content["sectors"]:
        for job in sector["jobs"]:
            p = proj.loc[job["soc"]]
            per_year = float(p["openings_10yr"]) / 10
            growth = float(p["growth"]) / float(p["emp_base"])
            job["openings_per_year"] = int(round(per_year, -1))
            job["demand"] = next(label for floor, label in DEMAND_LEVELS if per_year >= floor)
            job["growing_fast"] = growth >= FAST_GROWTH
            job["pay_start"] = wages[job["soc"]].get("start")
            job["pay_typical"] = wages[job["soc"]].get("typical")
            # kept for staff reference only; the page does not show these
            job["_lmi"] = {"title": p["title"], "emp_2024": int(p["emp_base"]),
                           "emp_2034": int(p["emp_proj"]), "growth_pct": round(growth * 100, 1)}

    content.pop("_readme", None)
    content["sources"] = {
        "projections": f"Louisiana Works, Long-Term Occupational Projections {PROJ_YEARS[:4]}-{PROJ_YEARS[4:]} (statewide)",
        "projections_url": PROJ_PAGE,
        "wages": f"U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics, Louisiana, May {wage_year}",
        "wages_url": "https://www.bls.gov/oes/current/oes_la.htm",
        "built": date.today().isoformat(),
    }
    js = "// Generated by build_data.py. Edit content.json, then rebuild.\nwindow.TOP_JOBS = " + \
        json.dumps(content, indent=2) + ";\n"
    (HERE / "data.js").write_text(js)
    print(f"Wrote {HERE / 'data.js'} ({len(socs)} jobs, wages May {wage_year})")


if __name__ == "__main__":
    main()
