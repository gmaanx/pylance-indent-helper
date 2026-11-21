"""Binary CSP traces and configurable N-queens exercises."""

__all__ = ["COURSE_CSP_SOLVERS"]


def _arc_consistency(domains, constraints, step_limit):
    from collections import defaultdict, deque

    tables = {}
    for left, right, pairs in constraints:
        forward = set(pairs)
        backward = {(b, a) for a, b in forward}
        for arc, allowed in (((left, right), forward), ((right, left), backward)):
            if arc in tables:
                tables[arc].intersection_update(allowed)
            else:
                tables[arc] = allowed
    neighbors = defaultdict(list)
    for left, right in tables:
        neighbors[left].append(right)

    reduced = {name: list(values) for name, values in domains.items()}
    pending = deque(tables)
    queued = set(tables)
    trace = []
    steps = 0
    while pending:
        left, right = pending.popleft()
        queued.remove((left, right))
        kept, removed = [], []
        for a in reduced[left]:
            for b in reduced[right]:
                steps += 1
                if steps > step_limit:
                    raise OverflowError("AC-3 work limit exceeded")
                if (a, b) in tables[left, right]:
                    kept.append(a)
                    break
            else:
                removed.append(a)
        if not removed:
            continue
        reduced[left] = kept
        trace.append({"arc": (left, right), "removed": removed})
        if not kept:
            return {"status": "inconsistent", "domains": reduced, "trace": trace}
        for other in neighbors[left]:
            if other != right and (other, left) not in queued:
                pending.append((other, left))
                queued.add((other, left))
    return {"status": "arc_consistent", "domains": reduced, "trace": trace}


def _ac3(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _name, _standalone

    _fields(problem, ("type", "domains", "constraints"))
    raw = problem["domains"]
    if not isinstance(raw, dict) or not 1 <= len(raw) <= 80:
        raise OfflineProblemError("invalid", "domains cần từ 1 đến 80 biến.")

    def concrete(value):
        if (type(value) is int and abs(value) <= 10**9) or (isinstance(value, str) and 1 <= len(value) <= 80):
            return value
        raise OfflineProblemError("invalid", "Giá trị miền cần là số nguyên hoặc chuỗi.")

    domains = {
        _name(name, "Biến"): tuple(dict.fromkeys(concrete(v) for v in _array(values, "Miền", 1, 50)))
        for name, values in raw.items()
    }
    constraints = []
    for constraint in _array(problem["constraints"], "constraints", 0, 250):
        _fields(constraint, ("vars",), ("op", "allowed"))
        left, right = (_name(name, "Biến trong ràng buộc") for name in _array(constraint["vars"], "vars", 2, 2))
        if left == right or left not in domains or right not in domains:
            raise OfflineProblemError("invalid", "Ràng buộc cần hai biến khác nhau đã khai báo.")
        if ("op" in constraint) == ("allowed" in constraint):
            raise OfflineProblemError("invalid", "Mỗi ràng buộc cần đúng một trong op hoặc allowed.")
        if "allowed" in constraint:
            pairs = [
                tuple(concrete(value) for value in _array(pair, "Cặp", 2, 2))
                for pair in _array(constraint["allowed"], "allowed", 0, 2500)
            ]
            if any(a not in domains[left] or b not in domains[right] for a, b in pairs):
                raise OfflineProblemError("invalid", "Cặp allowed chứa giá trị ngoài miền.")
        else:
            op = constraint["op"]
            if op not in ("eq", "ne", "lt", "le", "gt", "ge"):
                raise OfflineProblemError("unsupported", "op hỗ trợ eq, ne, lt, le, gt, ge.")
            if op not in ("eq", "ne") and any(type(v) is not int for v in (*domains[left], *domains[right])):
                raise OfflineProblemError("invalid", "So sánh thứ tự cần miền số nguyên.")
            from operator import eq, ge, gt, le, lt, ne
            compare = {"eq": eq, "ne": ne, "lt": lt, "le": le, "gt": gt, "ge": ge}[op]
            pairs = [(a, b) for a in domains[left] for b in domains[right] if compare(a, b)]
        constraints.append((left, right, pairs))
    args = (domains, constraints, 2_000_000)
    result = _arc_consistency(*args)
    consistent = result["status"] == "arc_consistent"
    summary = (
        "Đã đạt phù hợp cung cục bộ. Trạng thái này chưa kết luận CSP có nghiệm."
        if consistent else "AC-3 làm rỗng một miền. CSP vô nghiệm."
    )
    return OfflineSolution(
        "ac3", _standalone((_arc_consistency,), _arc_consistency, args, result),
        summary, ("Vết chạy ghi từng cung bị sửa và các giá trị bị loại.",),
        ("arc_consistent", consistent),
    )


def _solve_nqueens(size, fixed, blocked, count_all, limit):
    board = [-1] * size
    first, count, visited = None, 0, 0
    columns = [
        (fixed[col],) if col in fixed else tuple(row for row in range(size) if (col, row) not in blocked)
        for col in range(size)
    ]

    def visit(col, rows, rising, falling):
        nonlocal first, count, visited
        if col == size:
            count += 1
            if first is None:
                first = tuple(board)
            return not count_all
        for row in columns[col]:
            visited += 1
            if visited > limit:
                raise OverflowError("N-queens search budget exhausted")
            a, b, c = 1 << row, 1 << (row + col), 1 << (row - col + size - 1)
            if rows & a or rising & b or falling & c:
                continue
            board[col] = row
            if visit(col + 1, rows | a, rising | b, falling | c):
                return True
        return False

    visit(0, 0, 0, 0)
    return {"solution": first, "count": count if count_all else None}


def _nqueens(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "n"), ("fixed", "blocked", "mode"))
    n = _integer(problem["n"], "n", 1, 32)
    mode = problem.get("mode", "first")
    if mode not in ("first", "count"):
        raise OfflineProblemError("unsupported", "mode nhận first hoặc count.")
    if mode == "count" and n > 12:
        raise OfflineProblemError("limit", "Chế độ đếm toàn bộ hỗ trợ n tối đa 12.")

    def positions(field):
        checked = []
        for pair in _array(problem.get(field, []), field, 0, n * n):
            col, row = _array(pair, field, 2, 2)
            checked.append((_integer(col, "Cột", 0, n - 1), _integer(row, "Hàng", 0, n - 1)))
        if len(checked) != len(set(checked)):
            raise OfflineProblemError("invalid", f"{field} chứa ô trùng.")
        return checked

    fixed_positions, blocked = positions("fixed"), positions("blocked")
    fixed = dict(fixed_positions)
    if len(fixed) != len(fixed_positions) or set(fixed_positions) & set(blocked):
        raise OfflineProblemError("invalid", "Mỗi cột chỉ có một quân đặt trước và quân đó không nằm trên ô cấm.")
    args = (n, fixed, blocked, mode == "count", 6_000_000)
    result = _solve_nqueens(*args)
    summary = "Không có cấu hình hợp lệ." if result["solution"] is None else "Tìm được cấu hình không có hai hậu tấn công nhau."
    metric = ("satisfiable", result["solution"] is not None)
    if mode == "count":
        summary = f"Số cấu hình hợp lệ: {result['count']}."
        metric = ("solution_count", result["count"])
    return OfflineSolution(
        "nqueens", _standalone((_solve_nqueens,), _solve_nqueens, args, result),
        summary, ("Tọa độ [cột,hàng] từ 0. Các cấu hình đối xứng được đếm riêng.",), metric,
    )


COURSE_CSP_SOLVERS = {"ac3": _ac3, "nqueens": _nqueens}
