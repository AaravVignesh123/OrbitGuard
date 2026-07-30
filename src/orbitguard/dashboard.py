"""Dashboard — a single self-contained, motion-rich HTML product site.

Four tabs (Overview / Live Report / How it works / Roadmap). The Live Report's
visualization is a real **WebGL globe** (Three.js): a NASA-textured Earth, a live
sample of the catalogue's satellites animated along their real propagated orbits,
and the top conjunctions highlighted with a miss-distance line. Three.js, the
OrbitControls, and the Earth texture are all **vendored and inlined**, so the file
stays fully self-contained — no CDN, no external requests.

Premium motion elsewhere (aurora, cursor spotlight, scroll reveals, count-ups,
parallax cards, live ticker, magnetic buttons) is gated behind
``prefers-reduced-motion``. Built with token replacement (not str.format) so the
CSS braces and the large inlined blobs stay intact.
"""

from __future__ import annotations

import html
import json
import os
from typing import List

_VENDOR = os.path.join(os.path.dirname(__file__), "vendor")
_SAMPLE_HINT = 260  # kept in sync with report.build_globe default for the caption


def _vendor(name: str) -> str:
    with open(os.path.join(_VENDOR, name)) as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# inline line-icons (stroke=currentColor)
# --------------------------------------------------------------------------- #
_IC_ORBIT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">'
             '<circle cx="12" cy="12" r="3.1"/>'
             '<ellipse cx="12" cy="12" rx="10" ry="4.3" transform="rotate(28 12 12)"/>'
             '<rect x="20.2" y="9.1" width="2" height="2" rx="0.4" transform="rotate(28 12 12)" '
             'fill="currentColor" stroke="none"/></svg>')
_IC_IMPACT = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">'
              '<path d="M3 12h4"/><path d="m5.5 9.5 2.5 2.5-2.5 2.5"/><path d="M21 12h-4"/>'
              '<path d="m18.5 9.5-2.5 2.5 2.5 2.5"/><path d="M12 4.5v2.4M12 17.1v2.4M8.6 8.6l1.7 1.7'
              'M15.4 8.6l-1.7 1.7"/><circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none"/></svg>')
_IC_CLOCK = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4">'
             '<circle cx="12" cy="12" r="8.4"/><path d="M12 7.4V12l3.1 1.9"/></svg>')


# --------------------------------------------------------------------------- #
# HTML fragments
# --------------------------------------------------------------------------- #
def _count(value, dec=0):
    if value is None:
        return "—"
    return f'<span class="count" data-count="{value}" data-dec="{dec}">0</span>'


def _readout_row(label, value, dec=0, unit=""):
    ui = f'<i>{unit}</i>' if unit else ''
    return (f'<div class="ro-row"><span class="ro-lab">{label}</span>'
            f'<span class="ro-val">{_count(value, dec)}{ui}</span></div>')


def _sec_head(no: str, kicker: str, title: str) -> str:
    return (f'<div class="sec-head" data-reveal><div class="kicker"><span class="sec-no">{no}</span>'
            f'{kicker}</div><h2>{title}</h2></div>')


def _stat_cards(summary: dict, meta: dict) -> str:
    def card(label, value, dec=0, unit=""):
        return (f'<div class="stat" data-reveal><div class="stat-val">{_count(value, dec)}'
                f'<span class="unit">{unit}</span></div><div class="stat-lab">{label}</div></div>')
    return (
        '<div class="stats">'
        + card("Objects screened", meta.get("n_objects", 0))
        + card("Candidate events", summary.get("n_events", 0))
        + card("Closest approach", summary.get("closest_km"), 2, " km")
        + card("Median miss", summary.get("median_miss_km"), 1, " km")
        + card("Fastest closing speed", summary.get("fastest_kms"), 1, " km/s")
        + "</div>"
    )


def _table(events: List[dict], top: int = 50) -> str:
    head = ("<tr><th>#</th><th>Object A</th><th>Object B</th><th>TCA (UTC)</th>"
            "<th>Miss (km)</th><th>Rel. speed (km/s)</th><th>Alt (km)</th><th>Risk</th></tr>")
    rows = []
    for e in events[:top]:
        score = e["risk_score"]
        hue = int(48 - 0.48 * min(score, 100))
        chip = f'<span class="risk" style="--rh:{hue}">{score:.0f}</span>'
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
    return (f"<table><thead>{head}</thead>"
            f"<tbody id='ogbody'>{''.join(rows)}</tbody></table>")


def _ticker(events: List[dict]) -> str:
    chips = []
    for e in events[:16]:
        chips.append(
            f'<span class="tk"><b>{html.escape(str(e["object_a"]))}</b>'
            f'<i>↔</i><b>{html.escape(str(e["object_b"]))}</b>'
            f'<u>{e["miss_km"]:.2f} km</u><s>{e["rel_speed_kms"]:.1f} km/s</s></span>'
        )
    row = "".join(chips)
    return (
        '<div class="ticker" data-reveal>'
        '<span class="tk-lab"><span class="dot live"></span>LIVE FEED · FLAGGED CONJUNCTIONS</span>'
        f'<div class="tk-mask"><div class="tk-track">{row}{row}</div></div></div>'
    )


def _orbit_svg() -> str:
    return (
        '<svg viewBox="0 0 120 120" fill="none">'
        '<defs><radialGradient id="eg" cx="50%" cy="40%" r="60%">'
        '<stop offset="0%" stop-color="#2b6cb0"/><stop offset="100%" stop-color="#0a1a2f"/></radialGradient></defs>'
        '<circle cx="60" cy="60" r="15" fill="url(#eg)" stroke="#2a4a72" stroke-width="0.5"/>'
        '<g class="orbit-a"><ellipse cx="60" cy="60" rx="46" ry="18" stroke="#5cc8ff" stroke-width="1" '
        'stroke-dasharray="3 4" opacity="0.7" transform="rotate(24 60 60)"/>'
        '<circle cx="106" cy="60" r="2.6" fill="#5cc8ff" transform="rotate(24 60 60)"/></g>'
        '<g class="orbit-b"><ellipse cx="60" cy="60" rx="42" ry="22" stroke="#ff4d8d" stroke-width="1" '
        'stroke-dasharray="3 4" opacity="0.6" transform="rotate(-46 60 60)"/>'
        '<circle cx="102" cy="60" r="2.6" fill="#ff4d8d" transform="rotate(-46 60 60)"/></g></svg>'
    )


