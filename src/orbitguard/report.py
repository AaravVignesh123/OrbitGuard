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
            }
        )
    return pd.DataFrame(rows)


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


def build_json(
    ranked: List[RankedEvent],
    *,
    meta: dict,
    sats_by_index: Optional[dict] = None,
    top_geometry: int = 5,
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
                    "arc_a": _orbit_arc(sat_i, e.tca_utc, 12, 20, ts),
                    "arc_b": _orbit_arc(sat_j, e.tca_utc, 12, 20, ts),
                    "point_a": sat_i.at(_single_time(e.tca_utc, ts)).position.km.tolist(),
                    "point_b": sat_j.at(_single_time(e.tca_utc, ts)).position.km.tolist(),
                }
            )

    return {
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
