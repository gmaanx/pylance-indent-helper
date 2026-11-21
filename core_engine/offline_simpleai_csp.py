"""Bounded SimpleAI backtracking adapters for constraint exercises."""

MAX_CONSTRAINT_CHECKS = 160_000
MAX_CSP_SECONDS = 3.0
MAX_DOMAIN_VALUES = 32
MAX_CSP_VARIABLES = 24
MAX_CSP_CONSTRAINTS = 128
MAX_NQUEENS_SIZE = 14


def _constraint_holds(operation, values, detail):
    if operation == "all_different":
        return len(set(values)) == len(values)
    if operation == "sum_eq":
        return sum(values) == detail
    if operation == "table":
        return tuple(values) in detail
    left, right = values
    if operation == "eq":
        return left == right
    if operation == "ne":
        return left != right
    if operation == "lt":
        return left < right
    if operation == "le":
        return left <= right
    if operation == "abs_diff_ne":
        return abs(left - right) != detail
    if operation == "queens":
        return left != right and abs(left - right) != detail
    raise ValueError("Unsupported constraint operation")


def _run_simpleai_csp(domains, constraints, variable_order, value_order, inference, max_checks, max_seconds):
    from time import monotonic

    from simpleai.search import (
        CspProblem,
        HIGHEST_DEGREE_VARIABLE,
        LEAST_CONSTRAINING_VALUE,
        MOST_CONSTRAINED_VARIABLE,
        backtrack,
    )

    variable_heuristics = {"input": "", "mrv": MOST_CONSTRAINED_VARIABLE, "degree": HIGHEST_DEGREE_VARIABLE}
    value_heuristics = {"input": "", "lcv": LEAST_CONSTRAINING_VALUE}
    checks = 0
    deadline = monotonic() + max_seconds

    def predicate(operation, detail):
        def accepts(variables, values):
            nonlocal checks
            checks += 1
            if checks > max_checks or (checks % 64 == 1 and monotonic() >= deadline):
                raise OverflowError("SimpleAI CSP search limit exceeded")
            return _constraint_holds(operation, values, detail)

        return accepts

    normalized = [
        (operation, variables, frozenset(detail) if operation == "table" else detail)
        for operation, variables, detail in constraints
    ]
    problem = CspProblem(
        list(domains),
        {name: list(values) for name, values in domains.items()},
        [(variables, predicate(operation, detail)) for operation, variables, detail in normalized],
    )
    result = backtrack(
        problem,
        variable_heuristic=variable_heuristics[variable_order],
        value_heuristic=value_heuristics[value_order],
        inference=inference,
    )
    if result is None:
        return None
    if result.keys() != domains.keys() or any(value not in domains[name] for name, value in result.items()):
        raise RuntimeError("SimpleAI returned an assignment outside the specified domains")
    if any(
        not _constraint_holds(operation, [result[name] for name in variables], detail)
        for operation, variables, detail in normalized
    ):
        raise RuntimeError("SimpleAI returned an assignment that violates the constraints")
    return {name: result[name] for name in domains}


def _solve_nqueens(n, variable_order, value_order, inference, max_checks, max_seconds):
    columns = tuple(range(n))
    domains = {row: columns for row in range(n)}
    constraints = [
        ("queens", (left, right), right - left)
        for left in range(n) for right in range(left + 1, n)
    ]
    return _run_simpleai_csp(domains, constraints, variable_order, value_order, inference, max_checks, max_seconds)


def _heuristics(problem):
    from .offline_solver import OfflineProblemError

    variable = problem.get("variable_heuristic", "mrv")
    value = problem.get("value_heuristic", "lcv")
    inference = problem.get("inference", True)
    if variable not in ("input", "mrv", "degree"):
        raise OfflineProblemError("unsupported", "variable_heuristic hỗ trợ input, mrv và degree.")
    if value not in ("input", "lcv"):
        raise OfflineProblemError("unsupported", "value_heuristic hỗ trợ input và lcv.")
    if type(inference) is not bool:
        raise OfflineProblemError("invalid", "inference phải là true hoặc false.")
    return variable, value, inference


def _solve_and_emit(problem_type, function, extra_functions, arguments, inference):
    from .offline_solver import OfflineProblemError, OfflineSolution, _standalone

    args = (*arguments, MAX_CONSTRAINT_CHECKS, MAX_CSP_SECONDS)
    try:
        assignment = function(*args)
    except ImportError as exc:
        raise OfflineProblemError("unsupported", "Chưa có SimpleAI trong Python đang dùng. Cài thư viện offline qua setup.") from exc
    except RuntimeError as exc:
        raise OfflineProblemError("invalid", "Không xác nhận được kết quả của SimpleAI.") from exc
    summary = "Đã duyệt hết các gán khả thi. Bài toán vô nghiệm." if assignment is None else "Đã kiểm tra nghiệm theo miền và ràng buộc đã nhập."
    messages = [
        "Mã xuất sử dụng CspProblem và backtrack của SimpleAI.",
        "LCV nếu được chọn dùng cách xếp giá trị theo số xung đột của SimpleAI.",
    ]
    if inference:
        messages.append("AC-3 chỉ lan truyền ràng buộc nhị phân. Backtracking kiểm tra mọi ràng buộc.")
    if problem_type == "simpleai_nqueens":
        messages.append("Kết quả ánh xạ hàng sang cột. Cả hai bắt đầu từ 0.")
    return OfflineSolution(
        problem_type,
        _standalone((_constraint_holds, _run_simpleai_csp, *extra_functions), function, args, assignment),
        summary,
        tuple(messages),
        ("satisfiable", assignment is not None),
    )


