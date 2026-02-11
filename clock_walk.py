"""
Multimodal / Noisy Clock Walk — CLI entry point.

This script provides the interactive command-line interface.
All core logic lives in the ``clockwalk`` package and can be imported
independently by other programs.
"""

import json
import math
import os
import sys
from collections import defaultdict

from clockwalk import (
    DEFAULTS,
    ascii_hist,
    dist_clockwise,
    dist_min_steps,
    load_config_from_file,
    parse_attractor_string,
    print_data_index,
    resolve_data_file,
    run_monte_carlo,
    run_staleness_winner,
    validate_config,
)

# Re-export names that tests import from this file so existing
# ``from clock_walk import X`` continues to work.
from clockwalk import step_idx, list_data_files  # noqa: F401
from clockwalk.walk import choose_move as choose_move_multimodal  # noqa: F401


# ----------------------------
# Input helpers (CLI-only)
# ----------------------------

def read_int(prompt: str, min_value=None, max_value=None) -> int:
    while True:
        s = input(prompt).strip()
        try:
            x = int(s)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if min_value is not None and x < min_value:
            print(f"Please enter a number >= {min_value}.")
            continue
        if max_value is not None and x > max_value:
            print(f"Please enter a number <= {max_value}.")
            continue
        return x


def read_float(prompt: str, min_value=0.0, max_value=1.0) -> float:
    while True:
        s = input(prompt).strip()
        try:
            x = float(s)
        except ValueError:
            print("Please enter a number like 0.05.")
            continue
        if x < min_value or x > max_value:
            print(f"Please enter a value in [{min_value}, {max_value}].")
            continue
        return x


def read_yesno(prompt: str) -> bool:
    return input(prompt).strip().lower() in ("y", "yes")


def read_attractors(prompt: str):
    s = input(prompt).strip()
    if not s:
        return []
    return parse_attractor_string(s)


def get_config():
    """
    Ask user: JSON config or interactive prompts.
    Returns dict config.
    """
    print("Config input mode:")
    print("  1) Paste JSON config")
    print("  2) Answer prompts (interactive)")
    mode = input("Choose 1 or 2: ").strip()

    if mode == "1":
        print("\nPaste a JSON object with any of these keys:")
        print(", ".join(DEFAULTS.keys()))
        print("\nExample:")
        example = {
            "runs": 100000,
            "target": 6,
            "inertia": 0.9,
            "novelty": 0.2,
            "steps": 1000,
            "attractors": [1, 6, 9],
            "attract_strength": 0.8,
            "teleport_p": 0.002,
            "stay_p": 0.02,
            "try_matplotlib": False,
            "progress_every": 2000
        }
        print(json.dumps(example, indent=2))

        raw = input("\nJSON: ").strip()
        try:
            user_cfg = json.loads(raw)
            if not isinstance(user_cfg, dict):
                raise ValueError("JSON must be an object (dict).")
        except Exception:
            print("\nInvalid JSON. Falling back to interactive prompts.")
            user_cfg = {}

        cfg = DEFAULTS.copy()
        cfg.update(user_cfg)
        return validate_config(cfg)

    # interactive mode
    cfg = DEFAULTS.copy()
    print("\nInteractive config (press Enter to accept defaults where shown).")

    def ask_int(key, prompt, min_value=None, max_value=None):
        default = cfg[key]
        s = input(f"{prompt} [{default}]: ").strip()
        if s == "":
            return
        try:
            x = int(s)
        except ValueError:
            print("Invalid int; keeping default.")
            return
        if min_value is not None and x < min_value:
            print("Out of range; keeping default.")
            return
        if max_value is not None and x > max_value:
            print("Out of range; keeping default.")
            return
        cfg[key] = x

    def ask_float(key, prompt, min_value=0.0, max_value=1.0):
        default = cfg[key]
        s = input(f"{prompt} [{default}]: ").strip()
        if s == "":
            return
        try:
            x = float(s)
        except ValueError:
            print("Invalid float; keeping default.")
            return
        if x < min_value or x > max_value:
            print("Out of range; keeping default.")
            return
        cfg[key] = x

    def ask_bool(key, prompt):
        default = cfg[key]
        s = input(f"{prompt} (y/n) [{ 'y' if default else 'n' }]: ").strip().lower()
        if s == "":
            return
        cfg[key] = s in ("y", "yes")

    ask_int("runs", "Runs", min_value=1)
    ask_int("target", "Target label (1..12)", min_value=1, max_value=12)
    ask_float("inertia", "Inertia (0..1)", 0.0, 1.0)
    ask_float("novelty", "Novelty bonus (0..1)", 0.0, 1.0)
    ask_int("steps", "Steps for staleness winner", min_value=1)

    s = input(f"Attractors comma-list like 1,6,9 [{','.join(map(str,cfg['attractors'])) if cfg['attractors'] else ''}]: ").strip()
    if s != "":
        cfg["attractors"] = parse_attractor_string(s)

    ask_float("attract_strength", "Attractor strength (0..1)", 0.0, 1.0)
    ask_float("teleport_p", "Teleport probability per step (0..0.2)", 0.0, 0.2)
    ask_float("stay_p", "Stay-put probability per step (0..0.5)", 0.0, 0.5)

    ask_bool("try_matplotlib", "Try matplotlib plots if available?")
    ask_int("progress_every", "Progress update every N runs", min_value=1)

    return validate_config(cfg)


