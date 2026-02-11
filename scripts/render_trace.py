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

    # Generate animated GIF
    gif_path = os.path.join(args.output_dir, "clockwalk.gif")
    _render_animated_gif(trace, gif_path)
    print(f"GIF:   {gif_path}")


def _render_animated_gif(trace, gif_path, dpi=100, frame_ms=120, max_gif_frames=200):
    """Render the trace as an animated GIF that plays on any device.

    To keep file size reasonable, if the trace has more frames than
    *max_gif_frames*, we sample evenly across the timeline.
    """
    import io
    import math
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from PIL import Image

    from clockwalk.capture import EventTag

    labels = trace["labels"]
    config = trace["config"]
    frames = trace["frames"]
    n = len(labels)

    # Subsample frames if there are too many
    if len(frames) > max_gif_frames:
        indices = [int(i * (len(frames) - 1) / (max_gif_frames - 1))
                   for i in range(max_gif_frames)]
        sampled = [frames[i] for i in indices]
    else:
        sampled = list(frames)

    # Pre-compute angles
    def label_angle(idx):
        return math.pi / 2 - 2 * math.pi * idx / n

    angles = [label_angle(i) for i in range(n)]
    ring_r = 1.0
    label_r = 1.15

    # Event tag colours
    tag_style = {
        EventTag.NORMAL.value:           {"color": "#888888", "s": 9},
        EventTag.SAMPLE.value:           {"color": "#4A90D9", "s": 16},
        EventTag.FIRST_VISIT.value:      {"color": "#2ECC40", "s": 50},
        EventTag.TELEPORT.value:         {"color": "#FF4136", "s": 50},
        EventTag.REVERSAL.value:         {"color": "#FF851B", "s": 36},
        EventTag.STAY.value:             {"color": "#B10DC9", "s": 36},
        EventTag.ATTRACT_APPROACH.value: {"color": "#FFDC00", "s": 36},
    }
    default_style = {"color": "#888888", "s": 9}

    attractors = config.get("attractors", [])
    pil_frames = []

    # Build the cumulative list of dots for each GIF frame
    # Map sampled frames back to the original frame list for cumulative display
    cumulative = []
    orig_idx = 0
    for si, sf in enumerate(sampled):
        # Add all original frames up to and including this sampled frame
        while orig_idx < len(frames) and frames[orig_idx] != sf:
            cumulative.append(frames[orig_idx])
            orig_idx += 1
        if orig_idx < len(frames):
            cumulative.append(frames[orig_idx])
            orig_idx += 1

        fig, ax = plt.subplots(figsize=(5, 5))

        # Draw ring
        ring_x = [ring_r * math.cos(a) for a in angles]
        ring_y = [ring_r * math.sin(a) for a in angles]
        ax.plot(ring_x + [ring_x[0]], ring_y + [ring_y[0]],
                color="#CCCCCC", linewidth=1, zorder=1)

        # Draw labels
        for i, lab in enumerate(labels):
            lx = label_r * math.cos(angles[i])
            ly = label_r * math.sin(angles[i])
            ax.text(lx, ly, str(lab), ha="center", va="center",
                    fontsize=11, fontweight="bold", zorder=5)

        # Mark attractors
        for a_val in attractors:
            if a_val in labels:
                idx = labels.index(a_val)
                ax.plot(ring_x[idx], ring_y[idx], marker="o", markersize=16,
                        markerfacecolor="none", markeredgecolor="#FF4136",
                        markeredgewidth=2, zorder=3)

        # Plot all cumulative dots with fading
        total = len(cumulative)
        for di, (t, pos, tag_val) in enumerate(cumulative):
            style = tag_style.get(tag_val, default_style)
            a = angles[pos]
            jitter = 0.02 * ((t % 5) - 2)
            fx = (ring_r + jitter) * math.cos(a)
            fy = (ring_r + jitter) * math.sin(a)
            alpha = max(0.2, 1 - (total - 1 - di) / 40) if total > 1 else 1.0
            ax.plot(fx, fy, marker="o", color=style["color"],
                    markersize=max(3, style["s"] ** 0.5),
                    alpha=alpha, zorder=4,
                    markeredgecolor="black", markeredgewidth=0.3)

        # Cursor on current position
        cur_pos = sf[1]
        ca = angles[cur_pos]
        ax.plot(ring_r * math.cos(ca), ring_r * math.sin(ca),
                marker="o", markersize=18,
                markerfacecolor="none", markeredgecolor="#00e5ff",
                markeredgewidth=2.5, zorder=6)

        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect("equal")
        ax.set_title(f"Clock Walk — frame {si + 1}/{len(sampled)}", fontsize=11)
        ax.axis("off")
        fig.tight_layout()

        # Render to PIL Image
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
        plt.close(fig)
        buf.seek(0)
        pil_frames.append(Image.open(buf).copy())

    if not pil_frames:
        return

    # Hold on the last frame longer so it doesn't loop immediately
    last_frame_ms = 2000
    durations = [frame_ms] * (len(pil_frames) - 1) + [last_frame_ms]

    pil_frames[0].save(
        gif_path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=durations,
        loop=0,
    )


def _format_config(config):
    import json
    return json.dumps(config, indent=2)


if __name__ == "__main__":
    main()
