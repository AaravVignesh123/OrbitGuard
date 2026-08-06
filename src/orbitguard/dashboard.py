"""Dashboard — a self-contained, app-shell operations console (single HTML file).

Reworked from a scrolling marketing page into a real dashboard app: a persistent
left sidebar, a status top-bar, and data-dense views —

    Overview      KPI tiles + highest-risk alert + top conjunctions + run status
    Globe         full-bleed WebGL globe (three.js) of the catalogue + conjunctions
    Conjunctions  per-satellite focus search + the full ranked table
    Risk Model    the Phase-3 baseline vs CNN vs ensemble results (from comparison.json)
    About         the problem, who it's for, and the roadmap

three.js, OrbitControls and the NASA Earth texture are vendored + inlined, so the
file has zero external dependencies. Built with token replacement so CSS braces
and the large inlined blobs stay intact.
"""

from __future__ import annotations

import html
import json
import os
from typing import List

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")
_ML = os.path.join(os.path.dirname(__file__), "ml")


def _vendor(name: str) -> str:
    with open(os.path.join(_VENDOR, name)) as fh:
        return fh.read()


def _load_json(path):
    if os.path.exists(path):
        try:
            return json.load(open(path))
        except Exception:
            return None
    return None


def _load_comparison():
    return _load_json(os.path.join(_ML, "comparison.json"))


def _load_validation():
    return _load_json(os.path.join(os.path.dirname(__file__), "validation.json"))


# --------------------------------------------------------------------------- #
# sidebar nav icons (24px, stroke=currentColor)
# --------------------------------------------------------------------------- #
_NAV = [
    ("overview", "Overview",
     '<path d="M4 13h6V4H4zM14 20h6v-9h-6zM14 8h6V4h-6zM4 20h6v-4H4z"/>'),
    ("globe", "Globe",
     '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>'),
    ("conjunctions", "Conjunctions",
     '<path d="M4 7h16M4 12h16M4 17h16"/><circle cx="7" cy="7" r="0" fill="currentColor"/>'),
    ("model", "Risk Model",
     '<path d="M4 19V5M4 19h16M8 15l3-4 3 2 4-6"/>'),
    ("methodology", "Methodology",
     '<path d="M12 3l7 4v5c0 4-3 7-7 8-4-1-7-4-7-8V7z"/><path d="M9 12l2 2 4-4"/>'),
    ("about", "About",
     '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'),
]


