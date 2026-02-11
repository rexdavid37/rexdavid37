"""
Tests for clockwalk.capture — frame capture modes for animation.

Covers:
- EventTag enum values
- FullCapture: records every step
- NthCapture: records every N-th step
- EventCapture: records only on state changes (teleport, reversal, first visit,
  stay, attract approach)
- Capture callbacks are compatible with run_staleness_winner's on_step parameter
"""

import random
import unittest

from clockwalk.capture import (
    EventTag,
    FullCapture,
    NthCapture,
    EventCapture,
)
from clockwalk.walk import run_staleness_winner

LABELS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


# ================================================================
# EventTag enum
# ================================================================

class TestEventTag(unittest.TestCase):
    def test_expected_tags_exist(self):
        for name in ("TELEPORT", "REVERSAL", "FIRST_VISIT", "STAY",
                      "ATTRACT_APPROACH", "NORMAL", "SAMPLE"):
            self.assertTrue(hasattr(EventTag, name), f"Missing EventTag.{name}")

    def test_tags_are_distinct(self):
        tags = [EventTag.TELEPORT, EventTag.REVERSAL, EventTag.FIRST_VISIT,
                EventTag.STAY, EventTag.ATTRACT_APPROACH, EventTag.NORMAL,
                EventTag.SAMPLE]
        self.assertEqual(len(tags), len(set(tags)))


# ================================================================
# FullCapture
# ================================================================

class TestFullCapture(unittest.TestCase):
    def test_records_every_step(self):
        cap = FullCapture()
        # Simulate 5 steps manually
        for t in range(1, 6):
            cap(t, pos=t, move=1, label=t, last_move=1,
                visited_set=set(range(1, t + 1)), tracker=None)
        self.assertEqual(len(cap.frames), 5)

    def test_frame_shape(self):
        cap = FullCapture()
        cap(1, pos=0, move=1, label=12, last_move=None,
            visited_set={12}, tracker=None)
        frame = cap.frames[0]
        self.assertEqual(frame[0], 1)      # t
        self.assertEqual(frame[1], 0)      # pos
        self.assertEqual(frame[2], EventTag.SAMPLE)  # tag

    def test_clear_resets(self):
        cap = FullCapture()
        cap(1, pos=0, move=1, label=12, last_move=None,
            visited_set={12}, tracker=None)
        self.assertEqual(len(cap.frames), 1)
        cap.clear()
        self.assertEqual(len(cap.frames), 0)


# ================================================================
# NthCapture
# ================================================================

class TestNthCapture(unittest.TestCase):
    def test_records_every_nth(self):
        cap = NthCapture(n=3)
        for t in range(1, 13):
            cap(t, pos=t % 12, move=1, label=t % 12, last_move=1,
                visited_set=set(), tracker=None)
        # Steps 3, 6, 9, 12 should be recorded
        self.assertEqual(len(cap.frames), 4)
        self.assertEqual([f[0] for f in cap.frames], [3, 6, 9, 12])

    def test_n_equals_one_is_full_capture(self):
        cap = NthCapture(n=1)
        for t in range(1, 6):
            cap(t, pos=0, move=1, label=12, last_move=1,
                visited_set=set(), tracker=None)
        self.assertEqual(len(cap.frames), 5)

    def test_tag_is_sample(self):
        cap = NthCapture(n=1)
        cap(1, pos=0, move=1, label=12, last_move=None,
            visited_set=set(), tracker=None)
        self.assertEqual(cap.frames[0][2], EventTag.SAMPLE)

    def test_n_must_be_positive(self):
        with self.assertRaises(ValueError):
            NthCapture(n=0)
        with self.assertRaises(ValueError):
            NthCapture(n=-1)


# ================================================================
# EventCapture
# ================================================================

