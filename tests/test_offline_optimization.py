"""Independent small-case oracles and end-to-end tests for optimization models."""

import ast
from contextlib import redirect_stdout
import io
from itertools import combinations, permutations
import json
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core_engine.offline_optimization import (
    _solve_interval_scheduling,
    _solve_knapsack,
    _solve_tsp,
)
from core_engine.offline_solver import OfflineProblemError, solve_offline


def _all_subsets(items):
    for size in range(len(items) + 1):
        yield from combinations(items, size)


def _run_spec(spec):
    solution = solve_offline("@solve " + json.dumps(spec), None)
    output = io.StringIO()
    with redirect_stdout(output):
        exec(compile(solution.code, "<standalone>", "exec"), {"__name__": "__main__"})
    return ast.literal_eval(output.getvalue())


class OptimizationOracleTests(unittest.TestCase):
    def test_knapsack_matches_exhaustive_with_required_count_and_ties(self):
        rng = random.Random(7)
        for _ in range(100):
            items = [(str(i), rng.randrange(0, 6), rng.randrange(-5, 9)) for i in range(8)]
            capacity = rng.randrange(0, 15)
            required = rng.sample([row[0] for row in items], rng.randrange(4))
            count = rng.choice([None, 0, 2, 4, 6, 8])
            for tie in ("min_weight", "fewest_items"):
                possible = []
                for subset in _all_subsets(items):
                    members = {row[0] for row in subset}
                    weight = sum(row[1] for row in subset)
                    if weight > capacity or not set(required).issubset(members):
                        continue
                    if count is not None and len(subset) != count:
                        continue
                    value = sum(row[2] for row in subset)
                    secondary = (-weight, -len(subset)) if tie == "min_weight" else (-len(subset), -weight)
                    possible.append((value, *secondary))
                result = _solve_knapsack(items, capacity, required, count, tie, 10_000)
                if not possible:
                    self.assertIsNone(result)
                    continue
                value, weight, selected = result
                selected_items = [row for row in items if row[0] in selected]
                self.assertEqual(len(selected_items), len(selected))
                self.assertEqual(sum(row[1] for row in selected_items), weight)
                self.assertEqual(sum(row[2] for row in selected_items), value)
                self.assertTrue(set(required).issubset(selected))
                self.assertLessEqual(weight, capacity)
                if count is not None:
                    self.assertEqual(len(selected), count)
                secondary = (-weight, -len(selected)) if tie == "min_weight" else (-len(selected), -weight)
                self.assertEqual((value, *secondary), max(possible))

    def test_tsp_matches_exhaustive_on_asymmetric_incomplete_graphs(self):
        rng = random.Random(8)
        nodes = list("SABCD")
        for _ in range(80):
            edges = [(a, b, rng.randrange(-5, 21)) for a, b in permutations(nodes, 2) if rng.random() < 0.6]
            cost_by_edge = {(a, b): cost for a, b, cost in edges}
            for end, cycle in ((None, True), (None, False), ("B", False)):
                possible = []
                for permutation in permutations(nodes[1:]):
                    path = ["S", *permutation]
                    if end is not None and path[-1] != end:
                        continue
                    if cycle:
                        path.append("S")
                    steps = list(zip(path, path[1:]))
                    if all(edge in cost_by_edge for edge in steps):
                        possible.append((sum(cost_by_edge[edge] for edge in steps), path))
                result = _solve_tsp(nodes, edges, "S", end, cycle)
                if not possible:
                    self.assertIsNone(result)
                else:
                    self.assertIn(result, possible)
                    self.assertEqual(result[0], min(value for value, _ in possible))

    def test_interval_scheduling_matches_exhaustive_with_required_jobs(self):
        rng = random.Random(9)
        for _ in range(100):
            start_times = [rng.randrange(-3, 12) for _ in range(8)]
            intervals = [
                (str(index), start, start + rng.randrange(1, 6), rng.randrange(-5, 16))
                for index, start in enumerate(start_times)
            ]
            required = rng.sample([row[0] for row in intervals], rng.randrange(4))
            possible = []
            for subset in _all_subsets(intervals):
                if not set(required).issubset(row[0] for row in subset):
                    continue
                ordered = sorted(subset, key=lambda row: row[1])
                if all(left[2] <= right[1] for left, right in zip(ordered, ordered[1:])):
                    possible.append((sum(row[3] for row in ordered), [row[0] for row in ordered]))
            result = _solve_interval_scheduling(intervals, required)
            if not possible:
                self.assertIsNone(result)
            else:
                self.assertIn(result, possible)
                self.assertEqual(result[0], max(value for value, _ in possible))


