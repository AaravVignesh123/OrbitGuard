"""SOCRATES cross-check — physical validation against CelesTrak's authoritative feed.

CelesTrak SOCRATES Plus publishes the operational conjunction list (its own fresh
element sets, its own screening). We fetch its top conjunctions, independently
reproduce each one with OrbitGuard (fetch both objects' current TLEs → propagate →
our TCA + miss → our Pc), and compare. This turns "our math is self-consistent"
into "and it agrees with the reference." Order-of-magnitude agreement is the bar —
element sets and epochs differ slightly between the two systems.

SOCRATES documents its max-probability covariance as RTN = (100 m, 300 m, 100 m),
so we use the same for an apples-to-apples max-Pc comparison.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
import urllib.request

import numpy as np

from . import risk_pc as _risk_pc

_TABLE_URL = ("https://celestrak.org/socrates/table-socrates.php"
              "?NAME=,&ORDER={order}&MAX={n}")
_CATNR_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR={cat}&FORMAT=TLE"
_UA = {"User-Agent": "Mozilla/5.0 OrbitGuard/1.0"}

# SOCRATES max-probability covariance (radial, in-track, cross-track), metres.
SOC_SIGMA_M = (100.0, 300.0, 100.0)


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def fetch_socrates(order: str = "MINRANGE", n: int = 6) -> list:
    """Return the top-``n`` SOCRATES conjunctions as dicts."""
    raw = _get(_TABLE_URL.format(order=order, n=n))
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.S | re.I):
        cells = [_html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        cells = [c for c in cells if c != ""]
        if len(cells) >= 5 and cells[1].isdigit():   # a data row (col 1 = NORAD id)
            rows.append(cells)
    out = []
    for k in range(0, len(rows) - 1, 2):             # primary + secondary rows pair up
        p, s = rows[k], rows[k + 1]
        try:
            out.append({
                "norad_a": int(p[1]), "name_a": p[2],
                "norad_b": int(s[1]), "name_b": s[2],
                "tca_utc": p[4], "min_range_km": float(p[5]),
                "rel_speed_kms": float(p[6]), "max_prob": float(s[4]),
            })
        except (ValueError, IndexError):
            continue
    return out


def _fetch_sat(cat: int, ts):
    from skyfield.api import EarthSatellite
    txt = _get(_CATNR_URL.format(cat=cat))
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    l1 = next(ln for ln in lines if ln.startswith("1 "))
    l2 = next(ln for ln in lines if ln.startswith("2 "))
    return EarthSatellite(l1, l2, str(cat), ts)


def reproduce(conj: dict, ts, half_min: float = 3.0, dt_s: float = 0.5) -> dict:
    """Independently compute OrbitGuard's miss + Pc for one SOCRATES conjunction."""
    sat_a = _fetch_sat(conj["norad_a"], ts)
    sat_b = _fetch_sat(conj["norad_b"], ts)
    t0 = _dt.datetime.strptime(conj["tca_utc"][:19], "%Y-%m-%d %H:%M:%S")
    offs = np.arange(-half_min * 60, half_min * 60 + dt_s, dt_s)
    t = ts.utc(t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second + offs)
    ea, eb = sat_a.at(t), sat_b.at(t)
    sep = np.linalg.norm(ea.position.km - eb.position.km, axis=0)
    k = int(np.argmin(sep))
    # analytic refine at the discrete min
    r = ea.position.km[:, k] - eb.position.km[:, k]
    v = ea.velocity.km_per_s[:, k] - eb.velocity.km_per_s[:, k]
    vv = float(v @ v)
    dT = -float(r @ v) / vv if vv > 1e-12 else 0.0
    dT = max(min(dT, dt_s), -dt_s)
    r_miss = (r + v * dT) * 1e3                       # metres
    ca = _risk_pc.rtn_to_eci_cov(ea.position.km[:, k] * 1e3, ea.velocity.km_per_s[:, k] * 1e3, *SOC_SIGMA_M)
    cb = _risk_pc.rtn_to_eci_cov(eb.position.km[:, k] * 1e3, eb.velocity.km_per_s[:, k] * 1e3, *SOC_SIGMA_M)
    our_max_pc = float(_risk_pc.max_pc(r_miss, v * 1e3, ca, cb, _risk_pc.DEFAULT_HBR_M))
    return {
        "our_miss_km": float(np.linalg.norm(r + v * dT)),
        "our_rel_speed_kms": float(np.sqrt(vv)),
        "our_max_pc": our_max_pc,
        "tca_offset_s": float(offs[k] + dT),
    }


def cross_check(order: str = "TCA", n: int = 6, ts=None) -> dict:
    """Fetch SOCRATES top-n and reproduce each; return a comparison block.

    Default order=TCA (soonest conjunctions) minimises TLE drift between SOCRATES'
    element sets and our freshly-fetched ones, so it's the fair comparison — multi-
    day predictions diverge purely from element freshness, not a method error.
    """
    from skyfield.api import load
    ts = ts or load.timescale()
    try:
        conjs = fetch_socrates(order=order, n=n)
    except Exception as e:
        return {"status": f"fetch failed: {type(e).__name__}", "events": []}
    if not conjs:
        return {"status": "no SOCRATES data returned", "events": []}

    events, miss_err = [], []
    for c in conjs:
        try:
            rep = reproduce(c, ts)
        except Exception:
            continue
        de = abs(rep["our_miss_km"] - c["min_range_km"]) * 1000.0
        miss_err.append(de)
        events.append({
            "pair": f'{c["name_a"]} ↔ {c["name_b"]}',
            "tca_utc": c["tca_utc"][:19],
            "socrates_miss_km": round(c["min_range_km"], 3),
            "our_miss_km": round(rep["our_miss_km"], 3),
            "miss_diff_m": round(de, 1),
            "socrates_max_prob": c["max_prob"],
            "our_max_pc": float(f'{rep["our_max_pc"]:.2e}'),
        })
    return {
        "status": "ok" if events else "reproduction failed",
        "source": "CelesTrak SOCRATES Plus",
        "order": order,
        "n_checked": len(events),
        "max_miss_diff_m": round(max(miss_err), 1) if miss_err else None,
        "median_miss_diff_m": round(float(np.median(miss_err)), 1) if miss_err else None,
        "events": events,
    }
