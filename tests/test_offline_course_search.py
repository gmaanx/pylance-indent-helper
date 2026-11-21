"""Check deterministic traces, graph shortest paths, and heuristic guarantees."""

import ast
from collections import deque
from contextlib import redirect_stdout
from io import StringIO
from itertools import permutations
import random
import unittest

from core_engine.offline_course_search import COURSE_SEARCH_SOLVERS, _solve_search_trace
from core_engine.offline_solver import OfflineProblemError


def _run(spec):
    problem = {"type": "search_trace", **spec}
    solution = COURSE_SEARCH_SOLVERS[problem["type"]](problem)
    output = StringIO()
    with redirect_stdout(output):
        exec(compile(solution.code, "<standalone>", "exec"), {"__name__": "__main__"})
    return ast.literal_eval(output.getvalue())


class CourseSearchTests(unittest.TestCase):
    def setUp(self):
        self.graph = {
            "start": "S", "goals": ["G"],
            "edges": [["S", "A", 4], ["S", "B", 1], ["A", "C", 4], ["C", "G", 1], ["B", "G", 2], ["C", "S"]],
        }

    def test_bfs_ucs_dfs_use_their_own_frontier_policy(self):
        cases = (
            ("bfs", ["S", "B", "G"], ["S", "A", "B", "C", "G"], "depth"),
            ("ucs", ["S", "B", "G"], ["S", "B", "G"], "cost"),
            ("dfs", ["S", "A", "C", "G"], ["S", "A", "C", "G"], None),
        )
        for algorithm, route, trace, optimal_for in cases:
            with self.subTest(algorithm=algorithm):
                result = _run({**self.graph, "algorithm": algorithm})
                self.assertEqual(result["path"], route)
                self.assertEqual([step["node"] for step in result["trace"]], trace)
                self.assertEqual(result["optimal_for"], optimal_for)

    def test_dls_distinguishes_depth_cutoff_from_an_exhausted_cycle(self):
        cutoff = _run({**self.graph, "algorithm": "dls", "depth_limit": 1})
        self.assertEqual(cutoff["status"], "cutoff")
        at_limit = _run({**self.graph, "algorithm": "dls", "depth_limit": 2})
        self.assertEqual(at_limit["path"], ["S", "B", "G"])
        cycle_only = [
            ["S", "A", 1], ["A", "S", 1],
        ]
        exhausted = _run({**self.graph, "algorithm": "dls", "depth_limit": 1, "edges": cycle_only})
        self.assertEqual(exhausted["status"], "unreachable")

    def test_ids_revisits_at_new_depths_and_reports_configured_cutoff(self):
        short = _run({**self.graph, "algorithm": "ids", "depth_limit": 1})
        self.assertEqual(short["status"], "cutoff")
        complete = _run({**self.graph, "algorithm": "ids"})
        self.assertEqual(complete["path"], ["S", "B", "G"])
        self.assertEqual(complete["rounds"], [
            {"limit": 0, "status": "cutoff", "trace_range": (0, 1)},
            {"limit": 1, "status": "cutoff", "trace_range": (1, 4)},
            {"limit": 2, "status": "found", "trace_range": (4, 9)},
        ])

    def test_astar_reopens_states_with_admissible_inconsistent_heuristic(self):
        graph = {
            "start": "S", "goals": ["G"],
            "edges": [["S", "A", 4], ["S", "B", 2], ["B", "A", 1], ["A", "G", 4]],
            "heuristic": {"S": 5, "A": 0, "B": 4, "G": 0},
        }
        result = _run({**graph, "algorithm": "astar"})
        self.assertEqual(result["path"], ["S", "B", "A", "G"])
        self.assertEqual(result["cost"], 7)
        self.assertEqual(result["optimal_for"], "cost")
        self.assertTrue(result["heuristic_check"]["admissible"])
        self.assertFalse(result["heuristic_check"]["consistent"])
        self.assertEqual([visit["g"] for visit in result["trace"] if visit["node"] == "A"], [4, 3])
        greedy = _run({**graph, "algorithm": "gbfs"})
        self.assertEqual(greedy["cost"], 8)
        self.assertIsNone(greedy["optimal_for"])
        graph["heuristic"]["B"] = 12
        inadmissible = _run({**graph, "algorithm": "astar"})
        self.assertEqual(inadmissible["cost"], 8)
        self.assertIsNone(inadmissible["optimal_for"])
        self.assertEqual(inadmissible["heuristic_check"]["overestimates"], ["B"])

    def test_ucs_and_zero_heuristic_astar_match_exhaustive_shortest_routes(self):
        rng = random.Random(74)
        nodes = list("SABGT")
        goals = ["G", "T"]
        for _ in range(60):
            edges = [(start, end, rng.randrange(7)) for start, end in permutations(nodes, 2) if rng.random() < 0.45]
            costs = {(start, end): weight for start, end, weight in edges}
            expected = []
            for length in range(3):
                for middle in permutations("AB", length):
                    for goal in goals:
                        route = ("S", *middle, goal)
                        steps = list(zip(route, route[1:]))
                        if all(step in costs for step in steps):
                            expected.append(sum(costs[step] for step in steps))
            for algorithm, heuristic in (("ucs", None), ("astar", dict.fromkeys(nodes, 0))):
                result = _solve_search_trace("S", goals, edges, algorithm, heuristic, True, None, 100)
                self.assertEqual(result["cost"], min(expected) if expected else None)
                self.assertEqual(result["status"], "found" if expected else "unreachable")

    def test_input_errors_and_budget_are_explicit(self):
        for fields, expected in (
            ({"algorithm": "dls"}, "needs_input"),
            ({"algorithm": "astar", "heuristic": {"S": 0}}, "needs_input"),
            ({"algorithm": "ucs", "depth_limit": 2}, "unsupported"),
            ({"algorithm": "ucs", "edges": [["S", "G", -1]]}, "invalid"),
        ):
            with self.subTest(fields=fields), self.assertRaises(OfflineProblemError) as caught:
                _run({**self.graph, **fields})
            self.assertEqual(caught.exception.status, expected)
        with self.assertRaises(OverflowError):
            _solve_search_trace("S", ["G"], [("S", "A", 1)], "dfs", None, True, None, 1)

    def test_puzzle_heuristics_match_independent_bfs_and_report_unreachable_boards(self):
        goal = (1, 2, 3, 4, 0, 5, 6, 7, 8)
        start = (1, 8, 2, 4, 0, 3, 7, 6, 5)
        allowed_swaps = (
            (1, 3), (0, 2, 4), (1, 5), (0, 4, 6), (1, 3, 5, 7),
            (2, 4, 8), (3, 7), (4, 6, 8), (5, 7),
        )
        queue = deque([(goal, 0)])
        seen = {goal}
        while queue:
            board, depth = queue.popleft()
            if board == start:
                break
            zero = board.index(0)
            for other in allowed_swaps[zero]:
                next_board = list(board)
                next_board[zero], next_board[other] = next_board[other], next_board[zero]
                key = tuple(next_board)
                if key not in seen:
                    seen.add(key)
                    queue.append((key, depth + 1))
        else:
            self.fail("Test boards should have the same parity")

        spec = {"type": "puzzle_heuristics", "start": list(start), "goal": list(goal)}
        result = _run(spec)
        self.assertEqual((result["status"], result["moves"]), ("found", depth))
        self.assertEqual(result["h1"]["initial"], 6)
        self.assertEqual(result["h2"]["initial"], 8)
        for heuristic in ("h1", "h2"):
            path = result[heuristic]["path"]
            self.assertEqual((path[0], path[-1], len(path) - 1), (start, goal, depth))
            for before, after in zip(path, path[1:]):
                self.assertIn(after.index(0), allowed_swaps[before.index(0)])
                changed = [index for index in range(9) if before[index] != after[index]]
                self.assertEqual(set(changed), {before.index(0), after.index(0)})

        unreachable = _run({**spec, "start": [2, 1, 3, 4, 0, 5, 6, 7, 8]})
        self.assertEqual(unreachable["status"], "unreachable")
        for heuristic in ("h1", "h2"):
            self.assertIsNone(unreachable[heuristic]["path"])
            self.assertEqual(unreachable[heuristic]["expanded"], 0)


if __name__ == "__main__":
    unittest.main()
