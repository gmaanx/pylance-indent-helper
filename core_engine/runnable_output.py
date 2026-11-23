"""Runnable output formatting for offline solvers and static AST print checks for models."""

from __future__ import annotations

import ast
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .golden_skeletons import strip_accents

_SUPPORTED_FORMATS = ("default", "json", "pretty_json", "lines", "join", "fixed", "template")
_SEP_NAMES = {
    "dau cach": " ",
    "khoang trang": " ",
    "dau phay": ", ",
    "dau cham phay": "; ",
    "mui ten": " -> ",
}
_TEMPLATE_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_FORBID_PRINT_PATTERNS = (
    r"\bkhong\s+(?:can\s+)?(?:in|print|them\s+vi\s+du|them\s+__main__|goi\s+ham)\b",
    r"\bdung\s+(?:in|print|them\s+vi\s+du|them\s+__main__)\b",
    r"\bbo\s+(?:doan\s+)?(?:vi\s+du|chay\s+thu|in)\b",
    r"\bchi\s+(?:viet|dinh\s+nghia|khai\s+bao)\s+(?:ham|lop)\s*,\s*khong\s+(?:in|goi)\b",
    r"\b(?:do\s+not|don't|no)\s+(?:print|add\s+__main__|add\s+example)\b",
    r"\bwithout\s+(?:__main__|print|printing|example)\b",
)
_OUTPUT_CALL_NAMES = {"print", "pprint", "input"}
_OUTPUT_ATTR_TARGETS = {
    ("sys", "stdout", "write"),
    ("sys", "stderr", "write"),
    ("pprint", "pprint"),
    ("logging", "info"),
    ("logging", "warning"),
    ("logging", "error"),
    ("logging", "debug"),
}
_PREFERRED_ENTRY_FUNCS = ("main", "run", "chay", "solve", "giai", "result", "ket_qua")

_TRAILING_JSON = re.compile(
    r"(?:[.,;:\n]\s*|\s+)(?:va\s+)?(?:hay\s+)?(?:(?:in|xuat|hien\s+thi)(?:\s+ra)?(?:\s+ket\s+qua)?(?:\s+ra)?\s+)?"
    r"(?:o\s+|theo\s+)?dang\s+json"
    r"(?:\s+(?P<pretty>dep|co\s+thut\s+le|thut\s+le))?[.\s]*$",
    re.IGNORECASE,
)
_TRAILING_LINES = re.compile(
    r"(?:[.,;:\n]\s*|\s+)(?:va\s+)?(?:hay\s+)?(?:(?:in|xuat|hien\s+thi)(?:\s+ra)?(?:\s+ket\s+qua)?\s+)?"
    r"(?:moi\s+(?:so|phan\s+tu|buoc|dong|trang\s+thai|nghiem|cap|muc|ket\s+qua)(?:\s+tren)?\s+(?:mot|1)\s+dong"
    r"|(?:in|xuat|hien\s+thi)(?:\s+ra)?\s+tung\s+(?:buoc|phan\s+tu|so|trang\s+thai|nghiem)(?:\s+tren\s+(?:mot|1)\s+dong)?)[.\s]*$",
    re.IGNORECASE,
)
_TRAILING_JOIN = re.compile(
    r"(?:[.,;:\n]\s*|\s+)(?:va\s+)?(?:hay\s+)?(?:(?:in|xuat|hien\s+thi)(?:\s+ra)?(?:\s+ket\s+qua)?\s+)?"
    r"(?:tren\s+(?:mot|1)\s+dong[,\s]*)?(?:cach\s+nhau|ngan\s+cach)(?:\s+boi|\s+bang)?\s+"
    r"(?P<sep>dau\s+cach|khoang\s+trang|dau\s+phay|dau\s+cham\s+phay|mui\s+ten)[.\s]*$",
    re.IGNORECASE,
)
_TRAILING_FIXED = re.compile(
    r"(?:[.,;:\n]\s*|\s+)(?:va\s+)?(?:hay\s+)?(?:(?:in|xuat|hien\s+thi)(?:\s+ra)?(?:\s+ket\s+qua)?\s+)?"
    r"lam\s+tron(?:\s+den|\s+toi)?\s+(?P<decimals>\d{1,2})\s+chu\s+so"
    r"(?:\s+thap\s+phan|\s+sau\s+dau\s+phay)?[.\s]*$",
    re.IGNORECASE,
)
_TRAILING_TEMPLATE = re.compile(
    r"""(?:[.,;:\n]\s*|\s+)(?:va\s+)?(?:hay\s+)?(?:(?:in|xuat|hien\s+thi)(?:\s+ra)?(?:\s+ket\s+qua)?\s+)?"""
    r"""(?:theo\s+)?(?:mau|dinh\s+dang)\s*(?::\s*)?(?P<quote>["'])(?P<tpl>[^"'\r\n]{1,200})(?P=quote)[.\s]*$""",
    re.IGNORECASE,
)


