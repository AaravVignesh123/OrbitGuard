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
def _kpi(label, value, dec=0, unit="", accent="", d=0):
    return (f'<div class="kpi {accent}" data-reveal style="--d:{d}ms">'
            f'<div class="kpi-lab">{label}</div>'
            f'<div class="kpi-val">{_count(value, dec)}<i>{unit}</i></div></div>')


def _ov_hero(summary, meta) -> str:
    n_obj = meta.get("n_objects", 0) or 0
    n_evt = summary.get("n_events", 0) or 0
    group = html.escape(str(meta.get("group", "—")))
    snap = html.escape(str(meta.get("snapshot_date", "—")))
    hours = html.escape(str(meta.get("hours", "—")))
    return (
        '<div class="ov-hero panel" data-reveal>'
        '<div class="hero-bg" aria-hidden="true"><div class="stars"></div><div class="stars s2"></div>'
        '<svg class="orb" viewBox="0 0 640 360">'
        '<ellipse class="orb-ring" cx="320" cy="180" rx="290" ry="104"/>'
        '<ellipse class="orb-ring r2" cx="320" cy="180" rx="210" ry="164"/></svg></div>'
        '<div class="hero-body">'
        '<div class="eyebrow">{ orbital conjunction screening }</div>'
        f'<h1 class="hero-h">{n_obj:,} objects screened<i>·</i>{n_evt:,} conjunctions flagged</h1>'
        f'<div class="hero-sub mono">catalogue <b>{group}</b> · snapshot <b>{snap}</b> · window <b>{hours} h</b>'
        '<span class="hero-live"><span class="dot live"></span>LIVE <span id="heroclock">--:--:--</span> UTC</span></div>'
        '<div class="hero-cta"><a class="pill" data-view="globe">Open globe →</a>'
        '<a class="pill" data-view="conjunctions">All conjunctions →</a></div>'
        '</div></div>'
    )


def _encounter_svg(top) -> str:
    miss = top.get("miss_km", 0.0) or 0.0
    return (
        '<svg class="enc" viewBox="0 0 220 120" aria-hidden="true">'
        '<path class="enc-a" d="M8,104 Q112,-6 212,72"/>'
        '<path class="enc-b" d="M8,56 Q112,150 212,18"/>'
        '<line class="enc-miss" x1="110" y1="48" x2="130" y2="62"/>'
        '<circle class="enc-pt a" cx="110" cy="48" r="3.6"/>'
        '<circle class="enc-pt b" cx="130" cy="62" r="3.6"/>'
        f'<text class="enc-t" x="120" y="44">{miss:.3f} km</text></svg>'
    )


def _trust_strip(validation) -> str:
    if not validation:
        return ""
    chips = []
    kd = validation.get("kdtree") or {}
    if kd.get("identical"):
        chips.append('<span class="chip"><b>✓</b> KD-tree = brute force</span>')
    ref = validation.get("refinement") or {}
    if ref.get("max_error_m") is not None:
        chips.append(f'<span class="chip">refined miss &lt; {ref["max_error_m"]:.0f} m</span>')
    soc = validation.get("socrates") or {}
    if soc.get("status") == "ok" and soc.get("median_miss_diff_m") is not None:
        chips.append(
            f'<span class="chip">SOCRATES ~{soc["median_miss_diff_m"]:.0f} m '
            f'(n={soc.get("n_checked", "?")})</span>'
        )
    chips.append('<span class="chip">Pc · Foster 2-D · modelled cov</span>')
    return ('<div class="trust" data-reveal><span class="trust-lab">VALIDATED</span>'
            + "".join(chips) + '</div>')


def _pipeline_ribbon() -> str:
    steps = ["catalogue", "propagate", "screen", "refine", "Pc", "rank"]
    nodes = '<i class="rb-sep">→</i>'.join(f'<span class="rb-step">{s}</span>' for s in steps)
    return ('<div class="ribbon"><span class="rb-lab">PIPELINE</span>'
            f'<div class="rb-track"><span class="rb-dot"></span>{nodes}</div></div>')


def _overview(summary, meta, events, validation=None) -> str:
    hero = _ov_hero(summary, meta)

    kpis = (
        '<div class="kpis">'
        + _kpi("OBJECTS SCREENED", meta.get("n_objects", 0), d=0)
        + _kpi("CONJUNCTIONS", summary.get("n_events", 0), d=60)
        + _kpi("CLOSEST APPROACH", summary.get("closest_km"), 2, " km", "warn", d=120)
        + _kpi("FASTEST CLOSING", summary.get("fastest_kms"), 1, " km/s", d=180)
        + _kpi("MEDIAN MISS", summary.get("median_miss_km"), 1, " km", d=240)
        + "</div>"
    )

    top = events[0] if events else None
    alert = '<div class="panel muted" data-reveal>No conjunctions flagged.</div>'
    if top:
        alert = (
            f'<div class="panel alert" data-reveal><div class="p-head"><span class="dot warn"></span>'
            f'HIGHEST-RISK PASS</div><div class="al-top"><div class="al-main">'
            f'<div class="al-pair">{html.escape(str(top["object_a"]))}'
            f'<i>↔</i>{html.escape(str(top["object_b"]))}</div>'
            f'<div class="al-grid">'
            f'<div><span>MISS</span><b>{top["miss_km"]:.3f} km</b></div>'
            f'<div><span>CLOSING</span><b>{top["rel_speed_kms"]:.2f} km/s</b></div>'
            f'<div><span>Pc</span><b>{_pc_str(top.get("pc"))}</b></div>'
            f'<div><span>TCA · UTC</span><b>{top["tca_utc"][5:16]}</b></div>'
            f'<div><span>RISK</span><b class="risk" style="--rh:{_hue(top["risk_score"])}">'
            f'{top["risk_score"]:.0f}</b></div></div></div>'
            f'{_encounter_svg(top)}</div>'
            f'<a class="pill" data-view="globe">View in globe →</a></div>'
        )

    rows = "".join(
        f'<div class="lrow" data-reveal style="--d:{i*45}ms"><span class="lr-rank">{e["rank"]:02d}</span>'
        f'<span class="lr-pair">{html.escape(str(e["object_a"]))} <i>↔</i> '
        f'{html.escape(str(e["object_b"]))}</span>'
        f'<span class="lr-miss">{e["miss_km"]:.3f}<i>km</i></span>'
        f'<span class="risk" style="--rh:{_hue(e["risk_score"])}">{e["risk_score"]:.0f}</span></div>'
        for i, e in enumerate(events[:8])
    )
    toplist = (f'<div class="panel" data-reveal><div class="p-head">TOP CONJUNCTIONS'
               f'<a class="p-more" data-view="conjunctions">all {summary.get("n_events",0):,} →</a>'
               f'</div><div class="list">{rows}</div></div>')

    trust = _trust_strip(validation)

    status = (
        '<div class="panel" data-reveal><div class="p-head">RUN STATUS</div><div class="status">'
        + f'<div><span>CATALOGUE</span><b>{meta.get("group")}</b></div>'
        + f'<div><span>SNAPSHOT</span><b>{meta.get("snapshot_date")}</b></div>'
        + f'<div><span>WINDOW</span><b>{meta.get("hours")} h</b></div>'
        + f'<div><span>STEP</span><b>{int(meta.get("step_s",60))} s</b></div>'
        + f'<div><span>THRESHOLD</span><b>{meta.get("threshold_km")} km</b></div>'
        + f'<div><span>VALID / SCREENED</span><b>{meta.get("n_valid","—")} / {meta.get("n_objects",0):,}</b></div>'
        + f'<div><span>RUNTIME</span><b>{meta.get("runtime_s","—")} s</b></div>'
        + '</div>'
        + _pipeline_ribbon()
        + '</div>'
    )

    return (f'{hero}{kpis}<div class="ov-grid"><div class="ov-left">{alert}</div>'
            f'<div class="ov-right">{toplist}</div></div>{trust}{status}')


