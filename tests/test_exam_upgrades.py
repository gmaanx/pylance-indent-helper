"""Comprehensive tests for the 10-point exam upgrades:
- Encrypted credentials round-trip & RAM-aware model selection
- Chapter 8 (Ontology/Frames) & Chapter 9 (Bayes/CPT/Fuzzy) + OOP Golden Skeletons
- Flexible natural-language offline prompts (NutTimKiem, 8-Puzzle variants)
- Sibling workspace file context (.json, .txt, .py) & # TODO starter template completion
- Zero-fingerprint output & closed-loop Shadow Execution Traceback auto-repair
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core_engine import brain_router
from core_engine.config_manager import (
    clear_encrypted_credentials,
    load_encrypted_credentials,
    save_encrypted_credential,
)
from core_engine.engine_pipeline import process_request
from core_engine.golden_skeletons import ALL_SKELETONS
from core_engine.workspace_context import collect_workspace_context, is_starter_template
from setup_lab import local_ai


class ExamUpgradeTests(unittest.TestCase):
    def test_encrypted_credentials_roundtrip_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = save_encrypted_credential("gemini", "AIzaTestKey_123", install_dir=root)
            raw_text = path.read_text(encoding="utf-8")
            self.assertNotIn("AIzaTestKey_123", raw_text)
            save_encrypted_credential("groq", "gsk_SecondKey_456", install_dir=root)
            loaded = load_encrypted_credentials(install_dir=root)
            self.assertEqual(list(loaded.keys())[0], "groq")
            self.assertEqual(loaded["groq"], "gsk_SecondKey_456")
            self.assertEqual(loaded["gemini"], "AIzaTestKey_123")
            clear_encrypted_credentials(install_dir=root)
            self.assertEqual(load_encrypted_credentials(install_dir=root), {})

    def test_ram_aware_model_selection(self):
        with patch.object(local_ai, "detect_ram_gb", return_value=7.9):
            self.assertEqual(local_ai.recommend_model_for_machine(), "qwen2.5-coder:1.5b")
        with patch.object(local_ai, "detect_ram_gb", return_value=15.8):
            self.assertEqual(local_ai.recommend_model_for_machine(), "qwen2.5-coder:3b")

    def test_new_chapter_8_9_and_oop_skeletons_exist_and_retrieve(self):
        expected_ids = {
            "ontology_tbox_abox_simpleai",
            "frame_inheritance_conflict",
            "logic_backward_chaining_hybrid",
            "prob_joint_conditional_bayes",
            "prob_bayesian_network_cpt",
            "fuzzy_sets_inference",
            "oop_vector24_cosine_plagiarism",
            "oop_search_node_nuttimkiem",
        }
        self.assertTrue(expected_ids.issubset(ALL_SKELETONS.keys()))

        ont = brain_router.select_relevant_skeletons(
            "Biểu diễn tri thức bằng Ontology TBox ABox, subClassOf, disjoint và kiểm chứng bằng SimpleAI",
            top_k=2,
        )
        self.assertTrue(any(s["id"] == "ontology_tbox_abox_simpleai" for s in ont))

        fuzzy = brain_router.select_relevant_skeletons(
            "Tính hợp, giao, phần bù tập mờ, lát cắt alpha và giải mờ trọng tâm Centroid",
            top_k=2,
        )
        self.assertTrue(any(s["id"] == "fuzzy_sets_inference" for s in fuzzy))

    def test_nut_tim_kiem_and_flexible_puzzle_solve_offline_with_zero_fingerprint(self):
        prompt = (
            "Bài 1.2: Lớp NutTimKiem (Node cho bài toán tìm kiếm) "
            "Viết lớp NutTimKiem dùng biểu diễn nút trong thuật toán tìm kiếm: "
            "__init__(self, state, parent=None, action=None, g=0.0, h=0.0): lưu các thuộc tính. "
            "f_cost(self): trả về tổng chi phí f(n) = g(n) + h(n). "
            "truy_vet_duong_di(self): đi ngược từ nút hiện tại qua parent đến nút gốc."
        )
        res = process_request(prompt, action_mode="instant")
        self.assertTrue(res.verified_ok)
        self.assertEqual(res.validation_status, "verified")
        self.assertFalse(res.code.startswith("# ["))
        self.assertIn("class NutTimKiem:", res.code)
        self.assertIn("def truy_vet_duong_di(self):", res.code)

        puzzle_prompt = (
            "Giải bài toán 8-puzzle với trạng thái đầu ((1, 2, 3), (4, 0, 6), (7, 5, 8)) "
            "và đích ((1, 2, 3), (4, 5, 6), (7, 8, 0)). "
            "Viết chương trình bằng simpleai giải bằng A* với khoảng cách Manhattan."
        )
        res_puz = process_request(puzzle_prompt, action_mode="instant")
        self.assertTrue(res_puz.verified_ok)
        self.assertFalse(res_puz.code.startswith("# ["))

    def test_workspace_context_scans_sibling_data_and_python_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            exam_py = folder / "bai_thi.py"
            exam_py.write_text("# Đọc relationships.json và dùng Vector24 từ btvnbuoi1\n", encoding="utf-8")
            (folder / "relationships.json").write_text(
                json.dumps({"father": [{"John": "William"}, {"John": "David"}]}),
                encoding="utf-8",
            )
            (folder / "coastal_states.txt").write_text("California, Oregon, Washington\n", encoding="utf-8")
            (folder / "btvnbuoi1.py").write_text(
                "class Vector24:\n    def __init__(self, components):\n        pass\n    def tich_vo_huong(self, other):\n        pass\n",
                encoding="utf-8",
            )
            ctx = collect_workspace_context(
                "# Đọc relationships.json và coastal_states.txt, import btvnbuoi1",
                file_path=str(exam_py),
                notebook_context="CELL_VAR = 42",
            )
            self.assertIn("CELL_VAR = 42", ctx)
            self.assertIn("relationships.json", ctx)
            self.assertIn("coastal_states.txt", ctx)
            self.assertIn("class Vector24", ctx)

    def test_starter_template_detection_and_completion(self):
        starter = (
            '"""Viết hàm tinh_binh_phuong(x) trả về x * x."""\n'
            "def tinh_binh_phuong(x):\n"
            "    # TODO: hoàn thiện hàm\n"
            "    pass\n"
        )
        self.assertTrue(is_starter_template(starter))
        completed = (
            "def tinh_binh_phuong(x):\n"
            "    return x * x\n\n"
            "def main():\n"
            "    print(tinh_binh_phuong(6))\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n"
        )
        with patch.object(brain_router, "_post_json", side_effect=[{}, {"done": True, "response": completed}]):
            res = process_request(starter, action_mode="full", allow_local=True, allow_shadow_exec=True)
        self.assertEqual(res.validation_status, "runtime_checked")
        self.assertEqual(res.stdout_preview, "36")
        self.assertIn("def tinh_binh_phuong(x):", res.code)

    def test_shadow_execution_self_heals_runtime_traceback_and_alt4_self_fix(self):
        # 1. Model produces buggy first draft (ZeroDivisionError), then repairs after Traceback feedback
        buggy = 'def main():\n    print(10 // 0)\n\nif __name__ == "__main__":\n    main()\n'
        fixed = 'def main():\n    print(10 // 2)\n\nif __name__ == "__main__":\n    main()\n'
        with patch.object(
            brain_router,
            "_post_json",
            side_effect=[
                {},
                {"done": True, "response": buggy},
                {},
                {"done": True, "response": fixed},
            ],
        ) as post:
            res = process_request(
                "# Tính thương 10 chia 2",
                action_mode="local",
                allow_local=True,
                allow_shadow_exec=True,
            )
        self.assertEqual(post.call_count, 4)
        self.assertEqual(res.validation_status, "runtime_checked")
        self.assertEqual(res.stdout_preview, "5")

        # 2. Alt+4 True Self-Fix catches runtime NameError and repairs via Ollama
        broken_user_code = "def tinh():\n    return bien_chua_khai_bao + 1\n\nprint(tinh())\n"
        fixed_user_code = "def tinh():\n    bien_da_khai_bao = 9\n    return bien_da_khai_bao + 1\n\nprint(tinh())\n"
        with patch.object(
            brain_router,
            "_post_json",
            side_effect=[{}, {"done": True, "response": fixed_user_code}],
        ):
            fix_res = process_request(
                broken_user_code,
                action_mode="self_fix",
                allow_local=True,
                allow_shadow_exec=True,
            )
        self.assertEqual(fix_res.validation_status, "runtime_checked")
        self.assertEqual(fix_res.stdout_preview, "10")

    def test_auto_pilot_rag_fallback_when_cloud_and_ollama_unavailable(self):
        res = process_request(
            "# Biểu diễn tri thức bằng Ontology TBox ABox kết hợp SimpleAI",
            action_mode="full",
            allow_cloud=False,
            allow_local=False,
            allow_rag_fallback=True,
            allow_shadow_exec=True,
        )
        self.assertEqual(res.validation_status, "reference")
        self.assertIn("ontology_tbox_abox_simpleai", res.tier_used)
        self.assertTrue(res.stdout_preview)


if __name__ == "__main__":
    unittest.main()
