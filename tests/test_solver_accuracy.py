"""Check emitted programs against independently calculated results."""

import ast
import contextlib
import io
import itertools
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from core_engine import engine_pipeline
from core_engine.dual_parser import parse_user_input
from core_engine.engine_pipeline import process_request


def structured(problem):
    return "# @solve " + json.dumps(problem, ensure_ascii=False)


class SolverTests(unittest.TestCase):
    def run_exact(self, request):
        if not isinstance(request, str):
            request = structured(request)
        response = process_request(request, action_mode="instant")
        self.assertEqual(response.validation_status, "verified", response.error_detail)
        output = io.StringIO()
        # These tests run only deterministic source emitted from trusted solver functions.
        with contextlib.redirect_stdout(output):
            exec(compile(response.code, "<offline-solver>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_vietnamese_jugs_use_the_requested_instance(self):
        path = self.run_exact(
            "# Bài toán đong nước bằng BFS. Dung tích các bình: (2, 4, 7, 9). "
            "Trạng thái ban đầu (0, 0, 0, 9). Mục tiêu 5 lít."
        )
        self.assertEqual(path, [(0, 0, 0, 9), (0, 4, 0, 5)])

    def test_jugs_partial_goal_needs_shortest_conserving_path(self):
        capacities = (3, 5, 8)
        start = (0, 0, 8)
        goal = (None, 4, 4)
        path = self.run_exact({
            "type": "water_jugs", "capacities": capacities, "start": start,
            "goal": goal, "algorithm": "bfs",
        })
        # Enumerate the state graph by differences independently of the solver's pour generator.
        def legal_pour(a, b):
            differences = [right - left for left, right in zip(a, b)]
            drained = [index for index, delta in enumerate(differences) if delta < 0]
            filled = [index for index, delta in enumerate(differences) if delta > 0]
            return (
                len(drained) == len(filled) == 1
                and sum(a) == sum(b)
                and (b[drained[0]] == 0 or b[filled[0]] == capacities[filled[0]])
            )

        states = {
            state for state in itertools.product(*(range(capacity + 1) for capacity in capacities))
            if sum(state) == sum(start)
        }
        layer, seen = {start}, set()
        for depth in range(len(states)):
            if any(state[1:] == goal[1:] for state in layer):
                break
            seen |= layer
            layer = {b for b in states - seen if any(legal_pour(a, b) for a in layer)}
        self.assertEqual(path[0], start)
        self.assertEqual(path[-1][1:], goal[1:])
        self.assertTrue(all(legal_pour(a, b) for a, b in zip(path, path[1:])))
        self.assertEqual(len(path) - 1, depth)

    def test_jugs_limited_pour_changes_shortest_path_and_blocked_jug(self):
        text = (
            "# Đong nước bằng BFS với 3 bình có dung tích (3, 5, 8). "
            "Trạng thái ban đầu (0, 0, 8). Mục tiêu 4 lít. Mỗi bước chỉ rót tối đa 1 lít."
        )
        path = self.run_exact(text)
        self.assertEqual(len(path) - 1, 4)
        self.assertIn(4, path[-1])
        self.assertTrue(all(sum(abs(a - b) for a, b in zip(previous, state)) == 2 for previous, state in zip(path, path[1:])))
        self.assertIsNone(self.run_exact({
            "type": "water_jugs", "capacities": [3, 5, 8], "start": [0, 0, 8],
            "goal": 4, "max_pour": 1, "blocked_jugs": [2],
        }))

    def test_coin_change_matches_dynamic_programming_and_unsat(self):
        coins = (4, 7, 9)
        for amount in range(32):
            with self.subTest(amount=amount):
                counts = [0] + [float("inf")] * amount
                for value in range(1, amount + 1):
                    counts[value] = min(
                        (counts[value - coin] + 1 for coin in coins if value >= coin),
                        default=float("inf"),
                    )
                result = self.run_exact({"type": "coin_change", "amount": amount, "denominations": coins})
                if counts[amount] == float("inf"):
                    self.assertIsNone(result)
                else:
                    self.assertEqual(sum(result), amount)
                    self.assertTrue(set(result) <= set(coins))
                    self.assertEqual(len(result), counts[amount])

    def test_natural_coin_change_preserves_denominations(self):
        result = self.run_exact(
            "# Bài toán đổi tiền bằng tìm kiếm. Đổi 17 đồng, chỉ được dùng các mệnh giá 4, 7, 9."
        )
        self.assertEqual(sum(result), 17)
        self.assertEqual(len(result), 3)
        self.assertTrue(set(result) <= {4, 7, 9})

    def test_bounded_coin_change_matches_exhaustive_quantities(self):
        denominations = [7, 4, 3]
        inventory = [1, 1, 2]
        counts = list(itertools.product(*(range(count + 1) for count in inventory)))
        for amount in range(20):
            with self.subTest(amount=amount):
                best = min(
                    (sum(row) for row in counts if sum(coin * count for coin, count in zip(denominations, row)) == amount),
                    default=None,
                )
                result = self.run_exact({
                    "type": "coin_change", "amount": amount,
                    "denominations": denominations, "inventory": inventory,
                })
                if best is None:
                    self.assertIsNone(result)
                else:
                    self.assertEqual(sum(result), amount)
                    self.assertEqual(len(result), best)
                    self.assertTrue(set(result) <= set(denominations))
                    self.assertTrue(all(result.count(coin) <= count for coin, count in zip(denominations, inventory)))

    def test_graph_bfs_optimizes_hops_ucs_optimizes_total_cost(self):
        edges = [["A", "D", 50], ["A", "B", 1], ["A", "B", 9], ["B", "C", 0], ["C", "D", 2]]
        base = {"type": "graph", "start": "A", "goal": "D"}
        self.assertEqual(self.run_exact({**base, "algorithm": "ucs", "edges": edges}), (3, ["A", "B", "C", "D"]))
        self.assertEqual(
            self.run_exact({**base, "algorithm": "bfs", "edges": [edge[:2] for edge in edges]}),
            (1, ["A", "D"]),
        )
        self.assertIsNone(self.run_exact({**base, "start": "D", "goal": "A", "algorithm": "ucs", "edges": edges}))
        self.assertEqual(
            self.run_exact({**base, "start": "D", "goal": "A", "algorithm": "ucs", "directed": False, "edges": edges}),
            (3, ["D", "C", "B", "A"]),
        )

    def test_csp_checks_all_constraints(self):
        domains = {"A": [0, 1, 2], "B": [0, 1, 2], "C": [0, 1, 2]}
        constraints = [
            {"op": "all_different", "vars": ["A", "B", "C"]},
            {"op": "lt", "vars": ["A", "B"]},
            {"op": "sum_eq", "vars": ["B", "C"], "value": 3},
            {"op": "ne", "vars": ["A", "C"]},
            {"op": "le", "vars": ["B", "C"]},
        ]
        expected = {
            (a, b, c)
            for a, b, c in itertools.product(*domains.values())
            if len({a, b, c}) == 3 and a < b <= c and b + c == 3 and a != c
        }
        problem = {"type": "csp", "domains": domains, "constraints": constraints}
        result = self.run_exact(problem)
        self.assertIn(tuple(result[key] for key in domains), expected)
        constraints.append({"op": "eq", "vars": ["B", "C"]})
        self.assertIsNone(self.run_exact(problem))

    def test_bellman_ford_distinguishes_negative_edges_and_relevant_cycles(self):
        spec = {
            "type": "graph", "algorithm": "bellman_ford", "start": "A", "goal": "D",
            "edges": [["A", "D", 2], ["A", "B", 3], ["B", "D", -5], ["A", "C", 1], ["C", "C", -1]],
        }
        self.assertEqual(self.run_exact(spec), (-2, ["A", "B", "D"]))
        self.assertEqual(self.run_exact({**spec, "edges": [*spec["edges"], ["C", "D", 100]]}), {"status": "unbounded"})
        self.assertEqual(self.run_exact({**spec, "start": "D"}), (0, ["D"]))
        self.assertIsNone(self.run_exact({**spec, "goal": "Z"}))
        self.assertEqual(
            process_request(structured({**spec, "algorithm": "ucs"}), "instant").validation_status,
            "invalid",
        )

    def test_limit_is_reported_as_unknown(self):
        spec = {"type": "coin_change", "amount": 10, "denominations": [1]}
        with patch("core_engine.offline_solver.MAX_STATES", 4):
            response = process_request(structured(spec), "instant")
        self.assertEqual(response.validation_status, "limit")
        self.assertFalse(response.verified_ok)
        self.assertFalse(response.code)

    def test_rejects_extra_requirements_wrong_algorithm_or_missing_fields(self):
        invalid = [
            (
                "needs_input",
                "# Đong nước bằng BFS với 3 bình có dung tích (3, 5, 8). "
                "Trạng thái ban đầu (0, 0, 8). Mục tiêu 4 lít. Không dùng bình thứ hai.",
            ),
            ("invalid", '# @solve {"type":"coin_change","amount":17,"amount":19,"denominations":[4,7,9]}'),
            ("needs_input", structured({"type": "water_jugs", "capacities": [3, 5]})),
            ("invalid", structured({"type": "coin_change", "amount": 5, "denominations": [2, 3], "inventory": [1]})),
            ("unsupported", structured({"type": "coin_change", "amount": 5, "denominations": [2, 3], "algorithm": "greedy"})),
            ("invalid", "# @search bai:dong_nuoc binh:3,5,8 dau:0,0,8 dich:4 dich:6"),
            ("unsupported", "# @search bai:dong_nuoc binh:3,5,8 dau:0,0,8 dich:4\n# Use a different cost."),
            ("invalid", structured({"type": "coin_change", "amount": 5, "denominations": [2, 3]}) + "\nrequired_cost = 2"),
        ]
        for status, request in invalid:
            with self.subTest(request=request):
                response = process_request(request, "instant")
                self.assertEqual(response.validation_status, status, response.error_detail)
                self.assertFalse(response.verified_ok)
                self.assertFalse(response.code)

    def test_unrelated_template_and_cloud_output_are_never_verified(self):
        with patch.object(engine_pipeline, "call_tier1_cloud_llm") as cloud, patch.object(
            engine_pipeline, "call_tier2_local_llm",
        ) as local:
            response = process_request("# zqxvv zqnw", "full")
            self.assertEqual(response.validation_status, "unsupported")
            self.assertFalse(response.code)
            cloud.assert_not_called()
            local.assert_not_called()

            cloud.return_value = ("raise AssertionError('code must not execute')", "tier1_mock")
            response = process_request("# zqxvv zqnw", "full", allow_cloud=True)
            self.assertEqual(response.validation_status, "syntax_checked")
            self.assertFalse(response.verified_ok)
            local.assert_not_called()

            cloud.return_value = ("x = ", "tier1_mock")
            response = process_request("# zqxvv zqnw", "full", allow_cloud=True)
            self.assertEqual(response.validation_status, "invalid")
            self.assertFalse(response.code)

    def test_self_fix_does_not_remove_triple_quoted_data_or_claim_semantic_correctness(self):
        code = 'DATA = """line one\nline two"""\nprint(DATA)'
        parsed = parse_user_input(code, force_mode="self_fix")
        self.assertEqual(parsed.existing_code, code)
        self.assertEqual(parsed.prompt_text, "")
        response = process_request("print(undefined_name)", "self_fix")
        self.assertFalse(response.verified_ok)
        self.assertFalse(response.code)
        self.assertEqual(response.validation_status, "unsupported")


if __name__ == "__main__":
    unittest.main()
