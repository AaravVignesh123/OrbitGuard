"""Dashboard — a single self-contained HTML *product site* you can open or share.

This is more than a report: it's a four-tab page aimed at both engineers and
non-technical stakeholders (operators, agencies like NASA/ESA, constellation
businesses):

    Overview     — what OrbitGuard is, who it's for, v1-now vs. what's next
    Live Report  — the actual screening results: stat cards, 3D close-approach
                   viewer, and the ranked conjunction table
    How it works — the six-stage pipeline, explained
    Roadmap      — v1 → ML risk → autonomy → showcase

Everything (including the Plotly library) is inlined, so the file has zero
external dependencies — double-click it, or host `docs/index.html` on GitHub
Pages. We build the page with token replacement (not str.format) so the CSS
braces stay readable.
"""

from __future__ import annotations

import html
from typing import List

import numpy as np
import plotly.graph_objects as go

_EARTH_RADIUS_KM = 6371.0
_SCENE_DIV_ID = "scene3d"


# --------------------------------------------------------------------------- #
# 3D figure
# --------------------------------------------------------------------------- #
def _earth_mesh(n: int = 40):
    u = np.linspace(0, 2 * np.pi, n)
    v = np.linspace(0, np.pi, n)
    x = _EARTH_RADIUS_KM * np.outer(np.cos(u), np.sin(v))
    y = _EARTH_RADIUS_KM * np.outer(np.sin(u), np.sin(v))
    z = _EARTH_RADIUS_KM * np.outer(np.ones_like(u), np.cos(v))
    return x, y, z