class OptimizationSpecTests(unittest.TestCase):
    def test_standalone_knapsack_uses_count_and_mandatory_item(self):
        spec = {
            "type": "knapsack", "capacity": 7,
            "items": [["a", 3, 6], ["b", 4, 7], ["c", 1, 2], ["d", 0, -1]],
            "required": ["c"], "count": 2,
        }
        self.assertEqual(_run_spec(spec), (9, 5, ["b", "c"]))
        self.assertIsNone(_run_spec({**spec, "capacity": 0}))
        with self.assertRaises(OverflowError):
            _solve_knapsack([("a", 1, 1), ("b", 2, 2)], 5, [], None, "min_weight", 1)

    def test_standalone_tsp_checks_missing_final_edge_and_start_end(self):
        spec = {
            "type": "tsp", "nodes": ["S", "A", "B"], "start": "S",
            "edges": [["S", "A", 4], ["A", "B", 2]], "directed": True,
        }
        self.assertIsNone(_run_spec(spec))
        self.assertEqual(_run_spec({**spec, "return_to_start": False, "end": "B"}), (6, ["S", "A", "B"]))
        self.assertIsNone(_run_spec({**spec, "return_to_start": False, "end": "A"}))

    def test_standalone_schedules_compute_reward_and_critical_path(self):
        interval = {
            "type": "interval_scheduling",
            "intervals": [["a", 0, 3, 9], ["b", 3, 5, 8], ["c", 0, 5, 15]],
        }
        self.assertEqual(_run_spec(interval), (17, ["a", "b"]))
        self.assertIsNone(_run_spec({**interval, "required": ["a", "c"]}))
        precedence = {
            "type": "precedence_scheduling",
            "tasks": [["a", 4], ["b", 6], ["c", 3], ["d", 5]],
            "dependencies": [["a", "c"], ["b", "c"], ["c", "d"]],
        }
        self.assertEqual(_run_spec(precedence), (
            14, [("a", 0, 4), ("b", 0, 6), ("c", 6, 9), ("d", 9, 14)], ["b", "c", "d"],
        ))
        self.assertIsNone(_run_spec({**precedence, "dependencies": [*precedence["dependencies"], ["d", "b"]]}))

    def test_invalid_unknown_and_unbounded_models_are_not_accepted(self):
        cases = (
            ("unsupported", {"type": "knapsack", "capacity": 5, "items": [["a", 1, 1]], "max_per_item": 3}),
            ("invalid", {"type": "knapsack", "capacity": 5, "items": [["a", 1, 1]], "required": ["missing"]}),
            ("limit", {"type": "tsp", "nodes": [str(i) for i in range(14)], "start": "0", "edges": []}),
            ("unsupported", {"type": "precedence_scheduling", "tasks": [["a", 7]], "dependencies": [], "machines": 2}),
            ("invalid", {"type": "interval_scheduling", "intervals": [["a", 1, 1, 9]]}),
        )
        for expected, spec in cases:
            with self.subTest(spec=spec), self.assertRaises(OfflineProblemError) as caught:
                _run_spec(spec)
            self.assertEqual(caught.exception.status, expected)


if __name__ == "__main__":
    unittest.main()
