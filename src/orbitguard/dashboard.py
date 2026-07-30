"""Dashboard — a single self-contained HTML *product site* you can open or share.

Four tabs aimed at both engineers and stakeholders (operators, agencies like
NASA/ESA, constellation businesses):

    Overview     — what OrbitGuard is, who it's for, v1-now vs. what's next
    Live Report  — screening results: instrument readout, 3D close-approach
                   viewer, and the ranked conjunction table
    How it works — the six-stage pipeline, explained
    Roadmap      — v1 → ML risk → autonomy → showcase

Design language is deliberately a "space situational-awareness instrument":
mono technical labels, hairline rules, an asymmetric editorial hero, a subtle
starfield — no rainbow gradients, no emoji-card soup. Everything (including the
Plotly library) is inlined, so the file has zero external dependencies — open it
directly, or host `docs/index.html` on GitHub Pages. Built with token
replacement (not str.format) so the CSS braces stay readable.
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
            colorscale=[[0, "#0a1a2f"], [1, "#12385f"]], opacity=0.92,
            hoverinfo="skip", name="Earth",
            lighting=dict(ambient=0.7, diffuse=0.55),
        )
    )

    per_event = 5
    for gi, g in enumerate(geometry):
        vis = gi == 0
        arc_a = np.array(g["arc_a"]); arc_b = np.array(g["arc_b"])
        pa = np.array(g["point_a"]); pb = np.array(g["point_b"])

        fig.add_trace(go.Scatter3d(
            x=arc_a[:, 0], y=arc_a[:, 1], z=arc_a[:, 2], mode="lines",
            line=dict(color="#5cc8ff", width=4), name=g["object_a"],
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=arc_b[:, 0], y=arc_b[:, 1], z=arc_b[:, 2], mode="lines",
            line=dict(color="#ff4d8d", width=4), name=g["object_b"],
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=[pa[0]], y=[pa[1]], z=[pa[2]], mode="markers",
            marker=dict(size=5, color="#5cc8ff"), name=g["object_a"] + " @ TCA",
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=[pb[0]], y=[pb[1]], z=[pb[2]], mode="markers",
            marker=dict(size=5, color="#ff4d8d"), name=g["object_b"] + " @ TCA",
            visible=vis, hoverinfo="name"))
        fig.add_trace(go.Scatter3d(
            x=[pa[0], pb[0]], y=[pa[1], pb[1]], z=[pa[2], pb[2]],
            mode="lines+text", line=dict(color="#f5a524", width=6, dash="dot"),
            text=["", f"{g['miss_km']:.2f} km"], textposition="middle right",
            textfont=dict(color="#f5a524", size=13), name="miss distance",
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
        font=dict(family="ui-monospace, SFMono-Regular, Menlo, monospace"),
        updatemenus=[dict(
            buttons=buttons, direction="down", showactive=True,
            x=0.01, xanchor="left", y=0.99, yanchor="top",
            bgcolor="#0e1626", font=dict(color="#e6ecf5", size=12),
            bordercolor="#2a3a57",
        )] if geometry else [],
        scene=dict(
            xaxis=dict(showbackground=False, showticklabels=False, title="", color="#5c6880"),
            yaxis=dict(showbackground=False, showticklabels=False, title="", color="#5c6880"),
            zaxis=dict(showbackground=False, showticklabels=False, title="", color="#5c6880"),
            aspectmode="data", bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, height=560,
    )
    return fig


# --------------------------------------------------------------------------- #
# small inline line-icons (stroke=currentColor so CSS colors them)
# --------------------------------------------------------------------------- #
_IC_ORBIT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="1.4"><circle cx="12" cy="12" r="3.1"/>'
             '<ellipse cx="12" cy="12" rx="10" ry="4.3" transform="rotate(28 12 12)"/>'
             '<rect x="20.2" y="9.1" width="2" height="2" rx="0.4" '
             'transform="rotate(28 12 12)" fill="currentColor" stroke="none"/></svg>')
_IC_IMPACT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="1.4"><path d="M3 12h4"/><path d="m5.5 9.5 2.5 2.5-2.5 2.5"/>'
              '<path d="M21 12h-4"/><path d="m18.5 9.5-2.5 2.5 2.5 2.5"/>'
              '<path d="M12 4.5v2.4M12 17.1v2.4M8.6 8.6l1.7 1.7M15.4 8.6l-1.7 1.7"/>'
              '<circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/></svg>')
_IC_CLOCK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="1.4"><circle cx="12" cy="12" r="8.4"/>'
             '<path d="M12 7.4V12l3.1 1.9"/></svg>')


# --------------------------------------------------------------------------- #
# HTML fragments
# --------------------------------------------------------------------------- #
def _readout_row(label, value, unit=""):
    return (f'<div class="ro-row"><span class="ro-lab">{label}</span>'
            f'<span class="ro-val">{value}<i>{unit}</i></span></div>')


def _stat_cards(summary: dict, meta: dict) -> str:
    def card(label, value, unit=""):
        return (f'<div class="stat"><div class="stat-val">{value}'
                f'<span class="unit">{unit}</span></div>'
                f'<div class="stat-lab">{label}</div></div>')
    closest = summary.get("closest_km")
    fastest = summary.get("fastest_kms")
    median = summary.get("median_miss_km")
    return (
        '<div class="stats">'
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
        hue = int(48 - 0.48 * min(score, 100))  # amber(48) -> red(0)
        chip = (f'<span class="risk" style="--rh:{hue}">{score:.0f}</span>')
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
    return f"<table>{head}{''.join(rows)}</table>"


def _sec_head(no: str, kicker: str, title: str) -> str:
    return (f'<div class="sec-head"><div class="kicker"><span class="sec-no">{no}</span>'
            f'{kicker}</div><h2>{title}</h2></div>')


def _overview(summary: dict, meta: dict) -> str:
    n_obj = f"{meta.get('n_objects', 0):,}"
    n_evt = f"{summary.get('n_events', 0):,}"
    closest = summary.get("closest_km")
    fastest = summary.get("fastest_kms")
    closest_s = f"{closest:.2f}" if closest is not None else "—"
    fastest_s = f"{fastest:.1f}" if fastest is not None else "—"
    window = f"{meta.get('hours')}"
    return f"""
