"""Check generated programs on routes and game trees with tricky variants."""

import ast
import contextlib
import io
import json
import random
import unittest

from core_engine.engine_pipeline import process_request


def offline_response(problem):
    text = "# @solve " + json.dumps(problem) if isinstance(problem, dict) else problem
    return process_request(text, action_mode="instant")


class OfflineSearchTests(unittest.TestCase):
    def solve(self, problem):
        response = offline_response(problem)
        self.assertEqual(response.validation_status, "verified", response.error_detail)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(response.code, "<trusted-offline-solver>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_grid_revisiting_a_cell_with_key_is_a_new_state(self):
        result = self.solve({
            "type": "grid", "rows": [".A.", ".##", "a##"],
            "start": [0, 0], "goal": [0, 2], "visit": [[0, 1]],
        })
        self.assertEqual(result, {
            "cost": 6, "path": [(0, 0), (1, 0), (2, 0), (1, 0), (0, 0), (0, 1), (0, 2)],
        })

    def test_grid_optimal_cost_is_not_fewest_steps(self):
        spec = {"type": "grid", "rows": [".9.", "..."], "start": [0, 0], "goal": [0, 2]}
        self.assertEqual(self.solve(spec)["cost"], 2)
        spec["costs"] = {"9": 9}
        self.assertEqual(self.solve(spec)["cost"], 4)
        self.assertEqual(offline_response({**spec, "algorithm": "bfs"}).validation_status, "unsupported")

    def test_diagonal_and_checkpoint_order_change_feasibility(self):
        diagonal = {"type": "grid", "rows": [".#", "#."], "start": [0, 0], "goal": [1, 1], "moves": "diagonal"}
        self.assertIsNone(self.solve(diagonal))
        self.assertEqual(self.solve({**diagonal, "no_corner_cut": False})["cost"], 1)
        route = {"type": "grid", "rows": ["...."], "start": [0, 0], "goal": [0, 3], "visit": [[0, 2], [0, 1]]}
        self.assertEqual(self.solve(route)["cost"], 3)
        self.assertIsNone(self.solve({**route, "visit_order": "ordered"}))

    def test_alpha_beta_matches_unpruned_oracle(self):
        rng = random.Random(489)

        def make_tree(depth):
            if depth == 0 or rng.random() < 0.1:
                return rng.randint(-8, 8)
            return [make_tree(depth - 1) for _ in range(rng.randint(2, 4))]

        def oracle(tree, maximize):
            if isinstance(tree, int):
                return tree, []
            children = [oracle(child, not maximize) for child in tree]
            choose = max if maximize else min
            index = choose(range(len(children)), key=lambda i: children[i][0])
            return children[index][0], [index, *children[index][1]]

        for _ in range(20):
            tree = make_tree(4)
            for root in ("min", "max"):
                expected = oracle(tree, root == "max")
                spec = {"type": "minimax", "tree": tree, "root": root}
                result = self.solve(spec)
                baseline = self.solve({**spec, "algorithm": "minimax"})
                self.assertEqual((result["value"], result["path"]), expected)
                self.assertEqual((baseline["value"], baseline["path"]), expected)
                self.assertLessEqual(result["visited"], baseline["visited"])

    def test_depth_cutoff_uses_explicit_scores(self):
        spec = {"type": "minimax", "tree": [{"children": [100], "heuristic": -7}, {"children": [-100], "heuristic": 4}]}
        self.assertEqual(self.solve({**spec, "depth_limit": 1})["value"], 4)
        self.assertEqual(offline_response({**spec, "tree": [[100], [10]], "depth_limit": 1}).validation_status, "needs_input")

    def test_known_text_formats_and_extra_constraints(self):
        puzzle = "# Giải bài toán 8-puzzle bằng A* với Manhattan. Trạng thái ban đầu: ((1,2,3),(4,0,6),(7,5,8)). Trạng thái đích: 123456780."
        self.assertEqual(len(self.solve(puzzle)) - 1, 2)
        self.assertFalse(offline_response(puzzle + " Không được đi sang phải.").verified_ok)
        minimax = "# Đánh giá cây alpha-beta, gốc MAX: [[3, 5], [2, 9]]."
        self.assertEqual(self.solve(minimax)["value"], 3)
        dimacs = "# c Test\n# p cnf 2 3\n# 1 0 -1 2 0\n# 2 0"
        assignment = self.solve(dimacs)
        self.assertEqual(dict(assignment), {1: True, 2: True})
        self.assertEqual(offline_response(dimacs + "\n# 1 0").validation_status, "invalid")


if __name__ == "__main__":
    unittest.main()
