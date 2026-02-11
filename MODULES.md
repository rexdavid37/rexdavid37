# Extractable Library Modules

Analysis of `clock_walk.py` identifying single-concern capabilities that
can be extracted into independent, reusable modules.

---

## 1. `ring_geometry` — Discrete Circular Topology

**Functions:** `step_idx`, `dist_min_steps`, `dist_clockwise`

**What it does:** Pure math on a ring of N positions. Step forward/backward
with wraparound, compute shortest distance between two positions, compute
directed (clockwise) distance.

**Why it's reusable:** Any process that models cyclic/periodic structures
(clock faces, circular buffers, modular arithmetic, compass bearings,
musical scales, color wheels) needs these exact operations. Zero
dependencies, fully generic over ring size N.

**Interface:**
```python
step(position: int, move: int, n: int) -> int
shortest_distance(n: int, i: int, j: int) -> int
directed_distance(n: int, i: int, j: int) -> int
```

---

## 2. `biased_walk` — Configurable Random Walk Engine

**Functions:** `choose_move_multimodal`

**What it does:** Single-step move decision for a random walk with five
simultaneous bias channels: inertia (momentum), novelty-seeking (prefer
unvisited), attractor pull (toward target positions), teleportation
(random jump), and stickiness (stay put). Returns a move given current
state.

**Why it's reusable:** This is a general-purpose biased random walk
kernel. Useful for any simulation, recommendation engine, exploration
strategy, or search algorithm that needs to compose multiple competing
heuristics into a single probabilistic decision. The bias channels map
to common patterns:
- **Inertia** = momentum / trend-following
- **Novelty** = exploration bonus (like UCB in bandits)
- **Attractors** = goal-seeking / reward shaping
- **Teleport** = random restart (like PageRank damping)
- **Stay** = inaction cost / friction

**Interface:**
```python
choose_move(
    position: int,
    last_move: int | None,
    labels: list,
    visited: set,
    inertia: float,
    novelty: float,
    attractors: list[int],
    attract_strength: float,
    stay_p: float,
    teleport_p: float,
) -> int | str  # -1, +1, 0, or "TELEPORT"
```

---

## 3. `staleness_tracker` — Recency-Based Scoring

**Functions:** `run_staleness_winner` (the tracking/scoring logic, separated
from the walk engine)

**What it does:** Tracks when each position was last visited and determines
which position has gone the longest without a visit ("most stale"). Handles
the edge case of never-visited positions.

**Why it's reusable:** "Least recently used" / "most stale" selection is a
pattern that appears in cache eviction (LRU), load balancing (route to
least-recently-served node), content rotation (show the item users haven't
seen in longest), and fair scheduling. The staleness logic is independent
of how the walk itself works.

**Interface:**
```python
class StalenessTracker:
    def __init__(self, labels: list)
    def visit(self, label, timestamp: int)
    def stalest(self) -> list  # labels tied for most stale
    def never_visited(self) -> list
```

---

## 4. `config_loader` — Schema-Validated Config with Defaults

**Functions:** `DEFAULTS`, `validate_config`, `load_config_from_file`,
`parse_attractor_string`

**What it does:** Merges user-provided config (from JSON file or dict)
with a defaults dict, then validates and clamps all values to legal ranges.
Type coercion (string to int/float/list), deduplication, and range clamping
are all handled.

**Why it's reusable:** Almost every simulation or CLI tool needs
"defaults + user overrides + validation." This pattern of
`defaults.copy() -> update(user) -> validate()` with per-field clamping
is a lightweight alternative to heavier schema libraries (pydantic,
jsonschema) for projects that want zero dependencies.

**Interface:**
```python
def load_config(source: str | dict, defaults: dict, validators: dict) -> dict
```

---

## 5. `indexed_data_store` — Convention-Based File Registry

**Functions:** `get_data_dir`, `list_data_files`, `resolve_data_file`,
`print_data_index`, `load_config_from_file`

**What it does:** Discovers JSON files in a sibling `data/` directory,
indexes them by leading integer in the filename, and resolves user queries
(by index, exact name, or substring) to a specific file path.

**Why it's reusable:** Any tool that ships with numbered presets, example
configs, test fixtures, or sample datasets needs this "look up file by
index or fuzzy name" pattern. The convention of `{N}_{description}.json`
is lightweight and filesystem-native — no database, no manifest file.

**Interface:**
```python
def list_entries(directory: str, ext: str = ".json") -> list[Entry]
def resolve(query: str, entries: list[Entry]) -> str | None  # file path
```

---

## 6. `ascii_histogram` — Terminal-Based Visualization

**Functions:** `ascii_hist`

**What it does:** Renders a horizontal bar chart in the terminal using
block characters. Auto-scales bars to the maximum value.

**Why it's reusable:** Useful for any CLI tool, log analyzer, or monitoring
script that wants quick visual output without matplotlib. Works over SSH,
in CI logs, in Docker containers — anywhere with a terminal.

**Interface:**
```python
def histogram(
    keys: list,
    counts: dict,
    width: int = 50,
    title: str = "",
    stream: TextIO = sys.stdout,
) -> None
```

---

## 7. `monte_carlo_runner` — Batch Simulation with Progress

**Functions:** The simulation loop in `main()` + `progress_update`

**What it does:** Runs N independent trials of a callable, collects
results into a Counter, and displays a spinner with percentage and elapsed
time. The progress display uses carriage returns for single-line updates.

**Why it's reusable:** The "run function N times, count outcomes, show
progress" pattern appears in any Monte Carlo simulation, A/B test
simulator, bootstrap resampler, or stochastic optimizer. Separating the
runner from the trial function makes it composable.

**Interface:**
```python
def run_monte_carlo(
    trial_fn: Callable[[], T],
    n: int,
    progress_every: int = 500,
) -> Counter[T]
```

---

## Dependency Graph (proposed modules)

```
monte_carlo_runner
    └── biased_walk
    │       ├── ring_geometry
    │       └── staleness_tracker
    ├── config_loader
    │       └── indexed_data_store
    └── ascii_histogram
```

The three leaf modules (`ring_geometry`, `ascii_histogram`,
`indexed_data_store`) have zero internal dependencies and can be
published or vendored independently. `biased_walk` depends only on
`ring_geometry`. `staleness_tracker` is fully standalone.
