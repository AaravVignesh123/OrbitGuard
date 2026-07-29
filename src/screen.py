#!/usr/bin/env python3
"""OrbitGuard CLI — one command, catalog to ranked conjunction report.

Examples
--------
    python src/screen.py --group active --hours 24 --threshold 10
    python src/screen.py --group starlink --hours 12 --threshold 5 --max-objects 2000
    python src/screen.py --group stations --hours 48 --no-dashboard

Outputs (under ./out by default):
    conjunctions_<timestamp>.csv   ranked table (pair, TCA, miss, risk)
    report_<timestamp>.json        full payload (feeds the dashboard)
    dashboard_<timestamp>.html      self-contained interactive dashboard
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys

# Make the package importable whether run as `python src/screen.py` or installed.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    p.add_argument("--outdir", default="out", help="Output directory (default: out)")
    p.add_argument("--data-dir", default="data", help="TLE cache directory (default: data)")
    p.add_argument("--force-download", action="store_true",
                   help="Re-download the TLE snapshot even if today's is cached")
    p.add_argument("--no-dashboard", action="store_true",
                   help="Skip building the HTML dashboard")
    p.add_argument("--top-geometry", type=int, default=5,
                   help="How many top events to embed 3D geometry for (default: 5)")
    p.add_argument("--quiet", action="store_true", help="Suppress progress logging")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    result = pipeline.run(
        group=args.group,
        hours=args.hours,
        step_s=args.step_s,
        threshold_km=args.threshold_km,
        max_objects=args.max_objects,
        data_dir=args.data_dir,
        force_download=args.force_download,
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
    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")

    if not args.no_dashboard:
        html_path = os.path.join(args.outdir, f"dashboard_{stamp}.html")
        build_dashboard(payload, html_path)
        # Also keep a stable 'latest' copy for easy linking.
        latest = os.path.join(args.outdir, "dashboard_latest.html")
        build_dashboard(payload, latest)
        print(f"Wrote {html_path}")
        print(f"Wrote {latest}  (open this in a browser)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
