# -*- coding: utf-8 -*-
"""
Exact verified offline solvers for pure-Python exam exercises (Bai 1.x - Bai 6.x):
- Bai 2.1: vector_nguyen_am(text) & do_tuong_dong_cosine(v1, v2)
- Bai 2.2: khu_dau_tieng_viet(text), do_tuong_dong_jaccard(s1, s2), khoang_cach_levenshtein(s1, s2)
- Bai 3.1: 8-Puzzle pure Python heuristics & A* (so_o_sai, khoang_cach_manhattan, sinh_trang_thai_ke, giai_8_puzzle)
- Bai 3.2: Weighted graph dict UCS / Greedy / A* (ucs, greedy, a_star / astar)
- Bai 4.1: bfs(graph, start, goal) & dfs(graph, start, goal) on dict adjacency lists
- Bai 4.2: suy_dien_tien(facts) & dem_rang_buoc_vi_pham(assignment, clauses)
- Bai 4.3: N-Queens conflict counter & Hill Climbing (dem_cap_tan_cong / so_cap_tan_cong + hill_climbing)
- Bai 6.1: Decision Tree ID3 Entropy & Information Gain (tinh_entropy / entropy + information_gain)
"""

from __future__ import annotations

import ast
import re
import warnings
from typing import Any, Dict, List, Optional, Tuple

from .golden_skeletons import strip_accents

_SMART_TRANSLATION = str.maketrans(
    {
        "“": '"',
        "”": '"',
        "„": '"',
        "‘": "'",
        "’": "'",
        "‚": "'",
        "−": "-",
        "–": "-",
        "\u00a0": " ",
        "\u200b": "",
    }
)


def normalize_pdf_code_artifacts(text: str) -> str:
    """Normalize Word/PDF curly quotes, Unicode minus signs, and zero-width spaces."""
    return text.translate(_SMART_TRANSLATION)


def _extract_named_literal(text: str, var_names: Tuple[str, ...], open_ch: str, close_ch: str) -> Optional[Any]:
    cleaned = normalize_pdf_code_artifacts(text)
    for var_name in var_names:
        pattern = re.compile(rf"\b{re.escape(var_name)}\s*(?::[^=\n]+)?=\s*\{re.escape(open_ch)}", re.IGNORECASE)
        m = pattern.search(cleaned)
        if not m:
            continue
        start_idx = cleaned.rfind(open_ch, m.start(), m.end())
        if start_idx == -1:
            continue
        depth = 0
        in_q: Optional[str] = None
        esc = False
        for idx in range(start_idx, len(cleaned)):
            ch = cleaned[idx]
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
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    snippet = cleaned[start_idx : idx + 1]
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", SyntaxWarning)
                            return ast.literal_eval(snippet)
                    except (ValueError, SyntaxError):
                        break
    return None


def _extract_named_dict_literal(text: str, var_name: str) -> Optional[Dict[Any, Any]]:
    val = _extract_named_literal(text, (var_name,), "{", "}")
    return val if isinstance(val, dict) else None


def _extract_implication_rules(text: str) -> List[Tuple[List[str], str]]:
    """Extract Horn rules like `$C \\land A \\rightarrow Q$` or `C and A -> Q`."""
    rules: List[Tuple[List[str], str]] = []
    cleaned = normalize_pdf_code_artifacts(text)
    for raw_line in cleaned.splitlines():
        line = raw_line.strip().lstrip("-•*").strip().strip("$").strip()
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
        normalized = re.sub(r"^R\d+\s*:\s*", "", normalized, flags=re.IGNORECASE)
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


def _find_requested_func_name(folded: str, candidates: Tuple[str, ...]) -> Optional[str]:
    for name in candidates:
        if re.search(rf"\b{re.escape(name)}\s*\(", folded):
            return name
    return None


