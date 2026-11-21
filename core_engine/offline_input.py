"""Convert fully recognized text formats into offline problem specifications."""

import ast
import json
import re

from .golden_skeletons import strip_accents

__all__ = ["read_known_format"]

_BOARD = r"[\[\(0-8][\[\]\(\)0-8,\s]{7,80}"
_PUZZLE_PROMPT = re.compile(
    r"(?:(?:cho|giai)\s+)?(?:bai toan\s+)?8[ -]?puzzle"
    r"(?:\s+bang\s+a\*(?:\s+voi\s+(?:khoang cach\s+)?manhattan)?)?[.\s,;:]+"
    r"(?:trang thai )?(?:ban dau|dau)\s*:?\s*(?P<start>" + _BOARD + r")"
    r"[.\s,;]+(?:(?:trang thai )?dich|muc tieu)\s*:?\s*(?P<goal>" + _BOARD + r")[.\s]*"
)
_MINIMAX_PROMPT = re.compile(
    r"(?:(?:tinh|danh gia)\s+)?cay\s+(?P<algorithm>minimax|alpha[- ]beta)"
    r"[,\s]+goc\s+(?P<root>min|max)\s*:\s*(?P<tree>\[[\[\]\s,0-9-]+\])[.\s]*"
)
_FIBONACCI_PROMPT = re.compile(
    r"(?:in|liet ke|tao)\s+(?P<count>[0-9]{1,3})\s+(?:so|phan tu)\s+fibonacci"
    r"(?:\s+dau tien)?(?:[,\s]+bat dau(?:\s+tu)?\s*:?[\s]*(?P<a>-?[0-9]{1,12})[\s,]+(?P<b>-?[0-9]{1,12}))?[.\s]*"
)
_QUEENS_PROMPT = re.compile(
    r"(?P<action>dem(?: so)?(?: cach xep| cau hinh)?|giai|xep)\s+"
    r"(?:bai toan\s+)?(?P<n>[0-9]{1,2})\s+quan hau"
    r"(?:\s+tren ban co (?P<rows>[0-9]{1,2})\s*[x×]\s*(?P<cols>[0-9]{1,2}))?"
    r"(?:\s+bang\s+(?:quay lui|backtracking))?[.\s]*"
)
_PARITY_PROMPT = re.compile(
    r"tinh tong (?:cac )?so chan va (?:tong )?(?:cac )?so le"
    r"\s+(?:trong\s+)?(?:danh sach\s*)?:?\s*(?P<items>\[[\s0-9,-]*\])[.\s]*"
)
_PRIMES_PROMPT = re.compile(r"(?:in|liet ke|tim)\s+(?P<count>[0-9]{1,4})\s+so nguyen to dau tien[.\s]*")


def _board(text):
    if re.fullmatch(r"[0-8]{9}", text):
        return [int(tile) for tile in text]
    value = ast.literal_eval(text)
    if isinstance(value, (tuple, list)):
        if len(value) == 3 and all(isinstance(row, (tuple, list)) and len(row) == 3 for row in value):
            return [tile for row in value for tile in row]
        return list(value)
    raise ValueError("Board must be a sequence")


def _dimacs(text):
    lines = [
        words for line in text.splitlines()
        if (words := line.split()) and words[0] != "c"
    ]
    if not lines or lines[0][:2] != ["p", "cnf"]:
        return None
    if len(lines[0]) != 4 or any(not re.fullmatch(r"[0-9]{1,6}", count) for count in lines[0][2:]):
        raise ValueError("Tiêu đề DIMACS cần dạng p cnf <số biến> <số mệnh đề>.")
    num_variables, num_clauses = map(int, lines[0][2:])
    clause = []
    clauses = []
    for line in lines[1:]:
        for token in line:
            if not re.fullmatch(r"(?:0|-?[1-9][0-9]{0,5})", token):
                raise ValueError("DIMACS cần literal nguyên và số 0 kết thúc mỗi mệnh đề.")
            value = int(token)
            if value:
                clause.append(value)
            else:
                clauses.append(clause)
                clause = []
    if clause or len(clauses) != num_clauses:
        raise ValueError("Số mệnh đề DIMACS hoặc dấu 0 kết thúc chưa khớp với tiêu đề.")
    return {"type": "sat", "variables": num_variables, "clauses": clauses}


def read_known_format(text):
    dimacs = _dimacs(text)
    if dimacs is not None:
        return dimacs
    normalized = re.sub(r"\s+", " ", strip_accents(text).casefold()).strip()
    match = _PUZZLE_PROMPT.fullmatch(normalized)
    if match:
        try:
            return {
                "type": "sliding_puzzle",
                "start": _board(match["start"].strip()),
                "goal": _board(match["goal"].strip()),
                "algorithm": "astar",
            }
        except (ValueError, SyntaxError):
            raise ValueError("Bảng 8-puzzle cần 9 ô hoặc ba hàng, mỗi hàng 3 ô.") from None
    match = _MINIMAX_PROMPT.fullmatch(normalized)
    if match:
        return {
            "type": "minimax",
            "root": match["root"],
            "algorithm": "minimax" if match["algorithm"] == "minimax" else "alpha_beta",
            "tree": json.loads(match["tree"]),
        }
    match = _FIBONACCI_PROMPT.fullmatch(normalized)
    if match:
        problem = {"type": "fibonacci", "count": int(match["count"])}
        if match["a"] is not None:
            problem["initial"] = [int(match["a"]), int(match["b"])]
        return problem
    match = _QUEENS_PROMPT.fullmatch(normalized)
    if match:
        n = int(match["n"])
        if match["rows"] is not None and (int(match["rows"]) != n or int(match["cols"]) != n):
            raise ValueError("Số hậu cần khớp với hai chiều bàn cờ trong dạng N hậu.")
        return {"type": "nqueens", "n": n, "mode": "count" if match["action"].startswith("dem") else "first"}
    match = _PARITY_PROMPT.fullmatch(normalized)
    if match:
        return {"type": "parity_sum", "values": json.loads(match["items"])}
    match = _PRIMES_PROMPT.fullmatch(normalized)
    if match:
        return {"type": "primes", "count": int(match["count"])}
    return None
