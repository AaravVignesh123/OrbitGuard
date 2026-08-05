"""Feature notes for the Phase-3 risk model.

The per-event feature construction lives in :func:`orbitguard.ml.dataset.build_event_table`
— it is the single source of truth. Each event becomes one row: a snapshot of the
last CDM before the 2-day decision horizon (``snap_*``) plus trend/aggregate
features over the earlier history (``risk_trend``, ``miss_min``, ``n_cdms_early``, …).

This module holds the *bridge* to live screener output, so the trained Kelvins
model can eventually score OrbitGuard's own conjunctions. It is a Phase-4 concern
(our screener produces geometry but not covariance-bearing CDMs), so it is left as
a documented stub rather than pretending to a mapping we can't yet make faithfully.
"""

from __future__ import annotations

from typing import List


def bridge_from_screener(refined_event) -> List[float]:
    """Map a v1 ``RefinedEvent`` into the Kelvins feature space (Phase 4).

    Only geometry (miss distance, relative speed) overlaps directly; the CDM
    covariance / OD-quality features have no screener equivalent yet and would
    need to be imputed. Implemented once we ingest real CDMs for our catalogue.
    """
    raise NotImplementedError(
        "Phase 4: requires covariance/CDM features the v1 screener does not "
        "produce. See src/orbitguard/ml/README.md."
    )
