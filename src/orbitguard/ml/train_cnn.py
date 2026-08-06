#!/usr/bin/env python3
"""Train the 1-D CNN and compare it head-to-head with the tree baseline.

    python src/orbitguard/ml/train_cnn.py

Same events, same 5-fold split, same metrics. Prints CNN vs baseline and saves
out/ml/cnn_metrics.json.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from orbitguard.ml import cnn as _cnn
from orbitguard.ml import sequences as _seq


def _row(name, m):
    return (f"  {name:10} PR-AUC {m['pr_auc']:.3f} | ROC {m['roc_auc']:.3f} | "
            f"F2 {m['f2_best']:.3f} (thr {m['f2_best_threshold']:.2f}) | "
            f"RMSE_HR {m['rmse_high_risk']:.3f}")


def main() -> int:
    t0 = time.time()
    print("[1/2] Building CDM sequences ...")
    seq = _seq.load()
    print(f"      {len(seq.X)} events | shape {seq.X.shape} (events, L, F) | "
          f"{int(seq.y_high.sum())} high-risk")

    print("[2/2] Training 1-D CNN (5-fold, MPS/CPU) ...")
    res = _cnn.train_cnn(seq)

    base = None
    bpath = os.path.join(os.path.dirname(__file__), "baseline_metrics.json")
    if os.path.exists(bpath):
        base = json.load(open(bpath))["metrics"]

    print("\n" + "=" * 68)
    print("HEAD-TO-HEAD — cross-validated (identical folds + metrics)")
    print("=" * 68)
    if base:
        print(_row("baseline", base))
    print(_row("CNN-1D", res.metrics))
    if base:
        d_f2 = res.metrics["f2_best"] - base["f2_best"]
        d_pr = res.metrics["pr_auc"] - base["pr_auc"]
        verdict = "CNN wins" if (d_f2 > 0 and d_pr > 0) else (
            "baseline holds" if (d_f2 < 0 and d_pr < 0) else "mixed")
        print(f"\n  Δ vs baseline: F2 {d_f2:+.3f} | PR-AUC {d_pr:+.3f}  ->  {verdict}")

    os.makedirs("out/ml", exist_ok=True)
    json.dump({"cnn": res.metrics, "baseline": base},
              open("out/ml/cnn_metrics.json", "w"), indent=2)
    print(f"\n  Saved out/ml/cnn_metrics.json\nDone in {time.time() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
