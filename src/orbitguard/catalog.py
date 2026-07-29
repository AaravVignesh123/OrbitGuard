"""Catalog loading — turn a CelesTrak group into a clean list of satellites.

CelesTrak publishes "General Perturbations" element sets (TLEs) grouped by
category. We download the raw text once, cache it to ``data/`` with the date in
the filename (reproducible snapshots), then parse it into skyfield
``EarthSatellite`` objects. Malformed lines are skipped and counted; duplicate
NORAD catalog numbers (an object can appear in several groups) are de-duplicated,
keeping the first occurrence.

Orbital-mechanics note: a TLE ("two-line element set") encodes an object's
mean orbital elements at a reference instant (its *epoch*). skyfield feeds these
to the SGP4 propagator, which analytically advances the orbit forward or back in
time. TLEs go stale within days, so we always pull a fresh snapshot.
"""

from __future__ import annotations

import datetime as _dt
import os
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

from skyfield.api import EarthSatellite, load

CELESTRAK_GP = "https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"


@dataclass
class Catalog:
    """A loaded snapshot of satellites plus provenance metadata."""

    sats: List[EarthSatellite]
    group: str
    source_path: str
    n_loaded: int
    n_skipped: int
    n_duplicate: int
    snapshot_date: str
    names: List[str] = field(default_factory=list)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.sats)

    def summary(self) -> str:
        return (
            f"Catalog '{self.group}' ({self.snapshot_date}): "
            f"{self.n_loaded} objects loaded, "
            f"{self.n_duplicate} duplicates removed, "
            f"{self.n_skipped} malformed skipped."
        )


def _gp_url(group: str) -> str:
    return CELESTRAK_GP.format(group=group)


def download_tles(
    group: str,
    data_dir: str = "data",
    *,
    force: bool = False,
    date: Optional[str] = None,
    timeout: int = 90,
) -> str:
    """Download a CelesTrak group to ``data/tle_<group>_<YYYYMMDD>.txt``.

    Returns the path to the cached file. If today's snapshot already exists we
    reuse it unless ``force=True`` — this keeps runs reproducible and polite to
    CelesTrak's servers.
    """
    os.makedirs(data_dir, exist_ok=True)
    date = date or _dt.datetime.utcnow().strftime("%Y%m%d")
    path = os.path.join(data_dir, f"tle_{group}_{date}.txt")

    if os.path.exists(path) and not force and os.path.getsize(path) > 0:
        return path

    url = _gp_url(group)
    # A browser-like UA avoids intermittent 403s from CelesTrak's edge.
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) OrbitGuard/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")

    if "Invalid query" in text or "No GP data found" in text or len(text) < 10:
        raise ValueError(
            f"CelesTrak returned no usable data for group '{group}'. "
            f"Check the group name (e.g. stations, active, starlink)."
        )

    with open(path, "w") as fh:
        fh.write(text)
    return path


def parse_tle_file(path: str, ts=None) -> "Catalog":
    """Parse a 3-line TLE text file into de-duplicated EarthSatellite objects.

    We parse manually (rather than ``load.tle_file``) so we can (a) skip
    malformed records without aborting and (b) de-duplicate by NORAD id.
    """
    ts = ts or load.timescale()
    with open(path) as fh:
        lines = [ln.rstrip("\n") for ln in fh]

    sats: List[EarthSatellite] = []
    seen: set = set()
    n_skipped = 0
    n_duplicate = 0

    i = 0
    n = len(lines)
    while i < n:
        # A record is: name line, "1 ..." line, "2 ..." line.
        name = lines[i].strip()
        if name.startswith("1 ") or name.startswith("2 "):
            # No name line (2-line format) — treat this as line 1.
            l1, l2 = name, lines[i + 1] if i + 1 < n else ""
            name = ""
            i += 2
        else:
            l1 = lines[i + 1] if i + 1 < n else ""
            l2 = lines[i + 2] if i + 2 < n else ""
            i += 3

        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            n_skipped += 1
            continue

        try:
            sat = EarthSatellite(l1, l2, name or None, ts)
            norad = sat.model.satnum
        except Exception:
            n_skipped += 1
            continue

        if norad in seen:
            n_duplicate += 1
            continue
        seen.add(norad)
        if not sat.name:
            sat.name = f"NORAD {norad}"
        sats.append(sat)

    date = _infer_date_from_path(path)
    return Catalog(
        sats=sats,
        group=_infer_group_from_path(path),
        source_path=path,
        n_loaded=len(sats),
        n_skipped=n_skipped,
        n_duplicate=n_duplicate,
        snapshot_date=date,
        names=[s.name for s in sats],
    )


def _infer_date_from_path(path: str) -> str:
    base = os.path.basename(path)
    parts = base.replace(".txt", "").split("_")
    return parts[-1] if parts and parts[-1].isdigit() else "unknown"


def _infer_group_from_path(path: str) -> str:
    base = os.path.basename(path)
    parts = base.replace(".txt", "").split("_")
    return parts[1] if len(parts) >= 3 else "unknown"


def load_catalog(
    group: str = "active",
    *,
    data_dir: str = "data",
    force: bool = False,
    max_objects: Optional[int] = None,
    ts=None,
) -> "Catalog":
    """Download (or reuse) and parse a CelesTrak group into a ``Catalog``.

    Parameters
    ----------
    group : CelesTrak group name (``stations``, ``active``, ``starlink``, ...).
    max_objects : optionally cap the catalog size (handy for quick runs/tests).
    """
    path = download_tles(group, data_dir=data_dir, force=force)
    cat = parse_tle_file(path, ts=ts)
    if max_objects is not None and len(cat.sats) > max_objects:
        cat.sats = cat.sats[:max_objects]
        cat.names = cat.names[:max_objects]
        cat.n_loaded = len(cat.sats)
    return cat
