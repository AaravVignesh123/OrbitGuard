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

from . import risk_pc as _risk_pc
from .propagate import PositionCube
from .screen import CandidateEvent


def _tle_age_days(sat, at_dt) -> float:
    """Days between a satellite's TLE epoch and ``at_dt`` (>= 0)."""
    try:
        epoch = sat.epoch.utc_datetime().replace(tzinfo=None)
        return max((at_dt - epoch).total_seconds() / 86400.0, 0.0)
    except Exception:
        return 0.0


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
    pc: float = float("nan")          # Foster 2-D Pc under assumed covariance
    pc_max: float = float("nan")      # worst-case (max) Pc
    ml_risk: float = float("nan")     # Phase-4 experimental learned risk (log10 Pc)
    rel_pos_rtn_km: tuple = (0.0, 0.0, 0.0)   # miss vector in object-A RTN frame
    rel_vel_rtn_kms: tuple = (0.0, 0.0, 0.0)  # relative velocity in object-A RTN frame


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


def _separation(sat_i, sat_j, flag_dt, offsets, ts):
    """Separation (km) between two objects at ``flag_dt + offsets`` (seconds)."""
    t = ts.utc(
        flag_dt.year, flag_dt.month, flag_dt.day, flag_dt.hour, flag_dt.minute,
        flag_dt.second + flag_dt.microsecond * 1e-6 + offsets,
    )
    ei, ej = sat_i.at(t), sat_j.at(t)
    sep = np.linalg.norm(ei.position.km - ej.position.km, axis=0)
    return sep, ei, ej


def refine_event(
    sat_i: EarthSatellite,
    sat_j: EarthSatellite,
    cube: PositionCube,
    event: CandidateEvent,
    *,
    bracket_s: float = 45.0,
    step_s: float = 1.0,
    hbr_m: float = _risk_pc.DEFAULT_HBR_M,
    ts=None,
) -> RefinedEvent:
    """Refine one candidate to a precise TCA, miss distance and closing speed.

    A fast conjunction's minimum is an extremely sharp notch — for a 14 km/s pass
    with a 0.3 km miss it is only ~0.02 s wide — so no affordable time grid lands
    in it, and fitting the *distance* curve (a hyperbola near the min) over a
    coarse grid over-estimates the miss by hundreds of metres.

    Instead we use the standard analytic close-approach solution. Propagate both
    objects across a tight ±``bracket_s`` window (the coarse 60 s flag is within
    ±30 s of the true TCA), take the relative position ``r`` and velocity ``v`` at
    the nearest sample, and correct to the true minimum assuming constant relative
    velocity over that fraction of a second::

        ΔT = -(r·v) / |v|²          # time from the sample to closest approach
        miss = | r + v·ΔT |          # perpendicular miss distance
        TCA  = sample_time + ΔT

    This is exact for linear relative motion; over ≤0.5 s the orbital curvature
    error is ~2 m. Validated against a 0.01 s brute-force search
    (``tests/test_miss_distance_matches_independent_ground_truth``).
    """
    ts = ts or load.timescale()
    flag_dt = cube.times[event.k_min].utc_datetime().replace(tzinfo=None)

    n = int(round(2 * bracket_s / step_s)) + 1
    offs = np.linspace(-bracket_s, bracket_s, n)
    sep, ei, ej = _separation(sat_i, sat_j, flag_dt, offs, ts)
    k = int(np.argmin(sep))

    r = ei.position.km[:, k] - ej.position.km[:, k]        # relative position (km)
    v = ei.velocity.km_per_s[:, k] - ej.velocity.km_per_s[:, k]   # relative velocity (km/s)
    vv = float(np.dot(v, v))
    if vv > 1e-9:
        dT = -float(np.dot(r, v)) / vv
        dT = max(min(dT, step_s), -step_s)                # stay within the sampled bracket
        miss = float(np.linalg.norm(r + v * dT))
    else:                                                 # co-moving (e.g. docked modules)
        dT, miss = 0.0, float(sep[k])
    miss = min(miss, float(sep[k]))                       # analytic value is a minimum

    tca_dt = flag_dt + _dt.timedelta(seconds=float(offs[k] + dT))
    rel_speed = float(np.sqrt(vv))
    pos_a = ei.position.km[:, k]; vel_a = ei.velocity.km_per_s[:, k]
    pos_b = ej.position.km[:, k]; vel_b = ej.velocity.km_per_s[:, k]
    r_i = np.linalg.norm(pos_a)
    r_j = np.linalg.norm(pos_b)
    alt_km = float((r_i + r_j) / 2.0 - _EARTH_RADIUS_KM)

    # --- Probability of Collision (Foster 2-D, under assumed covariance) ---------
    r_miss = r + v * dT                                    # miss vector at TCA (km)
    pc = pc_max = float("nan")
    rel_pos_rtn = rel_vel_rtn = (0.0, 0.0, 0.0)
    if vv > 1e-9:
        try:
            age_a = _tle_age_days(sat_i, flag_dt)
            age_b = _tle_age_days(sat_j, flag_dt)
            alt_a = float(r_i - _EARTH_RADIUS_KM)   # per-object altitude → drag-scaled σ
            alt_b = float(r_j - _EARTH_RADIUS_KM)
            ca = _risk_pc.rtn_to_eci_cov(pos_a * 1e3, vel_a * 1e3, *_risk_pc.assumed_rtn_sigma(age_a, alt_a))
            cb = _risk_pc.rtn_to_eci_cov(pos_b * 1e3, vel_b * 1e3, *_risk_pc.assumed_rtn_sigma(age_b, alt_b))
            pc = float(_risk_pc.foster_pc(r_miss * 1e3, v * 1e3, ca, cb, hbr_m))
            pc_max = float(_risk_pc.max_pc(r_miss * 1e3, v * 1e3, ca, cb, hbr_m))
            rel_pos_rtn = _risk_pc.eci_to_rtn(pos_a, vel_a, r_miss)
            rel_vel_rtn = _risk_pc.eci_to_rtn(pos_a, vel_a, v)
        except Exception:
            pass

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
        pc=pc,
        pc_max=pc_max,
        rel_pos_rtn_km=rel_pos_rtn,
        rel_vel_rtn_kms=rel_vel_rtn,
    )
