"""Exact solvers for propositional logic and finite relation exercises."""

from collections import defaultdict


MAX_TRUTH_VARIABLES = 16
MAX_TRUTH_WORK = 2_000_000
MAX_RESOLUTION_PAIRS = 150_000
MAX_RESOLUTION_CLAUSES = 2000
MAX_HORN_STEPS = 100_000
MAX_JOIN_STEPS = 200_000
MAX_JOIN_ROWS = 5000
MAX_EXPRESSION_WORK = 500_000
MAX_EXPRESSION_BINDINGS = 1000


def _truth_value(expression, assignment):
    if type(expression) is bool:
        return expression
    if isinstance(expression, str):
        return assignment[expression]
    operator, *operands = expression
    if operator == "not":
        return not _truth_value(operands[0], assignment)
    if operator == "and":
        return all(_truth_value(child, assignment) for child in operands)
    if operator == "or":
        return any(_truth_value(child, assignment) for child in operands)

    left, right = (_truth_value(child, assignment) for child in operands)
    if operator == "implies":
        return not left or right
    if operator == "iff":
        return left == right
    return left != right


def _solve_entailment(premises, query, atoms):
    from itertools import product

    consistent = False
    for values in product((False, True), repeat=len(atoms)):
        assignment = dict(zip(atoms, values))
        if all(_truth_value(premise, assignment) for premise in premises):
            consistent = True
            if not _truth_value(query, assignment):
                return {"entailed": False, "premises_satisfiable": True, "counterexample": assignment}
    return {"entailed": True, "premises_satisfiable": consistent, "counterexample": None}


def _identifier(value):
    from .offline_solver import OfflineProblemError, _name

    value = _name(value, "Tên")
    if not value.isidentifier():
        raise OfflineProblemError("invalid", "Dùng tên hợp lệ gồm chữ, số và dấu gạch dưới cho mệnh đề, quan hệ và biến.")
    return value


