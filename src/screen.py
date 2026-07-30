#!/usr/bin/env python3
"""OrbitGuard CLI — one command, catalog to ranked conjunction report.

Examples
--------
    # full catalogue, 24 h, 10 km threshold
    python src/screen.py --group active --hours 24 --threshold 10

    # per-satellite threat list (operator view)
    python src/screen.py --group active --focus STARLINK-6106
    python src/screen.py --group active --focus 57154

    # continuous re-tracking: re-pull fresh TLEs and re-run every 3 h,
    # refreshing the hosted dashboard each cycle
    python src/screen.py --group active --hours 6 --watch 180 --docs

Outputs (under ./out by default):
    conjunctions_<timestamp>.csv   ranked table (pair, TCA, miss, risk)
    report_<timestamp>.json        full payload (feeds the dashboard)
    dashboard_<timestamp>.html      self-contained interactive dashboard
    dashboard_latest.html           stable copy for easy linking
    threats_<focus>.csv             (with --focus) the focal object's threat list
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
import time

# Make the package importable whether run as `python src/screen.py` or installed.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orbitguard import focus as _focus
from orbitguard import pipeline, report
from orbitguard.dashboard import build_dashboard


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="orbitguard",
        description="Screen a satellite catalog for close approaches and rank them by risk.",
    )
    p.add_argument("--group", default="active",
                   help="CelesTrak group: stations, active, starlink, ... (default: active)")
    p.add_argument("--hours", type=float, default=24.0,
                   help="Screening window length in hours (default: 24)")
    p.add_argument("--step", type=float, default=60.0, dest="step_s",
                   help="Coarse time step in seconds (default: 60)")
    p.add_argument("--threshold", type=float, default=10.0, dest="threshold_km",
                   help="Coarse screening distance in km (default: 10)")
    p.add_argument("--max-objects", type=int, default=None,
                   help="Cap catalog size (handy for quick runs)")
    p.add_argument("--focus", default=None,
                   help="Pivot the report onto one object: a name substring or NORAD id "
                        "(e.g. STARLINK-6106 or 57154). Prints and saves its threat list.")
    p.add_argument("--outdir", default="out", help="Output directory (default: out)")
    p.add_argument("--data-dir", default="data", help="TLE cache directory (default: data)")
    p.add_argument("--force-download", action="store_true",
                   help="Re-download the TLE snapshot even if today's is cached")
    p.add_argument("--watch", type=float, default=None, metavar="MINUTES",
                   help="Continuous mode: re-pull fresh TLEs and re-run every MINUTES minutes "
                        "(Ctrl-C to stop). Implies --force-download each cycle.")
    p.add_argument("--docs", action="store_true",
                   help="Also write docs/index.html (the GitHub Pages source) each run")
    p.add_argument("--no-dashboard", action="store_true",
                   help="Skip building the HTML dashboard")
    p.add_argument("--top-geometry", type=int, default=5,
                   help="How many top events to embed 3D geometry for (default: 5)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress logging")
    return p.parse_args(argv)


def _run_once(args, *, force_download: bool) -> None:
    result = pipeline.run(
        group=args.group,
        hours=args.hours,
        step_s=args.step_s,
        threshold_km=args.threshold_km,
        max_objects=args.max_objects,
        data_dir=args.data_dir,
        force_download=force_download,
        verbose=not args.quiet,
    )

    report.print_summary(result.ranked, result.meta)

    os.makedirs(args.outdir, exist_ok=True)
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    csv_path = os.path.join(args.outdir, f"conjunctions_{stamp}.csv")
    json_path = os.path.join(args.outdir, f"report_{stamp}.json")

    report.write_csv(result.ranked, csv_path)
    payload = report.build_json(
        result.ranked, meta=result.meta,
        sats_by_index=result.sats_by_index, top_geometry=args.top_geometry,
    )
    report.write_json(payload, json_path)
    # Stable 'latest' copies (fixed filenames for the dashboard, watch loop,
    # and the ML bootstrap generator).
    report.write_csv(result.ranked, os.path.join(args.outdir, "conjunctions_latest.csv"))
    report.write_json(payload, os.path.join(args.outdir, "report_latest.json"))
    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")

    # Optional per-object (operator) view.
    if args.focus:
        _report_focus(result.ranked, args.focus, args.outdir)

    if not args.no_dashboard:
        html_path = os.path.join(args.outdir, f"dashboard_{stamp}.html")
        build_dashboard(payload, html_path)
        latest = os.path.join(args.outdir, "dashboard_latest.html")
        build_dashboard(payload, latest)
        print(f"Wrote {html_path}")
        print(f"Wrote {latest}  (open this in a browser)")
        if args.docs:
            os.makedirs("docs", exist_ok=True)
            build_dashboard(payload, os.path.join("docs", "index.html"))
            report.write_csv(result.ranked, os.path.join("docs", "sample_conjunctions.csv"))
            print("Wrote docs/index.html  (GitHub Pages source)")


def _report_focus(ranked, query, outdir) -> None:
    hits = _focus.threats_to(ranked, query)
    print("\n" + "-" * 74)
    if not hits:
        print(f"FOCUS '{query}': no conjunctions found for that object in this run.")
        print("-" * 74)
        return
    s = _focus.summarize_focus(ranked, query)
    print(f"FOCUS '{query}' — {s['n_threats']} threatening approaches | "
          f"closest {s['closest_km']:.3f} km | fastest {s['fastest_kms']:.2f} km/s | "
          f"worst partner: {s['worst_partner']}")
    print("-" * 74)
    df = report.to_dataframe(hits)
    show = df.head(15)[["rank", "object_a", "object_b", "tca_utc", "miss_km",
                        "rel_speed_kms", "risk_score"]]
    print(show.to_string(index=False))
    safe = "".join(c if c.isalnum() else "_" for c in query)[:40]
    path = os.path.join(outdir, f"threats_{safe}.csv")
    report.write_csv(hits, path)
    print(f"\nWrote {path}")


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.watch:
        interval = max(1.0, args.watch) * 60.0
        print(f"[watch] continuous mode — re-running every {args.watch:g} min. Ctrl-C to stop.")
        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"\n===== cycle {cycle} @ {_dt.datetime.utcnow():%Y-%m-%d %H:%M:%S} UTC =====")
                try:
                    _run_once(args, force_download=True)  # always pull the freshest TLEs
                except Exception as exc:  # keep the watcher alive across transient failures
                    print(f"[watch] cycle failed: {exc}")
                print(f"[watch] sleeping {args.watch:g} min ...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[watch] stopped.")
        return 0

    _run_once(args, force_download=args.force_download)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
