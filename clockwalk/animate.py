"""
Animation driver and trace I/O for clock-walk visualisation.

This module provides:

- **build_trace** — run a single simulation with a chosen capture mode and
  return a trace dict containing the config, labels, and captured frames.
- **write_trace / load_trace** — serialise/deserialise traces as JSON files.
- **render_clock_face** — (requires matplotlib) replay a trace on a circular
  clock-face plot with distinct visual treatments per event type.

Usage from the command line::

    python -m clockwalk.animate --config data/3_single_strong_attractor.json \\
                                --mode event --output trace.json
    python -m clockwalk.animate --replay trace.json
"""

import json
import math
import sys

from clockwalk.capture import EventTag, FullCapture, NthCapture, EventCapture
from clockwalk.walk import run_staleness_winner
from clockwalk.config import DEFAULTS

LABELS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


# ------------------------------------------------------------------ #
# Trace I/O                                                           #
# ------------------------------------------------------------------ #

def write_trace(trace: dict, path: str):
    """Write a trace dict to *path* as JSON.

    The trace dict must contain ``config``, ``labels``, and ``frames``.
    Frame tags are stored as their string values for readability.
    """
    serialisable = {
        "config": trace["config"],
        "labels": trace["labels"],
        "frames": [
            [t, pos, (tag if isinstance(tag, str) else tag)]
            for t, pos, tag in trace["frames"]
        ],
    }
    with open(path, "w") as f:
        json.dump(serialisable, f, indent=2)


def load_trace(path: str) -> dict:
    """Load a trace dict from a JSON file written by :func:`write_trace`."""
    with open(path) as f:
        data = json.load(f)
    data["frames"] = [tuple(f) for f in data["frames"]]
    return data


# ------------------------------------------------------------------ #
# build_trace helper                                                  #
# ------------------------------------------------------------------ #

def build_trace(mode="event", nth=10,
                inertia_p=None, novelty_bonus=None,
                attractors=None, attract_strength=None,
                steps=None, stay_p=None, teleport_p=None,
                start_index=0, labels=None):
    """Run one simulation and return the trace dict.

    Parameters
    ----------
    mode : str
        ``"full"``, ``"nth"``, or ``"event"``.
    nth : int
        Sample interval for ``"nth"`` mode.
    """
    labels = labels or list(LABELS)
    inertia_p = inertia_p if inertia_p is not None else DEFAULTS["inertia"]
    novelty_bonus = novelty_bonus if novelty_bonus is not None else DEFAULTS["novelty"]
    attractors = attractors if attractors is not None else list(DEFAULTS["attractors"])
    attract_strength = attract_strength if attract_strength is not None else DEFAULTS["attract_strength"]
    steps = steps if steps is not None else DEFAULTS["steps"]
    stay_p = stay_p if stay_p is not None else DEFAULTS["stay_p"]
    teleport_p = teleport_p if teleport_p is not None else DEFAULTS["teleport_p"]

    if mode == "full":
        cap = FullCapture()
    elif mode == "nth":
        cap = NthCapture(n=nth)
    elif mode == "event":
        cap = EventCapture(labels=labels, attractors=attractors)
    else:
        raise ValueError(f"Unknown capture mode: {mode!r}")

    run_staleness_winner(
        labels, start_index,
        inertia_p, novelty_bonus,
        attractors, attract_strength,
        steps, stay_p, teleport_p,
        on_step=cap,
    )

    config = {
        "capture_mode": mode,
        "inertia_p": inertia_p,
        "novelty_bonus": novelty_bonus,
        "attractors": attractors,
        "attract_strength": attract_strength,
        "steps": steps,
        "stay_p": stay_p,
        "teleport_p": teleport_p,
        "start_index": start_index,
    }
    if mode == "nth":
        config["nth"] = nth

    return {
        "config": config,
        "labels": labels,
        "frames": [(t, pos, tag.value) for t, pos, tag in cap.frames],
    }


# ------------------------------------------------------------------ #
# Clock-face renderer (matplotlib)                                    #
# ------------------------------------------------------------------ #

# Visual vocabulary — maps EventTag values to rendering parameters.
EVENT_STYLE = {
    EventTag.NORMAL.value:           {"color": "#888888", "marker": "o",  "size": 3,  "label": "normal"},
    EventTag.SAMPLE.value:           {"color": "#4A90D9", "marker": "o",  "size": 4,  "label": "sample"},
    EventTag.FIRST_VISIT.value:      {"color": "#2ECC40", "marker": "*",  "size": 10, "label": "first visit"},
    EventTag.TELEPORT.value:         {"color": "#FF4136", "marker": "X",  "size": 10, "label": "teleport"},
    EventTag.REVERSAL.value:         {"color": "#FF851B", "marker": "D",  "size": 8,  "label": "reversal"},
    EventTag.STAY.value:             {"color": "#B10DC9", "marker": "s",  "size": 8,  "label": "stay"},
    EventTag.ATTRACT_APPROACH.value: {"color": "#FFDC00", "marker": "^",  "size": 8,  "label": "attract"},
}


def _label_angle(idx, n):
    """Return the angle (radians) for clock position *idx* on a ring of *n*."""
    return math.pi / 2 - 2 * math.pi * idx / n


