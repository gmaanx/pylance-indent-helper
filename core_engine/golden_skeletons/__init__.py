# -*- coding: utf-8 -*-
"""
Trung tam Kho Phoi Vang (Golden Skeletons Registry) + BM25 Offline RAG + Parameter Injector.
Bao phu 47 Phoi Vang toan bo SimpleAI (Search, Local, CSP, Environments, Machine Learning, RL),
Cai chay (Nut/gamma), miniKanren (Buoi06), Logic & Suy dien (Chuong 6), va Doi khang (Minimax/Alpha-Beta).
"""

import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from .classical_search import CLASSICAL_SEARCH_SKELETONS
from .raw_search import RAW_SEARCH_SKELETONS
from .local_search import LOCAL_SEARCH_SKELETONS
from .csp_problems import CSP_SKELETONS
from .logic_kanren import LOGIC_KANREN_SKELETONS
from .adversarial_game import ADVERSARIAL_GAME_SKELETONS
from .slide_and_variants import SLIDE_AND_VARIANT_SKELETONS
from .csp_logic_ml_variants import CSP_LOGIC_ML_VARIANT_SKELETONS
from .knowledge_uncertainty_oop import KNOWLEDGE_UNCERTAINTY_OOP_SKELETONS

ALL_SKELETONS: Dict[str, Dict[str, Any]] = {}
for _group in (
    CLASSICAL_SEARCH_SKELETONS,
    RAW_SEARCH_SKELETONS,
    LOCAL_SEARCH_SKELETONS,
    CSP_SKELETONS,
    LOGIC_KANREN_SKELETONS,
    ADVERSARIAL_GAME_SKELETONS,
    SLIDE_AND_VARIANT_SKELETONS,
    CSP_LOGIC_ML_VARIANT_SKELETONS,
    KNOWLEDGE_UNCERTAINTY_OOP_SKELETONS,
):
    ALL_SKELETONS.update(_group)

SIMPLEAI_STRICT_RULES = """
QUY TAC BAT BUOC KHI VIET CODE PYTHON MON TRI TUE NHAN TAO (UEH LAB STYLE):
1. PHONG CACH CODE TREN LOP:
   - Dat ten bien/ham tieng Viet khong dau tu nhien (VD: `trang_thai`, `so_nut_xet`, `ket_qua`, `bat_dau`, `thoi_gian`, `chay`, `in_ket_qua`, `khong_xung_dot`, `so_cap_tan_cong`).
   - Do thoi gian bang `time.perf_counter()` va dem `self.so_nut_xet += 1` trong `is_goal(self, state)`.
   - Comment ngan gon khong dau, TUYET DOI KHONG viet comment kieu AI dai dong.
2. QUY TAC CUNG CUA THU VIEN `simpleai`:
   - `INITIAL_STATE` va gia tri tra ve cua `result(self, state, action)` BAT BUOC phai la kieu BAT BIEN (hashable): `tuple`, `str`, `int`, `frozenset`, hoac `tuple of tuples` `tuple(tuple(r) for r in grid)`. TUYET DOI KHONG tra ve `list` hay `dict`!
   - Trong `__init__(self, initial_state=...)` cua lop ke thua `SearchProblem`, luon goi `super().__init__(initial_state)`.
   - Khi goi thuat toan tim kiem do thi (`breadth_first`, `depth_first`, `uniform_cost`, `greedy`, `astar`), LUON truyen `graph_search=True` (tru bai toan cay phan nhanh khong chu trinh).
   - Doi voi `Local Search` (`from simpleai.search.local import hill_climbing, hill_climbing_stochastic, hill_climbing_random_restarts, beam, beam_best_first, simulated_annealing, genetic`):
     + SimpleAI LUON CUC DAI HOA (MAXIMIZE) ham `value(self, state)`. Neu bai toan la cuc tieu hoa xung dot/chi phi/so o sai vi tri, phai tra ve `-so_xung_dot(state)` hoac `-so_o_sai(state)`.
     + Bat buoc cai dat `generate_random_state(self)` cho `hill_climbing_random_restarts`, `beam`, `genetic`, va `crossover(self, state1, state2)`, `mutate(self, state)` cho `genetic`.
   - Doi voi `CSP` (`from simpleai.search import CspProblem, backtrack, min_conflicts, convert_to_binary, MOST_CONSTRAINED_VARIABLE, HIGHEST_DEGREE_VARIABLE, LEAST_CONSTRAINING_VALUE` va `from simpleai.search.arc import arc_consistency_3, revise, all_arcs`):
     + Moi ham rang buoc (constraint function) BAT BUOC nhan dung 2 tham so: `def ten_ham(variables, values):` (KHONG viet `def ten_ham(a, b):`).
     + Danh sach `constraints` co dang `[((var1, var2), ten_ham), ...]`.
     + Khi co rang buoc >2 bien va muon dung AC-3 hoac LCV, dung `convert_to_binary(variables, domains, constraints)` hoac `inference=False`.
3. QUY TAC VOI `miniKanren` (`kanren`):
   - Import chuan: `from kanren import run, var, eq, membero, Relation, facts, fact, conde` va `from kanren.core import lall`, `from toolz import unique`.
"""

