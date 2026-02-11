"""
Tests for clockwalk.animate — trace file I/O and animation driver.

Covers:
- write_trace / load_trace round-trip
- Trace header contains full config
- Trace frames are serialisable tuples
- build_trace helper runs simulation and returns trace dict
"""

import json
import os
import random
import tempfile
import unittest

from clockwalk.capture import EventTag, FullCapture, NthCapture, EventCapture
from clockwalk.animate import write_trace, load_trace, build_trace

LABELS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


# ================================================================
# Trace I/O round-trip
# ================================================================

class TestTraceIO(unittest.TestCase):
    def _make_trace(self):
        """Build a small trace dict for testing."""
        config = {
            "inertia": 0.7,
            "novelty": 0.2,
            "attractors": [6],
            "attract_strength": 0.8,
            "steps": 20,
            "stay_p": 0.02,
            "teleport_p": 0.002,
        }
        frames = [
            (1, 0, EventTag.FIRST_VISIT.value),
            (5, 3, EventTag.REVERSAL.value),
            (10, 7, EventTag.TELEPORT.value),
        ]
        return {"config": config, "frames": frames, "labels": LABELS}

    def test_write_creates_file(self):
        trace = self._make_trace()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_trace(trace, path)
            self.assertTrue(os.path.isfile(path))
            self.assertGreater(os.path.getsize(path), 0)
        finally:
            os.unlink(path)

    def test_round_trip_preserves_config(self):
        trace = self._make_trace()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_trace(trace, path)
            loaded = load_trace(path)
            self.assertEqual(loaded["config"], trace["config"])
        finally:
            os.unlink(path)

    def test_round_trip_preserves_frames(self):
        trace = self._make_trace()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_trace(trace, path)
            loaded = load_trace(path)
            self.assertEqual(len(loaded["frames"]), len(trace["frames"]))
            for orig, loaded_f in zip(trace["frames"], loaded["frames"]):
                self.assertEqual(tuple(loaded_f), tuple(orig))
        finally:
            os.unlink(path)

    def test_round_trip_preserves_labels(self):
        trace = self._make_trace()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_trace(trace, path)
            loaded = load_trace(path)
            self.assertEqual(loaded["labels"], LABELS)
        finally:
            os.unlink(path)

    def test_output_is_valid_json(self):
        trace = self._make_trace()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_trace(trace, path)
            with open(path) as fh:
                data = json.load(fh)
            self.assertIn("config", data)
            self.assertIn("frames", data)
        finally:
            os.unlink(path)


# ================================================================
# build_trace helper
# ================================================================

class TestBuildTrace(unittest.TestCase):
    def test_returns_trace_dict(self):
        random.seed(42)
        trace = build_trace(
            mode="full",
            inertia_p=0.7,
            novelty_bonus=0.2,
            attractors=[],
            attract_strength=0.0,
            steps=30,
            stay_p=0.0,
            teleport_p=0.0,
        )
        self.assertIn("config", trace)
        self.assertIn("frames", trace)
        self.assertIn("labels", trace)

    def test_full_mode_captures_all(self):
        random.seed(42)
        trace = build_trace(mode="full", steps=50)
        self.assertEqual(len(trace["frames"]), 50)

    def test_nth_mode_captures_every_n(self):
        random.seed(42)
        trace = build_trace(mode="nth", nth=5, steps=50)
        self.assertEqual(len(trace["frames"]), 10)

    def test_event_mode_captures_fewer(self):
        random.seed(42)
        trace_full = build_trace(mode="full", steps=100)
        random.seed(42)
        trace_event = build_trace(mode="event", steps=100,
                                  attractors=[6], attract_strength=0.8)
        self.assertLess(len(trace_event["frames"]), len(trace_full["frames"]))

    def test_config_in_trace_matches_params(self):
        random.seed(42)
        trace = build_trace(
            mode="full",
            inertia_p=0.9,
            novelty_bonus=0.1,
            attractors=[3, 9],
            attract_strength=0.5,
            steps=20,
            stay_p=0.05,
            teleport_p=0.01,
        )
        cfg = trace["config"]
        self.assertEqual(cfg["inertia_p"], 0.9)
        self.assertEqual(cfg["novelty_bonus"], 0.1)
        self.assertEqual(cfg["attractors"], [3, 9])
        self.assertEqual(cfg["attract_strength"], 0.5)
        self.assertEqual(cfg["steps"], 20)
        self.assertEqual(cfg["stay_p"], 0.05)
        self.assertEqual(cfg["teleport_p"], 0.01)
        self.assertEqual(cfg["capture_mode"], "full")

    def test_default_params_work(self):
        """build_trace with minimal args uses sensible defaults."""
        random.seed(42)
        trace = build_trace(mode="full")
        self.assertGreater(len(trace["frames"]), 0)


if __name__ == "__main__":
    unittest.main()
