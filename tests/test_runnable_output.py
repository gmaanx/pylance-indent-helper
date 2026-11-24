"""Tests for automatic runnable printing across Offline, Cloud API, and Ollama."""

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from core_engine import brain_router
from core_engine.cli_entry import decode_request
from core_engine.engine_pipeline import process_request
from core_engine.runnable_output import code_prints_when_run, ensure_runnable_print, has_meaningful_runnable_main
from tests.test_offline_geometry_classes import DIEM_PROMPT, VECTOR_PROMPT


def _exec_main(code: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<runnable-output-test>", "exec"), {"__name__": "__main__"})
    return buf.getvalue()


def _exec_import(code: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<runnable-output-import>", "exec"), {"__name__": "imported_module"})
    return buf.getvalue()


def _make_cloud_review(code: str) -> str:
    areas = ("input", "algorithm", "constraints", "output", "edge_cases")
    checks = {area: {"status": "ok", "detail": "Đã kiểm tra"} for area in areas}
    return json.dumps({"decision": "revise" if code else "keep", "code": code, "checks": checks})


class OfflineRunnableOutputTests(unittest.TestCase):
    def test_natural_vietnamese_output_formats_print_as_requested(self):
        cases = (
            (
                "# In 4 số Fibonacci đầu tiên bắt đầu từ 2, 3, mỗi số trên một dòng.",
                "2\n3\n5\n8\n",
            ),
            (
                "# Liệt kê 5 số nguyên tố đầu tiên cách nhau bởi dấu phẩy.",
                "2, 3, 5, 7, 11\n",
            ),
            (
                "# Tính tổng số chẵn và tổng số lẻ trong danh sách [-3, 0, 4, 7]. In kết quả dạng JSON.",
                '{"even_sum": 4, "odd_sum": 4}\n',
            ),
            (
                "# Bài toán đong nước bằng BFS. Dung tích các bình: (2, 4, 7, 9). "
                "Trạng thái ban đầu (0, 0, 0, 9). Mục tiêu 5 lít. In từng bước trên một dòng.",
                "(0, 0, 0, 9)\n(0, 4, 0, 5)\n",
            ),
            (
                DIEM_PROMPT + "\nIn kết quả với điểm (1, 2, 2), làm tròn 2 chữ số thập phân.",
                "3.00\n",
            ),
            (
                DIEM_PROMPT + '\nIn theo định dạng "Khoang cach: {result:.2f}"',
                "Khoang cach: 13.00\n",
            ),
        )
        for prompt, expected_stdout in cases:
            with self.subTest(prompt=prompt):
                res = process_request(prompt, "instant")
                self.assertEqual(res.validation_status, "verified", res.error_detail)
                self.assertEqual(_exec_import(res.code), "")
                self.assertEqual(_exec_main(res.code), expected_stdout)

    def test_structured_solve_output_formats_and_validation(self):
        graph_spec = {
            "type": "simpleai_graph",
            "start": "S",
            "goals": ["G"],
            "edges": [["S", "A", 2], ["A", "G", 3]],
            "algorithm": "ucs",
        }
        joined = process_request(
            "# @solve " + json.dumps({**graph_spec, "output": {"format": "join", "sep": " -> "}}),
            "instant",
        )
        self.assertTrue(joined.verified_ok, joined.error_detail)
        self.assertEqual(_exec_main(joined.code), "S -> A -> G\n")

        templated = process_request(
            "# @solve "
            + json.dumps({
                **graph_spec,
                "output": {"format": "template", "field": "cost", "template": "Chi phi: {result}"},
            }),
            "instant",
        )
        self.assertTrue(templated.verified_ok, templated.error_detail)
        self.assertEqual(_exec_main(templated.code), "Chi phi: 5\n")

        unsolvable = process_request(
            "# @solve "
            + json.dumps({
                "type": "water_jugs",
                "capacities": [2, 4],
                "start": [0, 4],
                "goal": 3,
                "output": {"none_text": "Khong co loi giai"},
            }),
            "instant",
        )
        self.assertTrue(unsolvable.verified_ok, unsolvable.error_detail)
        self.assertEqual(_exec_main(unsolvable.code), "Khong co loi giai\n")

        vec_json = process_request(
            "# @solve "
            + json.dumps({
                "type": "vector24",
                "sample": [[1] + [0] * 23, [0, 1] + [0] * 22],
                "output": {"format": "json"},
            }),
            "instant",
        )
        self.assertTrue(vec_json.verified_ok, vec_json.error_detail)
        parsed = json.loads(_exec_main(vec_json.code))
        self.assertEqual(parsed["dot"], 0)
        self.assertEqual(parsed["sum"][:2], [1, 1])

        # Invalid or unsupported output specs must never be silently ignored.
        bad_specs = (
            ("unsupported", {"type": "diem3d", "output": {"format": "xml"}}),
            ("unsupported", {"type": "diem3d", "output": {"format": "template", "template": "{result.__class__}"}}),
            ("unsupported", {"type": "diem3d", "output": {"format": "json", "sep": ","}}),
            ("needs_input", {"type": "diem3d", "output": {"format": "template"}}),
        )
        for expected_status, spec in bad_specs:
            with self.subTest(spec=spec):
                bad = process_request("# @solve " + json.dumps(spec), "instant")
                self.assertEqual(bad.validation_status, expected_status)
                self.assertFalse(bad.code)

    def test_vector24_prompt_with_json_output(self):
        res = process_request(VECTOR_PROMPT + "# In kết quả dạng JSON.", "instant")
        self.assertTrue(res.verified_ok, res.error_detail)
        parsed = json.loads(_exec_main(res.code))
        self.assertEqual(parsed["dot"], 11)


class CloudAndOllamaRunnableOutputTests(unittest.TestCase):
    def test_cloud_api_receives_runnable_print_instructions_in_generation_and_review(self):
        prompt = '# Viết hàm tinh_tong(a, b) trả về tổng a + b. Gọi thử tinh_tong(4, 9).'
        draft = "def tinh_tong(a, b):\n    return a + b"
        with patch.object(brain_router, "_request_cloud", side_effect=[draft, _make_cloud_review("")]) as provider:
            res = decode_request(json.dumps({
                "text": prompt,
                "mode": "full",
                "allow_cloud": True,
                "credentials": {"gemini": "fixture-key"},
            }), allow_network=True)

        self.assertEqual(provider.call_count, 2)
        gen_system = provider.call_args_list[0].args[4]
        review_system = provider.call_args_list[1].args[4]
        self.assertIn('if __name__ == "__main__":', gen_system)
        self.assertIn("print kết quả", gen_system)
        self.assertIn("định dạng yêu cầu", gen_system)
        self.assertIn('if __name__ == "__main__":', review_system)
        self.assertIn("print kết quả", review_system)

        # Even if the model still omitted __main__, the literal sample call from the prompt is printed on run.
        self.assertEqual(_exec_import(res["code"]), "")
        self.assertEqual(_exec_main(res["code"]), "13\n")

    def test_ollama_auto_appends_main_print_for_zero_arg_and_readme_example(self):
        readme_prompt = (
            '# Viết hàm chuan_hoa_ten(text) trả chuỗi đã bỏ khoảng trắng hai đầu '
            'và gộp các khoảng trắng liên tiếp thành một dấu cách. Thêm ví dụ với "  An   Bình  ".'
        )
        bare_fn = 'def chuan_hoa_ten(text):\n    return " ".join(text.split())'
        with patch.object(brain_router, "_post_json", side_effect=[{}, {"done": True, "response": bare_fn}]):
            res = decode_request(json.dumps({
                "text": readme_prompt,
                "mode": "local",
                "allow_local": True,
            }), allow_network=True)

        self.assertEqual(res["tier_used"], "tier2_ollama")
        self.assertEqual(_exec_import(res["code"]), "")
        self.assertEqual(_exec_main(res["code"]), "An Bình\n")

        with patch.object(
            brain_router, "_post_json",
            side_effect=[{}, {"done": True, "response": "def main():\n    return 99"}],
        ):
            res2 = decode_request(json.dumps({
                "text": "# Tính giá trị mẫu",
                "mode": "local",
                "allow_local": True,
            }), allow_network=True)
        self.assertEqual(_exec_import(res2["code"]), "")
        self.assertEqual(_exec_main(res2["code"]), "99\n")

    def test_static_ast_helper_edge_cases_and_opt_out(self):
        # 1. Existing __main__ assignment without print
        code_main_assign = 'def f(x):\n    return x * 2\n\nif __name__ == "__main__":\n    kq = f(6)\n'
        updated, ok = ensure_runnable_print(code_main_assign, "# Tính f")
        self.assertTrue(ok)
        self.assertEqual(_exec_main(updated), "12\n")

        # 2. Existing __main__ bare call without print
        code_main_call = 'def f(x):\n    return x * 3\n\nif __name__ == "__main__":\n    f(5)\n'
        updated2, ok2 = ensure_runnable_print(code_main_call, "# Tính f")
        self.assertTrue(ok2)
        self.assertEqual(_exec_main(updated2), "15\n")

        # 3. JSON print requirement honored by fallback
        code_fn = "def lay_ds():\n    return [1, 2, 3]\n"
        updated3, ok3 = ensure_runnable_print(code_fn, "# In kết quả dạng JSON")
        self.assertTrue(ok3)
        self.assertEqual(json.loads(_exec_main(updated3)), [1, 2, 3])

        # 4. Explicit opt-out is respected
        untouched, ok4 = ensure_runnable_print(code_fn, "# Chỉ định nghĩa hàm, không in")
        self.assertTrue(ok4)
        self.assertEqual(untouched, code_fn)

        # 5. Editing existing code leaves output untouched
        untouched2, ok5 = ensure_runnable_print(code_fn, "# Sửa lỗi", editing_existing=True)
        self.assertTrue(ok5)
        self.assertEqual(untouched2, code_fn)

        # 6. Function calling helper that prints is recognized as already printing
        already_prints = 'def show():\n    print("ok")\n\nif __name__ == "__main__":\n    show()\n'
        self.assertTrue(code_prints_when_run(already_prints))
        same, ok6 = ensure_runnable_print(already_prints, "# In ok")
        self.assertTrue(ok6)
        self.assertEqual(same, already_prints)

        # 7. Dummy greeting main() or undefined main() is rejected as non-meaningful
        dummy_main = (
            "class HinhChuNhat:\n    def __init__(self, d, r):\n        self.d, self.r = d, r\n\n"
            'def main():\n    print("Xin chao")\n\nif __name__ == "__main__":\n    main()\n'
        )
        self.assertFalse(has_meaningful_runnable_main(dummy_main, "# Viết lớp HinhChuNhat"))
        _, ok7 = ensure_runnable_print(dummy_main, "# Viết lớp HinhChuNhat")
        self.assertFalse(ok7)

        undefined_main = (
            "def tinh(a, b):\n    return a + b\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        _, ok8 = ensure_runnable_print(undefined_main, "# Viết hàm tinh")
        self.assertFalse(ok8)

        shadowed_main = (
            "def giai_thua(n):\n    return 1 if n <= 1 else n * giai_thua(n - 1)\n\n"
            "def main():\n    giai_thua = giai_thua(5)\n    print(giai_thua)\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        self.assertFalse(has_meaningful_runnable_main(shadowed_main, "# Viết hàm giai_thua"))

    def test_ollama_repairs_dummy_or_missing_main_in_one_followup_call(self):
        prompt = '# Viết lớp HinhChuNhat(dai, rong) tính dien_tich().'
        dummy_draft = (
            "class HinhChuNhat:\n"
            "    def __init__(self, dai, rong):\n"
            "        self.dai, self.rong = dai, rong\n"
            "    def dien_tich(self):\n"
            "        return self.dai * self.rong\n\n"
            'if __name__ == "__main__":\n'
            '    print("Xin chao")\n'
        )
        repaired_code = (
            "class HinhChuNhat:\n"
            "    def __init__(self, dai, rong):\n"
            "        self.dai, self.rong = dai, rong\n"
            "    def dien_tich(self):\n"
            "        return self.dai * self.rong\n\n"
            "def main():\n"
            "    hcn = HinhChuNhat(4, 5)\n"
            "    print(hcn.dien_tich())\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )
        with patch.object(
            brain_router, "_post_json",
            side_effect=[
                {},
                {"done": True, "response": dummy_draft},
                {"done": True, "response": repaired_code},
            ],
        ) as post:
            res = decode_request(json.dumps({
                "text": prompt,
                "mode": "local",
                "allow_local": True,
            }), allow_network=True)

        self.assertEqual(post.call_count, 3)
        self.assertEqual(_exec_import(res["code"]), "")
        self.assertEqual(_exec_main(res["code"]), "20\n")


if __name__ == "__main__":
    unittest.main()