<section class="hero">
  <div class="hero-grid">
    <div class="hero-main">
      <div class="eyebrow"><span class="dot live"></span>Space situational awareness · conjunction screener · v1</div>
      <h1 class="display">Catch the close approach<br>before it becomes a<span class="uline"> collision.</span></h1>
      <p class="lead">Low-Earth orbit now holds tens of thousands of tracked objects, and
      the count climbs every launch. <b>OrbitGuard</b> ingests a live catalogue, propagates
      every object forward in time, and surfaces the pairs headed for a dangerously close
      pass — with a precise time, miss distance, and risk rank.</p>
      <div class="cta">
        <a class="btn primary" data-goto="report">Open the live report<span class="arr">→</span></a>
        <a class="btn ghost" data-goto="how">How it works</a>
      </div>
    </div>
    <aside class="readout" aria-label="latest run readout">
      <div class="ro-head"><span>LATEST RUN</span><span class="ro-live"><span class="dot live"></span>COMPLETE</span></div>
      {_readout_row("OBJECTS SCREENED", n_obj)}
      {_readout_row("CONJUNCTIONS FLAGGED", n_evt)}
      {_readout_row("CLOSEST PASS", closest_s, " km")}
      {_readout_row("FASTEST CLOSING", fastest_s, " km/s")}
      {_readout_row("WINDOW", window, " h")}
      {_readout_row("SOURCE", "CelesTrak")}
      <div class="ro-foot">TLE snapshot {meta.get('snapshot_date','')}</div>
    </aside>
  </div>
</section>

<section>
  {_sec_head("01", "THE PROBLEM", "Why orbital conjunctions matter")}
  <div class="grid3">
    <div class="feature"><div class="fic">{_IC_ORBIT}</div><h3>The sky is filling up</h3>
      <p>Mega-constellations added thousands of satellites in a few years. More objects
      means combinatorially more pairs that can cross paths.</p></div>
    <div class="feature"><div class="fic">{_IC_IMPACT}</div><h3>Collisions cascade</h3>
      <p>A single impact spawns thousands of fragments — the Kessler effect — each one a
      new hazard. Prevention is orders of magnitude cheaper than cleanup.</p></div>
    <div class="feature"><div class="fic">{_IC_CLOCK}</div><h3>Lead time is everything</h3>
      <p>A maneuver takes planning. Knowing <i>which</i> pairs and <i>when</i>, hours to
      days ahead, is precisely what makes avoidance possible.</p></div>
  </div>
</section>