# ----------------------------
# Optional matplotlib plots
# ----------------------------

def try_matplotlib_plots(labels, start_index, counts, title_prefix):
    import matplotlib.pyplot as plt

    n = len(labels)
    start_label = labels[start_index]

    xs = labels
    ys = [counts.get(lab, 0) for lab in labels]
    plt.figure()
    plt.bar(xs, ys)
    plt.title(f"{title_prefix} — counts by label")
    plt.xlabel("Label")
    plt.ylabel("Count")
    plt.xticks(xs)
    plt.show()

    cw_hist = [0] * n
    for lab, c in counts.items():
        j = labels.index(lab)
        cw = dist_clockwise(n, start_index, j)
        cw_hist[cw] += c

    plt.figure()
    plt.bar(list(range(n)), cw_hist)
    plt.title(f"{title_prefix} — clockwise distance (0..11)")
    plt.xlabel("Clockwise distance")
    plt.ylabel("Count")
    plt.xticks(list(range(n)))
    plt.show()

    dist_counts = defaultdict(int)
    for lab, c in counts.items():
        if lab == start_label:
            continue
        j = labels.index(lab)
        dmin = dist_min_steps(n, start_index, j)
        dist_counts[dmin] += c

    ds = list(range(0, (n // 2) + 1))
    hist = [dist_counts.get(d, 0) for d in ds]

    items = [(d, dist_counts[d]) for d in dist_counts if d != 0]
    tot = sum(w for _, w in items) or 1
    mu = sum(d * w for d, w in items) / tot
    var = sum(((d - mu) ** 2) * w for d, w in items) / tot
    sigma = math.sqrt(var) if var > 1e-12 else 1e-6

    def normal_pdf(x):
        return (1.0 / (sigma * math.sqrt(2 * math.pi))) * math.exp(-0.5 * ((x - mu) / sigma) ** 2)

    curve_x = [x / 50.0 for x in range(0, (n // 2) * 50 + 1)]
    curve_y = [normal_pdf(x) for x in curve_x]
    peak_hist = max(hist) if hist else 1
    peak_curve = max(curve_y) if curve_y else 1
    scale = peak_hist / peak_curve if peak_curve > 0 else 1.0
    curve_y = [y * scale for y in curve_y]

    plt.figure()
    plt.bar(ds, hist)
    plt.plot(curve_x, curve_y)
    plt.title(f"{title_prefix} — min distance (Normal \u03bc={mu:.2f}, \u03c3={sigma:.2f})")
    plt.xlabel("Min distance")
    plt.ylabel("Count")
    plt.xticks(ds)
    plt.show()


# ----------------------------
# Main
# ----------------------------

def main():
    print("=== MULTIMODAL / NOISY CLOCK WALK (JSON or prompts + progress) ===")

    # Handle CLI arguments: index, filename, substring, or --list
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ("--list", "-l"):
            print_data_index()
            return

        if arg in ("--help", "-h"):
            print("Usage: python clock_walk.py [OPTION]")
            print()
            print("Options:")
            print("  <index>       Load data config by index (e.g. 0, 3, 9)")
            print("  <name>        Load by filename or substring (e.g. 'sticky', 'attractor')")
            print("  --list, -l    List all available data configs")
            print("  --help, -h    Show this help message")
            print()
            print("With no arguments, launches interactive config mode.")
            return

        fpath = resolve_data_file(arg)
        if fpath is None:
            print(f"Could not resolve '{arg}' to a data file.")
            print("Use --list to see available configs.")
            return
        print(f"Loading config: {os.path.basename(fpath)}")
        cfg = load_config_from_file(fpath)
    else:
        cfg = get_config()

    labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    start_index = 0
    start_label = labels[start_index]

    runs = cfg["runs"]
    target = cfg["target"]
    inertia = cfg["inertia"]
    novelty = cfg["novelty"]
    steps = cfg["steps"]
    attractors = cfg["attractors"]
    attract_strength = cfg["attract_strength"]
    teleport_p = cfg["teleport_p"]
    stay_p = cfg["stay_p"]
    try_mpl = cfg["try_matplotlib"]
    progress_every = cfg["progress_every"]

    print("\nConfig loaded:")
    print(json.dumps(cfg, indent=2))

    def trial():
        return run_staleness_winner(
            labels, start_index,
            inertia, novelty,
            attractors, attract_strength,
            steps, stay_p, teleport_p
        )

    counts = run_monte_carlo(
        trial, runs,
        progress_every=progress_every,
        phase="Simulating staleness-winner runs",
    )

    pct = 100.0 * counts.get(target, 0) / runs

    print("\nSummary:")
    print(f"Runs: {runs} | Steps: {steps} | Start: {start_label}")
    print(f"Target: {target} | Inertia: {inertia} | Novelty: {novelty}")
    print(f"Attractors: {attractors} | Strength: {attract_strength}")
    print(f"Teleport_p: {teleport_p} | Stay_p: {stay_p}")
    print(f"Target percent: {pct:.4f}%")

    print("\nCounts by label:")
    for lab in labels:
        print(f"{lab:>2}: {counts.get(lab, 0)}")

    # ASCII plots
    ascii_hist(labels, counts, title="ASCII — counts by label")

    n = len(labels)

    dist_counts = defaultdict(int)
    for lab, c in counts.items():
        j = labels.index(lab)
        dmin = dist_min_steps(n, start_index, j)
        dist_counts[dmin] += c
    ascii_hist(list(range(0, (n // 2) + 1)), dist_counts, title="ASCII — min distance histogram (0..6)")

    cw = defaultdict(int)
    for lab, c in counts.items():
        j = labels.index(lab)
        cw_d = dist_clockwise(n, start_index, j)
        cw[cw_d] += c
    ascii_hist(list(range(0, n)), cw, title="ASCII — clockwise distance histogram (0..11)")

    if try_mpl:
        try:
            try_matplotlib_plots(labels, start_index, counts, "Staleness winner")
        except Exception as e:
            print("\n\u26a0\ufe0f Matplotlib plotting failed here.")
            print("Reason:", repr(e))
            print("ASCII plots above are the fallback.")


if __name__ == "__main__":
    main()