def _accent_offsets(original: str) -> Tuple[str, List[int]]:
    normalized = strip_accents(original)
    if len(original) == len(normalized):
        return normalized, list(range(len(original) + 1))
    offsets: List[int] = []
    for index, char in enumerate(original):
        folded = strip_accents(char)
        for _ in folded:
            offsets.append(index)
    offsets.append(len(original))
    return normalized, offsets


def _validate_template_string(template: str) -> str:
    from .offline_solver import OfflineProblemError

    if not isinstance(template, str) or not 1 <= len(template) <= 200 or "\n" in template or "\r" in template:
        raise OfflineProblemError("invalid", "template cần là chuỗi 1 dòng dài 1–200 ký tự.")
    # Reject unbalanced single braces (escaped {{ or }} are allowed).
    stripped = template.replace("{{", "").replace("}}", "")
    if stripped.count("{") != stripped.count("}"):
        raise OfflineProblemError("invalid", "template có dấu ngoặc nhọn không khớp.")
    placeholders = _TEMPLATE_PLACEHOLDER.findall(stripped)
    if not placeholders:
        raise OfflineProblemError("invalid", "template cần chứa {result} hoặc {result:.2f}.")
    for token in placeholders:
        if token == "result":
            continue
        match = re.fullmatch(r"result:\.(\d{1,2})f", token)
        if not match or not 0 <= int(match.group(1)) <= 12:
            raise OfflineProblemError(
                "unsupported",
                "template chỉ hỗ trợ {result} hoặc {result:.Nf} với N từ 0 đến 12.",
            )
    return template


def validate_output_spec(raw: Any) -> Optional[Dict[str, Any]]:
    """Validate optional @solve 'output' formatting settings."""
    from .offline_solver import OfflineProblemError, _fields, _integer

    if raw is None:
        return None
    if isinstance(raw, str):
        raw = {"format": raw}
    if not isinstance(raw, dict):
        raise OfflineProblemError("invalid", "output phải là tên định dạng hoặc đối tượng cấu hình JSON.")

    _fields(
        raw,
        (),
        ("format", "sep", "decimals", "prefix", "suffix", "template", "field", "none_text"),
    )
    fmt = raw.get("format", "default")
    if not isinstance(fmt, str) or fmt not in _SUPPORTED_FORMATS:
        raise OfflineProblemError(
            "unsupported",
            "output.format hỗ trợ: " + ", ".join(_SUPPORTED_FORMATS) + ".",
        )
    spec: Dict[str, Any] = {"format": fmt}

    if "sep" in raw:
        if fmt != "join":
            raise OfflineProblemError("unsupported", "output.sep chỉ dùng khi format='join'.")
        sep = raw["sep"]
        if not isinstance(sep, str) or not 1 <= len(sep) <= 20 or "\r" in sep:
            raise OfflineProblemError("invalid", "output.sep cần là chuỗi dài 1–20 ký tự.")
        spec["sep"] = sep
    elif fmt == "join":
        spec["sep"] = " "

    if "decimals" in raw:
        if fmt not in ("fixed", "lines", "join", "default"):
            raise OfflineProblemError("unsupported", "output.decimals không dùng với định dạng này.")
        spec["decimals"] = _integer(raw["decimals"], "output.decimals", 0, 12)
    elif fmt == "fixed":
        spec["decimals"] = 2

    if "template" in raw:
        if fmt != "template":
            raise OfflineProblemError("unsupported", "output.template chỉ dùng khi format='template'.")
        spec["template"] = _validate_template_string(raw["template"])
    elif fmt == "template":
        raise OfflineProblemError("needs_input", "format='template' cần trường template.")

    for key in ("prefix", "suffix", "none_text"):
        if key in raw:
            val = raw[key]
            if not isinstance(val, str) or len(val) > 120 or "\r" in val:
                raise OfflineProblemError("invalid", f"output.{key} cần là chuỗi tối đa 120 ký tự.")
            spec[key] = val

    if "field" in raw:
        field_name = raw["field"]
        if not isinstance(field_name, str) or not 1 <= len(field_name) <= 60:
            raise OfflineProblemError("invalid", "output.field cần là tên khóa dài 1–60 ký tự.")
        spec["field"] = field_name

    if fmt == "default" and len(spec) == 1:
        return None
    return spec


