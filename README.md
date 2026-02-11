# Clock Walk

A configurable Monte Carlo simulator for biased random walks on a
12-position clock face. The walker moves clockwise or counterclockwise
under the influence of five competing bias channels — inertia, novelty,
attractors, teleportation, and stickiness — then the simulation reports
which position went the longest without being visited ("staleness winner").

## Quick Start

```bash
# Run with a preset config (by index)
python clock_walk.py 0

# Run with a preset config (by name)
python clock_walk.py sticky

# List all available presets
python clock_walk.py --list

# Interactive mode (prompts or paste JSON)
python clock_walk.py
```

## How It Works

1. A walker starts at the 12 o'clock position on a ring of 12 positions
   (labeled 12, 1, 2, ..., 11).
2. At each time step, the walker decides to move clockwise (+1),
   counterclockwise (-1), stay (0), or teleport to a random position.
   The decision is probabilistic and shaped by five bias channels.
3. After a fixed number of steps, the simulation checks which position
   was visited least recently (most "stale"). That position wins the trial.
4. This trial is repeated thousands of times, and the distribution of
   winners is reported as counts, percentages, and histograms.

### Bias Channels

| Channel | Parameter | Effect |
|---|---|---|
| **Inertia** | `inertia` (0-1) | Tendency to continue in the same direction. 0.5 = unbiased, 1.0 = always continue. |
| **Novelty** | `novelty` (0-1) | Bonus weight for stepping onto an unvisited position. |
| **Attractors** | `attractors` + `attract_strength` | Pull the walker toward specific positions on the clock. |
| **Teleport** | `teleport_p` (0-0.2) | Per-step probability of jumping to a random position. |
| **Stay** | `stay_p` (0-0.5) | Per-step probability of not moving at all. |

## Configuration

### Preset Data Configs

The `data/` directory contains 10 numbered JSON presets that exercise
different parameter regimes:

| Index | Name | What it tests |
|---|---|---|
| 0 | Pure random baseline | Symmetric walk, no biases. Uniform distribution baseline. |
| 1 | Extreme inertia | Ballistic sweeps around the clock. |
| 2 | High novelty explorer | Strongly prefers unvisited positions. |
| 3 | Single strong attractor | One attractor at position 6 warps the distribution. |
| 4 | Competing attractors | Multiple attractors create interference patterns. |
| 5 | High teleport chaos | Frequent random jumps disrupt walk structure. |
| 6 | Sticky short walk | High stay probability with few steps. |
| 7 | Inertia vs attractor tug | Momentum and attraction compete. |
| 8 | Triple attractor cluster | Three nearby attractors form a cluster. |
| 9 | Long ergodic with novelty | Long walk with novelty bonus for thorough coverage. |

### JSON Config Format

Any subset of keys can be provided; missing keys use defaults.

```json
{
  "runs": 10000,
  "target": 6,
  "inertia": 0.7,
  "novelty": 0.2,
  "steps": 333,
  "attractors": [1, 6, 9],
  "attract_strength": 0.8,
  "teleport_p": 0.002,
  "stay_p": 0.02,
  "try_matplotlib": false,
  "progress_every": 500
}
```

| Key | Type | Default | Description |
|---|---|---|---|
| `runs` | int | 10000 | Number of independent Monte Carlo trials. |
| `target` | int (1-12) | 6 | Position to highlight in summary output. |
| `inertia` | float (0-1) | 0.7 | Directional momentum. |
| `novelty` | float (0-1) | 0.2 | Bonus for unvisited positions. |
| `steps` | int | 333 | Walk length per trial. |
| `attractors` | list[int] | [] | Positions that pull the walker. |
| `attract_strength` | float (0-1) | 0.8 | How strongly attractors pull. |
| `teleport_p` | float (0-0.2) | 0.002 | Random-jump probability per step. |
| `stay_p` | float (0-0.5) | 0.02 | Stay-in-place probability per step. |
| `try_matplotlib` | bool | false | Attempt graphical plots (falls back to ASCII). |
| `progress_every` | int | 500 | Spinner refresh interval. |

## Library Usage

The core logic is packaged as the `clockwalk` Python package and can be
imported independently by other programs without running the CLI.

### Package Structure

```
clockwalk/
    __init__.py     Top-level imports for convenience
    geometry.py     Discrete ring topology (step, distance)
    walk.py         Biased walk kernel + StalenessTracker
    config.py       Defaults, validation, data-file registry
    viz.py          ASCII histogram rendering
    runner.py       Monte Carlo batch runner with progress
```

### Modules by Concern

The five modules are grouped by cross-cutting concern so related
functionality can be adopted together:

**Simulation core** (`geometry` + `walk`)
```python
from clockwalk.geometry import step_idx, dist_min_steps, dist_clockwise
from clockwalk.walk import choose_move, StalenessTracker, run_staleness_winner
```