def _overview(summary: dict, meta: dict, events: List[dict]) -> str:
    n_obj = f"{meta.get('n_objects', 0):,}"
    top = events[0] if events else None
    alert = ""
    if top:
        hue = int(48 - 0.48 * min(top["risk_score"], 100))
        alert = (
            '<div class="fc-wrap parallax fc-alert" data-depth="30"><div class="float-card fc-anim">'
            '<div class="fc-head"><span class="dot warn"></span>HIGHEST-RISK PASS</div>'
            f'<div class="fc-pair">{html.escape(str(top["object_a"]))} '
            f'<i>↔</i> {html.escape(str(top["object_b"]))}</div>'
            '<div class="fc-grid">'
            f'<div><span>MISS</span><b>{top["miss_km"]:.2f} km</b></div>'
            f'<div><span>CLOSING</span><b>{top["rel_speed_kms"]:.1f} km/s</b></div>'
            f'<div><span>RISK</span><b class="risk" style="--rh:{hue}">{top["risk_score"]:.0f}</b></div>'
            '</div></div></div>'
        )
    orbit = ('<div class="fc-wrap parallax fc-orbit" data-depth="16"><div class="float-card fc-anim orb">'
             + _orbit_svg() + '</div></div>')
    readout = (
        '<div class="fc-wrap parallax fc-main" data-depth="8"><div class="float-card fc-anim readout">'
        '<div class="ro-head"><span>LATEST RUN</span><span class="ro-live"><span class="dot live"></span>COMPLETE</span></div>'
        + _readout_row("OBJECTS SCREENED", meta.get("n_objects", 0))
        + _readout_row("CONJUNCTIONS FLAGGED", summary.get("n_events", 0))
        + _readout_row("CLOSEST PASS", summary.get("closest_km"), 2, " km")
        + _readout_row("FASTEST CLOSING", summary.get("fastest_kms"), 1, " km/s")
        + _readout_row("WINDOW", meta.get("hours"), 0, " h")
        + f'<div class="ro-foot">SOURCE · CelesTrak · SNAPSHOT {meta.get("snapshot_date","")}</div>'
        + '</div></div>'
    )

    return f"""
<section class="hero">
  <div class="hero-grid">
    <div class="hero-main">
      <div class="eyebrow" data-reveal><span class="dot live"></span>Space situational awareness · conjunction screener · v1</div>
      <h1 class="display" data-reveal>Catch the close approach<br>before it becomes a<span class="hl"> collision.</span></h1>
      <p class="lead" data-reveal>Low-Earth orbit now holds tens of thousands of tracked objects, and the
      count climbs every launch. <b>OrbitGuard</b> ingests a live catalogue, propagates every object
      forward in time, and surfaces the pairs headed for a dangerously close pass — with a precise time,
      miss distance, and risk rank.</p>
      <div class="cta" data-reveal>
        <a class="btn primary magnet" data-goto="report"><span>Open the live globe</span><span class="arr">→</span></a>
        <a class="btn ghost magnet" data-goto="how">How it works</a>
      </div>
      <div class="hero-cmd" data-reveal><span class="prompt">$</span>python src/screen.py --group active --hours 24 --threshold 10</div>
    </div>
    <div class="hero-stage" data-reveal>
      {readout}
      {alert}
      {orbit}
    </div>
  </div>
  {_ticker(events)}
</section>

<section>
  {_sec_head("01", "THE PROBLEM", "Why orbital conjunctions matter")}
  <div class="grid3">
    <div class="feature" data-reveal><div class="fic">{_IC_ORBIT}</div><h3>The sky is filling up</h3>
      <p>Mega-constellations added thousands of satellites in a few years. More objects means
      combinatorially more pairs that can cross paths.</p></div>
    <div class="feature" data-reveal><div class="fic">{_IC_IMPACT}</div><h3>Collisions cascade</h3>
      <p>A single impact spawns thousands of fragments — the Kessler effect — each one a new hazard.
      Prevention is orders of magnitude cheaper than cleanup.</p></div>
    <div class="feature" data-reveal><div class="fic">{_IC_CLOCK}</div><h3>Lead time is everything</h3>
      <p>A maneuver takes planning. Knowing <i>which</i> pairs and <i>when</i>, hours to days ahead, is
      precisely what makes avoidance possible.</p></div>
  </div>
</section>

<section>
  {_sec_head("02", "AUDIENCE", "Who it's for")}
  <div class="grid3">
    <div class="feature aud" data-reveal><div class="aud-tag">OPERATORS</div><h3>Satellite operators</h3>
      <p>Constellation and single-asset teams (Starlink, OneWeb, Planet, and smaller fleets) who need a
      first-pass screen of their objects against the full catalogue.</p></div>
    <div class="feature aud" data-reveal><div class="aud-tag">AGENCIES</div><h3>Space agencies</h3>
      <p>Teams like <b>NASA</b> and <b>ESA</b> running conjunction assessment — OrbitGuard mirrors the
      front half of the pipeline behind services such as CelesTrak SOCRATES and NASA CARA.</p></div>
    <div class="feature aud" data-reveal><div class="aud-tag">ANALYSTS</div><h3>Analysts &amp; insurers</h3>
      <p>Anyone quantifying orbital risk: space-traffic researchers, debris analysts, and underwriters
      pricing on-orbit collision exposure.</p></div>
  </div>
</section>

<section>
  {_sec_head("03", "STATUS", "Today, and where it's going")}
  <div class="nowlater">
    <div class="nl-col now" data-reveal>
      <div class="nl-tag"><span class="dot live"></span>v1 — AVAILABLE NOW</div>
      <ul>
        <li>Pulls a live <b>CelesTrak</b> catalogue ({n_obj} objects this run)</li>
        <li>Propagates every object with SGP4 onto one shared clock</li>
        <li>Screens the whole population with a KD-tree — past the O(n²) wall</li>
        <li>Refines each flag to a sub-second <b>time of closest approach</b> and true <b>miss distance</b></li>
        <li>Ranks by a closing-speed × closeness <b>risk proxy</b></li>
        <li>Exports CSV + JSON + this interactive globe</li>
      </ul>
    </div>
    <div class="nl-col later" data-reveal>
      <div class="nl-tag"><span class="dot next"></span>NEXT — IN DEVELOPMENT</div>
      <ul>
        <li><b>ML risk model</b> — a learned probability of collision trained on real Conjunction Data
            Messages (ESA Kelvins), replacing the geometric proxy</li>
        <li><b>Covariance &amp; uncertainty</b> — proper error ellipsoids, not point geometry</li>
        <li><b>Autonomy</b> — for top-risk events, suggest a small avoidance Δv and show the improved miss</li>
        <li><b>Higher-fidelity data</b> — Space-Track integration and operational validation</li>
        <li><b>Alerting</b> — per-operator watchlists and notifications</li>
      </ul>
    </div>
  </div>
  <p class="disclaimer" data-reveal>OrbitGuard v1 is a self-directed engineering project and a screening /
  analysis tool — not an operational or safety-certified system. Always validate against authoritative
  sources (CelesTrak SOCRATES, Space-Track) before any operational decision.</p>
</section>

<section class="ctaband" data-reveal>
  <div class="ctaband-in">
    <div><div class="kicker"><span class="sec-no">→</span>SEE IT LIVE</div>
      <h2>The catalogue, on a globe — screened and ranked.</h2></div>
    <a class="btn primary magnet" data-goto="report"><span>Open the live globe</span><span class="arr">→</span></a>
  </div>
</section>
"""