SYNONYM_MAP: Dict[str, List[str]] = {
    "chieu rong": ["bfs", "breadth_first"],
    "chieu sau": ["dfs", "depth_first"],
    "chi phi cuc tieu": ["ucs", "uniform_cost"],
    "gioi han do sau": ["dls", "limited_depth_first"],
    "sau dan": ["ids", "iterative_limited_depth_first"],
    "tham lam": ["greedy"],
    "a sao": ["astar", "a*"],
    "leo doi": ["hill_climbing", "local"],
    "luyen kim": ["simulated_annealing", "local"],
    "toi u": ["simulated_annealing", "local"],
    "toi thep": ["simulated_annealing", "local"],
    "di truyen": ["genetic", "local", "crossover", "mutate"],
    "chum tia": ["beam", "beam_best_first", "local"],
    "quan hau": ["nqueens", "namquanhau", "in_ban_co", "so_cap_tan_cong"],
    "8 so": ["8puzzle", "8-puzzle", "eight_puzzle", "manhattan", "misplaced"],
    "o chu 8 so": ["8puzzle", "8-puzzle", "manhattan", "misplaced"],
    "15 so": ["15puzzle", "15-puzzle", "npuzzle"],
    "o trong": ["8puzzle", "tim_o", "in_ma_tran"],
    "may hut bui": ["vacuum", "mayhutbuiproblem", "search_vacuum_world"],
    "thieu cam nhan": ["sensorless", "search_sensorless_vacuum", "belief"],
    "dong nuoc": ["water_jugs", "binh_nuoc", "dung_tich"],
    "qua song": ["river_crossing", "nha_truyen_giao", "tho_dan"],
    "soi de bap cai": ["wolf_goat_cabbage", "soidebapcaiproblem"],
    "quan ma": ["knight", "quanmaproblem", "ma_di_tuan"],
    "doi tien": ["coin_change", "doitienproblem", "menh_gia"],
    "nhieu diem dich": ["multi_goal", "robotthuthapproblem", "chia_khoa"],
    "me cung": ["maze", "grid", "mecungproblem"],
    "to mau": ["map_coloring", "khac_mau", "csp"],
    "mat ma": ["cryptarithmetic", "send", "more", "money", "two", "four", "csp"],
    "thoa man rang buoc": ["csp", "cspproblem", "backtrack"],
    "phu hop canh": ["ac3", "arc_consistency_3", "revise", "csp_convert_to_binary_ac3"],
    "quay lui": ["backtrack", "csp"],
    "xung dot": ["min_conflicts", "khong_xung_dot"],
    "bang chan ly": ["truth_table", "logic_truth_table", "bao_ham"],
    "hop giai": ["resolution", "logic_cnf_resolution", "cnf", "phan_chung"],
    "cay quyet dinh": ["decisiontreelearner", "id3", "ml_classifiers_simpleai"],
    "hoc tang cuong": ["tdqlearner", "sarsalearner", "ml_reinforcement_simpleai"],
    "gia pha": ["family", "kanren", "father", "mother", "grandparent"],
    "gia dinh": ["family", "kanren", "father", "mother", "sibling"],
    "so nguyen to": ["prime", "check_prime", "kanren", "sympy"],
    "giao hoan": ["assoccomm", "commutative", "associative", "expression_matcher"],
    "bang ven bien": ["states", "coastal", "adjacent", "kanren"],
    "nuoi tho": ["zebra", "puzzle", "lall", "membero", "kanren"],
    "suy dien lui": ["backward_chaining", "logic_chaining"],
    "suy dien tien": ["forward_chaining", "logic_chaining"],
    "cat tia": ["alpha_beta", "minimax", "game"],
    "doi khang": ["minimax", "alpha_beta", "game"],
    "co caro": ["tictactoe", "alpha_beta"],
    "boc soi": ["nim", "alpha_beta"],
    "cai tui": ["knapsack", "caituiproblem", "local"],
    "ba lo": ["knapsack", "caituiproblem", "local"],
    "nguoi du lich": ["tsp", "tspproblem"],
    "thap ha noi": ["hanoi", "thaphanoiproblem"],
    "class nut": ["raw_graph_search", "gamma", "fringe"],
    "nuttimkiem": ["oop_search_node_nuttimkiem", "f_cost", "truy_vet_duong_di"],
    "vector24": ["oop_vector24_cosine_plagiarism", "tich_vo_huong", "cosine"],
    "dao van": ["oop_vector24_cosine_plagiarism", "do_tuong_dong_cosin", "khu_dau"],
    "ontology": ["ontology_tbox_abox_simpleai", "tbox", "abox", "subclassof", "disjoint"],
    "mang ngu nghia": ["ontology_tbox_abox_simpleai", "frame_inheritance_conflict"],
    "he thong khung": ["frame_inheritance_conflict", "frame", "slots"],
    "da ke thua": ["frame_inheritance_conflict", "frame", "override"],
    "dinh ly bayes": ["prob_joint_conditional_bayes", "posterior", "prior", "likelihood"],
    "xac suat co dieu kien": ["prob_joint_conditional_bayes", "conditional_probability"],
    "mang bayes": ["prob_bayesian_network_cpt", "cpt", "enumeration_ask"],
    "tap mo": ["fuzzy_sets_inference", "fuzzy", "lat_cat_alpha", "giai_mo_trong_tam"],
    "lat cat alpha": ["fuzzy_sets_inference", "alpha_cut", "fuzzy"],
    "giai mo": ["fuzzy_sets_inference", "centroid", "defuzzification"],
}