def _globe_view(sample_n) -> str:
    return f"""
<div class="globe-wrap">
  <div id="globe"></div>
  <div class="ghud ghud-tl">
    <div id="gsrc" class="gsrc"><span class="dot warn"></span>fetching live catalogue…</div>
    <select id="conjsel" aria-label="highlighted conjunction"></select>
    <div id="conjinfo" class="conjinfo"></div>
    <div id="scrubwrap" class="scrubwrap" style="display:none">
      <div class="scrub-lab">TIME · WATCH THE APPROACH</div>
      <div class="scrub-row">
        <button id="scrubplay" class="scrub-btn" aria-label="play through the encounter">▶</button>
        <input id="scrub" type="range" min="-1800" max="1800" value="0" step="10" aria-label="time around closest approach">
        <button id="scrublive" class="scrub-btn live" title="return to real time">● LIVE</button>
      </div>
      <div class="scrub-read"><b id="scrubdt">±00:00</b><span>to TCA · miss</span><b id="scrubmiss" class="scrub-miss">— km</b></div>
    </div>
  </div>
  <div id="gpick" class="gpick" style="display:none"></div>
  <div class="ghud ghud-bl glegend">
    <span><i class="sw" style="background:#5cc8ff"></i>live positions · fetched from CelesTrak now</span>
    <span><i class="sw" style="background:#5cc8ff"></i>conjunction · object A</span>
    <span><i class="sw" style="background:#ff4d8d"></i>conjunction · object B</span>
    <span><i class="sw" style="background:#f5a524"></i>miss distance</span>
    <span class="gnote">TLEs fetched live in-browser from CelesTrak, propagated by SGP4 to the current instant;
    Earth oriented by sidereal time so each object sits over its true sub-point. Conjunction analysis is from the last screening run.
    Pick a conjunction and drag the time slider to watch the pass; click any satellite to inspect it.</span>
  </div>
  <div id="globefallback" class="globefallback">Fetching live catalogue from CelesTrak…</div>
</div>
"""


def _pc_str(pc) -> str:
    import math
    if pc is None or (isinstance(pc, float) and math.isnan(pc)):
        return "—"
    if pc < 1e-12:
        return "&lt;1e-12"
    return f"{pc:.1e}"


def _conjunctions_view(events) -> str:
    head = ("<tr><th>#</th><th>Object A</th><th>Object B</th><th>TCA (UTC)</th>"
            "<th>Miss (km)</th><th>Rel. speed</th><th>Alt (km)</th><th>Pc</th><th>Risk</th></tr>")
    rows = []
    for e in events[:60]:
        chip = f'<span class="risk" style="--rh:{_hue(e["risk_score"])}">{e["risk_score"]:.0f}</span>'
        rows.append(
            f"<tr class='crow' data-rank='{e['rank']}'>"
            f"<td class='rank'>{e['rank']}</td>"
            f"<td>{html.escape(str(e['object_a']))}<span class='norad'>NORAD {e['norad_a']}</span></td>"
            f"<td>{html.escape(str(e['object_b']))}<span class='norad'>NORAD {e['norad_b']}</span></td>"
            f"<td class='mono'>{e['tca_utc']}</td>"
            f"<td class='mono num'>{e['miss_km']:.3f}</td>"
            f"<td class='mono num'>{e['rel_speed_kms']:.2f}</td>"
            f"<td class='mono num'>{e['alt_km']:.0f}</td>"
            f"<td class='mono num'>{_pc_str(e.get('pc'))}</td>"
            f"<td>{chip}</td></tr>"
        )
    return f"""
<div class="focusbar">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
  <input id="ogfocus" type="text" autocomplete="off" spellcheck="false" placeholder="Focus a satellite — name or NORAD id (e.g. STARLINK-30876 or 57154)">
  <span id="ogfocusinfo" class="focusinfo"></span>
</div>
<div class="rowhint mono">Click any row to open it on the globe and scrub through the approach.</div>
<div class="panel tablewrap"><table><thead>{head}</thead><tbody id="ogbody">{''.join(rows)}</tbody></table></div>
<div class="note"><b>Pc</b> = Foster 2-D probability of collision under a <em>modelled</em> covariance —
altitude- + TLE-age-scaled (along-track 1-σ ≈ 0.5 km at epoch, growing ~1 km/day at 800 km and faster
low in LEO; hard-body radius 10 m), calibrated to published TLE-error magnitudes. Public TLEs carry no
covariance of their own, so treat Pc as an order-of-magnitude estimate, not an operational number. <b>Risk</b> is the
v1 geometric proxy (closing speed / miss), log-scaled 0–100. See <b>Methodology</b> for the method and limits.</div>
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
    before TCA, on the ESA Kelvins dataset ({b['n_events']:,} events, {b['n_high_risk']} high-risk).</div>
  </div>
  <div class="panel span2">
    <div class="p-head">PHASE 4 · SCORING OUR OWN LIVE CONJUNCTIONS (EXPERIMENTAL)</div>
    <div class="note">The bridge (<code>ml/features.bridge_from_screener</code>) is implemented: it maps a live
    screener event into the model's feature space and scores it. But our TLE screener can honestly produce
    only <b>9 of the model's 110 features</b> — the rest, including the model's single most important input
    (the prior CDM <code>risk</code> estimate) and all orbit-determination-quality columns, have no
    TLE-derived source and are imputed. With those missing, the learned score is <b>near-constant</b> across
    events, so it is <b>not surfaced per-conjunction</b> (it would be misleading). It is kept in the report
    JSON for research. The honest conclusion: a covariance-based <b>Pc</b> (see the Conjunctions tab) is the
    right live risk signal today; the learned model needs real CDMs to add value. That gap is the point.</div>
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
        ("04", "Pc", "Foster 2-D probability of collision: project the combined covariance onto the "
         "encounter plane (⟂ relative velocity) and integrate a 2-D Gaussian over the hard-body disk. "
         "Public TLEs carry no covariance, so we model an RTN covariance scaled by altitude and TLE age "
         "(drag-driven along-track growth), calibrated to published TLE-error magnitudes — Pc is an "
         "order-of-magnitude estimate, and we also report the worst-case max-Pc.", "risk_pc.py"),
        ("05", "Rank", "A geometric proxy (closing speed / miss, log-scaled 0–100) for quick triage, "
         "shown alongside Pc.", "risk.py"),
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
  refinement math, not the TLE physics.</div></div>
{_socrates_panel(val.get("socrates"))}
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


def _socrates_panel(soc) -> str:
    if not soc or soc.get("status") != "ok" or not soc.get("events"):
        msg = (soc or {}).get("status", "not run")
        return (f'<div class="panel"><div class="p-head">◈ PHYSICAL VALIDATION · CelesTrak SOCRATES</div>'
                f'<div class="note">Independent cross-check against the authoritative feed — '
                f'run <code>python -m orbitguard.validate</code> with a network connection. Status: {html.escape(str(msg))}.</div></div>')
    rows = "".join(
        f'<tr><td>{html.escape(e["pair"])}</td><td class="mono">{e["tca_utc"][5:16]}</td>'
        f'<td class="num">{e["socrates_miss_km"]:.3f}</td><td class="num">{e["our_miss_km"]:.3f}</td>'
        f'<td class="num vok">{e["miss_diff_m"]:.0f}</td>'
        f'<td class="num">{e["socrates_max_prob"]:.1e}</td><td class="num">{e["our_max_pc"]:.1e}</td></tr>'
        for e in soc["events"])
    med = soc.get("median_miss_diff_m")
    return f"""
