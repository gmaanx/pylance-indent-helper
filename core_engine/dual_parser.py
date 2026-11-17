# -*- coding: utf-8 -*-
"""
Module 1: Dual-Parser (Bo phan tich dau vao da che do).
Ho tro:
1. Copy thang de thi tu PDF/Word/LMS vao comment `# ...` hoac `\"\"\" ... \"\"\"` (Che do chinh).
2. Shorthand DSL (`@search`, `@raw`, `@local`, `@csp`, `@game`, `@logic`) phan hoi < 0.05s.
3. Inline Stealth Config (`# @cfg gemini:AIza... groq:gsk_...`).
4. Tu dong tach phan comment de bai va phan code khung co san trong file de thi.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
}


@dataclass
class ParsedInput:
    mode: str  # "cfg" | "dsl" | "natural" | "self_fix"
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
    "kq:",
    "===",
    "---",
)


def _is_system_status_comment(line_content: str) -> bool:
    low = line_content.strip().lower()
    if not low:
        return True
    return any(low.startswith(prefix) for prefix in _IGNORED_COMMENT_PREFIXES)


def _extract_comments_and_code(raw_text: str) -> Tuple[str, str]:
    """
    Tách phần đề bài trong `\"\"\" yêu cầu \"\"\"`, `''' yêu cầu '''` hoặc `# yêu cầu`
    và phần code Python có sẵn.
    Hỗ trợ đầy đủ:
    - `\"\"\" yêu cầu \"\"\"` trên 1 dòng hoặc nhiều dòng (kể cả khi đặt đầu file, giữa file, cuối file).
    - `''' yêu cầu '''` trên 1 dòng hoặc nhiều dòng.
    - `# yêu cầu` trên 1 dòng hoặc nhiều dòng.
    - Văn bản thuần copy từ PDF/Word/LMS chưa có dấu `#` hay `\"\"\"`.
    """
    text = raw_text.strip()
    if not text:
        return "", ""

    docstring_prompts: List[str] = []

    # 1. Bat moi khoi """ ... """ hoac ''' ... ''' (ke ca 1 dong hay nhieu dong)
    triple_pattern = re.compile(r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')')
    for match in triple_pattern.finditer(text):
        full_box = match.group(0)
        inner = full_box[3:-3].strip()
        if inner and not inner.lower().startswith("module "):
            docstring_prompts.append(inner)

    # Xoa cac khoi triple-quoted da bat khoi van ban de phan tich tiep # va code
    remaining_text = triple_pattern.sub("", text)

    # Ho tro truong hop nguoi dung mo """ yeu cau nhung quen dong """ o cuoi file
    for open_delim in ('"""', "'''"):
        if open_delim in remaining_text:
            parts = remaining_text.split(open_delim, 1)
            remaining_text = parts[0]
            unclosed_inner = parts[1].strip()
            if unclosed_inner:
                docstring_prompts.append(unclosed_inner)

    lines = remaining_text.splitlines()
    hash_comment_lines: List[str] = []
    code_lines: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            cleaned_comment = re.sub(r"^#+\s?", "", stripped).strip()
            if not _is_system_status_comment(cleaned_comment):
                hash_comment_lines.append(cleaned_comment)
        else:
            code_lines.append(line)

    code_block = "\n".join(code_lines).strip()

    # Neu co """ yeu cau """ hoac ''' yeu cau ''', uu tien lay """ yeu cau """
    # (Chi kem them dong # neu dong # do chua lenh @cfg hoac @search/@csp/...)
    combined_comments: List[str] = []
    if docstring_prompts:
        # Lay khoi """ yeu cau """ moi nhat (hoac tat ca khoi docstring nguoi dung viet)
        combined_comments.append("\n".join(docstring_prompts))
        for hc in hash_comment_lines:
            if "@" in hc:
                combined_comments.append(hc)
    elif hash_comment_lines:
        combined_comments.append("\n".join(hash_comment_lines))

    comment_block = "\n".join(combined_comments).strip()

    # Neu khong co '#' hay '"""' nhung van ban la de thi tu nhien (copy thang tu PDF/Word/Web)
    if not comment_block and code_block:
        python_indicators = (
            "import ", "from ", "class ", "def ", "if __name__", "print(", "return "
        )
        has_py_keyword = any(ind in code_block for ind in python_indicators)
        if not has_py_keyword:
            return code_block, ""

    return comment_block, code_block


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
    if not cleaned_raw:
        return ParsedInput(mode="natural", raw_input="", prompt_text="")

    comment_text, existing_code = _extract_comments_and_code(cleaned_raw)
    effective_prompt = comment_text if comment_text else cleaned_raw

    # 1. Kiem tra lenh cau hinh ngam: # @cfg gemini:AIza...
    m_cfg = re.search(r"@cfg\b(.*)$", effective_prompt, re.IGNORECASE | re.MULTILINE)
    if m_cfg:
        cfg_params = _parse_key_value_tokens(m_cfg.group(1))
        return ParsedInput(
            mode="cfg",
            raw_input=cleaned_raw,
            prompt_text=effective_prompt,
            dsl_params=cfg_params,
        )

    # 2. Neu ep che do Self-Fix (Alt + 4) va co code Python de sua
    if force_mode == "self_fix" and existing_code.strip():
        return ParsedInput(
            mode="self_fix",
            raw_input=cleaned_raw,
            prompt_text=comment_text,
            existing_code=existing_code,
        )

    # 3. Kiem tra Shorthand DSL (@search, @raw, @local, @csp, @game, @logic)
    m_dsl = re.search(
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
