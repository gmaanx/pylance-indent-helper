# -*- coding: utf-8 -*-
"""
Module 4: Tram Kiem Dinh Ngam & Tu Chua Lanh (shadow_runner_healer.py).
1. Static AST Auto-Healer: Tu dong phat hien va sua 4 bay kinh dien cua SimpleAI:
   - Bay 1 (TypeError: unhashable type 'list'): Tu dong boc tuple / tuple(map(tuple, ...)) cho INITIAL va result().
   - Bay 2 (Sai chu ky ham CSP): Tu dong chuan hoa `def func(a, b):` thanh `def func(variables, values):`.
   - Bay 3 (Quen super().__init__(initial_state)): Tu dong chen vao SearchProblem.__init__.
   - Bay 4 (Lap vo tan tren do thi): Tu dong them `graph_search=True` cho breadth_first, depth_first, uniform_cost, greedy, astar.
2. Shadow Execution: Chay thu ngam bang subprocess voi co `CREATE_NO_WINDOW` tren Windows
   (dam bao TUYET DOI KHONG nhay cua so den cmd/console), timeout=2.5s, tu dong sua loi Traceback.
"""

import ast
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple

GRAPH_SEARCH_ALGOS = {
    "breadth_first",
    "depth_first",
    "uniform_cost",
    "greedy",
    "astar",
}
LOCAL_SEARCH_ALGOS = {
    "hill_climbing",
    "hill_climbing_random_restarts",
    "hill_climbing_stochastic",
    "simulated_annealing",
    "beam",
    "beam_best_first",
    "genetic",
}
NO_GRAPH_SEARCH_ALGOS = LOCAL_SEARCH_ALGOS | {"backtrack", "min_conflicts", "convert_to_binary"}


def _make_hashable_helper_node() -> ast.FunctionDef:
    helper_src = (
        "def _to_hashable(obj):\n"
        "    if isinstance(obj, (list, tuple)):\n"
        "        return tuple(_to_hashable(x) for x in obj)\n"
        "    if isinstance(obj, dict):\n"
        "        return tuple(sorted((k, _to_hashable(v)) for k, v in obj.items()))\n"
        "    if isinstance(obj, set):\n"
        "        return frozenset(_to_hashable(x) for x in obj)\n"
        "    return obj\n"
    )
    return ast.parse(helper_src).body[0]  # type: ignore[return-value]


