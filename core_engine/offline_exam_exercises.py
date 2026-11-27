# -*- coding: utf-8 -*-
"""
Exact verified offline solvers for pure-Python exam exercises (Bai 1.x - Bai 6.x):
- Bai 2.1: vector_nguyen_am(text) & do_tuong_dong_cosine(v1, v2)
- Bai 4.1: bfs(graph, start, goal) & dfs(graph, start, goal) on dict adjacency lists
- Bai 4.2: suy_dien_tien(facts) & dem_rang_buoc_vi_pham(assignment, clauses)
"""

from __future__ import annotations

import ast
import re
import warnings
from typing import Any, Dict, List, Optional, Tuple

from .golden_skeletons import strip_accents


def _extract_named_dict_literal(text: str, var_name: str) -> Optional[Dict[Any, Any]]:
    pattern = re.compile(rf"\b{re.escape(var_name)}\s*=\s*\{{", re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return None
    brace_start = text.find("{", m.start())
    if brace_start == -1:
        return None
    depth = 0
    in_q: Optional[str] = None
    esc = False
    for idx in range(brace_start, len(text)):
        ch = text[idx]
        if in_q:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_q:
                in_q = None
            continue
        if ch in ("'", '"'):
            in_q = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = text[brace_start : idx + 1]
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", SyntaxWarning)
                        parsed = ast.literal_eval(snippet)
                    if isinstance(parsed, dict):
                        return parsed
                except (ValueError, SyntaxError):
                    return None
                break
    return None


def _extract_implication_rules(text: str) -> List[Tuple[List[str], str]]:
    """Extract Horn rules like `$C \\land A \\rightarrow Q$` or `C and A -> Q`."""
    rules: List[Tuple[List[str], str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip().strip("$").strip()
        if not line:
            continue
        normalized = (
            line.replace("\\land", "&")
            .replace("\\wedge", "&")
            .replace("∧", "&")
            .replace("\\rightarrow", "->")
            .replace("\\to", "->")
            .replace("→", "->")
            .replace("=>", "->")
        )
        # Skip prose explanation lines like `(A -> B tương đương (not A) or B)`
        if "(" in normalized or ")" in normalized or ":" in normalized:
            continue
        if "->" not in normalized:
            continue
        lhs, rhs = normalized.split("->", 1)
        head = rhs.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", head):
            continue
        premises = [p.strip() for p in re.split(r"\s*(?:&|\^|\band\b)\s*", lhs.strip()) if p.strip()]
        if premises and all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p) for p in premises):
            rules.append((premises, head))
    return rules


def parse_exam_coding_exercise(text: str) -> Optional[Dict[str, Any]]:
    """Recognize complete pure-Python coding exercises from the course exam bank."""
    folded = strip_accents(text).casefold()

    # 1. Bai 2.1: vector_nguyen_am & do_tuong_dong_cosine
    if (
        "vector_nguyen_am" in folded
        and "do_tuong_dong_cosine" in folded
        and "aeiou" in folded
    ):
        return {"type": "exam_vowel_cosine"}

    # 2. Bai 4.1: bfs(graph, start, goal) & dfs(graph, start, goal) on dict
    has_bfs_sig = bool(re.search(r"\bbfs\s*\(\s*graph\s*,\s*start\s*,\s*goal\s*\)", folded))
    has_dfs_sig = bool(re.search(r"\bdfs\s*\(\s*graph\s*,\s*start\s*,\s*goal\s*\)", folded))
    if (has_bfs_sig or has_dfs_sig) and "dict" in folded and "simpleai" not in folded:
        sample_graph = _extract_named_dict_literal(text, "graph")
        if sample_graph is not None and not all(
            isinstance(k, str) and isinstance(v, (list, tuple))
            for k, v in sample_graph.items()
        ):
            sample_graph = None
        return {
            "type": "exam_graph_dict_bfs_dfs",
            "include_bfs": has_bfs_sig or not has_dfs_sig,
            "include_dfs": has_dfs_sig or not has_bfs_sig,
            "graph": sample_graph or {
                "A": ["B", "C"],
                "B": ["D", "E"],
                "C": ["F"],
                "D": [],
                "E": ["F"],
                "F": [],
            },
        }

    # 3. Bai 4.2: suy_dien_tien(facts) & dem_rang_buoc_vi_pham(assignment, clauses)
    has_fc = "suy_dien_tien" in folded
    has_viol = "dem_rang_buoc_vi_pham" in folded
    if has_fc and has_viol:
        sample_facts = _extract_named_dict_literal(text, "facts")
        if sample_facts is not None and not all(
            isinstance(k, str) and isinstance(v, bool) for k, v in sample_facts.items()
        ):
            sample_facts = None
        rules = _extract_implication_rules(text)
        if not rules:
            rules = [
                (["C", "A"], "Q"),
                (["R", "I"], "H"),
                (["Q", "H", "D"], "E"),
                (["E"], "S"),
            ]
        return {
            "type": "exam_prop_logic_and_clauses",
            "facts": sample_facts or {"C": True, "A": True, "R": True, "I": False, "D": True},
            "rules": rules,
        }

    return None


def _solve_exam_vowel_cosine(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution, _fields

    _fields(problem, ("type",))
    code = '''from __future__ import annotations

import math


def vector_nguyen_am(text: str) -> list[int]:
    """Đếm tần suất xuất hiện của 5 nguyên âm 'a', 'e', 'i', 'o', 'u' (không phân biệt hoa/thường)."""
    lowered = text.lower()
    return [lowered.count(vowel) for vowel in "aeiou"]


def do_tuong_dong_cosine(v1: list[int], v2: list[int]) -> float:
    """Tính độ tương đồng Cosine giữa 2 vector cùng độ dài; trả về 0.0 nếu có vector chuẩn bằng 0."""
    if len(v1) != len(v2):
        raise ValueError("Hai vector phải có cùng độ dài.")
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(y * y for y in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    return float(dot_product / (norm1 * norm2))


def main() -> None:
    text_1 = "Artificial Intelligence and Machine Learning"
    text_2 = "Automated Reasoning in Computer Science"
    text_rong = "Rhythm myth"

    v1 = vector_nguyen_am(text_1)
    v2 = vector_nguyen_am(text_2)
    v0 = vector_nguyen_am(text_rong)

    print("Vector nguyên âm (a, e, i, o, u) của chuỗi 1:", v1)
    print("Vector nguyên âm (a, e, i, o, u) của chuỗi 2:", v2)
    print(f"Độ tương đồng Cosine(v1, v2): {do_tuong_dong_cosine(v1, v2):.6f}")
    print(f"Kiểm tra biên vector 0 (chuỗi không nguyên âm): {do_tuong_dong_cosine(v1, v0):.1f}")


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_vowel_cosine",
        code,
        "Đã cài đặt vector_nguyen_am(text) và do_tuong_dong_cosine(v1, v2) kèm xử lý biên chuẩn bằng 0.",
        ("Đếm đúng thứ tự 'a', 'e', 'i', 'o', 'u' và trả 0.0 khi một trong hai vector có chuẩn bằng 0.",),
    )


def _solve_exam_graph_dict_bfs_dfs(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution, _fields

    _fields(problem, ("type",), ("include_bfs", "include_dfs", "graph"))
    inc_bfs = bool(problem.get("include_bfs", True))
    inc_dfs = bool(problem.get("include_dfs", True))
    sample_graph = problem.get("graph") or {
        "A": ["B", "C"],
        "B": ["D", "E"],
        "C": ["F"],
        "D": [],
        "E": ["F"],
        "F": [],
    }
    nodes = list(sample_graph.keys())
    start_node = nodes[0] if nodes else "A"
    goal_node = nodes[-1] if len(nodes) >= 2 else start_node

    parts: List[str] = ["from __future__ import annotations\n"]
    if inc_bfs:
        parts.append("from collections import deque\n")

    if inc_bfs:
        parts.append(
            '''

def bfs(graph: dict, start, goal):
    """Tìm đường đi từ start đến goal bằng hàng đợi FIFO (BFS). Trả về list đường đi hoặc None."""
    if start == goal:
        return [start] if (start in graph or any(start in k for k in graph.values())) else [start]
    if start not in graph:
        return None

    queue = deque([(start, [start])])
    visited = {start}

    while queue:
        current, path = queue.popleft()
        for neighbor in graph.get(current, []):
            if neighbor == goal:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None'''
        )

    if inc_dfs:
        parts.append(
            '''

def dfs(graph: dict, start, goal):
    """Tìm đường đi từ start đến goal bằng ngăn xếp LIFO (DFS). Trả về list đường đi hoặc None."""
    if start == goal:
        return [start]
    if start not in graph:
        return None

    stack = [(start, [start])]
    visited = set()

    while stack:
        current, path = stack.pop()
        if current in visited:
            continue
        if current == goal:
            return path
        visited.add(current)
        # Đưa đỉnh kề vào ngăn xếp theo thứ tự ngược để lấy ra đúng thứ tự khai báo
        for neighbor in reversed(graph.get(current, [])):
            if neighbor not in visited:
                stack.append((neighbor, path + [neighbor]))
    return None'''
        )

    graph_src = repr(sample_graph)
    main_calls: List[str] = []
    if inc_bfs:
        main_calls.append(f'    print(f"Đường đi BFS ({start_node!r} -> {goal_node!r}):", bfs(graph, {start_node!r}, {goal_node!r}))')
    if inc_dfs:
        main_calls.append(f'    print(f"Đường đi DFS ({start_node!r} -> {goal_node!r}):", dfs(graph, {start_node!r}, {goal_node!r}))')

    parts.append(
        f"\n\n\ndef main() -> None:\n"
        f"    graph = {graph_src}\n"
        + "\n".join(main_calls)
        + "\n\n\nif __name__ == \"__main__\":\n    main()\n"
    )
    code = "".join(parts)
    return OfflineSolution(
        "exam_graph_dict_bfs_dfs",
        code,
        "Đã cài đặt BFS (FIFO deque) và DFS (LIFO stack) trên đồ thị từ điển.",
        ("Sử dụng tập visited chống chu trình, trả danh sách đỉnh từ start đến goal hoặc None.",),
    )


def _solve_exam_prop_logic_and_clauses(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution, _fields

    _fields(problem, ("type",), ("facts", "rules"))
    sample_facts = problem.get("facts") or {"C": True, "A": True, "R": True, "I": False, "D": True}
    raw_rules = problem.get("rules") or [
        (["C", "A"], "Q"),
        (["R", "I"], "H"),
        (["Q", "H", "D"], "E"),
        (["E"], "S"),
    ]
    rules_tuples = [(tuple(p), str(h)) for p, h in raw_rules]

    # Build CNF clauses corresponding to the implication rules for realistic demonstration in main():
    # (P1 ^ P2 -> H)  <=>  (~P1 v ~P2 v H)  <=>  [(P1, False), (P2, False), (H, True)]
    cnf_clauses = [
        [(p, False) for p in premises] + [(head, True)]
        for premises, head in rules_tuples
    ]

    code = f'''from __future__ import annotations

RULES: list[tuple[tuple[str, ...], str]] = {rules_tuples!r}


def suy_dien_tien(facts: dict[str, bool]) -> dict[str, bool]:
    """Suy diễn tiến (Forward Chaining) tìm giá trị các biến suy luận từ facts ban đầu."""
    ket_qua: dict[str, bool] = {{k: bool(v) for k, v in facts.items()}}
    for _, ket_luan in RULES:
        ket_qua.setdefault(ket_luan, False)

    thay_doi = True
    while thay_doi:
        thay_doi = False
        for tien_de, ket_luan in RULES:
            if not ket_qua[ket_luan] and all(ket_qua.get(bien, False) for bien in tien_de):
                ket_qua[ket_luan] = True
                thay_doi = True
    return ket_qua


def dem_rang_buoc_vi_pham(
    assignment: dict[str, bool],
    clauses: list[list[tuple[str, bool]]],
) -> int:
    """Đếm số mệnh đề tuyển (OR) không được thỏa mãn dưới phép gán assignment."""
    so_vi_pham = 0
    for clause in clauses:
        thoa_man = any(
            bien in assignment and bool(assignment[bien]) == bool(gia_tri_mong_muon)
            for bien, gia_tri_mong_muon in clause
        )
        if not thoa_man:
            so_vi_pham += 1
    return so_vi_pham


def main() -> None:
    facts = {sample_facts!r}
    ket_qua_suy_dien = suy_dien_tien(facts)
    print("Kết quả suy diễn tiến:", ket_qua_suy_dien)

    # Biểu diễn 4 luật kéo theo sang dạng mệnh đề tuyển CNF: (A ^ B -> Q) <=> (~A v ~B v Q)
    clauses: list[list[tuple[str, bool]]] = {cnf_clauses!r}
    print("Số mệnh đề vi phạm (với kết quả suy diễn hợp lệ):", dem_rang_buoc_vi_pham(ket_qua_suy_dien, clauses))

    # Thử một phép gán vi phạm luật C ^ A -> Q (C=True, A=True nhưng Q=False)
    gan_sai = {{**ket_qua_suy_dien, "Q": False}}
    print("Số mệnh đề vi phạm (khi gán sai Q=False):", dem_rang_buoc_vi_pham(gan_sai, clauses))


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_prop_logic_and_clauses",
        code,
        "Đã cài đặt suy_dien_tien(facts) và dem_rang_buoc_vi_pham(assignment, clauses).",
        ("Suy diễn điểm bất động Modus Ponens và kiểm tra từng mệnh đề tuyển (ten_bien, can_gia_tri_dung).",),
    )


EXAM_CODING_SOLVERS = {
    "exam_vowel_cosine": _solve_exam_vowel_cosine,
    "exam_graph_dict_bfs_dfs": _solve_exam_graph_dict_bfs_dfs,
    "exam_prop_logic_and_clauses": _solve_exam_prop_logic_and_clauses,
}
