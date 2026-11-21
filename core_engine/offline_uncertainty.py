"""Exact probability and finite fuzzy sets for structured offline exercises."""

import re
from fractions import Fraction
from math import prod

__all__ = ["UNCERTAINTY_SOLVERS"]

_RATIONAL = re.compile(r"[+-]?(?:\d{1,18}(?:/\d{1,9}|\.\d{1,9})?|\.\d{1,9})", re.ASCII)
_DENOMINATOR_LIMIT = 1_000_000_000


def _fraction_string(value, field, upper=1):
    from .offline_solver import OfflineProblemError

    if type(value) not in (int, float, str) or (isinstance(value, str) and not _RATIONAL.fullmatch(value)):
        raise OfflineProblemError("invalid", f"{field} cần số nguyên, số thập phân hoặc chuỗi phân số.")
    try:
        number = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise OfflineProblemError("invalid", f"{field} không phải giá trị hữu hạn hoặc có mẫu bằng 0.") from exc
    if not 0 <= number <= upper or number.denominator > _DENOMINATOR_LIMIT:
        raise OfflineProblemError("invalid", f"{field} cần nằm trong [0, {upper}] với mẫu số tối đa {_DENOMINATOR_LIMIT}.")
    return str(number)


def _solution(problem_type, function, args, result, summary, notes, metric=None):
    from .offline_solver import OfflineSolution, _standalone

    imports = "from fractions import Fraction\n"
    if problem_type == "bayes":
        imports += "from math import prod\n"
    source = imports + _standalone((function,), function, args, result)
    return OfflineSolution(problem_type, source, summary, notes, metric)


def _solve_conditional_probability(rows, query, evidence):
    def matches(assignment, event):
        return all(
            type(assignment[index]) is type(value) and assignment[index] == value
            for index, value in event.items()
        )

    total = Fraction(0)
    query_weight = Fraction(0)
    evidence_weight = Fraction(0)
    joint_weight = Fraction(0)
    for assignment, raw_weight in rows:
        weight = Fraction(raw_weight)
        has_query = matches(assignment, query)
        has_evidence = matches(assignment, evidence)
        total += weight
        if has_query:
            query_weight += weight
        if has_evidence:
            evidence_weight += weight
        if has_query and has_evidence:
            joint_weight += weight
    return {
        "query_probability": str(query_weight / total),
        "evidence_probability": str(evidence_weight / total),
        "joint_probability": str(joint_weight / total),
        "conditional_probability": str(joint_weight / evidence_weight) if evidence_weight else None,
        "independent": joint_weight * total == query_weight * evidence_weight,
    }


def _value_key(value, field):
    from .offline_solver import OfflineProblemError

    if (type(value) is str and 0 < len(value) <= 100) or type(value) is bool:
        return type(value).__name__, value
    if type(value) is int and -1_000_000 <= value <= 1_000_000:
        return "int", value
    raise OfflineProblemError("invalid", f"{field} phải là chuỗi, số nguyên hoặc boolean.")