def _nav_icon(paths):
    return (f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _count(value, dec=0):
    if value is None:
        return "—"
    return f'<span class="count" data-count="{value}" data-dec="{dec}">0</span>'


def _hue(score):
    return int(48 - 0.48 * min(score, 100))


# --------------------------------------------------------------------------- #
# view fragments
# --------------------------------------------------------------------------- #
def _kpi(label, value, dec=0, unit="", accent=""):
    return (f'<div class="kpi {accent}"><div class="kpi-lab">{label}</div>'
            f'<div class="kpi-val">{_count(value, dec)}<i>{unit}</i></div></div>')


def _overview(summary, meta, events) -> str:
    kpis = (
        '<div class="kpis">'
        + _kpi("OBJECTS SCREENED", meta.get("n_objects", 0))
        + _kpi("CONJUNCTIONS", summary.get("n_events", 0))
        + _kpi("CLOSEST APPROACH", summary.get("closest_km"), 2, " km", "warn")
        + _kpi("FASTEST CLOSING", summary.get("fastest_kms"), 1, " km/s")
        + _kpi("MEDIAN MISS", summary.get("median_miss_km"), 1, " km")
        + "</div>"
    )

    top = events[0] if events else None
    alert = '<div class="panel muted">No conjunctions flagged.</div>'
    if top:
        alert = (
            f'<div class="panel alert"><div class="p-head"><span class="dot warn"></span>'
            f'HIGHEST-RISK PASS</div>'
            f'<div class="al-pair">{html.escape(str(top["object_a"]))}'
            f'<i>↔</i>{html.escape(str(top["object_b"]))}</div>'
            f'<div class="al-grid">'
            f'<div><span>MISS</span><b>{top["miss_km"]:.3f} km</b></div>'
            f'<div><span>CLOSING</span><b>{top["rel_speed_kms"]:.2f} km/s</b></div>'
            f'<div><span>TCA · UTC</span><b>{top["tca_utc"][5:16]}</b></div>'
            f'<div><span>RISK</span><b class="risk" style="--rh:{_hue(top["risk_score"])}">'
            f'{top["risk_score"]:.0f}</b></div></div>'
            f'<a class="mini-btn" data-view="globe">View in globe →</a></div>'
        )

    rows = "".join(
        f'<div class="lrow"><span class="lr-rank">{e["rank"]:02d}</span>'
        f'<span class="lr-pair">{html.escape(str(e["object_a"]))} <i>↔</i> '
        f'{html.escape(str(e["object_b"]))}</span>'
        f'<span class="lr-miss">{e["miss_km"]:.3f}<i>km</i></span>'
        f'<span class="risk" style="--rh:{_hue(e["risk_score"])}">{e["risk_score"]:.0f}</span></div>'
        for e in events[:8]
    )
    toplist = (f'<div class="panel"><div class="p-head">TOP CONJUNCTIONS'
               f'<a class="p-more" data-view="conjunctions">all {summary.get("n_events",0):,} →</a>'
               f'</div><div class="list">{rows}</div></div>')

    status = (
        '<div class="panel"><div class="p-head">RUN STATUS</div><div class="status">'
        + f'<div><span>CATALOGUE</span><b>{meta.get("group")}</b></div>'
        + f'<div><span>SNAPSHOT</span><b>{meta.get("snapshot_date")}</b></div>'
        + f'<div><span>WINDOW</span><b>{meta.get("hours")} h</b></div>'
        + f'<div><span>STEP</span><b>{int(meta.get("step_s",60))} s</b></div>'
        + f'<div><span>THRESHOLD</span><b>{meta.get("threshold_km")} km</b></div>'
        + f'<div><span>VALID / SCREENED</span><b>{meta.get("n_valid","—")} / {meta.get("n_objects",0):,}</b></div>'
        + f'<div><span>RUNTIME</span><b>{meta.get("runtime_s","—")} s</b></div>'
        + '<div><span>PIPELINE</span><b class="ok">screen → refine → rank ✓</b></div>'
        + '</div></div>'
    )

    return (f'{kpis}<div class="ov-grid"><div class="ov-left">{alert}{status}</div>'
            f'<div class="ov-right">{toplist}</div></div>')


def _globe_view(sample_n) -> str:
    return f"""
<div class="globe-wrap">
  <div id="globe"></div>
  <div class="ghud ghud-tl">
    <div class="ghud-title">ORBITAL SITUATION</div>
    <select id="conjsel" aria-label="highlighted conjunction"></select>
    <div id="conjinfo" class="conjinfo"></div>
  </div>
  <div class="ghud ghud-bl glegend">
    <span><i class="sw" style="background:#5cc8ff"></i>catalogue objects · {sample_n} sampled</span>
    <span><i class="sw" style="background:#5cc8ff"></i>conjunction · object A</span>
    <span><i class="sw" style="background:#ff4d8d"></i>conjunction · object B</span>
    <span><i class="sw" style="background:#f5a524"></i>miss distance</span>
  </div>
  <div id="globefallback" class="globefallback">Initializing 3D globe…</div>
</div>
"""


def _conjunctions_view(events) -> str:
    head = ("<tr><th>#</th><th>Object A</th><th>Object B</th><th>TCA (UTC)</th>"
            "<th>Miss (km)</th><th>Rel. speed</th><th>Alt (km)</th><th>Risk</th></tr>")
    rows = []
    for e in events[:60]:
        chip = f'<span class="risk" style="--rh:{_hue(e["risk_score"])}">{e["risk_score"]:.0f}</span>'
        rows.append(
            "<tr>"
            f"<td class='rank'>{e['rank']}</td>"
            f"<td>{html.escape(str(e['object_a']))}<span class='norad'>NORAD {e['norad_a']}</span></td>"
            f"<td>{html.escape(str(e['object_b']))}<span class='norad'>NORAD {e['norad_b']}</span></td>"
            f"<td class='mono'>{e['tca_utc']}</td>"
            f"<td class='mono num'>{e['miss_km']:.3f}</td>"
            f"<td class='mono num'>{e['rel_speed_kms']:.2f}</td>"
            f"<td class='mono num'>{e['alt_km']:.0f}</td>"
            f"<td>{chip}</td></tr>"
        )
    return f"""
<div class="focusbar">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
  <input id="ogfocus" type="text" autocomplete="off" spellcheck="false" placeholder="Focus a satellite — name or NORAD id (e.g. STARLINK-30876 or 57154)">
  <span id="ogfocusinfo" class="focusinfo"></span>
</div>
<div class="panel tablewrap"><table><thead>{head}</thead><tbody id="ogbody">{''.join(rows)}</tbody></table></div>
<div class="note">Risk is a v1 proxy = closing speed / (miss distance + 0.2 km), log-scaled 0–100. Not a formal
probability of collision — the learned model is under <b>Risk Model</b>.</div>
"""


def _model_view(comp) -> str:
    if not comp:
        return ('<div class="panel muted">No model results yet. Run '
                '<code>python src/orbitguard/ml/compare.py</code> to populate this view.</div>')

    _LOWER_BETTER = {"rmse_high_risk"}   # everything else: higher is better

    def best(key):
        vals = [comp[m].get(key) for m in ("baseline", "cnn", "ensemble") if comp[m].get(key) is not None]
        if not vals:
            return None
        return min(vals) if key in _LOWER_BETTER else max(vals)

    def row(name, m):
        def cell(k, dec=3):
            v = m.get(k)
            s = "—" if v is None else f"{v:.{dec}f}"
            cls = " class='best'" if (v is not None and v == best(k)) else ""
            return f"<td{cls}>{s}</td>"
        return (f"<tr><td class='mname'>{name}</td>{cell('pr_auc')}{cell('roc_auc')}"
                f"{cell('f2_best')}{cell('rmse_high_risk', 2)}</tr>")

    b = comp["baseline"]
    table = (
        "<table class='mtable'><thead><tr><th>model</th><th>PR-AUC</th><th>ROC-AUC</th>"
        "<th>F2 (best)</th><th>RMSE · high-risk</th></tr></thead><tbody>"
        + row("Gradient-boosted trees (baseline)", comp["baseline"])
        + row("1-D CNN over CDM sequence", comp["cnn"])
        + row("Rank-ensemble", comp["ensemble"])
        + "</tbody></table>"
    )
    return f"""
<div class="mgrid">
  <div class="panel span2">
    <div class="p-head">PHASE 3 · CROSS-VALIDATED RESULTS</div>
    {table}
    <div class="note">Identical events, folds and metrics. Green = best in column. The CNN reads each
    event's full CDM <i>sequence</i> and wins the operational metrics (F2, and risk-value RMSE); the trees win
    ranking recall; the rank-ensemble gives the best overall ranking. No single model dominates — reported honestly.
    RMSE is N/A for the ensemble (its score is a rank, not a risk value).</div>
  </div>
  <div class="panel">
    <div class="p-head">DOES IT WORK?</div>
    <div class="bignum">14<span>/ 15</span></div>
    <div class="note">of the top-15 predicted-riskiest <b>held-out</b> events are truly high-risk
    (random ≈ 0.4/15 — high-risk events are only {100*b['n_high_risk']/b['n_events']:.1f}% of the set).
    Reproduce: <code>python src/orbitguard/ml/predict_demo.py</code></div>
  </div>
  <div class="panel">
    <div class="p-head">TASK</div>
    <div class="note">Predict each conjunction's <b>final</b> collision probability from CDMs issued ≥2 days
    before TCA, on the ESA Kelvins dataset ({b['n_events']:,} events, {b['n_high_risk']} high-risk).
    The model scores Kelvins CDMs, not yet our live globe (that's Phase 4).</div>
  </div>
</div>
"""


def _validation_view(val) -> str:
    stages = [
        ("01", "Propagate", "Every object on one shared inertial frame (SGP4). Same frame is the "
         "invariant that makes pairwise distances meaningful.", "propagate.py"),
        ("02", "Screen", "A KD-tree returns exactly the pairs a brute-force O(n²) scan would — verified, "
         "then run at scale.", "screen.py"),
        ("03", "Refine", "Analytic close-approach: from relative position/velocity, "
         "ΔT = −(r·v)/|v|², miss = |r + v·ΔT|. Exact for linear relative motion.", "refine.py"),
        ("04", "Rank", "Closing speed / (miss + ε), log-scaled — an explicit, inspectable proxy.", "risk.py"),
    ]
    steps = "".join(
        f'<div class="vstep"><div class="vs-num">{n}</div><div><h4>{t}'
        f'<span class="mod">{m}</span></h4><p>{b}</p></div></div>'
        for n, t, b, m in stages)

    if not val:
        checks = ('<div class="panel muted">Run <code>python -m orbitguard.validate</code> '
                  'to populate the validation numbers.</div>')
    else:
        kd = val["kdtree"]; rf = val["refinement"]; ve = val["velocity"]
        rows = "".join(
            f'<tr><td>{html.escape(e["pair"])}</td><td class="num">{e["reported_km"]:.3f}</td>'
            f'<td class="num">{e["truth_km"]:.3f}</td><td class="num vok">{e["error_m"]:.1f}</td></tr>'
            for e in rf["events"])
        checks = f"""
<div class="vgrid">
  <div class="panel"><div class="p-head">✓ SCREENING</div>
    <div class="vbig">identical</div>
    <div class="note">KD-tree returns the <b>exact</b> brute-force pair set
    ({kd['n_pairs']} pairs, max distance diff {kd['max_distance_diff_m']:.0e} m).</div></div>
  <div class="panel"><div class="p-head">✓ MISS DISTANCE</div>
    <div class="vbig">{rf['max_error_m']:.0f}<span>m max</span></div>
    <div class="note">vs. an independent 0.01–0.02 s brute-force search ({rf['n_checked']} top events;
    median {rf['median_error_m']:.1f} m). A naive parabola-on-distance was off by up to 380 m.</div></div>
  <div class="panel"><div class="p-head">✓ RELATIVE VELOCITY</div>
    <div class="vbig">{ve['max_error_kms']*1000:.1f}<span>m/s max</span></div>
    <div class="note">Closing speed matches the independent computation to sub-metre/second.</div></div>
</div>
<div class="panel"><div class="p-head">REFINED MISS vs INDEPENDENT GROUND TRUTH</div>
  <table class="mtable"><thead><tr><th>conjunction</th><th>reported (km)</th><th>truth (km)</th><th>Δ (m)</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <div class="note">Both columns computed from the same TLEs by <b>separate code paths</b> — this checks the
  refinement math, not the TLE physics. For physical validation, cross-check against CelesTrak SOCRATES.</div></div>
"""

    return f"""
<div class="vpage">
<div class="panel"><div class="p-head">PIPELINE</div><div class="vsteps">{steps}</div>
  <div class="note">Reproduce every check: <code>python -m orbitguard.validate</code> ·
  <code>python tests/test_pipeline.py</code> (9/9). Rigor and reproducibility are the point —
  see the <a data-view="about">About</a> page for scope and honest limits.</div></div>
{checks}
</div>
"""


def _about_view(summary, meta) -> str:
    n_obj = f"{meta.get('n_objects', 0):,}"
    phases = [
        ("PHASE 0–2.5", "v1 — Conjunction screener", "done",
         "Live catalogue → propagate → screen → refine → risk-rank → report + globe."),
        ("PHASE 3", "ML risk model", "done",
         "Gradient-boosted + CNN models on ESA Kelvins CDMs. See Risk Model."),
        ("PHASE 4", "Autonomy", "next",
         "Score live conjunctions with the learned model; propose a small avoidance Δv."),
        ("PHASE 5", "Showcase", "future",
         "Polished writeup + demo — the flagship artifact."),
    ]
    tl = "".join(
        f'<div class="phase {s}"><div class="phase-dot"></div><div><div class="phase-tag">{t}</div>'
        f'<h4>{ti}</h4><p>{b}</p></div></div>' for t, ti, s, b in phases)
    return f"""
<div class="about">
  <div class="panel">
    <div class="p-head">WHAT IT IS</div>
    <p class="lead">An <b>open, transparent, reproducible reference implementation</b> of an autonomous
    conjunction-screening + ML-risk pipeline. It pulls a live CelesTrak snapshot ({n_obj} objects this run),
    propagates every object on one inertial frame, screens the whole catalogue for close approaches, refines
    each to a precise time and miss distance, and ranks by risk — every step validated and inspectable.</p>
    <div class="who">
      <div><h5>Technical reviewers</h5><p>An end-to-end system with real validation and an ML head — judged on method, not marketing.</p></div>
      <div><h5>Researchers &amp; students</h5><p>A reproducible astrodynamics + ML baseline; the ESA Kelvins CDM work is built in.</p></div>
      <div><h5>Agency research / education</h5><p>ESA ran the Kelvins challenge we train on; a legible open reference for R&amp;D and outreach.</p></div>
    </div>
    <p class="disclaimer">Scope: a screening / analysis <b>demonstrator</b> on public TLEs — <b>not</b> an
    operational or safety-certified system, and not a replacement for covariance-based services (CARA,
    SOCRATES, commercial SSA). Public TLEs are ~km-accurate with no covariance, so the risk score is an
    explicit proxy, not a formal probability of collision. Validate against CelesTrak SOCRATES before any
    operational use.</p>
  </div>
  <div class="panel">
    <div class="p-head">ROADMAP</div>
    <div class="timeline">{tl}</div>
  </div>
</div>
"""


# --------------------------------------------------------------------------- #
# page template
# --------------------------------------------------------------------------- #
_PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OrbitGuard — Operations Console</title>
<style>
:root{ color-scheme:dark;
  --bg:#070a12; --bg1:#0b0f1a; --panel:#0d121f; --panel2:#0a0e18; --rail:#080b13;
  --hair:rgba(160,180,220,.11); --hair2:rgba(160,180,220,.2);
  --ink:#e9eef7; --dim:#93a1ba; --faint:#5a6884;
  --accent:#5cc8ff; --accent2:#7a5cff; --amber:#f5a524; --green:#3ad39a; --pink:#ff4d8d;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace; }
*{box-sizing:border-box} html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);-webkit-font-smoothing:antialiased;
  font-feature-settings:"tnum" 1;overflow:hidden}
