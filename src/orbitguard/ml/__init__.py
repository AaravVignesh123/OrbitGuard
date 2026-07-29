"""OrbitGuard Phase 3 — ML conjunction-risk model (scaffold).

The v1 screener ranks conjunctions by a geometric *proxy* (closing speed / miss
distance). Phase 3 replaces that proxy with a learned probability that a
conjunction will *escalate*, trained on real Conjunction Data Messages (CDMs).

Data: the ESA Kelvins "Collision Avoidance Challenge" dataset — time series of
CDMs per event, where the label is the final (closest-to-TCA) risk. See
``dataset.py`` for the loader contract and ``model.py`` for the training stub.

This package is intentionally a scaffold: the interfaces and feature list are
defined so the fall build can drop in the data and train without re-architecting.
"""

__all__ = ["dataset", "features", "model"]
