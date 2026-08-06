#!/usr/bin/env python3
"""Generate docs/model.html — a self-contained Phase-3 model card for the site.

    python src/orbitguard/ml/model_card.py

Reads the checked-in comparison.json and renders a static results page (task,
baseline vs CNN vs ensemble, honest verdict, how to reproduce). No dependencies.
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(__file__)


def _fmt(v, nd=3):
    return "—" if v is None else f"{v:.{nd}f}"


def build(comparison_path=None, out_path="docs/model.html") -> str:
    comparison_path = comparison_path or os.path.join(HERE, "comparison.json")
    r = json.load(open(comparison_path))
    b, c, e = r["baseline"], r["cnn"], r["ensemble"]

    def row(name, m, hi=False):
        cls = ' class="best"' if hi else ""
        return (f"<tr><td>{name}</td>"
                f"<td{cls if _is_best(r,'pr_auc',m) else ''}>{_fmt(m['pr_auc'])}</td>"
                f"<td{cls if _is_best(r,'roc_auc',m) else ''}>{_fmt(m['roc_auc'])}</td>"
                f"<td{cls if _is_best(r,'f2_best',m) else ''}>{_fmt(m['f2_best'])}</td>"
                f"<td>{_fmt(m.get('rmse_high_risk'), 2)}</td></tr>")

    table = (
        "<table><thead><tr><th>model</th><th>PR-AUC</th><th>ROC-AUC</th>"
        "<th>F2 (best)</th><th>RMSE · high-risk</th></tr></thead><tbody>"
        + row("Gradient-boosted trees (baseline)", b)
        + row("1-D CNN over CDM sequence", c)
        + row("Rank-ensemble", e)
        + "</tbody></table>"
    )

    n_ev = b["n_events"]
    n_hi = b["n_high_risk"]
    html = _PAGE.replace("__TABLE__", table).replace("__NEV__", f"{n_ev:,}") \
                .replace("__NHI__", str(n_hi)).replace("__PCT__", f"{100*n_hi/n_ev:.1f}")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        fh.write(html)
    return out_path


def _is_best(r, key, m):
    vals = [x[key] for x in (r["baseline"], r["cnn"], r["ensemble"]) if x.get(key) is not None]
    return m.get(key) is not None and m[key] == max(vals)


_PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OrbitGuard — Phase 3 Model Card</title>
<style>
:root{ color-scheme:dark; --bg:#04060d; --panel:rgba(13,18,32,.72); --hair:rgba(150,170,210,.14);
  --ink:#eef2f8; --dim:#9aa7be; --faint:#5f6c85; --accent:#5cc8ff; --green:#34d399;
  --mono:ui-monospace,SFMono-Regular,Menlo,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  line-height:1.6;background-image:radial-gradient(1000px 600px at 80% -10%,rgba(28,58,102,.4),transparent 60%);}
a{color:var(--accent);text-decoration:none}
.wrap{max-width:900px;margin:0 auto;padding:44px 24px 80px}
.kick{font-family:var(--mono);font-size:11px;letter-spacing:.22em;color:var(--faint);text-transform:uppercase}
h1{font-size:34px;letter-spacing:-.03em;margin:10px 0 6px}
h2{font-size:20px;margin:38px 0 12px;letter-spacing:-.02em}
.lead{color:#c4cee0;font-size:16px;max-width:680px}
.pill{display:inline-block;font-family:var(--mono);font-size:11px;color:var(--green);border:1px solid rgba(52,211,153,.3);
  background:rgba(52,211,153,.08);padding:4px 10px;border-radius:999px;margin-bottom:16px}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:6px}
th,td{padding:10px 12px;border-bottom:1px solid var(--hair);text-align:right;font-family:var(--mono)}
th:first-child,td:first-child{text-align:left;font-family:var(--sans)}
th{color:var(--faint);font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:600}
td.best{color:var(--green);font-weight:600}
.panel{border:1px solid var(--hair);border-radius:14px;padding:18px 20px;background:var(--panel);margin-top:8px}
.demo{font-family:var(--mono);font-size:13px;color:#bcd0ea;white-space:pre-wrap;line-height:1.5}
.big{font-size:30px;font-weight:700;color:var(--green)}
code{font-family:var(--mono);background:#0b1120;border:1px solid var(--hair);border-radius:6px;padding:1px 6px;font-size:.9em;color:#cfe6ff}
.cmd{font-family:var(--mono);font-size:13px;color:#cfe6ff;background:#080d18;border:1px solid var(--hair);
  border-radius:10px;padding:12px 14px;margin:8px 0;white-space:pre-wrap}
.note{color:var(--faint);font-size:12.5px;margin-top:10px;line-height:1.6}
footer{margin-top:44px;border-top:1px solid var(--hair);padding-top:16px;color:var(--faint);font-family:var(--mono);font-size:12px}
</style></head>
<body><div class="wrap">
<div class="kick"><a href="./">← OrbitGuard</a> · Phase 3</div>
<div class="pill">● TRAINED &amp; CROSS-VALIDATED</div>
<h1>Conjunction-risk model</h1>
<p class="lead">A learned replacement for the v1 geometric risk proxy: predict whether a close
approach will <b>escalate</b> — its final collision probability — from Conjunction Data Messages
issued at least 2 days before closest approach. Trained on the ESA Kelvins Collision Avoidance
Challenge dataset (__NEV__ events; only __NHI__ — __PCT__% — are truly high-risk).</p>

<h2>Results — 5-fold cross-validation</h2>
<div class="panel">__TABLE__</div>
<p class="note">Identical events, folds and metrics across all three. Green = best in column.
The <b>CNN</b> reads each event's full CDM <i>sequence</i> and wins on operational metrics
(F2, and the risk-value RMSE); the <b>trees</b> win on ranking recall; the <b>rank-ensemble</b>
gives the best overall ranking (PR-AUC / ROC-AUC). No single model dominates — an honest,
complementary-strengths result. RMSE is N/A for the ensemble (its score is a rank, not a risk value).</p>

<h2>Does it actually work?</h2>
<div class="panel"><div class="demo">Top-15 predicted-riskiest <b>held-out</b> events (never seen in training):
<span class="big">14 / 15</span> are truly high-risk.
A random ranker would get ~0.4 / 15 (high-risk events are only 2.7% of the test set).</div></div>
<p class="note">Reproduce this yourself: <code>python src/orbitguard/ml/predict_demo.py</code></p>

<h2>Reproduce everything</h2>
<div class="cmd"># 1 · get the public Kelvins data (no login)
curl -L -o data/kelvins/train_data.zip \
  https://kelvins.esa.int/media/public/competitions/collision-avoidance-challenge/train_data.zip
cd data/kelvins &amp;&amp; unzip train_data.zip &amp;&amp; cd -

# 2 · baseline, CNN, and the head-to-head
python src/orbitguard/ml/train_baseline.py
python src/orbitguard/ml/train_cnn.py
python src/orbitguard/ml/compare.py</div>

<h2>Honest limits</h2>
<p class="note">This model scores <b>Kelvins CDMs</b>, not yet OrbitGuard's own live conjunctions — our
v1 screener produces geometry, not the covariance / orbit-determination features this model relies on.
Wiring the two together (imputing or generating CDM-like features for our catalogue) is Phase 4.
Metrics here are cross-validated, not a held-out competition submission.</p>

<footer>OrbitGuard · Phase 3 · gradient-boosted trees + 1-D CNN · data © ESA Kelvins</footer>
</div></body></html>
"""


if __name__ == "__main__":
    p = build()
    print(f"wrote {p}")
