# OrbitGuard — Phase 3 · ML risk model

Goal: replace the v1 geometric risk **proxy** with a **learned probability that a
conjunction escalates**, trained on real Conjunction Data Messages (CDMs).

## Two datasets

### 1. Real data — ESA Kelvins Collision Avoidance Challenge (the target)

The canonical dataset: ~162,634 CDM rows across ~13,154 unique conjunction
events (≈12 CDMs/event), anonymised, ESA 2015–2019. Each event is a *time
series* of CDMs issued as TCA approaches; the label is the risk of the **last**
CDM before TCA. The task: predict that final risk from the earlier CDMs — i.e.
decide, days ahead, whether an event becomes high-risk (`risk > -6`).

**Get it (free):**
- Official: <https://kelvins.esa.int/collision-avoidance-challenge/data/> (register, download `train_data.csv` / `test_data.csv`)
- Public mirror (Kaggle account): <https://www.kaggle.com/datasets/shadmanrohan/collisionavoidancechallenge>

Then place the files here:

```
data/kelvins/train_data.csv
data/kelvins/test_data.csv
```

`dataset.py` defines the loading contract; `features.py` the per-event
aggregation; `model.py` the training stub (gradient-boosted trees + GroupKFold on
`event_id`). The Kessler library (ESA/Trillium) is a good reference for parsing CDMs.

### 2. Bootstrap data — start today (plumbing, not science)

You don't need to wait for the download to build the training harness. Generate a
correctly-shaped, labelled starter CSV straight from OrbitGuard's own screening
output:

```bash
python -m orbitguard.ml.bootstrap_dataset out/report_latest.json data/ml_bootstrap_dataset.csv
```

(A ready-made copy is committed at [`data/ml_bootstrap_dataset.csv`](../../../data/ml_bootstrap_dataset.csv).)

Columns: `event_id, object_a, object_b, miss_km, coarse_miss_km, rel_speed_kms,
alt_km, closing_geom, risk_score, high_risk`.

⚠️ The `high_risk` label here is a **deterministic rule** on the features
(close *and* fast), so any model will score ~perfectly — that is expected and
proves only that the pipeline works. Use it to build/validate data loading,
splits, training, and metrics; swap in Kelvins for real learning.

## Suggested first model (baseline)

1. Load Kelvins, group by `event_id`, sort each event by `time_to_tca` desc.
2. Aggregate per event: last-CDM snapshot + simple trend features (Δmiss, Δrisk).
3. `HistGradientBoostingRegressor` (or classifier on `risk > -6`).
4. **GroupKFold on `event_id`** so no event leaks across folds.
5. Report the challenge's F2-style metric (rewards catching true high-risk events).

See the module stubs in this folder for the interfaces to fill in.