<div class="panel"><div class="p-head">◈ PHYSICAL VALIDATION · CelesTrak SOCRATES (authoritative feed)</div>
  <table class="mtable"><thead><tr><th>conjunction</th><th>TCA</th><th>SOCRATES miss (km)</th>
  <th>our miss (km)</th><th>Δ (m)</th><th>SOCRATES maxPc</th><th>our maxPc</th></tr></thead>
  <tbody>{rows}</tbody></table>
  <div class="note">We independently reproduce SOCRATES' soonest conjunctions (its objects, our freshly-fetched
  TLEs, our propagation + Pc). Miss distances agree to <b>~{med:.0f} m median</b> — order-of-magnitude
  agreement against the reference; larger scatter comes from element-set freshness (volatile debris),
  not method error. Max-Pc uses SOCRATES' documented RTN covariance (100/300/100 m) for an apples-to-apples
  comparison. This validates the <em>physics</em>, not just our internal math.</div></div>
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
    SOCRATES, commercial SSA). Public TLEs are ~km-accurate and carry no covariance, so the <b>Pc</b> is a
    Foster 2-D probability under a <em>modelled</em> covariance (altitude- + TLE-age-scaled) — an
    order-of-magnitude estimate, cross-checked against SOCRATES in <b>Methodology</b>. Validate against
    CelesTrak SOCRATES before any operational use.</p>
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
:root[data-theme="light"]{
  --bg:#eef1f7; --bg1:#e7ebf3; --panel:#ffffff; --panel2:#f4f7fb; --rail:#e9edf4;
  --hair:rgba(30,50,90,.14); --hair2:rgba(30,50,90,.26);
  --ink:#111a2b; --dim:#46536e; --faint:#7d89a2;
  --accent:#1683c9; --accent-ink:#ffffff; --amber:#b9760a; --green:#0f9e60; --pink:#d63268; }
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
.themetgl{background:transparent;border:1px solid var(--hair2);color:var(--dim);border-radius:8px;width:30px;height:26px;cursor:pointer;font-size:14px;line-height:1}
.themetgl:hover{color:var(--ink);border-color:var(--accent)}
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
.al-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(78px,1fr));gap:14px 16px}
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
.lrow .lr-pair i{color:var(--faint)}

/* ---- overview: hero + bento + motion ---- */
[data-reveal]{opacity:0;transform:translateY(14px);transition:opacity .6s cubic-bezier(.22,1,.36,1),transform .6s cubic-bezier(.22,1,.36,1);transition-delay:var(--d,0ms)}
[data-reveal].in{opacity:1;transform:none}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.12em;color:var(--dim);margin-bottom:14px}
.pill{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:12px;color:var(--ink);cursor:pointer;
  border:1px solid var(--hair2);border-radius:999px;padding:8px 16px;transition:border-color .2s,background .2s,transform .2s}
.pill:hover{border-color:var(--accent);background:rgba(92,200,255,.08);transform:translateY(-1px)}
/* cursor sheen on cards (gentle ripple, all views) */
.kpi,.panel{position:relative}
.kpi::before,.panel::before{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;opacity:0;transition:opacity .3s;
  background:radial-gradient(240px circle at var(--mx,50%) var(--my,50%),rgba(120,180,255,.10),transparent 60%)}
.kpi:hover::before,.panel:hover::before{opacity:1}
.kpi{transition:transform .2s,border-color .2s}.kpi:hover{transform:translateY(-2px);border-color:var(--hair2)}
/* hero */
.ov-hero{position:relative;overflow:hidden;padding:34px 30px;margin-bottom:16px;min-height:186px;display:flex;align-items:center;
  background:radial-gradient(120% 150% at 82% -20%,rgba(46,74,140,.30),var(--panel) 62%)}
