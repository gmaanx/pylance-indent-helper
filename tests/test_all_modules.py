# -*- coding: utf-8 -*-
"""
Bo kiem thu toan dien he thong `midtermtool`:
1. Chay thu ngam (Shadow Execution) TOAN BO 27 Phoi Vang trong `golden_skeletons` (dam bao 100% returncode == 0).
2. Kiem thu luong Copy-Paste thang de thi vao comment `# ...` (Natural Language + Parameter Injector).
3. Kiem thu 4 bay Static AST Auto-Healer cua SimpleAI (`unhashable list`, `CSP constraint signature`, `missing super().__init__`, `graph_search=True`).
4. Kiem thu Stealth Config (`# @cfg`) va CLI JSON Entrypoint (`cli_entry.py`).
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core_engine.config_manager import CONFIG, deobfuscate_str, obfuscate_str  # noqa: E402
from core_engine.engine_pipeline import process_request  # noqa: E402
from core_engine.golden_skeletons import ALL_SKELETONS  # noqa: E402
from core_engine.shadow_runner_healer import shadow_execute, static_auto_heal  # noqa: E402


def test_all_golden_skeletons_execute() -> None:
    print(f"=== 1. KIEM THU CHAY THUC TE {len(ALL_SKELETONS)} PHOI VANG ===")
    for sid, item in ALL_SKELETONS.items():
        res = shadow_execute(item["code"], timeout=4.0)
        assert res.ok, f"[FAIL] Skeleton {sid} failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        print(f"  [OK] {sid:<30} | {res.elapsed_sec*1000:6.1f} ms | {res.summary}")


def test_copy_paste_exam_comments() -> None:
    print("\n=== 2. KIEM THU COPY-PASTE DE THI THANG VAO COMMENT (#) ===")
    exam_prompts = [
        (
            "# Cho bai toan 8-puzzle voi trang thai ban dau ((1, 2, 3), (4, 0, 6), (7, 5, 8)) "
            "va trang thai dich ((1, 2, 3), (4, 5, 6), (7, 8, 0)). Giai bang thuat toan A* voi h1 va h2.",
            "search_8puzzle_astar",
            "(4, 0, 6)",
        ),
        (
            "# Bai toan 8 quan hau tren ban co 8x8. Su dung tim kiem cuc bo (Hill climbing, Simulated annealing, Genetic) cua SimpleAI.",
            "local_nqueens",
            "N = 8",
        ),
        (
            "# Giai bai toan 6 quan hau bang CSP Backtrack (MOST_CONSTRAINED_VARIABLE, LEAST_CONSTRAINING_VALUE) ket hop Local Search.",
            "csp_nqueens_hybrid",
            "N = 6",
        ),
        (
            "# Bai toan sinh xau 'HELLO' tu xau rong bang thu vien simpleai.",
            "search_string_gen",
            "GOAL = 'HELLO'",
        ),
        (
            "# Cai dat chay class Nut, ham gamma, fringe cho cac thuat toan BFS, UCS, DFS, DLS, IDS tim duong tu Oradea den Eforie.",
            "raw_graph_search",
            'bat_dau, dich = "Oradea", {"Eforie"}',
        ),
        (
            "# Dung thu vien miniKanren (lall, eq, membero) giai bai toan 4 nguoi Steve, Matthew, Jack, Alfred ai la nguoi nuoi tho (rabbit).",
            "kanren_zebra_puzzle",
            "rabbit",
        ),
        (
            "# Dung miniKanren (Relation, facts, conde) bieu dien cay gia pha family: father, mother, parent, grandparent, sibling, uncle.",
            "kanren_family",
            "def grandparent",
        ),
        (
            "# Kiem tra so nguyen to trong danh sach va in 7 so nguyen to dau tien bang miniKanren va sympy (check_prime).",
            "kanren_prime",
            "def check_prime",
        ),
        (
            "# Giai mat ma chu so TWO + TWO = FOUR bang CspProblem va backtrack cua SimpleAI.",
            "csp_cryptarithmetic",
            "TU_1 = 'TWO'",
        ),
        (
            "# Cai dat thuat toan Minimax va Cat tia Alpha-Beta (Alpha-Beta Pruning) tren cay tro choi.",
            "game_minimax_alphabeta_tree",
            "def alpha_beta",
        ),
        (
            "# Bai toan may hut bui trang thai don bat dau o trang thai #5. Tim chuoi hanh dong lam sach.",
            "search_vacuum_world",
            "MayHutBuiProblem",
        ),
        (
            "# Bai toan may hut bui thieu cam nhan (sensorless) bat dau o tap trang thai {#1,#2,#3,#4,#5,#6,#7,#8}.",
            "search_sensorless_vacuum",
            "MayHutBuiThieuCamNhan",
        ),
        (
            "# Tim kiem leo doi (hill climbing) cho bai toan o chu 8-puzzle voi f(n) = -(so luong cac o chu nam sai vi tri).",
            "local_8puzzle_hill_climbing",
            "PuzzleLocalProblem",
        ),
        (
            "# Bai toan thoa man rang buoc: cac bien x1..x6 mien gia tri {0,1}, rang buoc x1+x2+x6=1, x1-x3+x4=1.",
            "csp_numeric_equations",
            "convert_to_binary",
        ),
        (
            "# Giai thuat phu hop canh AC-3 (arc_consistency_3, revise) tren do thi rang buoc to mau ban do.",
            "csp_convert_to_binary_ac3",
            "arc_consistency_3",
        ),
        (
            "# Bai toan mat ma so hoc TWO + TWO = FOUR voi cac bien nho X1, X2, X3.",
            "csp_two_plus_two_carry",
            "X1",
        ),
        (
            "# Chung minh dua tren bang chan ly (Truth-table) KB |= alpha.",
            "logic_truth_table",
            "kiem_tra_bang_chan_ly",
        ),
        (
            "# Chung minh bang hop giai phan chung (Resolution refutation) chuyen KB ve dang chuan CNF.",
            "logic_cnf_resolution",
            "chung_minh_hop_giai",
        ),
        (
            "# Bai toan chung minh thoa man SAT o dang chuan ket hop CNF giai bang Backtracking va Walk-SAT.",
            "logic_sat_csp_local",
            "SATLocalProblem",
        ),
        (
            "# Phan lop du lieu bang cay quyet dinh ID3 (DecisionTreeLearner) va KNearestNeighbors trong simpleai.machine_learning.",
            "ml_classifiers_simpleai",
            "DecisionTreeLearner",
        ),
        (
            "# Hoc tang cuong Q-Learning (TDQLearner, RLEnvironment) trong simpleai.machine_learning.reinforcement_learning.",
            "ml_reinforcement_simpleai",
            "TDQLearner",
        ),
    ]

    for prompt, expected_sid, expected_snippet in exam_prompts:
        resp = process_request(prompt, action_mode="instant", verify_shadow=True)
        assert resp.verified_ok, f"[FAIL] Prompt failed verification: {prompt}\nErr: {resp.error_detail}"
        assert expected_sid in resp.tier_used, f"[FAIL] Expected {expected_sid}, got {resp.tier_used}"
        assert expected_snippet in resp.code, f"[FAIL] Expected '{expected_snippet}' in generated code for {expected_sid}"
        print(f"  [OK] Copy-Paste -> {resp.tier_used:<38} | Verified in {resp.elapsed_sec*1000:5.1f} ms")


def test_static_ast_auto_healer_traps() -> None:
    print("\n=== 3. KIEM THU 4 BAY STATIC AST AUTO-HEALER CUA SIMPLEAI ===")

    # Trap 1 + 3 + 4: INITIAL is a list, missing super().__init__, result returns a list, astar missing graph_search=True
    buggy_search_code = """
