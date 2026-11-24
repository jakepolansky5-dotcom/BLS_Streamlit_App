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
BLS_API_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"

# Plain-language demand labels. Thresholds are average job openings per year, statewide.
DEMAND_LEVELS = [(1000, "Very high demand"), (400, "High demand"), (0, "In demand")]
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


WAGE_CACHE = HERE / "wages_cache.json"


def _post(url: str, payload: dict) -> dict:
    return requests.post(url, json=payload, timeout=60).json()


def load_wages(socs: list[str], start_socs: list[str]) -> tuple[dict, str]:
    """Median (13) annual wage for every code, plus the 25th percentile (12) for `start_socs`.

    Uses the BLS API v2 (with BLS_API_KEY if set). If v2 refuses (e.g. the daily limit for
    requests without a key), falls back to v1. Values already in wages_cache.json are reused,
    so a rebuild only asks BLS for codes it hasn't seen; delete the cache to refresh everything."""
    cache = json.loads(WAGE_CACHE.read_text()) if WAGE_CACHE.exists() else {"year": "", "wages": {}}
    out: dict = {s: dict(cache["wages"].get(s, {})) for s in set(socs) | set(start_socs)}
    ids = {f"OEUS2200000000000{s.replace('-', '')}13": (s, "13") for s in socs if "typical" not in out[s]}
    ids.update({f"OEUS2200000000000{s.replace('-', '')}12": (s, "12")
                for s in start_socs if "start" not in out[s]})
    year = cache["year"]
    keys = list(ids)
    use_v1 = False
    for i in range(0, len(keys), 25):
        payload = {"seriesid": keys[i:i + 25]}
        j = None
        if not use_v1:
            if os.environ.get("BLS_API_KEY"):
                payload["registrationkey"] = os.environ["BLS_API_KEY"]
            j = _post(BLS_API, payload)
            if j.get("status") != "REQUEST_SUCCEEDED":
                print(f"BLS API v2 refused ({j.get('message')}); using v1")
                use_v1 = True
                payload.pop("registrationkey", None)
        if use_v1:
            j = _post(BLS_API_V1, payload)
        if j.get("status") != "REQUEST_SUCCEEDED":
            print(f"BLS API unavailable: {j.get('message')}")
            return None, year
        for ser in j.get("Results", {}).get("series", []):
            if not ser["data"] or not ser["data"][0]["value"].replace(".", "").isdigit():
                continue  # no data, or suppressed ("-")
            soc, d = ids[ser["seriesID"]]
            latest = ser["data"][0]
            year = max(year, latest["year"])
            out[soc]["start" if d == "12" else "typical"] = int(float(latest["value"]))
        cache["wages"].update(out)
        cache["year"] = year
        WAGE_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    return out, year


EDU_ORDER = ["After high school", "Certificate or 2-year degree", "4-year degree or more"]


def split_codes(v: str) -> list[str]:
    return [c.strip() for c in v.split(",") if c.strip()]


def build_groups(occ: pd.DataFrame, proj: pd.DataFrame, wages: dict, first: list[str]) -> list[dict]:
    """One record per sheet row. Combined rows add up openings and use an openings-weighted average wage.
    Groups in `first` (the focus areas, in order) come first; the rest follow by total openings."""
    rows = []
    for r in occ.itertuples():
        codes = split_codes(r.soc_codes)
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
    lead = [g for g in first if g in groups]
    order = lead + sorted((g for g in groups if g not in lead), key=lambda g: -sum(x["openings"] for x in groups[g]))
    return [{"name": g, "careers": sorted(groups[g], key=lambda x: -x["openings"])} for g in order]


def spotlight_numbers(codes: list[str], proj: pd.DataFrame, wages: dict) -> dict:
    """Demand and pay for a spotlight job. Several codes: openings add up, growth is pooled,
    and starting/typical pay are averages weighted by openings."""
    rows = [proj.loc[c] for c in codes]
    opens = [float(p["openings_10yr"]) / 10 for p in rows]
    per_year = sum(opens)
    growth = sum(float(p["growth"]) for p in rows) / sum(float(p["emp_base"]) for p in rows)

    def weighted(key):
        pairs = [(o, wages.get(c, {}).get(key)) for o, c in zip(opens, codes)]
        pairs = [(o, w) for o, w in pairs if w]
        return int(round(sum(o * w for o, w in pairs) / sum(o for o, _ in pairs))) if pairs else None

    return {
        "openings_per_year": int(round(per_year, -1)),
        "demand": next(label for floor, label in DEMAND_LEVELS if per_year >= floor),
        "growing_fast": growth >= FAST_GROWTH,
        "pay_start": weighted("start"),
        "pay_typical": weighted("typical"),
        # kept for staff reference only; the page does not show these
        "_lmi": {"titles": [p["title"] for p in rows], "emp_2024": int(sum(float(p["emp_base"]) for p in rows)),
                 "emp_2034": int(sum(float(p["emp_proj"]) for p in rows)), "growth_pct": round(growth * 100, 1)},
    }


