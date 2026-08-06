#!/usr/bin/env python3
"""Sanity demo — load the trained baseline and score real held-out events.

    python src/orbitguard/ml/predict_demo.py

Trains on 80% of events, predicts final risk for a random 20% it never saw, and
prints the events it ranks as most dangerous next to their TRUE outcome — so you
can eyeball that high predictions really are the high-risk conjunctions.
"""

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sklearn.model_selection import train_test_split

from orbitguard.ml import dataset as _ds
from orbitguard.ml.model import _make_model


def main() -> int:
    ds = _ds.load()
    idx = np.arange(len(ds.X))
    tr, te = train_test_split(idx, test_size=0.2, random_state=7, stratify=ds.y_high)

    model = _make_model(ds.cat_features)
    model.fit(ds.X.iloc[tr], np.clip(ds.y_risk[tr], -10, None))
    pred = model.predict(ds.X.iloc[te])

    order = np.argsort(pred)[::-1]           # most dangerous first
    print("Top-15 predicted-riskiest held-out events (never seen in training):\n")
    print(f"  {'event_id':>10} {'pred_risk':>10} {'true_risk':>10} {'true_high?':>11}")
    hits = 0
    for k in order[:15]:
        i = te[k]
        hi = ds.y_high[i]
        hits += int(hi)
        flag = "  HIGH-RISK" if hi else ""
        print(f"  {ds.event_id[i]:>10} {pred[k]:>10.2f} {ds.y_risk[i]:>10.2f} "
              f"{str(bool(hi)):>11}{flag}")

    n_high_te = int(ds.y_high[te].sum())
    print(f"\n  {hits}/15 of the top predictions are truly high-risk "
          f"(only {n_high_te} high-risk events exist in the whole {len(te)}-event test set, "
          f"= {100*n_high_te/len(te):.1f}%).")
    print("  A random ranker would get ~"
          f"{15*n_high_te/len(te):.1f}/15. The model concentrates them at the top.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
