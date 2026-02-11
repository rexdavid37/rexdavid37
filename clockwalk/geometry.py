"""
Discrete ring topology operations.

All functions are pure, stateless, and work for any ring of size *n*.
"""


def step_idx(i: int, move: int, n: int) -> int:
    """Move *move* positions from index *i* on a ring of size *n*."""
    return (i + move) % n


def dist_min_steps(n: int, i: int, j: int) -> int:
    """Shortest distance (either direction) between positions *i* and *j*."""
    d = abs(j - i)
    return min(d, n - d)


def dist_clockwise(n: int, i: int, j: int) -> int:
    """Clockwise (directed) distance from *i* to *j*."""
    return (j - i) % n
