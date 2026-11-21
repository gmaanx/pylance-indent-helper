"""Exercise emitted SimpleAI programs and their correctness boundaries."""

import ast
from contextlib import redirect_stdout
from io import StringIO
from itertools import permutations
import random
import unittest

from core_engine.offline_simpleai_search import SIMPLEAI_SEARCH_SOLVERS, _solve_simpleai_graph
from core_engine.offline_solver import OfflineProblemError


def _run(spec):
    solution = SIMPLEAI_SEARCH_SOLVERS[spec["type"]](spec)
    output = StringIO()
    with redirect_stdout(output):
        exec(compile(solution.code, "<simpleai-standalone>", "exec"), {"__name__": "__main__"})
    return ast.literal_eval(output.getvalue()), solution


class SimpleAISearchTests(unittest.TestCase):
    def test_bfs_and_ucs_observe_different_objectives_on_uneven_costs(self):
        spec = {
            "type": "simpleai_graph", "start": "S", "goals": ["G"],
            "edges": [["S", "G", 13], ["S", "A", 2], ["A", "G", 3]],
        }
        bfs, bfs_solution = _run({**spec, "algorithm": "bfs"})
        ucs, ucs_solution = _run({**spec, "algorithm": "ucs"})
        self.assertEqual((bfs["path"], bfs["cost"], bfs["optimal_for"]), (["S", "G"], 13, "depth"))
        self.assertEqual(bfs_solution.metric, ("minimum_depth", 1))
        self.assertEqual((ucs["path"], ucs["cost"], ucs["optimal_for"]), (["S", "A", "G"], 5, "cost"))
        self.assertEqual(ucs_solution.metric, ("minimum_cost", 5))

    def test_graph_search_respects_direction_and_multiple_goals(self):
        spec = {
            "type": "simpleai_graph", "start": "S", "goals": ["X", "G"], "algorithm": "ucs",
            "edges": [["G", "A", 1], ["A", "S", 2], ["X", "S", 8]],
        }
        directed, _ = _run(spec)
        undirected, _ = _run({**spec, "directed": False})
        self.assertEqual(directed["status"], "unreachable")
        self.assertEqual((undirected["cost"], undirected["path"]), (3, ["S", "A", "G"]))

    def test_dls_can_reconsider_a_state_at_a_shallower_depth(self):
        spec = {
            "type": "simpleai_graph", "start": "S", "goals": ["G"],
            "edges": [["S", "A"], ["A", "B"], ["S", "B"], ["B", "S"], ["B", "G"]],
        }
        dls, _ = _run({**spec, "algorithm": "dls", "depth_limit": 2})
        ids, _ = _run({**spec, "algorithm": "ids"})
        dfs, _ = _run({**spec, "algorithm": "dfs"})
        self.assertEqual(dls["path"], ["S", "B", "G"])
        self.assertEqual(ids["path"], ["S", "B", "G"])
        self.assertEqual([entry["status"] for entry in ids["rounds"]], ["cutoff", "cutoff", "found"])
        self.assertEqual(dfs["status"], "found")
        self.assertIsNone(dfs["optimal_for"])
        cutoff, _ = _run({**spec, "algorithm": "ids", "depth_limit": 1})
        self.assertEqual(cutoff["status"], "cutoff")
        exhausted, _ = _run({**spec, "algorithm": "ids", "edges": [["S", "B"], ["B", "S"]]})
        self.assertEqual(exhausted["status"], "unreachable")

    def test_greedy_and_astar_observe_distinct_priorities(self):
        spec = {
            "type": "simpleai_graph", "start": "S", "goals": ["G"],
            "edges": [["S", "A", 9], ["S", "B", 2], ["A", "G", 1], ["B", "G", 3]],
            "heuristic": {"S": 0, "A": 0, "B": 3, "G": 0},
        }
        greedy, _ = _run({**spec, "algorithm": "greedy"})
        astar, _ = _run({**spec, "algorithm": "astar"})
        self.assertEqual((greedy["cost"], greedy["optimal_for"]), (10, None))
        self.assertEqual((astar["cost"], astar["optimal_for"]), (5, "cost"))
        with self.assertRaises(OfflineProblemError) as caught:
            _run({**spec, "algorithm": "astar", "heuristic": {**spec["heuristic"], "S": 6}})
        self.assertEqual(caught.exception.status, "unsupported")

    def test_ucs_and_astar_match_exhaustive_route_costs(self):
        rng = random.Random(142)
        vertices = list("SABCG")
        for _ in range(55):
            edges = [(u, v, rng.randrange(0, 10)) for u, v in permutations(vertices, 2) if rng.random() < 0.54]
            weights = {(u, v): cost for u, v, cost in edges}
            possibilities = []
            for length in range(len(vertices) - 1):
                for middle in permutations(vertices[1:-1], length):
                    path = ("S", *middle, "G")
                    steps = list(zip(path, path[1:]))
                    if all(step in weights for step in steps):
                        possibilities.append(sum(weights[step] for step in steps))
            expected = min(possibilities) if possibilities else None
            for algorithm, heuristic in (("ucs", None), ("astar", dict.fromkeys(vertices, 0))):
                result = _solve_simpleai_graph("S", ["G"], edges, algorithm, True, heuristic, None, 100)
                self.assertEqual(result["cost"], expected)

    def test_8_puzzle_supports_both_heuristics_and_returns_legal_path(self):
        goal = [1, 2, 3, 4, 0, 5, 6, 7, 8]
        start = [1, 2, 3, 4, 7, 5, 0, 6, 8]
        spec = {"type": "simpleai_puzzle", "goal": goal, "start": start}
        for heuristic in ("misplaced", "manhattan"):
            result, solution = _run({**spec, "heuristic": heuristic})
            self.assertEqual(result["moves"], 2)
            self.assertEqual(result["path"][0], tuple(start))
            self.assertEqual(result["path"][-1], tuple(goal))
            self.assertEqual(solution.metric, ("minimum_moves", 2))
            for before, after in zip(result["path"], result["path"][1:]):
                old_blank, new_blank = before.index(0), after.index(0)
                old_row, old_column = divmod(old_blank, 3)
                new_row, new_column = divmod(new_blank, 3)
                self.assertEqual(abs(old_row - new_row) + abs(old_column - new_column), 1)
                self.assertEqual([i for i in range(9) if before[i] != after[i]], sorted((old_blank, new_blank)))
        unreachable, _ = _run({**spec, "start": [2, 1, 3, 4, 0, 5, 6, 7, 8]})
        self.assertEqual((unreachable["status"], unreachable["visited"]), ("unreachable", 0))

    def test_input_errors_and_budget_are_explicit(self):
        spec = {"type": "simpleai_graph", "start": "S", "goals": ["G"], "edges": [["S", "G"]]}
        for fields, expected in (
            ({"algorithm": "dls"}, "needs_input"),
            ({"algorithm": "bfs", "depth_limit": 2}, "unsupported"),
            ({"algorithm": "ucs", "edges": [["S", "G", -1]]}, "invalid"),
            ({"algorithm": "astar", "heuristic": {"S": 0}}, "needs_input"),
            ({"algorithm": "astar", "heuristic": {"S": 0, "G": 1}}, "invalid"),
        ):
            with self.subTest(fields=fields), self.assertRaises(OfflineProblemError) as caught:
                _run({**spec, **fields})
            self.assertEqual(caught.exception.status, expected)
        with self.assertRaises(OverflowError):
            _solve_simpleai_graph("S", ["G"], [("S", "G", 1)], "bfs", True, None, None, 1)


if __name__ == "__main__":
    unittest.main()
