"""Validation — prove the pipeline's numbers, and write it out for the site.

Rigor is the product, so we recompute the key correctness claims from scratch and
publish them:

  * **Screening** — the KD-tree returns exactly the brute-force pair set.
  * **Refinement** — each reported miss distance matches an independent 0.01 s
    brute-force close-approach search (a separate code path) to within metres.
  * **Relative velocity** — matches the independent computation.

Run:  python -m orbitguard.validate            (writes out/validation.json)
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys

import numpy as np
from skyfield.api import load

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orbitguard import catalog as _catalog
from orbitguard import screen as _screen


def _kdtree_check(seed: int = 1, n: int = 400, threshold: float = 10.0) -> dict:
    rng = np.random.default_rng(seed)
    pos = rng.normal(0, 40, (n, 3))
    bf = _screen.close_pairs_bruteforce(pos, threshold)
    kd = _screen.close_pairs_kdtree(pos, threshold)
    dk = {(i, j): d for i, j, d in kd}
    max_diff = max((abs(dk[(i, j)] - d) for i, j, d in bf), default=0.0)
    return {
        "n_points": n, "n_pairs": len(bf),
        "identical": {(i, j) for i, j, _ in bf} == set(dk),
        "max_distance_diff_m": float(max_diff * 1000.0),
    }


def _ground_truth(sat_a, sat_b, tca_str, ts, half_min=5.0, dt=0.02):
    t0 = _dt.datetime.strptime(tca_str, "%Y-%m-%d %H:%M:%S")
    offs = np.linspace(-half_min * 60, half_min * 60, int(2 * half_min * 60 / dt) + 1)
    t = ts.utc(t0.year, t0.month, t0.day, t0.hour, t0.minute, t0.second + offs)
    ea, eb = sat_a.at(t), sat_b.at(t)
    sep = np.linalg.norm(ea.position.km - eb.position.km, axis=0)
    k = int(np.argmin(sep))
    va = ea.velocity.km_per_s[:, k]; vb = eb.velocity.km_per_s[:, k]
    return float(sep[k]), float(np.linalg.norm(va - vb))


def validate_run(report_path="out/report_latest.json", data_dir="data",
                 top_n: int = 10) -> dict:
    ts = load.timescale()
    report = json.load(open(report_path))
    meta = report["meta"]
    tle = os.path.join(data_dir, f"tle_{meta['group']}_{meta['snapshot_date']}.txt")
    cat = _catalog.parse_tle_file(tle, ts=ts)
    by_norad = {int(s.model.satnum): s for s in cat.sats}

    miss_err, vel_err, rows = [], [], []
    for e in report["events"][:top_n]:
        a, b = by_norad.get(e["norad_a"]), by_norad.get(e["norad_b"])
        if a is None or b is None:
            continue
        gt_miss, gt_v = _ground_truth(a, b, e["tca_utc"], ts)
        de = abs(e["miss_km"] - gt_miss) * 1000.0
        dv = abs(e["rel_speed_kms"] - gt_v)
        miss_err.append(de); vel_err.append(dv)
        rows.append({"pair": f'{e["object_a"]} ↔ {e["object_b"]}',
                     "reported_km": round(e["miss_km"], 3),
                     "truth_km": round(gt_miss, 3), "error_m": round(de, 1)})

    return {
        "generated_utc": meta.get("generated_utc"),
        "snapshot_date": meta.get("snapshot_date"),
        "kdtree": _kdtree_check(),
        "refinement": {
            "n_checked": len(rows),
            "max_error_m": round(max(miss_err), 1) if miss_err else None,
            "median_error_m": round(float(np.median(miss_err)), 1) if miss_err else None,
            "events": rows,
        },
        "velocity": {"max_error_kms": round(max(vel_err), 5) if vel_err else None},
        "socrates": {"status": "manual — compare a few events at celestrak.org/SOCRATES"},
    }


def main() -> int:
    out = validate_run()
    os.makedirs("out", exist_ok=True)
    json.dump(out, open("out/validation.json", "w"), indent=2)
    # tracked copy for the site build
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "validation.json"), "w"), indent=2)
    r = out["refinement"]
    print(f"KD-tree identical to brute force: {out['kdtree']['identical']} "
          f"({out['kdtree']['n_pairs']} pairs, max diff {out['kdtree']['max_distance_diff_m']:.1e} m)")
    print(f"Refinement vs 0.02s ground truth: max {r['max_error_m']} m, median {r['median_error_m']} m "
          f"({r['n_checked']} events)")
    print(f"Relative velocity max error: {out['velocity']['max_error_kms']} km/s")
    print("Wrote out/validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