ONET_WAGES = "https://www.onetonline.org/link/localwages/{code}?st=LA"
ONET_UA = {"User-Agent": "la-top-jobs-build/1.0 (static site build script)"}


def onet_wages(soc: str) -> dict:
    """Louisiana 25th percentile and median from O*NET OnLine, which republishes the same BLS OEWS
    estimates. Fallback when the BLS API refuses. Tries the .00 O*NET code, then .01."""
    import re
    for suffix in ("00", "01", "02", "03"):
        try:
            r = requests.get(ONET_WAGES.format(code=f"{soc}.{suffix}"), headers=ONET_UA, timeout=60)
        except requests.RequestException:
            continue
        if r.status_code != 200:
            continue
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
        m = re.search(r"Louisiana \$([\d,]+) \$([\d,]+) \$([\d,]+) \$([\d,]+) \$([\d,]+)", text)
        y = re.search(r"Bureau of Labor Statistics (\d{4}) wage data", text)
        if m:
            num = lambda v: int(v.replace(",", ""))
            return {"start": num(m.group(2)), "typical": num(m.group(3)), "year": y.group(1) if y else ""}
    return {}


def load_previous() -> dict | None:
    f = HERE / "data.js"
    if not f.exists():
        return None
    return json.loads(f.read_text().split("= ", 1)[1].rstrip().rstrip(";"))


def main() -> None:
    content = json.loads((HERE / "content.json").read_text())
    jobs = [j for s in content["sectors"] for j in s["jobs"]]
    spot_codes = sorted({c for j in jobs for c in split_codes(j["soc"])})
    occ = pd.read_csv(HERE / "occupations.csv", dtype=str).fillna("")
    all_codes = sorted({c for v in occ["soc_codes"] for c in split_codes(v)} | set(spot_codes))
    proj = load_projections()
    wages, wage_year = load_wages(all_codes, spot_codes)
    if wages is None:  # BLS API refused: use cached BLS values, then O*NET for missing starting pay
        cache = json.loads(WAGE_CACHE.read_text()) if WAGE_CACHE.exists() else {"year": "", "wages": {}}
        wages, wage_year = {c: dict(v) for c, v in cache["wages"].items()}, cache["year"]
        missing = [c for c in spot_codes if "start" not in wages.get(c, {})]
        missing += [c for c in all_codes if "typical" not in wages.get(c, {}) and c not in missing]
        for c in missing:
            o = onet_wages(c)
            if o and (not wage_year or o["year"] == wage_year):
                wages.setdefault(c, {}).update({k: o[k] for k in ("start", "typical")})
                print(f"  {c}: from O*NET (BLS {o['year']})")
            else:
                print(f"  {c}: no O*NET wages for {wage_year or 'the same year'}")
        # Codes still missing have no published Louisiana estimate: they drop out of weighted averages
        # (typical pay then falls back to the LA Works median).
        cache["wages"].update(wages)
        WAGE_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    prev = load_previous()
    stale = wages is None
    if stale:
        if not prev:
            raise SystemExit("BLS API unavailable and no previous data.js to fall back on. Try again tomorrow.")
        print("Keeping pay from the previous build; rerun once BLS is reachable to refresh it.")
        wages, wage_year = {}, prev["sources"]["wages"].rsplit(" ", 1)[-1]
    content["groups"] = build_groups(occ, proj, wages, [s["group"] for s in content["sectors"] if s.get("group")])
    content["education_levels"] = EDU_ORDER
    prev_pay = {tuple(c["soc"]): c["pay"] for g in (prev or {}).get("groups", []) for c in g["careers"]}
    prev_start = {tuple(j.get("codes") or [j["soc"]]): j.get("pay_start")
                  for s in (prev or {}).get("sectors", []) for j in s["jobs"]}
    if stale:
        for g in content["groups"]:
            for c in g["careers"]:
                c["pay"] = prev_pay.get(tuple(c["soc"]), c["pay"])

    for job in jobs:
        codes = split_codes(job["soc"])
        job["codes"] = codes
        job["anchor"] = "job-" + codes[0]
        job.update(spotlight_numbers(codes, proj, wages))
        if stale:
            job["pay_start"] = prev_start.get(tuple(codes))
            job["pay_typical"] = prev_pay.get(tuple(codes), job["pay_typical"])
    missing = [j["plural"] for j in jobs if not j["pay_start"]]
    if missing:
        print("No starting pay yet for:", ", ".join(missing))

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
    print(f"Wrote {HERE / 'data.js'} ({len(jobs)} spotlight jobs, wages May {wage_year})")


if __name__ == "__main__":
    main()
