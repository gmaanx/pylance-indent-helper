# -*- coding: utf-8 -*-
"""
Unambiguous Vietnamese natural-language parsers that translate complete exam
prompts directly into verified offline solver specifications (< 0.05s, 0% network).
Never guesses missing parameters or ignores extra unsupported constraints.
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional

from .golden_skeletons import strip_accents
from .offline_exam_exercises import normalize_pdf_code_artifacts

_CRYPT_RE = re.compile(
    r"^\s*(?:cau\s+\d+\s*:\s*)?(?:giai\s+)?(?:bai\s+toan\s+)?(?:mat\s+ma\s+(?:chu\s+so|so\s+hoc)|cryptarithmetic)"
    r"\s*:?\s*(?P<lhs>[A-Z]{2,10}(?:\s*\+\s*[A-Z]{2,10})+)\s*=\s*(?P<rhs>[A-Z]{2,12})"
    r"(?:\s+bang\s+(?:quay\s+lui|backtracking))?\s*\.?\s*$",
    re.IGNORECASE,
)

_HORN_RE = re.compile(
    r"^\s*(?:cau\s+\d+\s*:\s*)?cho\s+(?:tap\s+)?su\s+kien(?:\s+ban\s+dau)?\s*(?:facts\s*=\s*)?(?P<facts>[\[\(\{][^\]\)\}]+[\]\)\}])"
    r"\s*(?:,|va)\s*(?:tap\s+)?luat(?:\s+horn)?\s*:?\s*(?P<rules>[A-Za-z0-9_,\s&^+\->;:]+?)"
    r"[.\s,;]+(?:hay\s+)?(?:kiem\s+tra|chung\s+minh|xac\s+dinh)\s+(?:muc\s+tieu\s+|ket\s+luan\s+)?(?P<query>['\"]?[A-Za-z0-9_]+['\"]?)"
    r"\s+bang\s+(?P<mode>suy\s+dien\s+tien|forward\s+chaining|suy\s+dien\s+lui|backward\s+chaining)\s*\.?\s*$",
    re.IGNORECASE,
)

_MAP_COLOR_RE = re.compile(
    r"^\s*(?:cau\s+\d+\s*:\s*)?(?:giai\s+)?(?:bai\s+toan\s+)?to\s+mau(?:\s+ban\s+do|\s+do\s+thi)?"
    r"\s+bang\s+simpleai(?:\s+csp)?"
    r"\s+cho\s+(?:cac\s+)?(?:vung|dinh)(?:\s+variables\s*=)?\s*(?P<vars>\[[^\]]+\])"
    r"\s+(?:voi\s+)?(?:cac\s+)?mau(?:\s+colors\s*=|\s+domains\s*=)?\s*(?P<colors>\[[^\]]+\])"
    r"\s*[.,;]\s*(?:cac\s+cap\s+(?:vung\s+|dinh\s+)?ke\s+nhau|canh(?:\s+ke)?)\s*:?\s*(?P<edges>\[.+?\])"
    r"(?:\s+voi\s+(?P<vh>mrv|degree)(?:\s*(?:\+|va)\s*(?P<valh>lcv))?)?\s*\.?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_SIMPLEAI_GRAPH_RE = re.compile(
    r"^\s*(?:cau\s+\d+\s*:\s*)?cho\s+do\s+thi(?:\s+(?P<dir>co\s+huong|vo\s+huong))?"
    r"\s+(?:gom\s+|voi\s+)?(?:cac\s+)?canh(?:\s+edges\s*=)?\s*:?\s*(?P<edges>\[.+?\])"
    r"\s*[.,;]\s*tim\s+duong(?:\s+di)?\s+tu\s+(?P<start>['\"][^'\"]+['\"])\s+den\s+(?P<goal>['\"][^'\"]+['\"])"
    r"\s+bang\s+simpleai\s+(?:voi\s+)?(?:thuat\s+toan\s+)?(?P<alg>bfs|dfs|ucs|greedy|a\*|astar)"
    r"(?:\s+(?:voi\s+|va\s+)?heuristic\s*=?\s*(?P<heur>\{[^}]+\}))?\s*\.?\s*$",
    re.IGNORECASE | re.DOTALL,
)

_FUZZY_RE = re.compile(
    r"^\s*(?:cau\s+\d+\s*:\s*)?cho\s+(?:hai\s+)?tap\s+mo\s+a\s*=\s*(?P<left>\{[^}]+\})"
    r"(?:\s*(?:,|va)\s*b\s*=\s*(?P<right>\{[^}]+\}))?"
    r"\s*[.,;]\s*(?:hay\s+)?tinh\s+(?P<op>hop|giao|phan\s+bu|lat\s+cat\s+alpha\s*=\s*(?P<alpha>[0-9]+(?:\.[0-9]+|/[0-9]+)?))\s*\.?\s*$",
    re.IGNORECASE,
)


def _safe_eval(snippet: str) -> Any:
    return ast.literal_eval(snippet.strip())


def parse_natural_vietnamese_problem(raw_text: str) -> Optional[Dict[str, Any]]:
    text = normalize_pdf_code_artifacts(raw_text).strip()
    if not text:
        return None
    folded = strip_accents(text)
    collapsed = re.sub(r"\s+", " ", folded).strip()

    # 1. Dynamic Cryptarithmetic (SEND + MORE = MONEY, BASE + BALL = GAMES, ...)
    m_crypt = _CRYPT_RE.match(collapsed)
    if m_crypt and "bien nho" not in collapsed.casefold():
        # Extract uppercase tokens from the accent-stripped original
        rhs_orig = m_crypt.group("rhs").upper()
        lhs_orig = [w.strip().upper() for w in m_crypt.group("lhs").split("+")]
        letters = set("".join(lhs_orig) + rhs_orig)
        if 2 <= len(lhs_orig) <= 6 and len(letters) <= 10:
            return {"type": "cryptarithm", "addends": lhs_orig, "result": rhs_orig, "base": 10}

    # 2. Horn Forward / Backward Chaining with explicit facts & rules
    m_horn = _HORN_RE.match(collapsed)
    if m_horn:
        try:
            # Recover slice from original text if lengths match; symbols in Horn rules are ASCII identifiers
            raw_facts = _safe_eval(m_horn.group("facts"))
            if not isinstance(raw_facts, (list, tuple, set)):
                return None
            facts = [str(f).strip() for f in raw_facts if str(f).strip()]
            rules: List[Dict[str, Any]] = []
            for clause in re.split(r"[;\n]+|,\s*(?=[A-Za-z0-9_]+\s*(?:[&^+]|\->))", m_horn.group("rules")):
                clause = clause.strip()
                if not clause:
                    continue
                clause = re.sub(r"^R\d+\s*:\s*", "", clause, flags=re.IGNORECASE)
                if "->" not in clause:
                    return None
                lhs_part, rhs_part = clause.split("->", 1)
                premises = [p.strip() for p in re.split(r"\s*(?:&|\^|\+|\bva\b)\s*", lhs_part.strip()) if p.strip()]
                conclusion = rhs_part.strip()
                if not premises or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", conclusion):
                    return None
                if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p) for p in premises):
                    return None
                rules.append({"if": premises, "then": conclusion})
            query = m_horn.group("query").strip().strip("'\"")
            mode_str = m_horn.group("mode").casefold()
            solver_type = "backward_horn" if ("lui" in mode_str or "backward" in mode_str) else "horn"
            if facts and rules and query:
                return {"type": solver_type, "facts": facts, "rules": rules, "query": query}
        except (ValueError, SyntaxError):
            return None

    # 3. SimpleAI Map Coloring CSP
    if len(text) == len(folded):
        m_map = _MAP_COLOR_RE.match(folded)
    else:
        m_map = None
        # Map offsets back to original text so Vietnamese color names keep accents
        offsets = [idx for idx, ch in enumerate(text) for _ in strip_accents(ch)] + [len(text)]
        cand_m = _MAP_COLOR_RE.match(folded)
        if cand_m:
            m_map = cand_m
    if m_map:
        offsets = (
            list(range(len(text) + 1))
            if len(text) == len(folded)
            else [idx for idx, ch in enumerate(text) for _ in strip_accents(ch)] + [len(text)]
        )
        try:
            vs, ve = m_map.span("vars")
            cs, ce = m_map.span("colors")
            es, ee = m_map.span("edges")
            nodes = _safe_eval(text[offsets[vs]:offsets[ve]])
            colors = _safe_eval(text[offsets[cs]:offsets[ce]])
            edges = _safe_eval(text[offsets[es]:offsets[ee]])
            if (
                isinstance(nodes, (list, tuple))
                and isinstance(colors, (list, tuple))
                and isinstance(edges, (list, tuple))
                and nodes and colors
            ):
                domains = {str(n): list(colors) for n in nodes}
                constraints = [{"op": "ne", "vars": [str(u), str(v)]} for u, v in edges]
                spec: Dict[str, Any] = {"type": "simpleai_csp", "domains": domains, "constraints": constraints}
                if m_map.group("vh"):
                    spec["variable_heuristic"] = m_map.group("vh").lower()
                if m_map.group("valh"):
                    spec["value_heuristic"] = m_map.group("valh").lower()
                return spec
        except (ValueError, SyntaxError, TypeError):
            return None

    # 4. SimpleAI Graph Search
    m_graph = _SIMPLEAI_GRAPH_RE.match(folded)
    if m_graph:
        offsets = (
            list(range(len(text) + 1))
            if len(text) == len(folded)
            else [idx for idx, ch in enumerate(text) for _ in strip_accents(ch)] + [len(text)]
        )
        try:
            es, ee = m_graph.span("edges")
            ss, se = m_graph.span("start")
            gs, ge = m_graph.span("goal")
            edges_raw = _safe_eval(text[offsets[es]:offsets[ee]])
            start_node = _safe_eval(text[offsets[ss]:offsets[se]])
            goal_node = _safe_eval(text[offsets[gs]:offsets[ge]])
            alg = m_graph.group("alg").lower()
            if alg == "a*":
                alg = "astar"
            dir_tok = (m_graph.group("dir") or "").casefold()
            directed = False if "vo huong" in dir_tok else True
            edges_norm = [list(e) for e in edges_raw]
            spec = {
                "type": "simpleai_graph",
                "start": start_node,
                "goals": [goal_node],
                "edges": edges_norm,
                "algorithm": alg,
                "directed": directed,
            }
            if m_graph.group("heur"):
                hs, he = m_graph.span("heur")
                spec["heuristic"] = _safe_eval(text[offsets[hs]:offsets[he]])
            return spec
        except (ValueError, SyntaxError, TypeError):
            return None

    # 5. Fuzzy Set Operations
    m_fuzzy = _FUZZY_RE.match(folded)
    if m_fuzzy:
        offsets = (
            list(range(len(text) + 1))
            if len(text) == len(folded)
            else [idx for idx, ch in enumerate(text) for _ in strip_accents(ch)] + [len(text)]
        )
        try:
            ls, le = m_fuzzy.span("left")
            left_dict = {str(k): str(v) for k, v in _safe_eval(text[offsets[ls]:offsets[le]]).items()}
            op_raw = re.sub(r"\s+", " ", m_fuzzy.group("op").casefold()).strip()
            if op_raw == "hop" and m_fuzzy.group("right"):
                rs, re_idx = m_fuzzy.span("right")
                right_dict = {str(k): str(v) for k, v in _safe_eval(text[offsets[rs]:offsets[re_idx]]).items()}
                return {"type": "fuzzy_set", "operation": "union", "left": left_dict, "right": right_dict}
            if op_raw == "giao" and m_fuzzy.group("right"):
                rs, re_idx = m_fuzzy.span("right")
                right_dict = {str(k): str(v) for k, v in _safe_eval(text[offsets[rs]:offsets[re_idx]]).items()}
                return {"type": "fuzzy_set", "operation": "intersection", "left": left_dict, "right": right_dict}
            if op_raw == "phan bu" and not m_fuzzy.group("right"):
                return {"type": "fuzzy_set", "operation": "complement", "left": left_dict}
            if m_fuzzy.group("alpha") and not m_fuzzy.group("right"):
                return {
                    "type": "fuzzy_set",
                    "operation": "alpha_cut",
                    "left": left_dict,
                    "alpha": m_fuzzy.group("alpha"),
                }
        except (ValueError, SyntaxError, TypeError, AttributeError):
            return None

    return None
