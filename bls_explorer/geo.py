"""Geography model.

A Geo is a named set of QCEW area codes. Single-code geos (U.S., a state,
a county, a published MSA) use BLS values directly; multi-code geos (metros
built from parishes, custom regions) are summed from their components.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config as C
from . import qcew

WATCHLIST_FILE = Path(__file__).resolve().parent.parent / "watchlists.json"


@dataclass(frozen=True)
class Geo:
    key: str
    name: str
    codes: tuple
    kind: str                     # us | state | county | metro | region | msa
    short: str = field(default="", compare=False)

    @property
    def label(self) -> str:
        return self.short or self.name

    @property
    def is_composite(self) -> bool:
        return len(self.codes) > 1


US = Geo("US000", "United States", ("US000",), "us", "U.S.")


def state(fips2: str) -> Geo:
    name, abbr = C.STATES[fips2]
    return Geo(f"{fips2}000", name, (f"{fips2}000",), "state", abbr)


LOUISIANA = state(C.LA)


def parish(fips: str) -> Geo:
    return Geo(fips, C.LA_PARISHES[fips], (fips,), "county", C.LA_PARISHES[fips].replace(" Parish", ""))


def la_metro(code: str) -> Geo:
    table = {**C.LA_METROS, **C.LA_MICROS, **C.LA_CSAS}
    name, parishes = table[code]
    return Geo(f"LA-{code}", name, tuple(parishes), "metro", name.replace(" MSA", "").replace(" MicroSA", ""))


def region(name: str, codes) -> Geo:
    codes = tuple(sorted(set(codes)))
    if len(codes) == 1 and codes[0] in C.LA_PARISHES:
        return parish(codes[0])
    return Geo("R-" + "-".join(codes), name, codes, "region", name)


def county(fips: str) -> Geo:
    if fips in C.LA_PARISHES:
        return parish(fips)
    title = qcew.area_titles().get(fips, fips)
    return Geo(fips, title, (fips,), "county", title.split(",")[0])


def published_msa(code: str) -> Geo:
    title = qcew.area_titles().get(code, code)
    return Geo(code, title, (code,), "msa", title.split(",")[0])


def all_la_parishes() -> list[Geo]:
    return [parish(f) for f in C.LA_PARISHES]


def all_states() -> list[Geo]:
    return [state(f) for f in C.STATES]


def la_metros(include_micro: bool = True, include_csa: bool = False) -> list[Geo]:
    codes = list(C.LA_METROS)
    if include_micro:
        codes += list(C.LA_MICROS)
    if include_csa:
        codes += list(C.LA_CSAS)
    return [la_metro(c) for c in codes]


def counties_in_state(fips2: str) -> dict:
    if fips2 == C.LA:
        return dict(C.LA_PARISHES)
    titles = qcew.area_titles()
    return {k: v for k, v in titles.items()
            if len(k) == 5 and k.isdigit() and k.startswith(fips2) and not k.endswith("000")
            and int(k[2:]) < 900}


def msas_in_state(abbr: str) -> dict:
    titles = qcew.area_titles()
    out = {}
    for k, v in titles.items():
        if not k.startswith("C") or k.startswith("CS"):
            continue
        tail = v.split(",")[-1]
        if abbr in tail.replace("-", " ").split():
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Watchlists (presets in config + user-saved in watchlists.json)
# ---------------------------------------------------------------------------
def load_watchlists() -> dict:
    lists = {k: dict(v, builtin=True) for k, v in C.WATCHLIST_PRESETS.items()}
    try:
        if WATCHLIST_FILE.exists():
            for k, v in json.loads(WATCHLIST_FILE.read_text()).items():
                # A saved list with a built-in's name is the user's customized version of it.
                lists[k] = dict(v, builtin=k in C.WATCHLIST_PRESETS, customized=k in C.WATCHLIST_PRESETS)
    except (OSError, ValueError):
        pass
    return lists


def save_watchlist(name: str, parishes: list, industries: list, baseline: str, notes: str = ""):
    data = {}
    try:
        if WATCHLIST_FILE.exists():
            data = json.loads(WATCHLIST_FILE.read_text())
    except (OSError, ValueError):
        data = {}
    data[name] = {"parishes": list(parishes), "industries": list(industries),
                  "baseline": baseline, "notes": notes}
    WATCHLIST_FILE.write_text(json.dumps(data, indent=2))


def delete_watchlist(name: str):
    try:
        data = json.loads(WATCHLIST_FILE.read_text())
        data.pop(name, None)
        WATCHLIST_FILE.write_text(json.dumps(data, indent=2))
    except (OSError, ValueError):
        pass
