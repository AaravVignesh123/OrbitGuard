"""OrbitGuard — autonomous orbital collision-avoidance screener.

Pipeline: load_catalog -> propagate -> screen -> refine -> rank -> report.

The public API is intentionally small; see the individual modules for detail:

    from orbitguard import catalog, propagate, screen, refine, risk, report
"""

__version__ = "1.0.0"

__all__ = [
    "catalog",
    "propagate",
    "screen",
    "refine",
    "risk",
    "report",
]
