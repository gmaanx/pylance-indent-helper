"""Validate SimpleAI adapters against independent small CSP witnesses."""

import ast
import contextlib
import io
import itertools
import json
import unittest
from unittest.mock import patch

from core_engine.engine_pipeline import process_request
from core_engine.offline_simpleai_csp import _run_simpleai_csp


def solve(spec):
    return process_request("# @solve " + json.dumps(spec, ensure_ascii=False), "instant")


class SimpleAICSPTests(unittest.TestCase):
    def run_generated(self, spec):
        result = solve(spec)
        self.assertEqual(result.validation_status, "verified", result.error_detail)
        self.assertEqual(result.tier_used, "offline_" + spec["type"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(result.code, "<simpleai-csp>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_backtrack_accepts_both_variable_heuristics_and_lcv(self):
        from simpleai.search import (
            HIGHEST_DEGREE_VARIABLE,
            LEAST_CONSTRAINING_VALUE,
            MOST_CONSTRAINED_VARIABLE,
            backtrack,
        )

        for order, expected_order in (("mrv", MOST_CONSTRAINED_VARIABLE), ("degree", HIGHEST_DEGREE_VARIABLE)):
            with self.subTest(order=order), patch("simpleai.search.backtrack", wraps=backtrack) as actual:
                result = _run_simpleai_csp(
                    {"A": (1, 2), "B": (1, 2)}, [("ne", ("A", "B"), None)],
                    order, "lcv", True, 10_000, 3.0,
                )
                self.assertNotEqual(result["A"], result["B"])
                self.assertEqual(actual.call_args.kwargs, {
                    "variable_heuristic": expected_order, "value_heuristic": LEAST_CONSTRAINING_VALUE, "inference": True,
                })

    def test_numeric_constraints_respect_domains_and_nonbinary_sum(self):
        domains = {"A": [0, 1, 2, 3], "B": [0, 1, 2, 3], "C": [0, 1, 2, 3]}
        constraints = [
            {"op": "all_different", "vars": ["A", "B", "C"]},
            {"op": "sum_eq", "vars": ["A", "B", "C"], "value": 5},
            {"op": "lt", "vars": ["A", "B"]},
            {"op": "le", "vars": ["B", "C"]},
            {"op": "abs_diff_ne", "vars": ["A", "C"], "value": 1},
        ]
        answers = {
            (a, b, c) for a, b, c in itertools.product(*domains.values())
            if len({a, b, c}) == 3 and a + b + c == 5 and a < b <= c and abs(a - c) != 1
        }
        for inference in (True, False):
            with self.subTest(inference=inference):
                result = self.run_generated({
                    "type": "simpleai_csp", "domains": domains, "constraints": constraints,
                    "inference": inference, "value_heuristic": "input",
                })
                self.assertIn(tuple(result[name] for name in domains), answers)

    def test_table_constraints_compile_and_keep_tuple_argument_order(self):
        problem = {
            "type": "simpleai_csp",
            "domains": {"A": ["north", "south"], "B": [1, 2], "C": [1, 2]},
            "constraints": [
                {"op": "table", "vars": ["B", "A"], "allowed": [[1, "north"], [2, "south"]]},
                {"op": "table", "vars": ["A"], "allowed": [["south"]]},
                {"op": "eq", "vars": ["B", "C"]},
            ],
        }
        self.assertEqual(self.run_generated(problem), {"A": "south", "B": 2, "C": 2})
        problem["constraints"].append({"op": "ne", "vars": ["B", "C"]})
        self.assertIsNone(self.run_generated(problem))

    def test_nqueens_witness_and_unsatisfiable_small_boards(self):
        for size in (1, 2, 3, 5, 8):
            with self.subTest(size=size):
                columns = self.run_generated({"type": "simpleai_nqueens", "n": size, "inference": True})
                if size in (2, 3):
                    self.assertIsNone(columns)
                    continue
                self.assertEqual(set(columns), set(range(size)))
                self.assertEqual(set(columns.values()), set(range(size)))
                for left, right in itertools.combinations(columns, 2):
                    self.assertNotEqual(right - left, abs(columns[right] - columns[left]))

    def test_invalid_dependency_and_resource_states_are_reported_separately(self):
        base = {
            "type": "simpleai_csp", "domains": {"A": [1, 2], "B": [1, 2]},
            "constraints": [{"op": "ne", "vars": ["A", "B"]}],
        }
        self.assertEqual(solve({**base, "variable_heuristic": "random"}).validation_status, "unsupported")
        self.assertEqual(solve({**base, "inference": 1}).validation_status, "invalid")
        invalid_table = {"op": "table", "vars": ["A", "B"], "allowed": [[1, 3]]}
        self.assertEqual(solve({**base, "constraints": [invalid_table]}).validation_status, "invalid")
        with patch("core_engine.offline_simpleai_csp.MAX_CONSTRAINT_CHECKS", 0):
            response = solve(base)
        self.assertEqual(response.validation_status, "limit")
        self.assertFalse(response.code)
        with patch("core_engine.offline_simpleai_csp._run_simpleai_csp", side_effect=ModuleNotFoundError("simpleai")):
            response = solve(base)
        self.assertEqual(response.validation_status, "unsupported")
        self.assertFalse(response.code)

    def test_adapter_rejects_invalid_backend_assignment(self):
        base = {"type": "simpleai_nqueens", "n": 4}
        for assignment in ({0: 3}, {0: 0, 1: 0, 2: 0, 3: 0}):
            with self.subTest(assignment=assignment):
                with patch("simpleai.search.backtrack", return_value=assignment):
                    response = solve(base)
                self.assertEqual(response.validation_status, "invalid")
                self.assertFalse(response.code)


if __name__ == "__main__":
    unittest.main()
