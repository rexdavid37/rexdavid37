"""
Frame capture modes for animation traces.

Three capture strategies are provided, each implementing the ``on_step``
callback signature expected by :func:`clockwalk.walk.run_staleness_winner`:

- **FullCapture** — record every step.
- **NthCapture** — record every *n*-th step.
- **EventCapture** — record only when an interesting state change occurs
  (teleport, reversal, first visit, stay, approach toward attractor).

Each capture object accumulates ``(t, pos, tag)`` tuples in its ``.frames``
list.  The *tag* is an :class:`EventTag` enum value that tells the renderer
what kind of transition happened.
"""

import enum

from clockwalk.geometry import dist_min_steps


class EventTag(enum.Enum):
    """Classification of a single simulation step for animation purposes."""
    TELEPORT = "teleport"
    REVERSAL = "reversal"
    FIRST_VISIT = "first_visit"
    STAY = "stay"
    ATTRACT_APPROACH = "attract_approach"
    NORMAL = "normal"
    SAMPLE = "sample"


# ------------------------------------------------------------------ #
# Full capture                                                        #
# ------------------------------------------------------------------ #

class FullCapture:
    """Record every step as ``(t, pos, SAMPLE)``."""

    def __init__(self):
        self.frames: list[tuple] = []

    def __call__(self, t, pos, move, label, last_move, visited_set, tracker):
        self.frames.append((t, pos, EventTag.SAMPLE))

    def clear(self):
        self.frames.clear()


# ------------------------------------------------------------------ #
# Nth capture                                                         #
# ------------------------------------------------------------------ #

class NthCapture:
    """Record every *n*-th step as ``(t, pos, SAMPLE)``."""

    def __init__(self, n: int = 10):
        if n < 1:
            raise ValueError(f"n must be >= 1, got {n}")
        self.n = n
        self.frames: list[tuple] = []

    def __call__(self, t, pos, move, label, last_move, visited_set, tracker):
        if t % self.n == 0:
            self.frames.append((t, pos, EventTag.SAMPLE))

    def clear(self):
        self.frames.clear()


# ------------------------------------------------------------------ #
# Event capture                                                       #
# ------------------------------------------------------------------ #

class EventCapture:
    """Record only steps where something interesting happens.

    Parameters
    ----------
    labels : list, optional
        Position labels (needed for attractor distance calculation).
    attractors : list, optional
        Attractor position labels (needed for ATTRACT_APPROACH detection).
    """

    def __init__(self, labels=None, attractors=None):
        self.frames: list[tuple] = []
        self.labels = labels
        self.attractors = attractors or []
        self._prev_pos = None

    def _classify(self, t, pos, move, label, last_move, visited_set):
        """Return an EventTag for this step, or None to skip."""
        if move == "TELEPORT":
            return EventTag.TELEPORT

        if move == 0:
            return EventTag.STAY

        # Reversal: directional move opposite to previous direction
        if move in (-1, 1) and last_move is not None and move == -last_move:
            return EventTag.REVERSAL

        # First visit: label was not in visited_set *before* this step
        # (the caller passes visited_set as it was before adding the label)
        if label not in visited_set:
            return EventTag.FIRST_VISIT

        # Attract approach: moved closer to nearest attractor
        if self.attractors and self.labels and self._prev_pos is not None:
            n = len(self.labels)
            prev_best = min(
                dist_min_steps(n, self._prev_pos, self.labels.index(a))
                for a in self.attractors
            )
            cur_best = min(
                dist_min_steps(n, pos, self.labels.index(a))
                for a in self.attractors
            )
            if cur_best < prev_best:
                return EventTag.ATTRACT_APPROACH

        return None  # NORMAL — skip in event mode

    def __call__(self, t, pos, move, label, last_move, visited_set, tracker):
        tag = self._classify(t, pos, move, label, last_move, visited_set)
        if tag is not None:
            self.frames.append((t, pos, tag))
        self._prev_pos = pos

    def clear(self):
        self.frames.clear()
        self._prev_pos = None
