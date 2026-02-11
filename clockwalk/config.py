"""
Configuration loading, validation, and indexed data-file discovery.

Provides a lightweight "defaults + user overrides + validation" pattern
and a convention-based file registry for numbered JSON presets stored
in a ``data/`` directory.
"""

import json
import os
import glob as globmod


# ------------------------------------------------------------------ #
# Defaults                                                           #
# ------------------------------------------------------------------ #

DEFAULTS = {
    "runs": 10000,
    "target": 6,
    "inertia": 0.7,
    "novelty": 0.2,
    "steps": 333,
    "attractors": [],
    "attract_strength": 0.8,
    "teleport_p": 0.002,
    "stay_p": 0.02,
    "try_matplotlib": False,
    "progress_every": 500,
}


# ------------------------------------------------------------------ #
# Attractor parsing                                                  #
# ------------------------------------------------------------------ #

def parse_attractor_string(s: str):
    """Parse a comma-separated string like ``"1,6,9"`` into a deduplicated list of ints in [1,12]."""
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


# ------------------------------------------------------------------ #
# Validation                                                         #
# ------------------------------------------------------------------ #

def validate_config(cfg: dict) -> dict:
    """Coerce types, clamp ranges, and deduplicate attractors."""
    cfg["runs"] = max(1, int(cfg.get("runs", DEFAULTS["runs"])))
    cfg["target"] = int(cfg.get("target", DEFAULTS["target"]))
    if cfg["target"] < 1:
        cfg["target"] = 1
    if cfg["target"] > 12:
        cfg["target"] = 12

    def clamp01(x):
        try:
            x = float(x)
        except Exception:
            return 0.0
        return min(1.0, max(0.0, x))

    cfg["inertia"] = clamp01(cfg.get("inertia", DEFAULTS["inertia"]))
    cfg["novelty"] = clamp01(cfg.get("novelty", DEFAULTS["novelty"]))
    cfg["steps"] = max(1, int(cfg.get("steps", DEFAULTS["steps"])))

    a = cfg.get("attractors", DEFAULTS["attractors"])
    if isinstance(a, str):
        a = parse_attractor_string(a)
    if not isinstance(a, list):
        a = []
    a = [int(v) for v in a if 1 <= int(v) <= 12]
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


# ------------------------------------------------------------------ #
# Indexed data-file registry                                         #
# ------------------------------------------------------------------ #

def get_data_dir():
    """Return the path to the ``data/`` folder next to the calling script."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def list_data_files():
    """
    Return sorted list of ``(index, filename, full_path)`` for all JSON
    files in ``data/``.  The index is parsed from a leading integer in the
    filename (e.g. ``0_pure_random_baseline.json`` -> index 0).
    """
    data_dir = get_data_dir()
    if not os.path.isdir(data_dir):
        return []
    files = sorted(globmod.glob(os.path.join(data_dir, "*.json")))
    result = []
    for fpath in files:
        fname = os.path.basename(fpath)
        parts = fname.split("_", 1)
        try:
            idx = int(parts[0])
        except ValueError:
            idx = None
        result.append((idx, fname, fpath))
    return result


def resolve_data_file(arg: str):
    """
    Resolve a CLI argument to a data-file path.

    Accepts an integer index, an exact filename, or a case-insensitive
    substring.  Returns ``None`` on no match or ambiguous match.
    """
    entries = list_data_files()
    if not entries:
        return None

    try:
        idx = int(arg)
        for entry_idx, fname, fpath in entries:
            if entry_idx == idx:
                return fpath
        return None
    except ValueError:
        pass

    for _, fname, fpath in entries:
        if fname == arg:
            return fpath

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
    """Print a numbered list of available data configs to stdout."""
    entries = list_data_files()
    if not entries:
        print("No data files found in data/ folder.")
        return
    print("Available data configs:")
    for idx, fname, _ in entries:
        prefix = f"  [{idx}]" if idx is not None else "  [?]"
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