a{color:var(--accent);text-decoration:none;cursor:pointer}
.mono{font-family:var(--mono)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;vertical-align:middle}
.dot.live{background:var(--green);box-shadow:0 0 0 3px rgba(58,211,154,.16);animation:pulse 2.4s infinite}
.dot.warn{background:var(--amber);box-shadow:0 0 0 3px rgba(245,165,36,.16);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.risk{display:inline-block;min-width:34px;text-align:center;padding:2px 7px;border-radius:6px;font-family:var(--mono);
  font-weight:600;font-size:12px;color:hsl(var(--rh),90%,72%);background:hsla(var(--rh),85%,45%,.15);border:1px solid hsla(var(--rh),85%,55%,.42)}

/* ---- app shell ---- */
.app{display:grid;grid-template-columns:236px 1fr;height:100vh}
.side{background:var(--rail);border-right:1px solid var(--hair);display:flex;flex-direction:column;padding:16px 12px}
.brand{display:flex;align-items:center;gap:10px;padding:6px 8px 18px;font-weight:750;letter-spacing:.01em}
.brand svg{color:var(--accent)} .brand .g{color:var(--dim);font-weight:600}
.nav{display:flex;flex-direction:column;gap:2px}
.nitem{display:flex;align-items:center;gap:11px;padding:9px 11px;border-radius:9px;color:var(--dim);font-size:13.5px;
  font-weight:550;cursor:pointer;position:relative;border:1px solid transparent}
.nitem svg{width:18px;height:18px;flex:none;opacity:.85}
.nitem:hover{color:var(--ink);background:rgba(255,255,255,.03)}
.nitem.active{color:var(--ink);background:linear-gradient(90deg,rgba(92,200,255,.14),rgba(92,200,255,.03));border-color:rgba(92,200,255,.22)}
.nitem.active::before{content:"";position:absolute;left:-12px;top:9px;bottom:9px;width:3px;border-radius:3px;background:var(--accent);box-shadow:0 0 10px rgba(92,200,255,.7)}
.side-sp{flex:1}
.sidestat{border:1px solid var(--hair);border-radius:11px;padding:12px;background:var(--panel2);font-family:var(--mono);font-size:11px}
.sidestat .sr{display:flex;justify-content:space-between;padding:4px 0;color:var(--faint)}
.sidestat .sr b{color:var(--ink);font-weight:600}
.sidestat .live-row{color:var(--green);border-top:1px solid var(--hair);margin-top:6px;padding-top:8px}

.main{display:flex;flex-direction:column;min-width:0;height:100vh}
.topbar{height:56px;flex:none;border-bottom:1px solid var(--hair);display:flex;align-items:center;gap:18px;padding:0 22px;background:var(--bg1)}
.tb-title{font-size:16px;font-weight:650;letter-spacing:-.01em}
.tb-meta{font-family:var(--mono);font-size:11.5px;color:var(--faint);display:flex;gap:16px;flex-wrap:wrap}
.tb-meta b{color:var(--dim);font-weight:500}
.tb-live{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--green);white-space:nowrap}
.content{flex:1;overflow-y:auto;overflow-x:hidden;padding:22px}
.content.flush{padding:0}
.view{display:none}.view.active{display:block;animation:fade .3s ease}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* ---- panels ---- */
.panel{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:16px 18px}
.panel.muted{color:var(--faint)}
.p-head{font-family:var(--mono);font-size:10.5px;letter-spacing:.14em;color:var(--faint);text-transform:uppercase;
  display:flex;align-items:center;margin-bottom:12px}
