"""Build per-event CDM *sequences* for the 1-D CNN.

Where the tree baseline sees a single snapshot per event, the CNN sees the whole
trajectory: the ordered series of CDMs leading up to (but stopping 2 days before)
TCA. Each event becomes a fixed-length ``(L, F)`` array — ``L`` timesteps of ``F``
per-CDM features — plus a validity mask for padding.

Same no-leak rule as the baseline: only CDMs with ``time_to_tca >= 2`` are used;
the label is the final CDM's risk.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .dataset import DECISION_HORIZON_DAYS, HIGH_RISK_THRESHOLD, TRAIN_CSV

# Curated, physically-meaningful per-CDM features (present in the Kelvins schema).
SEQ_FEATURES = [
    "time_to_tca", "risk", "max_risk_estimate", "max_risk_scaling",
    "miss_distance", "relative_speed",
    "relative_position_r", "relative_position_t", "relative_position_n",
    "relative_velocity_r", "relative_velocity_t", "relative_velocity_n",
    "mahalanobis_distance",
    "c_sigma_r", "c_sigma_t", "c_sigma_n",
    "t_sigma_r", "t_sigma_t", "t_sigma_n",
]

MAX_LEN = 20   # keep the last L CDMs before the decision horizon


@dataclass
class SeqDataset:
    X: np.ndarray        # (N, L, F) float32, raw (unscaled); padded with 0
    mask: np.ndarray     # (N, L) bool — True where a real CDM sits
    y_risk: np.ndarray   # (N,) final risk
    y_high: np.ndarray   # (N,) bool
    event_id: np.ndarray
    features: list


def build_sequences(df: pd.DataFrame, features=SEQ_FEATURES, max_len: int = MAX_LEN) -> "SeqDataset":
    feats = [c for c in features if c in df.columns]
    df = df.sort_values(["event_id", "time_to_tca"])   # ascending: final CDM first

    Xs, masks, y_risk, y_high, eids = [], [], [], [], []
    for eid, g in df.groupby("event_id", sort=False):
        final_risk = float(g.iloc[0]["risk"])
        early = g[g["time_to_tca"] >= DECISION_HORIZON_DAYS]
        if early.empty:
            continue
        # chronological order (earliest -> latest pre-decision); keep last max_len
        early = early.sort_values("time_to_tca", ascending=False).tail(max_len)
        arr = early[feats].to_numpy(dtype=np.float32)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        L = arr.shape[0]
        padded = np.zeros((max_len, len(feats)), dtype=np.float32)
        m = np.zeros(max_len, dtype=bool)
        padded[max_len - L:] = arr      # right-align: latest CDM at the last slot
        m[max_len - L:] = True
        Xs.append(padded); masks.append(m)
        y_risk.append(final_risk); y_high.append(final_risk >= HIGH_RISK_THRESHOLD); eids.append(eid)

    return SeqDataset(
        X=np.stack(Xs), mask=np.stack(masks),
        y_risk=np.asarray(y_risk, np.float32), y_high=np.asarray(y_high, bool),
        event_id=np.asarray(eids), features=feats,
    )


def load(path: str = TRAIN_CSV) -> "SeqDataset":
    import os
    if not os.path.exists(path):
        from .dataset import load as _l  # reuse the friendly error message
        _l(path)
    return build_sequences(pd.read_csv(path))


def standardize(X_train, X_all, mask_train):
    """Per-feature z-score using only *valid* timesteps of the training split.

    Returns the standardized ``X_all`` (same shape). Padding stays ~0.
    """
    valid = X_train[mask_train]                       # (n_valid_steps, F)
    mu = valid.mean(axis=0)
    sd = valid.std(axis=0) + 1e-6
    return (X_all - mu) / sd