def _build_figure(geometry: List[dict]) -> go.Figure:
    fig = go.Figure()

    ex, ey, ez = _earth_mesh()
    fig.add_trace(
        go.Surface(
            x=ex, y=ey, z=ez, showscale=False,
            colorscale=[[0, "#0b2545"], [1, "#13315c"]], opacity=0.9,
            hoverinfo="skip", name="Earth",
            lighting=dict(ambient=0.65, diffuse=0.6),
        )
    )

    per_event = 5
    for gi, g in enumerate(geometry):
        vis = gi == 0
        arc_a = np.array(g["arc_a"]); arc_b = np.array(g["arc_b"])
        pa = np.array(g["point_a"]); pb = np.array(g["point_b"])

        fig.add_trace(go.Scatter3d(
            x=arc_a[:, 0], y=arc_a[:, 1], z=arc_a[:, 2], mode="lines",
            line=dict(color="#4cc9f0", width=4), name=g["object_a"],
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=arc_b[:, 0], y=arc_b[:, 1], z=arc_b[:, 2], mode="lines",
            line=dict(color="#f72585", width=4), name=g["object_b"],
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=[pa[0]], y=[pa[1]], z=[pa[2]], mode="markers",
            marker=dict(size=5, color="#4cc9f0"), name=g["object_a"] + " @ TCA",
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=[pb[0]], y=[pb[1]], z=[pb[2]], mode="markers",
            marker=dict(size=5, color="#f72585"), name=g["object_b"] + " @ TCA",
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=[pa[0], pb[0]], y=[pa[1], pb[1]], z=[pa[2], pb[2]],
            mode="lines+text", line=dict(color="#ffd166", width=6, dash="dot"),
            text=["", f"{g['miss_km']:.2f} km"], textposition="middle right",
            textfont=dict(color="#ffd166", size=13), name="miss distance",
            visible=vis, hoverinfo="text"))

    buttons = []
    n_traces = 1 + per_event * len(geometry)
    for gi, g in enumerate(geometry):
        visible = [False] * n_traces
        visible[0] = True
        for t in range(per_event):
            visible[1 + gi * per_event + t] = True
        label = f"#{g['rank']}  {g['object_a']} ↔ {g['object_b']}  ({g['miss_km']:.2f} km)"
        buttons.append(dict(label=label, method="update", args=[{"visible": visible}]))

    fig.update_layout(
        updatemenus=[dict(
            buttons=buttons, direction="down", showactive=True,
            x=0.01, xanchor="left", y=0.99, yanchor="top",
            bgcolor="#13315c", font=dict(color="#e8eef7"), bordercolor="#4cc9f0",
        )] if geometry else [],
        scene=dict(
            xaxis=dict(showbackground=False, showticklabels=False, title="", color="#8899b0"),
            yaxis=dict(showbackground=False, showticklabels=False, title="", color="#8899b0"),
            zaxis=dict(showbackground=False, showticklabels=False, title="", color="#8899b0"),
            aspectmode="data", bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, height=560,
    )
    return fig


# --------------------------------------------------------------------------- #
# HTML fragments
# --------------------------------------------------------------------------- #
def _stat_cards(summary: dict, meta: dict) -> str:
    def card(label, value, unit=""):
        return (f'<div class="card"><div class="card-value">{value}'
                f'<span class="unit">{unit}</span></div>'
                f'<div class="card-label">{label}</div></div>')
    closest = summary.get("closest_km")
    fastest = summary.get("fastest_kms")
    median = summary.get("median_miss_km")
    return (
        '<div class="cards">'
        + card("Objects screened", f"{meta.get('n_objects', 0):,}")
        + card("Candidate events", f"{summary.get('n_events', 0):,}")
        + card("Closest approach", f"{closest:.2f}" if closest is not None else "—", " km")
        + card("Median miss", f"{median:.1f}" if median is not None else "—", " km")
        + card("Fastest closing speed", f"{fastest:.1f}" if fastest is not None else "—", " km/s")
        + "</div>"
    )


def _table(events: List[dict], top: int = 50) -> str:
    head = ("<tr><th>#</th><th>Object A</th><th>Object B</th><th>TCA (UTC)</th>"
            "<th>Miss (km)</th><th>Rel. speed (km/s)</th><th>Alt (km)</th><th>Risk</th></tr>")
    rows = []
    for e in events[:top]:
        score = e["risk_score"]
        hue = int(120 - 1.2 * min(score, 100))
        chip = (f'<span class="risk" style="background:hsl({hue},70%,30%);'
                f'border-color:hsl({hue},70%,45%)">{score:.0f}</span>')
        rows.append(
            "<tr>"
            f"<td class='rank'>{e['rank']}</td>"
            f"<td>{html.escape(str(e['object_a']))}<span class='norad'>{e['norad_a']}</span></td>"
            f"<td>{html.escape(str(e['object_b']))}<span class='norad'>{e['norad_b']}</span></td>"
            f"<td class='mono'>{e['tca_utc']}</td>"
            f"<td class='mono'>{e['miss_km']:.3f}</td>"
            f"<td class='mono'>{e['rel_speed_kms']:.2f}</td>"
            f"<td class='mono'>{e['alt_km']:.0f}</td>"
            f"<td>{chip}</td></tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


def _overview(summary: dict, meta: dict) -> str:
    n_obj = f"{meta.get('n_objects', 0):,}"
    n_evt = f"{summary.get('n_events', 0):,}"
    closest = summary.get("closest_km")
    closest_s = f"{closest:.2f} km" if closest is not None else "—"
    return f"""
<section class="hero">
  <div class="pill">v1 · conjunction screener · live demo</div>
  <h1 class="hero-title">See the collision<br><span class="grad">before it happens.</span></h1>
  <p class="lead">Low-Earth orbit is getting crowded — tens of thousands of tracked
  objects, and climbing fast. <b>OrbitGuard</b> ingests a live satellite catalog,
  propagates every object forward in time, and finds the pairs headed for a
  dangerously close pass — ranked by risk, ready to act on.</p>
  <div class="hero-metrics">
    <div><span class="hm-num">{n_obj}</span><span class="hm-lab">objects screened this run</span></div>
    <div><span class="hm-num">{n_evt}</span><span class="hm-lab">close approaches flagged</span></div>
    <div><span class="hm-num">{closest_s}</span><span class="hm-lab">closest predicted pass</span></div>
  </div>
  <div class="cta"><a class="btn primary" data-goto="report">See the live report →</a>
  <a class="btn ghost" data-goto="how">How it works</a></div>
</section>

<section>
  <h2>Why this matters</h2>
  <div class="grid3">
    <div class="feature"><div class="ficon">🛰️</div><h3>The sky is filling up</h3>
      <p>Mega-constellations added thousands of satellites in a few years. More
      objects means exponentially more pairs that can conjunct.</p></div>
    <div class="feature"><div class="ficon">💥</div><h3>Collisions cascade</h3>
      <p>One impact creates thousands of new fragments — the Kessler effect — each
      a fresh hazard. Prevention is far cheaper than cleanup.</p></div>
    <div class="feature"><div class="ficon">⏱️</div><h3>Warning time is everything</h3>
      <p>A maneuver needs planning. Knowing <i>which</i> pairs and <i>when</i>,
      hours to days ahead, is what makes avoidance possible.</p></div>
  </div>
</section>

<section>
  <h2>Who it's for</h2>
  <div class="grid3">
    <div class="feature"><h3>Satellite operators</h3>
      <p>Constellation and single-asset operators (Starlink, OneWeb, Planet, and
      smaller fleets) who need a first-pass screen of their objects against the
      full catalog.</p></div>
    <div class="feature"><h3>Space agencies</h3>
      <p>Teams like <b>NASA</b> and <b>ESA</b> running conjunction assessment —
      OrbitGuard mirrors the front half of the pipeline behind services such as
      CelesTrak SOCRATES and CARA.</p></div>
    <div class="feature"><h3>Analysts &amp; insurers</h3>
      <p>Anyone quantifying orbital risk: space-traffic researchers, debris
      analysts, and underwriters pricing on-orbit collision exposure.</p></div>
  </div>
</section>

<section>
  <h2>Where OrbitGuard is today — and where it's going</h2>
  <div class="nowlater">
    <div class="nl-col now">
      <div class="nl-tag">✅ v1 — available now</div>
      <ul>
        <li>Pulls a live <b>CelesTrak</b> catalog ({n_obj} objects this run)</li>
        <li>Propagates every object with SGP4 onto one shared clock</li>
        <li>Screens the whole population for close approaches with a KD-tree
            (dodges the O(n²) wall)</li>
        <li>Refines each flag to a sub-second <b>time of closest approach</b> and
            true <b>miss distance</b></li>
        <li>Ranks by a closing-speed × closeness <b>risk proxy</b></li>
        <li>Outputs CSV + JSON + this interactive dashboard</li>
      </ul>
    </div>
    <div class="nl-col later">
      <div class="nl-tag">🚧 next — in development</div>
      <ul>
        <li><b>ML risk model</b> — a learned probability of collision trained on
            real Conjunction Data Messages (ESA Kelvins dataset), replacing the
            geometric proxy</li>
        <li><b>Covariance &amp; uncertainty</b> — proper error ellipsoids, not
            just point geometry</li>
        <li><b>Autonomy</b> — for top-risk events, suggest a small avoidance
            Δv and show the improved miss distance</li>
        <li><b>Higher-fidelity data</b> — Space-Track integration and validation
            against operational reports</li>
        <li><b>Alerting</b> — watchlists and notifications per operator</li>
      </ul>
    </div>
  </div>
  <p class="disclaimer">OrbitGuard v1 is a self-directed engineering project and a
  screening/analysis tool — not an operational or safety-certified system. Always
  validate against authoritative sources (CelesTrak SOCRATES, Space-Track) before
  any operational decision.</p>
</section>
"""


def _how_it_works() -> str:
    steps = [
        ("01", "Catalog", "Download a CelesTrak group (active, starlink, stations…), "
         "cache the dated raw TLE snapshot, parse to satellites, skip malformed "
         "records, and de-duplicate by NORAD id.", "catalog.py"),
        ("02", "Propagate", "SGP4-propagate every object to every timestep into one "
         "(N × T × 3) position cube — all in a single inertial frame, the invariant "
         "that makes distances meaningful.", "propagate.py"),
        ("03", "Screen", "At each timestep build a scipy cKDTree and query pairs within "
         "the threshold. 16k objects would be ~130M brute-force pairs per step; the "
         "tree makes it milliseconds. Consecutive hits group into one event.", "screen.py"),
        ("04", "Refine", "Re-propagate just the two objects at 1-second cadence around "
         "each flag and fit a parabola to the separation curve — a sub-second TCA and a "
         "true miss distance (the coarse grid always over-estimates).", "refine.py"),
        ("05", "Rank", "Compute relative velocity at closest approach and score "
         "risk ∝ closing speed / (miss distance + ε), log-scaled to 0–100.", "risk.py"),
        ("06", "Report", "Emit a ranked CSV, a full JSON payload, and this "
         "self-contained interactive dashboard.", "report.py / dashboard.py"),
    ]
    items = []
    for num, title, body, mod in steps:
        items.append(
            f'<div class="step"><div class="step-num">{num}</div>'
            f'<div class="step-body"><h3>{title} <span class="mod">{mod}</span></h3>'
            f'<p>{body}</p></div></div>'
        )
    return f"""
<section>
  <h2>How it works</h2>
  <p class="lead">One command — <code>python src/screen.py --group active --hours 24
  --threshold 10</code> — runs the whole chain:</p>
  <div class="flow">CelesTrak TLEs → propagate → KD-tree screen → refine TCA →
  risk rank → report</div>
  <div class="steps">{''.join(items)}</div>
</section>
"""


def _roadmap() -> str:
    phases = [
        ("Phase 0–2.5", "v1 — Conjunction screener", "done",
         "Live catalog → propagate → screen → refine → risk-rank → report + dashboard. "
         "Validated: KD-tree equals brute force; refinement sharpens every flag."),
        ("Phase 3", "ML risk model", "next",
         "Train on the ESA Kelvins Collision Avoidance Challenge CDM dataset to predict "
         "whether a conjunction escalates — replacing the geometric proxy with a learned "
         "probability of collision. (Scaffold already in src/orbitguard/ml/.)"),
        ("Phase 4", "Autonomy", "future",
         "For high-risk events, propose a small avoidance Δv and show the resulting "
         "improved miss distance — closing the loop from detection to action."),
        ("Phase 5", "Showcase", "future",
         "Polished repo, writeup, and public demo — the flagship artifact tying the "
         "whole trajectory together."),
    ]
    items = []
    for tag, title, state, body in phases:
        items.append(
            f'<div class="phase {state}"><div class="phase-dot"></div>'
            f'<div class="phase-body"><div class="phase-tag">{tag}</div>'
            f'<h3>{title}</h3><p>{body}</p></div></div>'
        )
    return f"""
<section>
  <h2>Roadmap</h2>
  <p class="lead">v1 is the screening core. The fall phases add the ML and autonomy
  layers that turn a screener into a decision-support system.</p>
  <div class="timeline">{''.join(items)}</div>
</section>
"""


# --------------------------------------------------------------------------- #
# Page template (token replacement — no str.format, so CSS braces stay clean)
# --------------------------------------------------------------------------- #
_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OrbitGuard — Orbital Collision-Avoidance</title>
<style>
:root { color-scheme: dark;
  --bg:#060a14; --bg2:#0a111e; --panel:#0e1626; --line:#1b2942; --line2:#16233b;
  --txt:#e8eef7; --mut:#8899b0; --mut2:#5b6b85;
  --cy:#4cc9f0; --pk:#f72585; --gold:#ffd166; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:radial-gradient(1200px 600px at 70% -10%, #10203f 0%, var(--bg) 55%);
  color:var(--txt); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased; line-height:1.55; }
a { color:var(--cy); text-decoration:none; cursor:pointer; }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; background:#0c1526;
  border:1px solid var(--line); border-radius:6px; padding:1px 6px; font-size:.9em; color:#cfe6ff; }

/* nav */
.nav { position:sticky; top:0; z-index:50; backdrop-filter:blur(10px);
  background:rgba(6,10,20,.72); border-bottom:1px solid var(--line); }
.nav-in { max-width:1080px; margin:0 auto; padding:14px 20px; display:flex; align-items:center; gap:22px; }
.brand { font-weight:750; font-size:18px; letter-spacing:-.02em; margin-right:auto; }
.brand .g { color:var(--cy); }
.tabs { display:flex; gap:4px; }
.tab { padding:7px 14px; border-radius:10px; color:var(--mut); font-size:14px; font-weight:550;
  border:1px solid transparent; }
.tab:hover { color:var(--txt); background:#0e1830; }
.tab.active { color:#fff; background:#13233f; border-color:#25406b; }

.wrap { max-width:1080px; margin:0 auto; padding:36px 20px 80px; }
.view { display:none; animation:fade .35s ease; }
.view.active { display:block; }
@keyframes fade { from{opacity:0; transform:translateY(6px);} to{opacity:1; transform:none;} }

section { margin-top:44px; }
section:first-child { margin-top:8px; }
h1,h2,h3 { letter-spacing:-.02em; }
h2 { font-size:24px; margin:0 0 18px; }
h3 { font-size:17px; margin:0 0 6px; }
.lead { color:#c3d0e6; font-size:17px; max-width:760px; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }

/* hero */
.hero { padding:26px 0 6px; }
.pill { display:inline-block; font-size:12.5px; color:var(--cy); border:1px solid #25406b;
  background:#0d1c33; padding:5px 12px; border-radius:999px; margin-bottom:18px; }
.hero-title { font-size:52px; line-height:1.03; margin:0 0 16px; font-weight:800; }
.grad { background:linear-gradient(90deg,#4cc9f0,#7b6cf6 55%,#f72585);
  -webkit-background-clip:text; background-clip:text; color:transparent; }
.hero-metrics { display:flex; flex-wrap:wrap; gap:34px; margin:26px 0 24px; }
.hero-metrics .hm-num { display:block; font-size:30px; font-weight:750; color:#fff; }
.hero-metrics .hm-lab { color:var(--mut); font-size:13.5px; }
.cta { display:flex; gap:12px; flex-wrap:wrap; }
.btn { padding:11px 20px; border-radius:12px; font-weight:600; font-size:14.5px; border:1px solid transparent; }
.btn.primary { background:linear-gradient(90deg,#3aa0ff,#6c5cf6); color:#fff; }
.btn.primary:hover { filter:brightness(1.08); }
.btn.ghost { border-color:var(--line); color:var(--txt); }
.btn.ghost:hover { background:#0e1830; }

/* grids / cards */
.grid3 { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; }
.feature { background:linear-gradient(180deg,var(--panel),var(--bg2)); border:1px solid var(--line);
  border-radius:16px; padding:20px; }
.feature .ficon { font-size:24px; margin-bottom:8px; }
.feature p { color:var(--mut); font-size:14px; margin:0; }

.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin:6px 0 8px; }
.card { background:linear-gradient(180deg,var(--panel),var(--bg2)); border:1px solid var(--line);
  border-radius:14px; padding:18px 20px; }
.card-value { font-size:28px; font-weight:700; color:#fff; }
.card-value .unit { font-size:14px; color:var(--mut); font-weight:400; margin-left:3px; }
.card-label { color:var(--mut); font-size:13px; margin-top:4px; }

/* now / later */
.nowlater { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.nl-col { border:1px solid var(--line); border-radius:16px; padding:20px 22px; background:var(--bg2); }
.nl-col.now { border-color:#1c5a3a; background:linear-gradient(180deg,#0c1a14,#0a1410); }
.nl-col.later { border-color:#4a3a12; background:linear-gradient(180deg,#191408,#12100a); }
.nl-tag { font-weight:700; margin-bottom:10px; }
.nl-col ul { margin:0; padding-left:18px; color:#cbd6ea; font-size:14px; }
.nl-col li { margin:7px 0; }
.disclaimer { color:var(--mut2); font-size:12.5px; margin-top:16px; border-top:1px solid var(--line2);
  padding-top:14px; }

/* how it works */
.flow { font-family:ui-monospace,monospace; color:#9fe6ff; background:#0b1728; border:1px solid var(--line);
  border-radius:12px; padding:14px 16px; margin:14px 0 22px; overflow-x:auto; white-space:nowrap; font-size:13.5px; }
.steps { display:grid; gap:12px; }
.step { display:flex; gap:16px; background:var(--bg2); border:1px solid var(--line); border-radius:14px; padding:16px 18px; }
.step-num { font-family:ui-monospace,monospace; font-size:20px; font-weight:700; color:var(--cy); min-width:34px; }
.step-body p { color:var(--mut); font-size:14px; margin:0; }
.step .mod { font-family:ui-monospace,monospace; font-size:12px; color:var(--mut2); font-weight:400; margin-left:6px; }

/* timeline */
.timeline { position:relative; margin-left:8px; }
.phase { display:flex; gap:18px; padding:0 0 26px 4px; position:relative; }
.phase::before { content:""; position:absolute; left:6px; top:16px; bottom:-6px; width:2px; background:var(--line); }
.phase:last-child::before { display:none; }
.phase-dot { width:14px; height:14px; border-radius:50%; margin-top:5px; flex:none; z-index:1;
  background:#26324a; border:2px solid #3a4a66; }
.phase.done .phase-dot { background:#28c76f; box-shadow:0 0 0 4px rgba(40,199,111,.15); }
.phase.next .phase-dot { background:var(--cy); box-shadow:0 0 0 4px rgba(76,201,240,.15); }
.phase-tag { font-family:ui-monospace,monospace; font-size:12px; color:var(--mut); }
.phase-body p { color:var(--mut); font-size:14px; margin:4px 0 0; max-width:720px; }

/* panel + table */
.panel { background:var(--bg2); border:1px solid var(--line); border-radius:16px; padding:14px; margin-top:8px; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
th,td { text-align:left; padding:9px 10px; border-bottom:1px solid var(--line2); }
th { color:var(--mut); font-weight:600; font-size:11.5px; text-transform:uppercase; letter-spacing:.04em; }
tr:hover td { background:#0e1830; }
.rank { color:var(--cy); font-weight:700; }
.norad { display:block; color:var(--mut2); font-size:11px; font-family:ui-monospace,monospace; }
.risk { display:inline-block; min-width:34px; text-align:center; padding:3px 8px; border-radius:8px;
  border:1px solid; font-weight:700; font-size:12px; color:#fff; }
.note { color:var(--mut2); font-size:12.5px; margin-top:10px; line-height:1.6; }
.meta { color:var(--mut2); font-size:12.5px; font-family:ui-monospace,monospace; margin-top:6px; }

footer { margin-top:56px; color:var(--mut2); font-size:12px; border-top:1px solid var(--line2); padding-top:18px; }

@media (max-width:720px){
  .hero-title{ font-size:38px; } .nowlater{ grid-template-columns:1fr; }
  .tabs{ overflow-x:auto; } .nav-in{ gap:12px; }
}
</style></head>
<body>
<nav class="nav"><div class="nav-in">
  <div class="brand"><span class="g">Orbit</span>Guard</div>
  <div class="tabs">
    <a class="tab active" data-view="overview">Overview</a>
    <a class="tab" data-view="report">Live Report</a>
    <a class="tab" data-view="how">How it works</a>
    <a class="tab" data-view="roadmap">Roadmap</a>
  </div>
</div></nav>

<div class="wrap">
  <div class="view active" id="view-overview">__OVERVIEW__</div>

  <div class="view" id="view-report">
    <section>
      <h2>Live conjunction report</h2>
      <div class="meta">__META_LINE__</div>
      __CARDS__
    </section>
    <section>
      <h3>Top conjunction — 3D close-approach geometry</h3>
      <div class="panel">__FIGURE__</div>
      <div class="note">Blue and pink arcs are the two objects' orbit tracks in the ±12 min
      around closest approach (Earth-centred inertial frame); the dotted gold line is the
      miss distance at the time of closest approach (TCA). Use the dropdown to switch events;
      drag to rotate, scroll to zoom.</div>
    </section>
    <section>
      <h3>Ranked conjunctions</h3>
      <div class="panel">__TABLE__</div>
      <div class="note">Risk is a v1 proxy = closing&nbsp;speed / (miss&nbsp;distance + 0.2&nbsp;km),
      log-scaled to 0–100 — higher means a small miss <em>and</em> a high closing speed. It is not a
      formal probability of collision; a covariance-based ML risk model is the next phase.</div>
    </section>
  </div>

  <div class="view" id="view-how">__HOW__</div>
  <div class="view" id="view-roadmap">__ROADMAP__</div>

  <footer>
    Generated __GENERATED__ UTC · catalog snapshot __SNAPSHOT__ · __NOBJ__ objects ·
    runtime __RUNTIME__s · data © CelesTrak · OrbitGuard v__VERSION__.
    A student-built screening tool — validate against CelesTrak SOCRATES before operational use.
  </footer>
</div>

<script>
(function(){
  var tabs = document.querySelectorAll('.tab');
  var views = document.querySelectorAll('.view');
  function show(name){
    tabs.forEach(function(t){ t.classList.toggle('active', t.dataset.view===name); });
    views.forEach(function(v){ v.classList.toggle('active', v.id==='view-'+name); });
    if(name==='report'){
      var el = document.getElementById('__SCENE_ID__');
      if(el && window.Plotly){ try{ Plotly.Plots.resize(el); }catch(e){} }
    }
    if(history && history.replaceState){ history.replaceState(null,'','#'+name); }
    window.scrollTo({top:0});
  }
  document.addEventListener('click', function(e){
    var t = e.target.closest('[data-view]'); var g = e.target.closest('[data-goto]');
    if(t){ show(t.dataset.view); } else if(g){ show(g.dataset.goto); }
  });
  var h = (location.hash||'').replace('#',''); if(h){ show(h); }
})();
</script>
</body></html>
"""


def build_dashboard(payload: dict, path: str) -> str:
    meta = payload["meta"]
    summary = payload["summary"]

    fig = _build_figure(payload.get("geometry", []))
    fig_html = fig.to_html(include_plotlyjs=True, full_html=False, div_id=_SCENE_DIV_ID,
                           config={"displayModeBar": False, "responsive": True})

    meta_line = (
        f"group={meta['group']} · window={meta['hours']}h · step={int(meta['step_s'])}s · "
        f"threshold={meta['threshold_km']}km · screened from {meta['start_utc']} UTC"
    )

    repl = {
        "__OVERVIEW__": _overview(summary, meta),
        "__META_LINE__": html.escape(meta_line),
        "__CARDS__": _stat_cards(summary, meta),
        "__FIGURE__": fig_html,
        "__TABLE__": _table(payload["events"]),
        "__HOW__": _how_it_works(),
        "__ROADMAP__": _roadmap(),
        "__GENERATED__": str(meta.get("generated_utc", "")),
        "__SNAPSHOT__": str(meta.get("snapshot_date", "")),
        "__NOBJ__": f"{meta.get('n_objects', 0):,}",
        "__RUNTIME__": str(meta.get("runtime_s", "")),
        "__VERSION__": str(meta.get("orbitguard_version", "1.0.0")),
        "__SCENE_ID__": _SCENE_DIV_ID,
    }
    page = _PAGE
    for k, v in repl.items():
        page = page.replace(k, v)

    with open(path, "w") as fh:
        fh.write(page)
    return path