class TestEventCapture(unittest.TestCase):
    def test_teleport_detected(self):
        cap = EventCapture()
        cap(1, pos=5, move="TELEPORT", label=6, last_move=1,
            visited_set={12, 6}, tracker=None)
        self.assertEqual(len(cap.frames), 1)
        self.assertEqual(cap.frames[0][2], EventTag.TELEPORT)

    def test_reversal_detected(self):
        cap = EventCapture()
        # Moving +1, then -1 → reversal
        cap(1, pos=1, move=-1, label=1, last_move=1,
            visited_set={12, 1}, tracker=None)
        self.assertEqual(len(cap.frames), 1)
        self.assertEqual(cap.frames[0][2], EventTag.REVERSAL)

    def test_first_visit_detected(self):
        cap = EventCapture()
        # Label 3 not in visited_set at the *start* of this step
        # We pass visited_set as it was *before* adding the new label
        cap(1, pos=3, move=1, label=3, last_move=1,
            visited_set={12}, tracker=None)
        self.assertEqual(len(cap.frames), 1)
        self.assertEqual(cap.frames[0][2], EventTag.FIRST_VISIT)

    def test_stay_detected(self):
        cap = EventCapture()
        cap(1, pos=0, move=0, label=12, last_move=1,
            visited_set={12}, tracker=None)
        self.assertEqual(len(cap.frames), 1)
        self.assertEqual(cap.frames[0][2], EventTag.STAY)

    def test_normal_step_not_recorded(self):
        """A normal directional step to an already-visited position is skipped."""
        cap = EventCapture()
        # Move +1, continuing same direction, to an already-visited label
        cap(1, pos=1, move=1, label=1, last_move=1,
            visited_set={12, 1}, tracker=None)
        self.assertEqual(len(cap.frames), 0)

    def test_attract_approach_detected(self):
        """Moving closer to an attractor triggers ATTRACT_APPROACH."""
        cap = EventCapture(labels=LABELS, attractors=[6])
        # First call sets _prev_pos to 3
        cap(1, pos=3, move=1, label=3, last_move=1,
            visited_set={12, 1, 2, 3}, tracker=None)
        # Second call: from pos 3 to pos 4, closer to attractor at index 6
        # dist(3,6)=3, dist(4,6)=2 → closer → ATTRACT_APPROACH
        cap(2, pos=4, move=1, label=4, last_move=1,
            visited_set={12, 1, 2, 3, 4}, tracker=None)
        has_attract = any(f[2] == EventTag.ATTRACT_APPROACH for f in cap.frames)
        self.assertTrue(has_attract)

    def test_priority_teleport_over_first_visit(self):
        """Teleport to unvisited position → tagged as TELEPORT, not FIRST_VISIT."""
        cap = EventCapture()
        cap(1, pos=5, move="TELEPORT", label=6, last_move=1,
            visited_set={12}, tracker=None)
        self.assertEqual(cap.frames[0][2], EventTag.TELEPORT)

    def test_reduces_frame_count(self):
        """Event capture produces fewer frames than full capture for same walk."""
        random.seed(42)
        full = FullCapture()
        run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=200, stay_p=0.02, teleport_p=0.002,
            on_step=full,
        )
        random.seed(42)
        event = EventCapture(labels=LABELS, attractors=[6])
        run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=200, stay_p=0.02, teleport_p=0.002,
            on_step=event,
        )
        self.assertLess(len(event.frames), len(full.frames))


# ================================================================
# Integration with run_staleness_winner
# ================================================================

class TestCaptureIntegration(unittest.TestCase):
    def test_on_step_none_unchanged(self):
        """Default on_step=None produces same result as before."""
        random.seed(42)
        w1 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[], attract_strength=0.0,
            steps=100, stay_p=0.0, teleport_p=0.0,
        )
        random.seed(42)
        w2 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[], attract_strength=0.0,
            steps=100, stay_p=0.0, teleport_p=0.0,
            on_step=None,
        )
        self.assertEqual(w1, w2)

    def test_full_capture_records_all_steps(self):
        cap = FullCapture()
        random.seed(42)
        run_staleness_winner(
            LABELS, 0, inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            steps=50, stay_p=0.0, teleport_p=0.0,
            on_step=cap,
        )
        self.assertEqual(len(cap.frames), 50)

    def test_nth_capture_records_correct_count(self):
        cap = NthCapture(n=10)
        random.seed(42)
        run_staleness_winner(
            LABELS, 0, inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            steps=100, stay_p=0.0, teleport_p=0.0,
            on_step=cap,
        )
        self.assertEqual(len(cap.frames), 10)

    def test_capture_does_not_alter_result(self):
        """Adding a capture callback must not change the simulation outcome."""
        random.seed(123)
        w1 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=100, stay_p=0.02, teleport_p=0.002,
        )
        random.seed(123)
        cap = FullCapture()
        w2 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=100, stay_p=0.02, teleport_p=0.002,
            on_step=cap,
        )
        self.assertEqual(w1, w2)

    def test_frame_timestamps_are_sequential(self):
        cap = FullCapture()
        random.seed(42)
        run_staleness_winner(
            LABELS, 0, inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            steps=20, stay_p=0.0, teleport_p=0.0,
            on_step=cap,
        )
        times = [f[0] for f in cap.frames]
        self.assertEqual(times, list(range(1, 21)))


# ================================================================
# Backwards compatibility: existing tests still pass
# ================================================================

class TestBackwardsCompatibility(unittest.TestCase):
    def test_run_staleness_winner_positional_args_still_work(self):
        """Calling without on_step kwarg still works (positional args unchanged)."""
        random.seed(42)
        w = run_staleness_winner(
            LABELS, 0, 0.7, 0.2, [], 0.0, 50, 0.0, 0.0
        )
        self.assertIn(w, LABELS)


if __name__ == "__main__":
    unittest.main()
