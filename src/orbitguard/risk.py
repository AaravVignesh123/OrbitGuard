"""Risk scoring — rank conjunctions by "how scary", not just "how close".

A tiny miss distance is only alarming if the two objects are actually converging
fast; two satellites flying in formation 2 km apart at nearly zero relative
speed are far less dangerous than a 2 km pass at 14 km/s. So the v1 risk proxy
combines both:

    risk = closing_speed / (miss_distance + softening)

which is large when the miss is small AND the closing speed is high. We then map
it onto a 0-100 scale for readability. This is deliberately a *proxy*, not a true
probability of collision (Pc) — the physically rigorous Pc from covariance data
is the job of the fall ML phase (Phase 3), where we train on the ESA Kelvins CDM
dataset.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from .refine import RefinedEvent

# Softening (km): keeps the score finite at zero miss and sets the distance
# scale at which closeness starts to dominate. ~0.2 km ~ combined object size +
# margin.
_SOFTENING_KM = 0.2


@dataclass
class RankedEvent:
    event: RefinedEvent
    risk_raw: float
    risk_score: float  # 0-100, higher = scarier
    rank: int = field(default=0)


def _raw_risk(miss_km: float, rel_speed_kms: float) -> float:
    return rel_speed_kms / (miss_km + _SOFTENING_KM)


def rank_events(events: List[RefinedEvent]) -> List[RankedEvent]:
    """Score and sort events, scariest first, with a 0-100 readable score."""
    if not events:
        return []

    raws = np.array([_raw_risk(e.miss_km, e.rel_speed_kms) for e in events])
    # Log-compress the long tail, then min-max to 0-100.
    logs = np.log1p(raws)
    lo, hi = logs.min(), logs.max()
    scaled = 100.0 * (logs - lo) / (hi - lo) if hi > lo else np.full_like(logs, 50.0)

    ranked = [
        RankedEvent(event=e, risk_raw=float(r), risk_score=float(s))
        for e, r, s in zip(events, raws, scaled)
    ]
    ranked.sort(key=lambda re: re.risk_raw, reverse=True)
    for pos, re in enumerate(ranked, start=1):
        re.rank = pos
    return ranked