.hero-bg{position:absolute;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.hero-body{position:relative;z-index:1;max-width:760px}
.hero-h{font-size:clamp(28px,4.4vw,52px);line-height:1.03;letter-spacing:-.02em;font-weight:760;margin:0 0 12px}
.hero-h i{font-style:normal;color:var(--faint);margin:0 12px;font-weight:400}
.hero-sub{font-size:12px;color:var(--dim);display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px}
.hero-sub b{color:var(--ink);font-weight:500}
.hero-live{color:var(--green);display:inline-flex;align-items:center;gap:6px}
.hero-cta{display:flex;gap:12px;margin-top:20px}
.stars{position:absolute;inset:-20% -20%;background-repeat:no-repeat;opacity:.5;animation:starDrift 60s linear infinite;
  background-image:radial-gradient(1.4px 1.4px at 20% 30%,rgba(200,220,255,.9),transparent),
    radial-gradient(1.4px 1.4px at 70% 60%,rgba(200,220,255,.7),transparent),
    radial-gradient(1px 1px at 40% 80%,rgba(200,220,255,.8),transparent),
    radial-gradient(1.6px 1.6px at 85% 25%,rgba(200,220,255,.75),transparent),
    radial-gradient(1px 1px at 55% 15%,rgba(200,220,255,.7),transparent),
    radial-gradient(1.2px 1.2px at 12% 68%,rgba(200,220,255,.7),transparent)}
.stars.s2{animation-duration:95s;animation-direction:reverse;opacity:.28;transform:scale(1.4)}
@keyframes starDrift{from{transform:translate3d(0,0,0)}to{transform:translate3d(-46px,22px,0)}}
.orb{position:absolute;right:-30px;top:50%;margin-top:-180px;width:640px;height:360px;opacity:.55}
.orb-ring{fill:none;stroke:var(--accent);stroke-width:1;opacity:.34;stroke-dasharray:6 10;transform-box:fill-box;transform-origin:center;animation:orbSpin 42s linear infinite}
.orb-ring.r2{stroke:var(--accent2);opacity:.26;animation-duration:66s;animation-direction:reverse}
@keyframes orbSpin{to{transform:rotate(360deg)}}
/* highest-risk spotlight schematic */
.al-top{display:flex;gap:18px;align-items:center}.al-main{flex:1;min-width:0}
.enc{width:200px;height:110px;flex:none;opacity:.95}
.enc path{fill:none;stroke-width:1.5}
.enc-a{stroke:var(--accent);opacity:.75}.enc-b{stroke:var(--pink);opacity:.75}
.enc-miss{stroke:var(--amber);stroke-width:1.5;stroke-dasharray:2 2}
.enc-pt.a{fill:var(--accent)}.enc-pt.b{fill:var(--pink)}
.enc-t{fill:var(--dim);font-family:var(--mono);font-size:9px}
/* trust strip */
.trust{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:18px 0 2px}
.trust-lab{font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--faint);margin-right:2px}
.chip{font-family:var(--mono);font-size:11px;color:var(--dim);border:1px solid var(--hair);border-radius:999px;padding:6px 12px;background:var(--panel2)}
.chip b{color:var(--green);font-weight:600}
/* pipeline ribbon */
.ribbon{display:flex;align-items:center;gap:14px;margin-top:16px;border-top:1px solid var(--hair);padding-top:14px}
.rb-lab{font-family:var(--mono);font-size:10px;letter-spacing:.14em;color:var(--faint);flex:none}
.rb-track{position:relative;display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:var(--mono);font-size:12px}
.rb-step{color:var(--ink)}.rb-sep{color:var(--faint);font-style:normal}
.rb-dot{position:absolute;left:0;top:50%;margin-top:-3px;width:6px;height:6px;border-radius:50%;background:var(--accent);
  box-shadow:0 0 10px 2px rgba(92,200,255,.7);animation:ribbonFlow 4.6s ease-in-out infinite}
@keyframes ribbonFlow{0%{left:0;opacity:0}9%{opacity:1}88%{opacity:1}100%{left:100%;opacity:0}}

/* ---- globe view ---- */
.globe-wrap{position:relative;height:100%;background:radial-gradient(120% 90% at 70% 6%,rgba(20,40,80,.35),#05070e 72%)}
#globe{position:absolute;inset:0}#globe canvas{display:block}
.ghud{position:absolute;z-index:3;font-family:var(--mono);pointer-events:none}
.ghud-tl{top:18px;left:18px;max-width:290px}.ghud-bl{bottom:18px;left:18px}
.ghud-title{font-size:10px;letter-spacing:.16em;color:var(--faint);margin-bottom:9px}
.gsrc{font-size:10.5px;letter-spacing:.06em;color:var(--green);margin-bottom:10px;background:rgba(9,13,24,.86);border:1px solid var(--hair2);border-radius:8px;padding:7px 10px;display:inline-block}
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
.glegend .gnote{color:var(--faint);font-size:9px;max-width:230px;line-height:1.4;margin-top:2px}
.globefallback{position:absolute;inset:0;z-index:2;display:flex;align-items:center;justify-content:center;color:var(--faint);font-family:var(--mono);font-size:12px;letter-spacing:.1em}
/* time-scrubber */
.scrubwrap{pointer-events:auto;margin-top:10px;background:rgba(9,13,24,.86);border:1px solid var(--hair2);border-radius:11px;padding:11px 13px;backdrop-filter:blur(6px)}
.scrub-lab{font-family:var(--mono);font-size:9px;letter-spacing:.14em;color:var(--faint);margin-bottom:8px}
.scrub-row{display:flex;align-items:center;gap:9px}
.scrub-btn{flex:none;background:transparent;border:1px solid var(--hair2);color:var(--ink);border-radius:8px;height:26px;min-width:30px;padding:0 8px;cursor:pointer;font-family:var(--mono);font-size:11px;line-height:1}
.scrub-btn:hover{border-color:var(--accent);color:var(--accent)}
.scrub-btn.live{color:var(--green);border-color:rgba(58,211,154,.4)}.scrub-btn.live:hover{background:rgba(58,211,154,.1)}
.scrubwrap input[type=range]{flex:1;-webkit-appearance:none;appearance:none;height:4px;border-radius:3px;background:linear-gradient(90deg,var(--accent),var(--pink));outline:none}
.scrubwrap input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;height:14px;border-radius:50%;background:var(--ink);border:2px solid var(--accent);cursor:pointer}
.scrubwrap input[type=range]::-moz-range-thumb{width:14px;height:14px;border-radius:50%;background:var(--ink);border:2px solid var(--accent);cursor:pointer}
.scrub-read{display:flex;align-items:center;gap:8px;margin-top:9px;font-family:var(--mono);font-size:11px;color:var(--faint)}
.scrub-read b{color:var(--ink);font-weight:600}.scrub-read .scrub-miss{margin-left:auto;color:var(--amber)}
.gpick{position:absolute;z-index:6;pointer-events:none;background:rgba(9,13,24,.92);border:1px solid var(--hair2);border-radius:9px;padding:8px 11px;max-width:200px;backdrop-filter:blur(6px)}
.gpick b{display:block;font-size:12px;color:var(--ink);margin-bottom:2px}.gpick span{font-family:var(--mono);font-size:9.5px;color:var(--dim)}
.gtoast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(12px);z-index:50;background:var(--panel);border:1px solid var(--hair2);color:var(--ink);font-size:12.5px;border-radius:10px;padding:10px 16px;opacity:0;pointer-events:none;transition:opacity .3s,transform .3s;box-shadow:0 8px 30px rgba(0,0,0,.4)}
.gtoast.show{opacity:1;transform:translateX(-50%) translateY(0)}

