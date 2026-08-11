"""Reporting — assemble ranked events into a CSV, a JSON, and a summary.

The CSV is the human/analyst artifact (pair, TCA, miss distance, risk). The JSON
carries everything the dashboard needs, including a little geometry for the top
events so the web page can draw the two orbit arcs and the close-approach point.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from typing import List, Optional

import numpy as np
import pandas as pd
from skyfield.api import load

from .risk import RankedEvent


def to_dataframe(ranked: List[RankedEvent]) -> pd.DataFrame:
    rows = []
    for re in ranked:
        e = re.event
        rows.append(
            {
                "rank": re.rank,
                "object_a": e.name_i,
                "norad_a": e.norad_i,
                "object_b": e.name_j,
                "norad_b": e.norad_j,
                "tca_utc": e.tca_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "miss_km": round(e.miss_km, 4),
                "coarse_miss_km": round(e.coarse_miss_km, 3),
                "rel_speed_kms": round(e.rel_speed_kms, 3),
                "alt_km": round(e.alt_km, 1),
                "risk_score": round(re.risk_score, 1),
                "pc": _fmt_pc(getattr(e, "pc", float("nan"))),
                "pc_max": _fmt_pc(getattr(e, "pc_max", float("nan"))),
            }
        )
    return pd.DataFrame(rows)


def _fmt_pc(pc):
    """Pc as a compact float (or None) — kept full precision for the CSV/JSON."""
    import math
    return None if pc is None or (isinstance(pc, float) and math.isnan(pc)) else float(f"{pc:.3e}")


def write_csv(ranked: List[RankedEvent], path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df = to_dataframe(ranked)
    df.to_csv(path, index=False)
    return path


def _orbit_arc(sat, tca_dt: _dt.datetime, minutes: float, step_s: float, ts) -> list:
    """Sample an object's position (km, GCRS) around TCA for plotting."""
    n = int(round(2 * minutes * 60 / step_s)) + 1
    offs = np.linspace(-minutes * 60, minutes * 60, n)
    t = ts.utc(
        tca_dt.year, tca_dt.month, tca_dt.day, tca_dt.hour, tca_dt.minute,
        tca_dt.second + tca_dt.microsecond * 1e-6 + offs,
    )
    p = sat.at(t).position.km  # (3, n)
    return p.T.tolist()


def build_globe(cube, *, sample_n: int = 260, path_points: int = 48) -> dict:
    """Sample real orbit paths from the position cube for the 3D globe.

    We take an even sample of the valid objects and, for each, downsample the
    first ~orbital-period of its propagated positions into a short polyline
    (ECI km). The web globe scales these to Earth radius = 1 and animates each
    satellite along its own path. Rounded to whole km — invisible at globe scale,
    and keeps the payload small.
    """
    pos = cube.positions          # (N, T, 3) km, GCRS/ECI
    valid = np.where(cube.valid)[0]
    N, T, _ = pos.shape
    # ~one LEO period at 60 s steps ≈ 96 samples; clamp to the window.
    path_len = min(96, T)
    pick = np.linspace(0, path_len - 1, min(path_points, path_len)).astype(int)

    if len(valid) > sample_n:
        sel = valid[np.linspace(0, len(valid) - 1, sample_n).astype(int)]
    else:
        sel = valid

    sats = []
    for idx in sel:
        path = pos[idx, :path_len, :][pick]          # (path_points, 3)
        if not np.all(np.isfinite(path)):
            continue
        r0 = float(np.linalg.norm(path[0]))
        alt = r0 - 6371.0
        # colour band: LEO / MEO / high
        band = 0 if alt < 2000 else (1 if alt < 25000 else 2)
        sats.append({"p": np.round(path).astype(int).tolist(), "b": band})

    return {
        "earth_radius_km": 6371.0,
        "count_total": int(cube.valid.sum()),
        "sample_n": len(sats),
        "sats": sats,
    }


_MU_EARTH = 398600.4418  # km^3 / s^2


def _tle_altitude_band(l2: str) -> int:
    """Rough altitude band from a TLE's mean motion (for globe colouring)."""
    try:
        n_rev_day = float(l2[52:63])
        n = n_rev_day * 2.0 * np.pi / 86400.0          # rad/s
        a = (_MU_EARTH / (n * n)) ** (1.0 / 3.0)        # km, semi-major axis
        alt = a - 6371.0
    except Exception:
        return 0
    return 0 if alt < 2000 else (1 if alt < 25000 else 2)