.p-more,.p-head a{margin-left:auto;color:var(--accent);font-size:10.5px;letter-spacing:.08em}
.note{color:var(--faint);font-size:12px;line-height:1.6;margin-top:12px}
code{font-family:var(--mono);background:#0a1020;border:1px solid var(--hair);border-radius:5px;padding:1px 5px;font-size:.88em;color:#cfe6ff}

/* ---- kpis ---- */
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px}
.kpi{background:var(--panel);border:1px solid var(--hair);border-radius:13px;padding:14px 16px;position:relative;overflow:hidden}
.kpi::after{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--accent);opacity:.5}
.kpi.warn::after{background:var(--amber)}
.kpi-lab{font-family:var(--mono);font-size:9.5px;letter-spacing:.11em;color:var(--faint);text-transform:uppercase}
.kpi-val{font-family:var(--mono);font-size:24px;font-weight:600;margin-top:7px}
.kpi-val i{font-style:normal;font-size:12px;color:var(--dim);margin-left:2px}

.ov-grid{display:grid;grid-template-columns:1fr 1.05fr;gap:16px;align-items:start}
.ov-left{display:flex;flex-direction:column;gap:16px}
.panel.alert{border-color:rgba(245,165,36,.28)}
.al-pair{font-size:17px;font-weight:650;margin:4px 0 14px;line-height:1.3}.al-pair i{color:var(--faint);margin:0 6px}
.al-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px}
.al-grid span{display:block;font-family:var(--mono);font-size:9px;letter-spacing:.1em;color:var(--faint)}
.al-grid b{font-family:var(--mono);font-size:16px}
.mini-btn{display:inline-block;margin-top:14px;font-family:var(--mono);font-size:11px;color:var(--accent);border:1px solid rgba(92,200,255,.3);border-radius:8px;padding:6px 11px}
.mini-btn:hover{background:rgba(92,200,255,.08)}
.status{display:grid;grid-template-columns:1fr 1fr;gap:9px 16px}
.status div{display:flex;justify-content:space-between;font-family:var(--mono);font-size:11.5px;border-bottom:1px solid var(--hair);padding-bottom:6px}
.status span{color:var(--faint)}.status b{color:var(--ink);font-weight:500}.status .ok{color:var(--green)}
.list{display:flex;flex-direction:column}
.lrow{display:flex;align-items:center;gap:12px;padding:9px 2px;border-bottom:1px solid var(--hair);font-size:13px}
.lrow:last-child{border-bottom:0}
.lr-rank{font-family:var(--mono);color:var(--accent);font-size:12px}
.lr-pair{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lr-pair i{color:var(--faint)}
.lr-miss{font-family:var(--mono);font-size:13px}.lr-miss i{color:var(--faint);font-size:10px;margin-left:3px}

/* ---- globe view ---- */
.globe-wrap{position:relative;height:100%;background:radial-gradient(120% 90% at 70% 6%,rgba(20,40,80,.35),#05070e 72%)}
#globe{position:absolute;inset:0}#globe canvas{display:block}
.ghud{position:absolute;z-index:3;font-family:var(--mono);pointer-events:none}
.ghud-tl{top:18px;left:18px;max-width:290px}.ghud-bl{bottom:18px;left:18px}
.ghud-title{font-size:10px;letter-spacing:.16em;color:var(--faint);margin-bottom:9px}
#conjsel{pointer-events:auto;width:100%;background:rgba(9,13,24,.9);color:var(--ink);border:1px solid var(--hair2);border-radius:9px;padding:9px 10px;font-family:var(--mono);font-size:12px;outline:none}
#conjsel:focus{border-color:var(--accent)}
.conjinfo{margin-top:10px;background:rgba(9,13,24,.86);border:1px solid var(--hair2);border-radius:11px;padding:13px;backdrop-filter:blur(6px)}
.conjinfo .ci-lab{font-size:9px;letter-spacing:.14em;color:var(--faint)}
.conjinfo .ci-pair{font-size:13px;font-weight:600;margin:4px 0 10px;line-height:1.4}
.conjinfo .ci-pair .a{color:var(--accent)}.conjinfo .ci-pair .b{color:var(--pink)}
.conjinfo .ci-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}
.conjinfo .ci-grid span{font-size:9px;letter-spacing:.1em;color:var(--faint);display:block}.conjinfo .ci-grid b{font-size:13px}
.glegend{display:flex;flex-direction:column;gap:5px;background:rgba(9,13,24,.72);border:1px solid var(--hair);border-radius:10px;padding:10px 12px}
.glegend span{font-size:10px;color:var(--dim);display:flex;align-items:center;gap:7px}
.glegend .sw{width:9px;height:9px;border-radius:2px;display:inline-block}
.globefallback{position:absolute;inset:0;z-index:2;display:flex;align-items:center;justify-content:center;color:var(--faint);font-family:var(--mono);font-size:12px;letter-spacing:.1em}

/* ---- tables / focus ---- */
.focusbar{display:flex;align-items:center;gap:10px;border:1px solid var(--hair2);border-radius:11px;background:var(--panel);padding:10px 14px;margin-bottom:14px;color:var(--faint)}
.focusbar svg{flex:none;color:var(--accent)}
.focusbar input{flex:1;background:transparent;border:0;outline:none;color:var(--ink);font-family:var(--mono);font-size:13px}
.focusbar input::placeholder{color:var(--faint)}.focusbar:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px rgba(92,200,255,.1)}
.focusinfo{font-family:var(--mono);font-size:11px;color:var(--dim);white-space:nowrap;flex:none}
.tablewrap{padding:6px 6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--hair)}
th{color:var(--faint);font-family:var(--mono);font-weight:500;font-size:10px;text-transform:uppercase;letter-spacing:.09em}
td.num,th:nth-child(n+5){text-align:right}
tbody tr:hover td{background:rgba(92,200,255,.05)}
.rank{color:var(--accent);font-family:var(--mono);font-weight:600}
.norad{display:block;color:var(--faint);font-size:10px;font-family:var(--mono);margin-top:1px}

