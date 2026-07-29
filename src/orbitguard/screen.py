"""Conjunction screening — find close pairs, fast, across the whole window.

The naive approach is O(n^2): every pair, every timestep. At 16 000 objects
that is ~1.3e8 pairs *per timestep* — a wall you hit immediately. Instead, at
each timestep we build a ``scipy.spatial.cKDTree`` and ask ``query_pairs(r)``
for only the pairs within ``r`` kilometres. A KD-tree answers that in roughly
O(n log n), turning minutes-per-timestep into milliseconds.

A genuine close approach shows up across several *consecutive* timesteps for the
same pair. We group those consecutive hits into a single candidate *event* and
remember the timestep where the two objects were closest — that coarse flag is
what Session-8 refinement then sharpens into a true time-of-closest-approach.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist, squareform

from .propagate import PositionCube


@dataclass
class CandidateEvent:
    """One close-approach candidate: a pair and its coarse closest timestep."""

    i: int  # index into the catalog
    j: int
    k_min: int  # timestep index of minimum separation (coarse grid)
    dist_min_km: float  # minimum separation on the coarse grid
    k_first: int  # first timestep the pair was within threshold
    k_last: int  # last timestep the pair was within threshold


def close_pairs_bruteforce(pos: np.ndarray, threshold_km: float) -> List[Tuple[int, int, float]]:
    """Reference O(n^2) screen at a single instant. Used to validate the KD-tree.

    ``pos`` is ``(n, 3)``. Returns sorted ``(i, j, dist)`` with ``i < j``.
    """
    D = squareform(pdist(pos))
    iu, ju = np.where((D < threshold_km) & (D > 0))
    out = [(int(i), int(j), float(D[i, j])) for i, j in zip(iu, ju) if i < j]
    out.sort()
    return out


def close_pairs_kdtree(pos: np.ndarray, threshold_km: float) -> List[Tuple[int, int, float]]:
    """Fast KD-tree screen at a single instant. Returns sorted ``(i, j, dist)``."""
    tree = cKDTree(pos)
    pairs = tree.query_pairs(r=threshold_km)
    out = []
    for i, j in pairs:
        if i > j:
            i, j = j, i
        d = float(np.linalg.norm(pos[i] - pos[j]))
        out.append((i, j, d))
    out.sort()
    return out


def validate_kdtree(pos: np.ndarray, threshold_km: float) -> bool:
    """Trust step: KD-tree pairs must equal brute-force pairs on a subset."""
    bf = {(i, j) for i, j, _ in close_pairs_bruteforce(pos, threshold_km)}
    kd = {(i, j) for i, j, _ in close_pairs_kdtree(pos, threshold_km)}
    return bf == kd


def screen(
    cube: PositionCube,
    threshold_km: float = 10.0,
    *,
    progress: bool = False,
) -> List[CandidateEvent]:
    """Screen the whole time grid and return grouped candidate events.

    For each timestep we KD-tree the *valid* objects and record every pair
    within ``threshold_km``. Hits for the same pair on consecutive timesteps are
    then collapsed into one event (keeping the closest step). Distinct passes of
    the same pair separated by a gap become separate events.
    """
    pos = cube.positions
    valid = cube.valid
    N, T, _ = pos.shape
    valid_idx = np.where(valid)[0]

    # For each pair, collect (timestep, distance) hits.
    hits: Dict[Tuple[int, int], List[Tuple[int, float]]] = {}

    for k in range(T):
        p = pos[valid_idx, k, :]
        tree = cKDTree(p)
        for a, b in tree.query_pairs(r=threshold_km):
            i, j = valid_idx[a], valid_idx[b]
            if i > j:
                i, j = j, i
            d = float(np.linalg.norm(pos[i, k] - pos[j, k]))
            hits.setdefault((i, j), []).append((k, d))
        if progress and k % 200 == 0:
            print(f"  screened timestep {k}/{T}", flush=True)

    events: List[CandidateEvent] = []
    for (i, j), series in hits.items():
        series.sort()
        # Split into runs of consecutive timesteps -> distinct passes.
        run: List[Tuple[int, float]] = [series[0]]
        for step in series[1:]:
            if step[0] == run[-1][0] + 1:
                run.append(step)
            else:
                events.append(_event_from_run(i, j, run))
                run = [step]
        events.append(_event_from_run(i, j, run))

    events.sort(key=lambda e: e.dist_min_km)
    return events


def _event_from_run(i: int, j: int, run: List[Tuple[int, float]]) -> CandidateEvent:
    k_min, d_min = min(run, key=lambda x: x[1])
    return CandidateEvent(
        i=i,
        j=j,
        k_min=k_min,
        dist_min_km=d_min,
        k_first=run[0][0],
        k_last=run[-1][0],
    )