**Configuration** (`config`)
```python
from clockwalk.config import DEFAULTS, validate_config, load_config_from_file
from clockwalk.config import list_data_files, resolve_data_file
```

**Presentation** (`viz` + `runner`)
```python
from clockwalk.viz import ascii_hist
from clockwalk.runner import run_monte_carlo
```

### Examples

**Run a single trial programmatically:**

```python
from clockwalk import run_staleness_winner

labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
winner = run_staleness_winner(
    labels, start_index=0,
    inertia_p=0.7, novelty_bonus=0.2,
    attractors=[6], attract_strength=0.8,
    steps=333, stay_p=0.02, teleport_p=0.002,
)
print(f"Staleness winner: {winner}")
```

**Run a Monte Carlo batch:**

```python
from clockwalk import run_monte_carlo, run_staleness_winner

labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

def trial():
    return run_staleness_winner(
        labels, 0,
        inertia_p=0.7, novelty_bonus=0.2,
        attractors=[6], attract_strength=0.8,
        steps=333, stay_p=0.02, teleport_p=0.002,
    )

counts = run_monte_carlo(trial, n=10000, progress_every=1000)
for label in labels:
    print(f"{label:>2}: {counts.get(label, 0)}")
```

**Use the staleness tracker standalone:**

```python
from clockwalk.walk import StalenessTracker

tracker = StalenessTracker(["A", "B", "C", "D"])
tracker.visit("A", timestamp=0)
tracker.visit("B", timestamp=3)
tracker.visit("C", timestamp=7)

print(tracker.never_visited())       # ['D']
print(tracker.stalest(current_time=10))  # ['D'] (never visited = infinitely stale)

tracker.visit("D", timestamp=10)
print(tracker.stalest(current_time=10))  # ['A'] (staleness = 10)
```

**Load and validate a config from file:**

```python
from clockwalk import load_config_from_file, resolve_data_file

path = resolve_data_file("sticky")  # fuzzy lookup by name
cfg = load_config_from_file(path)
print(cfg["stay_p"])  # 0.4
```

**Use geometry helpers for any ring size:**

```python
from clockwalk.geometry import step_idx, dist_min_steps

# Works with any ring, not just 12
pos = step_idx(7, +1, 8)          # 8-position ring: 7 -> 0
d = dist_min_steps(8, 0, 5)       # shortest path: 3
```

## Testing

The test suite covers geometry, config validation, move selection,
staleness tracking, statistical distribution properties, data-file
resolution, and library/script parity.

```bash
# Run all 66 tests
python test_clock_walk.py -v
```

### Test Classes

| Class | Tests | Coverage |
|---|---|---|
| `TestStepIdx` | 6 | Ring movement and wraparound |
| `TestDistMinSteps` | 5 | Shortest distance, symmetry, bounds |
| `TestDistClockwise` | 4 | Directed distance |
| `TestValidateConfig` | 10 | Clamping, coercion, dedup |
| `TestParseAttractorString` | 6 | String parsing edge cases |
| `TestChooseMoveMultimodal` | 8 | All bias channels + library parity |
| `TestStalenessTracker` | 5 | Tracker class (visit, stalest, ties) |
| `TestRunStalenessWinner` | 6 | Simulation output + determinism + parity |
| `TestDistributionProperties` | 3 | Monte Carlo sanity checks |
| `TestRunMonteCarlo` | 2 | Batch runner counting |
| `TestDataFileResolution` | 7 | Index/name lookup, load all presets |
| `TestLoadConfigFromFile` | 4 | Temp-file JSON loading |

## Project Structure

```
.
├── clock_walk.py          CLI entry point (interactive + file-based)
├── clockwalk/             Importable library package
│   ├── __init__.py        Convenience re-exports
│   ├── geometry.py        Ring topology: step, distance
│   ├── walk.py            Walk kernel + StalenessTracker
│   ├── config.py          Defaults, validation, data registry
│   ├── viz.py             ASCII histograms
│   └── runner.py          Monte Carlo runner + progress
├── test_clock_walk.py     Test suite (66 tests)
├── data/                  Preset config files
│   ├── 0_pure_random_baseline.json
│   ├── 1_extreme_inertia.json
│   ├── 2_high_novelty_explorer.json
│   ├── 3_single_strong_attractor.json
│   ├── 4_competing_attractors.json
│   ├── 5_high_teleport_chaos.json
│   ├── 6_sticky_short_walk.json
│   ├── 7_inertia_vs_attractor_tug.json
│   ├── 8_triple_attractor_cluster.json
│   └── 9_long_ergodic_with_novelty.json
├── MODULES.md             Detailed analysis of extractable modules
└── .gitignore
```

## Requirements

- Python 3.7+
- No external dependencies (stdlib only)
- Optional: `matplotlib` for graphical plots (`try_matplotlib: true`)
