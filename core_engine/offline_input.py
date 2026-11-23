"""Convert fully recognized text formats into offline problem specifications."""

import ast
import json
import re

from .golden_skeletons import strip_accents
from .offline_course_prompts import read_course_prompt

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
_SIMPLEAI_QUEENS = re.compile(
    r"(?:giai|xep)\s+(?:bai toan\s+)?(?P<n>[0-9]{1,2})\s+quan hau"
    r"(?:\s+tren ban co (?P<rows>[0-9]{1,2})\s*[x×]\s*(?P<cols>[0-9]{1,2}))?"
    r"\s+bang\s+(?:simpleai|(?:backtrack(?:ing)?|quay lui) (?:cua|voi) simpleai)"
    r"(?:\s+voi\s+(?P<variable>mrv|degree)(?:\s*(?:\+|va)\s*(?P<value>lcv))?)?[.\s]*"
)


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


def _geometry_class_prompt(text):
    """Read the whole request for the two supported class exercises."""
    normalized = re.sub(r"\s+", " ", strip_accents(text).casefold()).strip()
    normalized = normalized.replace("`", "")
    normalized = re.sub(r"\\(?:left|right)(?=\\?\|)", "", normalized)
    normalized = normalized.replace(r"\|", "||").replace(r"\lvert", "||").replace(r"\rvert", "||")
    vector = re.fullmatch(
        r"(?:de bai yeu cau\s+)?(?:viet|tao)\s+(?:mot\s+)?lop\s+vector24"
        r"\s+(?:bieu dien\s+)?(?:vector|vec to|vecto)\s+24\s+chieu"
        r"(?:\s+bang python(?: thuan)?)?[,.:\s]+"
        r"(?:(?:co|voi cac yeu cau)\s*:\s*)?"
        r"[-•\s]*cong\s+(?:2|hai)\s+(?:vector|vecto|vec to)"
        r"(?:\s*\(v1\s*\+\s*v2\))?[.;\s]+"
        r"[-•\s]*tich vo huong"
        r"(?:\s*\(v1\s*[·⋅.]\s*v2\s*=\s*tong tich tung cap toa do tuong ung"
        r"(?::\s*\$?a_\{?1\}?\s*b_\{?1\}?(?:\s*\+\s*a_\{?2\}?\s*b_\{?2\}?)?"
        r"\s*\+\s*(?:\\cdots|\\dots|\\ldots|…|\.\.\.)(?:\s*\+\s*a_\{?24\}?\s*b_\{?24\}?)?\$?)?\))?[.;\s]+"
        r"[-•\s]*goc giua\s+(?:2|hai)\s+(?:vector|vecto|vec to)"
        r"(?:\s*\(tinh tu cong thuc\s+\$?\\cos\s*\\theta\s*=\s*"
        r"\\frac\{\\vec\{u\}\s*\\cdot\s*\\vec\{v\}\}"
        r"\{(?:\|\||\\lvert)\\vec\{u\}(?:\|\||\\rvert)"
        r"\s*(?:\|\||\\lvert)\\vec\{v\}(?:\|\||\\rvert)\}\$?[.,;\s]+sau do)?"
        r"(?:\s+dung)?\s+(?:math\.acos\s+de ra goc\s+(?:tinh\s+)?)?"
        r"(?:bang|theo)\s+radian\)?[.\s]*",
        normalized,
    )
    if vector:
        return {"type": "vector24"}

    point = re.fullmatch(
        r"(?:bai\s+[0-9]+(?:\.[0-9]+)*\s*:\s*lop diem3d"
        r"\s*\(diem trong khong gian 3 chieu\)\s*)?"
        r"(?:viet|tao)\s+(?:mot\s+)?lop diem3d bang python(?: thuan)?"
        r"(?:\s*\(import math\))?\s*voi cac yeu cau\s*:\s*[-•\s]*"
        r"__init__\(self,\s*x,\s*y,\s*z\)\s*:\s*chuyen x,\s*y,\s*z sang kieu float\."
        r"\s*neu gia tri khong phai so\s*\(hoac khong chuyen duoc sang float\),"
        r"\s*bao loi phu hop\s*\(typeerror hoac valueerror\)\.[\s-]*"
        r"khoang_cach_goc\(self\)\s*:\s*tinh khoang cach euclid tu diem toi goc toa do"
        r"\s*\$?\(0,\s*0,\s*0\)\$?"
        r"(?:,\s*cong thuc:\s*\$+d\s*=\s*\\sqrt\{x\^2\s*\+\s*y\^2\s*\+\s*z\^2\}\$+)?[.\s]*",
        normalized,
    )
    if point:
        return {"type": "diem3d"}

    return None


def read_known_format(text):
    course_problem = read_course_prompt(text)
    if course_problem is not None:
        return course_problem
    dimacs = _dimacs(text)
    if dimacs is not None:
        return dimacs
    geometry = _geometry_class_prompt(text)
    if geometry is not None:
        return geometry
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
    match = _SIMPLEAI_QUEENS.fullmatch(normalized)
    if match:
        n = int(match["n"])
        if match["rows"] is not None and (int(match["rows"]) != n or int(match["cols"]) != n):
            raise ValueError("Số hậu cần khớp với hai chiều bàn cờ trong dạng N hậu.")
        problem = {"type": "simpleai_nqueens", "n": n}
        if match["variable"]:
            problem["variable_heuristic"] = match["variable"]
        if match["value"]:
            problem["value_heuristic"] = match["value"]
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
