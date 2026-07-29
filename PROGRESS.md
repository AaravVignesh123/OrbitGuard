# OrbitGuard — Progress log

Running record of what's done and what's next. Newest at top.

## v1 complete ✅ (Phases 0–2 + 2.5)

**What works end to end:**
`python src/screen.py --group active --hours 24 --threshold 10` →
downloads/loads the CelesTrak catalog, propagates every object, KD-tree screens
the whole time grid, refines each flag to a precise TCA + miss distance, ranks by
a risk proxy, and writes a CSV + JSON + a self-contained interactive dashboard.

**Latest full run (2026-07-29, `active` group):**
- 16,115 objects loaded (0 malformed, 0 duplicate)
- 24 h window @ 60 s → `(16115, 1440, 3)` position cube
- **8,648 candidate events** at the 10 km threshold
- Refinement sharpens coarse flags dramatically (e.g. #1: 8.0 km coarse → **0.46 km** refined)
- Top events: Starlink–Starlink and Starlink–Flock passes, sub-km miss, 7–14 km/s closing speed
- Fastest closing speed 15.3 km/s; runtime ~292 s
- Showcase dashboard: [`docs/index.html`](docs/index.html)

**Session coverage:**
- Phase 0 (S1–2): ISS position + ground track — `notebooks/01`, `02`
- Phase 1 (S3–4): catalog load + propagation — `orbitguard/catalog.py`, `propagate.py`
- Phase 2 (S5–8): brute-force → KD-tree screen (validated equal) → time loop + grouping → TCA/miss refinement — `orbitguard/screen.py`, `refine.py`
- Phase 2.5 (S9–12): SOCRATES validation notebook (`notebooks/03`), packaged CLI (`src/screen.py`), risk sort (`orbitguard/risk.py`), demo dashboard (`orbitguard/dashboard.py`)
- Tests: `tests/test_pipeline.py` (6/6 passing) — KD-tree vs brute force, event grouping, parabola fit, risk ordering, refinement-beats-coarse.

**Next step:** Phase 3 — download the ESA Kelvins CDM dataset to `data/kelvins/`
and implement `src/orbitguard/ml/dataset.py` (per-event feature aggregation),
then train the baseline model in `ml/model.py`. Also: run `notebooks/03` against
live SOCRATES to record a concrete validation comparison.
