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
        pattern = re.compile(rf"\b{re.escape(var_name)}\s*(?::[^=\n]+)?=\s*{re.escape(open_ch)}", re.IGNORECASE)
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


def _extract_func_param_names(text: str, fn_name: str) -> List[str]:
    """Extract parameter identifiers of `fn_name(...)` respecting nested bracket annotations like `dict[str, list[str]]`."""
    cleaned = normalize_pdf_code_artifacts(text)
    m = re.search(rf"\b{re.escape(fn_name)}\s*\(", cleaned, flags=re.IGNORECASE)
    if not m:
        return []
    open_idx = m.end() - 1
    depth = 0
    in_q: Optional[str] = None
    esc = False
    inner: Optional[str] = None
    for idx in range(open_idx, min(len(cleaned), open_idx + 360)):
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
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                inner = cleaned[open_idx + 1 : idx]
                break
    if not inner:
        return []
    parts: List[str] = []
    b_depth = 0
    cur: List[str] = []
    for ch in inner:
        if ch in "([{":
            b_depth += 1
            cur.append(ch)
        elif ch in ")]}":
            b_depth = max(0, b_depth - 1)
            cur.append(ch)
        elif ch == "," and b_depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    names: List[str] = []
    for part in parts:
        if not part or part in ("self", "/", "*") or part.startswith("*"):
            continue
        head = part.split(":", 1)[0].split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", head):
            names.append(head)
    return names