def render_clock_face(trace: dict, ax=None, show=True):
    """Draw the trace on a clock-face plot.

    Parameters
    ----------
    trace : dict
        As returned by :func:`build_trace` or :func:`load_trace`.
    ax : matplotlib Axes, optional
        Axes to draw on.  Created if *None*.
    show : bool
        Call ``plt.show()`` when done.
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    labels = trace["labels"]
    config = trace["config"]
    frames = trace["frames"]
    n = len(labels)

    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 8))
    else:
        fig = ax.figure

    # Draw clock ring
    ring_r = 1.0
    label_r = 1.15
    angles = [_label_angle(i, n) for i in range(n)]

    ring_x = [ring_r * math.cos(a) for a in angles]
    ring_y = [ring_r * math.sin(a) for a in angles]
    ax.plot(ring_x + [ring_x[0]], ring_y + [ring_y[0]],
            color="#CCCCCC", linewidth=1, zorder=1)

    # Draw position labels
    for i, lab in enumerate(labels):
        lx = label_r * math.cos(angles[i])
        ly = label_r * math.sin(angles[i])
        ax.text(lx, ly, str(lab), ha="center", va="center",
                fontsize=12, fontweight="bold", zorder=5)

    # Mark attractors
    attractors = config.get("attractors", [])
    for a in attractors:
        if a in labels:
            idx = labels.index(a)
            ax.plot(ring_x[idx], ring_y[idx], marker="o", markersize=18,
                    markerfacecolor="none", markeredgecolor="#FF4136",
                    markeredgewidth=2, zorder=3)

    # Plot frames by event type
    plotted_tags = set()
    for t, pos, tag_val in frames:
        style = EVENT_STYLE.get(tag_val, EVENT_STYLE[EventTag.NORMAL.value])
        a = angles[pos]
        # Slight radial jitter based on time for visual separation
        jitter = 0.02 * ((t % 5) - 2)
        fx = (ring_r + jitter) * math.cos(a)
        fy = (ring_r + jitter) * math.sin(a)
        ax.plot(fx, fy, marker=style["marker"], color=style["color"],
                markersize=style["size"], zorder=4,
                markeredgecolor="black", markeredgewidth=0.3)
        plotted_tags.add(tag_val)

    # Legend — only for tags actually present
    handles = []
    for tag_val in sorted(plotted_tags):
        style = EVENT_STYLE.get(tag_val, EVENT_STYLE[EventTag.NORMAL.value])
        handles.append(mpatches.Patch(color=style["color"], label=style["label"]))
    if handles:
        ax.legend(handles=handles, loc="lower right", fontsize=9)

    # Config annotation
    param_lines = []
    for key in ("inertia_p", "novelty_bonus", "attract_strength",
                "stay_p", "teleport_p", "steps", "capture_mode"):
        if key in config:
            param_lines.append(f"{key}: {config[key]}")
    if attractors:
        param_lines.append(f"attractors: {attractors}")
    ax.text(-1.35, -1.35, "\n".join(param_lines),
            fontsize=7, family="monospace", verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect("equal")
    ax.set_title(f"Clock Walk Trace ({len(frames)} frames)", fontsize=13)
    ax.axis("off")

    if show:
        plt.tight_layout()
        plt.show()

    return fig, ax


# ------------------------------------------------------------------ #
# CLI entry point                                                     #
# ------------------------------------------------------------------ #

def main(argv=None):
    """Command-line interface for capturing and replaying traces."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Capture and visualise clock-walk animation traces.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- capture subcommand ---
    cap_p = sub.add_parser("capture", help="Run simulation and save trace")
    cap_p.add_argument("--config", help="JSON config file path")
    cap_p.add_argument("--mode", choices=["full", "nth", "event"],
                       default="event")
    cap_p.add_argument("--nth", type=int, default=10,
                       help="Sample interval for nth mode")
    cap_p.add_argument("--output", "-o", default="trace.json",
                       help="Output trace file path")

    # --- replay subcommand ---
    rep_p = sub.add_parser("replay", help="Replay a saved trace file")
    rep_p.add_argument("trace_file", help="Path to trace JSON file")

    args = parser.parse_args(argv)

    if args.command == "capture":
        # Load config if provided
        kwargs = {}
        if args.config:
            from clockwalk.config import load_config_from_file
            cfg = load_config_from_file(args.config)
            kwargs = {
                "inertia_p": cfg["inertia"],
                "novelty_bonus": cfg["novelty"],
                "attractors": cfg["attractors"],
                "attract_strength": cfg["attract_strength"],
                "steps": cfg["steps"],
                "stay_p": cfg["stay_p"],
                "teleport_p": cfg["teleport_p"],
            }

        trace = build_trace(mode=args.mode, nth=args.nth, **kwargs)
        write_trace(trace, args.output)
        print(f"Trace written to {args.output} "
              f"({len(trace['frames'])} frames, mode={args.mode})")

    elif args.command == "replay":
        trace = load_trace(args.trace_file)
        print(f"Loaded trace: {len(trace['frames'])} frames")
        render_clock_face(trace)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
