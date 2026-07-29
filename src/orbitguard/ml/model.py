"""Conjunction-risk model (Phase 3 scaffold).

Baseline plan: a gradient-boosted tree (sklearn ``HistGradientBoostingRegressor``
or ``GradientBoostingClassifier``) predicting the final CDM risk / high-risk
label from the aggregated per-event features in ``features.py``. Evaluate with a
*grouped* split (never leak CDMs from the same event across train/val) and the
challenge's own F2-style metric that rewards catching true high-risk events.

This mirrors the v1 screener's contract: given a candidate conjunction, return a
scalar risk — but learned from covariance-bearing CDMs rather than a geometric
proxy, so it can be dropped into ``risk.py`` as an alternative scorer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrainConfig:
    model: str = "hist_gbdt"
    n_splits: int = 5           # grouped CV folds
    random_state: int = 42
    high_risk_threshold: float = -6.0


def train(data, config: "TrainConfig" = None):
    """Fit the risk model. TODO (Phase 3): implement.

    Suggested skeleton::

        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.model_selection import GroupKFold
        model = HistGradientBoostingRegressor(random_state=config.random_state)
        # GroupKFold on data.groups, fit on data.X / data.y, report metric
        return model
    """
    raise NotImplementedError("Phase 3 scaffold — implement in the fall build.")


def predict_risk(model, features) -> float:
    """Return a learned risk for one conjunction (drop-in for risk.py)."""
    raise NotImplementedError("Phase 3 scaffold — implement in the fall build.")