def _how_it_works() -> str:
    steps = [
        ("01", "Catalogue", "Download a CelesTrak group (active, starlink, stations…), cache the dated raw "
         "TLE snapshot, parse to satellites, skip malformed records, and de-duplicate by NORAD id.", "catalog.py"),
        ("02", "Propagate", "SGP4-propagate every object to every timestep into one (N × T × 3) position "
         "cube — all in a single inertial frame, the invariant that makes distances meaningful.", "propagate.py"),
        ("03", "Screen", "At each timestep build a scipy cKDTree and query pairs within the threshold. 16k "
         "objects would be ~130M brute-force pairs per step; the tree makes it milliseconds. Consecutive "
         "hits group into one event.", "screen.py"),
        ("04", "Refine", "Re-propagate just the two objects at 1-second cadence around each flag and fit a "
         "parabola to the separation curve — a sub-second TCA and a true miss distance (the coarse grid "
         "always over-estimates).", "refine.py"),
        ("05", "Rank", "Compute relative velocity at closest approach and score risk ∝ closing speed / "
         "(miss distance + ε), log-scaled to 0–100.", "risk.py"),
        ("06", "Report", "Emit a ranked CSV, a full JSON payload, and this self-contained interactive "
         "globe + report.", "report.py"),
    ]
    items = []
    for num, title, body, mod in steps:
        items.append(
            f'<div class="step" data-reveal><div class="step-num">{num}</div>'
            f'<div class="step-body"><h3>{title}<span class="mod">{mod}</span></h3><p>{body}</p></div></div>'
        )
    return f"""
<section>
  {_sec_head("", "PIPELINE", "How it works")}
  <p class="lead" data-reveal>One command runs the whole chain:</p>
  <div class="cmd" data-reveal><span class="prompt">$</span> python src/screen.py --group active --hours 24 --threshold 10</div>
  <div class="flow" data-reveal><span>CelesTrak TLEs</span><i>→</i><span>propagate</span><i>→</i>
  <span>KD-tree screen</span><i>→</i><span>refine TCA</span><i>→</i><span>risk rank</span><i>→</i><span>report</span></div>
  <div class="steps">{''.join(items)}</div>
</section>
"""


def _roadmap() -> str:
    phases = [
        ("PHASE 0–2.5", "v1 — Conjunction screener", "done",
         "Live catalogue → propagate → screen → refine → risk-rank → report + globe. Validated: KD-tree "
         "equals brute force; refinement sharpens every flag."),
        ("PHASE 3", "ML risk model", "next",
         "Train on the ESA Kelvins Collision Avoidance Challenge CDM dataset to predict whether a conjunction "
         "escalates — replacing the geometric proxy with a learned probability of collision. (Scaffold "
         "already in src/orbitguard/ml/.)"),
        ("PHASE 4", "Autonomy", "future",
         "For high-risk events, propose a small avoidance Δv and show the resulting improved miss distance — "
         "closing the loop from detection to action."),
        ("PHASE 5", "Showcase", "future",
         "Polished repo, writeup, and public demo — the flagship artifact tying the whole trajectory together."),
    ]
    items = []
    for tag, title, state, body in phases:
        items.append(
            f'<div class="phase {state}" data-reveal><div class="phase-dot"></div>'
            f'<div class="phase-body"><div class="phase-tag">{tag}</div><h3>{title}</h3><p>{body}</p></div></div>'
        )
    return f"""
<section>
  {_sec_head("", "TRAJECTORY", "Roadmap")}
  <p class="lead" data-reveal>v1 is the screening core. The fall phases add the ML and autonomy layers that
  turn a screener into a decision-support system.</p>
  <div class="timeline">{''.join(items)}</div>
</section>
"""


# --------------------------------------------------------------------------- #
# Page template
# --------------------------------------------------------------------------- #
_PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OrbitGuard — Orbital Collision-Avoidance</title>
<style>
:root { color-scheme: dark;
  --bg:#04060d; --bg1:#0a0e18; --bg2:#0d1220; --panel:rgba(13,18,32,.72);
  --hair:rgba(150,170,210,.12); --hair2:rgba(150,170,210,.22);
  --ink:#eef2f8; --dim:#9aa7be; --faint:#5f6c85;
  --accent:#5cc8ff; --accent-ink:#04121e; --violet:#8b7bff; --amber:#f5a524; --green:#34d399; --pink:#ff4d8d;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; color:var(--ink); font-family:var(--sans); line-height:1.6; background:var(--bg);
  -webkit-font-smoothing:antialiased; overflow-x:hidden; }
a { color:var(--accent); text-decoration:none; cursor:pointer; }

.bg { position:fixed; inset:0; z-index:-3; overflow:hidden; pointer-events:none;
  background-image:
    radial-gradient(1px 1px at 15% 25%, rgba(255,255,255,.35), transparent),
    radial-gradient(1px 1px at 65% 15%, rgba(255,255,255,.22), transparent),
    radial-gradient(1px 1px at 40% 65%, rgba(255,255,255,.20), transparent),
    radial-gradient(1px 1px at 85% 55%, rgba(255,255,255,.28), transparent),
    radial-gradient(1px 1px at 55% 40%, rgba(255,255,255,.16), transparent); }
.bg::before, .bg::after { content:""; position:absolute; width:70vw; height:70vw; border-radius:50%; filter:blur(120px); opacity:.5; }
.bg::before { background:radial-gradient(circle, rgba(46,90,180,.55), transparent 60%); top:-24vw; right:-14vw; animation:drift1 26s ease-in-out infinite; }
.bg::after { background:radial-gradient(circle, rgba(139,123,255,.34), transparent 60%); bottom:-28vw; left:-16vw; animation:drift2 32s ease-in-out infinite; }
@keyframes drift1 { 0%,100%{transform:translate(0,0) scale(1);} 50%{transform:translate(-6vw,5vw) scale(1.12);} }
@keyframes drift2 { 0%,100%{transform:translate(0,0) scale(1);} 50%{transform:translate(7vw,-4vw) scale(1.08);} }
#spot { position:fixed; width:520px; height:520px; border-radius:50%; z-index:-2; pointer-events:none;
  background:radial-gradient(circle, rgba(92,200,255,.10), transparent 65%); transform:translate(-50%,-50%); left:50%; top:20%; transition:opacity .4s; opacity:0; }

.mono { font-family:var(--mono); }
.dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:7px; vertical-align:middle; }
.dot.live { background:var(--green); box-shadow:0 0 0 3px rgba(52,211,153,.18); animation:pulse 2.4s infinite; }
.dot.next { background:var(--accent); box-shadow:0 0 0 3px rgba(92,200,255,.18); }
.dot.warn { background:var(--amber); box-shadow:0 0 0 3px rgba(245,165,36,.18); animation:pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.35;} }

.nav { position:sticky; top:0; z-index:50; backdrop-filter:blur(14px); background:rgba(4,6,13,.7); border-bottom:1px solid var(--hair); }
.nav-in { max-width:1120px; margin:0 auto; padding:0 24px; height:60px; display:flex; align-items:center; gap:24px; }
.brand { display:flex; align-items:center; gap:9px; margin-right:auto; font-weight:700; letter-spacing:.02em; }
.brand svg { color:var(--accent); } .brand .g { color:var(--dim); font-weight:600; } .brand .b { color:var(--ink); }
.tabs { display:flex; gap:2px; }
.tab { position:relative; padding:8px 14px; color:var(--dim); font-size:13.5px; font-weight:550; border-radius:8px; transition:color .2s; }
.tab:hover { color:var(--ink); } .tab.active { color:var(--ink); }
.tab.active::after { content:""; position:absolute; left:14px; right:14px; bottom:-1px; height:2px; background:var(--accent); border-radius:2px; box-shadow:0 0 10px rgba(92,200,255,.7); }

.wrap { max-width:1120px; margin:0 auto; padding:40px 24px 90px; }
.view { display:none; } .view.active { display:block; }
section { margin-top:72px; } section:first-child { margin-top:8px; }
h1,h2,h3 { letter-spacing:-.02em; }

