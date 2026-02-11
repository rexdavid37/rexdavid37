"""
Monte Carlo batch runner with terminal progress display.

Runs N independent trials of a callable, collects results into a
``Counter``, and shows a single-line spinner with percentage and
elapsed time.
"""

import time
from collections import Counter

SPIN = ["|", "/", "-", "\\"]


def progress_update(i, total, phase, spin_idx, started_at):
    """Print a single-line progress update (carriage-return overwrite)."""
    pct = (i / total) * 100.0 if total else 100.0
    elapsed = time.time() - started_at
    msg = f"\r{SPIN[spin_idx % len(SPIN)]} {phase} {pct:6.2f}%  (elapsed {elapsed:5.1f}s)"
    print(msg, end="", flush=True)


def run_monte_carlo(trial_fn, n, progress_every=500, phase="Running"):
    """
    Execute *trial_fn* **n** times and return a ``Counter`` of results.

    Parameters
    ----------
    trial_fn : callable
        Zero-argument function that returns a hashable outcome.
    n : int
        Number of trials.
    progress_every : int
        How often to refresh the progress spinner.
    phase : str
        Label shown in the progress line.

    Returns
    -------
    collections.Counter
        Mapping from outcome to count.
    """
    counts = Counter()
    started_at = time.time()
    spin_idx = 0

    for i in range(1, n + 1):
        counts[trial_fn()] += 1

        if i % progress_every == 0 or i == n:
            progress_update(i, n, phase, spin_idx, started_at)
            spin_idx += 1

    print("\r\u2714 Done. " + " " * 40)
    return counts
