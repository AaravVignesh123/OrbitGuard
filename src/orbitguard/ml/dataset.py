"""ESA Kelvins CDM dataset — load and shape into a per-event learning table.

The challenge: each *event* is a time-ordered sequence of Conjunction Data
Messages (CDMs). The label is the **final risk** — the ``risk`` field
(log10 collision probability) of the CDM closest to TCA. The predictor may only
use information available **at least 2 days before TCA**; using any CDM inside
the 2-day window would leak the answer. So for each event we:

  * take the target from the last CDM (smallest ``time_to_tca``),
  * build features only from CDMs with ``time_to_tca >= 2`` (the decision point),
  * drop events that have no CDM before the 2-day boundary.

Features are a snapshot of the last pre-decision CDM plus a few trend/aggregate
features across the event's early history (is the risk climbing? is the miss
shrinking?), which is what lets a model anticipate escalation.

Get the data (public, no login):
    curl -L -o data/kelvins/train_data.zip \\
      https://kelvins.esa.int/media/public/competitions/collision-avoidance-challenge/train_data.zip
    (cd data/kelvins && unzip train_data.zip)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

DATA_DIR = os.path.join("data", "kelvins")
TRAIN_CSV = os.path.join(DATA_DIR, "train_data.csv")

DECISION_HORIZON_DAYS = 2.0    # may only use CDMs at time_to_tca >= this
HIGH_RISK_THRESHOLD = -6.0     # final risk >= this == "high risk" (challenge def.)

# Identifier / leakage columns never used as features.
_DROP = {"event_id", "mission_id"}
# The single categorical column worth keeping.
_CATEGORICAL = ["c_object_type", "t_object_type"]


@dataclass
class Dataset:
    X: pd.DataFrame          # one row per event (features)
    y_risk: np.ndarray       # final risk (regression target)
    y_high: np.ndarray       # final risk >= -6 (bool)
    event_id: np.ndarray
    cat_features: list        # names of categorical columns in X


def _numeric_feature_cols(df: pd.DataFrame) -> list:
    cols = []
    for c in df.columns:
        if c in _DROP or c in _CATEGORICAL:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def build_event_table(df: pd.DataFrame) -> "Dataset":
    """Collapse the raw CDM table into one feature row per event."""
    df = df.sort_values(["event_id", "time_to_tca"])  # ascending: closest-to-TCA first
    num_cols = _numeric_feature_cols(df)

    rows, y_risk, y_high, eids = [], [], [], []
    for eid, g in df.groupby("event_id", sort=False):
        final_risk = float(g.iloc[0]["risk"])         # smallest time_to_tca == final CDM
        early = g[g["time_to_tca"] >= DECISION_HORIZON_DAYS]
        if early.empty:
            continue                                   # no info before the 2-day boundary
        early = early.sort_values("time_to_tca")       # ascending
        snap = early.iloc[0]                            # last CDM before the boundary

        feat = {f"snap_{c}": float(snap[c]) for c in num_cols}
        for c in _CATEGORICAL:
            if c in early.columns:
                feat[c] = snap[c]

        # trend / aggregate features across the early history
        feat["n_cdms_early"] = len(early)
        feat["tca_span_days"] = float(early["time_to_tca"].max() - early["time_to_tca"].min())
        feat["risk_first"] = float(early.iloc[-1]["risk"])     # earliest CDM
        feat["risk_last"] = float(early.iloc[0]["risk"])       # latest pre-decision CDM
        feat["risk_max"] = float(early["risk"].max())
        feat["risk_trend"] = feat["risk_last"] - feat["risk_first"]
        feat["miss_last"] = float(early.iloc[0]["miss_distance"])
        feat["miss_min"] = float(early["miss_distance"].min())
        feat["miss_trend"] = float(early.iloc[0]["miss_distance"] - early.iloc[-1]["miss_distance"])

        rows.append(feat)
        y_risk.append(final_risk)
        y_high.append(final_risk >= HIGH_RISK_THRESHOLD)
        eids.append(eid)

    X = pd.DataFrame(rows)
    cat = [c for c in _CATEGORICAL if c in X.columns]
    for c in cat:
        X[c] = X[c].astype("category")
    return Dataset(
        X=X, y_risk=np.asarray(y_risk, float),
        y_high=np.asarray(y_high, bool), event_id=np.asarray(eids), cat_features=cat,
    )


def load(path: str = TRAIN_CSV) -> "Dataset":
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Download the public Kelvins archive:\n"
            "  curl -L -o data/kelvins/train_data.zip "
            "https://kelvins.esa.int/media/public/competitions/collision-avoidance-challenge/train_data.zip\n"
            "  (cd data/kelvins && unzip train_data.zip)"
        )
    return build_event_table(pd.read_csv(path))
