# -*- coding: utf-8 -*-
"""
Static AST API Contract Checker & Semantic Output Validator.
Prevents 0-point auto-grader failures caused by:
1. Renaming or omitting required classes, functions, or `(self, ...)` methods specified in the prompt or `# TODO` template.
2. Printing `None` (forgotten `return`), empty stdout, or placeholder text on Shadow Run.
"""

from __future__ import annotations

import ast
import re
import warnings
from typing import Dict, List, Optional, Set, Tuple

from .golden_skeletons import strip_accents
from .runnable_output import prompt_forbids_print

_CLASS_REQ_RE = re.compile(
    r"\b(?:viet|tao|xay\s+dung|cai\s+dat|dinh\s+nghia)\s+(?:mot\s+)?lop\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\b",
    re.IGNORECASE,
)
_FUNC_REQ_RE = re.compile(
    r"\b(?:(?:viet|tao|xay\s+dung|cai\s+dat|dinh\s+nghia)\s+)?ham(?:\s+python(?:\s+thuan)?)?\s+`?([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
_METHOD_SELF_RE = re.compile(
    r"`?([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*self\b",
)
_IGNORED_NAMES = {
    "SearchProblem", "CspProblem", "Environment", "RLEnvironment",
    "Python", "main", "heuristic", "danh_gia", "kiem_tra", "func", "f", "g", "h",
}


def _extract_balanced_parens(text: str, open_paren_idx: int) -> Optional[str]:
    if open_paren_idx < 0 or open_paren_idx >= len(text) or text[open_paren_idx] != "(":
        return None
    depth = 0
    in_q: Optional[str] = None
    esc = False
    for idx in range(open_paren_idx, min(len(text), open_paren_idx + 300)):
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
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren_idx + 1 : idx]
    return None


def _count_signature_params(sig_inner: str) -> Optional[Tuple[int, int]]:
    """Return `(min_required, max_positional)` for a prompt signature like `a, b: int = 1`, or None if variadic/unknown."""
    s = sig_inner.strip()
    if not s:
        return (0, 0)
    if "..." in s or "*" in s or "/" in s:
        return None
    parts: List[str] = []
    depth = 0
    cur: List[str] = []
    for ch in s:
        if ch in "([{":
            depth += 1
            cur.append(ch)
        elif ch in ")]}":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    parts = [p for p in parts if p and p != "self"]
    total = len(parts)
    optional = sum(1 for p in parts if "=" in p)
    return (max(0, total - optional), total)


def extract_prompt_func_arities(prompt: str) -> Dict[str, Tuple[int, int]]:
    """Extract `(min_args, max_args)` for functions explicitly specified with parameter lists in `prompt`."""
    if not prompt or not prompt.strip():
        return {}
    folded = strip_accents(prompt)
    same_len = len(prompt) == len(folded)
    arities: Dict[str, Tuple[int, int]] = {}
    for m in _FUNC_REQ_RE.finditer(folded):
        fn_name = prompt[m.start(1):m.end(1)] if same_len else m.group(1)
        if fn_name in _IGNORED_NAMES:
            continue
        open_idx = m.end() - 1
        inner = _extract_balanced_parens(folded, open_idx)
        if inner is None:
            continue
        counts = _count_signature_params(inner)
        if counts is not None:
            arities[fn_name] = counts
    return arities


def extract_prompt_api_names(prompt: str) -> Tuple[List[str], List[str], List[str]]:
    """Return `(required_classes, required_functions, required_self_methods)` explicitly named in `prompt`."""
    if not prompt or not prompt.strip():
        return [], [], []
    folded = strip_accents(prompt)
    same_len = len(prompt) == len(folded)
    classes: List[str] = []
    funcs: List[str] = []
    methods: List[str] = []

    for m in _CLASS_REQ_RE.finditer(folded):
        cls_name = prompt[m.start(1):m.end(1)] if same_len else m.group(1)
        if cls_name not in _IGNORED_NAMES and cls_name not in classes:
            classes.append(cls_name)

    for m in _FUNC_REQ_RE.finditer(folded):
        fn_name = prompt[m.start(1):m.end(1)] if same_len else m.group(1)
        if fn_name not in _IGNORED_NAMES and fn_name not in funcs:
            funcs.append(fn_name)

    scan_text = prompt if same_len else folded
    for m in _METHOD_SELF_RE.finditer(scan_text):
        meth_name = m.group(1)
        if meth_name not in ("__str__", "__repr__") and meth_name not in methods:
            methods.append(meth_name)

    return classes, funcs, methods


