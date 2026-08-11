"""Phase-4 bridge — score OrbitGuard's own live conjunctions with the Kelvins model.

**This is a research demonstration, and deliberately low-fidelity.** The Kelvins
tree model expects ~110 CDM features; our TLE screener can honestly produce only 9
of them (miss distance, relative speed, and the RTN relative position/velocity).
The other ~100 — including the model's single most important feature, the prior
CDM ``risk`` estimate, plus all orbit-determination-quality and covariance columns
— have no TLE-derived source and are imputed as NaN (the HistGradientBoosting model
handles NaN natively). So the resulting "ML risk" is an *illustrative* number, not
a trustworthy prediction. It is surfaced clearly labeled "experimental."

Feature construction lives in ``dataset.build_event_table`` (that's the training
contract); this module only maps a live ``RefinedEvent`` into that space.
"""

from __future__ import annotations

import datetime as _dt

import numpy as np

# The 9 model features the screener can genuinely fill, and how (Kelvins units:
# metres, m/s, days). Everything else the model expects is left NaN.
def bridge_from_screener(ev, time_to_tca_days: float | None = None) -> dict:
    """Map a v1 ``RefinedEvent`` to the subset of Kelvins ``snap_*`` features we can produce."""
    rp = getattr(ev, "rel_pos_rtn_km", (0.0, 0.0, 0.0))
    rv = getattr(ev, "rel_vel_rtn_kms", (0.0, 0.0, 0.0))
    if time_to_tca_days is None:
        time_to_tca_days = max((ev.tca_utc - _dt.datetime.utcnow()).total_seconds() / 86400.0, 0.0)
    return {
        "snap_time_to_tca": float(time_to_tca_days),
        "snap_miss_distance": float(ev.miss_km) * 1000.0,        # m
        "snap_relative_speed": float(ev.rel_speed_kms) * 1000.0,  # m/s
        "snap_relative_position_r": rp[0] * 1000.0,
        "snap_relative_position_t": rp[1] * 1000.0,
        "snap_relative_position_n": rp[2] * 1000.0,
        "snap_relative_velocity_r": rv[0] * 1000.0,
        "snap_relative_velocity_t": rv[1] * 1000.0,
        "snap_relative_velocity_n": rv[2] * 1000.0,
        # a couple of engineered aggregates the screener can honestly set:
        "miss_last": float(ev.miss_km) * 1000.0,
        "miss_min": float(ev.miss_km) * 1000.0,
        "miss_trend": 0.0,
        "n_cdms_early": 1,
        "tca_span_days": 0.0,
        "c_object_type": "PAYLOAD",   # assumed; both usually active payloads
    }


def load_model(path: str = "out/ml/baseline_model.joblib"):
    import os
    if not os.path.exists(path):
        return None
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        return None


def score_ranked(ranked, model, top_k: int | None = None) -> int:
    """Set ``event.ml_risk`` (predicted log10 Pc) on ranked events, best-effort.

    Returns the number scored. Requires the model's ``feature_names_in_``. Fills the
    bridge features, leaves the rest NaN. Experimental — see module docstring.
    """
    if model is None or not hasattr(model, "feature_names_in_"):
        return 0
    import pandas as pd
    cols = list(model.feature_names_in_)
    items = ranked if top_k is None else ranked[:top_k]
    if not items:
        return 0
    cat_cols = [c for c in (getattr(model, "categorical_features", None) or []) if c in cols]
    rows = []
    for re in items:
        feat = bridge_from_screener(re.event)
        rows.append({c: feat.get(c, np.nan) for c in cols})
    X = pd.DataFrame(rows, columns=cols)
    for c in cols:                      # numeric columns → float; categoricals → category dtype
        if c in cat_cols:
            X[c] = X[c].astype("category")
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce")
    try:
        preds = model.predict(X)
    except Exception:
        return 0
    for re, p in zip(items, preds):
        re.event.ml_risk = float(p)
    return len(items)