[data-reveal]{ opacity:0; transform:translateY(26px); transition:opacity .8s cubic-bezier(.2,.7,.2,1), transform .8s cubic-bezier(.2,.7,.2,1); }
[data-reveal].in{ opacity:1; transform:none; }

.sec-head { border-top:1px solid var(--hair); padding-top:16px; margin-bottom:28px; }
.kicker { font-family:var(--mono); font-size:11px; letter-spacing:.22em; color:var(--faint); text-transform:uppercase; }
.sec-no { color:var(--accent); margin-right:12px; }
.sec-head h2 { font-size:28px; margin:8px 0 0; font-weight:700; }
.lead { color:#c4cee0; font-size:16.5px; max-width:720px; }

.hero { margin-top:20px; }
.hero-grid { display:grid; grid-template-columns:1.5fr 1fr; gap:44px; align-items:center; min-height:520px; }
.eyebrow { font-family:var(--mono); font-size:11.5px; letter-spacing:.18em; text-transform:uppercase; color:var(--dim); display:flex; align-items:center; }
.display { font-size:60px; line-height:1.03; font-weight:800; margin:22px 0 22px; letter-spacing:-.038em; }
.hl { position:relative; white-space:nowrap; color:#fff; }
.hl::after { content:""; position:absolute; left:2px; right:6px; bottom:7px; height:11px; z-index:-1; border-radius:3px; background:linear-gradient(90deg, rgba(245,165,36,0), rgba(245,165,36,.5)); }
.cta { display:flex; gap:12px; flex-wrap:wrap; margin-top:28px; }
.btn { display:inline-flex; align-items:center; gap:9px; padding:13px 22px; border-radius:12px; font-weight:600; font-size:14.5px; border:1px solid transparent; position:relative; overflow:hidden; will-change:transform; }
.btn.primary { background:linear-gradient(90deg,#63caff,#8b7bff); color:var(--accent-ink); box-shadow:0 10px 30px -10px rgba(92,200,255,.6); }
.btn.primary::after { content:""; position:absolute; top:0; left:-60%; width:40%; height:100%; background:linear-gradient(90deg, transparent, rgba(255,255,255,.55), transparent); transform:skewX(-20deg); animation:shimmer 4.5s ease-in-out infinite; }
@keyframes shimmer { 0%{left:-60%;} 40%,100%{left:130%;} }
.btn.primary .arr { transition:transform .18s; } .btn.primary:hover .arr { transform:translateX(4px); }
.btn.ghost { border-color:var(--hair2); color:var(--ink); background:rgba(255,255,255,.02); } .btn.ghost:hover { background:rgba(255,255,255,.06); }
.hero-cmd { font-family:var(--mono); font-size:12.5px; color:#9fb6d0; margin-top:22px; opacity:.85; } .hero-cmd .prompt { color:var(--accent); margin-right:8px; }

.hero-stage { position:relative; height:460px; }
.fc-wrap { position:absolute; will-change:transform; }
.float-card { border:1px solid var(--hair2); border-radius:16px; background:linear-gradient(180deg, rgba(18,26,44,.86), rgba(9,13,22,.86)); box-shadow:0 40px 80px -30px rgba(0,0,0,.85), inset 0 1px 0 rgba(255,255,255,.05); backdrop-filter:blur(8px); }
.fc-anim { animation:floaty 7s ease-in-out infinite; }
@keyframes floaty { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-12px);} }
.fc-main { right:0; top:30px; width:290px; z-index:2; } .fc-main .float-card { padding:16px 16px 12px; }
.fc-alert { left:-14px; top:236px; width:262px; z-index:4; } .fc-alert .fc-anim { animation-duration:6s; animation-delay:-1.5s; } .fc-alert .float-card { padding:15px 16px; }
.fc-orbit { right:150px; top:-6px; width:132px; z-index:1; } .fc-orbit .fc-anim { animation-duration:8s; animation-delay:-3s; } .fc-orbit .float-card { padding:6px; }
.orb svg { width:100%; display:block; }
.orbit-a { transform-origin:60px 60px; animation:spin 18s linear infinite; } .orbit-b { transform-origin:60px 60px; animation:spin 24s linear infinite reverse; }
@keyframes spin { to { transform:rotate(360deg); } }
.ro-head { display:flex; justify-content:space-between; font-family:var(--mono); font-size:10px; letter-spacing:.18em; color:var(--faint); padding-bottom:11px; margin-bottom:4px; border-bottom:1px solid var(--hair); }
.ro-live { color:var(--green); } .ro-row { display:flex; justify-content:space-between; align-items:baseline; padding:8px 0; border-bottom:1px solid var(--hair); } .ro-row:last-of-type { border-bottom:0; }
.ro-lab { font-family:var(--mono); font-size:10px; letter-spacing:.12em; color:var(--faint); }
.ro-val { font-family:var(--mono); font-size:18px; color:var(--ink); font-weight:600; } .ro-val i { font-style:normal; font-size:11px; color:var(--dim); margin-left:2px; }
.ro-foot { font-family:var(--mono); font-size:9px; letter-spacing:.1em; color:var(--faint); margin-top:10px; text-align:right; }
.fc-head { font-family:var(--mono); font-size:10px; letter-spacing:.16em; color:var(--amber); margin-bottom:10px; }
.fc-pair { font-size:14px; font-weight:600; margin-bottom:12px; line-height:1.35; } .fc-pair i { color:var(--faint); }
.fc-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; }
.fc-grid span { display:block; font-family:var(--mono); font-size:9px; letter-spacing:.1em; color:var(--faint); } .fc-grid b { font-family:var(--mono); font-size:14px; }

.ticker { margin-top:44px; border-top:1px solid var(--hair); border-bottom:1px solid var(--hair); padding:14px 0; display:flex; align-items:center; gap:18px; }
.tk-lab { font-family:var(--mono); font-size:10px; letter-spacing:.16em; color:var(--faint); white-space:nowrap; flex:none; }
.tk-mask { position:relative; overflow:hidden; flex:1; -webkit-mask-image:linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent); mask-image:linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent); }
.tk-track { display:flex; gap:26px; width:max-content; animation:scroll 48s linear infinite; } .ticker:hover .tk-track { animation-play-state:paused; }
@keyframes scroll { to { transform:translateX(-50%); } }
.tk { display:inline-flex; align-items:center; gap:9px; font-family:var(--mono); font-size:12px; color:var(--dim); white-space:nowrap; }
.tk b { color:#cfe0f4; font-weight:600; } .tk i { color:var(--faint); font-style:normal; } .tk u { color:var(--accent); text-decoration:none; } .tk s { color:var(--faint); text-decoration:none; }

.grid3 { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:16px; }
.feature { border:1px solid var(--hair); border-radius:14px; padding:22px; background:var(--panel); transition:border-color .2s, transform .2s, box-shadow .2s; }
.feature:hover { border-color:var(--hair2); transform:translateY(-3px); box-shadow:0 24px 50px -30px rgba(0,0,0,.8); }
.fic { width:38px; height:38px; color:var(--accent); margin-bottom:14px; } .fic svg { width:38px; height:38px; }
.feature h3 { font-size:16.5px; margin:0 0 7px; } .feature p { color:var(--dim); font-size:14px; margin:0; }
.aud-tag { font-family:var(--mono); font-size:10px; letter-spacing:.2em; color:var(--accent); border:1px solid var(--hair2); border-radius:6px; padding:3px 8px; display:inline-block; margin-bottom:12px; }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:1px; background:var(--hair); border:1px solid var(--hair); border-radius:14px; overflow:hidden; }
.stat { background:var(--bg2); padding:20px; } .stat-val { font-family:var(--mono); font-size:26px; font-weight:600; color:var(--ink); } .stat-val .unit { font-size:13px; color:var(--dim); margin-left:2px; }
.stat-lab { color:var(--faint); font-family:var(--mono); font-size:10.5px; letter-spacing:.13em; text-transform:uppercase; margin-top:6px; }

