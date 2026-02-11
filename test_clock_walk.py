"""
Tests for the critical components of clock_walk.py and the clockwalk library.

Run with:  python test_clock_walk.py
Or:        python -m pytest test_clock_walk.py -v
"""

import json
import math
import os
import random
import tempfile
import unittest
from collections import Counter

# Import via the CLI script (backwards-compatible path)
from clock_walk import (
    DEFAULTS,
    choose_move_multimodal,
    dist_clockwise,
    dist_min_steps,
    list_data_files,
    load_config_from_file,
    parse_attractor_string,
    resolve_data_file,
    run_staleness_winner,
    step_idx,
    validate_config,
)

# Import directly from the library package
import clockwalk
from clockwalk.walk import StalenessTracker, choose_move
from clockwalk.runner import run_monte_carlo

LABELS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


# ================================================================
# Geometry helpers
# ================================================================

class TestStepIdx(unittest.TestCase):
    def test_forward(self):
        self.assertEqual(step_idx(0, 1, 12), 1)
        self.assertEqual(step_idx(5, 1, 12), 6)

    def test_backward(self):
        self.assertEqual(step_idx(0, -1, 12), 11)
        self.assertEqual(step_idx(3, -1, 12), 2)

    def test_wraparound_forward(self):
        self.assertEqual(step_idx(11, 1, 12), 0)

    def test_wraparound_backward(self):
        self.assertEqual(step_idx(0, -1, 12), 11)

    def test_stay(self):
        self.assertEqual(step_idx(7, 0, 12), 7)

    def test_library_matches_script(self):
        for i in range(12):
            for mv in (-1, 0, +1):
                self.assertEqual(
                    step_idx(i, mv, 12),
                    clockwalk.step_idx(i, mv, 12),
                )


class TestDistMinSteps(unittest.TestCase):
    def test_same_position(self):
        self.assertEqual(dist_min_steps(12, 0, 0), 0)

    def test_adjacent(self):
        self.assertEqual(dist_min_steps(12, 0, 1), 1)
        self.assertEqual(dist_min_steps(12, 0, 11), 1)

    def test_opposite(self):
        self.assertEqual(dist_min_steps(12, 0, 6), 6)

    def test_symmetry(self):
        for i in range(12):
            for j in range(12):
                self.assertEqual(dist_min_steps(12, i, j), dist_min_steps(12, j, i))

    def test_max_is_half(self):
        for i in range(12):
            for j in range(12):
                self.assertLessEqual(dist_min_steps(12, i, j), 6)


class TestDistClockwise(unittest.TestCase):
    def test_same(self):
        self.assertEqual(dist_clockwise(12, 0, 0), 0)

    def test_forward(self):
        self.assertEqual(dist_clockwise(12, 0, 3), 3)

    def test_wraparound(self):
        self.assertEqual(dist_clockwise(12, 11, 1), 2)

    def test_full_range(self):
        for i in range(12):
            for j in range(12):
                d = dist_clockwise(12, i, j)
                self.assertGreaterEqual(d, 0)
                self.assertLess(d, 12)


# ================================================================
# Config validation
# ================================================================

class TestValidateConfig(unittest.TestCase):
    def test_defaults_pass_through(self):
        cfg = validate_config(DEFAULTS.copy())
        self.assertEqual(cfg["runs"], DEFAULTS["runs"])
        self.assertEqual(cfg["target"], DEFAULTS["target"])

    def test_clamps_target(self):
        cfg = validate_config({**DEFAULTS, "target": 0})
        self.assertEqual(cfg["target"], 1)
        cfg = validate_config({**DEFAULTS, "target": 99})
        self.assertEqual(cfg["target"], 12)

    def test_clamps_inertia(self):
        cfg = validate_config({**DEFAULTS, "inertia": -0.5})
        self.assertEqual(cfg["inertia"], 0.0)
        cfg = validate_config({**DEFAULTS, "inertia": 2.0})
        self.assertEqual(cfg["inertia"], 1.0)

    def test_clamps_teleport(self):
        cfg = validate_config({**DEFAULTS, "teleport_p": 0.5})
        self.assertEqual(cfg["teleport_p"], 0.2)

    def test_clamps_stay(self):
        cfg = validate_config({**DEFAULTS, "stay_p": 0.9})
        self.assertEqual(cfg["stay_p"], 0.5)

    def test_runs_minimum(self):
        cfg = validate_config({**DEFAULTS, "runs": -10})
        self.assertEqual(cfg["runs"], 1)

    def test_attractors_deduped(self):
        cfg = validate_config({**DEFAULTS, "attractors": [3, 3, 6, 6, 9]})
        self.assertEqual(cfg["attractors"], [3, 6, 9])

    def test_attractors_out_of_range_dropped(self):
        cfg = validate_config({**DEFAULTS, "attractors": [0, 5, 13, 7]})
        self.assertEqual(cfg["attractors"], [5, 7])

    def test_attractors_from_string(self):
        cfg = validate_config({**DEFAULTS, "attractors": "1,6,9"})
        self.assertEqual(cfg["attractors"], [1, 6, 9])

    def test_non_numeric_inertia_becomes_zero(self):
        cfg = validate_config({**DEFAULTS, "inertia": "abc"})
        self.assertEqual(cfg["inertia"], 0.0)