from simpleai.search import SearchProblem, astar

INITIAL = [1, 0, 2]
GOAL = (0, 1, 2)

class MiniPuzzle(SearchProblem):
    def __init__(self, initial_state):
        self.dem = 0

    def actions(self, state):
        idx = state.index(0)
        acts = []
        if idx > 0:
            acts.append(idx - 1)
        if idx < 2:
            acts.append(idx + 1)
        return acts

    def result(self, state, action):
        idx = state.index(0)
        lst = list(state)
        lst[idx], lst[action] = lst[action], lst[idx]
        return [x for x in lst]

    def is_goal(self, state):
        return state == GOAL

    def heuristic(self, state):
        return 0

if __name__ == '__main__':
    prob = MiniPuzzle(INITIAL)
    kq = astar(prob)
    print("Cost:", kq.cost)
"""
    healed_1 = static_auto_heal(buggy_search_code)
    assert "super().__init__(initial_state)" in healed_1
    assert "graph_search=True" in healed_1
    assert "_to_hashable" in healed_1
    run_1 = shadow_execute(healed_1)
    assert run_1.ok, f"Trap 1/3/4 heal failed: {run_1.stderr}"
    print(f"  [OK] Bay 1 (list -> tuple), Bay 3 (super().__init__), Bay 4 (graph_search=True) -> {run_1.summary}")

    # Trap 2: Wrong CSP constraint signature def khac_nhau(a, b):
    buggy_csp_code = """