<section>
  {_sec_head("02", "AUDIENCE", "Who it's for")}
  <div class="grid3">
    <div class="feature aud"><div class="aud-tag">OPERATORS</div><h3>Satellite operators</h3>
      <p>Constellation and single-asset teams (Starlink, OneWeb, Planet, and smaller fleets)
      who need a first-pass screen of their objects against the full catalogue.</p></div>
    <div class="feature aud"><div class="aud-tag">AGENCIES</div><h3>Space agencies</h3>
      <p>Teams like <b>NASA</b> and <b>ESA</b> running conjunction assessment — OrbitGuard
      mirrors the front half of the pipeline behind services such as CelesTrak SOCRATES
      and NASA CARA.</p></div>
    <div class="feature aud"><div class="aud-tag">ANALYSTS</div><h3>Analysts &amp; insurers</h3>
      <p>Anyone quantifying orbital risk: space-traffic researchers, debris analysts, and
      underwriters pricing on-orbit collision exposure.</p></div>
  </div>
</section>

<section>
  {_sec_head("03", "STATUS", "Today, and where it's going")}
  <div class="nowlater">
    <div class="nl-col now">
      <div class="nl-tag"><span class="dot live"></span>v1 — AVAILABLE NOW</div>
      <ul>
        <li>Pulls a live <b>CelesTrak</b> catalogue ({n_obj} objects this run)</li>
        <li>Propagates every object with SGP4 onto one shared clock</li>
        <li>Screens the whole population with a KD-tree — past the O(n²) wall</li>
        <li>Refines each flag to a sub-second <b>time of closest approach</b> and true <b>miss distance</b></li>
        <li>Ranks by a closing-speed × closeness <b>risk proxy</b></li>
        <li>Exports CSV + JSON + this interactive report</li>
      </ul>
    </div>
    <div class="nl-col later">
      <div class="nl-tag"><span class="dot next"></span>NEXT — IN DEVELOPMENT</div>
      <ul>
        <li><b>ML risk model</b> — a learned probability of collision trained on real
            Conjunction Data Messages (ESA Kelvins), replacing the geometric proxy</li>
        <li><b>Covariance &amp; uncertainty</b> — proper error ellipsoids, not point geometry</li>
        <li><b>Autonomy</b> — for top-risk events, suggest a small avoidance Δv and show the improved miss</li>
        <li><b>Higher-fidelity data</b> — Space-Track integration and operational validation</li>
        <li><b>Alerting</b> — per-operator watchlists and notifications</li>
      </ul>
    </div>
  </div>
  <p class="disclaimer">OrbitGuard v1 is a self-directed engineering project and a
  screening / analysis tool — not an operational or safety-certified system. Always
  validate against authoritative sources (CelesTrak SOCRATES, Space-Track) before any
  operational decision.</p>
</section>
"""


def _how_it_works() -> str:
    steps = [
        ("01", "Catalogue", "Download a CelesTrak group (active, starlink, stations…), cache "
         "the dated raw TLE snapshot, parse to satellites, skip malformed records, and "
         "de-duplicate by NORAD id.", "catalog.py"),
        ("02", "Propagate", "SGP4-propagate every object to every timestep into one "
         "(N × T × 3) position cube — all in a single inertial frame, the invariant that "
         "makes distances meaningful.", "propagate.py"),
        ("03", "Screen", "At each timestep build a scipy cKDTree and query pairs within the "
         "threshold. 16k objects would be ~130M brute-force pairs per step; the tree makes "
         "it milliseconds. Consecutive hits group into one event.", "screen.py"),
        ("04", "Refine", "Re-propagate just the two objects at 1-second cadence around each "
         "flag and fit a parabola to the separation curve — a sub-second TCA and a true miss "
         "distance (the coarse grid always over-estimates).", "refine.py"),
        ("05", "Rank", "Compute relative velocity at closest approach and score "
         "risk ∝ closing speed / (miss distance + ε), log-scaled to 0–100.", "risk.py"),
        ("06", "Report", "Emit a ranked CSV, a full JSON payload, and this self-contained "
         "interactive report.", "report.py"),
    ]
    items = []
    for num, title, body, mod in steps:
        items.append(
            f'<div class="step"><div class="step-num">{num}</div>'
            f'<div class="step-body"><h3>{title}<span class="mod">{mod}</span></h3>'
            f'<p>{body}</p></div></div>'
        )
    return f"""
