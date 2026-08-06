# Phase 3 — ML conjunction-risk model

Replace the v1 geometric risk *proxy* with a **learned probability that a
conjunction escalates**, trained on real Conjunction Data Messages (CDMs) from
the **ESA Kelvins Collision Avoidance Challenge**.

## The task

Each *event* is a time-ordered sequence of CDMs (on average ~12) issued in the
days before the time of closest approach (TCA). The label is the **final risk** —
`risk` = log₁₀(collision probability) of the CDM closest to TCA. We may only use
information available **≥ 2 days before TCA**; anything inside the 2-day window
would leak the answer. An event is **high-risk** if final `risk ≥ −6`.

- 13,154 events · 162,634 CDMs · 103 raw features
- Only **2.7%** of events are high-risk → heavily imbalanced.

## Get the data (public, no login)

```bash
mkdir -p data/kelvins && cd data/kelvins
curl -L -o train_data.zip \
  https://kelvins.esa.int/media/public/competitions/collision-avoidance-challenge/train_data.zip
unzip train_data.zip     # -> train_data.csv   (git-ignored)
```

## Run the baseline

```bash
python src/orbitguard/ml/train_baseline.py
```

## Baseline results (5-fold stratified CV, gradient-boosted trees)

| metric | value |
|---|---|
| **PR-AUC** (avg precision) | **0.641** |
| **ROC-AUC** | **0.958** |
| **F2** (best threshold) | **0.635** |
| precision / recall @ −6 | 0.89 / 0.44 |
| RMSE on high-risk risk | 1.86 |

Model: `HistGradientBoostingRegressor` (handles NaNs + the categorical
object-type column natively). Key trick: **clip the training target at −10** — 64%
of events sit at the `−30` no-risk sentinel, which otherwise dominates the
squared-error loss; clipping (still 4 below the −6 decision boundary) more than
doubles PR-AUC and cuts high-risk RMSE ~4×. Top features: the early `risk`
estimate, `time_to_tca`, covariance sigmas — physically sensible.

For reference, ESA challenge winners scored ~F2 0.56–0.60 on the held-out set
under the official (slightly different) metric, so this is a competitive baseline.

## Files

- `dataset.py` — download contract + `build_event_table()` (raw CDMs → one row/event)
- `model.py` — `train_baseline()`: CV, metrics (PR-AUC / F2 / RMSE), full-fit model
- `train_baseline.py` — runnable entry point → `out/ml/`
- `features.py` — Phase-4 bridge to live screener output (stub)
- `bootstrap_dataset.py` — tiny self-generated dataset from our own screener (smoke-test only)
- `baseline_metrics.json` — the numbers above, checked in for the record

## CNN — head-to-head (done)

A small **1-D CNN** reads each event's *sequence* of CDMs (19 per-CDM features ×
20 timesteps → masked global avg/max pool → risk). Same events, folds, metrics.

| model | PR-AUC | ROC-AUC | F2 | RMSE (high-risk) |
|---|---|---|---|---|
| gradient-boosted trees | **0.641** | 0.958 | 0.635 | 1.86 |
| 1-D CNN | 0.565 | 0.963 | **0.653** | **1.32** |
| rank-ensemble | **0.652** | **0.965** | 0.645 | — |

**Honest verdict: no single model dominates.** The CNN wins the operational
metrics (F2, and the risk-value RMSE — it gets the *number* right on high-risk
events); the trees win ranking recall; the rank-ensemble gives the best overall
ranking. That's the complementary-strengths result you'd expect, reported as-is.

```bash
python src/orbitguard/ml/train_cnn.py     # CNN vs baseline
python src/orbitguard/ml/compare.py       # baseline vs CNN vs ensemble -> comparison.json
python src/orbitguard/ml/predict_demo.py  # sanity: 14/15 top predictions are truly high-risk
python src/orbitguard/ml/model_card.py    # regenerate docs/model.html
```

## Is it in the webpage?

There's a **model card** at `docs/model.html` (live at
`…github.io/OrbitGuard/model.html`) showing these results. The model does **not**
yet score OrbitGuard's own live conjunctions — our v1 screener produces geometry,
not the covariance/OD features this model needs. Bridging them is **Phase 4**
(`features.bridge_from_screener`).
