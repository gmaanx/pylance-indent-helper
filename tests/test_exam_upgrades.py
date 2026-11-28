"""Comprehensive tests for the 10-point exam upgrades:
- Encrypted credentials round-trip & RAM-aware model selection
- Chapter 8 (Ontology/Frames) & Chapter 9 (Bayes/CPT/Fuzzy) + OOP Golden Skeletons
- Flexible natural-language offline prompts (NutTimKiem, 8-Puzzle variants)
- Sibling workspace file context (.json, .txt, .py) & # TODO starter template completion
- Zero-fingerprint output & closed-loop Shadow Execution Traceback auto-repair
"""

from __future__ import annotations

import json
import sys
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
from core_engine.semantic_verifier import verify_candidate_semantics
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
        with patch.object(local_ai, "detect_nvidia_vram_gb", return_value=0.0):
            with patch.object(local_ai, "detect_ram_gb", return_value=7.9):
                self.assertEqual(local_ai.recommend_model_for_machine(), "qwen2.5-coder:1.5b")
            with patch.object(local_ai, "detect_ram_gb", return_value=15.8):
                self.assertEqual(local_ai.recommend_model_for_machine(), "qwen2.5-coder:1.5b")
        with patch.object(local_ai, "detect_nvidia_vram_gb", return_value=4.5), patch.object(
            local_ai, "detect_ram_gb", return_value=16.0
        ):
            self.assertEqual(local_ai.recommend_model_for_machine(), "qwen2.5-coder:3b")
        with patch.object(local_ai, "detect_nvidia_vram_gb", return_value=8.0), patch.object(
            local_ai, "detect_ram_gb", return_value=16.0
        ):
            self.assertEqual(local_ai.recommend_model_for_machine(), "qwen2.5-coder:7b")

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

    def test_semantic_verifier_catches_subtle_bugs_and_drives_closed_loop_repair(self):
        # 1. Catches bool returned when `-> int` was requested
        bool_instead_of_int = (
            "def dem_vi_pham(x: int) -> int:\n    return True\n\n"
            "def main():\n    print(dem_vi_pham(3))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        err_rt = verify_candidate_semantics(bool_instead_of_int, "Viết hàm dem_vi_pham(x: int) -> int")
        self.assertIn("int", err_rt)
        self.assertIn("bool", err_rt)

        # 2. Catches single zero-vector ZeroDivisionError (`and` instead of `or`) even when main() passed!
        buggy_cosine = (
            "import math\n"
            "def my_cos(v1: list[int], v2: list[int]) -> float:\n"
            "    if sum(v1) == 0 and sum(v2) == 0:\n        return 0.0\n"
            "    n1 = math.sqrt(sum(a*a for a in v1))\n"
            "    n2 = math.sqrt(sum(b*b for b in v2))\n"
            "    return sum(a*b for a, b in zip(v1, v2)) / (n1 * n2)\n\n"
            "def main():\n    print(my_cos([1, 2], [2, 1]))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        fixed_cosine = buggy_cosine.replace(
            "if sum(v1) == 0 and sum(v2) == 0:",
            "if all(x == 0 for x in v1) or all(y == 0 for y in v2):",
        )
        err_zero = verify_candidate_semantics(
            buggy_cosine,
            "Viết hàm my_cos(v1: list[int], v2: list[int]) -> float, trả về 0.0 để không bị lỗi chia cho 0.",
        )
        self.assertIn("ZeroDivisionError", err_zero)

        with patch.object(
            brain_router,
            "_post_json",
            side_effect=[
                {},
                {"done": True, "response": buggy_cosine},
                {},
                {"done": True, "response": fixed_cosine},
            ],
        ) as post_mock:
            repaired_res = process_request(
                "# Viết hàm my_cos(v1: list[int], v2: list[int]) -> float tính cosine, trả về 0.0 để không chia cho 0.",
                action_mode="local",
                allow_local=True,
                allow_shadow_exec=True,
            )
        self.assertEqual(post_mock.call_count, 4)
        self.assertEqual(repaired_res.validation_status, "runtime_checked")
        self.assertIn("or all", repaired_res.code)

        # 3. Catches sink-vertex KeyError (`graph[curr]` instead of `graph.get(curr, [])`) & cyclic graph bugs
        buggy_bfs = (
            "from collections import deque\n"
            "def tim_bfs(graph, start, goal):\n"
            "    q = deque([(start, [start])])\n"
            "    vis = {start}\n"
            "    while q:\n"
            "        u, p = q.popleft()\n"
            "        if u == goal: return p\n"
            "        for v in graph[u]:\n"
            "            if v not in vis:\n"
            "                vis.add(v)\n"
            "                q.append((v, p + [v]))\n"
            "    return None\n\n"
            'def main():\n    print(tim_bfs({"A": ["B"], "B": []}, "A", "B"))\n\n'
            'if __name__ == "__main__":\n    main()\n'
        )
        err_sink = verify_candidate_semantics(buggy_bfs, "Viết hàm tim_bfs(graph, start, goal)")
        self.assertIn("KeyError", err_sink)

        # 4. Catches latent short-circuit KeyError on propositional `facts` when all facts are True
        buggy_fc = (
            "def suy_dien(facts: dict[str, bool]) -> dict[str, bool]:\n"
            "    e = facts['A'] and facts['B']\n"
            "    s = e and facts['S']\n"
            "    return {'E': e, 'S': s}\n\n"
            "def main():\n    print(suy_dien({'A': True, 'B': False}))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        err_fc = verify_candidate_semantics(buggy_fc, "Viết hàm suy_dien(facts: dict[str, bool]) -> dict[str, bool]")
        self.assertIn("KeyError", err_fc)

        # 5. Catches doctest/example mismatch, unfinished pass stub, and uncalled second function in main()
        mismatch_code = (
            "def gap_doi(x: int) -> int:\n    return x + 2\n\n"
            "def main():\n    print(gap_doi(2))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        err_ex = verify_candidate_semantics(mismatch_code, "Viết hàm gap_doi(x: int) -> int. Ví dụ: gap_doi(5) -> 10")
        self.assertIn("gap_doi(5)", err_ex)

        uncalled_second = (
            "def ham_mot(x):\n    return x + 1\n"
            "def ham_hai(x):\n    return x * 2\n\n"
            "def main():\n    print(ham_mot(3))\n\n"
            'if __name__ == "__main__":\n    main()\n'
        )
        err_uncalled = verify_candidate_semantics(
            uncalled_second,
            "Viết hàm ham_mot(x) và viết hàm ham_hai(x).",
        )
        self.assertIn("ham_hai", err_uncalled)

    def test_tricky_exam_offline_solvers_pdf_quotes_and_todo_starter_templates(self):
        # 1. Weighted graph UCS & A* with Word curly quotes “ ” and both tuple-list & nested-dict support
        p_ucs_astar = (
            'Bài 3.2: Tìm kiếm có trọng số trên đồ thị dict\n'
            'Cho graph = {“A”: [(“B”, 2), (“C”, 5)], “B”: [(“C”, 1), (“D”, 4)], “C”: [(“D”, 1)], “D”: []} '
            'và heuristic = {“A”: 4, “B”: 2, “C”: 1, “D”: 0}.\n'
            'Viết hàm ucs(graph, start, goal) và hàm a_star(graph, start, goal, h) trả về tuple (duong_di, chi_phi).'
        )
        r_w = process_request(p_ucs_astar, action_mode="instant")
        self.assertEqual(r_w.validation_status, "verified")
        nsw = {"__name__": "tw"}
        exec(compile(r_w.code, "<tw>", "exec"), nsw)
        g_nested = {"A": {"B": 2, "C": 5}, "B": {"C": 1, "D": 4}, "C": {"D": 1}, "D": {}}
        h_map = {"A": 4, "B": 2, "C": 1, "D": 0}
        self.assertEqual(nsw["ucs"](g_nested, "A", "D"), (["A", "B", "C", "D"], 4.0))
        self.assertEqual(nsw["a_star"](g_nested, "A", "D", h_map), (["A", "B", "C", "D"], 4.0))

        # 2. Pure-Python 8-Puzzle functions (1D & 2D board support)
        p_puz = (
            "Bài 3.1: Cài đặt heuristic và A* cho 8-puzzle\n"
            "Viết hàm so_o_sai(state, goal), hàm khoang_cach_manhattan(state, goal), "
            "hàm sinh_trang_thai_ke(state) và hàm giai_8_puzzle(start, goal)."
        )
        r_puz = process_request(p_puz, action_mode="instant")
        self.assertEqual(r_puz.validation_status, "verified")
        nsp = {"__name__": "tp"}
        exec(compile(r_puz.code, "<tp>", "exec"), nsp)
        s_board = ((1, 2, 3), (4, 0, 6), (7, 5, 8))
        g_board = ((1, 2, 3), (4, 5, 6), (7, 8, 0))
        self.assertEqual(nsp["so_o_sai"](s_board, g_board), 2)
        self.assertEqual(nsp["khoang_cach_manhattan"](s_board, g_board), 2)
        self.assertEqual(len(nsp["giai_8_puzzle"](s_board, g_board)) - 1, 2)

        # 3. Vietnamese text Jaccard & Levenshtein
        p_text = (
            "Bài 2.2: Xử lý chuỗi nâng cao\n"
            "Viết hàm khu_dau_tieng_viet(text), hàm do_tuong_dong_jaccard(s1, s2) và hàm khoang_cach_levenshtein(s1, s2)."
        )
        r_txt = process_request(p_text, action_mode="instant")
        self.assertEqual(r_txt.validation_status, "verified")
        nst = {"__name__": "tt"}
        exec(compile(r_txt.code, "<tt>", "exec"), nst)
        self.assertEqual(nst["khu_dau_tieng_viet"]("Đặng Trí Tuệ"), "Dang Tri Tue")
        self.assertEqual(nst["do_tuong_dong_jaccard"]("", ""), 0.0)
        self.assertEqual(nst["khoang_cach_levenshtein"]("kitten", "sitting"), 3)

        # 4. N-Queens conflict count & Hill Climbing
        p_nq = (
            "Bài 4.3: Bài toán N quân hậu\n"
            "Viết hàm dem_cap_tan_cong(state) đếm số cặp quân hậu tấn công nhau và hàm hill_climbing_n_queens(n)."
        )
        r_nq = process_request(p_nq, action_mode="instant")
        self.assertEqual(r_nq.validation_status, "verified")
        nsq = {"__name__": "tq"}
        exec(compile(r_nq.code, "<tq>", "exec"), nsq)
        self.assertEqual(nsq["dem_cap_tan_cong"]([1, 3, 0, 2]), 0)
        sol8 = nsq["hill_climbing_n_queens"](8)
        self.assertEqual(nsq["dem_cap_tan_cong"](sol8), 0)

        # 5. Entropy & Information Gain (ID3)
        p_ig = (
            "Bài 6.1: Cây quyết định ID3\n"
            "Viết hàm tinh_entropy(labels) và hàm information_gain(parent_labels, subsets)."
        )
        r_ig = process_request(p_ig, action_mode="instant")
        self.assertEqual(r_ig.validation_status, "verified")
        nsi = {"__name__": "ti"}
        exec(compile(r_ig.code, "<ti>", "exec"), nsi)
        self.assertEqual(nsi["tinh_entropy"]([]), 0.0)
        self.assertAlmostEqual(nsi["tinh_entropy"]([1, 1, 0, 0]), 1.0)
        self.assertAlmostEqual(nsi["information_gain"]([1, 1, 0, 0], [[1, 1], [0, 0]]), 1.0)

        # 6. Offline # TODO starter template completion on Alt+1 (< 0.05s)
        starter_41 = (
            '"""Bài 4.1: Cài đặt BFS và DFS trên đồ thị (dict)\n'
            'Viết hàm bfs(graph, start, goal) và hàm dfs(graph, start, goal)."""\n\n'
            "def bfs(graph, start, goal):\n    # TODO\n    pass\n\n"
            "def dfs(graph, start, goal):\n    # TODO\n    pass\n"
        )
        r_todo = process_request(starter_41, action_mode="instant")
        self.assertEqual(r_todo.validation_status, "verified")
        self.assertIn("deque", r_todo.code)

        # 7. DLS/IDS, Minimax/Alpha-Beta, AC-3/CSP, K-NN/Bayes, Fuzzy Centroid, Tower of Hanoi (< 0.05s each)
        extra_prompts = [
            ("Viết hàm dls(graph, start, goal, limit) và hàm ids(graph, start, goal, max_depth) trên dict.", "ids"),
            ("Viết hàm minimax(node, is_max, tree, scores) và hàm alpha_beta(node, is_max, tree, scores).", "alpha_beta"),
            ("Cho miền giá trị domains, viết hàm ac3(domains, neighbors) và hàm backtrack_csp(domains, neighbors).", "ac3"),
            ("Viết hàm khoang_cach_euclid(p1, p2), hàm knn_predict(train_data, query, k) và hàm dinh_ly_bayes(p_a, p_ba, p_bna).", "knn_predict"),
            ("Viết hàm hop_mo(a, b), hàm giao_mo(a, b) và hàm giai_mo_trong_tam(fuzzy_num).", "giai_mo_trong_tam"),
            ("Bài toán Tháp Hà Nội: viết hàm thap_ha_noi(n, coc_nguon, coc_dich, coc_trung_gian) bằng đệ quy.", "thap_ha_noi"),
        ]
        for prompt_text, expected_fn in extra_prompts:
            with self.subTest(expected_fn=expected_fn):
                res_ex = process_request(prompt_text, action_mode="instant")
                self.assertEqual(res_ex.validation_status, "verified")
                self.assertLess(res_ex.elapsed_sec, 0.25)
                ns_ex = {"__name__": "tex"}
                exec(compile(res_ex.code, "<tex>", "exec"), ns_ex)
                self.assertIn(expected_fn, ns_ex)

        # 8. Anti-lag Ollama thread cap & compact KV-cache options
        opts = brain_router._ollama_perf_options(1200)
        self.assertEqual(opts["num_ctx"], 2048)
        self.assertLessEqual(opts["num_thread"], 6)

    def test_school_pc_winget_fallback_and_msix_escape(self):
        import go_cai_dat

        # 1. When winget.exe is absent on school Windows LTSC/Education, falls back to direct HTTPS installer
        with patch.object(local_ai.shutil, "which", return_value=None), patch.object(
            local_ai, "_download_and_install_ollama_direct", return_value=Path("C:/Ollama/ollama.exe")
        ) as direct_dl:
            exe = local_ai._install_ollama()
        self.assertEqual(exe, Path("C:/Ollama/ollama.exe"))
        direct_dl.assert_called_once()

        # 2. MSIX Microsoft Store Python escapes AppData virtualization into ~/.pylance-helper/engine
        home = Path.home().resolve()
        with patch.object(go_cai_dat, "_is_msix_python", return_value=True), patch.dict(
            "os.environ", {"LOCALAPPDATA": str(home / "AppData" / "Local")}
        ):
            self.assertEqual(go_cai_dat.install_root(), home / ".pylance-helper" / "engine")

        # 3. `ollama pull` does NOT pass CREATE_NO_WINDOW so download % bar is visible in .bat console!
        import subprocess as _sp
        with patch.object(local_ai.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), patch.object(
            local_ai.subprocess, "run", return_value=_sp.CompletedProcess([], 0)
        ) as run_mock:
            local_ai._run(["C:/Ollama/ollama.exe", "pull", "qwen2.5-coder:1.5b"], timeout=30)
        self.assertEqual(run_mock.call_args.kwargs["creationflags"], 0)

    @unittest.skipUnless(sys.platform == "win32", "Batch installer tests run on Windows cmd.exe")
    def test_bat_files_in_parentheses_folder_and_wheel_fallback(self):
        import shutil
        import subprocess
        import tempfile
        import setup as setup_mod

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Verify venv-less wheel extraction fallback imports simpleai, kanren, and sympy cleanly
            rt = Path(tmp) / "runtime-fallback"
            setup_mod._extract_wheels_fallback(rt)
            site_pkgs = rt / "site_pkgs"
            self.assertTrue((site_pkgs / "simpleai").is_dir())
            chk = subprocess.run(
                [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(site_pkgs)!r}); import simpleai, kanren, sympy"],
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(chk.returncode, 0, chk.stderr)

            # 2. Verify double-click simulation inside folder containing spaces & (1) works with 0 batch syntax errors
            tricky_dir = Path(tmp) / "pylance-indent-helper-main (1)"
            (tricky_dir / "setup_lab").mkdir(parents=True)
            for bat_name in ("setup_ollama.bat", "setup_ollama_sieu_nhe.bat", "setup_nhanh.bat", "setup_phong_thi.bat"):
                shutil.copy2(repo_root / bat_name, tricky_dir / bat_name)
            shutil.copy2(repo_root / "setup_lab" / "run_python.bat", tricky_dir / "setup_lab" / "run_python.bat")

            # Unextracted-ZIP guard (when setup.py is absent)
            res_unextracted = subprocess.run(
                ["cmd.exe", "/c", str(tricky_dir / "setup_ollama.bat")],
                input="\r\n", capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(res_unextracted.returncode, 1)
            self.assertIn("giai nen", res_unextracted.stdout)

            # Extracted double-click simulation (both success exit 0 and failure exit 2)
            (tricky_dir / "setup.py").write_text(
                "import sys; print('ARGS:', sys.argv[1:]); sys.exit(0)\n", encoding="utf-8"
            )
            for bat_name in ("setup_ollama.bat", "setup_ollama_sieu_nhe.bat"):
                res_ok = subprocess.run(
                    ["cmd.exe", "/c", str(tricky_dir / bat_name)],
                    input="\r\n", capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(res_ok.returncode, 0, res_ok.stdout + res_ok.stderr)
                self.assertIn("[HOAN TAT 100%]", res_ok.stdout)
                self.assertNotIn("Cai dat bao loi", res_ok.stdout)

            (tricky_dir / "setup.py").write_text(
                "import sys; print('[LOI] Gia lap loi mang truong', file=sys.stderr); sys.exit(2)\n", encoding="utf-8"
            )
            res_err = subprocess.run(
                ["cmd.exe", "/c", str(tricky_dir / "setup_ollama.bat")],
                input="\r\n", capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(res_err.returncode, 2, res_err.stdout + res_err.stderr)
            self.assertIn("Cai dat bao loi (ma 2)", res_err.stdout)

    def test_ensure_ollama_keypair_ssh_keygen_and_pure_python(self):
        import os
        import shutil
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            # 1. Pure-Python Ed25519 OpenSSH keypair fallback when ssh-keygen is unavailable
            d_py = Path(tmp) / "ollama_pure"
            with patch.object(local_ai.shutil, "which", return_value=None), patch.dict(
                "os.environ", {"SystemRoot": str(Path(tmp) / "no_win")}
            ):
                repaired = local_ai._ensure_ollama_keypair([d_py])
            self.assertTrue(repaired)
            priv = d_py / "id_ed25519"
            pub = d_py / "id_ed25519.pub"
            self.assertTrue(priv.is_file())
            self.assertIn("BEGIN OPENSSH PRIVATE KEY", priv.read_text(encoding="ascii"))
            self.assertTrue(pub.read_text(encoding="ascii").startswith("ssh-ed25519 "))
            # Second call is idempotent (returns False)
            self.assertFalse(local_ai._ensure_ollama_keypair([d_py]))

            # Cross-verify pure-Python private key with real OpenSSH ssh-keygen -y if available!
            ssh_kg = shutil.which("ssh-keygen")
            if ssh_kg and sys.platform == "win32":
                user = os.environ.get("USERNAME", "")
                if user:
                    subprocess.run(
                        ["icacls", str(priv), "/inheritance:r", "/grant:r", f"{user}:F"],
                        capture_output=True, check=False,
                    )
                    derived = subprocess.check_output([ssh_kg, "-y", "-f", str(priv)], text=True).strip()
                    self.assertEqual(derived, pub.read_text(encoding="ascii").strip())

    def test_pull_resilient_falls_back_to_hf_and_scrub_removes_startmenu_folder_and_onedrive_icon(self):
        from unittest.mock import MagicMock

        # 1. When `ollama pull` exits non-zero / stalls twice with 0 bytes gained, automatically switches to HuggingFace GGUF!
        fake_proc = MagicMock()
        fake_proc.poll.return_value = 1
        fake_proc.returncode = 1
        with patch.object(local_ai.subprocess, "Popen", return_value=fake_proc), \
                patch.object(local_ai, "_ollama_blobs_total_bytes", return_value=120 * 1024 * 1024), \
                patch.object(local_ai, "_restart_ollama_daemon") as restart_daemon, \
                patch.object(local_ai, "_download_gguf_from_hf_and_create") as hf_dl:
            local_ai._pull_model_resilient(Path("C:/Ollama/ollama.exe"), "qwen2.5-coder:0.5b")
        hf_dl.assert_called_once_with(Path("C:/Ollama/ollama.exe"), "qwen2.5-coder:0.5b")
        restart_daemon.assert_called_once()

        # 2. _scrub_ollama_windows_traces deletes Start Menu\Programs\Ollama\ folder + OneDrive\Desktop\Ollama.lnk
        with tempfile.TemporaryDirectory() as tmp:
            roaming = Path(tmp) / "Roaming"
            onedrive = Path(tmp) / "OneDrive"
            sm_ollama_dir = roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Ollama"
            sm_ollama_dir.mkdir(parents=True)
            (sm_ollama_dir / "Ollama.lnk").write_text("lnk", encoding="utf-8")
            (onedrive / "Desktop").mkdir(parents=True)
            (onedrive / "Desktop" / "Ollama.lnk").write_text("lnk", encoding="utf-8")

            with patch.dict("os.environ", {"APPDATA": str(roaming), "OneDrive": str(onedrive), "USERPROFILE": tmp}), \
                    patch.object(Path, "home", return_value=Path(tmp)), \
                    patch.dict("sys.modules", {"winreg": None}):
                local_ai._scrub_ollama_windows_traces()

            self.assertFalse(sm_ollama_dir.exists())
            self.assertFalse((onedrive / "Desktop" / "Ollama.lnk").exists())


if __name__ == "__main__":
    unittest.main()
