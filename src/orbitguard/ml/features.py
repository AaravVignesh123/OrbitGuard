"""Feature engineering for the Phase 3 risk model (scaffold).

Turns a per-event sequence of CDMs into a single feature row. The intuition: the
*last* CDM before TCA carries the best geometry, but the *trend* across earlier
CDMs (is the miss distance shrinking? is the covariance tightening?) is what lets
you predict escalation early.
"""

from __future__ import annotations

from typing import List


def aggregate_event(cdm_rows) -> dict:
    """Collapse one event's CDMs (sorted by time_to_tca desc) into features.

    TODO (Phase 3):
      * last-CDM snapshot of CANDIDATE_FEATURES
      * deltas between first and last CDM (miss_distance trend, risk trend)
      * count of CDMs, span of time_to_tca
      * combined position-covariance magnitude
    """
    raise NotImplementedError("Phase 3 scaffold.")


def bridge_from_screener(refined_event) -> List[float]:
    """Map a v1 ``RefinedEvent`` into the model's feature space where possible.

    Lets the trained model score live screener output even without full CDM
    covariance (missing fields imputed). Implemented in the fall.
    """
    raise NotImplementedError("Phase 3 scaffold.")