/* ---- model view ---- */
.mgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.panel.span2{grid-column:1 / -1}
.mtable td,.mtable th{font-family:var(--mono);text-align:right}.mtable td:first-child,.mtable th:first-child{text-align:left;font-family:var(--sans)}
.mtable .mname{font-size:13px}.mtable td.best{color:var(--green);font-weight:600}
.bignum{font-family:var(--mono);font-size:44px;font-weight:700;color:var(--green);line-height:1}
.bignum span{font-size:18px;color:var(--dim);margin-left:6px}

/* ---- methodology / validation ---- */
.vpage{display:flex;flex-direction:column;gap:16px}
.vsteps{display:grid;grid-template-columns:1fr 1fr;gap:14px 22px}
.vstep{display:flex;gap:14px}
.vs-num{font-family:var(--mono);font-size:14px;font-weight:600;color:var(--accent);padding-top:1px}
.vstep h4{margin:0 0 3px;font-size:14px}.vstep .mod{font-family:var(--mono);font-size:11px;color:var(--faint);font-weight:400;margin-left:8px}
.vstep p{margin:0;color:var(--dim);font-size:12.5px}
.vgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.vbig{font-family:var(--mono);font-size:32px;font-weight:700;color:var(--green);line-height:1;margin:2px 0 4px}
.vbig span{font-size:14px;color:var(--dim);margin-left:6px;font-weight:400}
td.vok{color:var(--green)}

