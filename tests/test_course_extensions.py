import ast
import io
import itertools
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core_engine.engine_pipeline import process_request


def run_case(kind, **fields):
    return process_request("# @solve " + json.dumps({"type": kind, **fields}, ensure_ascii=False), "instant")


class CourseExtensionsTests(unittest.TestCase):
    def result(self, response):
        self.assertEqual(response.validation_status, "verified", response.error_detail)
        output = io.StringIO()
        with redirect_stdout(output):
            exec(compile(response.code, "<trusted-solver-fixture>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(output.getvalue())

    def test_two_quoted_exercises_from_editor_work_in_all_modes(self):
        sample = (Path(__file__).resolve().parents[1] / "thu_nghiem.py").read_text(encoding="utf-8-sig")
        prompts = [ast.get_source_segment(sample, node) for node in ast.parse(sample).body]
        modes = (
            ("instant", {}),
            ("full", {}),
            ("full", {"allow_cloud": True}),
            ("self_fix", {}),
            ("full", {"allow_local": True}),
        )
        with (
            patch("core_engine.engine_pipeline.call_tier1_cloud_llm") as cloud,
            patch("core_engine.engine_pipeline.call_tier2_local_llm") as local,
        ):
            for action, options in modes:
                with self.subTest(action=action, options=options):
                    puzzle = self.result(process_request(prompts[0], action, **options))
                    self.assertEqual(puzzle["moves"], 2)
                    self.assertEqual(puzzle["h1"]["moves"], puzzle["h2"]["moves"])
                    shifts = self.result(process_request(prompts[1], action, **options))
                    self.assertEqual(set(shifts), {"An", "Binh", "Chi", "Dung"})
                    self.assertIn(shifts["An"], {"Sang", "Chieu"})
                    self.assertNotEqual(shifts["Dung"], "Sang")
                    for a, b in (("An", "Binh"), ("Binh", "Chi"), ("Chi", "Dung")):
                        self.assertNotEqual(shifts[a], shifts[b])
            cloud.assert_not_called()
            local.assert_not_called()

        extra_rule = prompts[1].replace("Yêu cầu:", "Mỗi ca có tối đa hai nhân viên.\nYêu cầu:")
        self.assertFalse(process_request(extra_rule, "instant").code)

    def test_basic_exercises_and_no_ignored_qualifier(self):
        self.assertEqual(self.result(process_request("# In 4 số Fibonacci đầu tiên bắt đầu từ 2, 3", "instant")), [2, 3, 5, 8])
        self.assertEqual(
            self.result(process_request("# Tính tổng số chẵn và tổng số lẻ trong danh sách [-3,0,4,7]", "instant")),
            {"even_sum": 4, "odd_sum": 4},
        )
        self.assertEqual(self.result(run_case("vector_metrics", left=[3, 4], right=[0, 0]))["angle_radians"], None)
        result = self.result(run_case("text_cosine", left="ĐÁa", right="da\u0301a", alphabet="ad"))
        self.assertEqual(result["left"], [2, 1])
        self.assertEqual(result["right"], result["left"])
        self.assertAlmostEqual(result["cosine"], 1)
        self.assertFalse(process_request("# In 4 số Fibonacci đầu tiên theo modulo 3", "instant").verified_ok)

    def test_ac3_merges_relations_on_same_arc_and_propagates(self):
        domains = {"A": [1, 2, 3], "B": [1, 2, 3], "C": [1, 2, 3]}
        constraints = [
            {"vars": ["A", "B"], "op": "lt"},
            {"vars": ["B", "A"], "allowed": [[2, 1], [3, 3]]},
            {"vars": ["C", "B"], "op": "eq"},
        ]
        answer = self.result(run_case("ac3", domains=domains, constraints=constraints))
        self.assertEqual(answer["domains"], {"A": [1], "B": [2], "C": [2]})
        self.assertTrue(answer["trace"])
        self.assertEqual(self.result(run_case("ac3", domains=domains, constraints=constraints + [{"vars": ["A", "B"], "op": "eq"}]))["status"], "inconsistent")

    def test_arc_consistency_does_not_claim_triangle_two_coloring_has_solution(self):
        response = run_case(
            "ac3", domains={name: ["red", "blue"] for name in "ABC"},
            constraints=[{"vars": [a, b], "op": "ne"} for a, b in itertools.combinations("ABC", 2)],
        )
        self.assertEqual(self.result(response)["status"], "arc_consistent")
        self.assertIn("chưa kết luận", response.stdout_preview)

    def test_nqueens_counts_with_fixed_blocked_and_vacuous_cases(self):
        for n, count in ((1, 1), (2, 0), (3, 0), (4, 2), (8, 92)):
            self.assertEqual(self.result(run_case("nqueens", n=n, mode="count"))["count"], count)
        one = self.result(run_case("nqueens", n=4, mode="count", fixed=[[0, 1]], blocked=[[1, 0]]))
        self.assertEqual(one, {"solution": (1, 3, 0, 2), "count": 1})
        self.assertEqual(self.result(process_request("# Đếm số cách xếp 5 quân hậu trên bàn cờ 5x5 bằng quay lui", "instant"))["count"], 10)

    def test_inheritance_retains_conflicting_unrelated_branches(self):
        frames = {
            "top": {"slots": {"can_fly": True, "weight": None}},
            "bird": {"parents": ["top"]},
            "owl": {"parents": ["bird"], "slots": {"can_fly": True}},
            "toy": {"parents": ["top"], "slots": {"can_fly": False}},
            "instance": {"parents": ["bird", "toy", "owl"]},
        }
        result = self.result(run_case("frame_inheritance", frames=frames, query="instance", slots=["can_fly", "weight", "color"]))
        self.assertEqual(result["can_fly"]["status"], "conflict")
        self.assertEqual({item["frame"] for item in result["can_fly"]["sources"]}, {"owl", "toy"})
        self.assertEqual(result["weight"]["status"], "value")
        self.assertIsNone(result["weight"]["value"])
        self.assertEqual(result["color"], {"status": "unknown"})
        frames["top"]["parents"] = ["instance"]
        self.assertEqual(run_case("frame_inheritance", frames=frames, query="instance", slots=["color"]).validation_status, "invalid")

    def test_sensorless_vacuum_cleans_every_possible_start(self):
        result = self.result(run_case("vacuum_plan", rooms=2, position=0, possible_dirty=[[], [0], [1], [0, 1]], first_action="right"))
        self.assertEqual(result["actions"], ["right", "suck", "left", "suck"])
        self.assertEqual(result["trace"][-1]["possible_dirty"], [[]])
        unknown_position = self.result(run_case(
            "vacuum_plan", rooms=2, position=[0, 1], possible_dirty=[[], [0], [1], [0, 1]], first_action="right",
        ))
        self.assertEqual(len(unknown_position["trace"][0]["possible_states"]), 8)
        self.assertEqual(unknown_position["actions"], result["actions"])
        self.assertIsNone(self.result(run_case("vacuum_plan", rooms=2, position=0, possible_dirty=[[]], goal_dirty=[1])))

    def test_hill_climbing_plateau_requires_explicit_sideways_steps(self):
        spec = {"scores": {"A": 1, "B": 1, "C": 3, "D": 9}, "edges": [["A", "B"], ["B", "C"]], "start": "A", "goal": "C"}
        self.assertEqual(self.result(run_case("hill_climbing", **spec))["status"], "plateau")
        self.assertEqual(self.result(run_case("hill_climbing", **spec, sideways_limit=1))["path"], ["A", "B", "C"])

    def test_string_search_matches_explicit_tree_traversal(self):
        goal, alphabet = "bba", "ab"

        def preorder(prefix, limit):
            yield prefix
            if len(prefix) < limit:
                for letter in alphabet:
                    yield from preorder(prefix + letter, limit)

        layers = [
            ["".join(chars) for chars in itertools.product(alphabet, repeat=depth)]
            for depth in range(len(goal) + 1)
        ]
        bfs_rank = [word for layer in layers for word in layer].index(goal) + 1
        dfs_rank = list(preorder("", len(goal))).index(goal) + 1
        expected = {"bfs": bfs_rank, "ucs": bfs_rank, "dfs": dfs_rank, "dls": dfs_rank,
                    "ids": sum(sum(len(layer) for layer in layers[:level + 1]) for level in range(len(goal))) + dfs_rank}
        for algorithm, count in expected.items():
            extras = {"depth_limit": 3} if algorithm == "dls" else {}
            result = self.result(run_case("string_search", goal=goal, alphabet=alphabet, algorithm=algorithm, **extras))
            self.assertEqual(result["visited"], count)
            self.assertEqual(result["path"], ["", "b", "bb", "bba"])
        self.assertEqual(self.result(run_case("string_search", goal="aa", alphabet="ab", algorithm="dls", depth_limit=1))["status"], "cutoff")


if __name__ == "__main__":
    unittest.main()
