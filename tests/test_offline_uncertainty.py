"""Regression tests for exact offline probability and finite fuzzy sets."""

import ast
from contextlib import redirect_stdout
from fractions import Fraction
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core_engine.engine_pipeline import process_request
from core_engine.offline_solver import OfflineProblemError, solve_spec


def run_spec(problem):
    result = solve_spec(problem)
    output = io.StringIO()
    # This executes only the trusted, local solver template with literal data.
    with redirect_stdout(output):
        exec(compile(result.code, "<standalone>", "exec"), {"__name__": "__main__"})
    answer_text = output.getvalue().strip()
    if problem.get("operation") in ("cardinality", "height"):
        return answer_text, result
    return ast.literal_eval(answer_text), result


class UncertaintyTests(unittest.TestCase):
    def test_joint_table_uses_declared_order_repeated_rows_and_exact_arithmetic(self):
        spec = {
            "type": "conditional_probability",
            "variables": {"wind": [False, True], "play": ["yes", "no"]},
            "rows": [[[True, "yes"], 2], [[True, "yes"], 1], [[True, "no"], 5],
                     [[False, "yes"], 4], [[False, "no"], 2]],
            "query": {"play": "yes"}, "evidence": {"wind": True},
        }
        value, result = run_spec(spec)
        self.assertEqual(value, {
            "query_probability": "1/2", "evidence_probability": "4/7", "joint_probability": "3/14",
            "conditional_probability": "3/8", "independent": False,
        })
        self.assertEqual(result.metric, ("conditional_probability", "3/8"))

    def test_zero_evidence_and_boolean_labels_distinct_from_integers(self):
        spec = {
            "type": "conditional_probability",
            "variables": {"value": [1, True, False]},
            "rows": [[[1], 2], [[True], 3]],
            "query": {"value": True}, "evidence": {"value": False},
        }
        value, _ = run_spec(spec)
        self.assertEqual(value["query_probability"], "3/5")
        self.assertEqual(value["evidence_probability"], "0")
        self.assertIsNone(value["conditional_probability"])

    def test_conditional_probability_matches_bayes_reversal_for_weighted_table(self):
        variables = {"type": ["known", "other"], "test": ["yes", "no"]}
        rows = [[["known", "yes"], "3/10"], [["known", "no"], "1/10"],
                [["other", "yes"], "1/20"], [["other", "no"], "11/20"]]
        table = {"type": "conditional_probability", "variables": variables, "rows": rows,
                 "query": {"type": "known"}, "evidence": {"test": "yes"}}
        bayes = {"type": "bayes", "priors": {"known": "2/5", "other": "3/5"},
                 "likelihoods": {"known": "3/4", "other": "1/12"}, "query": "known"}
        table_answer, _ = run_spec(table)
        bayes_answer, _ = run_spec(bayes)
        self.assertEqual(table_answer["conditional_probability"], "6/7")
        self.assertEqual(bayes_answer["query_probability"], table_answer["conditional_probability"])
        self.assertEqual(sum(Fraction(value) for value in bayes_answer["posterior"].values()), 1)

    def test_multiple_observations_require_explicit_independence_and_preserve_ties(self):
        bayes = {"type": "bayes", "priors": {"A": 0.25, "B": "3/4"},
                 "likelihoods": {"A": ["3/4", "1/2"], "B": ["1/2", "1/4"]}, "query": "A"}
        with self.assertRaises(OfflineProblemError) as missing:
            solve_spec(bayes)
        self.assertEqual(missing.exception.status, "needs_input")
        answer, result = run_spec({**bayes, "conditional_independence": True})
        self.assertEqual(answer["evidence_probability"], "3/16")
        self.assertEqual(answer["most_likely"], ["A", "B"])
        self.assertEqual(result.metric, ("posterior_probability", "1/2"))
        absent, _ = run_spec({**bayes, "likelihoods": {"A": 0, "B": 0}})
        self.assertIsNone(absent["posterior"])

    def test_fuzzy_operations_are_exact_at_alpha_boundary_and_preserve_universe(self):
        base = {"type": "fuzzy_set", "universe": ["x", "y", "z"], "left": {"x": "0.3", "y": "1/2"}}
        cases = (
            ({"operation": "alpha_cut", "alpha": "3/10"}, ["x", "y"]),
            ({"operation": "alpha_cut", "alpha": 0}, ["x", "y", "z"]),
            ({"operation": "complement"}, {"x": "7/10", "y": "1/2", "z": "1"}),
            ({"operation": "intersection", "right": {"x": 1}}, {"x": "3/10", "y": "0", "z": "0"}),
            ({"operation": "union", "right": {"x": 1}}, {"x": "1", "y": "1/2", "z": "0"}),
            ({"operation": "subset", "right": {"x": "0.3", "y": "3/4"}}, True),
            ({"operation": "equal", "right": {"x": "3/10", "y": "0.5", "z": 0}}, True),
            ({"operation": "cardinality"}, "4/5"),
            ({"operation": "height"}, "1/2"),
            ({"operation": "normal"}, False),
            ({"operation": "empty"}, False),
            ({"operation": "support"}, ["x", "y"]),
            ({"operation": "scale", "scalar": "1/3"}, {"x": "1/10", "y": "1/6", "z": "0"}),
            ({"operation": "power", "exponent": 2}, {"x": "9/100", "y": "1/4", "z": "0"}),
        )
        for details, expected in cases:
            with self.subTest(operation=details):
                answer, _ = run_spec({**base, **details})
                self.assertEqual(answer, expected)

    def test_invalid_tables_priors_and_fuzzy_parameters_are_rejected(self):
        invalid_specs = (
            {"type": "conditional_probability", "variables": {"x": [1]}, "rows": [[[True], 1]], "query": {}},
            {"type": "conditional_probability", "variables": {"x": [1]}, "rows": [[[1], 0]], "query": {}},
            {"type": "bayes", "priors": {"A": 0.5}, "likelihoods": {"A": 1}},
            {"type": "bayes", "priors": {"A": 1}, "likelihoods": {"A": "1/0"}},
            {"type": "fuzzy_set", "operation": "support", "left": {"x": 1}, "alpha": 0.5},
            {"type": "fuzzy_set", "operation": "support", "left": {"x": 1}, "universe": []},
        )
        for spec in invalid_specs:
            with self.subTest(spec=spec), self.assertRaises(OfflineProblemError):
                solve_spec(spec)

    def test_engine_routes_structured_uncertainty_to_local_model(self):
        spec = {"type": "fuzzy_set", "operation": "cardinality", "left": {"x": "2/3", "y": "1/3"}}
        reply = process_request("# @solve " + json.dumps(spec), action_mode="instant")
        self.assertTrue(reply.verified_ok)
        self.assertEqual(reply.tier_used, "offline_fuzzy_set")
        self.assertIn("Giá trị 1", reply.stdout_preview)


if __name__ == "__main__":
    unittest.main()
