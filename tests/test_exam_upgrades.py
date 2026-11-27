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
from core_engine.contract_checker import check_api_contract, validate_shadow_output
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

    def test_dynamic_vietnamese_nlp_solvers_verify_offline(self):
        cases = [
            "Giải bài toán mật mã chữ số SEND + MORE = MONEY.",
            "Cho tập sự kiện facts = ['A', 'B'] và tập luật Horn: R1: A & B -> C; R2: C -> D. Chứng minh 'D' bằng suy diễn lùi.",
            "Tô màu bản đồ bằng SimpleAI CSP cho các vùng ['WA', 'NT', 'SA'] với các màu ['Do', 'Xanh', 'Vang'], các cặp vùng kề nhau: [('WA', 'NT'), ('NT', 'SA'), ('WA', 'SA')] với MRV + LCV.",
            "Cho đồ thị có hướng với các cạnh [('A', 'B', 2), ('B', 'G', 3), ('A', 'G', 7)], tìm đường từ 'A' đến 'G' bằng SimpleAI với thuật toán A* và heuristic {'A': 4, 'B': 2, 'G': 0}.",
            "Cho hai tập mờ A = {'x1': '0.2', 'x2': '0.8'} và B = {'x1': '0.5', 'x2': '0.4'}, tính giao.",
        ]
        for prompt in cases:
            with self.subTest(prompt=prompt):
                res = process_request(prompt, action_mode="instant")
                self.assertTrue(res.verified_ok, f"Failed: {prompt} -> {res.error_detail}")
                self.assertEqual(res.validation_status, "verified")

    def test_api_contract_checker_and_semantic_none_output_repair(self):
        wrong_name_code = (
            "class WrongNode:\n"
            "    def __init__(self, s):\n        self.s = s\n\n"
            "def main():\n    print(123)\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        err = check_api_contract(
            wrong_name_code,
            "Viết lớp NutTimKiem có phương thức f_cost(self) và truy_vet_duong_di(self).",
        )
        self.assertIn("class NutTimKiem", err)
        self.assertIn("f_cost", err)

        forgot_return = (
            "def tinh_tong(a, b):\n    kq = a + b\n\n"
            "def main():\n    print(tinh_tong(3, 4))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        sem_err = validate_shadow_output(forgot_return, "None\n", "Viết hàm tinh_tong(a, b)")
        self.assertIn("return", sem_err)

        repaired = (
            "def tinh_tong(a, b):\n    return a + b\n\n"
            "def main():\n    print(tinh_tong(3, 4))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        with patch.object(
            brain_router,
            "_post_json",
            side_effect=[
                {},
                {"done": True, "response": forgot_return},
                {},
                {"done": True, "response": repaired},
            ],
        ):
            res = process_request(
                "# Viết hàm tinh_tong(a, b) trả về a + b",
                action_mode="local",
                allow_local=True,
                allow_shadow_exec=True,
            )
        self.assertEqual(res.validation_status, "runtime_checked")
        self.assertEqual(res.stdout_preview, "7")

    def test_scorched_earth_purge_ollama_wipes_all_folders_and_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_dir = root / "local"
            home_dir = root / "home"
            for d in (
                local_dir / "Programs" / "Ollama",
                local_dir / "Ollama",
                local_dir / "PylanceHelperLocalAI",
                home_dir / ".ollama" / "models",
            ):
                d.mkdir(parents=True)
                (d / "dummy.dat").write_text("trace", encoding="utf-8")
            unins = local_dir / "Programs" / "Ollama" / "unins000.exe"
            unins.write_text("exe", encoding="utf-8")

            with patch.dict("os.environ", {"LOCALAPPDATA": str(local_dir), "APPDATA": str(root / "roaming")}), \
                    patch.object(Path, "home", return_value=home_dir), \
                    patch.object(local_ai, "find_ollama", return_value=local_dir / "Programs" / "Ollama" / "ollama.exe"), \
                    patch.object(local_ai, "_stop_ollama_processes") as stop_proc, \
                    patch.object(local_ai, "_scrub_ollama_windows_traces") as scrub_reg, \
                    patch.object(local_ai, "_run") as run_cmd:
                local_ai.uninstall_local_ai(purge_all=True)

            self.assertGreaterEqual(stop_proc.call_count, 2)
            scrub_reg.assert_called_once()
            run_cmd.assert_called_once()
            self.assertFalse((local_dir / "Programs" / "Ollama").exists())
            self.assertFalse((local_dir / "Ollama").exists())
            self.assertFalse((local_dir / "PylanceHelperLocalAI").exists())
            self.assertFalse((home_dir / ".ollama").exists())

    def test_bai_2_1_4_1_4_2_and_four_quote_prompts_verify_and_execute_accurately(self):
        # 1. Bai 2.1 with 4 quotes """" ... """" and LaTeX escapes
        p_2_1 = (
            '""""\n'
            'Bài 2.1: Vector hóa nguyên âm & Khoảng cách / Độ tương đồng\n'
            'Cho một chuỗi văn bản tiếng Anh:\n'
            'Viết hàm vector_nguyen_am(text: str) -> list[int] đếm tần suất xuất hiện của 5 nguyên âm "aeiou" '
            '(không phân biệt chữ hoa/chữ thường nhờ .lower()), trả về danh sách gồm 5 số nguyên theo đúng thứ tự '
            "'a', 'e', 'i', 'o', 'u'.\n"
            'Viết hàm do_tuong_dong_cosine(v1: list[int], v2: list[int]) -> float tính độ tương đồng Cosine giữa hai vector cùng độ dài:\n'
            r'$$\text{sim}(v_1, v_2) = \frac{\sum v_{1,k} v_{2,k}}{\sqrt{\sum v_{1,k}^2} \cdot \sqrt{\sum v_{2,k}^2}}$$' + '\n'
            'Lưu ý biên: nếu một trong hai vector có chuẩn/độ dài bằng 0 (ví dụ chuỗi không có nguyên âm nào), '
            'trả về 0.0 để không bị lỗi chia cho 0.\n'
            '""""'
        )
        r21 = process_request(p_2_1, action_mode="instant")
        self.assertEqual(r21.validation_status, "verified")
        ns21 = {"__name__": "t21"}
        exec(compile(r21.code, "<t21>", "exec"), ns21)
        self.assertEqual(ns21["vector_nguyen_am"]("AeIoU aAA"), [4, 1, 1, 1, 1])
        self.assertEqual(ns21["do_tuong_dong_cosine"]([1, 2, 0, 0, 1], [0, 0, 0, 0, 0]), 0.0)
        self.assertAlmostEqual(ns21["do_tuong_dong_cosine"]([1, 2, 3, 0, 1], [1, 2, 3, 0, 1]), 1.0)

        # 2. Bai 4.1: BFS & DFS on dict
        p_4_1 = (
            'Bài 4.1: Cài đặt BFS và DFS trên đồ thị (dict)\n'
            'Cho đồ thị có hướng/vô hướng biểu diễn bằng từ điển (dict), ví dụ:\n'
            'graph = {"A": ["B", "C"], "B": ["D", "E"], "C": ["F"], "D": [], "E": ["F"], "F": []}\n'
            'Viết hàm bfs(graph, start, goal) sử dụng hàng đợi FIFO và tập visited để tìm đường đi từ start đến goal.\n'
            'Viết hàm dfs(graph, start, goal) sử dụng ngăn xếp LIFO để tìm đường đi từ start đến goal.'
        )
        r41 = process_request(p_4_1, action_mode="instant")
        self.assertEqual(r41.validation_status, "verified")
        ns41 = {"__name__": "t41"}
        exec(compile(r41.code, "<t41>", "exec"), ns41)
        g = {"A": ["B", "C"], "B": ["D", "E"], "C": ["F"], "D": [], "E": ["F"], "F": []}
        self.assertEqual(ns41["bfs"](g, "A", "F"), ["A", "C", "F"])
        self.assertEqual(ns41["dfs"](g, "A", "F"), ["A", "B", "E", "F"])
        self.assertIsNone(ns41["bfs"](g, "D", "A"))
        self.assertIsNone(ns41["dfs"](g, "D", "A"))

        # 3. Bai 4.2: Forward chaining & CNF violated clause counter
        p_4_2 = (
            'Bài 4.2: Kiểm tra ràng buộc / Suy diễn logic mệnh đề đơn giản\n'
            'facts = {"C": True, "A": True, "R": True, "I": False, "D": True}\n'
            r'$C \land A \rightarrow Q$' + '\n'
            r'$R \land I \rightarrow H$' + '\n'
            r'$Q \land H \land D \rightarrow E$' + '\n'
            r'$E \rightarrow S$' + '\n'
            'Viết hàm suy_dien_tien(facts: dict[str, bool]) -> dict[str, bool] suy ra giá trị của Q, H, E, S.\n'
            'Viết hàm dem_rang_buoc_vi_pham(assignment: dict[str, bool], clauses: list[list[tuple[str, bool]]]) -> int '
            'đếm xem có bao nhiêu mệnh đề không được thỏa mãn.'
        )
        r42 = process_request(p_4_2, action_mode="instant")
        self.assertEqual(r42.validation_status, "verified")
        ns42 = {"__name__": "t42"}
        exec(compile(r42.code, "<t42>", "exec"), ns42)
        out_f = ns42["suy_dien_tien"]({"C": True, "A": True, "R": True, "I": False, "D": True})
        self.assertEqual((out_f["Q"], out_f["H"], out_f["E"], out_f["S"]), (True, False, False, False))
        out_t = ns42["suy_dien_tien"]({"C": True, "A": True, "R": True, "I": True, "D": True})
        self.assertEqual((out_t["Q"], out_t["H"], out_t["E"], out_t["S"]), (True, True, True, True))
        self.assertEqual(
            ns42["dem_rang_buoc_vi_pham"](
                {"A": True, "B": False},
                [[("A", True)], [("A", False), ("B", True)], [("B", True)]],
            ),
            2,
        )

        # 4. Skeleton de-poisoning: Vector24 & 2-arg Nut BFS must NOT pollute custom pure-Python APIs
        skels_21 = brain_router.select_relevant_skeletons(p_2_1, top_k=2, for_local_model=True)
        self.assertFalse(any(s["id"] == "oop_vector24_cosine_plagiarism" for s in skels_21))
        skels_41 = brain_router.select_relevant_skeletons(p_4_1, top_k=2, for_local_model=True)
        self.assertFalse(any(s["id"] == "raw_graph_search" for s in skels_41))

        # 5. Every single exercise block in thu_nghiem.py solves offline with verified_ok=True
        import re as _re
        thu_nghiem_path = Path(__file__).resolve().parents[1] / "thu_nghiem.py"
        blocks = _re.findall(r'"""[\s\S]*?"""', thu_nghiem_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(blocks), 6)
        for idx, block in enumerate(blocks, start=1):
            with self.subTest(block_index=idx):
                res_blk = process_request(block, action_mode="instant")
                self.assertTrue(res_blk.verified_ok, f"Block {idx} failed: {res_blk.error_detail}")
                self.assertEqual(res_blk.validation_status, "verified")


if __name__ == "__main__":
    unittest.main()