def strip_accents(text: str) -> str:
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    norm = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")


def tokenize_query(text: str) -> List[str]:
    clean = strip_accents(text).lower()
    expanded_tokens: List[str] = []
    for phrase, syns in SYNONYM_MAP.items():
        if phrase in clean:
            expanded_tokens.extend(syns)
    words = re.findall(r"[a-z0-9_*]+", clean)
    return words + expanded_tokens


class BM25SkeletonRetriever:
    def __init__(self, skeletons: Dict[str, Dict[str, Any]]) -> None:
        self.skeletons = skeletons
        self.doc_tokens: Dict[str, List[str]] = {}
        self.doc_tf_maps: Dict[str, Dict[str, int]] = {}
        self.doc_freqs: Dict[str, int] = {}
        self.avg_dl = 1.0
        self._built = False

    def _build_index(self) -> None:
        if self._built:
            return
        total_len = 0
        for sid, item in self.skeletons.items():
            raw_text = " ".join([
                sid,
                item.get("category", ""),
                item.get("title", ""),
                " ".join(item.get("keywords", [])),
                item.get("code", "")[:1200],
            ])
            tokens = tokenize_query(raw_text)
            kw_tokens = tokenize_query(" ".join(item.get("keywords", [])))
            all_toks = tokens + kw_tokens * 3
            self.doc_tokens[sid] = all_toks
            tf_map: Dict[str, int] = {}
            for tok in all_toks:
                tf_map[tok] = tf_map.get(tok, 0) + 1
            self.doc_tf_maps[sid] = tf_map
            total_len += len(all_toks)
            for ut in tf_map:
                self.doc_freqs[ut] = self.doc_freqs.get(ut, 0) + 1
        if self.skeletons:
            self.avg_dl = total_len / len(self.skeletons)
        self._built = True

    def retrieve(
        self,
        query: str,
        top_k: int = 2,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self._built:
            self._build_index()
        q_tokens = tokenize_query(query)
        q_lower = strip_accents(query).lower()
        n_docs = len(self.skeletons)
        k1 = 1.5
        b = 0.75

        scores: List[Tuple[float, str]] = []
        for sid, item in self.skeletons.items():
            if category_filter and item.get("category") != category_filter:
                continue
            d_toks = self.doc_tokens[sid]
            dl = len(d_toks)
            score = 0.0
            tf_map = self.doc_tf_maps[sid]

            for qt in q_tokens:
                tf = tf_map.get(qt, 0)
                if tf == 0:
                    continue
                df = self.doc_freqs.get(qt, 0)
                idf = math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
                denom = tf + k1 * (1.0 - b + b * (dl / max(1.0, self.avg_dl)))
                score += idf * (tf * (k1 + 1.0)) / denom

            for kw in item.get("keywords", []):
                kw_clean = strip_accents(kw).lower()
                if kw_clean in q_lower:
                    score += 6.5

            # Disambiguation bonuses
            if sid == "raw_graph_search" and ("class nut" in q_lower or "def gamma" in q_lower or "khong dung simpleai" in q_lower):
                score += 25.0
            if sid == "local_8puzzle_genetic" and ("8" in q_lower and "puzzle" in q_lower and ("genetic" in q_lower or "di truyen" in q_lower)):
                score += 22.0
            if sid == "local_8puzzle_hill_climbing" and (("8-puzzle" in q_lower or "8 puzzle" in q_lower or "o chu" in q_lower) and ("leo doi" in q_lower or "hill" in q_lower)):
                score += 24.0
            if sid == "csp_nqueens_hybrid" and ("quan hau" in q_lower or "queens" in q_lower) and ("csp" in q_lower or "backtrack" in q_lower or "quay lui" in q_lower):
                score += 20.0
            if sid == "local_nqueens" and ("quan hau" in q_lower or "queens" in q_lower) and "csp" not in q_lower and "backtrack" not in q_lower:
                score += 18.0
            if sid == "csp_cryptarithmetic" and ("mat ma" in q_lower or "cryptarithmetic" in q_lower) and "bien nho" not in q_lower and "x1" not in q_lower:
                score += 18.0
            if sid == "csp_two_plus_two_carry" and ("bien nho" in q_lower or ("x1" in q_lower and "x2" in q_lower and "two" in q_lower)):
                score += 25.0

            scores.append((score, sid))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for sc, sid in scores[:top_k]:
            entry = dict(self.skeletons[sid])
            entry["score"] = round(sc, 3)
            results.append(entry)
        return results


RETRIEVER = BM25SkeletonRetriever(ALL_SKELETONS)


def _extract_3x3_matrices(text: str) -> List[Tuple[Tuple[int, ...], ...]]:
    matrices: List[Tuple[Tuple[int, ...], ...]] = []
    pattern = re.compile(
        r"(?:[\(\[\{]\s*){1,2}"
        r"([0-8])\s*[,\s]\s*([0-8])\s*[,\s]\s*([0-8])\s*[\)\]\}]?\s*[,\n\r\s]+\s*[\(\[\{]?\s*"
        r"([0-8])\s*[,\s]\s*([0-8])\s*[,\s]\s*([0-8])\s*[\)\]\}]?\s*[,\n\r\s]+\s*[\(\[\{]?\s*"
        r"([0-8])\s*[,\s]\s*([0-8])\s*[,\s]\s*([0-8])"
        r"(?:\s*[\)\]\}]){1,2}",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        nums = [int(m.group(i)) for i in range(1, 10)]
        if sorted(nums) == list(range(9)):
            mat = (tuple(nums[0:3]), tuple(nums[3:6]), tuple(nums[6:9]))
            if mat not in matrices:
                matrices.append(mat)

    for m9 in re.finditer(r"\b([0-8]{9})\b", text):
        nums = [int(ch) for ch in m9.group(1)]
        if sorted(nums) == list(range(9)):
            mat = (tuple(nums[0:3]), tuple(nums[3:6]), tuple(nums[6:9]))
            if mat not in matrices:
                matrices.append(mat)

    return matrices


def customize_skeleton_with_prompt(
    skeleton_id: str,
    code: str,
    raw_prompt: str,
    dsl_params: Optional[Dict[str, str]] = None,
) -> str:
    dsl = dsl_params or {}
    clean_p = strip_accents(raw_prompt)

    # 1. Bai toan 8-Puzzle (search_8puzzle_astar / local_8puzzle_genetic / local_8puzzle_hill_climbing)
    if skeleton_id in ("search_8puzzle_astar", "local_8puzzle_genetic", "local_8puzzle_hill_climbing"):
        mats = _extract_3x3_matrices(raw_prompt)
        if "dau" in dsl or "init" in dsl:
            raw_init = dsl.get("dau") or dsl.get("init", "")
            digits = [int(x) for x in re.findall(r"[0-8]", raw_init)]
            if len(digits) == 9 and sorted(digits) == list(range(9)):
                mats.insert(0, (tuple(digits[0:3]), tuple(digits[3:6]), tuple(digits[6:9])))

        if skeleton_id in ("search_8puzzle_astar", "local_8puzzle_hill_climbing") and mats:
            if len(mats) >= 2:
                init_m, goal_m = mats[0], mats[1]
                code = re.sub(
                    r"GOAL\s*=\s*\(\s*\([^\)]+\),\s*\([^\)]+\),\s*\([^\)]+\),?\s*\)",
                    f"GOAL = {repr(goal_m)}",
                    code,
                    count=1,
                )
                code = re.sub(
                    r"INITIAL\s*=\s*\(\s*\([^\)]+\),\s*\([^\)]+\),\s*\([^\)]+\),?\s*\)",
                    f"INITIAL = {repr(init_m)}",
                    code,
                    count=1,
                )
            elif len(mats) == 1:
                init_m = mats[0]
                code = re.sub(
                    r"INITIAL\s*=\s*\(\s*\([^\)]+\),\s*\([^\)]+\),\s*\([^\)]+\),?\s*\)",
                    f"INITIAL = {repr(init_m)}",
                    code,
                    count=1,
                )
        elif skeleton_id == "local_8puzzle_genetic" and mats:
            flat_goal = tuple(x for row in mats[-1] for x in row)
            code = re.sub(
                r"GOAL\s*=\s*\([^\)]+\)",
                f"GOAL = {repr(flat_goal)}",
                code,
                count=1,
            )

    # 2. Bai toan N-Queens (local_nqueens / csp_nqueens_hybrid)
    elif skeleton_id in ("local_nqueens", "csp_nqueens_hybrid"):
        n_val = None
        if "n" in dsl:
            try:
                n_val = int(dsl["n"])
            except ValueError:
                pass
        if n_val is None:
            m_q = re.search(r"\b(\d{1,2})\s*(?:quan\s*hau|queens|queen)\b", clean_p, re.IGNORECASE)
            if not m_q:
                m_q = re.search(r"\bban\s*co\s*(\d{1,2})\s*[xX*]\s*\1\b", clean_p, re.IGNORECASE)
            if m_q:
                cand = int(m_q.group(1))
                if 4 <= cand <= 20:
                    n_val = cand
        if n_val is not None:
            code = re.sub(r"^N\s*=\s*\d+", f"N = {n_val}", code, count=1, flags=re.MULTILINE)

    # 3. Bai toan Sinh xau (search_string_gen)
    elif skeleton_id == "search_string_gen":
        target_str = dsl.get("dich") or dsl.get("goal")
        if not target_str:
            m_s = re.search(r"['\"]([A-Z ]{2,25})['\"]", raw_prompt)
            if m_s:
                target_str = m_s.group(1)
        if target_str:
            code = re.sub(
                r"^GOAL\s*=\s*['\"][^'\"]+['\"]",
                f"GOAL = {repr(target_str.upper())}",
                code,
                count=1,
                flags=re.MULTILINE,
            )

    # 4. Bai toan Dong nuoc (search_water_jugs)
    elif skeleton_id == "search_water_jugs":
        if "binh" in dsl:
            jugs = tuple(int(x) for x in re.findall(r"\d+", dsl["binh"]))
            if jugs:
                code = re.sub(r"^DUNG_TICH\s*=\s*\([^\)]+\)", f"DUNG_TICH = {repr(jugs)}", code, count=1, flags=re.MULTILINE)
                if "dau" not in dsl:
                    init_j = tuple(0 for _ in jugs)
                    code = re.sub(r"^INITIAL\s*=\s*\([^\)]+\)", f"INITIAL = {repr(init_j)}", code, count=1, flags=re.MULTILINE)
        if "dau" in dsl:
            init_j = tuple(int(x) for x in re.findall(r"\d+", dsl["dau"]))
            if init_j:
                code = re.sub(r"^INITIAL\s*=\s*\([^\)]+\)", f"INITIAL = {repr(init_j)}", code, count=1, flags=re.MULTILINE)
        if "dich" in dsl:
            nums_d = re.findall(r"\d+", dsl["dich"])
            if len(nums_d) == 1:
                code = re.sub(r"^MUC_TIEU\s*=\s*.*", f"MUC_TIEU = {int(nums_d[0])}", code, count=1, flags=re.MULTILINE)

    # 5. Bai toan Thap Ha Noi (search_hanoi)
    elif skeleton_id == "search_hanoi":
        m_d = re.search(r"\b(\d)\s*(?:dia|disks|disk)\b", clean_p, re.IGNORECASE)
        if m_d:
            so_dia = int(m_d.group(1))
            if 2 <= so_dia <= 8:
                code = re.sub(r"^SO_DIA\s*=\s*\d+", f"SO_DIA = {so_dia}", code, count=1, flags=re.MULTILINE)

    # 6. Bai toan Cryptarithmetic (csp_cryptarithmetic)
    elif skeleton_id == "csp_cryptarithmetic":
        m_crypto = re.search(r"\b([A-Z]{2,8})\s*\+\s*([A-Z]{2,8})\s*=\s*([A-Z]{2,9})\b", raw_prompt)
        if m_crypto:
            w1, w2, w3 = m_crypto.group(1), m_crypto.group(2), m_crypto.group(3)
            code = re.sub(r"^TU_1\s*=\s*['\"][^'\"]+['\"]", f"TU_1 = {repr(w1)}", code, count=1, flags=re.MULTILINE)
            code = re.sub(r"^TU_2\s*=\s*['\"][^'\"]+['\"]", f"TU_2 = {repr(w2)}", code, count=1, flags=re.MULTILINE)
            code = re.sub(r"^TONG\s*=\s*['\"][^'\"]+['\"]", f"TONG = {repr(w3)}", code, count=1, flags=re.MULTILINE)

    # 7. Bai toan Tim duong tren do thi Romania (raw_graph_search / search_graph_simpleai)
    elif skeleton_id in ("raw_graph_search", "search_graph_simpleai"):
        romania_cities = [
            "Arad", "Bucharest", "Craiova", "Drobeta", "Eforie", "Fagaras",
            "Giurgiu", "Hirsova", "Iasi", "Lugoj", "Mehadia", "Neamt",
            "Oradea", "Pitesti", "Rimnicu Vilcea", "Sibiu", "Timisoara",
            "Urziceni", "Vaslui", "Zerind",
        ]
        found_cities = []
        for city in romania_cities:
            for m_c in re.finditer(r"\b" + re.escape(city) + r"\b", raw_prompt, re.IGNORECASE):
                found_cities.append((m_c.start(), city))
        found_cities.sort(key=lambda x: x[0])
        ordered_unique = []
        for _, c in found_cities:
            if c not in ordered_unique:
                ordered_unique.append(c)
        if len(ordered_unique) >= 2:
            start_c, goal_c = ordered_unique[0], ordered_unique[1]
            if skeleton_id == "raw_graph_search":
                code = re.sub(
                    r'bat_dau,\s*dich\s*=\s*"[^"]+",\s*\{\s*"[^"]+"\s*\}',
                    f'bat_dau, dich = "{start_c}", {{"{goal_c}"}}',
                    code,
                    count=1,
                )
            else:
                code = re.sub(r'^INITIAL\s*=\s*"[^"]+"', f'INITIAL = "{start_c}"', code, count=1, flags=re.MULTILINE)
                code = re.sub(r'^GOAL\s*=\s*"[^"]+"', f'GOAL = "{goal_c}"', code, count=1, flags=re.MULTILINE)

    # 8. Bai toan May hut bui (search_vacuum_world): ho tro trang thai #1..#8 tren Slide 8 Chuong 3
    elif skeleton_id == "search_vacuum_world":
        vac_states = {
            1: ('A', 'Ban', 'Ban'), 2: ('B', 'Ban', 'Ban'),
            3: ('A', 'Ban', 'Sach'), 4: ('B', 'Ban', 'Sach'),
            5: ('A', 'Sach', 'Ban'), 6: ('B', 'Sach', 'Ban'),
            7: ('A', 'Sach', 'Sach'), 8: ('B', 'Sach', 'Sach'),
        }
        m_vs = re.search(r"#([1-8])\b", raw_prompt)
        if m_vs:
            st_num = int(m_vs.group(1))
            code = re.sub(
                r"^INITIAL\s*=\s*\([^\)]+\)",
                f"INITIAL = {repr(vac_states[st_num])}",
                code,
                count=1,
                flags=re.MULTILINE,
            )

    # 9. Bai toan Doi tien (search_coin_change)
    elif skeleton_id == "search_coin_change":
        m_amt = re.search(r"(?:so\s*tien|doi|goal|dich)\s*[=:]?\s*(\d{2,5})\b", clean_p, re.IGNORECASE)
        if m_amt:
            amt = int(m_amt.group(1))
            code = re.sub(r"^SO_TIEN_CAN_DOI\s*=\s*\d+", f"SO_TIEN_CAN_DOI = {amt}", code, count=1, flags=re.MULTILINE)

    return code