<section>
  {_sec_head("", "PIPELINE", "How it works")}
  <p class="lead">One command runs the whole chain:</p>
  <div class="cmd"><span class="prompt">$</span> python src/screen.py --group active --hours 24 --threshold 10</div>
  <div class="flow"><span>CelesTrak TLEs</span><i>→</i><span>propagate</span><i>→</i>
  <span>KD-tree screen</span><i>→</i><span>refine TCA</span><i>→</i><span>risk rank</span>
  <i>→</i><span>report</span></div>
  <div class="steps">{''.join(items)}</div>
</section>
"""


def _roadmap() -> str:
    phases = [
        ("PHASE 0–2.5", "v1 — Conjunction screener", "done",
         "Live catalogue → propagate → screen → refine → risk-rank → report + dashboard. "
         "Validated: KD-tree equals brute force; refinement sharpens every flag."),
        ("PHASE 3", "ML risk model", "next",
         "Train on the ESA Kelvins Collision Avoidance Challenge CDM dataset to predict "
         "whether a conjunction escalates — replacing the geometric proxy with a learned "
         "probability of collision. (Scaffold already in src/orbitguard/ml/.)"),
        ("PHASE 4", "Autonomy", "future",
         "For high-risk events, propose a small avoidance Δv and show the resulting improved "
         "miss distance — closing the loop from detection to action."),
        ("PHASE 5", "Showcase", "future",
         "Polished repo, writeup, and public demo — the flagship artifact tying the whole "
         "trajectory together."),
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
  {_sec_head("", "TRAJECTORY", "Roadmap")}
  <p class="lead">v1 is the screening core. The fall phases add the ML and autonomy layers
  that turn a screener into a decision-support system.</p>
  <div class="timeline">{''.join(items)}</div>
</section>
"""


# --------------------------------------------------------------------------- #
# Page template — token replacement (no str.format), so CSS braces stay clean
# --------------------------------------------------------------------------- #
_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OrbitGuard — Orbital Collision-Avoidance</title>
<style>
:root { color-scheme: dark;
  --bg:#05070e; --bg1:#0a0e18; --bg2:#0d1220; --panel:#0b1120;
  --hair:rgba(150,170,210,.12); --hair2:rgba(150,170,210,.20);
  --ink:#eef2f8; --dim:#9aa7be; --faint:#5f6c85;
  --accent:#5cc8ff; --accent-ink:#04121e; --amber:#f5a524; --green:#34d399; --pink:#ff4d8d;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; color:var(--ink); font-family:var(--sans); line-height:1.6;
  -webkit-font-smoothing:antialiased; background-color:var(--bg);
  background-image:
    radial-gradient(1px 1px at 20% 30%, rgba(255,255,255,.35), transparent),
    radial-gradient(1px 1px at 70% 20%, rgba(255,255,255,.25), transparent),
    radial-gradient(1px 1px at 40% 70%, rgba(255,255,255,.22), transparent),
    radial-gradient(1px 1px at 85% 60%, rgba(255,255,255,.30), transparent),
    radial-gradient(1px 1px at 55% 45%, rgba(255,255,255,.18), transparent),
    radial-gradient(1200px 700px at 78% -12%, rgba(28,58,102,.45), transparent 60%);
  background-attachment:fixed; }
a { color:var(--accent); text-decoration:none; cursor:pointer; }

.mono { font-family:var(--mono); }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:7px; vertical-align:middle; }
.dot.live { background:var(--green); box-shadow:0 0 0 3px rgba(52,211,153,.18); animation:pulse 2.4s infinite; }
.dot.next { background:var(--accent); box-shadow:0 0 0 3px rgba(92,200,255,.18); }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.35;} }

/* nav */
.nav { position:sticky; top:0; z-index:50; backdrop-filter:blur(12px);
  background:rgba(5,7,14,.78); border-bottom:1px solid var(--hair); }
.nav-in { max-width:1120px; margin:0 auto; padding:0 24px; height:60px; display:flex; align-items:center; gap:24px; }
.brand { display:flex; align-items:center; gap:9px; margin-right:auto; font-weight:700; letter-spacing:.02em; }
.brand svg { color:var(--accent); }
.brand .g { color:var(--dim); font-weight:600; }
.brand .b { color:var(--ink); }
.tabs { display:flex; gap:2px; }
.tab { position:relative; padding:8px 14px; color:var(--dim); font-size:13.5px; font-weight:550; border-radius:8px; }
.tab:hover { color:var(--ink); }
.tab.active { color:var(--ink); }
.tab.active::after { content:""; position:absolute; left:14px; right:14px; bottom:-1px; height:2px;
  background:var(--accent); border-radius:2px; }

