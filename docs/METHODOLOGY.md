# OrbitGuard — Methodology

A short, honest technical writeup of how OrbitGuard turns a public satellite
catalogue into ranked, validated conjunction predictions with a real probability
of collision — and exactly where the limits are.

## Pipeline

```
CelesTrak TLEs → propagate (SGP4, one inertial frame) → position cube (N×T×3)
  → KD-tree screen (close pairs, verified == brute force) → group into events
  → refine (analytic TCA + miss) → Pc (Foster 2-D) → rank → report + globe
```

**1. Propagate.** Every object is advanced with SGP4 onto one shared inertial
frame (skyfield GCRS). Same-frame is the invariant that makes distances meaningful.

**2. Screen.** At each timestep a `scipy` KD-tree returns pairs within the
threshold in ~O(n·log n) instead of the O(n²) wall (~130 M pairs/step at 16 k
objects). Verified to return the *exact* brute-force pair set.

**3. Refine.** The coarse 60 s grid over-estimates the miss (objects move ~840 km
between samples at 14 km/s). We solve the closest approach analytically from the
relative position/velocity: `ΔT = −(r·v)/|v|²`, `miss = |r + v·ΔT|`. Exact for
linear relative motion; validated to **< 12 m** against an independent 0.01 s
brute-force search.

**4. Probability of collision (Foster 2-D).** Project the combined position
covariance onto the encounter plane (⟂ to the relative velocity) and integrate a
2-D Gaussian over the hard-body disk. Because public TLEs carry **no covariance**,
we use a *documented assumed* RTN covariance (along-track dominant, growing with
TLE age) and a hard-body radius. Pc is therefore an **order-of-magnitude
estimate**, reported with a worst-case `max-Pc`. The closed-form check
`Pc = 1 − exp(−HBR²/2σ²)` (isotropic, zero offset) anchors the numerical integral.

**5. Rank.** A geometric proxy (`closing speed / miss`, log-scaled) for quick
triage, shown alongside Pc.

## Validation

Rigor is the product, so every claim is recomputed and shown (the **Methodology**
tab renders these live):

- **Screening** = brute force, exactly (max pair-distance diff ~1e-12 m).
- **Refinement** miss vs. independent 0.01–0.02 s search: **< 12 m**.
- **Relative velocity** vs. independent computation: **< 1 m/s**.
- **Physical validation (SOCRATES).** We fetch CelesTrak SOCRATES' soonest
  conjunctions and independently reproduce them (its objects, our freshly-fetched
  TLEs, our propagation + Pc). Miss distances agree to **hundreds of metres
  (median)** — order-of-magnitude agreement against the authoritative feed; larger
  scatter comes from element-set freshness (volatile debris), not method error.
  Max-Pc uses SOCRATES' documented RTN covariance (100/300/100 m) for an
  apples-to-apples comparison.

## Machine learning (Phase 3)

A gradient-boosted baseline and a 1-D CNN, trained on the ESA Kelvins Collision
Avoidance Challenge CDM dataset, predict whether a conjunction *escalates* from
CDMs ≥ 2 days before TCA. Cross-validated (5-fold): PR-AUC ≈ 0.64–0.65, F2 ≈ 0.64.

**Phase 4 (experimental).** `ml.features.bridge_from_screener` maps a live screener
event into the model's feature space — but the TLE screener produces only **9 of
110** features; the rest (including the model's top feature, the prior CDM `risk`)
are imputed, so the learned score is near-constant and **not surfaced
per-conjunction**. The honest conclusion: a covariance-based **Pc** is the right
live risk signal today; the learned model needs real CDMs to add value.

## Honest limits

- TLE accuracy is ~km-level; Pc is under an *assumed* covariance.
- Conjunction analysis is a batch job; the globe's *positions* are live but the
  *risk numbers* on it are as-of the last screening run.
- OrbitGuard is a transparent **reference/demonstrator**, not an operational tool.

## Reproduce

```bash
python src/screen.py --group active --hours 24 --threshold 10   # full pipeline
python -m orbitguard.validate                                   # validation + SOCRATES
python tests/test_pipeline.py && python tests/test_pc.py        # 9 + 5 tests
```