class TestParseAttractorString(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_attractor_string("1,6,9"), [1, 6, 9])

    def test_empty(self):
        self.assertEqual(parse_attractor_string(""), [])

    def test_dedup(self):
        self.assertEqual(parse_attractor_string("3,3,3"), [3])

    def test_out_of_range(self):
        self.assertEqual(parse_attractor_string("0,5,13"), [5])

    def test_garbage_mixed(self):
        self.assertEqual(parse_attractor_string("a,2,b,7,"), [2, 7])

    def test_spaces(self):
        self.assertEqual(parse_attractor_string(" 1 , 6 , 9 "), [1, 6, 9])


# ================================================================
# Move selection
# ================================================================

class TestChooseMoveMultimodal(unittest.TestCase):
    def test_teleport_guaranteed(self):
        random.seed(0)
        result = choose_move_multimodal(
            pos=0, last_move=1, labels=LABELS, visited_set=set(LABELS),
            inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            stay_p=0.0, teleport_p=1.0,
        )
        self.assertEqual(result, "TELEPORT")

    def test_stay_guaranteed(self):
        random.seed(0)
        result = choose_move_multimodal(
            pos=0, last_move=1, labels=LABELS, visited_set=set(LABELS),
            inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            stay_p=1.0, teleport_p=0.0,
        )
        self.assertEqual(result, 0)

    def test_no_teleport_no_stay_returns_direction(self):
        random.seed(42)
        result = choose_move_multimodal(
            pos=3, last_move=None, labels=LABELS, visited_set={LABELS[3]},
            inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            stay_p=0.0, teleport_p=0.0,
        )
        self.assertIn(result, (-1, +1))

    def test_extreme_inertia_continues_direction(self):
        random.seed(42)
        directions = []
        for _ in range(200):
            mv = choose_move_multimodal(
                pos=3, last_move=+1, labels=LABELS, visited_set=set(LABELS),
                inertia_p=1.0, novelty_bonus=0.0,
                attractors=[], attract_strength=0.0,
                stay_p=0.0, teleport_p=0.0,
            )
            directions.append(mv)
        self.assertTrue(all(d == +1 for d in directions))

    def test_zero_inertia_ignores_last_move(self):
        random.seed(42)
        directions = []
        for _ in range(200):
            mv = choose_move_multimodal(
                pos=3, last_move=+1, labels=LABELS, visited_set=set(LABELS),
                inertia_p=0.0, novelty_bonus=0.0,
                attractors=[], attract_strength=0.0,
                stay_p=0.0, teleport_p=0.0,
            )
            directions.append(mv)
        self.assertTrue(all(d == -1 for d in directions))

    def test_balanced_inertia_is_fair(self):
        random.seed(42)
        counts = Counter()
        for _ in range(10000):
            mv = choose_move_multimodal(
                pos=3, last_move=+1, labels=LABELS, visited_set=set(LABELS),
                inertia_p=0.5, novelty_bonus=0.0,
                attractors=[], attract_strength=0.0,
                stay_p=0.0, teleport_p=0.0,
            )
            counts[mv] += 1
        ratio = counts[+1] / counts[-1]
        self.assertAlmostEqual(ratio, 1.0, delta=0.15)

    def test_novelty_prefers_unvisited(self):
        random.seed(42)
        visited = set(LABELS) - {4}
        counts = Counter()
        for _ in range(10000):
            mv = choose_move_multimodal(
                pos=3, last_move=None, labels=LABELS, visited_set=visited,
                inertia_p=0.5, novelty_bonus=0.9,
                attractors=[], attract_strength=0.0,
                stay_p=0.0, teleport_p=0.0,
            )
            counts[mv] += 1
        self.assertGreater(counts[+1], counts[-1])

    def test_library_choose_move_matches(self):
        """Library choose_move produces same results as script choose_move_multimodal."""
        for seed in (0, 42, 123):
            random.seed(seed)
            a = choose_move_multimodal(
                pos=5, last_move=+1, labels=LABELS, visited_set={LABELS[5]},
                inertia_p=0.7, novelty_bonus=0.2,
                attractors=[6], attract_strength=0.8,
                stay_p=0.02, teleport_p=0.002,
            )
            random.seed(seed)
            b = choose_move(
                pos=5, last_move=+1, labels=LABELS, visited_set={LABELS[5]},
                inertia_p=0.7, novelty_bonus=0.2,
                attractors=[6], attract_strength=0.8,
                stay_p=0.02, teleport_p=0.002,
            )
            self.assertEqual(a, b)


