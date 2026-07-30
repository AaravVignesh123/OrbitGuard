"""Correctness tests for the OrbitGuard screening pipeline.

Run with:  python -m pytest tests/ -q   (or plain `python tests/test_pipeline.py`)

These are deterministic and offline — no network, no live catalog.
"""

import datetime as _dt
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from orbitguard import screen, risk, refine, focus  # noqa: E402
from orbitguard.propagate import PositionCube, build_time_grid  # noqa: E402
from skyfield.api import EarthSatellite, load  # noqa: E402


# A real ISS TLE (epoch 2026-209) — fixed so tests are reproducible.
ISS_L1 = "1 25544U 98067A   26210.12010945  .00008919  00000+0  16839-3 0  9999"
ISS_L2 = "2 25544  51.6320  92.5700 0002829  30.0000 330.0000 15.50000000    05"


def test_kdtree_matches_bruteforce():
    """The KD-tree screen must return exactly the brute-force pairs."""
    rng = np.random.default_rng(1)
    pos = rng.normal(0, 40, (300, 3))
    assert screen.validate_kdtree(pos, 10.0)
    bf = screen.close_pairs_bruteforce(pos, 10.0)
    kd = screen.close_pairs_kdtree(pos, 10.0)
    assert len(bf) == len(kd) > 0
    # distances agree to floating precision
    dk = {(i, j): d for i, j, d in kd}
    for i, j, d in bf:
        assert abs(dk[(i, j)] - d) < 1e-9


def test_no_self_or_duplicate_pairs():
    rng = np.random.default_rng(2)
    pos = rng.normal(0, 30, (150, 3))
    pairs = screen.close_pairs_kdtree(pos, 15.0)
    for i, j, _ in pairs:
        assert i < j  # no self-pairs, no double counting


def test_event_grouping_collapses_consecutive_hits():
    """Two objects close across steps 3..7 should form ONE event at the min."""
    N, T = 3, 12
    pos = np.zeros((N, T, 3), dtype=np.float32)
    # Object 0 sits at origin; object 1 sweeps past it, closest at step 5.
    pos[0, :, :] = 0.0
    for k in range(T):
        pos[1, k, 0] = abs(k - 5) * 2.0  # min distance (=0-ish) at step 5
    pos[2, :, 0] = 5000.0  # far away, never flagged
    cube = PositionCube(
        positions=pos,
        times=build_time_grid(_dt.datetime(2026, 1, 1), hours=(T * 60) / 3600, step_s=60),
        epochs_utc=np.array([np.datetime64("2026-01-01")] * T),
        step_s=60.0,
        valid=np.ones(N, bool),
    )
    events = screen.screen(cube, threshold_km=10.0)
    pair_events = [e for e in events if {e.i, e.j} == {0, 1}]
    assert len(pair_events) == 1
    assert pair_events[0].k_min == 5


def test_parabola_vertex():
    """Parabola fit recovers the analytic minimum of a known quadratic."""
    x = np.array([-1.0, 0.0, 1.0])
    y = 3.0 * (x - 0.25) ** 2 + 2.0  # vertex at x=0.25, y=2
    xv, yv = refine._parabola_min(x, y)
    assert abs(xv - 0.25) < 1e-9
    assert abs(yv - 2.0) < 1e-9


def test_risk_ranking_orders_scary_first():
    """Smaller miss + higher speed must outrank a distant slow pass."""
    def mk(miss, speed):
        return refine.RefinedEvent(
            i=0, j=1, name_i="A", name_j="B", norad_i=1, norad_j=2,
            tca_utc=_dt.datetime(2026, 1, 1), miss_km=miss, coarse_miss_km=miss,
            rel_speed_kms=speed, alt_km=500.0,
        )
    events = [mk(9.0, 1.0), mk(0.5, 12.0), mk(3.0, 7.0)]
    ranked = risk.rank_events(events)
    assert ranked[0].event.miss_km == 0.5   # scariest first
    assert ranked[-1].event.miss_km == 9.0  # least scary last
    assert ranked[0].rank == 1


def _mk_ranked(pairs):
    """pairs: list of (name_i, norad_i, name_j, norad_j, miss, speed)."""
    evs = []
    for ni, ii, nj, jj, miss, spd in pairs:
        evs.append(refine.RefinedEvent(
            i=ii, j=jj, name_i=ni, name_j=nj, norad_i=ii, norad_j=jj,
            tca_utc=_dt.datetime(2026, 1, 1), miss_km=miss, coarse_miss_km=miss,
            rel_speed_kms=spd, alt_km=500.0))
    return risk.rank_events(evs)


def test_focus_by_name_and_norad():
    ranked = _mk_ranked([
        ("STARLINK-1", 101, "DEBRIS-A", 900, 0.5, 12.0),
        ("STARLINK-1", 101, "DEBRIS-B", 901, 3.0, 6.0),
        ("ONEWEB-9", 202, "DEBRIS-C", 902, 1.0, 8.0),
    ])
    by_name = focus.threats_to(ranked, "starlink-1")
    by_id = focus.threats_to(ranked, "101")
    assert len(by_name) == 2 and len(by_id) == 2
    # risk-sorted: the 0.5 km / 12 km/s pass outranks the 3 km / 6 km/s one
    assert by_name[0].event.miss_km == 0.5
    assert focus.threats_to(ranked, "does-not-exist") == []


def test_most_threatened_leaderboard():
    ranked = _mk_ranked([
        ("SAT-A", 1, "SAT-B", 2, 0.3, 13.0),   # very scary
        ("SAT-C", 3, "SAT-D", 4, 8.0, 3.0),    # mild
    ])
    board = focus.most_threatened(ranked, top=10)
    # every object appears once, scariest object first
    assert board[0]["norad"] in (1, 2)
    assert {row["norad"] for row in board} == {1, 2, 3, 4}
    assert board[0]["miss_km"] == 0.3


def test_refinement_beats_coarse_grid():
    """Refined miss distance must be <= the coarse-grid separation for a real pass."""
    ts = load.timescale()
    iss = EarthSatellite(ISS_L1, ISS_L2, "ISS", ts)
    # A twin trailing by a few seconds -> a close, fast conjunction geometry.
    twin = EarthSatellite(ISS_L1, ISS_L2.replace("330.0000", "330.2000"), "TWIN", ts)
    start = iss.epoch.utc_datetime().replace(tzinfo=None)
    from orbitguard import propagate
    cube = propagate.propagate([iss, twin], start=start, hours=1.0, step_s=60.0, ts=ts)
    events = screen.screen(cube, threshold_km=50.0)
    assert events, "expected at least one close approach for the ISS twin"
    ev = min(events, key=lambda e: e.dist_min_km)
    ref = refine.refine_event(iss, twin, cube, ev, ts=ts)
    assert ref.miss_km <= ev.dist_min_km + 1e-6
    assert ref.rel_speed_kms >= 0.0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} tests passed.")
