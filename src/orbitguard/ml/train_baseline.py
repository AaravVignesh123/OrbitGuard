#!/usr/bin/env python3
"""Train + evaluate the Phase-3 baseline risk model on the Kelvins CDM dataset.

    python src/orbitguard/ml/train_baseline.py

Prints cross-validated metrics, saves the fitted model and a metrics JSON under
``out/ml/``. This is the number the CNN has to beat.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from orbitguard.ml import dataset as _ds
from orbitguard.ml import model as _model


def main() -> int:
    t0 = time.time()
    print("[1/3] Loading + shaping Kelvins CDMs into per-event table ...")
    ds = _ds.load()
    print(f"      {len(ds.X)} events | {int(ds.y_high.sum())} high-risk "
          f"({100 * ds.y_high.mean():.2f}%) | {ds.X.shape[1]} features "
          f"| categorical: {ds.cat_features}")

    print("[2/3] 5-fold stratified cross-validation (HistGradientBoosting) ...")
    res = _model.train_baseline(ds)

    m = res.metrics
    print("\n" + "=" * 60)
    print("BASELINE — cross-validated (out-of-fold)")
    print("=" * 60)
    print(f"  PR-AUC (avg precision) : {m['pr_auc']:.4f}")
    print(f"  ROC-AUC                : {m['roc_auc']:.4f}")
    print(f"  F2 @ risk>=-6          : {m['f2_at_-6']:.4f}  "
          f"(precision {m['precision_at_-6']:.3f}, recall {m['recall_at_-6']:.3f})")
    print(f"  F2 @ best threshold    : {m['f2_best']:.4f}  (thr={m['f2_best_threshold']:.2f})")
    print(f"  RMSE on high-risk risk : {m['rmse_high_risk']:.4f}")
    print(f"  events / high-risk     : {m['n_events']} / {m['n_high_risk']}")
    print("\n  Top features (permutation importance):")
    for name, imp in res.feature_importance[:12]:
        print(f"    {imp:8.4f}  {name}")

    os.makedirs("out/ml", exist_ok=True)
    with open("out/ml/baseline_metrics.json", "w") as fh:
        json.dump({"metrics": m,
                   "feature_importance": res.feature_importance}, fh, indent=2)
    try:
        import joblib
        joblib.dump(res.model, "out/ml/baseline_model.joblib")
        print("\n  Saved out/ml/baseline_model.joblib")
    except Exception as e:
        print(f"\n  (model not pickled: {e})")
    print(f"  Saved out/ml/baseline_metrics.json")
    print(f"\nDone in {time.time() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
