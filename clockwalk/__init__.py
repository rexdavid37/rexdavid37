"""
clockwalk — A composable toolkit for biased random walks on circular structures.

Submodules
----------
geometry   Discrete ring/cycle topology operations.
walk       Multi-bias random walk engine and staleness tracking.
config     Defaults, validation, and indexed data-file resolution.
viz        Terminal-based histogram rendering.
runner     Monte Carlo batch runner with progress display.
"""

from clockwalk.geometry import step_idx, dist_min_steps, dist_clockwise
from clockwalk.walk import choose_move, StalenessTracker, run_staleness_winner
from clockwalk.config import (
    DEFAULTS,
    validate_config,
    parse_attractor_string,
    load_config_from_file,
    list_data_files,
    resolve_data_file,
    print_data_index,
    get_data_dir,
)
from clockwalk.viz import ascii_hist
from clockwalk.runner import run_monte_carlo, progress_update

__all__ = [
    # geometry
    "step_idx", "dist_min_steps", "dist_clockwise",
    # walk
    "choose_move", "StalenessTracker", "run_staleness_winner",
    # config
    "DEFAULTS", "validate_config", "parse_attractor_string",
    "load_config_from_file", "list_data_files", "resolve_data_file",
    "print_data_index", "get_data_dir",
    # viz
    "ascii_hist",
    # runner
    "run_monte_carlo", "progress_update",
]