def _simpleai_csp(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _integer, _name

    _fields(
        problem,
        ("type", "domains", "constraints"),
        ("variable_heuristic", "value_heuristic", "inference"),
    )
    variable_order, value_order, inference = _heuristics(problem)
    raw_domains = problem["domains"]
    if not isinstance(raw_domains, dict) or not 1 <= len(raw_domains) <= MAX_CSP_VARIABLES:
        raise OfflineProblemError("invalid", f"domains phải khai báo từ 1 đến {MAX_CSP_VARIABLES} biến.")

    def atom(value):
        if isinstance(value, str):
            return _name(value, "Giá trị dạng chữ")
        return _integer(value, "Giá trị miền", -1_000_000, 1_000_000)

    domains = {
        _name(name, "Tên biến"): tuple(dict.fromkeys(
            atom(value) for value in _array(values, "Miền", 1, MAX_DOMAIN_VALUES)
        ))
        for name, values in raw_domains.items()
    }
    constraints = []
    table_rows = 0
    for constraint in _array(problem["constraints"], "constraints", 0, MAX_CSP_CONSTRAINTS):
        _fields(constraint, ("op", "vars"), ("value", "allowed"))
        operation = constraint["op"]
        if operation in ("eq", "ne", "lt", "le", "abs_diff_ne"):
            min_arity, max_arity = 2, 2
        elif operation in ("sum_eq", "all_different", "table"):
            min_arity, max_arity = 1, MAX_CSP_VARIABLES
        else:
            raise OfflineProblemError("unsupported", "Phép ràng buộc SimpleAI chưa được hỗ trợ.")

        variables = tuple(_name(name, "Biến ràng buộc") for name in _array(
            constraint["vars"], "vars", min_arity, max_arity
        ))
        if len(set(variables)) != len(variables) or any(name not in domains for name in variables):
            raise OfflineProblemError("invalid", "vars cần là các biến khác nhau đã khai báo trong domains.")
        if operation in ("lt", "le", "abs_diff_ne", "sum_eq") and any(
            type(value) is not int for name in variables for value in domains[name]
        ):
            raise OfflineProblemError("invalid", f"{operation} cần miền số nguyên.")

        if operation == "table":
            _fields(constraint, ("op", "vars", "allowed"))
            rows = []
            for row in _array(constraint["allowed"], "allowed", 0, 400):
                values = tuple(atom(value) for value in _array(row, "Hàng ràng buộc", len(variables), len(variables)))
                if any(value not in domains[name] for name, value in zip(variables, values)):
                    raise OfflineProblemError("invalid", "Một hàng allowed dùng giá trị ngoài miền đã khai báo.")
                rows.append(values)
            table_rows += len(rows)
            if table_rows > 2000:
                raise OfflineProblemError("limit", "Tổng số hàng allowed vượt giới hạn 2000.")
            detail = tuple(dict.fromkeys(rows))
        elif operation in ("sum_eq", "abs_diff_ne"):
            _fields(constraint, ("op", "vars", "value"))
            lower = 0 if operation == "abs_diff_ne" else -24_000_000
            upper = 2_000_000 if operation == "abs_diff_ne" else 24_000_000
            detail = _integer(constraint["value"], "value", lower, upper)
        else:
            _fields(constraint, ("op", "vars"))
            detail = None
        constraints.append((operation, variables, detail))

    arguments = (domains, constraints, variable_order, value_order, inference)
    return _solve_and_emit("simpleai_csp", _run_simpleai_csp, (), arguments, inference)


def _simpleai_nqueens(problem):
    from .offline_solver import _fields, _integer

    _fields(problem, ("type", "n"), ("variable_heuristic", "value_heuristic", "inference"))
    variable_order, value_order, inference = _heuristics(problem)
    n = _integer(problem["n"], "n", 1, MAX_NQUEENS_SIZE)
    return _solve_and_emit(
        "simpleai_nqueens", _solve_nqueens, (_solve_nqueens,), (n, variable_order, value_order, inference), inference,
    )


SIMPLEAI_CSP_SOLVERS = {"simpleai_csp": _simpleai_csp, "simpleai_nqueens": _simpleai_nqueens}