def _entailment(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _standalone

    _fields(problem, ("type", "premises", "query"))
    atoms = set()
    size = 0

    def validate(expression, depth=0):
        nonlocal size
        size += 1
        if size > 1000 or depth > 24:
            raise OfflineProblemError("limit", "Công thức quá lớn hoặc có quá nhiều lớp lồng nhau.")
        if type(expression) is bool:
            return
        if isinstance(expression, str):
            atoms.add(_identifier(expression))
            return
        if not isinstance(expression, list) or not expression:
            raise OfflineProblemError("invalid", "Biểu thức phải là tên mệnh đề, Boolean hoặc danh sách có toán tử.")
        operator = expression[0]
        operand_count = len(expression) - 1
        if operator == "not":
            valid_arity = operand_count == 1
        elif operator in ("and", "or"):
            valid_arity = operand_count >= 2
        elif operator in ("implies", "iff", "xor"):
            valid_arity = operand_count == 2
        else:
            raise OfflineProblemError("unsupported", "Toán tử hỗ trợ gồm not, and, or, implies, iff, xor.")
        if not valid_arity:
            raise OfflineProblemError("invalid", f"Số toán hạng của {operator!r} không hợp lệ.")
        for child in expression[1:]:
            validate(child, depth + 1)

    premises = _array(problem["premises"], "premises", 0, 64)
    query = problem["query"]
    for expression in [*premises, query]:
        validate(expression)
    if len(atoms) > MAX_TRUTH_VARIABLES or (1 << len(atoms)) * size > MAX_TRUTH_WORK:
        raise OfflineProblemError("limit", "Bảng chân lý vượt giới hạn số dòng hoặc số phép tính.")
    args = (premises, query, sorted(atoms))
    result = _solve_entailment(*args)
    if not result["premises_satisfiable"]:
        summary = "Tập tiền đề mâu thuẫn, nên kéo theo mọi kết luận theo logic cổ điển."
    else:
        summary = "Tiền đề kéo theo kết luận." if result["entailed"] else "Tìm được phản ví dụ cho kết luận."
    return OfflineSolution(
        "entailment", _standalone((_truth_value, _solve_entailment), _solve_entailment, args, result),
        summary, ("Duyệt bảng chân lý. Phản ví dụ là một phép gán làm đúng toàn bộ tiền đề nhưng sai kết luận.",),
        ("entailed", result["entailed"]),
    )


def _resolve_clauses(clauses, query, pair_limit, clause_limit):
    """Resolve clause pairs and retain the ancestry of the empty clause."""
    def inverse(literal):
        return literal[1:] if literal.startswith("!") else "!" + literal

    records = []
    unique = set()

    def add(clause, source, parents=None, pivot=None):
        if clause in unique or any(inverse(literal) in clause for literal in clause):
            return
        if len(records) >= clause_limit:
            raise OverflowError("Resolution clause limit exceeded")
        unique.add(clause)
        records.append((clause, source, parents, pivot))

    def proof(end):
        involved = set()
        pending = [end]
        while pending:
            index = pending.pop()
            if index not in involved:
                involved.add(index)
                parents = records[index][2]
                if parents:
                    pending.extend(parents)
        output = []
        for index in sorted(involved):
            clause, source, parents, pivot = records[index]
            row = {"id": index, "clause": sorted(clause), "source": source}
            if parents:
                row.update(parents=list(parents), pivot=pivot)
            output.append(row)
        return {"entailed": True, "proof": output}

    for clause in clauses:
        add(frozenset(clause), "premise")
    for literal in query:
        add(frozenset((inverse(literal),)), "negated_query")
    for index, (clause, _, _, _) in enumerate(records):
        if not clause:
            return proof(index)

    right = 0
    pairs = 0
    while right < len(records):
        second = records[right][0]
        for left in range(right):
            pairs += 1
            if pairs > pair_limit:
                raise OverflowError("Resolution pair limit exceeded")
            first = records[left][0]
            for literal in sorted(first):
                opposite = inverse(literal)
                if opposite not in second:
                    continue
                resolvent = (first - {literal}) | (second - {opposite})
                add(resolvent, "resolution", (left, right), literal)
                if not resolvent:
                    return proof(len(records) - 1)
        right += 1
    return {"entailed": False, "proof": []}


def _resolution(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _standalone

    _fields(problem, ("type", "clauses", "query"))
    atoms = set()

    def read_clause(value, label):
        literals = []
        for literal in _array(value, label, 0, 32):
            if not isinstance(literal, str):
                raise OfflineProblemError("invalid", "Literal phải là tên mệnh đề hoặc tên có tiền tố !.")
            atom = _identifier(literal[1:] if literal.startswith("!") else literal)
            atoms.add(atom)
            literals.append(literal)
        return tuple(dict.fromkeys(literals))

    clauses = [read_clause(clause, "Mệnh đề tuyển") for clause in _array(problem["clauses"], "clauses", 0, 256)]
    query = read_clause(problem["query"], "query")
    if len(atoms) > 32:
        raise OfflineProblemError("limit", "Hợp giải hỗ trợ tối đa 32 mệnh đề nguyên tử.")
    args = (clauses, query, MAX_RESOLUTION_PAIRS, MAX_RESOLUTION_CLAUSES)
    result = _resolve_clauses(*args)
    summary = "Hợp giải suy ra mệnh đề rỗng." if result["entailed"] else "Đã xét hết các hợp giải và không suy ra mệnh đề rỗng."
    return OfflineSolution(
        "resolution", _standalone((_resolve_clauses,), _resolve_clauses, args, result), summary,
        ("Mỗi danh sách là một mệnh đề tuyển. Thêm phủ định của query rồi hợp giải để tìm mâu thuẫn.",),
        ("entailed", result["entailed"]),
    )


def _prove_backward(facts, rules, goal, step_limit):
    fact_set = set(facts)
    by_goal = defaultdict(list)
    for index, (premises, conclusion) in enumerate(rules):
        by_goal[conclusion].append((index, premises))
    proven = {}
    active = set()
    visited = {}
    steps = 0

    def prove(atom):
        nonlocal steps
        steps += 1
        if steps > step_limit:
            raise OverflowError("Backward proof limit exceeded")
        if atom in proven:
            return True
        visited[atom] = None
        if atom in fact_set:
            proven[atom] = {"goal": atom, "premises": [], "rule": None}
            return True
        if atom in active:
            return False
        active.add(atom)
        try:
            for index, premises in by_goal[atom]:
                if all(prove(premise) for premise in premises):
                    proven[atom] = {"goal": atom, "premises": list(premises), "rule": index}
                    return True
        finally:
            active.remove(atom)
        return False

    if not prove(goal):
        return {"entailed": False, "proof": [], "visited": list(visited)}

    needed = set()
    pending = [goal]
    while pending:
        atom = pending.pop()
        if atom not in needed:
            needed.add(atom)
            pending.extend(proven[atom]["premises"])
    return {
        "entailed": True,
        "proof": [step for atom, step in proven.items() if atom in needed],
        "visited": list(visited),
    }


def _backward_horn(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _standalone

    _fields(problem, ("type", "facts", "rules", "query"))
    facts = [_identifier(item) for item in _array(problem["facts"], "facts", 0, 256)]
    rules = []
    atoms = set(facts)
    for rule in _array(problem["rules"], "rules", 0, 400):
        _fields(rule, ("if", "then"))
        premises = tuple(dict.fromkeys(_identifier(item) for item in _array(rule["if"], "if", 0, 32)))
        conclusion = _identifier(rule["then"])
        atoms.update((*premises, conclusion))
        rules.append((premises, conclusion))
    query = _identifier(problem["query"])
    atoms.add(query)
    if len(atoms) > 180:
        raise OfflineProblemError("limit", "Suy diễn lùi hỗ trợ tối đa 180 mệnh đề khác nhau.")
    args = (facts, rules, query, MAX_HORN_STEPS)
    result = _prove_backward(*args)
    summary = "Tìm được chuỗi chứng minh mục tiêu." if result["entailed"] else "Không chứng minh được mục tiêu từ luật và dữ kiện đã cho."
    return OfflineSolution(
        "backward_horn", _standalone((_prove_backward,), _prove_backward, args, result), summary,
        ("Duyệt ngược từ mục tiêu, thử các luật có kết luận tương ứng. Chỉ số luật bắt đầu từ 0.",),
        ("entailed", result["entailed"]),
    )


def _join_relations(facts, goals, select, distinct, step_limit, row_limit):
    """Find all projected variable bindings in a finite conjunction."""
    bindings = [{}]
    steps = 0
    for name, args in sorted(goals, key=lambda goal: len(facts[goal[0]])):
        matches = []
        for old in bindings:
            for row in facts[name]:
                steps += 1
                if steps > step_limit:
                    raise OverflowError("Relation join work limit exceeded")
                match = dict(old)
                for (is_variable, term), value in zip(args, row):
                    if is_variable:
                        if match.setdefault(term, value) != value:
                            break
                    elif term != value:
                        break
                else:
                    if any(a in match and b in match and match[a] == match[b] for a, b in distinct):
                        continue
                    if len(matches) == row_limit:
                        raise OverflowError("Relation binding limit exceeded")
                    matches.append(match)
        bindings = matches
        if not bindings:
            break

    rows = {tuple(match[variable] for variable in select) for match in bindings}
    ordered = sorted(rows, key=lambda row: tuple((isinstance(value, str), value) for value in row))
    return {"matched": bool(rows), "rows": [list(row) for row in ordered]}


def _relation(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _name, _standalone

    _fields(problem, ("type", "facts", "where", "select"), ("distinct",))
    raw_facts = problem["facts"]
    if not isinstance(raw_facts, dict) or len(raw_facts) > 64:
        raise OfflineProblemError("invalid", "facts phải là đối tượng khai báo tối đa 64 quan hệ.")

    def value(constant):
        if isinstance(constant, str):
            return _name(constant, "Hằng chuỗi")
        return _integer(constant, "Hằng số", -1_000_000_000, 1_000_000_000)

    facts = {}
    arities = {}
    fact_count = 0
    for relation, entries in raw_facts.items():
        _identifier(relation)
        entries = _array(entries, "Các dữ kiện của quan hệ", 0, 1000)
        fact_count += len(entries)
        if fact_count > 4000:
            raise OfflineProblemError("limit", "Tổng số dữ kiện vượt giới hạn 4000.")
        parsed = []
        if entries:
            arity = len(_array(entries[0], "Dữ kiện quan hệ", 1, 8))
            arities[relation] = arity
            for row in entries:
                parsed.append(tuple(value(item) for item in _array(row, "Dữ kiện quan hệ", arity, arity)))
        facts[relation] = tuple(dict.fromkeys(parsed))

    goals = []
    variables = set()
    for goal in _array(problem["where"], "where", 1, 12):
        _fields(goal, ("relation", "args"))
        relation = _identifier(goal["relation"])
        if relation not in facts:
            raise OfflineProblemError("invalid", f"Chưa khai báo quan hệ {relation!r}.")
        raw_args = _array(goal["args"], "args", 1, 8)
        arity = arities.setdefault(relation, len(raw_args))
        if len(raw_args) != arity:
            raise OfflineProblemError("invalid", f"Quan hệ {relation!r} có {arity} đối số.")
        args = []
        for term in raw_args:
            if isinstance(term, dict):
                _fields(term, ("var",))
                variable = _identifier(term["var"])
                variables.add(variable)
                args.append((True, variable))
            else:
                args.append((False, value(term)))
        goals.append((relation, tuple(args)))

    def bound_variable(raw):
        name = _identifier(raw)
        if name not in variables:
            raise OfflineProblemError("invalid", f"Biến {name!r} chưa xuất hiện trong where.")
        return name

    select = tuple(bound_variable(item) for item in _array(problem["select"], "select", 0, 12))
    if len(set(select)) != len(select):
        raise OfflineProblemError("invalid", "select không được lặp tên biến.")
    distinct = []
    for pair in _array(problem.get("distinct", []), "distinct", 0, 32):
        distinct.append(tuple(bound_variable(item) for item in _array(pair, "Cặp biến khác nhau", 2, 2)))
    args = (facts, goals, select, distinct, MAX_JOIN_STEPS, MAX_JOIN_ROWS)
    result = _join_relations(*args)
    return OfflineSolution(
        "relation", _standalone((_join_relations,), _join_relations, args, result),
        f"Tìm được {len(result['rows'])} kết quả truy vấn quan hệ.",
        ("Các điều kiện where được kết hợp bằng phép và. Kết quả loại trùng và theo thứ tự biến trong select.",),
        ("row_count", len(result["rows"])),
    )


def _solve_primes(values, count):
    from math import isqrt

    limit = max(32, isqrt(max([0, *values])), 2 * count)
    while True:
        sieve = bytearray(b"\x01") * (limit + 1)
        sieve[:2] = b"\x00\x00"
        for divisor in range(2, isqrt(limit) + 1):
            if sieve[divisor]:
                start = divisor * divisor
                sieve[start::divisor] = b"\x00" * ((limit - start) // divisor + 1)
        primes = [value for value, prime in enumerate(sieve) if prime]
        if len(primes) >= count:
            break
        limit *= 2

    selected = []
    for value in values:
        if value < 2:
            continue
        if value <= limit:
            if sieve[value]:
                selected.append(value)
            continue
        maximum = isqrt(value)
        for divisor in primes:
            if divisor > maximum:
                selected.append(value)
                break
            if value % divisor == 0:
                break
        else:
            selected.append(value)
    return {"selected": selected, "first": primes[:count]}


def _primes(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type",), ("values", "count"))
    if "values" not in problem and "count" not in problem:
        raise OfflineProblemError("needs_input", "Nhập values, count hoặc cả hai.")
    values = [
        _integer(value, "Giá trị cần xét", -1_000_000_000, 1_000_000_000)
        for value in _array(problem.get("values", []), "values", 0, 1000)
    ]
    count = _integer(problem.get("count", 0), "count", 0, 5000)
    args = (values, count)
    result = _solve_primes(*args)
    return OfflineSolution(
        "primes", _standalone((_solve_primes,), _solve_primes, args, result),
        f"Lọc được {len(result['selected'])} giá trị nguyên tố và sinh {count} số nguyên tố đầu tiên.",
        ("selected giữ thứ tự và số lần xuất hiện của các phần tử trong values. first là dãy nguyên tố tăng dần.",),
    )


def _canonical_expression(expression, bindings):
    if type(expression) is int:
        return ("int", expression)
    if isinstance(expression, str):
        return ("symbol", expression)
    if isinstance(expression, dict):
        return bindings[expression["var"]]

    operator, *operands = expression
    children = []
    for operand in operands:
        child = _canonical_expression(operand, bindings)
        if child[0] == operator:
            children.extend(child[1])
        else:
            children.append(child)
    return operator, tuple(sorted(children))


def _solve_expression_match(pattern, target, domains, binding_limit):
    """Search the explicit domains modulo association and commutation."""
    from itertools import product

    names = sorted(domains)
    normalized_target = _canonical_expression(target, {})
    options = []
    for name in names:
        unique = {}
        for choice in domains[name]:
            unique.setdefault(_canonical_expression(choice, {}), choice)
        options.append(unique)

    matches = []
    for candidates in product(*options):
        bindings = dict(zip(names, candidates))
        if _canonical_expression(pattern, bindings) == normalized_target:
            if len(matches) >= binding_limit:
                raise OverflowError("Expression binding limit exceeded")
            matches.append({
                name: domain[candidate]
                for name, domain, candidate in zip(names, options, candidates)
            })
    return {"matched": bool(matches), "bindings": matches}


def _expression_match(problem):
    from math import prod

    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "pattern", "target"), ("domains",))
    occurrences = defaultdict(int)

    def validate(expression, allow_variables=False, depth=0):
        if depth > 20:
            raise OfflineProblemError("limit", "Biểu thức lồng quá 20 cấp.")
        if type(expression) is int:
            _integer(expression, "Hằng số", -1_000_000_000, 1_000_000_000)
            return 1
        if isinstance(expression, str):
            _identifier(expression)
            return 1
        if isinstance(expression, dict):
            if not allow_variables:
                raise OfflineProblemError("invalid", "Biến chỉ xuất hiện trong pattern.")
            _fields(expression, ("var",))
            occurrences[_identifier(expression["var"])] += 1
            return 1
        if not isinstance(expression, list) or len(expression) < 3:
            raise OfflineProblemError("invalid", "Biểu thức gồm một toán tử và ít nhất hai toán hạng.")
        operator, *operands = expression
        if operator not in ("+", "*"):
            raise OfflineProblemError("unsupported", "Đối sánh kết hợp và giao hoán hỗ trợ toán tử + và *.")
        return 1 + sum(validate(child, allow_variables, depth + 1) for child in operands)

    pattern = problem["pattern"]
    target = problem["target"]
    pattern_size = validate(pattern, allow_variables=True)
    target_size = validate(target)

    domains = problem.get("domains", {})
    if not isinstance(domains, dict):
        raise OfflineProblemError("invalid", "domains phải là đối tượng chứa một miền hữu hạn cho mỗi biến.")
    missing = occurrences.keys() - domains.keys()
    if missing:
        raise OfflineProblemError("needs_input", "Thiếu miền cho biến " + ", ".join(sorted(missing)) + ".")
    if domains.keys() - occurrences.keys():
        raise OfflineProblemError("invalid", "domains có biến chưa dùng trong pattern.")
    if len(domains) > 8:
        raise OfflineProblemError("limit", "Hỗ trợ tối đa 8 biến đối sánh.")

    input_work = target_size
    expanded_size = pattern_size
    for name, domain in domains.items():
        sizes = [validate(candidate) for candidate in _array(domain, "Miền biến", 1, 32)]
        input_work += sum(sizes)
        expanded_size += occurrences[name] * (max(sizes) - 1)
    candidates = prod(len(domain) for domain in domains.values())
    if input_work + expanded_size * candidates > MAX_EXPRESSION_WORK:
        raise OfflineProblemError("limit", "Biểu thức và miền biến vượt giới hạn đối sánh.")

    args = (pattern, target, domains, MAX_EXPRESSION_BINDINGS)
    result = _solve_expression_match(*args)
    summary = f"Tìm được {len(result['bindings'])} phép gán khớp." if result["matched"] else "Các biểu thức không khớp với miền đã cho."
    return OfflineSolution(
        "expression_match",
        _standalone((_canonical_expression, _solve_expression_match), _solve_expression_match, args, result),
        summary,
        ("Chỉ dùng tính kết hợp, giao hoán của + và *. Mỗi phần tử trong bindings là một phép gán.",),
        ("matched", result["matched"]),
    )


COURSE_LOGIC_SOLVERS = {
    "entailment": _entailment,
    "resolution": _resolution,
    "backward_horn": _backward_horn,
    "relation": _relation,
    "primes": _primes,
    "expression_match": _expression_match,
}
