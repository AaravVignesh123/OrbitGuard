"""Dashboard — a single self-contained HTML file you can open or share.

We build one interactive 3D scene (Earth + the top events' orbit arcs and their
close-approach points, switchable via a dropdown) with Plotly, inline the Plotly
library so the file has zero external dependencies, and wrap it in a styled page
with summary stat cards and the ranked conjunction table. No web server needed —
double-click the file.
"""

from __future__ import annotations

import html
import json
from typing import List

import numpy as np
import plotly.graph_objects as go

_EARTH_RADIUS_KM = 6371.0


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
            x=ex, y=ey, z=ez,
            showscale=False,
            colorscale=[[0, "#0b2545"], [1, "#13315c"]],
            opacity=0.85,
            hoverinfo="skip",
            name="Earth",
            lighting=dict(ambient=0.6, diffuse=0.6),
        )
    )

    per_event = 5  # arc_a, arc_b, pt_a, pt_b, connector
    for gi, g in enumerate(geometry):
        vis = gi == 0
        arc_a = np.array(g["arc_a"])
        arc_b = np.array(g["arc_b"])
        pa = np.array(g["point_a"])
        pb = np.array(g["point_b"])

        fig.add_trace(go.Scatter3d(
            x=arc_a[:, 0], y=arc_a[:, 1], z=arc_a[:, 2],
            mode="lines", line=dict(color="#4cc9f0", width=4),
            name=g["object_a"], visible=vis, hoverinfo="name",
        ))
        fig.add_trace(go.Scatter3d(
            x=arc_b[:, 0], y=arc_b[:, 1], z=arc_b[:, 2],
            mode="lines", line=dict(color="#f72585", width=4),
            name=g["object_b"], visible=vis, hoverinfo="name",
        ))
        fig.add_trace(go.Scatter3d(
            x=[pa[0]], y=[pa[1]], z=[pa[2]],
            mode="markers", marker=dict(size=5, color="#4cc9f0"),
            name=g["object_a"] + " @ TCA", visible=vis, hoverinfo="name",
        ))
        fig.add_trace(go.Scatter3d(
            x=[pb[0]], y=[pb[1]], z=[pb[2]],
            mode="markers", marker=dict(size=5, color="#f72585"),
            name=g["object_b"] + " @ TCA", visible=vis, hoverinfo="name",
        ))
        fig.add_trace(go.Scatter3d(
            x=[pa[0], pb[0]], y=[pa[1], pb[1]], z=[pa[2], pb[2]],
            mode="lines+text", line=dict(color="#ffd166", width=6, dash="dot"),
            text=["", f"{g['miss_km']:.2f} km"], textposition="middle right",
            textfont=dict(color="#ffd166", size=13),
            name="miss distance", visible=vis, hoverinfo="text",
        ))

    # Dropdown to switch events. Earth (trace 0) always visible.
    buttons = []
    n_traces = 1 + per_event * len(geometry)
    for gi, g in enumerate(geometry):
        visible = [False] * n_traces
        visible[0] = True
        for t in range(per_event):
            visible[1 + gi * per_event + t] = True
        label = f"#{g['rank']}  {g['object_a']} ↔ {g['object_b']}  ({g['miss_km']:.2f} km)"
        buttons.append(dict(
            label=label, method="update",
            args=[{"visible": visible}],
        ))

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
            aspectmode="data",
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
        height=560,
    )
    return fig


def _stat_cards(summary: dict) -> str:
    def card(label, value, unit=""):
        return (
            f'<div class="card"><div class="card-value">{value}'
            f'<span class="unit">{unit}</span></div>'
            f'<div class="card-label">{label}</div></div>'
        )

    closest = summary.get("closest_km")
    fastest = summary.get("fastest_kms")
    median = summary.get("median_miss_km")
    return (
        '<div class="cards">'
        + card("Candidate events", summary.get("n_events", 0))
        + card("Closest approach", f"{closest:.2f}" if closest is not None else "—", " km")
        + card("Median miss", f"{median:.1f}" if median is not None else "—", " km")
        + card("Fastest closing speed", f"{fastest:.1f}" if fastest is not None else "—", " km/s")
        + "</div>"
    )


def _table(events: List[dict], top: int = 25) -> str:
    head = (
        "<tr><th>#</th><th>Object A</th><th>Object B</th><th>TCA (UTC)</th>"
        "<th>Miss (km)</th><th>Rel. speed (km/s)</th><th>Alt (km)</th><th>Risk</th></tr>"
    )
    rows = []
    for e in events[:top]:
        score = e["risk_score"]
        # Color the risk chip by score.
        hue = int(120 - 1.2 * min(score, 100))  # green->red
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
            f"<td>{chip}</td>"
            "</tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OrbitGuard — Conjunction Report</title>
