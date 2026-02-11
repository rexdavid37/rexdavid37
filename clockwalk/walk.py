"""
Multi-bias random walk engine and staleness-based scoring.

The walk kernel composes five independent bias channels into a single
probabilistic step decision:

- **Inertia** — tendency to continue in the same direction.
- **Novelty** — preference for positions not yet visited.
- **Attractors** — pull toward one or more target positions.
- **Teleport** — random jump to any position (PageRank-style damping).
- **Stay** — probability of remaining in place (friction / stickiness).
"""

import random

from clockwalk.geometry import step_idx, dist_min_steps


# ------------------------------------------------------------------ #
# Move kernel                                                        #
# ------------------------------------------------------------------ #

def choose_move(pos, last_move, labels, visited_set,
                inertia_p, novelty_bonus,
                attractors, attract_strength,
                stay_p, teleport_p):
    """
    Return the next move for a walker on a ring.

    Returns
    -------
    int or str
        ``-1`` (counter-clockwise), ``+1`` (clockwise), ``0`` (stay),
        or ``"TELEPORT"`` (random jump).
    """
    n = len(labels)

    if teleport_p > 0 and random.random() < teleport_p:
        return "TELEPORT"

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


# ------------------------------------------------------------------ #
# Staleness tracker                                                  #
# ------------------------------------------------------------------ #

class StalenessTracker:
    """
    Track last-visit timestamps and identify the stalest positions.

    This implements a "least recently visited" selection strategy,
    useful for cache eviction, fair scheduling, and content rotation.
    """

    def __init__(self, labels):
        self.labels = list(labels)
        self.last_seen = {lab: None for lab in self.labels}

    def visit(self, label, timestamp: int):
        """Record that *label* was visited at *timestamp*."""
        self.last_seen[label] = timestamp

    def never_visited(self):
        """Return labels that have never been visited."""
        return [lab for lab in self.labels if self.last_seen[lab] is None]

    def stalest(self, current_time: int):
        """
        Return the list of labels tied for most stale.

        If any labels were never visited, those are returned instead
        (they are infinitely stale).
        """
        never = self.never_visited()
        if never:
            return never

        max_stale = -1
        winners = []
        for lab in self.labels:
            stale = current_time - self.last_seen[lab]
            if stale > max_stale:
                max_stale = stale
                winners = [lab]
            elif stale == max_stale:
                winners.append(lab)
        return winners


# ------------------------------------------------------------------ #
# Staleness-winner simulation (combines walk + tracker)              #
# ------------------------------------------------------------------ #

def run_staleness_winner(labels, start_index,
                         inertia_p, novelty_bonus,
                         attractors, attract_strength,
                         steps, stay_p, teleport_p,
                         on_step=None):
    """
    Run one walk trial and return the label that was most stale at the end.

    Parameters
    ----------
    on_step : callable or None
        Optional callback invoked after each step with the signature
        ``on_step(t, pos, move, label, last_move, visited_set, tracker)``.
        When *None* (the default) no callback overhead is incurred.
        The *visited_set* passed to the callback reflects the state
        **before** the current label is added, so that the callback can
        detect first visits.
    """
    n = len(labels)
    pos = start_index
    last_move = None

    tracker = StalenessTracker(labels)
    tracker.visit(labels[pos], 0)
    visited_set = {labels[pos]}

    for t in range(1, steps + 1):
        mv = choose_move(
            pos, last_move, labels, visited_set,
            inertia_p, novelty_bonus,
            attractors, attract_strength,
            stay_p, teleport_p
        )

        prev_last_move = last_move

        if mv == "TELEPORT":
            pos = random.randrange(n)
            last_move = None
        else:
            pos = step_idx(pos, mv, n)
            if mv in (-1, +1):
                last_move = mv

        v = labels[pos]

        if on_step is not None:
            on_step(t, pos, mv, v, prev_last_move, visited_set, tracker)

        visited_set.add(v)
        tracker.visit(v, t)

    winners = tracker.stalest(steps)
    return random.choice(winners)