def parse_exam_coding_exercise(text: str) -> Optional[Dict[str, Any]]:
    """Recognize complete pure-Python and parameterized SimpleAI coding exercises from the course exam bank."""
    cleaned = normalize_pdf_code_artifacts(text)
    folded = strip_accents(cleaned).casefold()
    if "kanren" in folded:
        return None

    # 0. Bai 5.x (SimpleAI): Parameterized binary CSP function (e.g. giai_csp_phan_ca(domains, pairs) -> dict | None)
    if "simpleai" in folded:
        m_scsp = re.search(
            r"\b(?P<fn>giai_csp_[A-Za-z0-9_]*|giai_csp|solve_csp_[A-Za-z0-9_]*|solve_csp|phan_ca_csp|to_mau_csp)\s*\(",
            folded,
        )
        if m_scsp and ("cspproblem" in folded or "backtrack" in folded or "csp" in folded):
            same_len = len(cleaned) == len(folded)
            fn_exact = cleaned[m_scsp.start("fn") : m_scsp.end("fn")] if same_len else m_scsp.group("fn")
            csp_params = _extract_func_param_names(cleaned, fn_exact)
            if len(csp_params) == 2:
                p1_exact, p2_exact = csp_params[0], csp_params[1]
                sample_domains = _extract_named_dict_literal(cleaned, p1_exact) or _extract_named_dict_literal(cleaned, "domains")
                sample_pairs = _extract_named_literal(cleaned, (p2_exact, "pairs", "edges", "conflicts", "xung_dot"), "[", "]")
                return {
                    "type": "exam_simpleai_csp_func",
                    "fn_name": fn_exact,
                    "p1": p1_exact,
                    "p2": p2_exact,
                    "use_mrv": "most_constrained_variable" in folded or "mrv" in folded,
                    "use_deg": ("highest_degree_variable" in folded or "degree" in folded) and "most_constrained_variable" not in folded,
                    "use_lcv": "least_constraining_value" in folded or "lcv" in folded,
                    "domains": sample_domains if isinstance(sample_domains, dict) else None,
                    "pairs": sample_pairs if isinstance(sample_pairs, list) else None,
                }
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
        ig_params = _extract_func_param_names(cleaned, ig_fn)
        return {
            "type": "exam_entropy_ig",
            "entropy_fn": entropy_fn,
            "ig_fn": ig_fn,
            "ig_params": ig_params,
        }

    # 9. Bai 3.3: DLS & IDS on graph dict
    dls_fn = _find_requested_func_name(folded, ("dls", "depth_limited_search", "tim_kiem_gioi_han_do_sau"))
    ids_fn = _find_requested_func_name(folded, ("ids", "iterative_deepening_search", "tim_kiem_sau_dan"))
    if (dls_fn or ids_fn) and "graph" in folded and "start" in folded and "goal" in folded:
        sample_graph = _extract_named_dict_literal(cleaned, "graph")
        return {
            "type": "exam_graph_dls_ids",
            "dls_fn": dls_fn,
            "ids_fn": ids_fn,
            "graph": sample_graph,
        }

    # 10. Bai 5.1: Minimax & Alpha-Beta Pruning on game tree
    mm_fn = _find_requested_func_name(folded, ("minimax",))
    ab_fn = _find_requested_func_name(folded, ("alpha_beta", "alphabeta"))
    if (mm_fn or ab_fn) and not re.search(r"\b(?:tictactoe|tic-tac-toe|caro|nim)\b", folded):
        ab_params = _extract_func_param_names(cleaned, ab_fn) if ab_fn else []
        mm_params = _extract_func_param_names(cleaned, mm_fn) if mm_fn else []
        check_params = ab_params or mm_params
        nested_list_mode = bool(
            check_params
            and not any(p.lower() in ("tree", "scores", "values", "utilities", "graph") for p in check_params)
            and ("list" in folded or "de quy" in folded or "depth" in [p.lower() for p in check_params])
        )
        sample_tree = _extract_named_dict_literal(cleaned, "tree")
        sample_scores = _extract_named_literal(cleaned, ("scores", "values", "utilities", "leaf_values"), "{", "}")
        return {
            "type": "exam_minimax_alphabeta",
            "mm_fn": mm_fn,
            "ab_fn": ab_fn,
            "ab_params": ab_params,
            "mm_params": mm_params,
            "nested_list_mode": nested_list_mode,
            "tree": sample_tree if isinstance(sample_tree, dict) else None,
            "scores": sample_scores if isinstance(sample_scores, dict) else None,
        }

    # 11. Bai 5.2: Pure-Python CSP AC-3 & Backtracking
    ac3_fn = _find_requested_func_name(folded, ("ac3", "arc_consistency_3", "phu_hop_cung"))
    bt_csp_fn = _find_requested_func_name(folded, ("backtrack_csp", "giai_csp"))
    if (ac3_fn or bt_csp_fn) and "domains" in folded:
        return {
            "type": "exam_csp_ac3_backtrack",
            "ac3_fn": ac3_fn,
            "bt_csp_fn": bt_csp_fn,
        }

    # 12. Bai 6.2 / Chuong 9: K-NN Classifier & Bayes Theorem
    euclid_fn = _find_requested_func_name(folded, ("khoang_cach_euclid", "euclidean_distance", "euclid_distance"))
    knn_fn = _find_requested_func_name(folded, ("knn_predict", "phan_loai_knn", "du_doan_knn"))
    bayes_fn = _find_requested_func_name(folded, ("dinh_ly_bayes", "tinh_bayes", "bayes_posterior"))
    if knn_fn or bayes_fn:
        return {
            "type": "exam_knn_bayes",
            "euclid_fn": euclid_fn,
            "knn_fn": knn_fn,
            "bayes_fn": bayes_fn,
        }

    # 13. Chuong 9: Pure-Python Fuzzy Set Operations & Centroid Defuzzification
    hop_mo_fn = _find_requested_func_name(folded, ("hop_mo", "fuzzy_union"))
    giao_mo_fn = _find_requested_func_name(folded, ("giao_mo", "fuzzy_intersection"))
    bu_mo_fn = _find_requested_func_name(folded, ("phan_bu_mo", "fuzzy_complement"))
    centroid_fn = _find_requested_func_name(folded, ("giai_mo_trong_tam", "centroid_defuzzification", "giai_mo_centroid"))
    if centroid_fn or (hop_mo_fn and giao_mo_fn):
        return {
            "type": "exam_fuzzy_centroid",
            "hop_mo_fn": hop_mo_fn,
            "giao_mo_fn": giao_mo_fn,
            "bu_mo_fn": bu_mo_fn,
            "centroid_fn": centroid_fn,
        }

    # 14. Bai 1.x / 3.x: Pure-Python Tower of Hanoi recursion
    hanoi_fn = _find_requested_func_name(folded, ("thap_ha_noi", "tower_of_hanoi", "hanoi"))
    if hanoi_fn and ("ha noi" in folded or "hanoi" in folded):
        return {
            "type": "exam_hanoi_recursion",
            "hanoi_fn": hanoi_fn,
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
    ig_params = problem.get("ig_params") or []
    if len(ig_params) == 3:
        p_rows, p_attr, p_target = ig_params[0], ig_params[1], ig_params[2]
        code = f'''from __future__ import annotations

import math
from collections import Counter, defaultdict


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


def {ig_fn}({p_rows}: list[dict], {p_attr}: str, {p_target}: str) -> float:
    """Tính độ lợi thông tin IG(S, attr) trên danh sách bản ghi dict."""
    total = len({p_rows})
    if total == 0:
        return 0.0
    parent_labels = [r[{p_target}] for r in {p_rows}]
    parent_ent = {entropy_fn}(parent_labels)
    groups: dict[object, list] = defaultdict(list)
    for r in {p_rows}:
        groups[r.get({p_attr})].append(r[{p_target}])
    weighted_child_ent = sum((len(sub) / total) * {entropy_fn}(sub) for sub in groups.values() if sub)
    return float(parent_ent - weighted_child_ent)


def main() -> None:
    du_lieu = [
        {{"ThoiTiet": "Nang", "Choi": "Khong"}},
        {{"ThoiTiet": "Nang", "Choi": "Khong"}},
        {{"ThoiTiet": "UAm", "Choi": "Co"}},
        {{"ThoiTiet": "Mua", "Choi": "Co"}},
        {{"ThoiTiet": "Mua", "Choi": "Khong"}},
    ]
    nhan_goc = [r["Choi"] for r in du_lieu]
    print(f"Entropy tập gốc: {{{entropy_fn}(nhan_goc):.6f}}")
    print(f"Information Gain (ThoiTiet): {{{ig_fn}(du_lieu, 'ThoiTiet', 'Choi'):.6f}}")


if __name__ == "__main__":
    main()
'''
    else:
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


def _solve_exam_graph_dls_ids(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    dls_fn = problem.get("dls_fn") or "dls"
    ids_fn = problem.get("ids_fn")
    sample_graph = problem.get("graph") or {
        "A": ["B", "C"],
        "B": ["D", "E"],
        "C": ["F"],
        "D": [],
        "E": ["F"],
        "F": [],
    }
    nodes = list(sample_graph.keys())
    s_node = nodes[0] if nodes else "A"
    g_node = nodes[-1] if len(nodes) >= 2 else s_node

    parts = [
        f'''from __future__ import annotations


def {dls_fn}(graph: dict, start, goal, limit: int):
    """Tìm kiếm giới hạn độ sâu (Depth-Limited Search). Trả về list đường đi hoặc None."""
    if limit < 0:
        return None
    if start not in graph and not any(start in v for v in graph.values()):
        return None

    def _rec(curr, depth_left, path_set):
        if curr == goal:
            return [curr]
        if depth_left == 0:
            return None
        for nb in graph.get(curr, []):
            if nb not in path_set:
                sub = _rec(nb, depth_left - 1, path_set | {{nb}})
                if sub is not None:
                    return [curr] + sub
        return None

    return _rec(start, limit, {{start}})
'''
    ]
    main_calls = []
    if problem.get("dls_fn"):
        main_calls.append(f'    print("DLS (limit=2):", {dls_fn}(graph, {s_node!r}, {g_node!r}, 2))')
    if ids_fn:
        parts.append(
            f'''

def {ids_fn}(graph: dict, start, goal, max_depth: int = 20):
    """Tìm kiếm sâu dần (Iterative Deepening Search) từ độ sâu 0 đến max_depth."""
    for depth in range(max_depth + 1):
        path = {dls_fn}(graph, start, goal, depth)
        if path is not None:
            return path
    return None
'''
        )
        main_calls.append(f'    print("IDS (max_depth=5):", {ids_fn}(graph, {s_node!r}, {g_node!r}, 5))')

    parts.append(
        f"\n\ndef main() -> None:\n    graph = {sample_graph!r}\n"
        + "\n".join(main_calls)
        + '\n\n\nif __name__ == "__main__":\n    main()\n'
    )
    return OfflineSolution(
        "exam_graph_dls_ids",
        "".join(parts),
        "Đã cài đặt tìm kiếm giới hạn độ sâu (DLS) và/hoặc sâu dần (IDS) trên đồ thị từ điển.",
        ("Kiểm tra tập đỉnh trên nhánh hiện tại để tránh chu trình mà vẫn bảo toàn tính tối ưu theo độ sâu.",),
    )


def _solve_exam_minimax_alphabeta(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    mm_fn = problem.get("mm_fn")
    ab_fn = problem.get("ab_fn")
    if problem.get("nested_list_mode"):
        ab_params = problem.get("ab_params") or ["node", "depth", "alpha", "beta", "is_max"]
        mm_params = problem.get("mm_params") or ["node", "depth", "is_max"]
        parts = ["from __future__ import annotations\n"]
        main_calls = []
        if mm_fn:
            if len(mm_params) == 2:
                p_n, p_m = mm_params
                parts.append(
                    f'''

def {mm_fn}({p_n}, {p_m}: bool = True):
    if isinstance({p_n}, (int, float)) or not {p_n}:
        return {p_n}
    if {p_m}:
        return max({mm_fn}(child, False) for child in {p_n})
    return min({mm_fn}(child, True) for child in {p_n})
'''
                )
                main_calls.append(f'    print("Giá trị Minimax tại gốc:", {mm_fn}(cay_mau, True))')
            else:
                p_n = mm_params[0] if len(mm_params) >= 1 else "node"
                p_d = mm_params[1] if len(mm_params) >= 2 else "depth"
                p_m = mm_params[2] if len(mm_params) >= 3 else "is_max"
                parts.append(
                    f'''

def {mm_fn}({p_n}, {p_d}: int, {p_m}: bool = True):
    if {p_d} == 0 or isinstance({p_n}, (int, float)) or not {p_n}:
        return {p_n}
    if {p_m}:
        return max({mm_fn}(child, {p_d} - 1, False) for child in {p_n})
    return min({mm_fn}(child, {p_d} - 1, True) for child in {p_n})
'''
                )
                main_calls.append(f'    print("Giá trị Minimax tại gốc:", {mm_fn}(cay_mau, 2, True))')
        if ab_fn:
            if len(ab_params) == 4:
                p_n, p_a, p_b, p_m = ab_params
                parts.append(
                    f'''

def {ab_fn}({p_n}, {p_a}: float = float("-inf"), {p_b}: float = float("inf"), {p_m}: bool = True):
    if isinstance({p_n}, (int, float)) or not {p_n}:
        return {p_n}
    if {p_m}:
        best = float("-inf")
        for child in {p_n}:
            val = {ab_fn}(child, {p_a}, {p_b}, False)
            if val > best:
                best = val
            if best > {p_a}:
                {p_a} = best
            if {p_a} >= {p_b}:
                break
        return best
    best = float("inf")
    for child in {p_n}:
        val = {ab_fn}(child, {p_a}, {p_b}, True)
        if val < best:
            best = val
        if best < {p_b}:
            {p_b} = best
        if {p_a} >= {p_b}:
            break
    return best
'''
                )
                main_calls.append(f'    print("Giá trị Alpha-Beta tại gốc:", {ab_fn}(cay_mau, float("-inf"), float("inf"), True))')
            else:
                p_n = ab_params[0] if len(ab_params) >= 1 else "node"
                p_d = ab_params[1] if len(ab_params) >= 2 else "depth"
                p_a = ab_params[2] if len(ab_params) >= 3 else "alpha"
                p_b = ab_params[3] if len(ab_params) >= 4 else "beta"
                p_m = ab_params[4] if len(ab_params) >= 5 else "is_max"
                parts.append(
                    f'''

def {ab_fn}({p_n}, {p_d}: int, {p_a}: float = float("-inf"), {p_b}: float = float("inf"), {p_m}: bool = True):
    if {p_d} == 0 or isinstance({p_n}, (int, float)) or not {p_n}:
        return {p_n}
    if {p_m}:
        best = float("-inf")
        for child in {p_n}:
            val = {ab_fn}(child, {p_d} - 1, {p_a}, {p_b}, False)
            if val > best:
                best = val
            if best > {p_a}:
                {p_a} = best
            if {p_a} >= {p_b}:
                break
        return best
    best = float("inf")
    for child in {p_n}:
        val = {ab_fn}(child, {p_d} - 1, {p_a}, {p_b}, True)
        if val < best:
            best = val
        if best < {p_b}:
            {p_b} = best
        if {p_a} >= {p_b}:
            break
    return best
'''
                )
                main_calls.append(f'    print("Giá trị Alpha-Beta tại gốc:", {ab_fn}(cay_mau, 2, float("-inf"), float("inf"), True))')
        parts.append(
            "\n\ndef main() -> None:\n    cay_mau = [[3, 5], [6, 9], [1, 2]]\n"
            + "\n".join(main_calls)
            + '\n\n\nif __name__ == "__main__":\n    main()\n'
        )
        return OfflineSolution(
            "exam_minimax_alphabeta",
            "".join(parts),
            "Đã cài đặt Minimax / Alpha-Beta đệ quy trên cây danh sách lồng nhau.",
            ("Cắt nhánh chính xác khi alpha >= beta.",),
        )

    sample_tree = problem.get("tree") or {
        "Root": ["B1", "B2"],
        "B1": ["C1", "C2"],
        "B2": ["C3", "C4"],
    }
    sample_scores = problem.get("scores") or {"C1": 3, "C2": 12, "C3": 8, "C4": 2}
    root_name = next(iter(sample_tree.keys()), "Root")

    parts = ["from __future__ import annotations\n"]
    main_calls = []
    if mm_fn:
        parts.append(
            f'''

def {mm_fn}(node, is_maximizing: bool, tree: dict, scores: dict) -> float:
    """Thuật toán Minimax trên cây trò chơi biểu diễn bằng dict."""
    if node in scores or node not in tree or not tree[node]:
        return scores[node]
    if is_maximizing:
        return max({mm_fn}(child, False, tree, scores) for child in tree[node])
    return min({mm_fn}(child, True, tree, scores) for child in tree[node])
'''
        )
        main_calls.append(f'    print("Giá trị Minimax tại gốc:", {mm_fn}({root_name!r}, True, tree, scores))')

    if ab_fn:
        parts.append(
            f'''

def {ab_fn}(
    node,
    is_maximizing: bool,
    tree: dict,
    scores: dict,
    alpha: float = float("-inf"),
    beta: float = float("inf"),
) -> float:
    """Thuật toán Cắt tỉa Alpha-Beta trên cây trò chơi biểu diễn bằng dict."""
    if node in scores or node not in tree or not tree[node]:
        return scores[node]
    if is_maximizing:
        best = float("-inf")
        for child in tree[node]:
            best = max(best, {ab_fn}(child, False, tree, scores, alpha, beta))
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    best = float("inf")
    for child in tree[node]:
        best = min(best, {ab_fn}(child, True, tree, scores, alpha, beta))
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best
'''
        )
        main_calls.append(f'    print("Giá trị Alpha-Beta tại gốc:", {ab_fn}({root_name!r}, True, tree, scores))')

    parts.append(
        f"\n\ndef main() -> None:\n    tree = {sample_tree!r}\n    scores = {sample_scores!r}\n"
        + "\n".join(main_calls)
        + '\n\n\nif __name__ == "__main__":\n    main()\n'
    )
    return OfflineSolution(
        "exam_minimax_alphabeta",
        "".join(parts),
        "Đã cài đặt Minimax và/hoặc Cắt tỉa Alpha-Beta trên cây trò chơi.",
        ("Cắt nhánh chuẩn khi alpha >= beta.",),
    )


def _solve_exam_csp_ac3_backtrack(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    ac3_fn = problem.get("ac3_fn") or "_ac3_internal"
    bt_fn = problem.get("bt_csp_fn")
    parts = [
        f'''from __future__ import annotations

from collections import deque


def {ac3_fn}(domains: dict[str, list], neighbors: dict[str, list[str]], constraint_fn=None) -> bool:
    """Thuật toán AC-3 thu hẹp miền giá trị; trả về False nếu phát hiện miền rỗng (vô nghiệm)."""
    pred = constraint_fn or (lambda u, x, v, y: x != y)
    queue = deque((xi, xj) for xi, nbs in neighbors.items() for xj in nbs)

    while queue:
        xi, xj = queue.popleft()
        revised = False
        new_dom = []
        for x in domains[xi]:
            if any(pred(xi, x, xj, y) for y in domains[xj]):
                new_dom.append(x)
            else:
                revised = True
        if revised:
            domains[xi] = new_dom
            if not new_dom:
                return False
            for xk in neighbors.get(xi, []):
                if xk != xj:
                    queue.append((xk, xi))
    return True
'''
    ]
    main_calls = [
        '    domains = {"WA": ["Do", "Xanh"], "NT": ["Do"], "SA": ["Do", "Xanh", "Vang"]}',
        '    neighbors = {"WA": ["NT", "SA"], "NT": ["WA", "SA"], "SA": ["WA", "NT"]}',
    ]
    if problem.get("ac3_fn"):
        main_calls.append(f'    hop_le = {ac3_fn}(domains, neighbors)')
        main_calls.append('    print("AC-3 hợp lệ:", hop_le, "| Miền sau khi thu hẹp:", domains)')

    if bt_fn:
        parts.append(
            f'''

def {bt_fn}(domains: dict[str, list], neighbors: dict[str, list[str]], constraint_fn=None):
    """Giải CSP bằng Quay lui kết hợp MRV."""
    pred = constraint_fn or (lambda u, x, v, y: x != y)
    dom_copy = {{k: list(v) for k, v in domains.items()}}
    if not {ac3_fn}(dom_copy, neighbors, pred):
        return None

    assignment: dict[str, object] = {{}}

    def _bt():
        if len(assignment) == len(dom_copy):
            return dict(assignment)
        unassigned = [v for v in dom_copy if v not in assignment]
        var = min(unassigned, key=lambda v: len(dom_copy[v]))
        for val in dom_copy[var]:
            if all(pred(var, val, nb, assignment[nb]) for nb in neighbors.get(var, []) if nb in assignment):
                assignment[var] = val
                res = _bt()
                if res is not None:
                    return res
                del assignment[var]
        return None

    return _bt()
'''
        )
        main_calls.append(f'    print("Nghiệm CSP:", {bt_fn}(domains, neighbors))')

    parts.append("\n\ndef main() -> None:\n" + "\n".join(main_calls) + '\n\n\nif __name__ == "__main__":\n    main()\n')
    return OfflineSolution(
        "exam_csp_ac3_backtrack",
        "".join(parts),
        "Đã cài đặt AC-3 và/hoặc Backtracking CSP Python thuần.",
        ("Kiểm tra đầy đủ tính phù hợp cung và chọn biến MRV.",),
    )


def _solve_exam_knn_bayes(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    euclid_fn = problem.get("euclid_fn") or "_euclid_dist"
    knn_fn = problem.get("knn_fn")
    bayes_fn = problem.get("bayes_fn")
    parts = ["from __future__ import annotations\n\nimport math\nfrom collections import Counter\n"]
    main_calls = []

    if knn_fn or problem.get("euclid_fn"):
        parts.append(
            f'''

def {euclid_fn}(p1: list[float], p2: list[float]) -> float:
    """Tính khoảng cách Euclid giữa 2 điểm nhiều chiều."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p1, p2)))
'''
        )
    if knn_fn:
        parts.append(
            f'''

def {knn_fn}(train_data: list[tuple[list[float], str]], query: list[float], k: int = 3) -> str:
    """Phân loại điểm dữ liệu query bằng thuật toán K láng giềng gần nhất (K-NN)."""
    if not train_data or k <= 0:
        raise ValueError("Tập huấn luyện không được rỗng và k > 0.")
    ranked = sorted((({euclid_fn}(x, query), idx, label) for idx, (x, label) in enumerate(train_data)))
    top_k = [label for _, _, label in ranked[: min(k, len(ranked))]]
    counts = Counter(top_k)
    max_votes = max(counts.values())
    # Ưu tiên lớp có nhiều phiếu nhất; nếu hòa phiếu thì chọn lớp của láng giềng gần nhất
    for label in top_k:
        if counts[label] == max_votes:
            return label
    return top_k[0]
'''
        )
        main_calls.extend([
            '    train = [([1.0, 2.0], "A"), ([1.5, 1.8], "A"), ([5.0, 8.0], "B"), ([6.0, 9.0], "B")]',
            f'    print("Dự đoán K-NN (k=3) cho [1.2, 1.9]:", {knn_fn}(train, [1.2, 1.9], k=3))',
        ])

    if bayes_fn:
        parts.append(
            f'''

def {bayes_fn}(p_a: float, p_b_given_a: float, p_b_given_not_a: float) -> float:
    """Tính xác suất hậu nghiệm P(A | B) theo Định lý Bayes."""
    p_b = p_b_given_a * p_a + p_b_given_not_a * (1.0 - p_a)
    if p_b == 0.0:
        return 0.0
    return float((p_b_given_a * p_a) / p_b)
'''
        )
        main_calls.append(f'    print(f"Xác suất hậu nghiệm Bayes P(Bệnh | Dương tính): {{{bayes_fn}(0.01, 0.99, 0.05):.6f}}")')

    parts.append("\n\ndef main() -> None:\n" + "\n".join(main_calls) + '\n\n\nif __name__ == "__main__":\n    main()\n')
    return OfflineSolution(
        "exam_knn_bayes",
        "".join(parts),
        "Đã cài đặt K-NN và/hoặc Định lý Bayes Python thuần.",
        ("Xử lý chặt chẽ trường hợp hòa phiếu trong K-NN và mẫu số bằng 0 trong Bayes.",),
    )


def _solve_exam_fuzzy_centroid(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    hop_fn = problem.get("hop_mo_fn") or "hop_mo"
    giao_fn = problem.get("giao_mo_fn") or "giao_mo"
    bu_fn = problem.get("bu_mo_fn") or "phan_bu_mo"
    cent_fn = problem.get("centroid_fn") or "giai_mo_trong_tam"

    code = f'''from __future__ import annotations


def {hop_fn}(a: dict, b: dict) -> dict:
    """Hợp hai tập mờ: mu_(A u B)(x) = max(mu_A(x), mu_B(x))."""
    keys = list(dict.fromkeys(list(a.keys()) + list(b.keys())))
    return {{x: max(float(a.get(x, 0.0)), float(b.get(x, 0.0))) for x in keys}}


def {giao_fn}(a: dict, b: dict) -> dict:
    """Giao hai tập mờ: mu_(A n B)(x) = min(mu_A(x), mu_B(x))."""
    keys = list(dict.fromkeys(list(a.keys()) + list(b.keys())))
    return {{x: min(float(a.get(x, 0.0)), float(b.get(x, 0.0))) for x in keys}}


def {bu_fn}(a: dict) -> dict:
    """Phần bù tập mờ: mu_(~A)(x) = 1 - mu_A(x)."""
    return {{x: round(1.0 - float(mu), 10) for x, mu in a.items()}}


def {cent_fn}(fuzzy_num: dict) -> float:
    """Giải mờ theo phương pháp Trọng tâm (Centroid): sum(x * mu(x)) / sum(mu(x))."""
    denom = sum(float(mu) for mu in fuzzy_num.values())
    if denom == 0.0:
        return 0.0
    numer = sum(float(x) * float(mu) for x, mu in fuzzy_num.items())
    return float(numer / denom)


def main() -> None:
    A = {{10: 0.2, 20: 0.6, 30: 1.0}}
    B = {{10: 0.5, 20: 0.4, 30: 0.8}}
    print("Hợp mờ A u B:", {hop_fn}(A, B))
    print("Giao mờ A n B:", {giao_fn}(A, B))
    print("Phần bù ~A:", {bu_fn}(A))
    print(f"Giải mờ trọng tâm Centroid(A): {{{cent_fn}(A):.4f}}")


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_fuzzy_centroid",
        code,
        "Đã cài đặt phép toán tập mờ và giải mờ trọng tâm (Centroid).",
        ("An toàn với tổng độ thuộc bằng 0.",),
    )


def _solve_exam_hanoi_recursion(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    hanoi_fn = problem["hanoi_fn"]
    code = f'''from __future__ import annotations


def {hanoi_fn}(n: int, coc_nguon: str = "A", coc_dich: str = "C", coc_trung_gian: str = "B") -> list[tuple[str, str]]:
    """Giải bài toán Tháp Hà Nội n đĩa bằng đệ quy; trả về danh sách các bước chuyển (từ_cọc, sang_cọc)."""
    if n <= 0:
        return []
    if n == 1:
        return [(coc_nguon, coc_dich)]
    buoc = {hanoi_fn}(n - 1, coc_nguon, coc_trung_gian, coc_dich)
    buoc.append((coc_nguon, coc_dich))
    buoc.extend({hanoi_fn}(n - 1, coc_trung_gian, coc_dich, coc_nguon))
    return buoc


def main() -> None:
    cac_buoc = {hanoi_fn}(3, "A", "C", "B")
    print(f"Tổng số bước chuyển 3 đĩa: {{len(cac_buoc)}}")
    for i, (tu, sang) in enumerate(cac_buoc, start=1):
        print(f"  Bước {{i}}: {{tu}} -> {{sang}}")


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_hanoi_recursion",
        code,
        f"Đã cài đặt đệ quy Tháp Hà Nội {hanoi_fn}().",
        ("Số bước tối ưu 2^n - 1.",),
    )


def _solve_exam_simpleai_csp_func(problem: Dict[str, Any]):
    from .offline_solver import OfflineSolution

    fn_name = problem["fn_name"]
    p1 = problem["p1"]
    p2 = problem["p2"]
    use_mrv = bool(problem.get("use_mrv"))
    use_deg = bool(problem.get("use_deg"))
    use_lcv = bool(problem.get("use_lcv"))

    imports = ["CspProblem", "backtrack"]
    bt_kwargs: List[str] = []
    if use_mrv:
        imports.append("MOST_CONSTRAINED_VARIABLE")
        bt_kwargs.append("variable_heuristic=MOST_CONSTRAINED_VARIABLE")
    elif use_deg:
        imports.append("HIGHEST_DEGREE_VARIABLE")
        bt_kwargs.append("variable_heuristic=HIGHEST_DEGREE_VARIABLE")
    if use_lcv:
        imports.append("LEAST_CONSTRAINING_VALUE")
        bt_kwargs.append("value_heuristic=LEAST_CONSTRAINING_VALUE")

    sample_domains = problem.get("domains") or {
        "An": ["Sang", "Chieu"],
        "Binh": ["Sang", "Chieu", "Toi"],
        "Chi": ["Sang", "Chieu", "Toi"],
        "Dung": ["Chieu", "Toi"],
    }
    sample_pairs = problem.get("pairs") or [
        ("An", "Binh"),
        ("Binh", "Chi"),
        ("Chi", "Dung"),
    ]
    bt_call = (
        f"backtrack(problem, {', '.join(bt_kwargs)})"
        if bt_kwargs
        else "backtrack(problem)"
    )

    code = f'''from __future__ import annotations

from simpleai.search import {", ".join(imports)}


def khong_trung_gia_tri(variables, values) -> bool:
    return values[0] != values[1]


def {fn_name}({p1}: dict, {p2}: list[tuple[str, str]]) -> dict | None:
    if not {p1}:
        return {{}}
    clean_domains = {{k: list(v) for k, v in {p1}.items()}}
    if any(len(v) == 0 for v in clean_domains.values()):
        return None
    variables = list(clean_domains.keys())
    constraints = [(tuple(cap), khong_trung_gia_tri) for cap in {p2}]
    problem = CspProblem(variables, clean_domains, constraints)
    ket_qua = {bt_call}
    return dict(ket_qua) if ket_qua is not None else None


def main() -> None:
    domains_mau = {sample_domains!r}
    pairs_mau = {sample_pairs!r}
    ket_qua = {fn_name}(domains_mau, pairs_mau)
    print("Kết quả giải CSP:", ket_qua)


if __name__ == "__main__":
    main()
'''
    return OfflineSolution(
        "exam_simpleai_csp_func",
        code,
        f"Đã cài đặt hàm {fn_name}({p1}, {p2}) bằng CspProblem & backtrack của SimpleAI.",
        ("Không làm thay đổi dữ liệu gốc, trả về dict nghiệm hợp lệ hoặc None khi vô nghiệm.",),
    )


EXAM_CODING_SOLVERS = {
    "exam_simpleai_csp_func": _solve_exam_simpleai_csp_func,
    "exam_vowel_cosine": _solve_exam_vowel_cosine,
    "exam_text_jaccard_levenshtein": _solve_exam_text_jaccard_levenshtein,
    "exam_graph_dict_bfs_dfs": _solve_exam_graph_dict_bfs_dfs,
    "exam_weighted_graph_ucs_astar": _solve_exam_weighted_graph_ucs_astar,
    "exam_puzzle_pure_functions": _solve_exam_puzzle_pure_functions,
    "exam_prop_logic_and_clauses": _solve_exam_prop_logic_and_clauses,
    "exam_nqueens_conflicts": _solve_exam_nqueens_conflicts,
    "exam_entropy_ig": _solve_exam_entropy_ig,
    "exam_graph_dls_ids": _solve_exam_graph_dls_ids,
    "exam_minimax_alphabeta": _solve_exam_minimax_alphabeta,
    "exam_csp_ac3_backtrack": _solve_exam_csp_ac3_backtrack,
    "exam_knn_bayes": _solve_exam_knn_bayes,
    "exam_fuzzy_centroid": _solve_exam_fuzzy_centroid,
    "exam_hanoi_recursion": _solve_exam_hanoi_recursion,
}