def parse_exam_coding_exercise(text: str) -> Optional[Dict[str, Any]]:
    """Recognize complete pure-Python coding exercises from the course exam bank."""
    cleaned = normalize_pdf_code_artifacts(text)
    folded = strip_accents(cleaned).casefold()
    if "simpleai" in folded or "kanren" in folded:
        return None

    # 1. Bai 2.1: vector_nguyen_am & do_tuong_dong_cosine
    if "vector_nguyen_am" in folded and "do_tuong_dong_cosine" in folded and "aeiou" in folded:
        return {"type": "exam_vowel_cosine"}

    # 2. Bai 2.2: Jaccard & Levenshtein (& optional khu_dau)
    jaccard_fn = _find_requested_func_name(folded, ("do_tuong_dong_jaccard", "jaccard_similarity", "tinh_jaccard"))
    lev_fn = _find_requested_func_name(folded, ("khoang_cach_levenshtein", "levenshtein_distance", "edit_distance", "levenshtein"))
    khu_dau_fn = _find_requested_func_name(folded, ("khu_dau_tieng_viet", "khu_dau", "bo_dau_tieng_viet"))
    if jaccard_fn or lev_fn:
        empty_both_one = bool(re.search(r"hai\s+tap\s+rong.*?1\.0|ca\s+hai\s+rong.*?1\.0", folded))
        return {
            "type": "exam_text_jaccard_levenshtein",
            "jaccard_fn": jaccard_fn,
            "lev_fn": lev_fn,
            "khu_dau_fn": khu_dau_fn,
            "empty_both_one": empty_both_one,
        }

    # 3. Bai 4.1: bfs(graph, start, goal) & dfs(graph, start, goal) on unweighted dict
    has_bfs_sig = bool(re.search(r"\bbfs\s*\(\s*graph\s*,\s*start\s*,\s*goal\b", folded))
    has_dfs_sig = bool(re.search(r"\bdfs\s*\(\s*graph\s*,\s*start\s*,\s*goal\b", folded))
    ucs_fn = _find_requested_func_name(folded, ("ucs", "uniform_cost_search"))
    astar_fn = _find_requested_func_name(folded, ("a_star", "astar", "a_sao"))
    greedy_fn = _find_requested_func_name(folded, ("greedy", "greedy_best_first", "best_first_search"))

    if (has_bfs_sig or has_dfs_sig) and "dict" in folded and not (ucs_fn or astar_fn or greedy_fn):
        sample_graph = _extract_named_dict_literal(cleaned, "graph")
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

    # 4. Bai 3.2: Weighted graph dict UCS / Greedy / A*
    if (ucs_fn or astar_fn or greedy_fn) and "graph" in folded and "start" in folded and "goal" in folded:
        sample_graph = _extract_named_dict_literal(cleaned, "graph")
        sample_h = _extract_named_literal(cleaned, ("h", "heuristic", "heuristics"), "{", "}")
        if not isinstance(sample_h, dict):
            sample_h = None
        returns_tuple = bool(
            re.search(r"tuple\s*\[|\(\s*(?:duong_di|path)\s*,\s*(?:chi_phi|cost|tong_chi_phi)\s*\)|tra\s+ve\s+duong\s+di\s+va\s+(?:tong\s+)?chi\s+phi", folded)
        )
        return {
            "type": "exam_weighted_graph_ucs_astar",
            "ucs_fn": ucs_fn,
            "astar_fn": astar_fn,
            "greedy_fn": greedy_fn,
            "returns_tuple": returns_tuple,
            "graph": sample_graph,
            "heuristic": sample_h,
        }

    # 5. Bai 3.1: Pure-Python 8-Puzzle heuristics & solver
    misplaced_fn = _find_requested_func_name(folded, ("so_o_sai", "dem_so_o_sai", "misplaced_tiles", "h1"))
    manhattan_fn = _find_requested_func_name(folded, ("khoang_cach_manhattan", "tinh_manhattan", "manhattan_distance", "manhattan", "h2"))
    neighbors_fn = _find_requested_func_name(folded, ("sinh_trang_thai_ke", "trang_thai_ke", "get_neighbors"))
    solve_puz_fn = _find_requested_func_name(folded, ("giai_8_puzzle", "astar_8_puzzle", "solve_8_puzzle"))
    if ("8-puzzle" in folded or "8 puzzle" in folded or "8_puzzle" in folded) and (misplaced_fn or manhattan_fn):
        return {
            "type": "exam_puzzle_pure_functions",
            "misplaced_fn": misplaced_fn,
            "manhattan_fn": manhattan_fn,
            "neighbors_fn": neighbors_fn,
            "solve_puz_fn": solve_puz_fn,
        }

    # 6. Bai 4.2: suy_dien_tien(facts) & dem_rang_buoc_vi_pham(assignment, clauses)
    if "suy_dien_tien" in folded and "dem_rang_buoc_vi_pham" in folded:
        sample_facts = _extract_named_dict_literal(cleaned, "facts")
        if sample_facts is not None and not all(
            isinstance(k, str) and isinstance(v, bool) for k, v in sample_facts.items()
        ):
            sample_facts = None
        rules = _extract_implication_rules(cleaned)
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

    # 7. Bai 4.3: N-Queens conflict count & Hill Climbing
    conflict_fn = _find_requested_func_name(
        folded,
        ("dem_cap_tan_cong", "so_cap_tan_cong", "so_cap_hau_tan_cong", "dem_xung_dot", "conflict_count", "attacking_pairs"),
    )
    hc_fn = _find_requested_func_name(
        folded,
        ("hill_climbing_n_queens", "hill_climbing", "leo_doi_n_hau", "leo_doi"),
    )
    if conflict_fn and ("hau" in folded or "queen" in folded):
        return {
            "type": "exam_nqueens_conflicts",
            "conflict_fn": conflict_fn,
            "hc_fn": hc_fn,
        }

    # 8. Bai 6.1: Entropy & Information Gain (ID3)
    entropy_fn = _find_requested_func_name(folded, ("tinh_entropy", "entropy"))
    ig_fn = _find_requested_func_name(folded, ("information_gain", "tinh_information_gain", "do_loi_thong_tin"))
    if entropy_fn and ig_fn:
        return {
            "type": "exam_entropy_ig",
            "entropy_fn": entropy_fn,
            "ig_fn": ig_fn,
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


def _solve_exam_text_jaccard_levenshtein(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    jaccard_fn = problem.get("jaccard_fn")
    lev_fn = problem.get("lev_fn")
    khu_dau_fn = problem.get("khu_dau_fn")
    empty_val = "1.0" if problem.get("empty_both_one") else "0.0"

    parts = ["from __future__ import annotations\n\nimport re\nimport unicodedata\n"]
    kd_helper = khu_dau_fn or "_khu_dau"
    parts.append(
        f'''

def {kd_helper}(text: str) -> str:
    """Khử dấu tiếng Việt và chuẩn hóa chữ thường."""
    nfd = unicodedata.normalize("NFD", text)
    khong_dau = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return khong_dau.replace("đ", "d").replace("Đ", "D")
'''
    )
    main_lines = [
        '    s1 = "Trí tuệ nhân tạo và học máy"',
        '    s2 = "Tri tue nhan tao ung dung"',
    ]
    if khu_dau_fn:
        main_lines.append(f'    print("Khử dấu:", {khu_dau_fn}(s1))')

    if jaccard_fn:
        parts.append(
            f'''

def {jaccard_fn}(s1: str, s2: str) -> float:
    """Tính độ tương đồng Jaccard giữa tập từ của hai chuỗi văn bản."""
    w1 = set(re.findall(r"[a-z0-9]+", {kd_helper}(s1).lower()))
    w2 = set(re.findall(r"[a-z0-9]+", {kd_helper}(s2).lower()))
    hop = w1 | w2
    if not hop:
        return {empty_val}
    return float(len(w1 & w2) / len(hop))
'''
        )
        main_lines.append(f'    print(f"Độ tương đồng Jaccard: {{{jaccard_fn}(s1, s2):.6f}}")')

    if lev_fn:
        parts.append(
            f'''

def {lev_fn}(s1: str, s2: str) -> int:
    """Tính khoảng cách chỉnh sửa Levenshtein tối thiểu giữa hai chuỗi bằng quy hoạch động."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, start=1):
        curr = [i]
        for j, c2 in enumerate(s2, start=1):
            cost = 0 if c1 == c2 else 1
            curr.append(min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]
'''
        )
        main_lines.append(f'    print("Khoảng cách Levenshtein:", {lev_fn}("kitten", "sitting"))')

    parts.append("\n\ndef main() -> None:\n" + "\n".join(main_lines) + '\n\n\nif __name__ == "__main__":\n    main()\n')
    return OfflineSolution(
        "exam_text_jaccard_levenshtein",
        "".join(parts),
        "Đã cài đặt các hàm xử lý văn bản, Jaccard và/hoặc khoảng cách Levenshtein.",
        ("Xử lý an toàn chuỗi rỗng và dấu tiếng Việt.",),
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
    if start not in graph and not any(start in v for v in graph.values()):
        return None
    if start == goal:
        return [start]

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
    if start not in graph and not any(start in v for v in graph.values()):
        return None
    if start == goal:
        return [start]

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
        + '\n\n\nif __name__ == "__main__":\n    main()\n'
    )
    return OfflineSolution(
        "exam_graph_dict_bfs_dfs",
        "".join(parts),
        "Đã cài đặt BFS (FIFO deque) và DFS (LIFO stack) trên đồ thị từ điển.",
        ("Sử dụng tập visited chống chu trình và graph.get() an toàn với đỉnh lá.",),
    )


def _solve_exam_weighted_graph_ucs_astar(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    ucs_fn = problem.get("ucs_fn")
    astar_fn = problem.get("astar_fn")
    greedy_fn = problem.get("greedy_fn")
    ret_tuple = bool(problem.get("returns_tuple"))
    sample_graph = problem.get("graph") or {
        "A": [("B", 2), ("C", 5)],
        "B": [("D", 4), ("E", 1)],
        "C": [("F", 2)],
        "D": [],
        "E": [("F", 3)],
        "F": [],
    }
    sample_h = problem.get("heuristic") or {"A": 6, "B": 4, "C": 2, "D": 6, "E": 3, "F": 0}
    nodes = list(sample_graph.keys())
    start_node = nodes[0] if nodes else "A"
    goal_node = nodes[-1] if len(nodes) >= 2 else start_node

    ret_found = "(path, cost)" if ret_tuple else "path"
    ret_none = "(None, float('inf'))" if ret_tuple else "None"

    parts = [
        '''from __future__ import annotations

import heapq
from itertools import count


def _iter_weighted_neighbors(graph: dict, node):
    """Hỗ trợ cả 2 dạng biểu diễn dict trọng số: {'A': [('B', 2)]} và {'A': {'B': 2}}."""
    raw = graph.get(node, [])
    if isinstance(raw, dict):
        for nb, w in raw.items():
            yield nb, float(w)
    else:
        for item in raw:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                yield item[0], float(item[1])
            else:
                yield item, 1.0
'''
    ]

    main_calls = []
    if ucs_fn:
        parts.append(
            f'''

def {ucs_fn}(graph: dict, start, goal):
    """Tìm đường đi chi phí cực tiểu bằng Uniform Cost Search (UCS)."""
    counter = count()
    frontier = [(0.0, next(counter), start, [start])]
    best_g = {{start: 0.0}}

    while frontier:
        cost, _, current, path = heapq.heappop(frontier)
        if cost > best_g.get(current, float("inf")):
            continue
        if current == goal:
            return {ret_found}
        for neighbor, weight in _iter_weighted_neighbors(graph, current):
            new_cost = cost + weight
            if new_cost < best_g.get(neighbor, float("inf")):
                best_g[neighbor] = new_cost
                heapq.heappush(frontier, (new_cost, next(counter), neighbor, path + [neighbor]))
    return {ret_none}
'''
        )
        main_calls.append(f'    print("Kết quả UCS:", {ucs_fn}(graph, {start_node!r}, {goal_node!r}))')

    if greedy_fn:
        parts.append(
            f'''

def {greedy_fn}(graph: dict, start, goal, h: dict):
    """Tìm kiếm tham lam theo lựa chọn tốt nhất (Greedy Best-First Search)."""
    counter = count()
    frontier = [(float(h.get(start, 0.0)), next(counter), 0.0, start, [start])]
    visited = set()

    while frontier:
        _, _, cost, current, path = heapq.heappop(frontier)
        if current in visited:
            continue
        if current == goal:
            return {ret_found}
        visited.add(current)
        for neighbor, weight in _iter_weighted_neighbors(graph, current):
            if neighbor not in visited:
                heapq.heappush(
                    frontier,
                    (float(h.get(neighbor, 0.0)), next(counter), cost + weight, neighbor, path + [neighbor]),
                )
    return {ret_none}
'''
        )
        main_calls.append(f'    print("Kết quả Greedy:", {greedy_fn}(graph, {start_node!r}, {goal_node!r}, h))')

    if astar_fn:
        parts.append(
            f'''

def {astar_fn}(graph: dict, start, goal, h: dict):
    """Tìm đường tối ưu bằng thuật toán A* với f(n) = g(n) + h(n)."""
    counter = count()
    frontier = [(float(h.get(start, 0.0)), next(counter), 0.0, start, [start])]
    best_g = {{start: 0.0}}

    while frontier:
        _, _, cost, current, path = heapq.heappop(frontier)
        if cost > best_g.get(current, float("inf")):
            continue
        if current == goal:
            return {ret_found}
        for neighbor, weight in _iter_weighted_neighbors(graph, current):
            new_g = cost + weight
            if new_g < best_g.get(neighbor, float("inf")):
                best_g[neighbor] = new_g
                f_val = new_g + float(h.get(neighbor, 0.0))
                heapq.heappush(frontier, (f_val, next(counter), new_g, neighbor, path + [neighbor]))
    return {ret_none}
'''
        )
        main_calls.append(f'    print("Kết quả A*:", {astar_fn}(graph, {start_node!r}, {goal_node!r}, h))')

    parts.append(
        f"\n\ndef main() -> None:\n"
        f"    graph = {sample_graph!r}\n"
        f"    h = {sample_h!r}\n"
        + "\n".join(main_calls)
        + '\n\n\nif __name__ == "__main__":\n    main()\n'
    )
    return OfflineSolution(
        "exam_weighted_graph_ucs_astar",
        "".join(parts),
        "Đã cài đặt tìm kiếm có trọng số / heuristic (UCS, Greedy, A*) trên đồ thị từ điển.",
        ("Hỗ trợ đồng thời cả biểu diễn danh sách kề có trọng số và từ điển lồng nhau.",),
    )


def _solve_exam_puzzle_pure_functions(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    misplaced_fn = problem.get("misplaced_fn")
    manhattan_fn = problem.get("manhattan_fn")
    neighbors_fn = problem.get("neighbors_fn")
    solve_puz_fn = problem.get("solve_puz_fn")

    parts = [
        '''from __future__ import annotations

import heapq
from itertools import count


def _flatten_board(board) -> tuple[int, ...]:
    """Chuẩn hóa bảng 8-puzzle (1D hoặc ma trận 3x3) về tuple 9 phần tử."""
    if len(board) == 3 and isinstance(board[0], (list, tuple)):
        return tuple(int(cell) for row in board for cell in row)
    return tuple(int(x) for x in board)
'''
    ]
    main_calls = [
        "    start = ((1, 2, 3), (4, 0, 6), (7, 5, 8))",
        "    goal = ((1, 2, 3), (4, 5, 6), (7, 8, 0))",
    ]

    if misplaced_fn:
        parts.append(
            f'''

def {misplaced_fn}(state, goal) -> int:
    """Đếm số ô sai vị trí (h1), không tính ô trống 0."""
    s, g = _flatten_board(state), _flatten_board(goal)
    return sum(1 for a, b in zip(s, g) if a != 0 and a != b)
'''
        )
        main_calls.append(f'    print("Heuristic số ô sai (h1):", {misplaced_fn}(start, goal))')

    h_for_astar = manhattan_fn or "_manhattan_default"
    parts.append(
        f'''

def {h_for_astar}(state, goal) -> int:
    """Tính tổng khoảng cách Manhattan (h2) của các ô số từ 1..8 (không tính ô trống 0)."""
    s, g = _flatten_board(state), _flatten_board(goal)
    goal_pos = {{val: divmod(idx, 3) for idx, val in enumerate(g) if val != 0}}
    dist = 0
    for idx, val in enumerate(s):
        if val != 0:
            r1, c1 = divmod(idx, 3)
            r2, c2 = goal_pos[val]
            dist += abs(r1 - r2) + abs(c1 - c2)
    return dist
'''
    )
    if manhattan_fn:
        main_calls.append(f'    print("Heuristic Manhattan (h2):", {manhattan_fn}(start, goal))')

    nb_helper = neighbors_fn or "_neighbors_default"
    if neighbors_fn or solve_puz_fn:
        parts.append(
            f'''

def {nb_helper}(state):
    """Sinh các trạng thái kế tiếp hợp lệ bằng cách trượt ô trống 0."""
    is_2d = len(state) == 3 and isinstance(state[0], (list, tuple))
    flat = list(_flatten_board(state))
    zero_idx = flat.index(0)
    r, c = divmod(zero_idx, 3)
    results = []
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if 0 <= nr < 3 and 0 <= nc < 3:
            nxt = flat[:]
            swap_idx = nr * 3 + nc
            nxt[zero_idx], nxt[swap_idx] = nxt[swap_idx], nxt[zero_idx]
            if is_2d:
                results.append(tuple(tuple(nxt[i : i + 3]) for i in range(0, 9, 3)))
            else:
                results.append(tuple(nxt))
    return results
'''
        )
        if neighbors_fn:
            main_calls.append(f'    print("Số trạng thái kề ban đầu:", len({neighbors_fn}(start)))')

    if solve_puz_fn:
        parts.append(
            f'''

def {solve_puz_fn}(start, goal):
    """Giải 8-puzzle bằng thuật toán A* với khoảng cách Manhattan."""
    s0 = start if isinstance(start, tuple) else _flatten_board(start)
    g_flat = _flatten_board(goal)
    counter = count()
    frontier = [({h_for_astar}(s0, g_flat), next(counter), 0, s0, [s0])]
    best_g = {{_flatten_board(s0): 0}}

    while frontier:
        _, _, g_val, curr, path = heapq.heappop(frontier)
        curr_key = _flatten_board(curr)
        if curr_key == g_flat:
            return path
        if g_val > best_g.get(curr_key, float("inf")):
            continue
        for nxt in {nb_helper}(curr):
            nxt_key = _flatten_board(nxt)
            ng = g_val + 1
            if ng < best_g.get(nxt_key, float("inf")):
                best_g[nxt_key] = ng
                heapq.heappush(frontier, (ng + {h_for_astar}(nxt_key, g_flat), next(counter), ng, nxt, path + [nxt]))
    return None
'''
        )
        main_calls.append(f'    duong_di = {solve_puz_fn}(start, goal)')
        main_calls.append('    print("Số bước giải A*:", len(duong_di) - 1 if duong_di else None)')

    parts.append("\n\ndef main() -> None:\n" + "\n".join(main_calls) + '\n\n\nif __name__ == "__main__":\n    main()\n')
    return OfflineSolution(
        "exam_puzzle_pure_functions",
        "".join(parts),
        "Đã cài đặt hàm heuristic và/hoặc bộ giải A* Python thuần cho 8-Puzzle.",
        ("Hỗ trợ cả biểu diễn tuple 1 chiều và ma trận 3x3, bỏ qua ô trống 0.",),
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

    clauses: list[list[tuple[str, bool]]] = {cnf_clauses!r}
    print("Số mệnh đề vi phạm (với kết quả suy diễn hợp lệ):", dem_rang_buoc_vi_pham(ket_qua_suy_dien, clauses))

    gan_sai = {{**ket_qua_suy_dien, {rules_tuples[0][1]!r}: False}}
    print("Số mệnh đề vi phạm (khi gán sai):", dem_rang_buoc_vi_pham(gan_sai, clauses))


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_prop_logic_and_clauses",
        code,
        "Đã cài đặt suy_dien_tien(facts) và dem_rang_buoc_vi_pham(assignment, clauses).",
        ("Suy diễn điểm bất động Modus Ponens và kiểm tra từng mệnh đề tuyển (ten_bien, can_gia_tri_dung).",),
    )


def _solve_exam_nqueens_conflicts(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    conflict_fn = problem["conflict_fn"]
    hc_fn = problem.get("hc_fn")
    parts = [
        f'''from __future__ import annotations

import random


def {conflict_fn}(state) -> int:
    """Đếm số cặp quân hậu tấn công nhau (cùng hàng hoặc cùng đường chéo)."""
    n = len(state)
    so_cap = 0
    for col1 in range(n):
        for col2 in range(col1 + 1, n):
            if state[col1] == state[col2] or abs(state[col1] - state[col2]) == col2 - col1:
                so_cap += 1
    return so_cap
'''
    ]
    main_lines = [
        f'    mau_sai = [0, 1, 2, 3]',
        f'    print("Số cặp hậu tấn công trên [0, 1, 2, 3]:", {conflict_fn}(mau_sai))',
        f'    mau_dung = [1, 3, 0, 2]',
        f'    print("Số cặp hậu tấn công trên [1, 3, 0, 2]:", {conflict_fn}(mau_dung))',
    ]

    if hc_fn:
        parts.append(
            f'''

def {hc_fn}(n: int = 8, max_restarts: int = 50) -> list[int]:
    """Giải bài toán N quân hậu bằng Leo đồi kết hợp khởi động lại ngẫu nhiên."""
    rng = random.Random(42)
    best_overall: list[int] = list(range(n))
    best_h = {conflict_fn}(best_overall)

    for _ in range(max_restarts):
        current = [rng.randrange(n) for _ in range(n)]
        curr_h = {conflict_fn}(current)
        while curr_h > 0:
            next_state = None
            next_h = curr_h
            for col in range(n):
                orig_row = current[col]
                for row in range(n):
                    if row == orig_row:
                        continue
                    cand = current[:]
                    cand[col] = row
                    h_val = {conflict_fn}(cand)
                    if h_val < next_h:
                        next_h = h_val
                        next_state = cand
            if next_state is None:
                break
            current, curr_h = next_state, next_h
        if curr_h < best_h:
            best_overall, best_h = current, curr_h
        if best_h == 0:
            break
    return best_overall
'''
        )
        main_lines.append(f'    nghiem_8 = {hc_fn}(8)')
        main_lines.append(f'    print("Nghiệm 8 hậu tìm được:", nghiem_8, "| Xung đột:", {conflict_fn}(nghiem_8))')

    parts.append("\n\ndef main() -> None:\n" + "\n".join(main_lines) + '\n\n\nif __name__ == "__main__":\n    main()\n')
    return OfflineSolution(
        "exam_nqueens_conflicts",
        "".join(parts),
        "Đã cài đặt hàm đếm cặp hậu tấn công và/hoặc tìm kiếm cục bộ Hill Climbing.",
        ("Kiểm tra chính xác cả xung đột ngang và hai đường chéo.",),
    )


def _solve_exam_entropy_ig(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    entropy_fn = problem["entropy_fn"]
    ig_fn = problem["ig_fn"]
    code = f'''from __future__ import annotations

import math
from collections import Counter


def {entropy_fn}(labels: list) -> float:
    """Tính Entropy Shannon (cơ số 2) cho danh sách nhãn; trả về 0.0 nếu danh sách rỗng hoặc thuần nhất."""
    total = len(labels)
    if total == 0:
        return 0.0
    counts = Counter(labels)
    ent = 0.0
    for cnt in counts.values():
        p = cnt / total
        if p > 0.0:
            ent -= p * math.log2(p)
    return float(ent)


def {ig_fn}(parent_labels: list, subsets: list[list]) -> float:
    """Tính độ lợi thông tin (Information Gain) khi phân hoạch parent_labels thành các tập con subsets."""
    total = len(parent_labels)
    if total == 0:
        return 0.0
    parent_ent = {entropy_fn}(parent_labels)
    weighted_child_ent = sum((len(sub) / total) * {entropy_fn}(sub) for sub in subsets if sub)
    return float(parent_ent - weighted_child_ent)


def main() -> None:
    nhan_goc = ["Co", "Co", "Co", "Co", "Co", "Co", "Co", "Co", "Co", "Khong", "Khong", "Khong", "Khong", "Khong"]
    nhanh_nang = ["Co", "Co", "Khong", "Khong", "Khong"]
    nhanh_u_am = ["Co", "Co", "Co", "Co"]
    nhanh_mua = ["Co", "Co", "Co", "Khong", "Khong"]

    print(f"Entropy tập gốc: {{{entropy_fn}(nhan_goc):.6f}}")
    print(f"Information Gain (Thời tiết): {{{ig_fn}(nhan_goc, [nhanh_nang, nhanh_u_am, nhanh_mua]):.6f}}")


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_entropy_ig",
        code,
        f"Đã cài đặt {entropy_fn}() và {ig_fn}() cho cây quyết định ID3.",
        ("Xử lý an toàn tập rỗng và xác suất bằng 0.",),
    )


EXAM_CODING_SOLVERS = {
    "exam_vowel_cosine": _solve_exam_vowel_cosine,
    "exam_text_jaccard_levenshtein": _solve_exam_text_jaccard_levenshtein,
    "exam_graph_dict_bfs_dfs": _solve_exam_graph_dict_bfs_dfs,
    "exam_weighted_graph_ucs_astar": _solve_exam_weighted_graph_ucs_astar,
    "exam_puzzle_pure_functions": _solve_exam_puzzle_pure_functions,
    "exam_prop_logic_and_clauses": _solve_exam_prop_logic_and_clauses,
    "exam_nqueens_conflicts": _solve_exam_nqueens_conflicts,
    "exam_entropy_ig": _solve_exam_entropy_ig,
}