def _conditional_probability(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _name

    _fields(problem, ("type", "variables", "rows", "query"), ("evidence",))
    variables = problem["variables"]
    if not isinstance(variables, dict) or not 1 <= len(variables) <= 16:
        raise OfflineProblemError("invalid", "variables cần khai báo 1–16 biến và tập giá trị của từng biến.")
    domains = {}
    for name, values in variables.items():
        _name(name, "Tên biến")
        domain = [_value_key(value, name) for value in _array(values, name, 1, 32)]
        if len(set(domain)) != len(domain):
            raise OfflineProblemError("invalid", f"Biến {name} có giá trị trùng lặp.")
        domains[name] = set(domain)
    columns = {name: index for index, name in enumerate(domains)}

    def checked_value(name, value):
        key = _value_key(value, name)
        if name not in domains or key not in domains[name]:
            raise OfflineProblemError("invalid", f"Giá trị của {name} ngoài tập đã khai báo.")
        return value

    def event(value, name):
        if not isinstance(value, dict) or any(key not in columns for key in value):
            raise OfflineProblemError("invalid", f"{name} phải gán giá trị cho các biến đã khai báo.")
        return {columns[key]: checked_value(key, item) for key, item in value.items()}

    query = event(problem["query"], "query")
    evidence = event(problem.get("evidence", {}), "evidence")
    rows = []
    for row in _array(problem["rows"], "rows", 1, 400):
        values, weight = _array(row, "Dòng bảng", 2, 2)
        values = _array(values, "Danh sách giá trị", len(columns), len(columns))
        assignment = tuple(checked_value(name, value) for name, value in zip(columns, values))
        rows.append((assignment, _fraction_string(weight, "Trọng số", upper=1_000_000_000)))
    if not any(weight != "0" for _, weight in rows):
        raise OfflineProblemError("invalid", "Tổng trọng số của bảng phải dương.")

    args = (rows, query, evidence)
    result = _solve_conditional_probability(*args)
    conditional = result["conditional_probability"]
    summary = (
        f"Xác suất có điều kiện {conditional}."
        if conditional is not None else "Xác suất của bằng chứng bằng 0 nên xác suất có điều kiện không xác định."
    )
    return _solution(
        "conditional_probability", _solve_conditional_probability, args, result, summary,
        ("Mỗi dòng là một quan sát có trọng số. Các dòng theo đúng thứ tự biến khai báo và được cộng dồn trước khi chuẩn hóa.",),
        ("conditional_probability", conditional),
    )


def _solve_bayes(priors, likelihoods, query):
    weights = {
        name: Fraction(prior) * prod(Fraction(value) for value in likelihoods[name])
        for name, prior in priors.items()
    }
    evidence = sum(weights.values(), Fraction(0))
    if evidence == 0:
        return {"evidence_probability": "0", "posterior": None, "most_likely": [], "query_probability": None}
    best = max(weights.values())
    posterior = {name: str(weight / evidence) for name, weight in weights.items()}
    return {
        "evidence_probability": str(evidence),
        "posterior": posterior,
        "most_likely": sorted(name for name, weight in weights.items() if weight == best),
        "query_probability": posterior[query] if query is not None else None,
    }


def _bayes(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _name

    _fields(problem, ("type", "priors", "likelihoods"), ("query", "conditional_independence"))
    priors = problem["priors"]
    likelihoods = problem["likelihoods"]
    if not isinstance(priors, dict) or not 1 <= len(priors) <= 32:
        raise OfflineProblemError("invalid", "priors cần khai báo xác suất trước của 1–32 giả thuyết.")
    if not isinstance(likelihoods, dict) or set(likelihoods) != set(priors):
        raise OfflineProblemError("invalid", "likelihoods phải có đầy đủ các giả thuyết trong priors.")
    independence = problem.get("conditional_independence", False)
    if type(independence) is not bool:
        raise OfflineProblemError("invalid", "conditional_independence phải là boolean.")

    named_priors = {_name(name, "Tên giả thuyết"): _fraction_string(value, "Xác suất trước") for name, value in priors.items()}
    if sum(Fraction(value) for value in named_priors.values()) != 1:
        raise OfflineProblemError("invalid", "Tổng xác suất trước phải đúng bằng 1.")
    query = problem.get("query")
    if query is not None and (not isinstance(query, str) or query not in named_priors):
        raise OfflineProblemError("invalid", "query phải là giả thuyết đã khai báo.")

    vectors = {}
    for name, raw in likelihoods.items():
        values = _array(raw, "Các khả năng quan sát", 1, 8) if isinstance(raw, list) else [raw]
        vectors[name] = tuple(_fraction_string(value, "Xác suất quan sát") for value in values)
    dimensions = {len(vector) for vector in vectors.values()}
    if len(dimensions) != 1:
        raise OfflineProblemError("invalid", "Cần cùng số lượng quan sát cho mọi giả thuyết.")
    if next(iter(dimensions)) > 1 and not independence:
        raise OfflineProblemError("needs_input", "Dùng xác suất đồng thời hoặc xác nhận conditional_independence cho các quan sát.")

    args = (named_priors, vectors, query)
    result = _solve_bayes(*args)
    summary = f"Xác suất của bằng chứng {result['evidence_probability']}."
    if result["posterior"] is None:
        summary += " Xác suất hậu nghiệm không xác định."
    elif query is not None:
        summary += f" Xác suất hậu nghiệm {result['query_probability']}."
    metric = ("posterior_probability", result["query_probability"]) if query is not None else None
    return _solution(
        "bayes", _solve_bayes, args, result, summary,
        ("Chuẩn hóa xác suất trước nhân khả năng quan sát. Kết quả giữ các giả thuyết đồng hạng.",), metric,
    )


def _solve_fuzzy_set(operation, universe, left, right, parameter):
    left = {name: Fraction(left.get(name, "0")) for name in universe}
    right = {name: Fraction(right.get(name, "0")) for name in universe}
    if operation == "complement":
        return {name: str(1 - value) for name, value in left.items()}
    if operation == "intersection":
        return {name: str(min(value, right[name])) for name, value in left.items()}
    if operation == "union":
        return {name: str(max(value, right[name])) for name, value in left.items()}
    if operation == "subset":
        return all(value <= right[name] for name, value in left.items())
    if operation == "equal":
        return left == right
    if operation == "cardinality":
        return str(sum(left.values(), Fraction(0)))
    if operation == "height":
        return str(max(left.values(), default=Fraction(0)))
    if operation == "normal":
        return any(value == 1 for value in left.values())
    if operation == "empty":
        return not any(left.values())
    if operation == "support":
        return [name for name, value in left.items() if value > 0]
    if operation == "alpha_cut":
        threshold = Fraction(parameter)
        return [name for name, value in left.items() if value >= threshold]
    if operation == "scale":
        scalar = Fraction(parameter)
        return {name: str(value * scalar) for name, value in left.items()}
    if operation == "power":
        return {name: str(value ** parameter) for name, value in left.items()}
    raise ValueError("Unsupported fuzzy set operation")


def _fuzzy_set(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _integer, _name

    _fields(problem, ("type", "operation", "left"), ("right", "universe", "alpha", "scalar", "exponent"))
    operation = problem["operation"]
    binary_operations = ("intersection", "union", "subset", "equal")
    parameter_fields = {"alpha_cut": "alpha", "scale": "scalar", "power": "exponent"}
    unary_operations = ("complement", "cardinality", "height", "normal", "empty", "support")
    if not isinstance(operation, str) or operation not in (*binary_operations, *unary_operations, *parameter_fields):
        raise OfflineProblemError("unsupported", "Phép toán tập mờ chưa được hỗ trợ.")
    extra = ("right",) if operation in binary_operations else ()
    if operation in parameter_fields:
        extra = (parameter_fields[operation],)
    _fields(problem, ("type", "operation", "left", *extra), ("universe",))

    def memberships(value, name):
        if not isinstance(value, dict) or len(value) > 400:
            raise OfflineProblemError("invalid", f"{name} cần ánh xạ phần tử sang mức độ thuộc, tối đa 400 phần tử.")
        return {_name(element, "Phần tử"): _fraction_string(degree, "Mức độ thuộc") for element, degree in value.items()}

    left = memberships(problem["left"], "left")
    right = memberships(problem.get("right", {}), "right")
    known = set(left) | set(right)
    if "universe" in problem:
        universe = [_name(name, "Phần tử") for name in _array(problem["universe"], "universe", 0, 400)]
        if len(universe) != len(set(universe)) or known - set(universe):
            raise OfflineProblemError("invalid", "universe không được trùng và phải chứa mọi phần tử có mức độ thuộc đã khai báo.")
    else:
        universe = sorted(known)
    parameter = None
    if operation == "power":
        parameter = _integer(problem["exponent"], "Số mũ", 1, 16)
    elif operation in parameter_fields:
        parameter = _fraction_string(problem[parameter_fields[operation]], "Tham số")

    args = (operation, universe, left, right, parameter)
    result = _solve_fuzzy_set(*args)
    summary = f"Kết quả phép tập mờ {operation}."
    if type(result) in (str, bool):
        summary += f" Giá trị {result}."
    metric = (operation, result) if type(result) in (str, bool) else None
    return _solution(
        "fuzzy_set", _solve_fuzzy_set, args, result, summary,
        ("Mức độ thuộc được tính bằng phân số. Phần tử không liệt kê trong một tập có mức độ thuộc bằng 0.",), metric,
    )


UNCERTAINTY_SOLVERS = {
    "conditional_probability": _conditional_probability,
    "bayes": _bayes,
    "fuzzy_set": _fuzzy_set,
}