def build_globe_tles(tle_path: str, *, sample_n: int = 700) -> dict:
    """Sample TLE line-pairs from the raw snapshot for LIVE in-browser SGP4.

    The web globe runs satellite.js on these to propagate every sampled object to
    the *current* time, so positions are live and geo-accurate — not a frozen
    snapshot. We only ship a sample to keep the payload light and the per-frame
    propagation cheap.
    """
    with open(tle_path) as fh:
        lines = [ln.rstrip("\n") for ln in fh]

    recs = []
    i, n = 0, len(lines)
    while i < n:
        name = lines[i].strip()
        if name.startswith("1 ") or name.startswith("2 "):
            l1, l2 = name, lines[i + 1] if i + 1 < n else ""
            i += 2
        else:
            l1 = lines[i + 1] if i + 1 < n else ""
            l2 = lines[i + 2] if i + 2 < n else ""
            i += 3
        if l1.startswith("1 ") and l2.startswith("2 "):
            recs.append((l1, l2))

    if len(recs) > sample_n:
        idx = np.linspace(0, len(recs) - 1, sample_n).astype(int)
        recs = [recs[k] for k in idx]

    tles = [{"l1": l1, "l2": l2, "b": _tle_altitude_band(l2)} for l1, l2 in recs]
    return {"earth_radius_km": 6371.0, "sample_n": len(tles), "tles": tles}


def build_json(
    ranked: List[RankedEvent],
    *,
    meta: dict,
    sats_by_index: Optional[dict] = None,
    top_geometry: int = 5,
    cube=None,
    tle_path: Optional[str] = None,
    ts=None,
) -> dict:
    """Build the dashboard payload. ``sats_by_index`` maps catalog index -> sat.

    For the top ``top_geometry`` events we embed short orbit arcs and the
    close-approach point so the web page can render a 3D scene with no backend.
    """
    ts = ts or load.timescale()
    df = to_dataframe(ranked)

    geometry = []
    if sats_by_index is not None:
        for re in ranked[:top_geometry]:
            e = re.event
            sat_i = sats_by_index.get(e.i)
            sat_j = sats_by_index.get(e.j)
            if sat_i is None or sat_j is None:
                continue
            geometry.append(
                {
                    "rank": re.rank,
                    "object_a": e.name_i,
                    "object_b": e.name_j,
                    "tca_utc": e.tca_utc.strftime("%Y-%m-%d %H:%M:%S"),
                    "miss_km": round(e.miss_km, 3),
                    "rel_speed_kms": round(e.rel_speed_kms, 3),
                    "risk_score": round(re.risk_score, 1),
                    "pc": _fmt_pc(getattr(e, "pc", float("nan"))),
                    "arc_a": _orbit_arc(sat_i, e.tca_utc, 12, 20, ts),
                    "arc_b": _orbit_arc(sat_j, e.tca_utc, 12, 20, ts),
                    "point_a": sat_i.at(_single_time(e.tca_utc, ts)).position.km.tolist(),
                    "point_b": sat_j.at(_single_time(e.tca_utc, ts)).position.km.tolist(),
                }
            )

    payload = {
        "meta": meta,
        "summary": {
            "n_events": len(ranked),
            "closest_km": float(df["miss_km"].min()) if len(df) else None,
            "median_miss_km": float(df["miss_km"].median()) if len(df) else None,
            "fastest_kms": float(df["rel_speed_kms"].max()) if len(df) else None,
        },
        "events": df.to_dict(orient="records"),
        "geometry": geometry,
    }
    if tle_path is not None:
        payload["globe"] = build_globe_tles(tle_path)   # live SGP4 in the browser
    elif cube is not None:
        payload["globe"] = build_globe(cube)             # legacy precomputed paths
    return payload


def _single_time(dt: _dt.datetime, ts):
    return ts.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                  dt.second + dt.microsecond * 1e-6)


def write_json(payload: dict, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=2)
    return path


def print_summary(ranked: List[RankedEvent], meta: dict, top: int = 15) -> None:
    df = to_dataframe(ranked)
    print("\n" + "=" * 74)
    print(f"OrbitGuard conjunction report — group '{meta.get('group')}' "
          f"| window {meta.get('hours')} h | threshold {meta.get('threshold_km')} km")
    print(f"Catalog: {meta.get('n_objects')} objects | screened {meta.get('start_utc')} UTC")
    print("=" * 74)
    if df.empty:
        print("No conjunctions found within the threshold.")
        return
    print(f"{len(df)} candidate events. Top {min(top, len(df))} by risk:\n")
    show = df.head(top)[
        ["rank", "object_a", "object_b", "tca_utc", "miss_km", "rel_speed_kms", "risk_score"]
    ]
    with pd.option_context("display.max_rows", None, "display.width", 200,
                           "display.max_colwidth", 26):
        print(show.to_string(index=False))
    print("\nClosest approach: {:.3f} km | Highest closing speed: {:.2f} km/s"
          .format(df["miss_km"].min(), df["rel_speed_kms"].max()))
