"""Per-object views — pivot the global pair ranking onto a single satellite.

The screener ranks *pairs* globally. But an operator asks a different question:
"of everything up there, what threatens **my** object, and how badly?" These
helpers pivot the same ranked events onto one object (``threats_to``) or build a
leaderboard of the most-threatened objects across the catalogue
(``most_threatened``) — no re-screening, just a re-view of the existing risk
ranking.
"""

from __future__ import annotations

from typing import List, Optional

from .risk import RankedEvent


def _matches(ev, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return False
    if q.isdigit():
        qi = int(q)
        return ev.norad_i == qi or ev.norad_j == qi
    return q in (ev.name_i or "").lower() or q in (ev.name_j or "").lower()


def threats_to(ranked: List[RankedEvent], query: str) -> List[RankedEvent]:
    """Every conjunction involving the object(s) matching ``query`` (name or NORAD).

    Input is already risk-sorted, so the output is too — the focal object's
    scariest neighbours come first.
    """
    return [re for re in ranked if _matches(re.event, query)]


def most_threatened(ranked: List[RankedEvent], top: int = 25) -> List[dict]:
    """Leaderboard: each object's single worst conjunction, ranked across all objects.

    For every object we keep only its highest-risk event (its "closest brush"),
    then sort those per-object worsts descending. Answers "which satellites are
    most at risk right now?".
    """
    best: dict = {}
    for re in ranked:
        e = re.event
        for oid, oname, other, onorad in (
            (e.norad_i, e.name_i, e.name_j, e.norad_j),
            (e.norad_j, e.name_j, e.name_i, e.norad_i),
        ):
            cur = best.get(oid)
            if cur is None or re.risk_raw > cur["risk_raw"]:
                best[oid] = {
                    "object": oname,
                    "norad": oid,
                    "worst_threat": other,
                    "worst_threat_norad": onorad,
                    "miss_km": e.miss_km,
                    "rel_speed_kms": e.rel_speed_kms,
                    "tca_utc": e.tca_utc.strftime("%Y-%m-%d %H:%M:%S"),
                    "risk_score": re.risk_score,
                    "risk_raw": re.risk_raw,
                }
    board = sorted(best.values(), key=lambda d: d["risk_raw"], reverse=True)
    for d in board:
        d.pop("risk_raw", None)
    return board[:top]


def summarize_focus(ranked: List[RankedEvent], query: str) -> Optional[dict]:
    """Small summary of a focal object's threat picture (count, closest, fastest)."""
    hits = threats_to(ranked, query)
    if not hits:
        return None
    misses = [re.event.miss_km for re in hits]
    speeds = [re.event.rel_speed_kms for re in hits]
    top = hits[0].event
    return {
        "query": query,
        "n_threats": len(hits),
        "closest_km": min(misses),
        "fastest_kms": max(speeds),
        "worst_partner": (top.name_j if query.strip().lower() in (top.name_i or "").lower()
                          or (query.strip().isdigit() and int(query) == top.norad_i)
                          else top.name_i),
    }