def extract_output_clause(prompt: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Extract an unambiguous trailing Vietnamese printing-format instruction if present.
    Never strips non-formatting algorithmic requirements.
    """
    text = prompt.strip()
    if not text:
        return prompt, None

    normalized, offsets = _accent_offsets(text)
    lowered = normalized.casefold()

    for pattern, kind in (
        (_TRAILING_TEMPLATE, "template"),
        (_TRAILING_JSON, "json"),
        (_TRAILING_LINES, "lines"),
        (_TRAILING_JOIN, "join"),
        (_TRAILING_FIXED, "fixed"),
    ):
        match = pattern.search(lowered)
        if not match or match.start() == 0:
            continue
        core_end = offsets[match.start()]
        core = text[:core_end].rstrip(" ,;.\n\t")
        if not core:
            continue
        if kind == "template":
            tpl_start = offsets[match.start("tpl")]
            tpl_end = offsets[match.end("tpl")]
            tpl = text[tpl_start:tpl_end]
            spec = validate_output_spec({"format": "template", "template": tpl})
            return core, spec
        if kind == "json":
            fmt = "pretty_json" if match.group("pretty") else "json"
            return core, {"format": fmt}
        if kind == "lines":
            return core, {"format": "lines"}
        if kind == "join":
            sep_key = re.sub(r"\s+", " ", match.group("sep").casefold()).strip()
            return core, {"format": "join", "sep": _SEP_NAMES[sep_key]}
        if kind == "fixed":
            decimals = int(match.group("decimals"))
            spec = validate_output_spec({"format": "fixed", "decimals": decimals})
            return core, spec

    return prompt, None


def render_main_output(
    call_expr: str,
    output_spec: Optional[Dict[str, Any]],
    *,
    default_collection_field: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Return `(extra_imports, main_body)` for an offline standalone script.
    When `output_spec` is None, returns the exact legacy `print(<call_expr>)` body.
    """
    if not output_spec:
        return "", f"    print({call_expr})\n"

    fmt = output_spec.get("format", "default")
    field = output_spec.get("field")
    if field is None and default_collection_field and fmt in ("lines", "join"):
        field = default_collection_field
    prefix = output_spec.get("prefix", "")
    suffix = output_spec.get("suffix", "")
    none_text = output_spec.get("none_text")
    decimals = output_spec.get("decimals")

    imports = "import json\n" if fmt in ("json", "pretty_json") else ""
    lines: List[str] = [f"    _output = {call_expr}"]

    if field is not None:
        lines.append(f"    if isinstance(_output, dict) and {field!r} in _output:")
        lines.append(f"        _output = _output[{field!r}]")

    if none_text is not None:
        lines.append("    if _output is None:")
        lines.append(f"        print({none_text!r})")
        lines.append("    else:")
        indent = "        "
    else:
        indent = "    "

    def _emit_round_helper(ind: str, dec: int) -> None:
        lines.append(f"{ind}def _fmt_num(val):")
        lines.append(f"{ind}    if isinstance(val, (int, float)) and not isinstance(val, bool):")
        lines.append(f"{ind}        return f'{{val:.{dec}f}}'")
        lines.append(f"{ind}    if isinstance(val, list):")
        lines.append(f"{ind}        return [_fmt_num(x) for x in val]")
        lines.append(f"{ind}    if isinstance(val, tuple):")
        lines.append(f"{ind}        return tuple(_fmt_num(x) for x in val)")
        lines.append(f"{ind}    if isinstance(val, dict):")
        lines.append(f"{ind}        return {{k: _fmt_num(v) for k, v in val.items()}}")
        lines.append(f"{ind}    return val")

    if fmt == "json":
        lines.append(f"{indent}print(json.dumps(_output, ensure_ascii=False))")
    elif fmt == "pretty_json":
        lines.append(f"{indent}print(json.dumps(_output, ensure_ascii=False, indent=2))")
    elif fmt == "lines":
        if decimals is not None:
            _emit_round_helper(indent, decimals)
            lines.append(f"{indent}_output = _fmt_num(_output)")
        lines.append(f"{indent}if isinstance(_output, dict):")
        lines.append(f"{indent}    for _k, _v in _output.items():")
        lines.append(f"{indent}        print(f'{{_k}}: {{_v}}')")
        lines.append(f"{indent}elif isinstance(_output, (list, tuple)):")
        lines.append(f"{indent}    for _item in _output:")
        lines.append(f"{indent}        print(_item)")
        lines.append(f"{indent}else:")
        lines.append(f"{indent}    print(_output)")
    elif fmt == "join":
        sep = output_spec.get("sep", " ")
        if decimals is not None:
            _emit_round_helper(indent, decimals)
            lines.append(f"{indent}_output = _fmt_num(_output)")
        lines.append(f"{indent}if isinstance(_output, (list, tuple)):")
        lines.append(f"{indent}    _text = {sep!r}.join(str(_item) for _item in _output)")
        lines.append(f"{indent}elif isinstance(_output, dict):")
        lines.append(f"{indent}    _text = {sep!r}.join(f'{{_k}}={{_v}}' for _k, _v in _output.items())")
        lines.append(f"{indent}else:")
        lines.append(f"{indent}    _text = str(_output)")
        lines.append(f"{indent}print({prefix!r} + _text + {suffix!r})" if (prefix or suffix) else f"{indent}print(_text)")
    elif fmt == "fixed":
        dec = decimals if decimals is not None else 2
        _emit_round_helper(indent, dec)
        lines.append(f"{indent}_formatted = _fmt_num(_output)")
        if prefix or suffix:
            lines.append(f"{indent}print({prefix!r} + str(_formatted) + {suffix!r})")
        else:
            lines.append(f"{indent}print(_formatted)")
    elif fmt == "template":
        tpl = output_spec["template"]
        lines.append(f"{indent}print({tpl!r}.format(result=_output))")
    else:
        if decimals is not None:
            _emit_round_helper(indent, decimals)
            lines.append(f"{indent}_output = _fmt_num(_output)")
        if prefix or suffix:
            lines.append(f"{indent}print({prefix!r} + str(_output) + {suffix!r})")
        else:
            lines.append(f"{indent}print(_output)")

    return imports, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Static AST auto-print detection & safe fallback for API / Ollama output
# ---------------------------------------------------------------------------

def _prompt_forbids_print(prompt: str) -> bool:
    folded = strip_accents(prompt).casefold()
    return any(re.search(pattern, folded) for pattern in _FORBID_PRINT_PATTERNS)


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    if len(node.test.ops) != 1 or not isinstance(node.test.ops[0], ast.Eq) or len(node.test.comparators) != 1:
        return False
    left, right = node.test.left, node.test.comparators[0]
    pair = (left, right)
    for name_node, const_node in (pair, pair[::-1]):
        if (
            isinstance(name_node, ast.Name)
            and name_node.id == "__name__"
            and isinstance(const_node, ast.Constant)
            and const_node.value == "__main__"
        ):
            return True
    return False


def _attr_chain(node: ast.AST) -> Tuple[str, ...]:
    parts: List[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return tuple(reversed(parts))
    return ()


def _call_names_in_node(node: ast.AST) -> Tuple[bool, Set[str]]:
    direct_output = False
    called: Set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Name):
            if sub.func.id in _OUTPUT_CALL_NAMES:
                direct_output = True
            called.add(sub.func.id)
        elif isinstance(sub.func, ast.Attribute):
            chain = _attr_chain(sub.func)
            if chain in _OUTPUT_ATTR_TARGETS or sub.func.attr in ("write", "writelines", "pprint"):
                direct_output = True
            called.add(sub.func.attr)
    return direct_output, called


def _printing_functions(tree: ast.Module) -> Set[str]:
    direct: Set[str] = set()
    edges: Dict[str, Set[str]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_out, called = _call_names_in_node(node)
            if has_out:
                direct.add(node.name)
            edges[node.name] = called
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    has_out, called = _call_names_in_node(item)
                    if has_out:
                        direct.add(item.name)
                        if item.name == "__init__":
                            direct.add(node.name)
                    edges[item.name] = called

    printing = set(direct)
    changed = True
    while changed:
        changed = False
        for name, callees in edges.items():
            if name not in printing and (callees & printing):
                printing.add(name)
                changed = True
    return printing


def code_prints_when_run(code: str) -> bool:
    """Return True if running the module as __main__ statically reaches a print/output call."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return False

    printing_funcs = _printing_functions(tree)
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            continue
        if isinstance(stmt, ast.Raise):
            return True
        if _is_main_guard(stmt):
            for sub in stmt.body:
                has_out, called = _call_names_in_node(sub)
                if has_out or (called & printing_funcs):
                    return True
            continue
        has_out, called = _call_names_in_node(stmt)
        if has_out or (called & printing_funcs):
            return True
    return False


def _required_positional_count(args: ast.arguments, *, is_method: bool = False) -> Tuple[int, int, bool]:
    """Return (min_pos, max_pos, has_vararg)."""
    pos = list(args.posonlyargs) + list(args.args)
    if is_method and pos:
        pos = pos[1:]
    total = len(pos)
    defaults = len(args.defaults)
    min_pos = max(0, total - defaults)
    has_vararg = args.vararg is not None
    return min_pos, total, has_vararg


def _has_required_kwonly(args: ast.arguments) -> bool:
    return any(default is None for default in args.kw_defaults)


def _is_zero_arg_callable(args: ast.arguments, *, is_method: bool = False) -> bool:
    min_pos, _, _ = _required_positional_count(args, is_method=is_method)
    return min_pos == 0 and not _has_required_kwonly(args)


def _is_literal_ast(node: ast.AST) -> bool:
    try:
        ast.literal_eval(node)
        return True
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False


def _call_matches_signature(call: ast.Call, func_def: ast.FunctionDef) -> bool:
    args = func_def.args
    min_pos, max_pos, has_vararg = _required_positional_count(args)
    if any(isinstance(arg, ast.Starred) for arg in call.args):
        return False
    if any(kw.arg is None for kw in call.keywords):
        return False
    if not all(_is_literal_ast(arg) for arg in call.args):
        return False
    if not all(_is_literal_ast(kw.value) for kw in call.keywords):
        return False

    pos_names = [a.arg for a in args.posonlyargs] + [a.arg for a in args.args]
    kwonly_names = [a.arg for a in args.kwonlyargs]
    allowed_kw = set(a.arg for a in args.args) | set(kwonly_names)
    kw_names = [kw.arg for kw in call.keywords]
    if len(kw_names) != len(set(kw_names)):
        return False
    if not args.kwarg and any(name not in allowed_kw for name in kw_names):
        return False

    provided_pos = len(call.args)
    if not has_vararg and provided_pos > max_pos:
        return False
    covered_pos = set(pos_names[:provided_pos])
    if covered_pos & set(kw_names):
        return False

    required_pos_names = set(pos_names[:min_pos])
    if not required_pos_names <= (covered_pos | set(kw_names)):
        return False
    required_kwonly = {
        arg.arg for arg, default in zip(args.kwonlyargs, args.kw_defaults) if default is None
    }
    return required_kwonly <= set(kw_names)


def _extract_literal_sample_call(prompt: str, funcs: Dict[str, ast.FunctionDef]) -> Optional[str]:
    """Find a literal call like `foo([1, 2], 'a')` in the prompt matching a defined function."""
    for name, func_def in funcs.items():
        if name.startswith("_"):
            continue
        pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
        for match in pattern.finditer(prompt):
            start = match.start()
            depth = 0
            in_quote: Optional[str] = None
            escaped = False
            end = -1
            for idx in range(match.end() - 1, min(len(prompt), start + 300)):
                ch = prompt[idx]
                if in_quote:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == in_quote:
                        in_quote = None
                    continue
                if ch in ("'", '"'):
                    in_quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        end = idx + 1
                        break
            if end == -1:
                continue
            snippet = prompt[start:end].strip()
            try:
                expr = ast.parse(snippet, mode="eval").body
            except (SyntaxError, ValueError, RecursionError):
                continue
            if isinstance(expr, ast.Call) and _call_matches_signature(expr, func_def):
                return ast.unparse(expr)
    return None


def _extract_example_literal_for_single_arg(prompt: str, funcs: Dict[str, ast.FunctionDef]) -> Optional[str]:
    """Match prompts like 'Thêm ví dụ với \"  An   Bình  \"' for a single 1-arg public function."""
    single_arg_funcs = []
    for name, fn in funcs.items():
        if name.startswith("_"):
            continue
        min_pos, max_pos, _ = _required_positional_count(fn.args)
        if min_pos == 1 and max_pos >= 1 and not _has_required_kwonly(fn.args):
            single_arg_funcs.append(name)
    if len(single_arg_funcs) != 1:
        return None
    normalized, offsets = _accent_offsets(prompt)
    pattern = re.compile(r"\b(?:vi\s+du|thu|kiem\s+thu|test)\s+voi\s+", re.IGNORECASE)
    for match in pattern.finditer(normalized):
        tail = prompt[offsets[match.end()]:].lstrip()
        # Try parsing a quoted string, bracketed collection, or number prefix.
        cand = ""
        if tail.startswith(('"', "'")):
            q = tail[0]
            esc = False
            for idx in range(1, min(len(tail), 200)):
                if esc:
                    esc = False
                elif tail[idx] == "\\":
                    esc = True
                elif tail[idx] == q:
                    cand = tail[: idx + 1]
                    break
        elif tail.startswith(("[", "(", "{")):
            open_ch = tail[0]
            close_ch = {"[": "]", "(": ")", "{": "}"}[open_ch]
            depth = 0
            in_q: Optional[str] = None
            esc = False
            for idx in range(min(len(tail), 200)):
                ch = tail[idx]
                if in_q:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == in_q:
                        in_q = None
                elif ch in ('"', "'"):
                    in_q = ch
                elif ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        cand = tail[: idx + 1]
                        break
        else:
            num_m = re.match(r"[+-]?\d+(?:\.\d+)?\b", tail)
            if num_m:
                cand = num_m.group(0)
        if cand:
            try:
                value = ast.literal_eval(cand)
            except (ValueError, SyntaxError, MemoryError, RecursionError):
                continue
            return f"{single_arg_funcs[0]}({value!r})"
    return None


def _format_print_expression(var_expr: str, prompt: str) -> Tuple[str, str]:
    """Use JSON/lines/fixed formatting if the prompt explicitly requested it."""
    _, spec = extract_output_clause(prompt)
    if spec is None:
        folded = strip_accents(prompt).casefold()
        if re.search(r"\bdang\s+json\b", folded):
            spec = {"format": "json"}
    if spec and spec.get("format") == "json":
        return "import json\n", f"print(json.dumps({var_expr}, ensure_ascii=False))"
    if spec and spec.get("format") == "pretty_json":
        return "import json\n", f"print(json.dumps({var_expr}, ensure_ascii=False, indent=2))"
    if spec and spec.get("format") == "fixed":
        dec = spec.get("decimals", 2)
        return "", f"print(f'{{{var_expr}:.{dec}f}}' if isinstance({var_expr}, (int, float)) and not isinstance({var_expr}, bool) else {var_expr})"
    return "", f"print({var_expr})"


def _prepend_import(code: str, import_line: str) -> str:
    if not import_line or import_line.strip() in code:
        return code
    return import_line + code


def ensure_runnable_print(
    code: str,
    prompt: str = "",
    *,
    editing_existing: bool = False,
) -> Tuple[str, bool]:
    """
    Ensure model-generated Python code prints output when run directly without executing it.
    Returns `(updated_code, has_runnable_output)`.
    Never guesses arbitrary arguments for functions/classes with unknown parameter types.
    """
    if not code or not code.strip():
        return code, False
    if editing_existing or _prompt_forbids_print(prompt):
        return code, True
    if code_prints_when_run(code):
        return code, True

    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return code, False

    # 1. Existing `if __name__ == "__main__":` block that computes a value without printing.
    main_blocks = [stmt for stmt in tree.body if _is_main_guard(stmt)]
    if main_blocks:
        last_main = main_blocks[-1]
        if last_main.body:
            last_stmt = last_main.body[-1]
            if isinstance(last_stmt, ast.Assign) and len(last_stmt.targets) == 1 and isinstance(last_stmt.targets[0], ast.Name):
                var_name = last_stmt.targets[0].id
                imp, print_stmt = _format_print_expression(var_name, prompt)
                base = _prepend_import(code.rstrip(), imp)
                return f"{base}\n    {print_stmt}\n", True
            if (
                isinstance(last_stmt, ast.Expr)
                and isinstance(last_stmt.value, ast.Call)
                and last_stmt.lineno == last_stmt.end_lineno
            ):
                lines = code.splitlines()
                idx = last_stmt.lineno - 1
                indent = lines[idx][: len(lines[idx]) - len(lines[idx].lstrip())]
                call_src = lines[idx].strip()
                imp, print_stmt = _format_print_expression("_ket_qua", prompt)
                lines[idx : idx + 1] = [
                    f"{indent}_ket_qua = {call_src}",
                    f"{indent}if _ket_qua is not None:",
                    f"{indent}    {print_stmt}",
                ]
                return _prepend_import("\n".join(lines).rstrip() + "\n", imp), True
        return code, False

    # 2. Top-level script computes a result after definitions without printing.
    last_def_idx = -1
    for index, stmt in enumerate(tree.body):
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            last_def_idx = index
    trailing = tree.body[last_def_idx + 1:]
    if trailing:
        last_stmt = trailing[-1]
        if (
            isinstance(last_stmt, ast.Assign)
            and len(last_stmt.targets) == 1
            and isinstance(last_stmt.targets[0], ast.Name)
            and isinstance(last_stmt.value, (ast.Call, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.BinOp))
        ):
            var_name = last_stmt.targets[0].id
            imp, print_stmt = _format_print_expression(var_name, prompt)
            base = _prepend_import(code.rstrip(), imp)
            return f"{base}\n{print_stmt}\n", True
        if (
            isinstance(last_stmt, ast.Expr)
            and isinstance(last_stmt.value, ast.Call)
            and last_stmt.lineno == last_stmt.end_lineno
        ):
            lines = code.splitlines()
            idx = last_stmt.lineno - 1
            call_src = lines[idx].strip()
            imp, print_stmt = _format_print_expression("_ket_qua", prompt)
            lines[idx : idx + 1] = [
                f"_ket_qua = {call_src}",
                "if _ket_qua is not None:",
                f"    {print_stmt}",
            ]
            return _prepend_import("\n".join(lines).rstrip() + "\n", imp), True
        return code, False

    # 3. Module only defines functions/classes.
    funcs: Dict[str, ast.FunctionDef] = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }

    # 3a. Literal sample call or single-arg example literal present in the user's prompt.
    sample_call = _extract_literal_sample_call(prompt, funcs) or _extract_example_literal_for_single_arg(prompt, funcs)
    if sample_call:
        imp, print_stmt = _format_print_expression("_ket_qua", prompt)
        base = _prepend_import(code.rstrip(), imp)
        block = (
            '\n\nif __name__ == "__main__":\n'
            f"    _ket_qua = {sample_call}\n"
            "    if _ket_qua is not None:\n"
            f"        {print_stmt}\n"
        )
        return base + block, True

    # 3b. Zero-required-argument public function (e.g., `def main():`, `def result(): return 3`).
    zero_arg_funcs = [
        name for name, fn in funcs.items() if _is_zero_arg_callable(fn.args)
    ]
    if zero_arg_funcs:
        chosen = next((name for name in _PREFERRED_ENTRY_FUNCS if name in zero_arg_funcs), zero_arg_funcs[-1])
        imp, print_stmt = _format_print_expression("_ket_qua", prompt)
        base = _prepend_import(code.rstrip(), imp)
        block = (
            '\n\nif __name__ == "__main__":\n'
            f"    _ket_qua = {chosen}()\n"
            "    if _ket_qua is not None:\n"
            f"        {print_stmt}\n"
        )
        return base + block, True

    # 3c. Zero-required-argument public class with zero-arg method or printable representation.
    classes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
    ]
    for cls in reversed(classes):
        init_fn = next((m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == "__init__"), None)
        if init_fn is None or _is_zero_arg_callable(init_fn.args, is_method=True):
            zero_methods = [
                m.name for m in cls.body
                if isinstance(m, ast.FunctionDef)
                and not m.name.startswith("_")
                and _is_zero_arg_callable(m.args, is_method=True)
            ]
            imp, print_stmt = _format_print_expression("_ket_qua", prompt)
            base = _prepend_import(code.rstrip(), imp)
            if zero_methods:
                method = next((m for m in _PREFERRED_ENTRY_FUNCS if m in zero_methods), zero_methods[0])
                block = (
                    '\n\nif __name__ == "__main__":\n'
                    f"    _obj = {cls.name}()\n"
                    f"    _ket_qua = _obj.{method}()\n"
                    "    if _ket_qua is not None:\n"
                    f"        {print_stmt}\n"
                )
            else:
                block = (
                    '\n\nif __name__ == "__main__":\n'
                    f"    print({cls.name}())\n"
                )
            return base + block, True

    return code, False