# ================================================================
# StalenessTracker (library-only class)
# ================================================================

class TestStalenessTracker(unittest.TestCase):
    def test_all_never_visited(self):
        t = StalenessTracker(LABELS)
        self.assertEqual(set(t.never_visited()), set(LABELS))

    def test_visit_removes_from_never(self):
        t = StalenessTracker(LABELS)
        t.visit(12, 0)
        self.assertNotIn(12, t.never_visited())
        self.assertEqual(len(t.never_visited()), 11)

    def test_stalest_returns_never_visited_first(self):
        t = StalenessTracker(LABELS)
        t.visit(12, 0)
        t.visit(1, 1)
        # 10 never-visited labels should be returned
        winners = t.stalest(current_time=1)
        self.assertEqual(len(winners), 10)
        self.assertNotIn(12, winners)
        self.assertNotIn(1, winners)

    def test_stalest_after_all_visited(self):
        t = StalenessTracker([1, 2, 3])
        t.visit(1, 0)
        t.visit(2, 5)
        t.visit(3, 10)
        # At time 10: staleness of 1=10, 2=5, 3=0
        winners = t.stalest(current_time=10)
        self.assertEqual(winners, [1])

    def test_stalest_tie(self):
        t = StalenessTracker([1, 2, 3])
        t.visit(1, 0)
        t.visit(2, 0)
        t.visit(3, 5)
        # At time 5: staleness of 1=5, 2=5, 3=0
        winners = t.stalest(current_time=5)
        self.assertEqual(set(winners), {1, 2})


# ================================================================
# Staleness winner simulation
# ================================================================

class TestRunStalenessWinner(unittest.TestCase):
    def test_returns_valid_label(self):
        random.seed(42)
        for _ in range(100):
            w = run_staleness_winner(
                LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
                attractors=[], attract_strength=0.0,
                steps=50, stay_p=0.0, teleport_p=0.0,
            )
            self.assertIn(w, LABELS)

    def test_single_step_returns_non_start(self):
        random.seed(42)
        results = set()
        for _ in range(200):
            w = run_staleness_winner(
                LABELS, 0, inertia_p=0.5, novelty_bonus=0.0,
                attractors=[], attract_strength=0.0,
                steps=1, stay_p=0.0, teleport_p=0.0,
            )
            results.add(w)
        self.assertNotIn(12, results)

    def test_very_long_walk_covers_all(self):
        random.seed(42)
        w = run_staleness_winner(
            LABELS, 0, inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            steps=10000, stay_p=0.0, teleport_p=0.1,
        )
        self.assertIn(w, LABELS)

    def test_deterministic_with_seed(self):
        random.seed(123)
        w1 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=100, stay_p=0.02, teleport_p=0.002,
        )
        random.seed(123)
        w2 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=100, stay_p=0.02, teleport_p=0.002,
        )
        self.assertEqual(w1, w2)

    def test_stay_only_walk_favors_distant(self):
        random.seed(42)
        results = set()
        for _ in range(500):
            w = run_staleness_winner(
                LABELS, 0, inertia_p=0.5, novelty_bonus=0.0,
                attractors=[], attract_strength=0.0,
                steps=50, stay_p=1.0, teleport_p=0.0,
            )
            results.add(w)
        self.assertNotIn(12, results)
        self.assertEqual(len(results), 11)

    def test_library_and_script_agree(self):
        """Library run_staleness_winner matches script's version."""
        random.seed(42)
        w1 = run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=100, stay_p=0.02, teleport_p=0.002,
        )
        random.seed(42)
        w2 = clockwalk.run_staleness_winner(
            LABELS, 0, inertia_p=0.7, novelty_bonus=0.2,
            attractors=[6], attract_strength=0.8,
            steps=100, stay_p=0.02, teleport_p=0.002,
        )
        self.assertEqual(w1, w2)


# ================================================================
# Statistical distribution tests (Monte Carlo sanity checks)
# ================================================================