class _SimpleAIHealerTransformer(ast.NodeTransformer):
    def __init__(self, csp_constraint_funcs: Set[str], *, uses_local_search: bool = False) -> None:
        super().__init__()
        self.csp_funcs = csp_constraint_funcs
        self.uses_local_search = uses_local_search
        self.needs_hashable_helper = False
        self.in_search_problem_class = False
        self.is_string_problem = False
        self.search_node_vars: Set[str] = set()
        self.csp_dict_vars: Set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        self.generic_visit(node)
        # Bay 1A: INITIAL / INITIAL_STATE / GOAL khai bao kieu list -> chuyen sang tuple
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.upper() in (
                "INITIAL",
                "INITIAL_STATE",
                "GOAL",
                "GOAL_STATE",
                "STANDARD_GOAL",
            ):
                if isinstance(node.value, ast.List):
                    self.needs_hashable_helper = True
                    node.value = ast.Call(
                        func=ast.Name(id="_to_hashable", ctx=ast.Load()),
                        args=[node.value],
                        keywords=[],
                    )
        # Track variables holding SimpleAI SearchNode results (`res = astar(...)` / `hill_climbing_random_restarts(...)`)
        if isinstance(node.value, ast.Call):
            fn = node.value.func.id if isinstance(node.value.func, ast.Name) else (
                node.value.func.attr if isinstance(node.value.func, ast.Attribute) else ""
            )
            if fn in (GRAPH_SEARCH_ALGOS | LOCAL_SEARCH_ALGOS):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.search_node_vars.add(target.id)
            elif fn in ("backtrack", "min_conflicts"):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.csp_dict_vars.add(target.id)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        # Bay 8: backtrack(problem) tra ve dict truc tiep (khong co .state nhu SearchNode)
        if node.attr == "state" and isinstance(node.value, ast.Name) and node.value.id in self.csp_dict_vars:
            return ast.Name(id=node.value.id, ctx=node.ctx)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        base_names = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                base_names.append(b.id)
            elif isinstance(b, ast.Attribute):
                base_names.append(b.attr)

        is_sp = any("Problem" in bn or bn == "SearchProblem" for bn in base_names)
        prev_sp = self.in_search_problem_class
        prev_str = self.is_string_problem

        if is_sp:
            self.in_search_problem_class = True
            self.is_string_problem = "Xau" in node.name or "Hello" in node.name or "String" in node.name
            self._heal_search_problem_init(node)
            self._heal_goal_test_alias(node)
            if self.uses_local_search:
                self._heal_local_search_value(node)

        self.generic_visit(node)
        self.in_search_problem_class = prev_sp
        self.is_string_problem = prev_str
        return node

    def _heal_goal_test_alias(self, cls_node: ast.ClassDef) -> None:
        # Bay 6: LLM viet nham `def goal_test(self, state):` (kieu AIMA) thay vi `def is_goal(self, state):` cua SimpleAI
        method_names = {item.name for item in cls_node.body if isinstance(item, ast.FunctionDef)}
        if "is_goal" not in method_names and "goal_test" in method_names:
            for item in cls_node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "goal_test":
                    item.name = "is_goal"
                    break

    def _heal_local_search_value(self, cls_node: ast.ClassDef) -> None:
        # Bay 5: Local search (hill_climbing, simulated_annealing, genetic, beam) can ham value(self, state)
        method_names = {item.name for item in cls_node.body if isinstance(item, ast.FunctionDef)}
        if "value" not in method_names and "heuristic" in method_names:
            val_fn = ast.parse("def value(self, state):\n    return -self.heuristic(state)\n").body[0]
            cls_node.body.append(val_fn)

    def _heal_search_problem_init(self, cls_node: ast.ClassDef) -> None:
        # Bay 3: Quen goi super().__init__(initial_state) trong SearchProblem.__init__
        for item in cls_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                has_super = False
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Call):
                        if isinstance(stmt.func, ast.Attribute) and stmt.func.attr == "__init__":
                            has_super = True
                            break
                if not has_super and len(item.args.args) >= 2:
                    init_arg_name = item.args.args[1].arg
                    super_stmt = ast.parse(f"super().__init__({init_arg_name})").body[0]
                    # Chen sau docstring neu co, nguoc lai chen dau ham
                    insert_idx = 0
                    if (
                        item.body
                        and isinstance(item.body[0], ast.Expr)
                        and isinstance(item.body[0].value, ast.Constant)
                        and isinstance(item.body[0].value.value, str)
                    ):
                        insert_idx = 1
                    item.body.insert(insert_idx, super_stmt)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        # Bay 2: Ham constraint cua CspProblem viet sai chu ky def f(a, b): hoac def f(v1, v2, v3):
        if node.name in self.csp_funcs:
            arg_names = [a.arg for a in node.args.args]
            # Trong SimpleAI CSP, ham constraint phai la def func(variables, values):
            # Neu AI viet def func(a, b): va dung a != b (coi tham so la gia tri cua bien)
            if len(arg_names) >= 2 and arg_names[0] not in ("variables", "vars", "vars_tuple", "bien"):
                # Kiem tra xem ham co unpack variables, values khong
                second_name = arg_names[1]
                if second_name not in ("values", "vals", "vals_tuple", "gia_tri"):
                    old_params = list(arg_names)
                    node.args.args = [
                        ast.arg(arg="variables"),
                        ast.arg(arg="values"),
                    ]
                    unpack_targets = ", ".join(old_params)
                    unpack_stmt = ast.parse(f"{unpack_targets} = values").body[0]
                    insert_idx = 0
                    if (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    ):
                        insert_idx = 1
                    node.body.insert(insert_idx, unpack_stmt)

        # Bay 1B: result(self, state, action) tra ve kieu list/unhashable (ke ca qua bien trung gian `return new_state`)
        if self.in_search_problem_class and node.name == "result" and not self.is_string_problem:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None:
                    already_wrapped = (
                        isinstance(sub.value, ast.Call)
                        and isinstance(sub.value.func, ast.Name)
                        and sub.value.func.id in ("_to_hashable", "tuple", "frozenset", "str", "int", "float", "bool")
                    )
                    if not already_wrapped and isinstance(
                        sub.value, (ast.List, ast.ListComp, ast.Dict, ast.Set, ast.Name, ast.Tuple, ast.Subscript)
                    ):
                        self.needs_hashable_helper = True
                        sub.value = ast.Call(
                            func=ast.Name(id="_to_hashable", ctx=ast.Load()),
                            args=[sub.value],
                            keywords=[],
                        )

        self.generic_visit(node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        # Bay 4: Quen graph_search=True khi goi thuat toan tim kiem SimpleAI (hoac truyen nham vao local search / CSP)
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in ("tuple", "list") and len(node.args) == 1 and isinstance(node.args[0], ast.Name):
            if node.args[0].id in self.search_node_vars:
                node.args[0] = ast.Attribute(
                    value=ast.Name(id=node.args[0].id, ctx=ast.Load()),
                    attr="state",
                    ctx=ast.Load(),
                )
        elif func_name in NO_GRAPH_SEARCH_ALGOS:
            node.keywords = [kw for kw in node.keywords if kw.arg != "graph_search"]
        elif func_name in GRAPH_SEARCH_ALGOS and not self.is_string_problem:
            has_gs = any(kw.arg == "graph_search" for kw in node.keywords)
            has_kwargs_unpack = any(kw.arg is None for kw in node.keywords)
            if not has_gs and not has_kwargs_unpack and len(node.args) == 1:
                node.keywords.append(
                    ast.keyword(arg="graph_search", value=ast.Constant(value=True))
                )
        return node


def _collect_csp_constraint_func_names(tree: ast.AST) -> Set[str]:
    """Tìm tên các hàm được truyền vào danh sách constraints của CspProblem."""
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            first, second = node.elts
            if isinstance(second, ast.Name) and isinstance(
                first, (ast.Tuple, ast.List, ast.Name, ast.Call)
            ):
                names.add(second.id)
    return names


def _detect_local_search_usage(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "local" in node.module:
            return True
        if isinstance(node, ast.Call):
            fn = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if fn in LOCAL_SEARCH_ALGOS:
                return True
    return False


_AUTO_STDLIB_MODULES = {
    "heapq", "math", "random", "itertools", "functools", "collections",
    "re", "json", "copy", "bisect", "statistics", "time", "sys", "os", "unicodedata",
}
_AUTO_COLLECTIONS_SYMBOLS = {"deque", "defaultdict", "Counter"}
_AUTO_SIMPLEAI_SEARCH_SYMBOLS = {
    "SearchProblem", "CspProblem", "breadth_first", "depth_first", "uniform_cost", "greedy", "astar",
    "backtrack", "MOST_CONSTRAINED_VARIABLE", "HIGHEST_DEGREE_VARIABLE", "LEAST_CONSTRAINING_VALUE", "min_conflicts",
}
_AUTO_SIMPLEAI_LOCAL_SYMBOLS = {
    "hill_climbing", "hill_climbing_random_restarts", "hill_climbing_stochastic",
    "simulated_annealing", "beam", "genetic",
}


def _inject_missing_stdlib_imports(code: str) -> str:
    """Prepend missing standard library imports (e.g. `import heapq`, `import math`) without altering code formatting."""
    if not code or not code.strip():
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    bound: Set[str] = set()
    star_modules: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    if node.module:
                        star_modules.add(node.module)
                else:
                    bound.add(alias.asname or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound.add(node.name)
            for arg_group in (node.args.posonlyargs, node.args.args, node.args.kwonlyargs):
                for a in arg_group:
                    bound.add(a.arg)
            if node.args.vararg:
                bound.add(node.args.vararg.arg)
            if node.args.kwarg:
                bound.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)

    missing_mods: List[str] = []
    missing_coll: List[str] = []
    missing_sa_search: List[str] = []
    missing_sa_local: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            ident = node.id
            if ident in bound:
                continue
            if ident in _AUTO_STDLIB_MODULES and ident not in missing_mods:
                missing_mods.append(ident)
            elif ident in _AUTO_COLLECTIONS_SYMBOLS and "collections" not in star_modules and ident not in missing_coll:
                missing_coll.append(ident)
            elif ident in _AUTO_SIMPLEAI_SEARCH_SYMBOLS and "simpleai.search" not in star_modules and ident not in missing_sa_search:
                missing_sa_search.append(ident)
            elif ident in _AUTO_SIMPLEAI_LOCAL_SYMBOLS and "simpleai.search.local" not in star_modules and ident not in missing_sa_local:
                missing_sa_local.append(ident)

    if not missing_mods and not missing_coll and not missing_sa_search and not missing_sa_local:
        return code

    import_lines: List[str] = [f"import {m}" for m in sorted(missing_mods)]
    if missing_coll:
        import_lines.append(f"from collections import {', '.join(sorted(missing_coll))}")
    if missing_sa_search:
        import_lines.append(f"from simpleai.search import {', '.join(sorted(missing_sa_search))}")
    if missing_sa_local:
        import_lines.append(f"from simpleai.search.local import {', '.join(sorted(missing_sa_local))}")

    src_lines = code.splitlines()
    insert_at = 0
    for idx, stmt in enumerate(tree.body):
        if (
            idx == 0
            and isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            insert_at = getattr(stmt, "end_lineno", stmt.lineno)
        elif isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            insert_at = getattr(stmt, "end_lineno", stmt.lineno)
        else:
            break
    while insert_at < len(src_lines) and src_lines[insert_at].strip().startswith("#"):
        insert_at += 1

    new_lines = src_lines[:insert_at] + import_lines + src_lines[insert_at:]
    return "\n".join(new_lines) + ("\n" if code.endswith("\n") else "")


def static_auto_heal(code: str) -> str:
    """
    Phân tích AST và tự động sửa các bẫy cú pháp đặc thù của SimpleAI.
    Nếu code không parse được AST, trả nguyên bản để tầng sau xử lý.
    """
    if not code or not code.strip():
        return code
    code = _inject_missing_stdlib_imports(code)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    # Kiem tra xem code co dung SinhXauProblem khong (tranh ep graph_search neu khong can)
    is_str_prob = "SinhXauProblem" in code or "HelloProblem" in code
    csp_funcs = _collect_csp_constraint_func_names(tree)
    uses_local = _detect_local_search_usage(tree)

    transformer = _SimpleAIHealerTransformer(csp_funcs, uses_local_search=uses_local)
    transformer.is_string_problem = is_str_prob
    healed_tree = transformer.visit(tree)

    if transformer.needs_hashable_helper and "_to_hashable" not in code:
        helper_node = _make_hashable_helper_node()
        # Chen ngay sau cac dong import dau file
        insert_pos = 0
        for idx, stmt in enumerate(healed_tree.body):
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                insert_pos = idx + 1
            elif (
                idx == 0
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                insert_pos = 1
        healed_tree.body.insert(insert_pos, helper_node)

    ast.fix_missing_locations(healed_tree)
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(healed_tree)
        except Exception:
            return code
    return _regex_heal_python38(code)


def _regex_heal_python38(code: str) -> str:
    """Fallback healer for Python 3.8 where ast.unparse is unavailable."""
    import re
    out = code
    for alg in GRAPH_SEARCH_ALGOS:
        out = re.sub(
            rf"\b{alg}\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
            rf"{alg}(\1, graph_search=True)",
            out,
        )
    return out


def static_auto_heal_preserve_style(code: str) -> str:
    """
    Chỉ áp dụng AST unparse khi thực sự phát hiện lỗi tĩnh của SimpleAI,
    giữ nguyên 100% định dạng khoảng trắng và comment gốc của Phôi Vàng nếu code đã chuẩn!
    """
    if not code or not code.strip():
        return code
    code = _inject_missing_stdlib_imports(code)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    needs_fix = False
    csp_funcs = _collect_csp_constraint_func_names(tree)
    uses_local = _detect_local_search_usage(tree)
    snode_vars: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn0 = node.value.func.id if isinstance(node.value.func, ast.Name) else (
                node.value.func.attr if isinstance(node.value.func, ast.Attribute) else ""
            )
            if fn0 in (GRAPH_SEARCH_ALGOS | LOCAL_SEARCH_ALGOS):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        snode_vars.add(t.id)

    for node in ast.walk(tree):
        # Check Bay 1A: INITIAL = [...]
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.upper() in ("INITIAL", "INITIAL_STATE", "GOAL", "GOAL_STATE"):
                    if isinstance(node.value, ast.List):
                        needs_fix = True
        # Check Bay 2: CSP constraint signature
        if isinstance(node, ast.FunctionDef) and node.name in csp_funcs:
            args = [a.arg for a in node.args.args]
            if len(args) >= 2 and args[0] not in ("variables", "vars", "vars_tuple", "bien") and args[1] not in ("values", "vals", "vals_tuple", "gia_tri"):
                needs_fix = True
        # Check Bay 4 invalid graph_search on local/CSP
        if isinstance(node, ast.Call):
            fn = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else ""
            )
            if fn in NO_GRAPH_SEARCH_ALGOS and any(kw.arg == "graph_search" for kw in node.keywords):
                needs_fix = True
            if fn in ("tuple", "list") and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id in snode_vars:
                needs_fix = True
        # Check Bay 3, Bay 1B, and Bay 5 on SearchProblem
        if isinstance(node, ast.ClassDef):
            bases = [
                b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else "")
                for b in node.bases
            ]
            if any("Problem" in bn or bn == "SearchProblem" for bn in bases):
                method_names = {it.name for it in node.body if isinstance(it, ast.FunctionDef)}
                if "is_goal" not in method_names and "goal_test" in method_names:
                    needs_fix = True
                if uses_local and "value" not in method_names and "heuristic" in method_names:
                    needs_fix = True
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        has_sup = any(
                            isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute) and s.func.attr == "__init__"
                            for s in ast.walk(item)
                        )
                        if not has_sup and len(item.args.args) >= 2:
                            needs_fix = True
                    if isinstance(item, ast.FunctionDef) and item.name == "result":
                        body_builds_list = any(
                            isinstance(s, (ast.List, ast.ListComp))
                            or (isinstance(s, ast.Call) and isinstance(s.func, ast.Name) and s.func.id == "list")
                            for s in ast.walk(item)
                        )
                        for s in ast.walk(item):
                            if isinstance(s, ast.Return) and s.value is not None:
                                if isinstance(s.value, (ast.List, ast.ListComp, ast.Dict, ast.Set)):
                                    needs_fix = True
                                elif body_builds_list and isinstance(s.value, ast.Name):
                                    needs_fix = True

    if needs_fix:
        return static_auto_heal(code)
    return code


@dataclass
class ShadowRunResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    elapsed_sec: float
    summary: str


def find_best_python_executable() -> str:
    """
    Tìm trình thông dịch Python có cài sẵn `simpleai` / `kanren` ưu tiên nhất
    (hỗ trợ cả môi trường `.venv` của môn học hoặc Python hệ thống phòng máy).
    """
    candidates: List[str] = []
    # 1. Check UEH course venv if present
    ueh_venv = Path(__file__).resolve().parents[2] / ".venv" / "Scripts" / "python.exe"
    if ueh_venv.exists():
        candidates.append(str(ueh_venv))
    local_venv = Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"
    if local_venv.exists():
        candidates.append(str(local_venv))

    # 2. Current sys.executable (neu dang chay bang pythonw.exe thi doi sang python.exe cho subprocess)
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        py_console = exe.with_name("python.exe")
        if py_console.exists():
            candidates.append(str(py_console))
    candidates.append(sys.executable)

    for cand in candidates:
        if Path(cand).exists():
            return cand
    return sys.executable


def shadow_execute(
    code: str,
    timeout: float = 2.5,
    *,
    stdin_data: str = "5\n1 2 3 4 5\n1\n2\n3\n",
    working_dir: Optional[str] = None,
) -> ShadowRunResult:
    """Run candidate or test code in a hidden subprocess with non-blocking sample stdin."""
    py_exe = find_best_python_executable()
    run_cwd: Optional[str] = None
    if working_dir and Path(working_dir).is_dir():
        run_cwd = str(Path(working_dir).resolve())

    fd, tmp_path = tempfile.mkstemp(prefix="pylance_lint_", suffix=".py")
    os.close(fd)

    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    required_env = {"path", "systemroot", "windir", "temp", "tmp", "localappdata", "appdata", "userprofile"}
    env = {name: value for name, value in os.environ.items() if name.lower() in required_env}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    python_paths: List[str] = []
    if run_cwd:
        python_paths.append(run_cwd)
    engine_parent = Path(__file__).resolve().parents[1]
    extra_pkg_candidates = [
        engine_parent / "site_pkgs",
        engine_parent / "shared_pkgs",
        engine_parent.parent / "shared_pkgs",
        engine_parent / "setup_lab" / "offline_pkgs",
    ]
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        extra_pkg_candidates.append(Path(local_appdata) / "Programs" / "PylanceHelper" / "shared_pkgs")
    for cand_site in extra_pkg_candidates:
        if cand_site.is_dir():
            s_str = str(cand_site)
            if s_str not in python_paths:
                python_paths.append(s_str)
    if python_paths:
        cur_pp = env.get("PYTHONPATH", "")
        joined = os.pathsep.join(python_paths)
        env["PYTHONPATH"] = f"{joined}{os.pathsep}{cur_pp}" if cur_pp else joined

    start_t = time.perf_counter()
    try:
        Path(tmp_path).write_text(code, encoding="utf-8")
        proc = subprocess.run(
            [py_exe, tmp_path],
            input=stdin_data,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=creationflags,
            env=env,
        )
        elapsed = time.perf_counter() - start_t
        ok = proc.returncode == 0
        out_lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
        short_summary = out_lines[0][:60] if out_lines else f"{elapsed:.2f}s"
        return ShadowRunResult(
            ok=ok,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            elapsed_sec=elapsed,
            summary=short_summary,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - start_t
        return ShadowRunResult(
            ok=False,
            returncode=-1,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=f"TimeoutExpired: Qua thoi gian {timeout}s (co the bi lap vo tan hoac khong gian trang thai qua lon).",
            elapsed_sec=elapsed,
            summary="timeout",
        )
    except Exception as exc:
        elapsed = time.perf_counter() - start_t
        return ShadowRunResult(
            ok=False,
            returncode=-2,
            stdout="",
            stderr=str(exc),
            elapsed_sec=elapsed,
            summary="error",
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
