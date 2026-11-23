"""The pasted class exercises must never yield unrelated example code."""

import io
import math
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core_engine.engine_pipeline import process_request


VECTOR_PROMPT = r"""## Đề bài yêu cầu tạo một lớp Vector24 biểu diễn vector 24 chiều,
# có:Cộng 2 vector (v1 + v2).
# Tích vô hướng (v1 · v2 = tổng tích từng cặp tọa độ tương ứng: $a_1 b_1 + a_2 b_2 + \cdots + a_{24} b_{24}$).
# Góc giữa 2 vector (tính từ công thức $\cos\theta = \frac{\vec{u} \cdot \vec{v}}{||\vec{u}||||\vec{v}||}$
# sau đó dùng math.acos để ra góc tính bằng radian).
"""
DIEM_PROMPT = (
    r"Bài 1.1: Lớp Diem3D (Điểm trong không gian 3 chiều)Viết lớp Diem3D bằng Python thuần (import math) "
    r"với các yêu cầu:__init__(self, x, y, z): chuyển x, y, z sang kiểu float. "
    r"Nếu giá trị không phải số (hoặc không chuyển được sang float), báo lỗi phù hợp (TypeError hoặc ValueError)."
    r"khoang_cach_goc(self): tính khoảng cách Euclid từ điểm tới gốc tọa độ $(0, 0, 0)$, "
    r"công thức: $$d = \sqrt{x^2 + y^2 + z^2}$$"
)


class GeometryClassTests(unittest.TestCase):
    def generated_class(self, prompt, name):
        response = process_request(prompt, "instant")
        self.assertEqual(response.tier_used, "offline_" + name.lower(), response.error_detail)
        self.assertTrue(response.verified_ok)
        self.assertNotIn("simpleai", response.code)
        namespace = {}
        exec(compile(response.code, "<geometry-class>", "exec"), namespace)
        return namespace[name]

    def test_vector24_screen_request_and_numerical_contract(self):
        vector = self.generated_class(VECTOR_PROMPT, "Vector24")
        x = vector([1, 0, *([0] * 22)])
        y = vector([0, 2, *([0] * 22)])
        self.assertEqual((x + y).components, (1, 2, *([0] * 22)))
        self.assertEqual(x.tich_vo_huong(y), 0)
        self.assertAlmostEqual(x.goc(y), math.pi / 2)
        self.assertAlmostEqual(x.goc(vector([-1, *([0] * 23)])), math.pi)
        huge = vector([1e300, *([0] * 23)])
        self.assertEqual(huge.goc(huge), 0)
        with self.assertRaises(ValueError):
            vector([0] * 23)
        with self.assertRaises(ValueError):
            x.goc(vector([0] * 24))
        with self.assertRaises(TypeError):
            vector(["seven"] * 24)

    def test_diem3d_uncommented_screen_request_and_numeric_validation(self):
        point = self.generated_class(DIEM_PROMPT, "Diem3D")
        instance = point(3, "4", 12)
        self.assertEqual((instance.x, instance.y, instance.z), (3.0, 4.0, 12.0))
        self.assertTrue(all(type(value) is float for value in (instance.x, instance.y, instance.z)))
        self.assertAlmostEqual(instance.khoang_cach_goc(), 13)
        self.assertAlmostEqual(point(1e300, 0, 0).khoang_cach_goc(), 1e300)
        for value, error in (("oops", ValueError), (None, TypeError), ("nan", ValueError), (10**400, ValueError)):
            with self.subTest(value=type(value), error=error), self.assertRaises(error):
                point(value, 0, 0)

    def test_class_prompt_with_mixed_comments_and_math_markdown(self):
        point_prompt = DIEM_PROMPT.replace("khoang_cach_goc", "\n# khoang_cach_goc")
        self.generated_class(point_prompt, "Diem3D")
        vector_prompt = VECTOR_PROMPT.replace(
            r"||\vec{u}||||\vec{v}||}$",
            r"\left\|\vec{u}\right\|\left\|\vec{v}\right\|}$.",
        )
        self.generated_class(vector_prompt, "Vector24")

    def test_class_solutions_print_examples_only_when_run_directly(self):
        for prompt, expected in ((DIEM_PROMPT, ["13.0"]), (VECTOR_PROMPT, ["11"])):
            with self.subTest(prompt=prompt):
                response = process_request(prompt, "instant")
                script = compile(response.code, "<geometry-example>", "exec")
                output = io.StringIO()
                with redirect_stdout(output):
                    exec(script, {"__name__": "exercise"})
                self.assertEqual(output.getvalue(), "")
                with redirect_stdout(output):
                    exec(script, {"__name__": "__main__"})
                self.assertLessEqual(set(expected), set(output.getvalue().splitlines()))

    def test_geometry_variants_cannot_silently_drop_extra_constraints(self):
        examples = (
            VECTOR_PROMPT + "# Ngoài ra tính thêm tích có hướng.",
            DIEM_PROMPT + " Thêm phương thức khoảng cách giữa hai điểm.",
            DIEM_PROMPT.replace("0, 0, 0", "1, 0, 0"),
            DIEM_PROMPT + "\n# --- Yêu cầu khác: so sánh hai điểm.",
        )
        for prompt in examples:
            with self.subTest(prompt=prompt):
                response = process_request(prompt, "instant")
                self.assertEqual(response.validation_status, "needs_input", response.error_detail)
                self.assertFalse(response.code)
                self.assertIn("@solve", response.error_detail)

    def test_strict_geometry_specs_and_no_fuzzy_reference_on_unrelated_prose(self):
        self.generated_class('# @solve {"type":"diem3d"}', "Diem3D")
        self.generated_class('# @solve {"type":"vector24"}', "Vector24")
        response = process_request('# @solve {"type":"diem3d","zero":[1,0,0]}', "instant")
        self.assertEqual(response.validation_status, "unsupported", response.error_detail)
        self.assertFalse(response.code)

        raw = "# Lớp ConNguoi lưu tên, tuổi, điểm thi, tổng điểm các cặp và đầu ra dạng bảng."
        with patch("core_engine.engine_pipeline.call_tier2_local_llm") as local, patch(
            "core_engine.engine_pipeline.call_tier1_cloud_llm",
        ) as cloud:
            response = process_request(raw, "instant")
            self.assertEqual(response.validation_status, "unsupported", response.error_detail)
            self.assertFalse(response.code)
            local.assert_not_called()
            cloud.assert_not_called()
            self.assertIn("Alt+5", response.diagnostics[0])
        reference = process_request("# @csp bai:magic_square", "instant")
        self.assertEqual(reference.validation_status, "reference", reference.error_detail)
        self.assertFalse(reference.verified_ok)
        self.assertIn("csp_magic_square", reference.tier_used)

    def test_solve_json_accepts_one_outer_markdown_fence_and_explains_bad_json(self):
        fenced = chr(96) * 3 + "json\n# @solve {\"type\":\"diem3d\"}\n" + chr(96) * 3
        response = process_request(fenced, "instant")
        self.assertEqual(response.validation_status, "verified")
        malformed = process_request("# @solve {\"type\":\"diem3d\",}", "instant")
        self.assertEqual(malformed.validation_status, "invalid")
        self.assertIn("dòng", malformed.error_detail)
        self.assertIn("diem3d", malformed.error_detail)


if __name__ == "__main__":
    unittest.main()