from simpleai.search import CspProblem, backtrack

VARIABLES = ('A', 'B', 'C')
DOMAINS = {v: [1, 2, 3] for v in VARIABLES}

def khac_nhau(a, b):
    return a != b

CONSTRAINTS = [
    (('A', 'B'), khac_nhau),
    (('B', 'C'), khac_nhau),
    (('A', 'C'), khac_nhau),
]

if __name__ == '__main__':
    prob = CspProblem(VARIABLES, DOMAINS, CONSTRAINTS)
    kq = backtrack(prob)
    print("CSP:", kq)
"""
    resp_fix = process_request(buggy_csp_code, action_mode="self_fix")
    assert resp_fix.verified_ok, f"Trap 2 CSP heal failed: {resp_fix.error_detail}"
    print(f"  [OK] Bay 2 (CSP constraint def f(a, b) -> def f(variables, values)) -> {resp_fix.stdout_preview}")


def test_stealth_config_and_cli() -> None:
    print("\n=== 4. KIEM THU MA HOA API KEY & CLI ENTRYPOINT ===")
    sample_key = "AIzaSyTestKey_UEH_2026_Stealth"
    enc = obfuscate_str(sample_key)
    assert sample_key not in enc
    assert deobfuscate_str(enc) == sample_key
    print("  [OK] XOR + Base64 API Key obfuscation verified")

    # Test CLI entrypoint via subprocess
    py_exe = Path(sys.executable)
    cli_path = ROOT_DIR / "core_engine" / "cli_entry.py"
    payload = json.dumps({
        "text": "# @search bai:dong_nuoc binh:3,5,8 dau:0,0,8 dich:4",
        "mode": "instant",
        "verify": True,
    })
    proc = subprocess.run(
        [str(py_exe), str(cli_path), "--mode", "instant"],
        input=payload,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5.0,
    )
    assert proc.returncode == 0, f"CLI Entrypoint failed: {proc.stderr}"
    data = json.loads(proc.stdout)
    assert data["verified_ok"] is True
    assert "DongNuocProblem" in data["code"]
    print(f"  [OK] CLI Entrypoint JSON response verified ({data['elapsed_sec']}s)")


def test_triple_quotes_across_all_alt_modes() -> None:
    print('\n=== 5. KIEM THU """ YEU CAU """ TREN CA 4 PHIM ALT+1 / ALT+2 / ALT+3 / ALT+4 ===')
    triple_prompt = (
        '"""\n'
        "Cho bài toán đong nước 3 bình (3, 5, 8), trạng thái đầu (0, 0, 8), đích cần đong được 4 lít.\n"
        '"""'
    )
    for mode, expected_header in (
        ("instant", "# [Alt+1 OK"),
        ("full", "# [Alt+2 OK"),
        ("ghost", "# [Alt+3 OK"),
        ("self_fix", "# [Alt+4 OK"),
    ):
        res = process_request(triple_prompt, action_mode=mode, verify_shadow=True)
        assert res.verified_ok, f"Failed triple-quote on {mode}: {res.error_detail}"
        first_line = res.code.splitlines()[0]
        last_line = res.code.splitlines()[-1]
        assert first_line.startswith(expected_header), f"Expected {expected_header}, got {first_line}"
        assert "DongNuocProblem" in res.code
        print(f"  [OK] {mode:<10} -> {first_line} | {last_line}")


if __name__ == "__main__":
    test_all_golden_skeletons_execute()
    test_copy_paste_exam_comments()
    test_static_ast_auto_healer_traps()
    test_stealth_config_and_cli()
    test_triple_quotes_across_all_alt_modes()
    print("\n>>> TAT CA KIEM THU HOAN TAT 100% (0 LOI)! <<<")
