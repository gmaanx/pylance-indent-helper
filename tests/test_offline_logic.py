"""Compare the standalone logic results with independent small reference problems."""

import ast
import contextlib
import io
import itertools
import json
import random
import unittest
from unittest.mock import patch

from core_engine.engine_pipeline import process_request


def solve(problem):
    return process_request("# @solve " + json.dumps(problem, ensure_ascii=False), action_mode="instant")


class OfflineLogicTests(unittest.TestCase):
    def check_result(self, problem):
        response = solve(problem)
        self.assertEqual(response.validation_status, "verified", response.error_detail)
        self.assertEqual(response.tier_used, "offline_" + problem["type"])
        output = io.StringIO()
        # Only execute deterministic source emitted from trusted solver functions.
        with contextlib.redirect_stdout(output):
            exec(compile(response.code, "<offline-logic>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_sat_matches_exhaustive_boolean_assignments(self):
        rng = random.Random(1924)
        test_cases = [
            (0, []),
            (0, [[]]),
            (1, [[1], [-1]]),
            (3, [[1, -1], [-2, -2], [2, 3]]),
        ]
        for count in range(1, 6):
            literals = [sign * index for index in range(1, count + 1) for sign in (-1, 1)]
            for _ in range(7):
                clauses = [rng.choices(literals, k=rng.randrange(1, 5)) for _ in range(rng.randrange(4, 20))]
                test_cases.append((count, clauses))

        for count, clauses in test_cases:
            with self.subTest(count=count, clauses=clauses):
                def satisfies(values):
                    return all(any(values[abs(literal) - 1] == (literal > 0) for literal in clause) for clause in clauses)

                expected = any(satisfies(values) for values in itertools.product((False, True), repeat=count))
                result = self.check_result({"type": "sat", "variables": count, "clauses": clauses})
                self.assertEqual(result is not None, expected)
                if result is not None:
                    self.assertEqual(set(result), set(range(1, count + 1)))
                    self.assertTrue(satisfies([result[index] for index in range(1, count + 1)]))

    def test_horn_closure_respects_conjunctions_and_cycles(self):
        rules = [
            {"if": ["Kết_quả"], "then": "Hệ_quả"},
            {"if": ["A", "B", "A"], "then": "Kết_quả"},
            {"if": ["Hệ_quả"], "then": "A"},
            {"if": ["C"], "then": "D"},
            {"if": ["D"], "then": "C"},
            {"if": [], "then": "B"},
            {"if": ["B", "C"], "then": "E"},
        ]
        for query in ("Kết_quả", "C", "E"):
            with self.subTest(query=query):
                result = self.check_result({"type": "horn", "facts": ["A"], "rules": rules, "query": query})
                self.assertEqual(set(result["closure"]), {"A", "B", "Kết_quả", "Hệ_quả"})
                self.assertEqual(result["entailed"], query == "Kết_quả")

    def test_sudoku_proves_uniqueness_and_preserves_9_by_9_givens(self):
        givens = [
            [5, 3, 0, 0, 7, 0, 0, 0, 0],
            [6, 0, 0, 1, 9, 5, 0, 0, 0],
            [0, 9, 8, 0, 0, 0, 0, 6, 0],
            [8, 0, 0, 0, 6, 0, 0, 0, 3],
            [4, 0, 0, 8, 0, 3, 0, 0, 1],
            [7, 0, 0, 0, 2, 0, 0, 0, 6],
            [0, 6, 0, 0, 0, 0, 2, 8, 0],
            [0, 0, 0, 4, 1, 9, 0, 0, 5],
            [0, 0, 0, 0, 8, 0, 0, 7, 9],
        ]
        result = self.check_result({"type": "sudoku", "grid": givens})
        self.assertEqual(result["status"], "unique")
        solution = result["solution"]
        self.assertEqual(solution[0], [5, 3, 4, 6, 7, 8, 9, 1, 2])
        self.assertEqual(solution[-1], [3, 4, 5, 2, 8, 6, 1, 7, 9])
        for row in range(9):
            for column in range(9):
                if givens[row][column]:
                    self.assertEqual(solution[row][column], givens[row][column])
        for unit in itertools.chain(
            solution, zip(*solution),
            ([solution[row + dr][column + dc] for dr in range(3) for dc in range(3)]
             for row in range(0, 9, 3) for column in range(0, 9, 3)),
        ):
            self.assertEqual(set(unit), set(range(1, 10)))

    def test_sudoku_distinguishes_invalid_unsatisfiable_and_multiple(self):
        self.assertEqual(
            self.check_result({"type": "sudoku", "grid": [[0, 0, 0, 0]] * 4})["status"], "multiple",
        )
        blocked = [
            [1, 2, 3, 0],
            [0, 0, 0, 4],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ]
        self.assertEqual(self.check_result({"type": "sudoku", "grid": blocked}), {"status": "none", "solution": None})
        blocked[1][3] = 3
        response = solve({"type": "sudoku", "grid": blocked})
        self.assertEqual(response.validation_status, "invalid")
        self.assertFalse(response.code)

    def test_cryptarithm_validates_carries_bases_and_leading_zero(self):
        decimal = self.check_result({"type": "cryptarithm", "addends": ["SEND", "MORE"], "result": "MONEY"})
        self.assertEqual(decimal, {"S": 9, "E": 5, "N": 6, "D": 7, "M": 1, "O": 0, "R": 8, "Y": 2})
        self.assertIsNone(self.check_result({"type": "cryptarithm", "addends": ["A", "A"], "result": "AA"}))
        self.assertEqual(
            self.check_result({"type": "cryptarithm", "base": 2, "addends": ["A", "A"], "result": "AB"}),
            {"A": 1, "B": 0},
        )
        for base in range(3, 7):
            expected = {
                (a, b, c) for a, b, c in itertools.permutations(range(base), 3)
                if a != 0 and a + b + c == a * base + c
            }
            result = self.check_result(
                {"type": "cryptarithm", "base": base, "addends": ["A", "B", "C"], "result": "AC"},
            )
            if expected:
                self.assertIn(tuple(result[letter] for letter in "ABC"), expected)
            else:
                self.assertIsNone(result)

    def test_bad_input_or_limit_cannot_be_reported_as_solved(self):
        invalid = [
            {"type": "sat", "variables": 2, "clauses": [[True]]},
            {"type": "sat", "variables": 2, "clauses": [[0]]},
            {"type": "sat", "variables": 2, "clauses": [[3]]},
            {"type": "horn", "facts": ["~A"], "rules": [], "query": "B"},
            {"type": "sudoku", "grid": [[0, 0, 0, 0]] * 3},
            {"type": "cryptarithm", "addends": ["send", "MORE"], "result": "MONEY"},
        ]
        for problem in invalid:
            response = solve(problem)
            self.assertEqual(response.validation_status, "invalid", response.error_detail)
            self.assertFalse(response.code)

        limit_problems = [
            ("MAX_SAT_WORK", {"type": "sat", "variables": 2, "clauses": [[1, 2]]}),
            ("MAX_SUDOKU_STEPS", {"type": "sudoku", "grid": [[0] * 4 for _ in range(4)]}),
            ("MAX_CRYPTARITHM_STEPS", {"type": "cryptarithm", "addends": ["A", "A"], "result": "B"}),
        ]
        for constant, problem in limit_problems:
            with patch("core_engine.offline_logic." + constant, 0):
                response = solve(problem)
            self.assertEqual(response.validation_status, "limit", response.error_detail)
            self.assertFalse(response.verified_ok)
            self.assertFalse(response.code)


if __name__ == "__main__":
    unittest.main()