.nowlater { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.nl-col { border:1px solid var(--hair); border-radius:14px; padding:22px; background:var(--panel); } .nl-col.now { border-color:rgba(52,211,153,.28); } .nl-col.later { border-color:rgba(92,200,255,.24); }
.nl-tag { font-family:var(--mono); font-size:11px; letter-spacing:.16em; font-weight:600; margin-bottom:14px; display:flex; align-items:center; } .nl-col.now .nl-tag { color:var(--green); } .nl-col.later .nl-tag { color:var(--accent); }
.nl-col ul { margin:0; padding:0; list-style:none; }
.nl-col li { position:relative; padding:8px 0 8px 20px; color:#cbd6ea; font-size:14px; border-bottom:1px solid var(--hair); } .nl-col li:last-child { border-bottom:0; }
.nl-col li::before { content:""; position:absolute; left:2px; top:15px; width:6px; height:6px; border-radius:1px; background:var(--faint); } .nl-col.now li::before { background:var(--green); } .nl-col.later li::before { background:var(--accent); }
.disclaimer { color:var(--faint); font-size:12.5px; margin-top:20px; border-top:1px solid var(--hair); padding-top:16px; max-width:820px; }

.ctaband { margin-top:80px; border:1px solid var(--hair2); border-radius:20px; padding:36px 40px; position:relative; overflow:hidden; background:linear-gradient(120deg, rgba(46,90,180,.22), rgba(139,123,255,.16)); }
.ctaband-in { display:flex; align-items:center; justify-content:space-between; gap:24px; flex-wrap:wrap; } .ctaband h2 { font-size:26px; margin:8px 0 0; }

.cmd { font-family:var(--mono); font-size:13.5px; color:#cfe6ff; background:#080d18; border:1px solid var(--hair2); border-radius:10px; padding:14px 16px; margin:16px 0 18px; overflow-x:auto; white-space:nowrap; } .cmd .prompt { color:var(--accent); margin-right:10px; }
.flow { display:flex; flex-wrap:wrap; align-items:center; gap:10px; font-family:var(--mono); font-size:12.5px; color:var(--dim); margin-bottom:26px; } .flow span { border:1px solid var(--hair2); border-radius:7px; padding:5px 10px; background:var(--bg2); color:#bcd0ea; } .flow i { color:var(--accent); font-style:normal; }
.steps { display:grid; gap:10px; }
.step { display:flex; gap:20px; border:1px solid var(--hair); border-radius:12px; padding:18px 20px; background:var(--panel); transition:border-color .2s, transform .2s; } .step:hover { border-color:var(--hair2); transform:translateX(4px); }
.step-num { font-family:var(--mono); font-size:15px; font-weight:600; color:var(--accent); min-width:26px; padding-top:1px; } .step-body h3 { font-size:16px; margin:0 0 5px; } .step-body p { color:var(--dim); font-size:14px; margin:0; } .step .mod { font-family:var(--mono); font-size:11.5px; color:var(--faint); font-weight:400; margin-left:10px; }

.timeline { position:relative; margin-left:6px; }
.phase { display:flex; gap:20px; padding:0 0 30px 6px; position:relative; } .phase::before { content:""; position:absolute; left:6px; top:18px; bottom:-4px; width:1px; background:var(--hair2); } .phase:last-child::before { display:none; }
.phase-dot { width:13px; height:13px; border-radius:50%; margin-top:5px; flex:none; z-index:1; background:var(--bg2); border:1px solid var(--faint); } .phase.done .phase-dot { background:var(--green); border-color:var(--green); box-shadow:0 0 0 4px rgba(52,211,153,.14); } .phase.next .phase-dot { background:var(--accent); border-color:var(--accent); box-shadow:0 0 0 4px rgba(92,200,255,.14); }
.phase-tag { font-family:var(--mono); font-size:10.5px; letter-spacing:.16em; color:var(--faint); } .phase.done .phase-tag { color:var(--green); } .phase.next .phase-tag { color:var(--accent); }
.phase-body h3 { font-size:17px; margin:5px 0 0; } .phase-body p { color:var(--dim); font-size:14px; margin:5px 0 0; max-width:720px; }

/* globe */
.globe-wrap { position:relative; height:580px; border:1px solid var(--hair2); border-radius:16px; overflow:hidden;
  background:radial-gradient(120% 90% at 70% 10%, rgba(20,40,80,.4), #04070e 70%); margin-top:8px; }
#globe { position:absolute; inset:0; } #globe canvas { display:block; }
.ghud { position:absolute; z-index:3; font-family:var(--mono); pointer-events:none; }
.ghud-tl { top:14px; left:14px; max-width:280px; } .ghud-bl { bottom:14px; left:14px; }
#conjsel { pointer-events:auto; width:100%; background:rgba(8,13,24,.85); color:var(--ink); border:1px solid var(--hair2);
  border-radius:9px; padding:8px 10px; font-family:var(--mono); font-size:12px; outline:none; }
#conjsel:focus { border-color:var(--accent); }
.conjinfo { margin-top:10px; background:rgba(8,13,24,.8); border:1px solid var(--hair2); border-radius:11px; padding:12px 13px; backdrop-filter:blur(6px); }
.conjinfo .ci-lab { font-size:9.5px; letter-spacing:.16em; color:var(--faint); }
.conjinfo .ci-pair { font-size:12.5px; color:var(--ink); font-weight:600; margin:3px 0 9px; line-height:1.4; }
.conjinfo .ci-pair .a { color:var(--accent); } .conjinfo .ci-pair .b { color:var(--pink); }
.conjinfo .ci-grid { display:grid; grid-template-columns:1fr 1fr; gap:7px 12px; }
.conjinfo .ci-grid span { font-size:9px; letter-spacing:.1em; color:var(--faint); display:block; }
.conjinfo .ci-grid b { font-size:13px; color:var(--ink); }
.glegend { display:flex; flex-direction:column; gap:5px; background:rgba(8,13,24,.7); border:1px solid var(--hair); border-radius:10px; padding:9px 11px; }
.glegend span { font-size:10px; color:var(--dim); display:flex; align-items:center; gap:7px; }
.glegend .sw { width:9px; height:9px; border-radius:2px; display:inline-block; }
.globefallback { position:absolute; inset:0; z-index:2; display:flex; align-items:center; justify-content:center; color:var(--faint); font-family:var(--mono); font-size:12px; letter-spacing:.1em; }

.focusbar { display:flex; align-items:center; gap:10px; border:1px solid var(--hair2); border-radius:11px; background:var(--bg2); padding:10px 14px; margin:4px 0 12px; color:var(--faint); }
.focusbar svg { flex:none; color:var(--accent); }
.focusbar input { flex:1; background:transparent; border:0; outline:none; color:var(--ink); font-family:var(--mono); font-size:13px; letter-spacing:.01em; }
.focusbar input::placeholder { color:var(--faint); } .focusbar:focus-within { border-color:var(--accent); box-shadow:0 0 0 3px rgba(92,200,255,.12); }
.focusinfo { font-family:var(--mono); font-size:11px; color:var(--dim); white-space:nowrap; flex:none; }

.panel { border:1px solid var(--hair); border-radius:14px; padding:14px; background:var(--panel); margin-top:8px; }
.meta { color:var(--faint); font-size:12px; font-family:var(--mono); letter-spacing:.04em; margin:2px 0 16px; }
table { width:100%; border-collapse:collapse; font-size:13.5px; }
th,td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--hair); }
th { color:var(--faint); font-family:var(--mono); font-weight:500; font-size:10.5px; text-transform:uppercase; letter-spacing:.1em; }
td.num, th:nth-child(n+5) { text-align:right; }
tr:hover td { background:rgba(92,200,255,.05); }
.rank { color:var(--accent); font-family:var(--mono); font-weight:600; }
.norad { display:block; color:var(--faint); font-size:10.5px; font-family:var(--mono); margin-top:1px; }
.risk { display:inline-block; min-width:38px; text-align:center; padding:3px 9px; border-radius:7px; font-family:var(--mono); font-weight:600; font-size:12px; color:hsl(var(--rh),85%,72%); background:hsla(var(--rh),80%,45%,.14); border:1px solid hsla(var(--rh),80%,55%,.4); }
.note { color:var(--faint); font-size:12.5px; margin-top:12px; line-height:1.65; }

footer { margin-top:72px; color:var(--faint); font-size:12px; font-family:var(--mono); letter-spacing:.03em; border-top:1px solid var(--hair); padding-top:20px; line-height:1.8; }

@media (max-width:860px){
  .hero-grid{ grid-template-columns:1fr; gap:20px; min-height:0; } .display{ font-size:42px; }
  .hero-stage{ height:400px; margin-top:14px; } .fc-main{ right:auto; left:0; } .fc-orbit{ right:10px; }
  .nowlater{ grid-template-columns:1fr; } .tabs{ overflow-x:auto; } .nav-in{ gap:14px; } .wrap{ padding:28px 18px 70px; }
  .ctaband-in{ flex-direction:column; align-items:flex-start; } .globe-wrap{ height:460px; }
}
@media (prefers-reduced-motion: reduce){
  *{ animation:none!important; transition:none!important; }
  [data-reveal]{ opacity:1!important; transform:none!important; }
  .bg::before,.bg::after,#spot{ display:none; }
}
</style></head>
<body>
<div class="bg"></div><div id="spot"></div>
<nav class="nav"><div class="nav-in">
  <div class="brand">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <circle cx="12" cy="12" r="2.6"/><ellipse cx="12" cy="12" rx="10" ry="4.4" transform="rotate(28 12 12)"/></svg>
    <span><span class="g">Orbit</span><span class="b">Guard</span></span>
  </div>
  <div class="tabs">
    <a class="tab active" data-view="overview">Overview</a>
    <a class="tab" data-view="report">Live Globe</a>
    <a class="tab" data-view="how">How it works</a>
    <a class="tab" data-view="roadmap">Roadmap</a>
  </div>
</div></nav>

<div class="wrap">
  <div class="view active" id="view-overview">__OVERVIEW__</div>

  <div class="view" id="view-report">
    <section>
      __REPORT_HEAD__
      <div class="meta" data-reveal>__META_LINE__</div>
      __CARDS__
    </section>
    <section>
      <div class="sec-head" data-reveal style="border:0;padding:0;margin-bottom:14px">
        <div class="kicker"><span class="sec-no">◈</span>ORBITAL SITUATION · LIVE 3D GLOBE</div></div>
      <div class="globe-wrap" data-reveal>
        <div id="globe"></div>
        <div class="ghud ghud-tl">
          <select id="conjsel" aria-label="highlighted conjunction"></select>
          <div id="conjinfo" class="conjinfo"></div>
        </div>
        <div class="ghud ghud-bl glegend">
          <span><i class="sw" style="background:#5cc8ff"></i>catalogue objects (LEO)</span>
          <span><i class="sw" style="background:#5cc8ff"></i>conjunction · object A</span>
          <span><i class="sw" style="background:#ff4d8d"></i>conjunction · object B</span>
          <span><i class="sw" style="background:#f5a524"></i>miss distance</span>
        </div>
        <div id="globefallback" class="globefallback">Initializing 3D globe…</div>
      </div>
      <div class="note" data-reveal>A live sample of __GLOBECOUNT__ catalogue objects on their real
      SGP4-propagated orbits (Earth-centred inertial), animated along track; the highlighted pair is the
      selected conjunction with its amber miss-distance line. Drag to rotate, scroll to zoom. The Earth
      texture is illustrative — the frame is inertial, not geo-referenced to sub-satellite points.</div>
    </section>
    <section>
      <div class="sec-head" data-reveal style="border:0;padding:0;margin-bottom:14px">
        <div class="kicker"><span class="sec-no">▤</span>RANKED CONJUNCTIONS</div></div>
      <div class="focusbar" data-reveal>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
        <input id="ogfocus" type="text" autocomplete="off" spellcheck="false" placeholder="Focus on a satellite — name or NORAD id (e.g. STARLINK-6106 or 57154)">
        <span id="ogfocusinfo" class="focusinfo"></span>
      </div>
      <div class="panel" data-reveal>__TABLE__</div>
      <div class="note" data-reveal>Risk is a v1 proxy = closing&nbsp;speed / (miss&nbsp;distance + 0.2&nbsp;km),
      log-scaled to 0–100 — higher means a small miss <em>and</em> a high closing speed. It is not a formal
      probability of collision; a covariance-based ML risk model is the next phase.</div>
    </section>
  </div>

  <div class="view" id="view-how">__HOW__</div>
  <div class="view" id="view-roadmap">__ROADMAP__</div>

  <footer>
    Generated __GENERATED__ UTC · catalogue snapshot __SNAPSHOT__ · __NOBJ__ objects · runtime __RUNTIME__s ·
    data © CelesTrak · Earth texture © NASA · 3D via three.js · OrbitGuard v__VERSION__<br>
    A student-built screening tool — validate against CelesTrak SOCRATES before operational use.
  </footer>
</div>

<script>__THREE_JS__</script>
<script>__ORBITCONTROLS_JS__</script>
<script>
var OG_EVENTS = __EVENTS_JSON__;
var OG_GLOBE = __GLOBE_JSON__;
var OG_GEOM = __GEOM_JSON__;
var OG_EARTH_TEX = "data:image/jpeg;base64,__EARTH_TEX__";
</script>
<script>
(function(){
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var fmt = function(n, dec){ return dec>0 ? n.toFixed(dec) : Math.round(n).toLocaleString('en-US'); };

  // ---- per-satellite focus filter ----
  var body = document.getElementById('ogbody'), inp = document.getElementById('ogfocus'), info = document.getElementById('ogfocusinfo');
  function esc(s){ var d=document.createElement('div'); d.textContent=String(s); return d.innerHTML; }
  function rowHtml(e){
    var hue = Math.round(48 - 0.48*Math.min(e.rs,100));
    return '<tr><td class="rank">'+e.r+'</td><td>'+esc(e.a)+'<span class="norad">NORAD '+e.na+'</span></td>'+
      '<td>'+esc(e.b)+'<span class="norad">NORAD '+e.nb+'</span></td><td class="mono">'+e.t+'</td>'+
      '<td class="mono num">'+e.m.toFixed(3)+'</td><td class="mono num">'+e.v.toFixed(2)+'</td>'+
      '<td class="mono num">'+Math.round(e.al)+'</td><td><span class="risk" style="--rh:'+hue+'">'+Math.round(e.rs)+'</span></td></tr>';
  }
  function render(list, limit){ var out='', n=Math.min(list.length, limit||50); for(var i=0;i<n;i++) out+=rowHtml(list[i]); if(body) body.innerHTML=out; }
  function applyFocus(){
    if(!body || !OG_EVENTS) return;
    var q=(inp.value||'').trim().toLowerCase();
    if(!q){ render(OG_EVENTS,50); info.textContent = OG_EVENTS.length.toLocaleString('en-US')+' conjunctions · top 50 by risk'; return; }
    var digit=/^\d+$/.test(q);
    var m=OG_EVENTS.filter(function(e){ return digit ? (e.na==+q||e.nb==+q) : (String(e.a).toLowerCase().indexOf(q)>=0 || String(e.b).toLowerCase().indexOf(q)>=0); });
    render(m, 400);
    if(m.length){ var closest=Math.min.apply(null, m.map(function(e){return e.m;})); info.textContent = m.length+' approach'+(m.length>1?'es':'')+' · closest '+closest.toFixed(3)+' km'; }
    else { info.textContent = 'no conjunctions for “'+inp.value+'” this run'; }
  }
  if(inp){ inp.addEventListener('input', applyFocus); applyFocus(); }

  // ---- count-ups + reveals ----
  function countUp(el){ var target=parseFloat(el.dataset.count), dec=+el.dataset.dec||0;
    if(reduce){ el.textContent=fmt(target,dec); return; }
    var dur=1100, start=null;
    function step(ts){ if(!start)start=ts; var p=Math.min((ts-start)/dur,1), e=1-Math.pow(1-p,3); el.textContent=fmt(target*e,dec); if(p<1)requestAnimationFrame(step); }
    requestAnimationFrame(step);
  }
  var io=new IntersectionObserver(function(entries){ entries.forEach(function(en){ if(en.isIntersecting){ en.target.classList.add('in'); en.target.querySelectorAll('.count').forEach(countUp); io.unobserve(en.target);} }); },{ threshold:.12, rootMargin:'0px 0px -8% 0px' });
  document.querySelectorAll('[data-reveal]').forEach(function(el){ io.observe(el); });
  function revealView(view){ view.querySelectorAll('[data-reveal]').forEach(function(el){ if(!el.classList.contains('in')){ el.classList.add('in'); el.querySelectorAll('.count').forEach(countUp);} }); }

  // ---- tabs ----
  var tabs=document.querySelectorAll('.tab'), views=document.querySelectorAll('.view');
  function show(name){
    tabs.forEach(function(t){ t.classList.toggle('active', t.dataset.view===name); });
    views.forEach(function(v){ v.classList.toggle('active', v.id==='view-'+name); });
    var view=document.getElementById('view-'+name); if(view){ revealView(view); }
    if(name==='report'){ ensureGlobe(); if(globeApi.resize) setTimeout(globeApi.resize, 30); }
    if(history&&history.replaceState){ history.replaceState(null,'','#'+name); }
    window.scrollTo({top:0});
  }
  document.addEventListener('click', function(e){ var t=e.target.closest('[data-view]'), g=e.target.closest('[data-goto]'); if(t){show(t.dataset.view);} else if(g){show(g.dataset.goto);} });

  // ---- motion (cursor spotlight, parallax, magnetic) ----
  if(!reduce){
    var spot=document.getElementById('spot'), cards=[].slice.call(document.querySelectorAll('.parallax')), tx=0,ty=0,raf=false;
    window.addEventListener('mousemove', function(e){ spot.style.opacity=1; spot.style.left=e.clientX+'px'; spot.style.top=e.clientY+'px';
      tx=e.clientX/window.innerWidth-.5; ty=e.clientY/window.innerHeight-.5; if(!raf){ raf=true; requestAnimationFrame(function(){ cards.forEach(function(c){ var d=+c.dataset.depth||12; c.style.transform='translate3d('+(-tx*d)+'px,'+(-ty*d)+'px,0)'; }); raf=false; }); } });
    document.querySelectorAll('.magnet').forEach(function(b){ b.addEventListener('mousemove', function(e){ var r=b.getBoundingClientRect(); b.style.transform='translate('+((e.clientX-r.left-r.width/2)*.25)+'px,'+((e.clientY-r.top-r.height/2)*.35)+'px)'; }); b.addEventListener('mouseleave', function(){ b.style.transform=''; }); });
  }

  // ---- Three.js globe ----
  var globeApi = { resize:null };
  var globeReady = false;
  function ensureGlobe(){ if(globeReady) return; if(!window.THREE || !OG_GLOBE){ return; } globeReady=true; initGlobe(); }
  function initGlobe(){
    var host=document.getElementById('globe'); if(!host) return;
    var W=host.clientWidth||900, H=host.clientHeight||580;
    var scene=new THREE.Scene();
    var camera=new THREE.PerspectiveCamera(42, W/H, 0.01, 200); camera.position.set(0.2,1.3,3.3);
    var renderer=new THREE.WebGLRenderer({antialias:true, alpha:true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 2)); renderer.setSize(W,H);
    host.appendChild(renderer.domElement);
    var controls=new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping=true; controls.dampingFactor=.06; controls.rotateSpeed=.5; controls.enablePan=false;
    controls.minDistance=1.45; controls.maxDistance=8;
    if(!reduce){ controls.autoRotate=true; controls.autoRotateSpeed=.32; }

    scene.add(new THREE.AmbientLight(0x6f8ec2, .6));
    var sun=new THREE.DirectionalLight(0xffffff, 1.15); sun.position.set(5,3,5); scene.add(sun);

    // starfield
    var sp=[]; for(var i=0;i<1300;i++){ var u=Math.random()*2-1, th=Math.random()*Math.PI*2, s=Math.sqrt(1-u*u), r=40; sp.push(r*s*Math.cos(th), r*u, r*s*Math.sin(th)); }
    var sg=new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(sp,3));
    scene.add(new THREE.Points(sg, new THREE.PointsMaterial({color:0x9fb3d0, size:.055, transparent:true, opacity:.7})));

    // earth
    var tex=new THREE.TextureLoader().load(OG_EARTH_TEX, function(){ var f=document.getElementById('globefallback'); if(f) f.style.display='none'; });
    var earth=new THREE.Mesh(new THREE.SphereGeometry(1,64,64), new THREE.MeshPhongMaterial({map:tex, shininess:9, specular:0x1b2a44}));
    scene.add(earth);
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(1.03,48,48), new THREE.MeshBasicMaterial({color:0x3aa0ff, transparent:true, opacity:.10, side:THREE.BackSide})));

    var S=1/OG_GLOBE.earth_radius_km, band=[0x5cc8ff,0xf5a524,0x8b7bff];
    function toV(q){ return [q[0]*S, q[2]*S, -q[1]*S]; }   // ECI (x,y,z) -> three (x, z, -y), pole up

    // orbit lines (merged per band) + animated sat points
    var segs={0:[],1:[],2:[]}, paths=[], ppos=[], pcol=[];
    OG_GLOBE.sats.forEach(function(sat){
      var pts=sat.p.map(toV); paths.push(pts);
      for(var k=0;k<pts.length-1;k++){ var a=pts[k],b=pts[k+1]; segs[sat.b].push(a[0],a[1],a[2],b[0],b[1],b[2]); }
      var c=new THREE.Color(band[sat.b]); ppos.push(pts[0][0],pts[0][1],pts[0][2]); pcol.push(c.r,c.g,c.b);
    });
    [0,1,2].forEach(function(b){ if(!segs[b].length) return; var g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(segs[b],3)); scene.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({color:band[b], transparent:true, opacity:.14}))); });
    var pg=new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.Float32BufferAttribute(ppos,3)); pg.setAttribute('color', new THREE.Float32BufferAttribute(pcol,3));
    var satPoints=new THREE.Points(pg, new THREE.PointsMaterial({size:.026, vertexColors:true, transparent:true, opacity:.95}));
    scene.add(satPoints);

    // highlighted conjunction
    var hi=new THREE.Group(); scene.add(hi);
    function drawConj(g){
      while(hi.children.length){ hi.remove(hi.children[0]); }
      if(!g) return;
      function arc(a,color){ var v=a.map(function(q){ var t=toV(q); return new THREE.Vector3(t[0],t[1],t[2]); }); hi.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(v), new THREE.LineBasicMaterial({color:color}))); }
      arc(g.arc_a, 0x5cc8ff); arc(g.arc_b, 0xff4d8d);
      var ta=toV(g.point_a), tb=toV(g.point_b);
      var pa=new THREE.Vector3(ta[0],ta[1],ta[2]), pb=new THREE.Vector3(tb[0],tb[1],tb[2]);
      [[pa,0x5cc8ff],[pb,0xff4d8d]].forEach(function(m){ var d=new THREE.Mesh(new THREE.SphereGeometry(.013,16,16), new THREE.MeshBasicMaterial({color:m[1]})); d.position.copy(m[0]); hi.add(d); });
      var dl=new THREE.Line(new THREE.BufferGeometry().setFromPoints([pa,pb]), new THREE.LineDashedMaterial({color:0xf5a524, dashSize:.03, gapSize:.02})); dl.computeLineDistances(); hi.add(dl);
    }
    // dropdown + info
    var sel=document.getElementById('conjsel'), ci=document.getElementById('conjinfo');
    function updInfo(g){ if(!ci) return; if(!g){ ci.innerHTML=''; return; }
      ci.innerHTML='<div class="ci-lab">SELECTED CONJUNCTION</div>'+
        '<div class="ci-pair"><span class="a">'+esc(g.object_a)+'</span> ↔ <span class="b">'+esc(g.object_b)+'</span></div>'+
        '<div class="ci-grid"><div><span>MISS</span><b>'+g.miss_km.toFixed(2)+' km</b></div>'+
        '<div><span>CLOSING</span><b>'+g.rel_speed_kms.toFixed(1)+' km/s</b></div>'+
        '<div><span>RISK</span><b>'+Math.round(g.risk_score)+'</b></div>'+
        '<div><span>TCA</span><b style="font-size:11px">'+esc(g.tca_utc.slice(5,16))+'</b></div></div>';
    }
    if(sel && OG_GEOM && OG_GEOM.length){
      OG_GEOM.forEach(function(g,i){ var o=document.createElement('option'); o.value=i; o.textContent='#'+g.rank+'  '+g.object_a+' ↔ '+g.object_b+'  ('+g.miss_km.toFixed(2)+' km)'; sel.appendChild(o); });
      sel.addEventListener('change', function(){ var g=OG_GEOM[+sel.value]; drawConj(g); updInfo(g); });
      drawConj(OG_GEOM[0]); updInfo(OG_GEOM[0]);
    } else if(sel){ sel.style.display='none'; }

    var last=0, t=0;
    function tick(ts){
      requestAnimationFrame(tick);
      var dt=Math.min((ts-last)/1000||0, .05); last=ts;
      controls.update();
      if(!reduce){
        t += dt*4;
        var arr=satPoints.geometry.attributes.position.array;
        for(var i=0;i<paths.length;i++){ var p=paths[i], L=p.length; if(L<2) continue; var f=(t + i*0.7) % (L-1), k=Math.floor(f), fr=f-k, a=p[k], b=p[k+1];
          arr[i*3]=a[0]+(b[0]-a[0])*fr; arr[i*3+1]=a[1]+(b[1]-a[1])*fr; arr[i*3+2]=a[2]+(b[2]-a[2])*fr; }
        satPoints.geometry.attributes.position.needsUpdate=true;
        earth.rotation.y += dt*0.015;
      }
      renderer.render(scene,camera);
    }
    requestAnimationFrame(tick);

    globeApi.resize=function(){ var w=host.clientWidth,h=host.clientHeight; if(!w||!h) return; camera.aspect=w/h; camera.updateProjectionMatrix(); renderer.setSize(w,h); };
    window.addEventListener('resize', globeApi.resize);
  }

  var h=(location.hash||'').replace('#',''); if(h){ show(h); }
})();
</script>
</body></html>
"""


def build_dashboard(payload: dict, path: str) -> str:
    meta = payload["meta"]
    summary = payload["summary"]
    events = payload["events"]
    globe = payload.get("globe", {"earth_radius_km": 6371.0, "sats": [], "sample_n": 0})

    meta_line = (
        f"group={meta['group']}  ·  window={meta['hours']}h  ·  step={int(meta['step_s'])}s  ·  "
        f"threshold={meta['threshold_km']}km  ·  screened from {meta['start_utc']} UTC"
    )

    compact = [
        {"r": e["rank"], "a": e["object_a"], "na": e["norad_a"], "b": e["object_b"],
         "nb": e["norad_b"], "t": e["tca_utc"], "m": round(e["miss_km"], 3),
         "v": round(e["rel_speed_kms"], 2), "al": round(e["alt_km"], 0),
         "rs": round(e["risk_score"], 1)}
        for e in events
    ]

    # Small tokens first, large blobs last (avoids re-scanning big inlined content).
    small = {
        "__OVERVIEW__": _overview(summary, meta, events),
        "__REPORT_HEAD__": _sec_head("", "LIVE DATA", "Conjunction report"),
        "__META_LINE__": html.escape(meta_line),
        "__CARDS__": _stat_cards(summary, meta),
        "__TABLE__": _table(events),
        "__HOW__": _how_it_works(),
        "__ROADMAP__": _roadmap(),
        "__GLOBECOUNT__": str(globe.get("sample_n", 0)),
        "__GENERATED__": str(meta.get("generated_utc", "")),
        "__SNAPSHOT__": str(meta.get("snapshot_date", "")),
        "__NOBJ__": f"{meta.get('n_objects', 0):,}",
        "__RUNTIME__": str(meta.get("runtime_s", "")),
        "__VERSION__": str(meta.get("orbitguard_version", "1.0.0")),
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
