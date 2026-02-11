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

    # Generate animated HTML player and static fallback
    import base64
    import json as _json

    with open(png_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    trace_json = _json.dumps(trace)
    config_desc = cfg.get("_description", "")
    config_name = os.path.basename(args.config)

    html_path = os.path.join(args.output_dir, "index.html")
    with open(html_path, "w") as f:
        f.write(_build_animation_html(
            trace_json, img_b64, config_desc, config_name,
            args.mode, len(trace["frames"]), kwargs["steps"],
            _format_config(trace["config"]),
        ))
    print(f"HTML:  {html_path}")


def _build_animation_html(trace_json, img_b64, desc, config_name,
                          mode, num_frames, steps, config_pre):
    """Return a self-contained HTML string with an animated clock-walk player."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clock Walk — {config_name}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, sans-serif; max-width: 820px;
         margin: 0 auto; padding: 1rem; background: #1a1a2e; color: #eee; }}
  canvas {{ display: block; margin: 0 auto; border-radius: 8px;
           background: #0f0f23; max-width: 100%; }}
  .controls {{ display: flex; align-items: center; gap: 0.5rem;
              justify-content: center; margin: 0.8rem 0; flex-wrap: wrap; }}
  button {{ background: #16213e; color: #eee; border: 1px solid #444;
           border-radius: 4px; padding: 0.4rem 1rem; cursor: pointer;
           font-size: 0.95rem; }}
  button:hover {{ background: #1a365d; }}
  input[type=range] {{ flex: 1; min-width: 120px; max-width: 400px; }}
  .info {{ font-size: 0.82rem; color: #aaa; text-align: center; }}
  .desc {{ font-style: italic; color: #ccc; text-align: center; margin: 0.5rem 0; }}
  .speed {{ font-size: 0.8rem; color: #aaa; min-width: 3em; text-align: center; }}
  #fallback {{ display: none; width: 100%; border-radius: 8px; }}
  pre  {{ background: #16213e; padding: 0.8rem; border-radius: 6px;
          overflow-x: auto; font-size: 0.8rem; }}
  details {{ margin-top: 0.8rem; font-size: 0.85rem; color: #aaa; }}
</style>
</head>
<body>
<h1 style="text-align:center; font-size:1.3rem;">Clock Walk Animation</h1>
<p class="desc">{desc}</p>
<canvas id="c" width="600" height="600"></canvas>
<img id="fallback" src="data:image/png;base64,{img_b64}" alt="Clock walk static">
<div class="controls">
  <button id="play">Pause</button>
  <button id="restart">Restart</button>
  <input id="scrub" type="range" min="0" max="1" step="1" value="0">
  <span id="counter" class="info">0 / 0</span>
</div>
<div class="controls">
  <button id="slower">Slower</button>
  <span id="speedLabel" class="speed">1x</span>
  <button id="faster">Faster</button>
</div>
<div class="info">
  Config: <code>{config_name}</code> &middot; Mode: <code>{mode}</code>
  &middot; Frames: {num_frames} &middot; Steps: {steps}
</div>
<details><summary>Trace config</summary><pre>{config_pre}</pre></details>

<script>
(function() {{
  const TRACE = {trace_json};
  const labels = TRACE.labels;
  const frames = TRACE.frames;   // [step, posIndex, tagValue]
  const config = TRACE.config;
  const n = labels.length;

  const TAG_STYLE = {{
    normal:           {{ color: "#888888", r: 3 }},
    sample:           {{ color: "#4A90D9", r: 4 }},
    first_visit:      {{ color: "#2ECC40", r: 6 }},
    teleport:         {{ color: "#FF4136", r: 6 }},
    reversal:         {{ color: "#FF851B", r: 5 }},
    stay:             {{ color: "#B10DC9", r: 5 }},
    attract_approach: {{ color: "#FFDC00", r: 5 }},
  }};

  const canvas = document.getElementById("c");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2, ringR = W * 0.37;

  const scrub = document.getElementById("scrub");
  const counter = document.getElementById("counter");
  const playBtn = document.getElementById("play");
  const speedLabel = document.getElementById("speedLabel");
  scrub.max = Math.max(frames.length - 1, 0);

  let frameIdx = 0;
  let playing = true;
  let speed = 1;
  const speeds = [0.25, 0.5, 1, 2, 4, 8];
  let speedIdx = 2;

  function labelAngle(i) {{
    return Math.PI / 2 - 2 * Math.PI * i / n;
  }}

  function drawRing() {{
    ctx.clearRect(0, 0, W, H);
    // ring
    ctx.beginPath();
    for (let i = 0; i <= n; i++) {{
      const a = labelAngle(i % n);
      const x = cx + ringR * Math.cos(a);
      const y = cy - ringR * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }}
    ctx.strokeStyle = "#555";
    ctx.lineWidth = 1;
    ctx.stroke();

    // labels
    ctx.fillStyle = "#ddd";
    ctx.font = "bold 16px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const lr = ringR * 1.14;
    for (let i = 0; i < n; i++) {{
      const a = labelAngle(i);
      ctx.fillText(String(labels[i]), cx + lr * Math.cos(a), cy - lr * Math.sin(a));
    }}

    // attractor circles
    const att = config.attractors || [];
    ctx.strokeStyle = "#FF4136";
    ctx.lineWidth = 2;
    att.forEach(v => {{
      const idx = labels.indexOf(v);
      if (idx < 0) return;
      const a = labelAngle(idx);
      ctx.beginPath();
      ctx.arc(cx + ringR * Math.cos(a), cy - ringR * Math.sin(a), 12, 0, 2 * Math.PI);
      ctx.stroke();
    }});
  }}

  function drawDot(pos, tag, alpha) {{
    const s = TAG_STYLE[tag] || TAG_STYLE.normal;
    const a = labelAngle(pos);
    const jitter = (Math.random() - 0.5) * 6;
    const x = cx + (ringR + jitter) * Math.cos(a);
    const y = cy - (ringR + jitter) * Math.sin(a);
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.arc(x, y, s.r * 1.3, 0, 2 * Math.PI);
    ctx.fillStyle = s.color;
    ctx.fill();
    ctx.globalAlpha = 1;
  }}

  // Highlight the current position with a pulsing ring
  function drawCursor(pos) {{
    const a = labelAngle(pos);
    const x = cx + ringR * Math.cos(a);
    const y = cy - ringR * Math.sin(a);
    ctx.beginPath();
    ctx.arc(x, y, 16, 0, 2 * Math.PI);
    ctx.strokeStyle = "#00e5ff";
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }}

  function renderFrame(upTo) {{
    drawRing();
    // draw all previous dots with slight fade
    for (let i = 0; i <= upTo; i++) {{
      const [t, pos, tag] = frames[i];
      const alpha = (i === upTo) ? 1.0 : Math.max(0.25, 1 - (upTo - i) / 60);
      drawDot(pos, tag, alpha);
    }}
    // cursor on current
    if (upTo >= 0 && upTo < frames.length) {{
      drawCursor(frames[upTo][1]);
    }}
    counter.textContent = (upTo + 1) + " / " + frames.length;
    scrub.value = upTo;
  }}

  // Animation loop
  let lastTime = 0;
  const baseInterval = 120; // ms between frames at 1x

  function tick(ts) {{
    if (playing && frames.length > 0) {{
      const interval = baseInterval / speed;
      if (ts - lastTime >= interval) {{
        lastTime = ts;
        frameIdx++;
        if (frameIdx >= frames.length) {{
          frameIdx = frames.length - 1;
          playing = false;
          playBtn.textContent = "Play";
        }}
        renderFrame(frameIdx);
      }}
    }}
    requestAnimationFrame(tick);
  }}

  // Controls
  playBtn.addEventListener("click", () => {{
    if (frameIdx >= frames.length - 1) frameIdx = 0;
    playing = !playing;
    playBtn.textContent = playing ? "Pause" : "Play";
  }});
  document.getElementById("restart").addEventListener("click", () => {{
    frameIdx = 0;
    playing = true;
    playBtn.textContent = "Pause";
    renderFrame(0);
  }});
  scrub.addEventListener("input", () => {{
    frameIdx = parseInt(scrub.value, 10);
    renderFrame(frameIdx);
  }});
  document.getElementById("slower").addEventListener("click", () => {{
    speedIdx = Math.max(0, speedIdx - 1);
    speed = speeds[speedIdx];
    speedLabel.textContent = speed + "x";
  }});
  document.getElementById("faster").addEventListener("click", () => {{
    speedIdx = Math.min(speeds.length - 1, speedIdx + 1);
    speed = speeds[speedIdx];
    speedLabel.textContent = speed + "x";
  }});

  // Init
  if (frames.length === 0) {{
    document.getElementById("fallback").style.display = "block";
    canvas.style.display = "none";
  }} else {{
    renderFrame(0);
    requestAnimationFrame(tick);
  }}
}})();
</script>
</body>
</html>"""


def _format_config(config):
    import json
    return json.dumps(config, indent=2)


if __name__ == "__main__":
    main()
