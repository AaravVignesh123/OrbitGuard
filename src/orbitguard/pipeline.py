"""End-to-end pipeline: catalog -> propagate -> screen -> refine -> rank -> report.

This is the orchestration layer the CLI calls. Each stage is a thin wrapper over
the corresponding module so the flow reads top-to-bottom like the README diagram.
"""

from __future__ import annotations

import datetime as _dt
import time
from dataclasses import dataclass
from typing import List, Optional

from skyfield.api import load

from . import catalog as _catalog
from . import propagate as _propagate
from . import refine as _refine
from . import report as _report
from . import risk as _risk
from . import screen as _screen


@dataclass
class PipelineResult:
    ranked: List[_risk.RankedEvent]
    meta: dict
    sats_by_index: dict
    catalog: _catalog.Catalog
    cube: object = None  # PositionCube — positions for the globe visualization


def run(
    *,
    group: str = "active",
    hours: float = 24.0,
    step_s: float = 60.0,
    threshold_km: float = 10.0,
    max_objects: Optional[int] = None,
    start: Optional[_dt.datetime] = None,
    data_dir: str = "data",
    force_download: bool = False,
    hbr_m: float = 10.0,
    verbose: bool = True,
) -> PipelineResult:
    ts = load.timescale()
    start = start or _dt.datetime.utcnow().replace(microsecond=0)

    def log(msg):
        if verbose:
            print(msg, flush=True)

    t0 = time.time()
    log(f"[1/5] Loading catalog '{group}' ...")
    cat = _catalog.load_catalog(
        group, data_dir=data_dir, force=force_download,
        max_objects=max_objects, ts=ts,
    )
    log("      " + cat.summary())

    log(f"[2/5] Propagating {len(cat)} objects over {hours} h @ {step_s:.0f}s ...")
    cube = _propagate.propagate(
        cat.sats, start=start, hours=hours, step_s=step_s, ts=ts, progress=verbose,
    )
    log(f"      cube {cube.positions.shape} | "
        f"{int(cube.valid.sum())} propagated cleanly, "
        f"{int((~cube.valid).sum())} dropped")

    log(f"[3/5] Screening at {threshold_km} km (KD-tree, all {cube.n_times} steps) ...")
    events = _screen.screen(cube, threshold_km=threshold_km, progress=verbose)
    log(f"      {len(events)} candidate events (grouped across time)")

    log(f"[4/5] Refining TCA + miss distance for {len(events)} events ...")
    refined = []
    for ev in events:
        r = _refine.refine_event(cat.sats[ev.i], cat.sats[ev.j], cube, ev, hbr_m=hbr_m, ts=ts)
        refined.append(r)

    log("[5/5] Ranking by risk ...")
    ranked = _risk.rank_events(refined)

    # Phase 4 (experimental): if a trained model is present, score the top events.
    try:
        from .ml import features as _mlfeatures
        _model = _mlfeatures.load_model()
        if _model is not None:
            n = _mlfeatures.score_ranked(ranked, _model, top_k=100)
            log(f"      scored {n} events with the learned model (experimental)")
    except Exception:
        pass

    meta = {
        "group": group,
        "hours": hours,
        "step_s": step_s,
        "threshold_km": threshold_km,
        "n_objects": len(cat),
        "n_valid": int(cube.valid.sum()),
        "start_utc": start.strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot_date": cat.snapshot_date,
        "generated_utc": _dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "runtime_s": round(time.time() - t0, 1),
        "orbitguard_version": __import__("orbitguard").__version__,
        "pc_hbr_m": hbr_m,
        "pc_sigma_note": ("Foster 2-D Pc under a modelled RTN covariance, "
                          "altitude- + TLE-age-scaled (σ_R≈200m; σ_T≈500m at epoch, "
                          "growing ~1km/day at 800km and faster low in LEO; σ_N≈200m "
                          "growing mildly with age); "
                          f"hard-body radius {hbr_m:.0f} m. Calibrated to published "
                          "TLE-error magnitudes (Flohrer 2008), not a per-object fit."),
    }
    sats_by_index = {ev.i: cat.sats[ev.i] for ev in events}
    sats_by_index.update({ev.j: cat.sats[ev.j] for ev in events})

    log(f"\nDone in {meta['runtime_s']} s.")
    return PipelineResult(ranked=ranked, meta=meta, sats_by_index=sats_by_index,
                          catalog=cat, cube=cube)
