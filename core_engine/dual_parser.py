# -*- coding: utf-8 -*-
"""
Module 1: Dual-Parser (Bo phan tich dau vao da che do).
Ho tro:
1. Copy thang de thi tu PDF/Word/LMS vao comment `# ...` hoac `\"\"\" ... \"\"\"` (Che do chinh).
2. Shorthand DSL (`@search`, `@raw`, `@local`, `@csp`, `@game`, `@logic`) phan hoi < 0.05s.
3. Inline Stealth Config (`# @cfg gemini:AIza... groq:gsk_...`).
4. Tu dong tach phan comment de bai va phan code khung co san trong file de thi.
"""

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .golden_skeletons import strip_accents


DSL_TAG_TO_CATEGORY = {
    "@search": "search",
    "@s": "search",
    "@raw": "raw",
    "@r": "raw",
    "@local": "local",
    "@l": "local",
    "@csp": "csp",
    "@c": "csp",
    "@game": "game",
    "@g": "game",
    "@logic": "logic",
    "@kanren": "logic",
}

BAI_ALIAS_TO_SKELETON = {
    "8puzzle": "search_8puzzle_astar",
    "8_puzzle": "search_8puzzle_astar",
    "eight_puzzle": "search_8puzzle_astar",
    "sinh_xau": "search_string_gen",
    "string": "search_string_gen",
    "hello": "search_string_gen",
    "dong_nuoc": "search_water_jugs",
    "water_jugs": "search_water_jugs",
    "jugs": "search_water_jugs",
    "qua_song": "search_river_crossing",
    "river": "search_river_crossing",
    "me_cung": "search_maze_grid",
    "maze": "search_maze_grid",
    "grid": "search_maze_grid",
    "do_thi": "search_graph_simpleai",
    "romania": "search_graph_simpleai",
    "graph": "search_graph_simpleai",
    "tsp": "search_tsp",
    "hanoi": "search_hanoi",
    "thap_ha_noi": "search_hanoi",
    "nut": "raw_graph_search",
    "gamma": "raw_graph_search",
    "cai_chay": "raw_graph_search",
    "nqueens": "local_nqueens",
    "quan_hau": "local_nqueens",
    "5quanhau": "local_nqueens",
    "8quanhau": "local_nqueens",
    "8puzzle_genetic": "local_8puzzle_genetic",
    "puzzle_genetic": "local_8puzzle_genetic",
    "cai_tui": "local_knapsack",
    "knapsack": "local_knapsack",
    "tsp_local": "local_tsp",
    "nqueens_csp": "csp_nqueens_hybrid",
    "quan_hau_csp": "csp_nqueens_hybrid",
    "to_mau": "csp_map_coloring",
    "map_coloring": "csp_map_coloring",
    "mat_ma": "csp_cryptarithmetic",
    "send_more_money": "csp_cryptarithmetic",
    "cryptarithmetic": "csp_cryptarithmetic",
    "magic_square": "csp_magic_square",
    "ma_phuong": "csp_magic_square",
    "xep_lich": "csp_scheduling",
    "schedule": "csp_scheduling",
    "zebra": "kanren_zebra_puzzle",
    "puzzle": "kanren_zebra_puzzle",
    "family": "kanren_family",
    "gia_pha": "kanren_family",
    "gia_dinh": "kanren_family",
    "states": "kanren_states_map",
    "bang": "kanren_states_map",
    "prime": "kanren_prime",
    "so_nguyen_to": "kanren_prime",
    "expression": "kanren_expression_matcher",
    "bieu_thuc": "kanren_expression_matcher",
    "chaining": "logic_chaining",
    "suy_dien": "logic_chaining",
    "minimax": "game_minimax_alphabeta_tree",
    "alphabeta": "game_minimax_alphabeta_tree",
    "alpha_beta": "game_minimax_alphabeta_tree",
    "tictactoe": "game_tictactoe",
    "caro": "game_tictactoe",
    "nim": "game_nim",
    "hut_bui": "search_vacuum_world",
    "vacuum": "search_vacuum_world",
    "thieu_cam_nhan": "search_sensorless_vacuum",
    "sensorless": "search_sensorless_vacuum",
    "env": "env_vacuum_agent",
    "cay": "search_tree_abc_slide",
    "tree": "search_tree_abc_slide",
    "8puzzle_local": "local_8puzzle_hill_climbing",
    "8puzzle_hc": "local_8puzzle_hill_climbing",
    "15puzzle": "search_15puzzle",
    "npuzzle": "search_15puzzle",
    "nhieu_dich": "search_multi_goal_grid",
    "multi_goal": "search_multi_goal_grid",
    "quan_ma": "search_knight_path",
    "knight": "search_knight_path",
    "soi_de_bap_cai": "search_wolf_goat_cabbage",
    "wolf_goat_cabbage": "search_wolf_goat_cabbage",
    "doi_tien": "search_coin_change",
    "coin": "search_coin_change",
    "he_pt": "csp_numeric_equations",
    "equations": "csp_numeric_equations",
    "ac3": "csp_convert_to_binary_ac3",
    "two_four": "csp_two_plus_two_carry",
    "sudoku": "csp_sudoku",
    "job": "csp_job_scheduling",
    "bang_chan_ly": "logic_truth_table",
    "truth_table": "logic_truth_table",
    "hop_giai": "logic_cnf_resolution",
    "resolution": "logic_cnf_resolution",
    "sat": "logic_sat_csp_local",
    "walksat": "logic_sat_csp_local",
    "id3": "ml_classifiers_simpleai",
    "decision_tree": "ml_classifiers_simpleai",
    "knn": "ml_classifiers_simpleai",
    "qlearning": "ml_reinforcement_simpleai",
    "rl": "ml_reinforcement_simpleai",
    "ontology": "ontology_tbox_abox_simpleai",
    "tbox": "ontology_tbox_abox_simpleai",
    "frame": "frame_inheritance_conflict",
    "khung": "frame_inheritance_conflict",
    "backward": "logic_backward_chaining_hybrid",
    "suy_dien_lui": "logic_backward_chaining_hybrid",
    "bayes": "prob_joint_conditional_bayes",
    "xac_suat": "prob_joint_conditional_bayes",
    "mang_bayes": "prob_bayesian_network_cpt",
    "cpt": "prob_bayesian_network_cpt",
    "tap_mo": "fuzzy_sets_inference",
    "fuzzy": "fuzzy_sets_inference",
    "vector24": "oop_vector24_cosine_plagiarism",
    "nut_tim_kiem": "oop_search_node_nuttimkiem",
    "nuttimkiem": "oop_search_node_nuttimkiem",
}