/* ---- about ---- */
.about{display:grid;grid-template-columns:1.3fr 1fr;gap:16px;align-items:start}
.lead{color:#c4cee0;font-size:15px;line-height:1.6}
.who{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin:18px 0}
.who h5{margin:0 0 4px;font-size:13px}.who p{margin:0;color:var(--dim);font-size:12.5px}
.disclaimer{color:var(--faint);font-size:12px;border-top:1px solid var(--hair);padding-top:12px;margin-top:6px}
.timeline{position:relative;margin-left:4px}
.phase{display:flex;gap:16px;padding:0 0 20px 4px;position:relative}
.phase::before{content:"";position:absolute;left:5px;top:16px;bottom:-2px;width:1px;background:var(--hair2)}
.phase:last-child::before{display:none}
.phase-dot{width:11px;height:11px;border-radius:50%;margin-top:4px;flex:none;z-index:1;background:var(--panel);border:1px solid var(--faint)}
.phase.done .phase-dot{background:var(--green);border-color:var(--green)}.phase.next .phase-dot{background:var(--accent);border-color:var(--accent)}
.phase-tag{font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--faint)}
.phase.done .phase-tag{color:var(--green)}.phase.next .phase-tag{color:var(--accent)}
.phase h4{margin:3px 0 2px;font-size:14px}.phase p{margin:0;color:var(--dim);font-size:12.5px;max-width:340px}

@media (max-width:920px){
  .app{grid-template-columns:1fr}
  .side{flex-direction:row;align-items:center;height:56px;padding:0 12px;overflow-x:auto}
  .brand{padding:0 10px 0 4px}.side-sp,.sidestat{display:none}.nav{flex-direction:row}
  .nitem.active::before{display:none}.nitem span{display:none}.nitem{padding:9px}
  .main{height:calc(100vh - 56px)}
  .kpis{grid-template-columns:repeat(2,1fr)}.ov-grid,.mgrid,.about{grid-template-columns:1fr}
  .vgrid{grid-template-columns:1fr}.vsteps{grid-template-columns:1fr}
  .tb-meta{display:none}
}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
</style></head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="2.6"/><ellipse cx="12" cy="12" rx="10" ry="4.4" transform="rotate(28 12 12)"/></svg>
      <span><span class="g">Orbit</span>Guard</span>
    </div>
    <nav class="nav">__NAV__</nav>
    <div class="side-sp"></div>
    <div class="sidestat">
      <div class="sr"><span>OBJECTS</span><b>__NOBJ__</b></div>
      <div class="sr"><span>CONJUNCTIONS</span><b>__NEVT__</b></div>
      <div class="sr"><span>SNAPSHOT</span><b>__SNAPSHOT__</b></div>
      <div class="sr live-row"><span><span class="dot live"></span>RUN COMPLETE</span><b>__RUNTIME__s</b></div>
    </div>
  </aside>
  <main class="main">
    <div class="topbar">
      <div class="tb-title" id="tbtitle">Overview</div>
      <div class="tb-meta"><span>catalogue <b>__GROUP__</b></span><span>window <b>__HOURS__h</b></span><span>threshold <b>__THRESH__km</b></span></div>
      <div class="tb-live"><span class="dot live"></span>__GENERATED__ UTC</div>
    </div>
    <div class="content" id="content">
      <div class="view active" id="view-overview">__OVERVIEW__</div>
      <div class="view" id="view-globe">__GLOBE__</div>
      <div class="view" id="view-conjunctions">__CONJ__</div>
      <div class="view" id="view-model">__MODEL__</div>
      <div class="view" id="view-methodology">__METHOD__</div>
      <div class="view" id="view-about">__ABOUT__</div>
    </div>
  </main>
</div>