class TestDistributionProperties(unittest.TestCase):
    def _run_batch(self, runs=2000, **kwargs):
        params = dict(
            inertia_p=0.5, novelty_bonus=0.0,
            attractors=[], attract_strength=0.0,
            steps=100, stay_p=0.0, teleport_p=0.0,
        )
        params.update(kwargs)
        counts = Counter()
        for _ in range(runs):
            w = run_staleness_winner(LABELS, 0, **params)
            counts[w] += 1
        return counts

    def test_pure_random_roughly_uniform(self):
        random.seed(42)
        counts = self._run_batch(runs=6000, inertia_p=0.5, steps=500)
        vals = [counts.get(lab, 0) for lab in LABELS]
        expected = 6000 / 12
        for v in vals:
            self.assertAlmostEqual(v, expected, delta=expected * 0.5)

    def test_attractor_shifts_staleness_away(self):
        random.seed(42)
        counts = self._run_batch(
            runs=5000, attractors=[6], attract_strength=0.9, steps=200,
        )
        avg = 5000 / 12
        self.assertLess(counts.get(6, 0), avg)

    def test_high_inertia_concentrates_near_start(self):
        random.seed(42)
        counts = self._run_batch(
            runs=5000, inertia_p=0.95, steps=200,
        )
        near_start = counts.get(11, 0) + counts.get(1, 0)
        far_away = counts.get(5, 0) + counts.get(7, 0)
        self.assertGreater(near_start, far_away)


# ================================================================
# Monte Carlo runner (library)
# ================================================================

class TestRunMonteCarlo(unittest.TestCase):
    def test_basic_counting(self):
        random.seed(42)
        counts = run_monte_carlo(
            lambda: random.choice([1, 2, 3]),
            n=3000,
            progress_every=10000,  # suppress spinner output
        )
        self.assertEqual(sum(counts.values()), 3000)
        self.assertTrue(all(k in (1, 2, 3) for k in counts))

    def test_single_outcome(self):
        counts = run_monte_carlo(lambda: "X", n=10, progress_every=100)
        self.assertEqual(counts["X"], 10)


# ================================================================
# Data file resolution
# ================================================================

class TestDataFileResolution(unittest.TestCase):
    def test_list_data_files_returns_entries(self):
        entries = list_data_files()
        self.assertGreater(len(entries), 0)
        for idx, fname, fpath in entries:
            self.assertTrue(fname.endswith(".json"))
            self.assertTrue(os.path.isfile(fpath))

    def test_resolve_by_index(self):
        fpath = resolve_data_file("0")
        self.assertIsNotNone(fpath)
        self.assertIn("0_", os.path.basename(fpath))

    def test_resolve_by_substring(self):
        fpath = resolve_data_file("sticky")
        self.assertIsNotNone(fpath)
        self.assertIn("sticky", os.path.basename(fpath))

    def test_resolve_nonexistent_index(self):
        fpath = resolve_data_file("999")
        self.assertIsNone(fpath)

    def test_resolve_nonexistent_name(self):
        fpath = resolve_data_file("zzz_no_match")
        self.assertIsNone(fpath)

    def test_load_config_from_file(self):
        fpath = resolve_data_file("0")
        self.assertIsNotNone(fpath)
        cfg = load_config_from_file(fpath)
        for key in DEFAULTS:
            self.assertIn(key, cfg)

    def test_all_data_files_load_successfully(self):
        entries = list_data_files()
        for idx, fname, fpath in entries:
            cfg = load_config_from_file(fpath)
            self.assertIsInstance(cfg, dict)
            self.assertIn("runs", cfg)
            self.assertIn("steps", cfg)


# ================================================================
# Config loading from temp file
# ================================================================

class TestLoadConfigFromFile(unittest.TestCase):
    def test_minimal_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"runs": 42}, f)
            f.flush()
            cfg = load_config_from_file(f.name)
        os.unlink(f.name)
        self.assertEqual(cfg["runs"], 42)
        self.assertEqual(cfg["target"], DEFAULTS["target"])

    def test_empty_object(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            f.flush()
            cfg = load_config_from_file(f.name)
        os.unlink(f.name)
        self.assertEqual(cfg, validate_config(DEFAULTS.copy()))

    def test_extra_keys_preserved(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"runs": 10, "_description": "test"}, f)
            f.flush()
            cfg = load_config_from_file(f.name)
        os.unlink(f.name)
        self.assertEqual(cfg["_description"], "test")

    def test_invalid_json_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("[1,2,3]")
            f.flush()
            with self.assertRaises(ValueError):
                load_config_from_file(f.name)
        os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
