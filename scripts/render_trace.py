#!/usr/bin/env python3
"""Generate a clock-walk trace and render it to PNG (headless).

Intended for CI / GitHub Actions but works locally too.

Usage:
    python scripts/render_trace.py --config data/7_inertia_vs_attractor_tug.json
    python scripts/render_trace.py --config data/7_inertia_vs_attractor_tug.json --mode full --steps 500
"""

import argparse
import os
import sys

# Use non-interactive backend before any other matplotlib import
import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from clockwalk.animate import build_trace, write_trace, render_clock_face
from clockwalk.config import load_config_from_file


def main():
    parser = argparse.ArgumentParser(description="Render a clock-walk trace to PNG.")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    parser.add_argument("--mode", default="event", choices=["event", "nth", "full"])
    parser.add_argument("--nth", type=int, default=10)
    parser.add_argument("--steps", type=int, default=None, help="Override step count")
    parser.add_argument("--output-dir", default="output", help="Directory for outputs")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    cfg = load_config_from_file(args.config)
    kwargs = {
        "inertia_p": cfg["inertia"],
        "novelty_bonus": cfg["novelty"],
        "attractors": cfg["attractors"],
        "attract_strength": cfg["attract_strength"],
        "steps": args.steps or cfg["steps"],
        "stay_p": cfg["stay_p"],
        "teleport_p": cfg["teleport_p"],
    }

    trace = build_trace(mode=args.mode, nth=args.nth, **kwargs)

    trace_path = os.path.join(args.output_dir, "trace.json")
    write_trace(trace, trace_path)
    print(f"Trace: {trace_path} ({len(trace['frames'])} frames)")

    fig, ax = render_clock_face(trace, show=False)
    png_path = os.path.join(args.output_dir, "clockwalk.png")
    fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Image: {png_path}")

    # Also generate a self-contained HTML page for easy phone viewing
    import base64
    with open(png_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    html_path = os.path.join(args.output_dir, "index.html")
    config_desc = cfg.get("_description", "")
    with open(html_path, "w") as f:
        f.write(f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clock Walk — {os.path.basename(args.config)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 800px;
         margin: 0 auto; padding: 1rem; background: #1a1a2e; color: #eee; }}
  img  {{ width: 100%; border-radius: 8px; }}
  .meta {{ font-size: 0.85rem; color: #aaa; margin-top: 1rem; }}
  .desc {{ font-style: italic; color: #ccc; margin: 0.5rem 0; }}
  pre  {{ background: #16213e; padding: 0.8rem; border-radius: 6px;
          overflow-x: auto; font-size: 0.8rem; }}
</style>
</head>
<body>
<h1>Clock Walk Trace</h1>
<p class="desc">{config_desc}</p>
<img src="data:image/png;base64,{img_b64}" alt="Clock walk visualization">
<div class="meta">
  <p>Config: <code>{os.path.basename(args.config)}</code> &middot;
     Mode: <code>{args.mode}</code> &middot;
     Frames: {len(trace['frames'])} &middot;
     Steps: {kwargs['steps']}</p>
  <details><summary>Trace config</summary>
    <pre>{_format_config(trace['config'])}</pre>
  </details>
</div>
</body>
</html>""")
    print(f"HTML:  {html_path}")


def _format_config(config):
    import json
    return json.dumps(config, indent=2)


if __name__ == "__main__":
    main()