@dataclass
class ParsedInput:
    mode: str  # "cfg" | "structured" | "dsl" | "natural" | "self_fix"
    raw_input: str
    prompt_text: str
    existing_code: str = ""
    category: Optional[str] = None
    target_skeleton_id: Optional[str] = None
    dsl_params: Dict[str, str] = field(default_factory=dict)


_IGNORED_COMMENT_PREFIXES = (
    "-*- coding",
    "[alt+",
    "[dang ",
)
_PROSE_HEADING = re.compile(r"^(?:bai\s+[0-9]+(?:\.[0-9]+)*\s*:|de bai\b|(?:viet|tao)(?: mot)? lop\b)")


def _is_system_status_comment(line_content: str) -> bool:
    low = line_content.strip().lower()
    if not low or all(character in "=- " for character in low):
        return True
    return any(low.startswith(prefix) for prefix in _IGNORED_COMMENT_PREFIXES)


def _extract_comments_and_code(raw_text: str) -> Tuple[str, str]:
    """Extract comment or standalone quoted requests without stripping code strings."""
    lines = raw_text.splitlines()
    descriptions: List[Tuple[int, str]] = []
    prompt_lines = set()
    if re.match(r"^@solve\b", raw_text, re.IGNORECASE):
        return raw_text, ""

    # A pasted request may start with prose and continue with comment bullets.
    # Keep the original ordering in that case so every requirement is matched.
    if _PROSE_HEADING.match(strip_accents(lines[0]).casefold()):
        return "\n".join(line.lstrip().lstrip("#").strip() for line in lines).strip(), ""

    try:
        bracket_depth = 0
        for token in tokenize.generate_tokens(io.StringIO(raw_text).readline):
            kind, value, (row, column), (end_row, end_column), _ = token
            if kind == tokenize.OP and value in ("(", "[", "{"):
                bracket_depth += 1
            elif kind == tokenize.OP and value in (")", "]", "}"):
                bracket_depth -= 1
            elif kind == tokenize.COMMENT and column == 0 and bracket_depth == 0:
                comment = value.lstrip("#").strip()
                if not _is_system_status_comment(comment):
                    descriptions.append((row, comment))
                prompt_lines.add(row)
            elif (
                kind == tokenize.STRING and column == 0 and bracket_depth == 0
                and value.startswith(('"""', "'''"))
                and not lines[end_row - 1][end_column:].strip()
            ):
                quote = value[:3]
                if value.endswith(quote) and len(value) >= 6:
                    descriptions.append((row, value[3:-3].strip()))
                    prompt_lines.update(range(row, end_row + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Keep unparsed source intact for the syntax checker or the model.
        pass

    prompt = "\n".join(text for _, text in sorted(descriptions)).strip()
    existing_code = "\n".join(line for row, line in enumerate(lines, 1) if row not in prompt_lines).strip()
    if not prompt and existing_code:
        try:
            ast.parse(existing_code)
        except (SyntaxError, ValueError, RecursionError):
            return existing_code, ""
    return prompt, existing_code


def _parse_key_value_tokens(line: str) -> Dict[str, str]:
    params: Dict[str, str] = {}
    for match in re.finditer(r"([a-zA-Z0-9_]+):([^\s]+)", line):
        params[match.group(1).lower()] = match.group(2).strip()
    return params


def parse_user_input(raw_text: str, force_mode: Optional[str] = None) -> ParsedInput:
    """
    Phân tích chuỗi đầu vào từ Editor hoặc Clipboard.
    """
    cleaned_raw = (raw_text or "").strip()
    if cleaned_raw.startswith("```") and cleaned_raw.endswith("```"):
        cleaned_raw = cleaned_raw[3:-3].strip()
        if cleaned_raw.lower().startswith("json"):
            cleaned_raw = cleaned_raw[4:].lstrip()
    if not cleaned_raw:
        return ParsedInput(mode="natural", raw_input="", prompt_text="")

    comment_text, existing_code = _extract_comments_and_code(cleaned_raw)
    effective_prompt = comment_text or ("" if existing_code else cleaned_raw)

    if re.match(r"^@solve\b", effective_prompt, re.IGNORECASE):
        return ParsedInput(
            mode="structured",
            raw_input=cleaned_raw,
            prompt_text=effective_prompt,
            existing_code=existing_code,
        )

    m_cfg = re.match(r"@cfg\b(.*)$", effective_prompt, re.IGNORECASE | re.MULTILINE)
    if m_cfg:
        cfg_params = _parse_key_value_tokens(m_cfg.group(1))
        return ParsedInput(
            mode="cfg",
            raw_input=cleaned_raw,
            prompt_text=effective_prompt,
            dsl_params=cfg_params,
        )

    # 2. Neu ep che do Self-Fix (Alt + 4) va co code Python de sua
    has_code_to_fix = existing_code.strip() or (
        not cleaned_raw.startswith(("#", '"""', "'''")) and comment_text == cleaned_raw
        and not _PROSE_HEADING.match(strip_accents(cleaned_raw).casefold())
    )
    if force_mode == "self_fix" and has_code_to_fix:
        return ParsedInput(
            mode="self_fix",
            raw_input=cleaned_raw,
            prompt_text=comment_text,
            existing_code=cleaned_raw,
        )

    # 3. Kiem tra Shorthand DSL (@search, @raw, @local, @csp, @game, @logic)
    m_dsl = re.match(
        r"(@(?:search|raw|local|csp|game|logic|kanren|s|r|l|c|g))\b(.*)$",
        effective_prompt,
        re.IGNORECASE | re.MULTILINE,
    )
    if m_dsl:
        tag = m_dsl.group(1).lower()
        rest = m_dsl.group(2).strip()
        category = DSL_TAG_TO_CATEGORY.get(tag, "search")
        kv = _parse_key_value_tokens(rest)

        # Ho tro positional token neu nguoi dung go ngan: # @s 8puzzle
        tokens = [t for t in rest.split() if ":" not in t]
        if tokens and "bai" not in kv:
            kv["bai"] = tokens[0].lower()
        if len(tokens) >= 2 and "thuat_toan" not in kv:
            kv["thuat_toan"] = tokens[1].lower()

        bai_key = kv.get("bai", "").lower()
        skeleton_id = BAI_ALIAS_TO_SKELETON.get(bai_key)

        return ParsedInput(
            mode="dsl",
            raw_input=cleaned_raw,
            prompt_text=effective_prompt,
            existing_code=existing_code,
            category=category,
            target_skeleton_id=skeleton_id,
            dsl_params=kv,
        )

    # 4. Mac dinh: De thi tu nhien copy thang vao # (Natural Language Exam Prompt)
    return ParsedInput(
        mode="natural",
        raw_input=cleaned_raw,
        prompt_text=effective_prompt,
        existing_code=existing_code,
    )