.wrap { max-width:1120px; margin:0 auto; padding:40px 24px 90px; }
.view { display:none; }
.view.active { display:block; animation:fade .4s ease; }
@keyframes fade { from{opacity:0; transform:translateY(8px);} to{opacity:1; transform:none;} }

section { margin-top:64px; }
section:first-child { margin-top:6px; }
h1,h2,h3 { letter-spacing:-.02em; }

/* section header w/ mono kicker + hairline */
.sec-head { border-top:1px solid var(--hair); padding-top:16px; margin-bottom:26px; }
.kicker { font-family:var(--mono); font-size:11px; letter-spacing:.22em; color:var(--faint); text-transform:uppercase; }
.sec-no { color:var(--accent); margin-right:12px; }
.sec-head h2 { font-size:27px; margin:8px 0 0; font-weight:680; }
.lead { color:#c4cee0; font-size:16.5px; max-width:720px; }

/* hero */
.hero { margin-top:14px; }
.hero-grid { display:grid; grid-template-columns:1.55fr 1fr; gap:46px; align-items:start; }
.eyebrow { font-family:var(--mono); font-size:11.5px; letter-spacing:.18em; text-transform:uppercase;
  color:var(--dim); display:flex; align-items:center; }
.display { font-size:56px; line-height:1.04; font-weight:800; margin:20px 0 20px; letter-spacing:-.035em; }
.uline { position:relative; white-space:nowrap; }
.uline::after { content:""; position:absolute; left:2px; right:6px; bottom:6px; height:10px;
  background:linear-gradient(90deg, rgba(245,165,36,.0), rgba(245,165,36,.42)); z-index:-1; border-radius:2px; }
.cta { display:flex; gap:12px; flex-wrap:wrap; margin-top:26px; }
.btn { display:inline-flex; align-items:center; gap:9px; padding:12px 20px; border-radius:11px;
  font-weight:600; font-size:14.5px; border:1px solid transparent; transition:transform .12s, filter .12s; }
.btn.primary { background:var(--accent); color:var(--accent-ink); }
.btn.primary:hover { filter:brightness(1.06); transform:translateY(-1px); }
.btn.primary .arr { transition:transform .15s; }
.btn.primary:hover .arr { transform:translateX(3px); }
.btn.ghost { border-color:var(--hair2); color:var(--ink); }
.btn.ghost:hover { background:var(--bg2); }

/* instrument readout panel */
.readout { position:relative; border:1px solid var(--hair2); border-radius:14px; background:
  linear-gradient(180deg, rgba(18,26,44,.7), rgba(9,13,22,.7)); padding:18px 18px 14px; }
.readout::before, .readout::after { content:""; position:absolute; width:11px; height:11px; border:1px solid var(--accent); opacity:.6; }
.readout::before { top:8px; left:8px; border-right:0; border-bottom:0; }
.readout::after { bottom:8px; right:8px; border-left:0; border-top:0; }
.ro-head { display:flex; justify-content:space-between; font-family:var(--mono); font-size:10.5px;
  letter-spacing:.2em; color:var(--faint); padding-bottom:12px; margin-bottom:6px; border-bottom:1px solid var(--hair); }
.ro-live { color:var(--green); }
.ro-row { display:flex; justify-content:space-between; align-items:baseline; padding:9px 0; border-bottom:1px solid var(--hair); }
.ro-row:last-of-type { border-bottom:0; }
.ro-lab { font-family:var(--mono); font-size:10.5px; letter-spacing:.14em; color:var(--faint); }
.ro-val { font-family:var(--mono); font-size:19px; color:var(--ink); font-weight:600; }
.ro-val i { font-style:normal; font-size:12px; color:var(--dim); margin-left:2px; }
.ro-foot { font-family:var(--mono); font-size:10px; letter-spacing:.12em; color:var(--faint); margin-top:12px; text-align:right; }

/* feature grid */
.grid3 { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; }
.feature { border:1px solid var(--hair); border-radius:14px; padding:22px; background:var(--panel);
  transition:border-color .15s, transform .15s; }
.feature:hover { border-color:var(--hair2); transform:translateY(-2px); }
.fic { width:38px; height:38px; color:var(--accent); margin-bottom:14px; }
.fic svg { width:38px; height:38px; }
.feature h3 { font-size:16.5px; margin:0 0 7px; }
.feature p { color:var(--dim); font-size:14px; margin:0; }
.aud-tag { font-family:var(--mono); font-size:10px; letter-spacing:.2em; color:var(--accent);
  border:1px solid var(--hair2); border-radius:6px; padding:3px 8px; display:inline-block; margin-bottom:12px; }

/* stats (live report) */
.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:1px;
  background:var(--hair); border:1px solid var(--hair); border-radius:14px; overflow:hidden; }
