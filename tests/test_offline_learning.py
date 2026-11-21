"""Exercise standalone learning programs through the normal engine entry point."""

import ast
import contextlib
import io
import json
import unittest
from fractions import Fraction
from functools import lru_cache
from unittest.mock import patch

from core_engine.engine_pipeline import process_request


def solve(problem):
    return process_request("# @solve " + json.dumps(problem, ensure_ascii=False), action_mode="instant")


class OfflineLearningTests(unittest.TestCase):
    def check_result(self, problem):
        response = solve(problem)
        self.assertEqual(response.validation_status, "verified", response.error_detail)
        self.assertEqual(response.tier_used, "offline_" + problem["type"])
        output = io.StringIO()
        # The engine only emits source from trusted deterministic solver functions here.
        with contextlib.redirect_stdout(output):
            exec(compile(response.code, "<offline-learning>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_knn_minmax_uses_training_ranges_and_ignores_constant_axes(self):
        problem = {
            "type": "knn", "k": 1, "query": [90, 0, 100],
            "train": [
                {"x": [0, 0, 2], "label": "A"},
                {"x": [100, 1, 2], "label": "B"},
                {"x": [1000, 0, 2], "label": "C"},
            ],
        }
        raw = self.check_result(problem)
        self.assertEqual(raw["prediction"], "B")
        self.assertEqual(raw["neighbors"][0]["distance_squared"], 9705)

        normalized = self.check_result({**problem, "normalize": "minmax"})
        self.assertEqual(normalized["prediction"], "A")
        self.assertEqual(normalized["neighbors"][0]["distance_squared"], 0.0081)

    def test_knn_uses_exact_decimal_distances_and_deterministic_ties(self):
        problem = {
            "type": "knn", "k": 1, "query": [0.2],
            "train": [{"x": [0.1], "label": "Z"}, {"x": [0.3], "label": "A"}],
        }
        nearest = self.check_result(problem)
        self.assertEqual(nearest["prediction"], "Z")
        self.assertEqual(nearest["neighbors"], [{"index": 0, "label": "Z", "distance_squared": 0.01}])
        voting = self.check_result({**problem, "k": 2})
        self.assertEqual(voting["prediction"], "A")
        self.assertEqual(voting["votes"], {"Z": 1, "A": 1})

        problem["train"][0]["x"] = [0.19]
        self.assertEqual(self.check_result({**problem, "k": 2})["prediction"], "Z")

    def test_id3_splits_on_more_informative_feature_and_marks_fallback(self):
        problem = {
            "type": "id3", "query": ["red", "rainy"],
            "train": [
                {"x": ["red", "sunny"], "label": "no"},
                {"x": ["red", "sunny"], "label": "no"},
                {"x": ["red", "rainy"], "label": "yes"},
                {"x": ["blue", "sunny"], "label": "no"},
                {"x": ["blue", "sunny"], "label": "no"},
                {"x": ["blue", "rainy"], "label": "yes"},
            ],
        }
        result = self.check_result(problem)
        self.assertEqual(result["tree"]["feature"], 1)
        self.assertEqual(result["prediction"], "yes")
        self.assertFalse(result["used_fallback"])
        unknown = self.check_result({**problem, "query": ["red", "snowy"]})
        self.assertEqual(unknown["prediction"], "no")
        self.assertEqual(unknown["path"], [(1, "snowy")])
        self.assertTrue(unknown["used_fallback"])

    def test_id3_can_learn_xor_with_equal_gain_at_root(self):
        train = [
            {"x": [str(a), str(b)], "label": str(a ^ b)}
            for a in range(2) for b in range(2)
        ]
        for sample in train:
            result = self.check_result({"type": "id3", "train": train, "query": sample["x"]})
            self.assertEqual(result["tree"]["feature"], 0)
            self.assertEqual(result["prediction"], sample["label"])

    def test_mdp_policy_depends_on_remaining_steps(self):
        states = {
            "S": {
                "stay": [{"to": "S", "p": 1, "reward": 1}],
                "close": [{"to": "T", "p": 1, "reward": 5}],
            },
            "T": {},
        }
        result = self.check_result({"type": "mdp", "states": states, "discount": 0.9, "horizon": 3})
        self.assertEqual([row["S"] for row in result["values_by_horizon"]], [0, 5, 5.5, 5.95])
        self.assertEqual([row["S"] for row in result["policies_by_horizon"]], [None, "close", "stay", "stay"])
        self.assertEqual(result["policy"]["S"], "stay")
        self.assertEqual(result["values"]["T"], 0)
        self.assertIsNone(result["policy"]["T"])

    def test_mdp_stochastic_expected_values_match_small_recursive_oracle(self):
        states = {
            "S": {
                "z_risk": [{"to": "S", "p": 0.25, "reward": 4}, {"to": "T", "p": 0.75, "reward": -4}],
                "a_risk": [{"to": "S", "p": 0.25, "reward": 4}, {"to": "T", "p": 0.75, "reward": -4}],
                "cycle": [{"to": "N", "p": 1, "reward": -3}],
            },
            "N": {"back": [{"to": "S", "p": 1, "reward": 9}]},
            "T": {},
        }

        @lru_cache
        def expected(state, remaining):
            if not remaining or not states[state]:
                return Fraction(0), None
            ranked = []
            for action, outcomes in states[state].items():
                score = sum(Fraction(str(entry["p"])) * (
                    entry["reward"] + Fraction(3, 4) * expected(entry["to"], remaining - 1)[0]
                ) for entry in outcomes)
                ranked.append((-score, action))
            negative, action = min(ranked)
            return -negative, action

        result = self.check_result({"type": "mdp", "states": states, "discount": 0.75, "horizon": 5})
        for remaining in range(6):
            for state in states:
                value, action = expected(state, remaining)
                self.assertEqual(result["values_by_horizon"][remaining][state], float(value))
                self.assertEqual(result["policies_by_horizon"][remaining][state], action)
        self.assertEqual(result["policies_by_horizon"][1]["S"], "a_risk")
        self.assertEqual(result["values_by_horizon"][1]["S"], -2)

    def test_validation_rejects_unknown_or_unrepresentable_specifications(self):
        sample = {"type": "knn", "train": [{"x": [0], "label": "A"}], "query": [0], "k": 1}
        mdp = {
            "type": "mdp", "discount": 1, "horizon": 2,
            "states": {"A": {"stay": [{"to": "A", "p": 1, "reward": 0}]}},
        }
        cases = [
            ("invalid", {**sample, "query": [False]}),
            ("invalid", {**sample, "query": [1e-7]}),
            ("invalid", {**sample, "query": [0, 0]}),
            ("invalid", {**sample, "k": 2}),
            ("unsupported", {**sample, "normalize": "zscore"}),
            ("invalid", {"type": "id3", "train": [{"x": [0], "label": "A"}], "query": [0]}),
            ("invalid", {**mdp, "states": {"A": {"stay": [{"to": "B", "p": 1, "reward": 0}]}}}),
            ("invalid", {**mdp, "states": {"A": {"stay": [{"to": "A", "p": 0.999, "reward": 0}]}}}),
        ]
        for expected, problem in cases:
            with self.subTest(problem=problem):
                response = solve(problem)
                self.assertEqual(response.validation_status, expected, response.error_detail)
                self.assertFalse(response.code)
        with patch("core_engine.offline_learning.MAX_MDP_BACKUPS", 1):
            response = solve(mdp)
        self.assertEqual(response.validation_status, "limit")
        self.assertFalse(response.code)


if __name__ == "__main__":
    unittest.main()
