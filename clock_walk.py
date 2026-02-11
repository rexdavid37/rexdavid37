import random
import math
import json
import time
import sys
import os
import glob as globmod
from collections import Counter, defaultdict


# ----------------------------
# Defaults
# ----------------------------

DEFAULTS = {
    "runs": 10000,
    "target": 6,
    "inertia": 0.7,
    "novelty": 0.2,
    "steps": 333,
    "attractors": [],          # e.g. [1,6,9]
    "attract_strength": 0.8,
    "teleport_p": 0.002,
    "stay_p": 0.02,
    "try_matplotlib": False,
    "progress_every": 500,     # update spinner every N runs
}


# ----------------------------
# Data file resolution
# ----------------------------

def get_data_dir():
    """Return the path to the data/ folder next to this script."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def list_data_files():
    """Return sorted list of (index, filename, full_path) for all JSON files in data/."""
    data_dir = get_data_dir()
    if not os.path.isdir(data_dir):
        return []
    files = sorted(globmod.glob(os.path.join(data_dir, "*.json")))
    result = []
    for fpath in files:
        fname = os.path.basename(fpath)
        # extract leading integer index from filename like "0_pure_random_baseline.json"
        parts = fname.split("_", 1)
        try:
            idx = int(parts[0])
        except ValueError:
            idx = None
        result.append((idx, fname, fpath))
    return result


def resolve_data_file(arg: str):
    """
    Resolve a CLI argument to a data file path.
    Accepts:
      - An integer index (e.g. "0", "3", "9")
      - A substring of a filename (e.g. "sticky", "attractor")
      - An exact filename (e.g. "0_pure_random_baseline.json")
    Returns the full path, or None if not found.
    """
    entries = list_data_files()
    if not entries:
        return None

    # try as integer index
    try:
        idx = int(arg)
        for entry_idx, fname, fpath in entries:
            if entry_idx == idx:
                return fpath
        return None
    except ValueError:
        pass

    # try exact filename match
    for _, fname, fpath in entries:
        if fname == arg:
            return fpath

    # try substring match (case-insensitive)
    arg_lower = arg.lower()
    matches = [(fname, fpath) for _, fname, fpath in entries if arg_lower in fname.lower()]
    if len(matches) == 1:
        return matches[0][1]
    elif len(matches) > 1:
        print(f"Ambiguous match for '{arg}'. Matches:")
        for fname, _ in matches:
            print(f"  {fname}")
        return None

    return None


def print_data_index():
    """Print a numbered list of available data configs."""
    entries = list_data_files()
    if not entries:
        print("No data files found in data/ folder.")
        return
    print("Available data configs:")
    for idx, fname, _ in entries:
        prefix = f"  [{idx}]" if idx is not None else "  [?]"
        # strip index prefix and .json suffix for display
        name_part = fname.split("_", 1)[1].replace(".json", "").replace("_", " ") if "_" in fname else fname
        print(f"{prefix} {name_part}  ({fname})")


def load_config_from_file(fpath: str) -> dict:
    """Load a JSON config file, merge with defaults, and validate."""
    with open(fpath, "r") as f:
        user_cfg = json.load(f)
    if not isinstance(user_cfg, dict):
        raise ValueError(f"JSON in {fpath} must be an object (dict).")
    cfg = DEFAULTS.copy()
    cfg.update(user_cfg)
    return validate_config(cfg)


# ----------------------------
# Input helpers
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
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out = []
    for p in parts:
        try:
            v = int(p)
        except ValueError:
            continue
        if 1 <= v <= 12:
            out.append(v)
    # unique, stable order
    seen = set()
    uniq = []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


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
        except Exception as e:
            print("\nInvalid JSON. Falling back to interactive prompts.")
            user_cfg = {}

        cfg = DEFAULTS.copy()
        cfg.update(user_cfg)
        return validate_config(cfg)

    # interactive mode
    cfg = DEFAULTS.copy()
    print("\nInteractive config (press Enter to accept defaults where shown).")

    # Small helper: allow blank to keep default
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

    # attractors are easiest as comma string
    s = input(f"Attractors comma-list like 1,6,9 [{','.join(map(str,cfg['attractors'])) if cfg['attractors'] else ''}]: ").strip()
    if s != "":
        cfg["attractors"] = read_attractors("Re-enter attractors (same format): ") if False else parse_attractor_string(s)

    ask_float("attract_strength", "Attractor strength (0..1)", 0.0, 1.0)
    ask_float("teleport_p", "Teleport probability per step (0..0.2)", 0.0, 0.2)
    ask_float("stay_p", "Stay-put probability per step (0..0.5)", 0.0, 0.5)

    ask_bool("try_matplotlib", "Try matplotlib plots if available?")
    ask_int("progress_every", "Progress update every N runs", min_value=1)

    return validate_config(cfg)


def parse_attractor_string(s: str):
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out = []
    for p in parts:
        try:
            v = int(p)
        except ValueError:
            continue
        if 1 <= v <= 12:
            out.append(v)
    seen = set()
    uniq = []
    for v in out:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def validate_config(cfg: dict) -> dict:
    # coerce + clamp lightly
    cfg["runs"] = max(1, int(cfg.get("runs", DEFAULTS["runs"])))
    cfg["target"] = int(cfg.get("target", DEFAULTS["target"]))
    if cfg["target"] < 1: cfg["target"] = 1
    if cfg["target"] > 12: cfg["target"] = 12

    def clamp01(x):
        try:
            x = float(x)
        except Exception:
            return 0.0
        return min(1.0, max(0.0, x))

    cfg["inertia"] = clamp01(cfg.get("inertia", DEFAULTS["inertia"]))
    cfg["novelty"] = clamp01(cfg.get("novelty", DEFAULTS["novelty"]))
    cfg["steps"] = max(1, int(cfg.get("steps", DEFAULTS["steps"])))

    # attractors
    a = cfg.get("attractors", DEFAULTS["attractors"])
    if isinstance(a, str):
        a = parse_attractor_string(a)
    if not isinstance(a, list):
        a = []
    a = [int(v) for v in a if 1 <= int(v) <= 12]
    # unique
    seen = set()
    uniq = []
    for v in a:
        if v not in seen:
            seen.add(v)
            uniq.append(v)
    cfg["attractors"] = uniq

    cfg["attract_strength"] = clamp01(cfg.get("attract_strength", DEFAULTS["attract_strength"]))

    def clamp(x, lo, hi, default):
        try:
            x = float(x)
        except Exception:
            return default
        return min(hi, max(lo, x))

    cfg["teleport_p"] = clamp(cfg.get("teleport_p", DEFAULTS["teleport_p"]), 0.0, 0.2, DEFAULTS["teleport_p"])
    cfg["stay_p"] = clamp(cfg.get("stay_p", DEFAULTS["stay_p"]), 0.0, 0.5, DEFAULTS["stay_p"])

    cfg["try_matplotlib"] = bool(cfg.get("try_matplotlib", DEFAULTS["try_matplotlib"]))
    cfg["progress_every"] = max(1, int(cfg.get("progress_every", DEFAULTS["progress_every"])))

    return cfg


# ----------------------------
# ASCII plotting
# ----------------------------

def ascii_hist(keys, counts_map, width=50, title=""):
    vals = [counts_map.get(k, 0) for k in keys]
    m = max(vals) if vals else 1
    print("\n" + title)
    for k in keys:
        c = counts_map.get(k, 0)
        bar_len = int((c / m) * width) if m > 0 else 0
        bar = "█" * bar_len
        print(f"{str(k):>3} | {bar:<{width}} {c}")


# ----------------------------
# Geometry helpers
# ----------------------------

def step_idx(i: int, move: int, n: int) -> int:
    return (i + move) % n


def dist_min_steps(n: int, i: int, j: int) -> int:
    d = abs(j - i)
    return min(d, n - d)


def dist_clockwise(n: int, i: int, j: int) -> int:
    return (j - i) % n


# ----------------------------
# Move rule with multimodal noise
# ----------------------------

def choose_move_multimodal(pos, last_move, labels, visited_set,
                           inertia_p, novelty_bonus,
                           attractors, attract_strength,
                           stay_p, teleport_p):
    n = len(labels)

    # teleport
    if teleport_p > 0 and random.random() < teleport_p:
        return "TELEPORT"

    # stay
    if stay_p > 0 and random.random() < stay_p:
        return 0

    # inertia multiplier
    if inertia_p == 0.5:
        inertia_mult = 1.0
    elif inertia_p == 1.0:
        inertia_mult = 1e9
    elif inertia_p == 0.0:
        inertia_mult = 0.0
    else:
        inertia_mult = inertia_p / (1.0 - inertia_p)

    weights = []
    for mv in (-1, +1):
        nxt = step_idx(pos, mv, n)
        nxt_label = labels[nxt]
        w = 1.0

        if nxt_label not in visited_set:
            w *= (1.0 + novelty_bonus)

        if last_move is not None and mv == last_move:
            w *= inertia_mult

        # attractors: pull toward nearest attractor (distance-based)
        if attractors:
            cur_best = None
            for a in attractors:
                a_j = labels.index(a)
                d = dist_min_steps(n, pos, a_j)
                cur_best = d if cur_best is None else min(cur_best, d)

            nxt_best = None
            for a in attractors:
                a_j = labels.index(a)
                d = dist_min_steps(n, nxt, a_j)
                nxt_best = d if nxt_best is None else min(nxt_best, d)

            if nxt_best is not None and cur_best is not None:
                if nxt_best < cur_best:
                    w *= (1.0 + attract_strength)
                elif nxt_best > cur_best:
                    w *= (1.0 / (1.0 + attract_strength))

        weights.append(w)

    total = weights[0] + weights[1]
    if total <= 0:
        return random.choice([-1, +1])

    r = random.random() * total
    return -1 if r < weights[0] else +1


def run_staleness_winner(labels, start_index,
                         inertia_p, novelty_bonus,
                         attractors, attract_strength,
                         steps, stay_p, teleport_p):
    n = len(labels)
    pos = start_index
    last_move = None

    last_seen = {lab: None for lab in labels}
    last_seen[labels[pos]] = 0
    visited_set = {labels[pos]}

    for t in range(1, steps + 1):
        mv = choose_move_multimodal(
            pos, last_move, labels, visited_set,
            inertia_p, novelty_bonus,
            attractors, attract_strength,
            stay_p, teleport_p
        )

        if mv == "TELEPORT":
            pos = random.randrange(n)
            last_move = None
        else:
            pos = step_idx(pos, mv, n)
            if mv in (-1, +1):
                last_move = mv

        v = labels[pos]
        visited_set.add(v)
        last_seen[v] = t

    never = [lab for lab in labels if last_seen[lab] is None]
    if never:
        return random.choice(never)

    max_stale = -1
    winners = []
    for lab in labels:
        stale = steps - last_seen[lab]
        if stale > max_stale:
            max_stale = stale
            winners = [lab]
        elif stale == max_stale:
            winners.append(lab)

    return random.choice(winners)


# ----------------------------
# Progress spinner
# ----------------------------

SPIN = ["|", "/", "-", "\\"]

def progress_update(i, total, phase, spin_idx, started_at):
    pct = (i / total) * 100.0 if total else 100.0
    elapsed = time.time() - started_at
    # carriage return keeps it on one line
    msg = f"\r{SPIN[spin_idx % len(SPIN)]} {phase} {pct:6.2f}%  (elapsed {elapsed:5.1f}s)"
    print(msg, end="", flush=True)


# ----------------------------
# Optional matplotlib plots (no von Mises; no i0)
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

    ds = list(range(0, (n//2) + 1))
    hist = [dist_counts.get(d, 0) for d in ds]

    items = [(d, dist_counts[d]) for d in dist_counts if d != 0]
    tot = sum(w for _, w in items) or 1
    mu = sum(d*w for d, w in items) / tot
    var = sum(((d - mu) ** 2) * w for d, w in items) / tot
    sigma = math.sqrt(var) if var > 1e-12 else 1e-6

    def normal_pdf(x):
        return (1.0/(sigma*math.sqrt(2*math.pi))) * math.exp(-0.5*((x-mu)/sigma)**2)

    curve_x = [x/50.0 for x in range(0, (n//2)*50 + 1)]
    curve_y = [normal_pdf(x) for x in curve_x]
    peak_hist = max(hist) if hist else 1
    peak_curve = max(curve_y) if curve_y else 1
    scale = peak_hist/peak_curve if peak_curve > 0 else 1.0
    curve_y = [y*scale for y in curve_y]

    plt.figure()
    plt.bar(ds, hist)
    plt.plot(curve_x, curve_y)
    plt.title(f"{title_prefix} — min distance (Normal μ={mu:.2f}, σ={sigma:.2f})")
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
    try_matplotlib = cfg["try_matplotlib"]
    progress_every = cfg["progress_every"]

    print("\nConfig loaded:")
    print(json.dumps(cfg, indent=2))

    counts = Counter()

    phase = "Simulating staleness-winner runs"
    started_at = time.time()
    spin_idx = 0

    for i in range(1, runs + 1):
        w = run_staleness_winner(
            labels, start_index,
            inertia, novelty,
            attractors, attract_strength,
            steps, stay_p, teleport_p
        )
        counts[w] += 1

        if i % progress_every == 0 or i == runs:
            progress_update(i, runs, phase, spin_idx, started_at)
            spin_idx += 1

    # finish line
    print("\r✔ Done. " + " " * 40)

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
    ascii_hist(list(range(0, (n//2)+1)), dist_counts, title="ASCII — min distance histogram (0..6)")

    cw = defaultdict(int)
    for lab, c in counts.items():
        j = labels.index(lab)
        cw_d = dist_clockwise(n, start_index, j)
        cw[cw_d] += c
    ascii_hist(list(range(0, n)), cw, title="ASCII — clockwise distance histogram (0..11)")

    if try_matplotlib:
        try:
            try_matplotlib_plots(labels, start_index, counts, "Staleness winner")
        except Exception as e:
            print("\n⚠️ Matplotlib plotting failed here.")
            print("Reason:", repr(e))
            print("ASCII plots above are the fallback.")


if __name__ == "__main__":
    main()