.stat { background:var(--panel); padding:20px 20px; }
.stat-val { font-family:var(--mono); font-size:26px; font-weight:600; color:var(--ink); }
.stat-val .unit { font-size:13px; color:var(--dim); margin-left:2px; }
.stat-lab { color:var(--faint); font-family:var(--mono); font-size:10.5px; letter-spacing:.13em;
  text-transform:uppercase; margin-top:6px; }

/* now / later */
.nowlater { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.nl-col { border:1px solid var(--hair); border-radius:14px; padding:22px; background:var(--panel); }
.nl-col.now { border-color:rgba(52,211,153,.28); }
.nl-col.later { border-color:rgba(92,200,255,.24); }
.nl-tag { font-family:var(--mono); font-size:11px; letter-spacing:.16em; font-weight:600; margin-bottom:14px; display:flex; align-items:center; }
.nl-col.now .nl-tag { color:var(--green); }
.nl-col.later .nl-tag { color:var(--accent); }
.nl-col ul { margin:0; padding:0; list-style:none; }
.nl-col li { position:relative; padding:8px 0 8px 20px; color:#cbd6ea; font-size:14px; border-bottom:1px solid var(--hair); }
.nl-col li:last-child { border-bottom:0; }
.nl-col li::before { content:""; position:absolute; left:2px; top:15px; width:6px; height:6px; border-radius:1px;
  background:var(--faint); }
.nl-col.now li::before { background:var(--green); }
.nl-col.later li::before { background:var(--accent); }
.disclaimer { color:var(--faint); font-size:12.5px; margin-top:20px; border-top:1px solid var(--hair);
  padding-top:16px; max-width:820px; }

/* how it works */
.cmd { font-family:var(--mono); font-size:13.5px; color:#cfe6ff; background:#080d18; border:1px solid var(--hair2);
  border-radius:10px; padding:14px 16px; margin:16px 0 18px; overflow-x:auto; white-space:nowrap; }
.cmd .prompt { color:var(--accent); margin-right:10px; }
.flow { display:flex; flex-wrap:wrap; align-items:center; gap:10px; font-family:var(--mono); font-size:12.5px;
  color:var(--dim); margin-bottom:26px; }
.flow span { border:1px solid var(--hair2); border-radius:7px; padding:5px 10px; background:var(--bg2); color:#bcd0ea; }
.flow i { color:var(--accent); font-style:normal; }
.steps { display:grid; gap:10px; }
.step { display:flex; gap:20px; border:1px solid var(--hair); border-radius:12px; padding:18px 20px; background:var(--panel); }
.step-num { font-family:var(--mono); font-size:15px; font-weight:600; color:var(--accent); min-width:26px; padding-top:1px; }
.step-body h3 { font-size:16px; margin:0 0 5px; }
.step-body p { color:var(--dim); font-size:14px; margin:0; }
.step .mod { font-family:var(--mono); font-size:11.5px; color:var(--faint); font-weight:400; margin-left:10px; }

/* timeline */
.timeline { position:relative; margin-left:6px; }
.phase { display:flex; gap:20px; padding:0 0 30px 6px; position:relative; }
.phase::before { content:""; position:absolute; left:6px; top:18px; bottom:-4px; width:1px; background:var(--hair2); }
.phase:last-child::before { display:none; }
.phase-dot { width:13px; height:13px; border-radius:50%; margin-top:5px; flex:none; z-index:1;
  background:var(--bg2); border:1px solid var(--faint); }
.phase.done .phase-dot { background:var(--green); border-color:var(--green); box-shadow:0 0 0 4px rgba(52,211,153,.14); }
.phase.next .phase-dot { background:var(--accent); border-color:var(--accent); box-shadow:0 0 0 4px rgba(92,200,255,.14); }
.phase-tag { font-family:var(--mono); font-size:10.5px; letter-spacing:.16em; color:var(--faint); }
.phase.done .phase-tag { color:var(--green); }
.phase.next .phase-tag { color:var(--accent); }
.phase-body h3 { font-size:17px; margin:5px 0 0; }
.phase-body p { color:var(--dim); font-size:14px; margin:5px 0 0; max-width:720px; }

/* panels + table */
.panel { border:1px solid var(--hair); border-radius:14px; padding:14px; background:var(--panel); margin-top:8px; }
.meta { color:var(--faint); font-size:12px; font-family:var(--mono); letter-spacing:.04em; margin:2px 0 16px; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
th,td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--hair); }
th { color:var(--faint); font-family:var(--mono); font-weight:500; font-size:10.5px; text-transform:uppercase; letter-spacing:.1em; }
td.num, th:nth-child(n+5) { text-align:right; }
tr:hover td { background:rgba(92,200,255,.05); }
.rank { color:var(--accent); font-family:var(--mono); font-weight:600; }
.norad { display:block; color:var(--faint); font-size:10.5px; font-family:var(--mono); margin-top:1px; }
.risk { display:inline-block; min-width:38px; text-align:center; padding:3px 9px; border-radius:7px;
  font-family:var(--mono); font-weight:600; font-size:12px;
  color:hsl(var(--rh),85%,72%); background:hsla(var(--rh),80%,45%,.14); border:1px solid hsla(var(--rh),80%,55%,.4); }
.note { color:var(--faint); font-size:12.5px; margin-top:12px; line-height:1.65; }

footer { margin-top:64px; color:var(--faint); font-size:12px; font-family:var(--mono); letter-spacing:.03em;
  border-top:1px solid var(--hair); padding-top:20px; line-height:1.8; }

@media (max-width:820px){
  .hero-grid{ grid-template-columns:1fr; gap:28px; } .display{ font-size:40px; }
  .nowlater{ grid-template-columns:1fr; } .tabs{ overflow-x:auto; } .nav-in{ gap:14px; }
  .wrap{ padding:28px 18px 70px; }
}
</style></head>
<body>
<nav class="nav"><div class="nav-in">
  <div class="brand">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="2.6"/><ellipse cx="12" cy="12" rx="10" ry="4.4" transform="rotate(28 12 12)"/></svg>
    <span><span class="g">Orbit</span><span class="b">Guard</span></span>
  </div>
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
      __REPORT_HEAD__
      <div class="meta">__META_LINE__</div>
      __CARDS__
    </section>
    <section>
      <div class="sec-head" style="border:0;padding:0;margin-bottom:14px">
        <div class="kicker"><span class="sec-no">◈</span>CLOSEST APPROACH · 3D GEOMETRY</div></div>
      <div class="panel">__FIGURE__</div>
      <div class="note">Blue and pink arcs are the two objects' orbit tracks in the ±12&nbsp;min around
      closest approach (Earth-centred inertial frame); the dotted amber line is the miss distance at the
      time of closest approach (TCA). Use the dropdown to switch events; drag to rotate, scroll to zoom.</div>
    </section>
    <section>
      <div class="sec-head" style="border:0;padding:0;margin-bottom:14px">
        <div class="kicker"><span class="sec-no">▤</span>RANKED CONJUNCTIONS</div></div>
      <div class="panel">__TABLE__</div>
      <div class="note">Risk is a v1 proxy = closing&nbsp;speed / (miss&nbsp;distance + 0.2&nbsp;km),
      log-scaled to 0–100 — higher means a small miss <em>and</em> a high closing speed. It is not a formal
      probability of collision; a covariance-based ML risk model is the next phase.</div>
    </section>
  </div>

  <div class="view" id="view-how">__HOW__</div>
  <div class="view" id="view-roadmap">__ROADMAP__</div>

  <footer>
    Generated __GENERATED__ UTC · catalogue snapshot __SNAPSHOT__ · __NOBJ__ objects · runtime __RUNTIME__s ·
    data © CelesTrak · OrbitGuard v__VERSION__<br>
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
        f"group={meta['group']}  ·  window={meta['hours']}h  ·  step={int(meta['step_s'])}s  ·  "
        f"threshold={meta['threshold_km']}km  ·  screened from {meta['start_utc']} UTC"
    )

    repl = {
        "__OVERVIEW__": _overview(summary, meta),
        "__REPORT_HEAD__": _sec_head("", "LIVE DATA", "Conjunction report"),
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
