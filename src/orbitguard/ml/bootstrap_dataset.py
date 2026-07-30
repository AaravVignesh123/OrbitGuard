"""Bootstrap ML dataset — a *starter* training table built from OrbitGuard's own
screening output, so you can stand up the Phase-3 training pipeline TODAY while
waiting on the real ESA Kelvins CDM data.

Honesty about what this is
--------------------------
The real Phase-3 task is to predict, from early Conjunction Data Messages,
whether an event will *escalate* — a label that comes from ESA's operational CDM
history (the Kelvins dataset). This bootstrap file does NOT have that ground
truth. It gives you:

  * real, correctly-shaped features from actual screened conjunctions
    (miss distance, closing speed, altitude, geometry), and
  * a transparent, rule-based ``high_risk`` label derived from the v1 risk proxy,

so your data loading, feature engineering, train/val split, model fitting, and
evaluation harness are all working end-to-end. When the Kelvins CSV lands, swap
the loader in ``dataset.py`` and keep the same harness.

Because the label is a deterministic function of the features, a model will hit
near-perfect scores — that is expected and meaningless for generalization. Treat
this as a *plumbing* dataset, not a science dataset. See ``ml/README.md``.
"""

from __future__ import annotations

import csv
import json
import os
from typing import List

FEATURES = ["miss_km", "coarse_miss_km", "rel_speed_kms", "alt_km",
            "closing_geom", "risk_score"]
LABEL = "high_risk"

# Rule for the bootstrap label: a "high risk" pass is close AND closing fast.
# Thresholds are chosen to give a non-degenerate class balance on a typical run
# (real collision risk is far rarer than this — see README).
_MISS_CUT_KM = 2.5
_SPEED_CUT_KMS = 5.0


def from_report_json(report_path: str, out_csv: str) -> str:
    """Turn a ``report_*.json`` payload into a labelled starter CSV."""
    with open(report_path) as fh:
        payload = json.load(fh)
    return _write(payload["events"], out_csv)


def _write(events: List[dict], out_csv: str) -> str:
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["event_id", "object_a", "object_b"] + FEATURES + [LABEL])
        for i, e in enumerate(events):
            miss = float(e["miss_km"])
            speed = float(e["rel_speed_kms"])
            # A cheap geometry proxy: closing speed per km of miss (unbounded → clip).
            closing_geom = round(min(speed / (miss + 0.2), 100.0), 4)
            label = int(miss < _MISS_CUT_KM and speed > _SPEED_CUT_KMS)
            w.writerow([
                i, e["object_a"], e["object_b"],
                round(miss, 4), round(float(e["coarse_miss_km"]), 4),
                round(speed, 4), round(float(e["alt_km"]), 2),
                closing_geom, round(float(e["risk_score"]), 2), label,
            ])
    return out_csv


if __name__ == "__main__":  # pragma: no cover
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "out/report_latest.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "data/ml_bootstrap_dataset.csv"
    print("wrote", from_report_json(src, dst))
