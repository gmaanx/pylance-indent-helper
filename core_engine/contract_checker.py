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
from typing import Set

from .golden_skeletons import strip_accents
from .runnable_output import prompt_forbids_print

_CLASS_REQ_RE = re.compile(
    r"\b(?:viet|tao|xay\s+dung|cai\s+dat|dinh\s+nghia)\s+(?:mot\s+)?lop\s+`?([A-Za-z_][A-Za-z0-9_]*)`?\b",
    re.IGNORECASE,
)
_FUNC_REQ_RE = re.compile(
    r"\b(?:viet|tao|xay\s+dung|cai\s+dat|dinh\s+nghia)\s+ham(?:\s+python(?:\s+thuan)?)?\s+`?([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.IGNORECASE,
)
_METHOD_SELF_RE = re.compile(
    r"`?([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*self\b",
)
_IGNORED_NAMES = {"SearchProblem", "CspProblem", "Environment", "RLEnvironment", "Python", "main"}


def check_api_contract(code: str, prompt: str = "", starter_code: str = "") -> str:
    """
    Verify that `code` defines every explicit class, function, and method name
    mandated by `starter_code` and `prompt`. Returns "" if satisfied, else a diagnostic string.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return "Mã nguồn có lỗi cú pháp."

    defined_classes: Set[str] = set()
    defined_funcs: Set[str] = set()
    defined_methods: Set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defined_classes.add(node.name)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined_methods.add(f"{node.name}.{item.name}")
                    defined_methods.add(item.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined_funcs.add(node.name)

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
    if prompt and prompt.strip():
        folded = strip_accents(prompt)
        # Preserve identifier casing by matching spans on folded when length matches
        scan_text = prompt if len(prompt) == len(folded) else folded
        for m in _CLASS_REQ_RE.finditer(folded):
            cls_name = prompt[m.start(1):m.end(1)] if len(prompt) == len(folded) else m.group(1)
            if cls_name not in _IGNORED_NAMES and not any(c.casefold() == cls_name.casefold() for c in defined_classes):
                missing.append(f"class {cls_name}")
            elif cls_name not in _IGNORED_NAMES and cls_name not in defined_classes and len(prompt) == len(folded):
                missing.append(f"class {cls_name} (sai hoa/thường)")

        for m in _FUNC_REQ_RE.finditer(folded):
            fn_name = prompt[m.start(1):m.end(1)] if len(prompt) == len(folded) else m.group(1)
            if fn_name not in _IGNORED_NAMES:
                all_callables = defined_funcs | defined_methods
                if not any(f.casefold() == fn_name.casefold() for f in all_callables):
                    missing.append(f"def {fn_name}()")

        for m in _METHOD_SELF_RE.finditer(scan_text):
            meth_name = m.group(1)
            if meth_name not in ("__str__", "__repr__") and meth_name not in defined_methods:
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
