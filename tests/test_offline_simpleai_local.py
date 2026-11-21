"""Verify SimpleAI N-queens witnesses and bounded search behavior."""

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core_engine.engine_pipeline import process_request
from core_engine.offline_simpleai_local import _attacking_pairs, _search_queens, _simpleai_local_nqueens
from core_engine.offline_solver import OfflineProblemError


TYPE = "simpleai_local_nqueens"
HAS_SIMPLEAI = importlib.util.find_spec("simpleai") is not None


def direct_attacks(board):
    return sum(
        board[left] == board[right] or abs(board[left] - board[right]) == right - left
        for left in range(len(board)) for right in range(left + 1, len(board))
    )


def run_standalone(code):
    output = io.StringIO()
    with redirect_stdout(output):
        exec(compile(code, "<local-simpleai>", "exec"), {"__name__": "__main__"})
    return ast.literal_eval(output.getvalue())


class SimpleAiLocalTests(unittest.TestCase):
    def test_fitness_matches_independent_pairwise_count(self):
        rng = random.Random(23)
        for width in (1, 4, 8, 25):
            for _ in range(25):
                board = [rng.randrange(width) for _ in range(width)]
                self.assertEqual(_attacking_pairs(board), direct_attacks(board))

    def test_trivial_and_impossible_board_sizes(self):
        for width in (1, 2, 3):
            with self.subTest(width=width):
                solution = _simpleai_local_nqueens({"type": TYPE, "n": width})
                result = run_standalone(solution.code)
                self.assertEqual(solution.metric, ("satisfiable", width == 1))
                self.assertEqual(solution.validation_status, "verified")
                self.assertEqual(result["evaluations"], 0)
                self.assertEqual(result["board"], [0] if width == 1 else None)

    @unittest.skipUnless(HAS_SIMPLEAI, "requires SimpleAI")
    def test_all_seven_algorithms_return_checked_seeded_results(self):
        methods = {
            "hill_climbing": {},
            "hill_climbing_stochastic": {},
            "hill_climbing_random_restarts": {"restarts_limit": 8},
            "beam": {"beam_size": 5},
            "beam_best_first": {"beam_size": 5},
            "simulated_annealing": {},
            "genetic": {"population_size": 6, "mutation_chance": 0.2},
        }
        state = random.getstate()
        for method, options in methods.items():
            with self.subTest(method=method):
                solution = _simpleai_local_nqueens({
                    "type": TYPE, "algorithm": method, "n": 5, "seed": 17,
                    "iterations_limit": 20, **options,
                })
                result = run_standalone(solution.code)
                self.assertEqual(result["attacking_pairs"], direct_attacks(result["board"]))
                self.assertEqual(result, run_standalone(solution.code))
                self.assertEqual(random.getstate(), state)
                self.assertEqual(solution.validation_status == "verified", result["attacking_pairs"] == 0)

    @unittest.skipUnless(HAS_SIMPLEAI, "requires SimpleAI")
    def test_end_to_end_distinguishes_witness_from_budget_exhaustion(self):
        spec = {"type": TYPE, "n": 4, "algorithm": "hill_climbing", "iterations_limit": 1}
        solved = process_request("# @solve " + json.dumps({**spec, "initial": [1, 3, 0, 2]}), "instant")
        self.assertTrue(solved.verified_ok)
        self.assertEqual(solved.tier_used, "offline_" + TYPE)
        self.assertIn("'status': 'found'", solved.code)

        unfinished = process_request("# @solve " + json.dumps(spec), "instant")
        self.assertFalse(unfinished.verified_ok)
        self.assertEqual(unfinished.validation_status, "reference")
        self.assertIn("'status': 'not_found_within_budget'", unfinished.code)
        self.assertIn("chưa tìm thấy nghiệm", unfinished.stdout_preview)

    @unittest.skipUnless(HAS_SIMPLEAI, "requires SimpleAI")
    def test_neighbor_budget_applies_before_full_expansion(self):
        result = _search_queens(12, "hill_climbing", 1, 2_000, {}, 2)
        self.assertEqual(result["evaluations"], 2)
        self.assertEqual(result["status"], "not_found_within_budget")

    def test_bad_inputs_fail_before_calling_simpleai(self):
        for fields in (
            {"n": 26}, {"n": 6, "iterations_limit": 0}, {"n": 4, "algorithm": "beam", "initial": [0] * 4},
            {"n": 4, "algorithm": "hill_climbing", "initial": [0, 0, 0, 4]},
            {"n": 4, "algorithm": "genetic", "mutation_chance": float("nan")},
        ):
            with self.subTest(fields=fields), patch("core_engine.offline_simpleai_local._isolated_search") as launch:
                with self.assertRaises(OfflineProblemError):
                    _simpleai_local_nqueens({"type": TYPE, **fields})
                launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
