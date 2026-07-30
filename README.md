# 🛰️ OrbitGuard

**Autonomous orbital collision-avoidance — a conjunction screener for low-Earth orbit.**

OrbitGuard pulls a live satellite catalog, propagates every object onto one
shared clock, screens the whole population for close approaches
(*conjunctions*), sharpens each flag into a precise time-of-closest-approach and
miss distance, and ranks the results by a risk proxy — then writes a CSV, a JSON
report, and a self-contained interactive dashboard.

> **v1 definition:** *Given a fresh catalog and a time window, output a ranked
> list of predicted close approaches (pair, time of closest approach, miss
> distance).* ✅

<p align="center"><em>One command, catalog → ranked conjunction report + dashboard.</em></p>

---

## Why this exists

There are tens of thousands of tracked objects in low-Earth orbit and the count
is climbing fast. Operators need to know, *ahead of time*, which pairs of objects
will pass dangerously close so they can plan avoidance maneuvers. That screening
problem — do it across the whole catalog, fast enough to be useful, and turn a
coarse flag into a trustworthy number — is exactly what OrbitGuard v1 does.

## What v1 does

```
CelesTrak TLEs ─► propagate ─► KD-tree screen ─► refine TCA ─► risk rank ─► report
   (catalog)      (N×T×3)      (close pairs)     (parabola)    (proxy)     CSV/JSON/HTML
```

1. **Catalog** — download a CelesTrak group (`active`, `starlink`, `stations`, …),
   cache the dated raw TLE snapshot, parse to skyfield satellites, skip malformed
   records, de-duplicate by NORAD id.
2. **Propagate** — SGP4-propagate every object to every timestep into one
   `(N, T, 3)` position cube, all in a single inertial frame (the invariant that
   makes distances meaningful).
3. **Screen** — at each timestep build a `scipy.spatial.cKDTree` and
   `query_pairs(r)` for pairs within the threshold. This dodges the O(n²) wall
   (16k objects ⇒ ~130M pairs *per step* brute-force). Consecutive hits for the
   same pair are grouped into a single candidate event.
4. **Refine** — re-propagate just the two objects at 1 s cadence around each
   flag and fit a parabola to the separation curve for a sub-second TCA and a
   refined miss distance (the coarse 60 s grid always *over*-estimates the miss).
5. **Rank** — compute relative velocity at TCA and score
   `risk ∝ closing_speed / (miss_distance + ε)`, log-scaled to 0–100.
6. **Report** — ranked CSV, full JSON, and an interactive 3D dashboard.

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Screen the full active catalog over the next 24 h at a 10 km threshold:
python src/screen.py --group active --hours 24 --threshold 10
```

Outputs land in `./out/`:

| File | What it is |
|------|-----------|
| `conjunctions_<ts>.csv` | Ranked table: pair, NORAD ids, TCA, miss distance, closing speed, risk |
| `report_<ts>.json` | Full payload incl. 3D geometry for the top events |
| `dashboard_latest.html` | Self-contained interactive dashboard — **just open it in a browser** |

### CLI options

```
--group        CelesTrak group: stations | active | starlink | ...   (default: active)
--hours        screening window length in hours                       (default: 24)
--step         coarse time step in seconds                            (default: 60)
--threshold    coarse screening distance in km                        (default: 10)
--max-objects  cap catalog size for a quick run
--no-dashboard skip the HTML build
```

Fast demo run:

```bash
python src/screen.py --group starlink --hours 6 --threshold 5 --max-objects 1500
```

## The dashboard

`dashboard_latest.html` (mirrored to [`docs/index.html`](docs/index.html) for
GitHub Pages) is a single self-contained file with Plotly inlined — no server, no
network. It's built as a four-tab **product site**, not just a report:

- **Overview** — what OrbitGuard is, why orbital conjunctions matter, who it's for
  (operators, agencies like NASA/ESA, analysts), and v1-now vs. what's next.
- **Live Report** — summary stat cards, a rotatable 3D scene of the top events
  (both orbit arcs + the close-approach point + the miss-distance line, switchable
  via a dropdown), and the ranked conjunction table.
- **How it works** — the six-stage pipeline, explained.
- **Roadmap** — v1 → ML risk → autonomy → showcase.

**Host it:** push, then enable GitHub Pages (*Settings → Pages → Branch: `main`,
Folder: `/docs`*) — it goes live at `https://<user>.github.io/OrbitGuard`.

## Validation

Miss distances and TCAs are sanity-checked against **CelesTrak SOCRATES**, the
public conjunction-report service, for a handful of current events. The bar for
v1 is order-of-magnitude agreement — our TLE snapshot may differ slightly in
epoch from theirs. See [`notebooks/03_validate_socrates.ipynb`](notebooks/).

## Repository layout

```
src/
  screen.py                 CLI entry point
  orbitguard/
    catalog.py              download + parse + de-dup TLEs
    propagate.py            SGP4 propagation to an (N,T,3) cube
    screen.py               KD-tree screening + event grouping (+ brute-force ref)
    refine.py               TCA + miss distance (parabolic refinement)
    risk.py                 relative velocity + risk score
    report.py               CSV / JSON / summary
    dashboard.py            self-contained interactive HTML
    pipeline.py             end-to-end orchestration
    ml/                     Phase 3 scaffold (ESA Kelvins CDM risk model)
notebooks/                  01 ISS position · 02 ground track · 03 SOCRATES validation
data/                       dated TLE snapshots (git-ignored)
out/                        generated reports + dashboards
tests/                      correctness tests (KD-tree vs brute force, refinement, …)
```

## Known limits (honest v1 caveats)

- The risk score is a **proxy**, not a formal probability of collision (Pc); it
  has no covariance/uncertainty model. That's Phase 3.
- TLE + SGP4 accuracy is ~km-level and degrades with propagation time.
- Catalogs like `stations` contain docked modules of the same platform (ISS/CSS)
  that legitimately sit <1 km apart at ~0 relative speed — expected, not a threat.
- Screening is geometric; it does not yet model maneuvers or object size.

## Roadmap

- **Phase 3 · ML risk model** — train on the ESA Kelvins Collision Avoidance
  Challenge CDM dataset to predict whether a conjunction escalates. *(scaffold in
  `src/orbitguard/ml/`)*
- **Phase 4 · Autonomy** — for top-risk events, propose a small avoidance Δv and
  show the improved miss distance.
- **Phase 5 · Showcase** — polished writeup + demo.

## Tech

Python · skyfield + sgp4 (propagation) · scipy cKDTree (screening) · numpy/pandas
· plotly (visualization). Data © [CelesTrak](https://celestrak.org).

---

*Built by Aarav as a self-directed project. The commit history is the record.*
