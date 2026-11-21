"""Independent exhaustive oracles and standalone checks for graph optimization."""

import ast
from contextlib import redirect_stdout
import io
from itertools import combinations, permutations
import random
import unittest

from core_engine.offline_combinatorial import _solve_assignment, _solve_max_flow, _solve_minimum_spanning_forest
from core_engine.offline_solver import OfflineProblemError, solve_spec


def _components(nodes, edges):
    adjacency = {name: set() for name in nodes}
    for start, end, _ in edges:
        adjacency[start].add(end)
        adjacency[end].add(start)
    components = set()
    unvisited = set(nodes)
    while unvisited:
        component = {unvisited.pop()}
        frontier = list(component)
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency[current] & unvisited:
                unvisited.remove(neighbor)
                component.add(neighbor)
                frontier.append(neighbor)
        components.add(frozenset(component))
    return components


class CombinatorialTests(unittest.TestCase):
    def test_assignment_matches_exhaustive_permutations(self):
        rng = random.Random(11)
        left, right = list("abc"), list("ABCD")
        for _ in range(90):
            edges = [(a, b, rng.randrange(-8, 15)) for a in left for b in right if rng.random() < 0.6]
            costs = {(a, b): cost for a, b, cost in edges}
            possibilities = []
            for permutation in permutations(right, len(left)):
                pairs = list(zip(left, permutation))
                if all(pair in costs for pair in pairs):
                    possibilities.append(sum(costs[pair] for pair in pairs))
            for objective in ("min", "max"):
                result = _solve_assignment(left, right, edges, objective)
                if not possibilities:
                    self.assertIsNone(result)
                    continue
                cost, pairs = result
                self.assertEqual([a for a, _ in pairs], left)
                self.assertEqual(len({b for _, b in pairs}), len(left))
                self.assertEqual(cost, sum(costs[pair] for pair in pairs))
                self.assertEqual(cost, (min if objective == "min" else max)(possibilities))

    def test_max_flow_matches_exhaustive_cuts_with_feasible_flow(self):
        rng = random.Random(12)
        nodes = list("sABZt")
        for _ in range(100):
            edges = [(a, b, rng.randrange(0, 10)) for a, b in permutations(nodes, 2) if rng.random() < 0.55]
            if edges:
                edges.append(rng.choice(edges))
            value, flows, (source_side, sink_side), capacity = _solve_max_flow(nodes, edges, "s", "t", 10_000)
            cuts = []
            for size in range(len(nodes) - 1):
                for subset in combinations(nodes[1:-1], size):
                    on_source_side = {"s", *subset}
                    cuts.append(sum(cap for a, b, cap in edges if a in on_source_side and b not in on_source_side))
            self.assertEqual(value, min(cuts))
            self.assertEqual(capacity, value)
            self.assertIn("s", source_side)
            self.assertIn("t", sink_side)
            self.assertEqual(set(source_side) | set(sink_side), set(nodes))
            self.assertFalse(set(source_side) & set(sink_side))
            self.assertEqual(capacity, sum(cap for a, b, cap in edges if a in source_side and b in sink_side))

            self.assertEqual([(a, b, cap) for a, b, _, cap in flows], edges)
            balance = dict.fromkeys(nodes, 0)
            for a, b, flow, cap in flows:
                self.assertLessEqual(0, flow)
                self.assertLessEqual(flow, cap)
                balance[a] += flow
                balance[b] -= flow
            self.assertEqual(balance, {"s": value, "t": -value, "A": 0, "B": 0, "Z": 0})

    def test_forest_matches_exhaustive_forests_with_isolates(self):
        rng = random.Random(13)
        nodes = list("ABCDE")
        for _ in range(100):
            edges = [(a, b, rng.randrange(-10, 21)) for a, b in combinations(nodes, 2) if rng.random() < 0.6]
            if edges:
                a, b, weight = rng.choice(edges)
                edges.append((b, a, weight - 1))
            expected_components = _components(nodes, edges)
            edge_count = len(nodes) - len(expected_components)
            possibilities = [
                sum(cost for _, _, cost in subset)
                for subset in combinations(edges, edge_count)
                if _components(nodes, subset) == expected_components
            ]
            weight, chosen, components = _solve_minimum_spanning_forest(nodes, edges)
            self.assertEqual(len(chosen), edge_count)
            self.assertEqual(_components(nodes, chosen), expected_components)
            self.assertEqual({frozenset(component) for component in components}, expected_components)
            self.assertEqual(weight, sum(cost for _, _, cost in chosen))
            self.assertEqual(weight, min(possibilities))

    def test_standalone_supports_three_models_and_result_metrics(self):
        cases = (
            (
                {"type": "assignment", "left": ["a", "b"], "right": ["x", "y", "z"], "objective": "max",
                 "edges": [["a", "x", 8], ["a", "y", 7], ["b", "x", 5], ["b", "z", -2]]},
                ("assignment_cost", 12),
            ),
            (
                {"type": "max_flow", "nodes": ["s", "a", "b", "x", "y", "t"], "source": "s", "sink": "t",
                 "edges": [["s", "a", 1], ["s", "b", 1], ["a", "x", 1], ["a", "y", 1], ["b", "x", 1],
                           ["x", "t", 1], ["y", "t", 1]]},
                ("max_flow", 2),
            ),
            (
                {"type": "minimum_spanning_forest", "nodes": ["A", "B", "C", "D", "E"],
                 "edges": [["A", "B", 6], ["A", "C", 2], ["B", "C", -3]]},
                ("spanning_forest_weight", -1),
            ),
        )
        for spec, metric in cases:
            with self.subTest(kind=spec["type"]):
                result = solve_spec(spec)
                self.assertEqual(result.metric, metric)
                output = io.StringIO()
                with redirect_stdout(output):
                    exec(compile(result.code, "<standalone>", "exec"), {"__name__": "__main__"})
                self.assertEqual(ast.literal_eval(output.getvalue())[0], metric[1])

    def test_assignment_infeasibility_and_validation(self):
        assignment = {"type": "assignment", "left": ["a", "b"], "right": ["a", "b"],
                      "edges": [["a", "a", 3], ["b", "a", 5]]}
        self.assertEqual(solve_spec(assignment).metric, ("assignment_cost", None))
        for spec, expected in (
            ({**assignment, "edges": [["a", "a", 3], ["a", "a", 5]]}, "invalid"),
            ({**assignment, "algorithm": "greedy"}, "unsupported"),
            ({**assignment, "right": list("abcdefghijklmnop")}, "limit"),
            ({"type": "max_flow", "nodes": ["s", "t"], "source": "s", "sink": "t",
              "edges": [["s", "t", -1]]}, "invalid"),
        ):
            with self.subTest(spec=spec), self.assertRaises(OfflineProblemError) as caught:
                solve_spec(spec)
            self.assertEqual(caught.exception.status, expected)
        with self.assertRaises(OverflowError):
            _solve_max_flow(["s", "t"], [("s", "t", 1)], "s", "t", 0)


if __name__ == "__main__":
    unittest.main()
