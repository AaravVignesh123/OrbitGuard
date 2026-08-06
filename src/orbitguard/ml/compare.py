#!/usr/bin/env python3
"""Definitive Phase-3 comparison: baseline vs CNN vs ensemble.

    python src/orbitguard/ml/compare.py

Runs both models on the *same* events and folds, then evaluates a rank-averaged
ensemble. Saves out/ml/comparison.json (the numbers shown in the model card).
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from orbitguard.ml import cnn as _cnn
from orbitguard.ml import dataset as _ds
from orbitguard.ml import model as _model
from orbitguard.ml import sequences as _seq
from orbitguard.ml.model import _metrics


def _rank(x):
    from scipy.stats import rankdata
    return rankdata(x) / len(x)


def _line(name, m):
    rmse = m.get("rmse_high_risk")
    rmse_s = f"{rmse:.3f}" if rmse is not None else "—"
    return (f"  {name:10} PR-AUC {m['pr_auc']:.3f} | ROC {m['roc_auc']:.3f} | "
            f"F2 {m['f2_best']:.3f} | RMSE_HR {rmse_s}")


def main() -> int:
    t0 = time.time()
    print("Loading data ...")
    ds = _ds.load()
    seq = _seq.load()
    assert list(ds.event_id) == list(seq.event_id), "event alignment mismatch"
    y_high, y_risk = ds.y_high, ds.y_risk

    print("Training baseline (trees) ...")
    base = _model.train_baseline(ds)
    print("Training CNN (1-D) ...")
    cnn = _cnn.train_cnn(seq)

    # rank-average ensemble (robust to the two models' different scales).
    # NOTE: the ensemble score is a rank in [0,1], NOT a log-risk value, so it is
    # used only for ranking metrics; RMSE (which needs the risk scale) is N/A here.
    ens_score = 0.5 * _rank(base.oof_pred) + 0.5 * _rank(cnn.oof_pred)
    ens = _metrics(y_high, y_risk, ens_score)
    ens["rmse_high_risk"] = None
    ens["note"] = "rank-averaged score (not on the risk scale); use for ranking only"

    results = {"baseline": base.metrics, "cnn": cnn.metrics, "ensemble": ens}
    print("\n" + "=" * 66)
    print("PHASE 3 — cross-validated (identical folds + metrics)")
    print("=" * 66)
    print(_line("baseline", base.metrics))
    print(_line("CNN-1D", cnn.metrics))
    print(_line("ensemble", ens))

    os.makedirs("out/ml", exist_ok=True)
    json.dump(results, open("out/ml/comparison.json", "w"), indent=2)
    # also drop a copy next to the package for the model card / repo record
    json.dump(results, open(os.path.join(os.path.dirname(__file__),
              "comparison.json"), "w"), indent=2)
    print(f"\nSaved out/ml/comparison.json  ·  done in {time.time() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
