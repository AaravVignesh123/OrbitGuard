"""Propagation — evaluate every object on one shared clock.

Given a catalog and a time window we build a single time grid and propagate
every satellite to every timestamp, producing an ``(N, T, 3)`` cube of position
vectors in kilometres. Every object lives in the *same* reference frame
(skyfield's GCRS, an Earth-centred inertial frame), which is the one invariant
that makes pairwise distances meaningful — mixing frames is the classic way to
get garbage miss distances.

We keep positions as float32 to halve memory: a 16 000-object, 24 h @ 60 s run
is ~16000 x 1440 x 3 which is ~280 MB at float32.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from skyfield.api import EarthSatellite, load


@dataclass
class PositionCube:
    """Positions for every object at every timestep, on a shared clock."""

    positions: np.ndarray  # (N, T, 3) float32, km, GCRS
    times: object  # skyfield Time array of length T
    epochs_utc: np.ndarray  # (T,) datetime64 for convenience
    step_s: float
    valid: np.ndarray  # (N,) bool — False where propagation failed/blew up

    @property
    def n_objects(self) -> int:
        return self.positions.shape[0]

    @property
    def n_times(self) -> int:
        return self.positions.shape[1]


def build_time_grid(start: _dt.datetime, hours: float, step_s: float, ts=None):
    """Build a skyfield Time array covering ``[start, start+hours)``.

    ``start`` must be timezone-naive UTC (or tz-aware; we normalise to UTC).
    """
    ts = ts or load.timescale()
    if start.tzinfo is not None:
        start = start.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    n_steps = int(round(hours * 3600.0 / step_s))
    secs = np.arange(n_steps) * step_s
    # skyfield gracefully handles seconds > 60 by carrying into minutes/hours.
    times = ts.utc(
        start.year, start.month, start.day, start.hour, start.minute,
        start.second + start.microsecond * 1e-6 + secs,
    )
    return times


def propagate(
    sats: List[EarthSatellite],
    *,
    start: Optional[_dt.datetime] = None,
    hours: float = 24.0,
    step_s: float = 60.0,
    ts=None,
    progress: bool = False,
) -> PositionCube:
    """Propagate every satellite over the window into an ``(N, T, 3)`` cube.

    Objects whose propagation produces non-finite positions (a decayed or
    numerically unstable TLE) are flagged in ``valid`` and zero-filled so the
    downstream KD-tree never sees NaNs.
    """
    ts = ts or load.timescale()
    start = start or _dt.datetime.utcnow().replace(microsecond=0)
    times = build_time_grid(start, hours, step_s, ts=ts)
    T = len(times)
    N = len(sats)

    positions = np.zeros((N, T, 3), dtype=np.float32)
    valid = np.ones(N, dtype=bool)

    for idx, sat in enumerate(sats):
        try:
            p = sat.at(times).position.km  # (3, T)
            if not np.all(np.isfinite(p)):
                valid[idx] = False
                continue
            positions[idx] = p.T.astype(np.float32)
        except Exception:
            valid[idx] = False
        if progress and idx % 2000 == 0:
            print(f"  propagated {idx}/{N}", flush=True)

    epochs = times.utc_datetime()
    epochs_utc = np.array(
        [np.datetime64(e.replace(tzinfo=None)) for e in epochs]
    )
    return PositionCube(
        positions=positions,
        times=times,
        epochs_utc=epochs_utc,
        step_s=step_s,
        valid=valid,
    )