<style>
:root {{ color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:#060a14; color:#e8eef7;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:32px 20px 64px; }}
header h1 {{ margin:0 0 4px; font-size:30px; letter-spacing:-0.02em; }}
header h1 .g {{ color:#4cc9f0; }}
.tag {{ color:#8899b0; font-size:14px; margin-bottom:2px; }}
.meta {{ color:#6b7c96; font-size:13px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  margin-top:8px; line-height:1.6; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:14px; margin:24px 0; }}
.card {{ background:linear-gradient(180deg,#0e1626,#0b1220); border:1px solid #1b2942;
  border-radius:14px; padding:18px 20px; }}
.card-value {{ font-size:30px; font-weight:650; color:#fff; }}
.card-value .unit {{ font-size:15px; color:#8899b0; font-weight:400; margin-left:3px; }}
.card-label {{ color:#8899b0; font-size:13px; margin-top:4px; }}
section {{ margin-top:32px; }}
h2 {{ font-size:18px; margin:0 0 12px; color:#cdd8ea; font-weight:600; }}
.panel {{ background:#0a111e; border:1px solid #1b2942; border-radius:16px; padding:14px; }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid #16233b; }}
th {{ color:#8899b0; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
tr:hover td {{ background:#0e1830; }}
.rank {{ color:#4cc9f0; font-weight:700; }}
.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:#cdd8ea; }}
.norad {{ display:block; color:#5b6b85; font-size:11px; font-family:ui-monospace,monospace; }}
.risk {{ display:inline-block; min-width:34px; text-align:center; padding:3px 8px;
  border-radius:8px; border:1px solid; font-weight:700; font-size:12px; color:#fff; }}
.note {{ color:#6b7c96; font-size:12.5px; margin-top:10px; line-height:1.6; }}
footer {{ margin-top:40px; color:#5b6b85; font-size:12px; border-top:1px solid #16233b; padding-top:16px; }}
a {{ color:#4cc9f0; }}
</style></head>
<body><div class="wrap">
<header>
  <div class="tag">Autonomous orbital collision-avoidance · v{version}</div>
  <h1><span class="g">Orbit</span>Guard — Conjunction Report</h1>
  <div class="meta">{meta_line}</div>
</header>
{cards}
<section>
  <h2>Top conjunction — 3D close-approach geometry</h2>
  <div class="panel">{figure}</div>
  <div class="note">Blue and pink arcs are the two objects' orbit tracks in the ±12 min
  around closest approach (Earth-centred inertial frame). The dotted gold line is the
  miss distance at the time of closest approach (TCA). Use the dropdown to switch events;
  drag to rotate, scroll to zoom.</div>
</section>
<section>
  <h2>Ranked conjunctions</h2>
  <div class="panel">{table}</div>
  <div class="note">Risk is a v1 proxy = closing&nbsp;speed / (miss&nbsp;distance + 0.2&nbsp;km),
  log-scaled to 0–100 — higher means a small miss <em>and</em> a high closing speed.
  It is not a formal probability of collision; a covariance-based ML risk model is the
  next phase.</div>
</section>
<footer>
  Generated {generated} UTC · catalog snapshot {snapshot} · {n_objects} objects ·
  runtime {runtime}s · data © CelesTrak. Validate against CelesTrak SOCRATES before
  operational use.
</footer>
</div></body></html>
"""


def build_dashboard(payload: dict, path: str) -> str:
    meta = payload["meta"]
    fig = _build_figure(payload.get("geometry", []))
    # Inline Plotly so the file is fully self-contained (works offline / as artifact).
    fig_html = fig.to_html(include_plotlyjs=True, full_html=False,
                           config={"displayModeBar": False})

    meta_line = (
        f"group={meta['group']} · window={meta['hours']}h · step={int(meta['step_s'])}s · "
        f"threshold={meta['threshold_km']}km · screened from {meta['start_utc']} UTC"
    )
    page = _PAGE.format(
        version=meta.get("orbitguard_version", "1.0.0"),
        meta_line=html.escape(meta_line),
        cards=_stat_cards(payload["summary"]),
        figure=fig_html,
        table=_table(payload["events"]),
        generated=meta.get("generated_utc", ""),
        snapshot=meta.get("snapshot_date", ""),
        n_objects=meta.get("n_objects", ""),
        runtime=meta.get("runtime_s", ""),
    )
    with open(path, "w") as fh:
        fh.write(page)
    return path