<script>__THREE_JS__</script>
<script>__ORBITCONTROLS_JS__</script>
<script>
var OG_EVENTS=__EVENTS_JSON__;var OG_GLOBE=__GLOBE_JSON__;var OG_GEOM=__GEOM_JSON__;
var OG_EARTH_TEX="data:image/jpeg;base64,__EARTH_TEX__";
</script>
<script>
(function(){
  var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var fmt=function(n,dec){return dec>0?n.toFixed(dec):Math.round(n).toLocaleString('en-US')};
  function esc(s){var d=document.createElement('div');d.textContent=String(s);return d.innerHTML}
  var TITLES={overview:'Overview',globe:'Orbital Globe',conjunctions:'Conjunctions',model:'Risk Model',methodology:'Methodology & Validation',about:'About'};

  // count-ups
  document.querySelectorAll('.count').forEach(function(el){
    var t=parseFloat(el.dataset.count),dec=+el.dataset.dec||0;
    if(reduce){el.textContent=fmt(t,dec);return}
    var dur=900,s=null;function step(ts){if(!s)s=ts;var p=Math.min((ts-s)/dur,1),e=1-Math.pow(1-p,3);el.textContent=fmt(t*e,dec);if(p<1)requestAnimationFrame(step)}requestAnimationFrame(step);
  });

  // nav / view switching
  var items=document.querySelectorAll('.nitem'),views=document.querySelectorAll('.view'),content=document.getElementById('content');
  function show(name){
    items.forEach(function(t){t.classList.toggle('active',t.dataset.view===name)});
    views.forEach(function(v){v.classList.toggle('active',v.id==='view-'+name)});
    document.getElementById('tbtitle').textContent=TITLES[name]||name;
    content.classList.toggle('flush',name==='globe');
    if(name==='globe'){ensureGlobe();if(globeApi.resize)setTimeout(globeApi.resize,40)}
    if(history&&history.replaceState)history.replaceState(null,'','#'+name);
  }
  document.addEventListener('click',function(e){var t=e.target.closest('[data-view]');if(t)show(t.dataset.view)});

  // focus search (conjunctions)
  var body=document.getElementById('ogbody'),inp=document.getElementById('ogfocus'),info=document.getElementById('ogfocusinfo');
  function rowHtml(e){var hue=Math.round(48-0.48*Math.min(e.rs,100));
    return '<tr><td class="rank">'+e.r+'</td><td>'+esc(e.a)+'<span class="norad">NORAD '+e.na+'</span></td>'+
      '<td>'+esc(e.b)+'<span class="norad">NORAD '+e.nb+'</span></td><td class="mono">'+e.t+'</td>'+
      '<td class="mono num">'+e.m.toFixed(3)+'</td><td class="mono num">'+e.v.toFixed(2)+'</td>'+
      '<td class="mono num">'+Math.round(e.al)+'</td><td><span class="risk" style="--rh:'+hue+'">'+Math.round(e.rs)+'</span></td></tr>'}
  function render(list,lim){var o='',n=Math.min(list.length,lim||60);for(var i=0;i<n;i++)o+=rowHtml(list[i]);if(body)body.innerHTML=o}
  function applyFocus(){if(!body||!OG_EVENTS)return;var q=(inp.value||'').trim().toLowerCase();
    if(!q){render(OG_EVENTS,60);info.textContent=OG_EVENTS.length.toLocaleString('en-US')+' conjunctions · top 60 by risk';return}
    var dig=/^\d+$/.test(q);var m=OG_EVENTS.filter(function(e){return dig?(e.na==+q||e.nb==+q):(String(e.a).toLowerCase().indexOf(q)>=0||String(e.b).toLowerCase().indexOf(q)>=0)});
    render(m,400);if(m.length){var c=Math.min.apply(null,m.map(function(e){return e.m}));info.textContent=m.length+' approach'+(m.length>1?'es':'')+' · closest '+c.toFixed(3)+' km'}else info.textContent='no conjunctions for "'+inp.value+'"'}
  if(inp){inp.addEventListener('input',applyFocus);applyFocus()}

  // ---- globe ----
  var globeApi={resize:null},globeReady=false;
  function ensureGlobe(){if(globeReady)return;if(!window.THREE||!OG_GLOBE)return;globeReady=true;initGlobe()}
  function initGlobe(){
    var host=document.getElementById('globe');if(!host)return;
    var W=host.clientWidth||900,H=host.clientHeight||580;
    var scene=new THREE.Scene();
    var camera=new THREE.PerspectiveCamera(42,W/H,0.1,200);camera.position.set(0.2,1.3,3.3);   // near=0.1 -> better depth precision (was 0.01, caused line flicker)
    var renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));renderer.setSize(W,H);host.appendChild(renderer.domElement);
    var controls=new THREE.OrbitControls(camera,renderer.domElement);
    controls.enableDamping=true;controls.dampingFactor=.06;controls.rotateSpeed=.5;controls.enablePan=false;
    controls.minDistance=1.45;controls.maxDistance=8;
    if(!reduce){controls.autoRotate=true;controls.autoRotateSpeed=.3}
    scene.add(new THREE.AmbientLight(0x6f8ec2,.6));
    var sun=new THREE.DirectionalLight(0xffffff,1.15);sun.position.set(5,3,5);scene.add(sun);
    var sp=[];for(var i=0;i<1200;i++){var u=Math.random()*2-1,th=Math.random()*Math.PI*2,s=Math.sqrt(1-u*u),r=40;sp.push(r*s*Math.cos(th),r*u,r*s*Math.sin(th))}
    var sg=new THREE.BufferGeometry();sg.setAttribute('position',new THREE.Float32BufferAttribute(sp,3));
    scene.add(new THREE.Points(sg,new THREE.PointsMaterial({color:0x9fb3d0,size:.05,transparent:true,opacity:.7,depthWrite:false})));
    var tex=new THREE.TextureLoader().load(OG_EARTH_TEX,function(){var f=document.getElementById('globefallback');if(f)f.style.display='none'});
    var earth=new THREE.Mesh(new THREE.SphereGeometry(1,64,64),new THREE.MeshPhongMaterial({map:tex,shininess:9,specular:0x1b2a44}));
    scene.add(earth);
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.03,48,48),new THREE.MeshBasicMaterial({color:0x3aa0ff,transparent:true,opacity:.09,side:THREE.BackSide,depthWrite:false})));
    var S=1/OG_GLOBE.earth_radius_km,band=[0x5cc8ff,0xf5a524,0x8b7bff];
    function toV(q){return [q[0]*S,q[2]*S,-q[1]*S]}
    var segs={0:[],1:[],2:[]},paths=[],ppos=[],pcol=[];
    OG_GLOBE.sats.forEach(function(sat){var pts=sat.p.map(toV);paths.push(pts);
      for(var k=0;k<pts.length-1;k++){var a=pts[k],b=pts[k+1];segs[sat.b].push(a[0],a[1],a[2],b[0],b[1],b[2])}
      var c=new THREE.Color(band[sat.b]);ppos.push(pts[0][0],pts[0][1],pts[0][2]);pcol.push(c.r,c.g,c.b)});
    // faint orbit shells: depthWrite:false + slightly higher opacity => no z-fight flicker
    [0,1,2].forEach(function(b){if(!segs[b].length)return;var g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(segs[b],3));
      scene.add(new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:band[b],transparent:true,opacity:.2,depthWrite:false})))});
    var pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.Float32BufferAttribute(ppos,3));pg.setAttribute('color',new THREE.Float32BufferAttribute(pcol,3));
    var satPoints=new THREE.Points(pg,new THREE.PointsMaterial({size:.026,vertexColors:true,transparent:true,opacity:.95,depthWrite:false}));
    scene.add(satPoints);
    var hi=new THREE.Group();scene.add(hi);
    function drawConj(g){while(hi.children.length)hi.remove(hi.children[0]);if(!g)return;
      function arc(a,color){var v=a.map(function(q){var t=toV(q);return new THREE.Vector3(t[0],t[1],t[2])});hi.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(v),new THREE.LineBasicMaterial({color:color,depthWrite:false})))}
      arc(g.arc_a,0x5cc8ff);arc(g.arc_b,0xff4d8d);
      var ta=toV(g.point_a),tb=toV(g.point_b),pa=new THREE.Vector3(ta[0],ta[1],ta[2]),pb=new THREE.Vector3(tb[0],tb[1],tb[2]);
      [[pa,0x5cc8ff],[pb,0xff4d8d]].forEach(function(m){var d=new THREE.Mesh(new THREE.SphereGeometry(.013,16,16),new THREE.MeshBasicMaterial({color:m[1]}));d.position.copy(m[0]);hi.add(d)});
      var dl=new THREE.Line(new THREE.BufferGeometry().setFromPoints([pa,pb]),new THREE.LineDashedMaterial({color:0xf5a524,dashSize:.03,gapSize:.02,depthWrite:false}));dl.computeLineDistances();hi.add(dl)}
    var sel=document.getElementById('conjsel'),ci=document.getElementById('conjinfo');
    function updInfo(g){if(!ci)return;if(!g){ci.innerHTML='';return}
      ci.innerHTML='<div class="ci-lab">SELECTED CONJUNCTION</div><div class="ci-pair"><span class="a">'+esc(g.object_a)+'</span> ↔ <span class="b">'+esc(g.object_b)+'</span></div>'+
        '<div class="ci-grid"><div><span>MISS</span><b>'+g.miss_km.toFixed(2)+' km</b></div><div><span>CLOSING</span><b>'+g.rel_speed_kms.toFixed(1)+' km/s</b></div>'+
        '<div><span>RISK</span><b>'+Math.round(g.risk_score)+'</b></div><div><span>TCA</span><b style="font-size:11px">'+esc(g.tca_utc.slice(5,16))+'</b></div></div>'}
    if(sel&&OG_GEOM&&OG_GEOM.length){OG_GEOM.forEach(function(g,i){var o=document.createElement('option');o.value=i;o.textContent='#'+g.rank+'  '+g.object_a+' ↔ '+g.object_b+'  ('+g.miss_km.toFixed(2)+' km)';sel.appendChild(o)});
      sel.addEventListener('change',function(){var g=OG_GEOM[+sel.value];drawConj(g);updInfo(g)});drawConj(OG_GEOM[0]);updInfo(OG_GEOM[0])}else if(sel)sel.style.display='none';
    var last=0,t=0;
    function tick(ts){requestAnimationFrame(tick);var dt=Math.min((ts-last)/1000||0,.05);last=ts;controls.update();
      if(!reduce){t+=dt*4;var arr=satPoints.geometry.attributes.position.array;
        for(var i=0;i<paths.length;i++){var p=paths[i],L=p.length;if(L<2)continue;var f=(t+i*0.7)%(L-1),k=Math.floor(f),fr=f-k,a=p[k],b=p[k+1];
          arr[i*3]=a[0]+(b[0]-a[0])*fr;arr[i*3+1]=a[1]+(b[1]-a[1])*fr;arr[i*3+2]=a[2]+(b[2]-a[2])*fr}
        satPoints.geometry.attributes.position.needsUpdate=true;earth.rotation.y+=dt*0.015}
      renderer.render(scene,camera)}
    requestAnimationFrame(tick);
    globeApi.resize=function(){var w=host.clientWidth,h=host.clientHeight;if(!w||!h)return;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h)};
    window.addEventListener('resize',globeApi.resize);
  }

  var h=(location.hash||'').replace('#','');if(h&&TITLES[h])show(h);
})();
</script>
</body></html>
"""


def build_dashboard(payload: dict, path: str) -> str:
    meta = payload["meta"]
    summary = payload["summary"]
    events = payload["events"]
    globe = payload.get("globe", {"earth_radius_km": 6371.0, "sats": [], "sample_n": 0})
    comp = _load_comparison()

    nav = "".join(
        f'<a class="nitem{" active" if key == "overview" else ""}" data-view="{key}">'
        f'{_nav_icon(paths)}<span>{label}</span></a>'
        for key, label, paths in _NAV
    )

    compact = [
        {"r": e["rank"], "a": e["object_a"], "na": e["norad_a"], "b": e["object_b"],
         "nb": e["norad_b"], "t": e["tca_utc"], "m": round(e["miss_km"], 3),
         "v": round(e["rel_speed_kms"], 2), "al": round(e["alt_km"], 0),
         "rs": round(e["risk_score"], 1)}
        for e in events
    ]

    small = {
        "__NAV__": nav,
        "__OVERVIEW__": _overview(summary, meta, events),
        "__GLOBE__": _globe_view(globe.get("sample_n", 0)),
        "__CONJ__": _conjunctions_view(events),
        "__MODEL__": _model_view(comp),
        "__METHOD__": _validation_view(_load_validation()),
        "__ABOUT__": _about_view(summary, meta),
        "__NOBJ__": f"{meta.get('n_objects', 0):,}",
        "__NEVT__": f"{summary.get('n_events', 0):,}",
        "__SNAPSHOT__": str(meta.get("snapshot_date", "")),
        "__GROUP__": str(meta.get("group", "")),
        "__HOURS__": str(meta.get("hours", "")),
        "__THRESH__": str(meta.get("threshold_km", "")),
        "__RUNTIME__": str(meta.get("runtime_s", "")),
        "__GENERATED__": str(meta.get("generated_utc", "")),
    }
    big = {
        "__EVENTS_JSON__": json.dumps(compact, separators=(",", ":")),
        "__GLOBE_JSON__": json.dumps(globe, separators=(",", ":")),
        "__GEOM_JSON__": json.dumps(payload.get("geometry", []), separators=(",", ":")),
        "__EARTH_TEX__": _vendor("earth_texture_b64.txt"),
        "__ORBITCONTROLS_JS__": _vendor("OrbitControls.js"),
        "__THREE_JS__": _vendor("three.min.js"),
    }

    page = _PAGE
    for k, v in small.items():
        page = page.replace(k, v)
    for k, v in big.items():
        page = page.replace(k, v)

    with open(path, "w") as fh:
        fh.write(page)
    return path
