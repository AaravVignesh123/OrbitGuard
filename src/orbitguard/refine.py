"""Refinement — turn a coarse flag into a real TCA and miss distance.

The coarse screen samples every 60 s, so its "minimum distance" is only as good
as the grid: two objects closing at ~14 km/s move ~840 km between samples, so
the true closest approach almost always falls *between* two coarse steps. For
each candidate we re-propagate just the two objects at 1 s cadence in a small
window around the flag, find the discrete minimum, then fit a parabola to the
three points bracketing it for a sub-second time-of-closest-approach (TCA) and a
refined miss distance.

We also grab each object's velocity at TCA (same GCRS frame as the positions) to
compute the relative velocity — the closing speed that drives the risk score.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Optional

import numpy as np
from skyfield.api import EarthSatellite, load

from .propagate import PositionCube
from .screen import CandidateEvent


@dataclass
class RefinedEvent:
    i: int
    j: int
    name_i: str
    name_j: str
    norad_i: int
    norad_j: int
    tca_utc: _dt.datetime
    miss_km: float
    coarse_miss_km: float
    rel_speed_kms: float
    alt_km: float  # geocentric radius midpoint minus Earth radius, rough altitude


_EARTH_RADIUS_KM = 6371.0


def _parabola_min(x: np.ndarray, y: np.ndarray) -> tuple:
    """Vertex of the parabola through three points (x, y). Returns (x*, y*)."""
    (x0, x1, x2), (y0, y1, y2) = x, y
    denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
    if denom == 0:
        return x1, y1
    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
    b = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
    if a <= 0:
        return x1, y1
    xv = -b / (2 * a)
    c = y1 - a * x1 * x1 - b * x1
    yv = a * xv * xv + b * xv + c
    return xv, yv


def refine_event(
    sat_i: EarthSatellite,
    sat_j: EarthSatellite,
    cube: PositionCube,
    event: CandidateEvent,
    *,
    window_s: float = 120.0,
    fine_step_s: float = 1.0,
    ts=None,
) -> RefinedEvent:
    """Refine one candidate to a precise TCA, miss distance and closing speed."""
    ts = ts or load.timescale()
    t_flag = cube.times[event.k_min]
    flag_dt = t_flag.utc_datetime().replace(tzinfo=None)

    n = int(round(2 * window_s / fine_step_s)) + 1
    offsets = np.linspace(-window_s, window_s, n)
    fine = ts.utc(
        flag_dt.year, flag_dt.month, flag_dt.day, flag_dt.hour, flag_dt.minute,
        flag_dt.second + flag_dt.microsecond * 1e-6 + offsets,
    )

    pi = sat_i.at(fine)
    pj = sat_j.at(fine)
    sep = np.linalg.norm(pi.position.km - pj.position.km, axis=0)  # (n,)

    kmin = int(np.argmin(sep))
    # Parabolic refinement using the bracketing triple (fallback to discrete).
    if 0 < kmin < n - 1:
        xs = offsets[kmin - 1 : kmin + 2]
        ys = sep[kmin - 1 : kmin + 2]
        t_star, miss = _parabola_min(xs, ys)
        # Guard: vertex must stay inside the bracket.
        if not (xs[0] <= t_star <= xs[2]):
            t_star, miss = offsets[kmin], sep[kmin]
    else:
        t_star, miss = offsets[kmin], sep[kmin]

    tca_dt = flag_dt + _dt.timedelta(seconds=float(t_star))

    # Velocities at the discrete closest sample (1 s away from TCA at most).
    vi = pi.velocity.km_per_s[:, kmin]
    vj = pj.velocity.km_per_s[:, kmin]
    rel_speed = float(np.linalg.norm(vi - vj))

    # Rough altitude at closest approach (midpoint radius - Earth radius).
    r_i = np.linalg.norm(pi.position.km[:, kmin])
    r_j = np.linalg.norm(pj.position.km[:, kmin])
    alt_km = float((r_i + r_j) / 2.0 - _EARTH_RADIUS_KM)

    return RefinedEvent(
        i=event.i,
        j=event.j,
        name_i=sat_i.name,
        name_j=sat_j.name,
        norad_i=int(sat_i.model.satnum),
        norad_j=int(sat_j.model.satnum),
        tca_utc=tca_dt,
        miss_km=float(miss),
        coarse_miss_km=float(event.dist_min_km),
        rel_speed_kms=rel_speed,
        alt_km=alt_km,
    )