def check_api_contract(code: str, prompt: str = "", starter_code: str = "") -> str:
    """
    Verify that `code` defines every explicit class, function, and method name
    mandated by `starter_code` and `prompt`. Returns "" if satisfied, else a diagnostic string.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return "Mã nguồn có lỗi cú pháp."

    defined_classes: Set[str] = set()
    defined_funcs: Set[str] = set()
    defined_methods: Set[str] = set()
    func_nodes: Dict[str, ast.AST] = {}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defined_classes.add(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_methods.add(f"{node.name}.{item.name}")
                    defined_methods.add(item.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_funcs.add(node.name)
            func_nodes[node.name] = node

    missing: list[str] = []

    # 1. Starter code contract (# TODO / pass skeleton)
    if starter_code and starter_code.strip():
        try:
            starter_tree = ast.parse(starter_code)
        except (SyntaxError, ValueError, RecursionError):
            starter_tree = None
        if starter_tree is not None:
            for node in starter_tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    if node.name not in defined_classes:
                        missing.append(f"class {node.name}")
                    else:
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                                item.name == "__init__" or not item.name.startswith("_")
                            ):
                                if f"{node.name}.{item.name}" not in defined_methods:
                                    missing.append(f"{node.name}.{item.name}()")
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    if node.name not in defined_funcs:
                        missing.append(f"def {node.name}()")

    # 2. Explicit prompt contract
    req_classes, req_funcs, req_methods = extract_prompt_api_names(prompt)
    for cls_name in req_classes:
        if not any(c.casefold() == cls_name.casefold() for c in defined_classes):
            missing.append(f"class {cls_name}")
        elif cls_name not in defined_classes:
            missing.append(f"class {cls_name} (sai hoa/thường)")

    req_arities = extract_prompt_func_arities(prompt)
    for fn_name in req_funcs:
        all_callables = defined_funcs | defined_methods
        if not any(f.casefold() == fn_name.casefold() for f in all_callables):
            missing.append(f"def {fn_name}()")
        elif fn_name in func_nodes and fn_name in req_arities:
            fn_node = func_nodes[fn_name]
            pos_total = len(fn_node.args.posonlyargs) + len(fn_node.args.args)
            min_def = max(0, pos_total - len(fn_node.args.defaults))
            has_vararg = fn_node.args.vararg is not None
            exp_min, exp_max = req_arities[fn_name]
            if not has_vararg and (pos_total < exp_max or min_def > exp_min):
                missing.append(f"def {fn_name}() sai số lượng tham số (đề yêu cầu {exp_max} tham số)")

    for meth_name in req_methods:
        if meth_name not in defined_methods:
            missing.append(f"phương thức {meth_name}(self, ...)")

    if not missing:
        return ""
    unique_missing = list(dict.fromkeys(missing))
    return (
        "Mã đề xuất thiếu hoặc đặt sai tên lớp/hàm/phương thức bắt buộc trong đề: "
        + ", ".join(unique_missing)
        + ". BẮT BUỘC giữ chính xác 100% tên và chữ ký API theo đề bài."
    )


def _has_non_main_function_without_value_return(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name not in ("main", "__init__") and not node.name.startswith("_"):
            has_val_return = any(
                isinstance(sub, ast.Return) and sub.value is not None
                and not (isinstance(sub.value, ast.Constant) and sub.value.value is None)
                for sub in ast.walk(node)
            )
            has_print = any(
                isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "print"
                for sub in ast.walk(node)
            )
            if not has_val_return and not has_print:
                return True
    return False


def validate_shadow_output(
    code: str,
    stdout: str,
    prompt: str = "",
    *,
    editing_existing: bool = False,
) -> str:
    """Return "" when runtime stdout looks genuine, or a repair diagnostic if hollow/None/empty."""
    if editing_existing or prompt_forbids_print(prompt):
        return ""
    stripped = (stdout or "").strip()
    if not stripped:
        return (
            "Chương trình chạy không văng lỗi nhưng KHÔNG in ra bất kỳ kết quả nào trên màn hình. "
            "Hãy đảm bảo `def main():` được gọi trong `if __name__ == \"__main__\":` và có lệnh `print(...)` in kết quả thực tế."
        )
    folded_out = strip_accents(stripped).casefold()
    if folded_out in ("xin chao", "xin chao!", "hello", "hello world", "todo", "pass"):
        return (
            f"Chương trình đang in chuỗi giữ chỗ '{stripped}' thay vì kết quả thực tế của bài toán. "
            "Hãy gọi hàm/lớp giải bài toán trong `main()` và in kết quả tính được."
        )
    if stripped == "None" and _has_non_main_function_without_value_return(code):
        return (
            "Chương trình chạy ra kết quả `None` vì hàm/phương thức tính toán quên câu lệnh `return` giá trị. "
            "Hãy kiểm tra và bổ sung `return` kết quả đúng trong hàm/phương thức."
        )
    return ""
