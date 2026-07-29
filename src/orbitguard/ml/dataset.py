"""ESA Kelvins CDM dataset loader (Phase 3 scaffold).

The ESA Kelvins Collision Avoidance Challenge released ~160k Conjunction Data
Messages grouped into events. Each event is a *sequence* of CDMs issued as TCA
approaches; the modeling task is to predict the final risk (the ``risk`` field
of the CDM closest to TCA) from the earlier CDMs — i.e. decide, days ahead,
whether an event will become high-risk.

Get the data
------------
1. Register at https://kelvins.esa.int/collision-avoidance-challenge/
2. Download ``train_data.csv`` (and ``test_data.csv``).
3. Place them under ``data/kelvins/``.

This module defines the loading contract; wire it up in the fall.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DATA_DIR = os.path.join("data", "kelvins")
TRAIN_CSV = os.path.join(DATA_DIR, "train_data.csv")

# The competition's high-risk decision threshold (log10 of collision prob).
HIGH_RISK_THRESHOLD = -6.0

# Columns most predictive per the challenge write-ups (starting feature set).
CANDIDATE_FEATURES = [
    "time_to_tca",          # days until closest approach
    "miss_distance",        # m
    "relative_speed",       # m/s
    "relative_position_r",  # radial rel. position (RTN frame)
    "relative_position_t",
    "relative_position_n",
    "c_sigma_r", "c_sigma_t", "c_sigma_n",  # chaser covariance (position sigmas)
    "t_sigma_r", "t_sigma_t", "t_sigma_n",  # target covariance
    "max_risk_estimate",
    "max_risk_scaling",
]

LABEL = "risk"  # log10(collision probability) of the CDM closest to TCA


@dataclass
class KelvinsData:
    X: object  # pandas.DataFrame of features (one row per event)
    y: object  # pandas.Series of the final risk label
    groups: object  # event_id per row (for grouped train/val splitting)


def load_train(path: str = TRAIN_CSV) -> "KelvinsData":
    """Load and shape the Kelvins training set into per-event features.

    TODO (Phase 3):
      * read the CSV with pandas
      * group by ``event_id``, sort each event by ``time_to_tca`` (descending)
      * build per-event features (last CDM's fields + simple trend features)
      * label = the final CDM's ``risk``; ``is_high_risk = risk > -6``
    """
    raise NotImplementedError(
        "Phase 3 scaffold: download the Kelvins CSV to data/kelvins/ and "
        "implement per-event feature aggregation here."
    )
