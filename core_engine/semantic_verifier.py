# -*- coding: utf-8 -*-
"""
Deep Dynamic Semantic, Return-Type, Doctest & Adversarial Edge-Case Verifier.

Runs ONLY inside an isolated child Python process when `allow_shadow_exec=True`.
Catches subtle logic & grading bugs that pass normal `main()` execution:
1. Unfinished `# TODO` / `pass` / `...` / `NotImplementedError` stubs in required functions/methods.
2. Incomplete `main()` that forgets to call & print all requested functions/classes.
3. Return-type mismatches against prompt annotations (`-> int` returning `bool`, `-> float` returning `None`/`NaN`, `-> list` returning scalar/tuple).
4. Destructive in-place mutation of caller `dict`/`list`/`set` inputs in value-returning functions.
5. Explicit doctest / inline literal example mismatches (`func(args) -> expected`).
6. Latent edge-case crashes:
   - Single zero-vector `[0, ...]` in 2-vector similarity/distance (`and` vs `or` ZeroDivisionError).
   - Sink vertex omitted from `graph` keys (`KeyError`), unreachable goal, and 2-cycle infinite loops in `bfs`/`dfs`.
   - All-True / All-False `facts` truth assignments exposing short-circuit `KeyError` in forward chaining.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .contract_checker import extract_prompt_api_names
from .golden_skeletons import strip_accents
from .runnable_output import prompt_forbids_print
from .shadow_runner_healer import find_best_python_executable

_RET_TYPE_RE = re.compile(
    r"`?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\([^()\n]{0,220}\)\s*->\s*`?(?P<rtype>[A-Za-z_][A-Za-z0-9_\[\],\s|.]*)`?",
)
_DOCTEST_RE = re.compile(
    r"^\s*>>>\s*(?P<expr>[^\r\n]+)\r?\n\s*(?P<expected>[^\r\n>]+)",
    re.MULTILINE,
)
_INLINE_ARROW_EXAMPLE_RE = re.compile(
    r"(?P<call>[A-Za-z_][A-Za-z0-9_]*\s*\([^:\n]{0,160}\))\s*(?:->|==|=>|trả về|tra ve)\s*(?P<expected>\[[^\]\n]{0,120}\]|\{[^}\n]{0,120}\}|\([^)\n]{0,120}\)|True|False|None|[+-]?\d+(?:\.\d+)?|'[^'\n]{0,80}'|\"[^\"\n]{0,80}\")",
    re.IGNORECASE,
)


def extract_prompt_return_types(prompt: str) -> Dict[str, str]:
    """Extract normalized base return type (`int`, `float`, `bool`, `list`, `dict`, `tuple`, `set`, `str`) per function."""
    if not prompt or not prompt.strip():
        return {}
    result: Dict[str, str] = {}
    for m in _RET_TYPE_RE.finditer(prompt):
        fn_name = m.group("name").strip()
        raw_rt = m.group("rtype").strip()
        # Take leading base identifier before `[` or `|` or whitespace
        base_m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", raw_rt)
        if not base_m:
            continue
        base = base_m.group(1).lower()
        if base in ("int", "float", "bool", "list", "dict", "tuple", "set", "str"):
            result[fn_name] = base
    return result


def extract_prompt_literal_examples(prompt: str, candidate_funcs: List[str]) -> List[Tuple[str, Any]]:
    """Extract concrete `(call_expr_str, expected_literal)` pairs from prompt doctests or prose."""
    if not prompt or not candidate_funcs:
        return []
    allowed = set(candidate_funcs)
    examples: List[Tuple[str, Any]] = []

    def _try_add(call_src: str, exp_src: str) -> None:
        call_src = call_src.strip().strip("`")
        exp_src = exp_src.strip().strip("`").rstrip(".,;")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                call_ast = ast.parse(call_src, mode="eval").body
                if not isinstance(call_ast, ast.Call) or not isinstance(call_ast.func, ast.Name):
                    return
                if call_ast.func.id not in allowed:
                    return
                # Ensure every argument is a pure Python literal (not parameter names like `bfs(graph, start, goal)`)
                for arg in call_ast.args:
                    ast.literal_eval(arg)
                for kw in call_ast.keywords:
                    ast.literal_eval(kw.value)
                expected_val = ast.literal_eval(exp_src)
        except (SyntaxError, ValueError, TypeError, MemoryError, RecursionError):
            return
        pair = (call_src, expected_val)
        if pair not in examples:
            examples.append(pair)

    for m in _DOCTEST_RE.finditer(prompt):
        _try_add(m.group("expr"), m.group("expected"))
    for m in _INLINE_ARROW_EXAMPLE_RE.finditer(prompt):
        _try_add(m.group("call"), m.group("expected"))

    return examples[:6]


def check_unfinished_stubs(code: str, prompt: str = "", starter_code: str = "") -> str:
    """Reject candidate code that leaves required functions/methods as `pass`, `...`, or `NotImplementedError`."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return ""

    req_classes, req_funcs, req_methods = extract_prompt_api_names(prompt)
    must_check_funcs = set(req_funcs)
    must_check_classes = set(req_classes)
    must_check_methods = set(req_methods)

    if starter_code and starter_code.strip():
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                st_tree = ast.parse(starter_code)
            for node in st_tree.body:
                if isinstance(node, ast.FunctionDef):
                    must_check_funcs.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    must_check_classes.add(node.name)
        except (SyntaxError, ValueError, RecursionError):
            pass

    def _is_stub_body(stmts: list[ast.stmt]) -> bool:
        real = [
            s for s in stmts
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
        ]
        if not real:
            return True
        if len(real) == 1:
            stmt = real[0]
            if isinstance(stmt, ast.Pass):
                return True
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
                return True
            if isinstance(stmt, ast.Raise):
                exc = stmt.exc.func if isinstance(stmt.exc, ast.Call) else stmt.exc
                if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                    return True
        return False

    stubs: List[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (not must_check_funcs or node.name in must_check_funcs) and not node.name.startswith("_"):
                if _is_stub_body(node.body):
                    stubs.append(f"def {node.name}()")
        elif isinstance(node, ast.ClassDef):
            if not must_check_classes or node.name in must_check_classes:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == "__init__" or not item.name.startswith("_") or item.name in must_check_methods:
                            if _is_stub_body(item.body):
                                stubs.append(f"{node.name}.{item.name}()")

    if stubs:
        return (
            "Mã đề xuất vẫn còn hàm/phương thức chưa cài đặt (đang để trống pass / ... / NotImplementedError): "
            + ", ".join(stubs)
            + ". Hãy viết đầy đủ nội dung xử lý cho tất cả các hàm và phương thức."
        )
    return ""


_HARNESS_SCRIPT = r'''# -*- coding: utf-8 -*-
import ast
import copy
import json
import math
import sys
import warnings

warnings.simplefilter("ignore", SyntaxWarning)

def _check_return_type(fn_name, val, expected_base, allow_none):
    if val is None:
        if allow_none:
            return None
        return f"Hàm `{fn_name}` trả về `None`, nhưng đề yêu cầu trả về kiểu `{expected_base}`."
    if expected_base == "int":
        if isinstance(val, bool) or not isinstance(val, int):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu kiểu `int` (không phải `bool`)."
    elif expected_base == "float":
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(float(val)):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu số thực `float` hữu hạn."
    elif expected_base == "bool":
        if not isinstance(val, bool):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu kiểu `bool` (True/False)."
    elif expected_base == "list":
        if not isinstance(val, list):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu trả về `list`."
    elif expected_base == "dict":
        if not isinstance(val, dict):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu trả về `dict`."
    elif expected_base == "tuple":
        if not isinstance(val, tuple):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu trả về `tuple`."
    elif expected_base == "set":
        if not isinstance(val, set):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu trả về `set`."
    elif expected_base == "str":
        if not isinstance(val, str):
            return f"Hàm `{fn_name}` trả về `{val!r}` (kiểu `{type(val).__name__}`), nhưng đề yêu cầu trả về `str`."
    return None


def _values_equal(actual, expected):
    if isinstance(expected, float) or isinstance(actual, float):
        if isinstance(actual, bool) or isinstance(expected, bool):
            return actual == expected
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            return math.isclose(float(actual), float(expected), rel_tol=1e-4, abs_tol=1e-4)
        return False
    if type(actual) is not type(expected):
        return False
    return actual == expected


def main_harness():
    with open(sys.argv[1], "r", encoding="utf-8") as cf_in:
        cfg = json.load(cf_in)
    code_path = cfg["code_path"]
    req_funcs = cfg["req_funcs"]
    req_classes = cfg["req_classes"]
    return_types = cfg["return_types"]
    allow_none_funcs = set(cfg["allow_none_funcs"])
    allow_mutation = bool(cfg["allow_mutation"])
    check_zero_vec = bool(cfg["check_zero_vec"])
    examples = cfg["examples"]
    enforce_main_calls = bool(cfg["enforce_main_calls"])

    with open(code_path, "r", encoding="utf-8") as fh:
        source = fh.read()

    tree = ast.parse(source, filename=code_path)
    main_guard_nodes = []
    def_body = []
    for stmt in tree.body:
        if (
            isinstance(stmt, ast.If)
            and isinstance(stmt.test, ast.Compare)
            and len(stmt.test.ops) == 1
            and isinstance(stmt.test.ops[0], ast.Eq)
            and (
                (isinstance(stmt.test.left, ast.Name) and stmt.test.left.id == "__name__")
                or (isinstance(stmt.test.comparators[0], ast.Name) and stmt.test.comparators[0].id == "__name__")
            )
        ):
            main_guard_nodes.extend(stmt.body)
        else:
            def_body.append(stmt)

    mod_tree = ast.Module(body=def_body, type_ignores=[])
    ast.fix_missing_locations(mod_tree)
    ns = {"__name__": "__main__", "__file__": code_path}
    exec(compile(mod_tree, code_path, "exec"), ns)

    issues = []
    call_counts = {name: 0 for name in req_funcs}
    class_counts = {name: 0 for name in req_classes}
    observed_calls = {}
    orig_funcs = {}

    for fn_name in list(ns.keys()):
        obj = ns[fn_name]
        if callable(obj) and not isinstance(obj, type) and fn_name != "main" and not fn_name.startswith("_"):
            orig_funcs[fn_name] = obj

            def _make_spy(name, target):
                def _spy(*args, **kwargs):
                    call_counts[name] = call_counts.get(name, 0) + 1
                    snap_args = None
                    if not allow_mutation:
                        try:
                            snap_args = copy.deepcopy(args)
                        except Exception:
                            snap_args = None
                    res = target(*args, **kwargs)
                    if name not in observed_calls and snap_args is not None:
                        observed_calls[name] = (snap_args, copy.deepcopy(kwargs), res)
                    if snap_args is not None and res is not None and not allow_mutation:
                        for idx, (before_a, after_a) in enumerate(zip(snap_args, args)):
                            if isinstance(before_a, (list, dict, set)) and before_a != after_a:
                                issues.append(
                                    f"Hàm `{name}` làm thay đổi trực tiếp dữ liệu đầu vào tham số thứ {idx + 1} (`{type(before_a).__name__}`). "
                                    f"Hãy sao chép dữ liệu (vd `dict(...)` / `deque(...)`) thay vì xóa/sửa trực tiếp biến của người gọi."
                                )
                                break
                    if name in return_types:
                        rt_err = _check_return_type(name, res, return_types[name], name in allow_none_funcs)
                        if rt_err and rt_err not in issues:
                            issues.append(rt_err)
                    return res
                return _spy

            ns[fn_name] = _make_spy(fn_name, obj)

    for cls_name in req_classes:
        cls_obj = ns.get(cls_name)
        if isinstance(cls_obj, type) and hasattr(cls_obj, "__init__"):
            orig_init = cls_obj.__init__

            def _make_init_spy(cname, target_init):
                def _init_spy(self, *a, **kw):
                    class_counts[cname] = class_counts.get(cname, 0) + 1
                    return target_init(self, *a, **kw)
                return _init_spy

            cls_obj.__init__ = _make_init_spy(cls_name, orig_init)

    # Execute __main__ block if present (suppressing stdout into devnull)
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        if main_guard_nodes:
            guard_mod = ast.Module(body=main_guard_nodes, type_ignores=[])
            ast.fix_missing_locations(guard_mod)
            exec(compile(guard_mod, code_path, "exec"), ns)
    finally:
        sys.stdout = old_stdout

    if enforce_main_calls:
        uncalled = [f for f in req_funcs if call_counts.get(f, 0) == 0 and f in orig_funcs]
        uncalled_cls = [c for c in req_classes if class_counts.get(c, 0) == 0 and isinstance(ns.get(c), type)]
        missing_calls = uncalled + uncalled_cls
        if missing_calls:
            issues.append(
                "Hàm `main()` chưa gọi kiểm thử đầy đủ tất cả hàm/lớp đề yêu cầu (còn thiếu: "
                + ", ".join(missing_calls)
                + "). Hãy gọi đầy đủ và print kết quả trong `main()`."
            )

    # Verify explicit prompt literal examples
    for call_src, expected_literal in examples:
        try:
            actual_val = eval(call_src, dict(ns))
        except Exception as exc:
            issues.append(f"Chạy ca ví dụ trong đề `{call_src}` bị lỗi `{type(exc).__name__}: {exc}`.")
            continue
        if not _values_equal(actual_val, expected_literal):
            issues.append(
                f"Sai kết quả trên ví dụ của đề: `{call_src}` trả về `{actual_val!r}`, nhưng đề yêu cầu `{expected_literal!r}`."
            )

    # Targeted adversarial edge-case probes based on observed call shapes
    for fn_name, target in orig_funcs.items():
        obs = observed_calls.get(fn_name)
        is_path_fn = any(
            tok in fn_name.lower()
            for tok in ("tim_duong", "duong_di", "bfs", "dfs", "ucs", "astar", "a_star", "shortest_path", "find_path")
        )
        if is_path_fn and return_types.get(fn_name) in ("list", None):
            if obs is None:
                pass
            else:
                o_args, _, o_res = obs
                if o_res is None:
                    issues.append(
                        f"Trong `main()`, hàm tìm đường `{fn_name}` trả về `None` trên dữ liệu mẫu (chưa kiểm chứng được nhánh tìm thấy đường đi). "
                        f"Hãy kiểm tra lại logic chuyển trạng thái và cho dữ liệu mẫu có nghiệm hợp lệ trong `main()`."
                    )
                elif isinstance(o_res, list) and len(o_res) == 1:
                    # Check if grid > 1x1 or start != goal
                    non_trivial = False
                    if len(o_args) >= 1 and isinstance(o_args[0], list) and (len(o_args[0]) > 1 or (o_args[0] and isinstance(o_args[0][0], list) and len(o_args[0][0]) > 1)):
                        non_trivial = True
                    elif len(o_args) >= 3 and o_args[1] != o_args[2]:
                        non_trivial = True
                    if non_trivial:
                        issues.append(
                            f"Hàm tìm đường `{fn_name}` chỉ trả về 1 phần tử `{o_res!r}` thay vì toàn bộ danh sách đường đi từ điểm đầu đến đích! "
                            f"BẮT BUỘC lưu kèm đường đi `path + [trang_thai_ke]` trong hàng đợi/ngăn xếp hoặc dùng `parent` để truy vết từ xuất phát tới đích."
                        )

        if not obs:
            continue
        obs_args, obs_kw, obs_res = obs
        if obs_kw:
            continue

        # 1. 2-vector float similarity / distance -> test zero-vector boundary
        if (
            (check_zero_vec or return_types.get(fn_name) == "float" or "cosine" in fn_name.lower())
            and len(obs_args) == 2
            and all(isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v) for v in obs_args)
            and len(obs_args[0]) == len(obs_args[1])
        ):
            zeros = [0] * len(obs_args[0])
            for probe_pair in ((copy.deepcopy(obs_args[0]), zeros), (zeros, copy.deepcopy(obs_args[1])), (zeros, list(zeros))):
                try:
                    z_res = target(*probe_pair)
                    if isinstance(z_res, float) and not math.isfinite(z_res):
                        issues.append(f"Hàm `{fn_name}` trả về `{z_res}` khi gặp vector 0 `{zeros}`.")
                        break
                except ZeroDivisionError:
                    issues.append(
                        f"Lỗi chia cho 0 (`ZeroDivisionError`) trong `{fn_name}` khi một trong hai vector bằng 0! "
                        f"BẮT BUỘC kiểm tra `if norm1 == 0 or norm2 == 0: return 0.0` (dùng `or`, KHÔNG dùng `and`)."
                    )
                    break
                except Exception:
                    pass

        # 2. Graph dict (graph, start, goal) -> test sink node missing from keys, unreachable, and 2-cycle
        if (
            len(obs_args) == 3
            and isinstance(obs_args[0], dict)
            and obs_args[0]
            and all(isinstance(k, str) and isinstance(v, (list, tuple, set)) for k, v in obs_args[0].items())
            and isinstance(obs_args[1], str)
            and isinstance(obs_args[2], str)
        ):
            # Sink vertex '__B__' not in dict keys -> catches `graph[curr]` KeyError!
            try:
                sink_res = target({"__A__": ["__B__"]}, "__A__", "__C__")
                if sink_res not in (None, [], False):
                    issues.append(f"Hàm `{fn_name}` trả về `{sink_res!r}` khi không có đường tới đích (cần trả về `None`).")
            except KeyError as exc:
                issues.append(
                    f"Hàm `{fn_name}` bị lỗi `KeyError: {exc}` khi đỉnh kề không nằm trong khóa của `graph`! "
                    f"Hãy dùng `graph.get(current, [])` thay vì `graph[current]`."
                )
            except Exception as exc:
                issues.append(f"Hàm `{fn_name}` lỗi khi kiểm tra đồ thị không tới được đích: `{type(exc).__name__}: {exc}`.")

            # Cyclic graph -> catches missing `visited` or wrong return value
            try:
                cyc_res = target({"__A__": ["__B__"], "__B__": ["__A__", "__C__"], "__C__": []}, "__A__", "__C__")
                if isinstance(obs_res, list) and cyc_res != ["__A__", "__B__", "__C__"]:
                    issues.append(
                        f"Hàm `{fn_name}` trả về `{cyc_res!r}` thay vì đường đi `['__A__', '__B__', '__C__']` trên đồ thị có chu trình."
                    )
            except RecursionError:
                issues.append(f"Hàm `{fn_name}` bị lặp vô hạn (`RecursionError`) trên đồ thị có chu trình — cần dùng tập `visited`.")
            except Exception as exc:
                issues.append(f"Hàm `{fn_name}` lỗi trên đồ thị có chu trình: `{type(exc).__name__}: {exc}`.")

        # 3. Propositional facts dict[str, bool] -> dict[str, bool]: test all-True and all-False facts
        if (
            len(obs_args) == 1
            and isinstance(obs_args[0], dict)
            and obs_args[0]
            and all(isinstance(k, str) and isinstance(v, bool) for k, v in obs_args[0].items())
            and isinstance(obs_res, dict)
        ):
            for fill_bool in (True, False):
                probe_facts = {k: fill_bool for k in obs_args[0]}
                try:
                    p_res = target(probe_facts)
                    if not isinstance(p_res, dict):
                        issues.append(f"Hàm `{fn_name}` không trả về `dict` khi thử `facts={probe_facts}`.")
                        break
                except KeyError as exc:
                    issues.append(
                        f"Hàm `{fn_name}` bị `KeyError: {exc}` khi các biến tiền đề mang giá trị `{fill_bool}`! "
                        f"Không đọc trực tiếp `facts[{exc}]` cho biến kết luận chưa có trong `facts`; hãy dùng `.get(..., False)`."
                    )
                    break
                except Exception as exc:
                    issues.append(f"Hàm `{fn_name}` lỗi với `facts={probe_facts}`: `{type(exc).__name__}: {exc}`.")
                    break

    print("__SEMANTIC_RESULT__" + json.dumps({"issues": issues[:4]}, ensure_ascii=False))


if __name__ == "__main__":
    main_harness()
'''


def verify_candidate_semantics(
    code: str,
    prompt: str = "",
    starter_code: str = "",
    *,
    editing_existing: bool = False,
    working_dir: Optional[str] = None,
    timeout: float = 2.8,
) -> str:
    """
    Run deep static + dynamic semantic & boundary verification in an isolated subprocess.
    Returns `""` when all checks pass, or a concise Vietnamese diagnostic string for LLM self-repair.
    """
    stub_err = check_unfinished_stubs(code, prompt, starter_code)
    if stub_err:
        return stub_err

    if editing_existing:
        return ""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return ""

    defined_funcs = [
        node.name for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name != "main" and not node.name.startswith("_")
    ]
    req_classes, req_funcs, _ = extract_prompt_api_names(prompt)
    return_types = extract_prompt_return_types(prompt)
    examples = extract_prompt_literal_examples(prompt, defined_funcs)

    folded = strip_accents(prompt).casefold()
    allow_none_funcs = [
        fn for fn in set(defined_funcs) | set(req_funcs)
        if "none" in folded or "khong tim thay" in folded or "khong toi duoc" in folded or "vo nghiem" in folded
    ]
    allow_mutation = any(
        kw in folded for kw in ("tai cho", "in-place", "in_place", "cap nhat truc tiep", "thay doi truc tiep")
    )
    check_zero_vec = any(kw in folded for kw in ("chia cho 0", "chuan bang 0", "do dai bang 0", "cosine"))
    enforce_main_calls = not prompt_forbids_print(prompt) and (len(req_funcs) + len(req_classes) >= 2)

    # Skip spawning extra process if there are no functions/classes/contracts to verify
    if not defined_funcs and not req_classes and not return_types and not examples:
        return ""

    code_path = None
    harness_path = None
    cfg_path = None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    cwd = str(Path(working_dir).resolve()) if (working_dir and Path(working_dir).is_dir()) else None
    py_exe = find_best_python_executable()

    required_env = {"path", "systemroot", "windir", "temp", "tmp"}
    env = {name: value for name, value in os.environ.items() if name.lower() in required_env}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    py_paths: List[str] = []
    if cwd:
        py_paths.append(cwd)
    if ".venv" not in py_exe.lower():
        offline_site = Path(__file__).resolve().parents[1] / "setup_lab" / "offline_pkgs"
        if offline_site.exists():
            py_paths.append(str(offline_site))
    if py_paths:
        env["PYTHONPATH"] = os.pathsep.join(py_paths)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False, dir=cwd) as cf:
            cf.write(code)
            code_path = cf.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as hf:
            hf.write(_HARNESS_SCRIPT)
            harness_path = hf.name
        payload_dict = {
            "code_path": code_path,
            "req_funcs": req_funcs,
            "req_classes": req_classes,
            "return_types": return_types,
            "allow_none_funcs": allow_none_funcs,
            "allow_mutation": allow_mutation,
            "check_zero_vec": check_zero_vec,
            "examples": examples,
            "enforce_main_calls": enforce_main_calls,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as jf:
            json.dump(payload_dict, jf, ensure_ascii=False)
            cfg_path = jf.name

        proc = subprocess.run(
            [py_exe, harness_path, cfg_path],
            input="5\n1 2 3 4 5\n1\n2\n3\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=env,
            creationflags=creationflags,
        )
        if proc.returncode != 0:
            return ""
        marker = "__SEMANTIC_RESULT__"
        idx = proc.stdout.find(marker)
        if idx == -1:
            return ""
        data = json.loads(proc.stdout[idx + len(marker) :].strip())
        issues = data.get("issues") or []
        return "\n".join(issues)
    except subprocess.TimeoutExpired:
        return (
            "Chương trình bị treo quá thời gian (vòng lặp vô hạn) khi kiểm thử trường hợp biên/đồ thị có chu trình. "
            "Hãy kiểm tra điều kiện dừng và tập `visited`."
        )
    except Exception:
        return ""
    finally:
        for p in (code_path, harness_path, cfg_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