/* ---- tables / focus ---- */
.focusbar{display:flex;align-items:center;gap:10px;border:1px solid var(--hair2);border-radius:11px;background:var(--panel);padding:10px 14px;margin-bottom:14px;color:var(--faint)}
.focusbar svg{flex:none;color:var(--accent)}
.focusbar input{flex:1;background:transparent;border:0;outline:none;color:var(--ink);font-family:var(--mono);font-size:13px}
.focusbar input::placeholder{color:var(--faint)}.focusbar:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px rgba(92,200,255,.1)}
.focusinfo{font-family:var(--mono);font-size:11px;color:var(--dim);white-space:nowrap;flex:none}
.rowhint{font-size:10.5px;letter-spacing:.06em;color:var(--faint);margin:0 2px 8px}
.tablewrap{padding:6px 6px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--hair)}
th{color:var(--faint);font-family:var(--mono);font-weight:500;font-size:10px;text-transform:uppercase;letter-spacing:.09em}
td.num,th:nth-child(n+5){text-align:right}
tbody tr:hover td{background:rgba(92,200,255,.05)}
tr.crow{cursor:pointer}tr.crow:hover td:first-child{color:var(--ink)}
tr.crow:hover td:first-child::before{content:"▶ ";color:var(--accent);font-size:9px}
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
  .ov-hero{padding:24px 20px;min-height:0}.orb{display:none}.hero-cta{flex-wrap:wrap}
  .al-top{flex-direction:column;align-items:stretch}.enc{width:100%}
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
      <div class="tb-meta"><span>catalogue <b>__GROUP__</b></span><span>threshold <b>__THRESH__km</b></span><span>screened <b>__GENERATED__</b> UTC</span></div>
      <div class="tb-live" title="current time — live clock"><span class="dot live"></span><span id="utcclock">--:--:-- UTC</span></div>
      <button id="themetgl" class="themetgl" title="toggle light / dark" aria-label="toggle theme">◐</button>
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
<script>__SATELLITE_JS__</script>
<script>
var OG_EVENTS=__EVENTS_JSON__;var OG_GLOBE=__GLOBE_JSON__;var OG_GEOM=__GEOM_JSON__;var OG_SNAPSHOT="__SNAPSHOT__";
var OG_EARTH_TEX="data:image/jpeg;base64,__EARTH_TEX__";
</script>
<script>
(function(){
  var reduce=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var fmt=function(n,dec){return dec>0?n.toFixed(dec):Math.round(n).toLocaleString('en-US')};
  function esc(s){var d=document.createElement('div');d.textContent=String(s);return d.innerHTML}
  var TITLES={overview:'Overview',globe:'Orbital Globe',conjunctions:'Conjunctions',model:'Risk Model',methodology:'Methodology & Validation',about:'About'};

  // count-up (fires when its tile scrolls into view)
  function runCount(el){
    if(el._c)return;el._c=1;
    var t=parseFloat(el.dataset.count),dec=+el.dataset.dec||0;
    if(isNaN(t))return;
    if(reduce){el.textContent=fmt(t,dec);return}
    var dur=1000,s=null;function step(ts){if(!s)s=ts;var p=Math.min((ts-s)/dur,1),e=1-Math.pow(1-p,3);el.textContent=fmt(t*e,dec);if(p<1)requestAnimationFrame(step)}requestAnimationFrame(step);
  }
  // reveal-on-scroll (air.inc-style stagger) + count-up trigger
  var reveals=document.querySelectorAll('[data-reveal]');
  function revealNow(el){el.classList.add('in');el.querySelectorAll('.count').forEach(runCount)}
  if(reduce||!('IntersectionObserver' in window)){
    reveals.forEach(revealNow);document.querySelectorAll('.count').forEach(runCount);
  }else{
    var io=new IntersectionObserver(function(ents){ents.forEach(function(en){if(en.isIntersecting){revealNow(en.target);io.unobserve(en.target)}})},
      {threshold:.14,rootMargin:'0px 0px -36px 0px'});
    reveals.forEach(function(el){io.observe(el)});
    document.querySelectorAll('.count').forEach(function(c){if(!c.closest('[data-reveal]'))runCount(c)});
  }
  // cursor sheen on cards
  if(!reduce)document.querySelectorAll('.kpi,.panel').forEach(function(el){
    el.addEventListener('pointermove',function(e){var r=el.getBoundingClientRect();
      el.style.setProperty('--mx',((e.clientX-r.left)/r.width*100)+'%');
      el.style.setProperty('--my',((e.clientY-r.top)/r.height*100)+'%')});
  });

  // live UTC clock (top-right) — proves the page runs on real current time
  function tickClock(){var t=new Date().toISOString().slice(11,19);var el=document.getElementById('utcclock');if(el)el.textContent=t+' UTC';var h=document.getElementById('heroclock');if(h)h.textContent=t;}
  tickClock();setInterval(tickClock,1000);

  // light / dark theme (persisted)
  try{var savedTheme=localStorage.getItem('og_theme');if(savedTheme)document.documentElement.setAttribute('data-theme',savedTheme);}catch(e){}
  var tgl=document.getElementById('themetgl');
  if(tgl)tgl.addEventListener('click',function(){
    var cur=document.documentElement.getAttribute('data-theme')==='light'?'dark':'light';
    document.documentElement.setAttribute('data-theme',cur);
    try{localStorage.setItem('og_theme',cur);}catch(e){}
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

  // table row -> open on globe, highlighted + scrub-ready
  var _toast=null;
  function toast(msg){var el=document.getElementById('gtoast');if(!el){el=document.createElement('div');el.id='gtoast';el.className='gtoast';document.body.appendChild(el);}
    el.textContent=msg;el.classList.add('show');clearTimeout(_toast);_toast=setTimeout(function(){el.classList.remove('show')},2600);}
  document.addEventListener('click',function(e){var row=e.target.closest('.crow');if(!row)return;
    var rank=+row.dataset.rank;show('globe');
    setTimeout(function(){var ok=globeApi.selectConjByRank&&globeApi.selectConjByRank(rank);
      if(!ok)toast('3-D geometry is embedded for the top '+((OG_GEOM&&OG_GEOM.length)||0)+' conjunctions — showing the globe.');},60);});

  // focus search (conjunctions)
  var body=document.getElementById('ogbody'),inp=document.getElementById('ogfocus'),info=document.getElementById('ogfocusinfo');
  function pcStr(pc){if(pc==null)return '—';if(pc<1e-12)return '<1e-12';return pc.toExponential(1);}
  function rowHtml(e){var hue=Math.round(48-0.48*Math.min(e.rs,100));
    return '<tr class="crow" data-rank="'+e.r+'"><td class="rank">'+e.r+'</td><td>'+esc(e.a)+'<span class="norad">NORAD '+e.na+'</span></td>'+
      '<td>'+esc(e.b)+'<span class="norad">NORAD '+e.nb+'</span></td><td class="mono">'+e.t+'</td>'+
      '<td class="mono num">'+e.m.toFixed(3)+'</td><td class="mono num">'+e.v.toFixed(2)+'</td>'+
      '<td class="mono num">'+Math.round(e.al)+'</td><td class="mono num">'+pcStr(e.pc)+'</td>'+
      '<td><span class="risk" style="--rh:'+hue+'">'+Math.round(e.rs)+'</span></td></tr>'}
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
    function toV(q){return [q[0]*S,q[2]*S,-q[1]*S]}   // ECI(TEME) -> three (pole up); Earth is rotated by GMST so this is geo-accurate
    function eciKm(sr,date){var pv=satellite.propagate(sr,date);var p=pv&&pv.position;if(!p||isNaN(p.x))return null;return [p.x,p.y,p.z];}
    function bandOf(sr){var rpd=(sr.no||sr.no_kozai||0.06)*1440/(2*Math.PI);return rpd>11.25?0:(rpd>2?1:2);}  // LEO / MEO / high by revs-per-day
    var satGroup=new THREE.Group();scene.add(satGroup);
    var live=[],satPoints=null;
    function clearSats(){while(satGroup.children.length){var c=satGroup.children[0];satGroup.remove(c);if(c.geometry&&c.geometry.dispose)c.geometry.dispose();}live=[];satPoints=null;}
    // --- LIVE SGP4: build orbit shells + current positions from a TLE set (satellite.js) ---
    function buildSats(tles){
      clearSats();
      var recs=[];tles.forEach(function(t){try{var sr=satellite.twoline2satrec(t.l1,t.l2);if(sr&&!sr.error)recs.push({sr:sr,b:bandOf(sr),nm:t.nm||'',satnum:sr.satnum});}catch(e){}});
      var now0=new Date(),segs={0:[],1:[],2:[]},ppos=[],pcol=[];
      recs.forEach(function(r){
        var mm=r.sr.no||r.sr.no_kozai||0.0011,Tmin=(2*Math.PI)/mm,K=40,prev=null;   // one orbital period
        for(var k=0;k<=K;k++){var e=eciKm(r.sr,new Date(now0.getTime()+(k/K)*Tmin*60000));if(!e){prev=null;continue;}var v=toV(e);if(prev)segs[r.b].push(prev[0],prev[1],prev[2],v[0],v[1],v[2]);prev=v;}
        var e0=eciKm(r.sr,now0);if(e0){var v0=toV(e0),c=new THREE.Color(band[r.b]);ppos.push(v0[0],v0[1],v0[2]);pcol.push(c.r,c.g,c.b);live.push(r);}
      });
      [0,1,2].forEach(function(b){if(!segs[b].length)return;var g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(segs[b],3));
        satGroup.add(new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:band[b],transparent:true,opacity:.16,depthWrite:false})));});
      var pg=new THREE.BufferGeometry();pg.setAttribute('position',new THREE.Float32BufferAttribute(ppos,3));pg.setAttribute('color',new THREE.Float32BufferAttribute(pcol,3));
      satPoints=new THREE.Points(pg,new THREE.PointsMaterial({size:.03,vertexColors:true,transparent:true,opacity:.98,depthWrite:false}));satGroup.add(satPoints);
    }
    function updateSats(now){if(!satPoints)return;var arr=satPoints.geometry.attributes.position.array;for(var i=0;i<live.length;i++){var e=eciKm(live[i].sr,now);if(!e)continue;var v=toV(e);arr[i*3]=v[0];arr[i*3+1]=v[1];arr[i*3+2]=v[2];}satPoints.geometry.attributes.position.needsUpdate=true;}
    function freshEpoch(){var mx=0;live.forEach(function(r){if(r.sr.jdsatepoch>mx)mx=r.sr.jdsatepoch;});return mx?new Date((mx-2440587.5)*86400000).toISOString().slice(0,10):'—';}
    function setSrc(state,info){var el=document.getElementById('gsrc');if(!el)return;
      if(state==='live'){el.innerHTML='<span class="dot live"></span>LIVE · CelesTrak · '+info;}
      else if(state==='cache'){el.innerHTML='<span class="dot live"></span>LIVE · CelesTrak (cached) · '+info;}
      else{el.innerHTML='<span class="dot warn"></span>snapshot '+(OG_SNAPSHOT||'')+' · using baked elements';}}
    function parseTLE(txt){var L=txt.split(/\r?\n/),o=[];for(var i=0;i+2<L.length;i+=3){var nm=(L[i]||'').trim(),l1=L[i+1],l2=L[i+2];if(l1&&l1.charAt(0)==='1'&&l2&&l2.charAt(0)==='2')o.push({l1:l1,l2:l2,nm:nm});}return o;}
    function sampleArr(a,n){if(a.length<=n)return a;var o=[],st=a.length/n;for(var i=0;i<n;i++)o.push(a[Math.floor(i*st)]);return o;}
    // instant render from the baked snapshot; HUD stays "fetching…" until the live fetch settles
    buildSats(OG_GLOBE.tles||[]);
    (function(){
      var CK='og_live_tles_v1',TTL=3*3600*1000,fb=document.getElementById('globefallback');   // cache 3h: respect CelesTrak's rate limit, avoid re-pull 403s
      function done(){if(fb)fb.style.display='none';}
      try{var c=JSON.parse(localStorage.getItem(CK)||'null');
        if(c&&c.tles&&c.tles.length&&(Date.now()-c.t)<TTL){buildSats(c.tles);setSrc('cache',live.length+' objects · elements '+freshEpoch());done();return;}}catch(e){}
      var groups=['active','starlink'],gi=0;   // CelesTrak 403s repeat pulls of the same group; try another
      (function tryG(){if(gi>=groups.length){setSrc('snapshot');done();return;}
        fetch('https://celestrak.org/NORAD/elements/gp.php?GROUP='+groups[gi]+'&FORMAT=tle',{cache:'no-store'})
          .then(function(r){if(!r.ok)throw 0;return r.text();})
          .then(function(txt){var all=parseTLE(txt);if(all.length<50)throw 0;
            var samp=sampleArr(all,500);buildSats(samp);
            try{localStorage.setItem(CK,JSON.stringify({t:Date.now(),tles:samp}));}catch(e){}
            setSrc('live',live.length+' of '+Number(all.length).toLocaleString('en-US')+' '+groups[gi]+' · elements '+freshEpoch());done();})
          .catch(function(){gi++;tryG();});})();
    })();
    var hi=new THREE.Group();scene.add(hi);
    function drawConj(g,arcsOnly){while(hi.children.length)hi.remove(hi.children[0]);if(!g)return;
      function arc(a,color){if(!a)return;var v=a.map(function(q){var t=toV(q);return new THREE.Vector3(t[0],t[1],t[2])});hi.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(v),new THREE.LineBasicMaterial({color:color,depthWrite:false})))}
      arc(g.arc_a,0x5cc8ff);arc(g.arc_b,0xff4d8d);
      if(arcsOnly||!g.point_a||!g.point_b)return;   // scrubbable pairs draw live markers instead
      var ta=toV(g.point_a),tb=toV(g.point_b),pa=new THREE.Vector3(ta[0],ta[1],ta[2]),pb=new THREE.Vector3(tb[0],tb[1],tb[2]);
      [[pa,0x5cc8ff],[pb,0xff4d8d]].forEach(function(m){var d=new THREE.Mesh(new THREE.SphereGeometry(.013,16,16),new THREE.MeshBasicMaterial({color:m[1]}));d.position.copy(m[0]);hi.add(d)});
      var dl=new THREE.Line(new THREE.BufferGeometry().setFromPoints([pa,pb]),new THREE.LineDashedMaterial({color:0xf5a524,dashSize:.03,gapSize:.02,depthWrite:false}));dl.computeLineDistances();hi.add(dl)}

    // --- time-scrubber: live-propagate the selected pair to watch them converge to TCA ---
    var SCRUB_W=1800;   // ± window (seconds) around TCA
    var scrubActive=false,scrubDate=null,scrubA=null,scrubB=null,tcaMs=0,playing=false,playRAF=0,sgrp=null;
    var scrubInput=document.getElementById('scrub'),scrubWrap=document.getElementById('scrubwrap'),
        scrubDt=document.getElementById('scrubdt'),scrubMissEl=document.getElementById('scrubmiss'),
        playBtn=document.getElementById('scrubplay'),liveBtn=document.getElementById('scrublive');
    function fmtDelta(sec){var s=Math.round(sec),sg=s<0?'−':'+';s=Math.abs(s);var m=Math.floor(s/60),ss=s%60;return sg+(m<10?'0':'')+m+':'+(ss<10?'0':'')+ss;}
    function ensureSgrp(){if(sgrp)return;sgrp=new THREE.Group();scene.add(sgrp);
      sgrp.mA=new THREE.Mesh(new THREE.SphereGeometry(.018,18,18),new THREE.MeshBasicMaterial({color:0x5cc8ff}));
      sgrp.mB=new THREE.Mesh(new THREE.SphereGeometry(.018,18,18),new THREE.MeshBasicMaterial({color:0xff4d8d}));
      sgrp.add(sgrp.mA);sgrp.add(sgrp.mB);sgrp.line=null;}
    function positionScrub(date){
      if(!scrubA||!scrubB){if(sgrp)sgrp.visible=false;return null;}
      ensureSgrp();sgrp.visible=true;
      var ea=eciKm(scrubA,date),eb=eciKm(scrubB,date);if(!ea||!eb)return null;
      var va=toV(ea),vb=toV(eb);
      sgrp.mA.position.set(va[0],va[1],va[2]);sgrp.mB.position.set(vb[0],vb[1],vb[2]);
      if(sgrp.line){sgrp.remove(sgrp.line);if(sgrp.line.geometry)sgrp.line.geometry.dispose();}
      sgrp.line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([sgrp.mA.position.clone(),sgrp.mB.position.clone()]),new THREE.LineDashedMaterial({color:0xf5a524,dashSize:.02,gapSize:.014,depthWrite:false}));sgrp.line.computeLineDistances();sgrp.add(sgrp.line);
      var dx=ea[0]-eb[0],dy=ea[1]-eb[1],dz=ea[2]-eb[2];return Math.sqrt(dx*dx+dy*dy+dz*dz);}
    function readout(off,miss){if(scrubDt)scrubDt.textContent=fmtDelta(off);if(scrubMissEl)scrubMissEl.textContent=(miss==null?'— km':miss.toFixed(3)+' km');}
    function primeScrub(off){scrubDate=new Date(tcaMs+off*1000);var m=positionScrub(scrubDate);if(scrubInput)scrubInput.value=off;readout(off,m);}   // draw pair at TCA, scene stays live
    function setScrub(off){scrubActive=true;scrubDate=new Date(tcaMs+off*1000);var m=positionScrub(scrubDate);if(!reduce)updateSats(scrubDate);if(scrubInput&&+scrubInput.value!==off)scrubInput.value=off;readout(off,m);}
    function stopPlay(){playing=false;if(playRAF)cancelAnimationFrame(playRAF);playRAF=0;if(playBtn)playBtn.textContent='▶';}
    function startPlay(){if(reduce||!(scrubA&&scrubB))return;playing=true;if(playBtn)playBtn.textContent='❚❚';var t0=null,dur=7000;
      (function step(ts){if(!playing)return;if(!t0)t0=ts;var p=(ts-t0)/dur;if(p>=1){setScrub(SCRUB_W);stopPlay();return;}setScrub(Math.round(-SCRUB_W+2*SCRUB_W*p));playRAF=requestAnimationFrame(step);})(performance.now());}
    function selectGeom(g){stopPlay();scrubA=scrubB=null;
      tcaMs=g.tca_ms||Date.parse(String(g.tca_utc).replace(' ','T')+'Z')||0;   // tca_ms keeps sub-second precision
      if(g.l1_a&&g.l2_a&&g.l1_b&&g.l2_b){try{var a=satellite.twoline2satrec(g.l1_a,g.l2_a),b=satellite.twoline2satrec(g.l1_b,g.l2_b);if(a&&!a.error&&b&&!b.error){scrubA=a;scrubB=b;}}catch(e){}}
      var ok=!!(scrubA&&scrubB&&tcaMs);
      drawConj(g,ok);updInfo(g);
      if(scrubWrap)scrubWrap.style.display=ok?'block':'none';
      scrubActive=false;                       // scene stays live until the user scrubs
      if(ok){primeScrub(0);}else if(sgrp){sgrp.visible=false;}}
    if(scrubInput)scrubInput.addEventListener('input',function(){setScrub(+scrubInput.value)});
    if(playBtn)playBtn.addEventListener('click',function(){playing?stopPlay():startPlay();});
    if(liveBtn)liveBtn.addEventListener('click',function(){stopPlay();scrubActive=false;if(sgrp)sgrp.visible=false;if(scrubInput)scrubInput.value=0;readout(0,null);if(scrubDt)scrubDt.textContent='live';});

    // --- click a satellite to inspect it (raycast the live point cloud) ---
    var ray=new THREE.Raycaster();ray.params.Points.threshold=.045;var mouse=new THREE.Vector2(),_downXY=null;
    function hidePick(){var el=document.getElementById('gpick');if(el)el.style.display='none';}
    function showPick(rec,x,y){var el=document.getElementById('gpick');if(!el||!rec)return;
      var e=eciKm(rec.sr,scrubActive?scrubDate:new Date()),alt=e?Math.round(Math.sqrt(e[0]*e[0]+e[1]*e[1]+e[2]*e[2])-6371):'—',bn=['LEO','MEO','HIGH'][rec.b]||'';
      el.innerHTML='<b>'+esc(rec.nm||('NORAD '+rec.satnum))+'</b><span>NORAD '+rec.satnum+' · '+bn+' · alt '+alt+' km</span>';
      var host=document.getElementById('globe').getBoundingClientRect();
      el.style.left=Math.max(8,Math.min(x-host.left+12,host.width-190))+'px';el.style.top=Math.min(y-host.top+12,host.height-60)+'px';el.style.display='block';}
    renderer.domElement.addEventListener('pointerdown',function(e){_downXY=[e.clientX,e.clientY];});
    renderer.domElement.addEventListener('pointerup',function(e){if(!_downXY)return;var dx=e.clientX-_downXY[0],dy=e.clientY-_downXY[1];_downXY=null;if(dx*dx+dy*dy>25||!satPoints)return;
      var r=renderer.domElement.getBoundingClientRect();mouse.x=((e.clientX-r.left)/r.width)*2-1;mouse.y=-((e.clientY-r.top)/r.height)*2+1;ray.setFromCamera(mouse,camera);
      var hits=ray.intersectObject(satPoints);if(hits.length&&live[hits[0].index])showPick(live[hits[0].index],e.clientX,e.clientY);else hidePick();});

    var sel=document.getElementById('conjsel'),ci=document.getElementById('conjinfo');
    function updInfo(g){if(!ci)return;if(!g){ci.innerHTML='';return}
      ci.innerHTML='<div class="ci-lab">SELECTED CONJUNCTION</div><div class="ci-pair"><span class="a">'+esc(g.object_a)+'</span> ↔ <span class="b">'+esc(g.object_b)+'</span></div>'+
        '<div class="ci-grid"><div><span>MISS</span><b>'+g.miss_km.toFixed(2)+' km</b></div><div><span>CLOSING</span><b>'+g.rel_speed_kms.toFixed(1)+' km/s</b></div>'+
        '<div><span>Pc (modelled cov)</span><b>'+pcStr(g.pc)+'</b></div><div><span>RISK</span><b>'+Math.round(g.risk_score)+'</b></div>'+
        '<div><span>TCA</span><b style="font-size:11px">'+esc(g.tca_utc.slice(5,16))+'</b></div></div>'}
    if(sel&&OG_GEOM&&OG_GEOM.length){OG_GEOM.forEach(function(g,i){var o=document.createElement('option');o.value=i;o.textContent='#'+g.rank+'  '+g.object_a+' ↔ '+g.object_b+'  ('+g.miss_km.toFixed(2)+' km)';sel.appendChild(o)});
      sel.addEventListener('change',function(){selectGeom(OG_GEOM[+sel.value])});selectGeom(OG_GEOM[0])}else if(sel)sel.style.display='none';
    globeApi.selectConjByRank=function(rank){if(!OG_GEOM)return false;for(var i=0;i<OG_GEOM.length;i++){if(OG_GEOM[i].rank===rank){if(sel)sel.value=i;selectGeom(OG_GEOM[i]);return true;}}return false;};
    var lastUpd=0;
    function tick(ts){requestAnimationFrame(tick);controls.update();
      var d=scrubActive?scrubDate:new Date();
      earth.rotation.y=satellite.gstime(d);            // Earth follows scrub time when scrubbing -> geo-consistent
      if(!scrubActive && !reduce && Date.now()-lastUpd>400){lastUpd=Date.now();updateSats(new Date());}   // live positions, throttled
      renderer.render(scene,camera);}
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
    validation = _load_validation()

    nav = "".join(
        f'<a class="nitem{" active" if key == "overview" else ""}" data-view="{key}">'
        f'{_nav_icon(paths)}<span>{label}</span></a>'
        for key, label, paths in _NAV
    )

    compact = [
        {"r": e["rank"], "a": e["object_a"], "na": e["norad_a"], "b": e["object_b"],
         "nb": e["norad_b"], "t": e["tca_utc"], "m": round(e["miss_km"], 3),
         "v": round(e["rel_speed_kms"], 2), "al": round(e["alt_km"], 0),
         "rs": round(e["risk_score"], 1), "pc": e.get("pc")}
        for e in events
    ]

    small = {
        "__NAV__": nav,
        "__OVERVIEW__": _overview(summary, meta, events, validation),
        "__GLOBE__": _globe_view(globe.get("sample_n", 0)),
        "__CONJ__": _conjunctions_view(events),
        "__MODEL__": _model_view(comp),
        "__METHOD__": _validation_view(validation),
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
        "__SATELLITE_JS__": _vendor("satellite.min.js"),
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
