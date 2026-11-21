"""Exact bounded solvers for four explicit optimization models."""


def _solve_knapsack(items, capacity, required, count, tie_break, step_limit):
    required_names = set(required)
    base_weight = base_value = base_mask = 0
    for index, (name, weight, value) in enumerate(items):
        if name in required_names:
            base_weight += weight
            base_value += value
            base_mask |= 1 << index
    if base_weight > capacity or (count is not None and len(required) > count):
        return None

    remaining_count = None if count is None else count - len(required)
    states = {(base_weight, 0): (base_value, base_mask)}
    steps = 0
    for index, (name, weight, value) in enumerate(items):
        if name in required_names:
            continue
        steps += len(states)
        if steps > step_limit:
            raise OverflowError("Knapsack step budget exceeded.")
        for (used_weight, used_count), (total_value, mask) in tuple(states.items()):
            new_weight = used_weight + weight
            new_count = used_count + 1 if remaining_count is not None else 0
            if new_weight > capacity or (remaining_count is not None and new_count > remaining_count):
                continue
            key = (new_weight, new_count)
            candidate = total_value + value, mask | (1 << index)
            previous = states.get(key)
            candidate_score = (candidate[0], -candidate[1].bit_count(), -candidate[1])
            if previous is None or candidate_score > (previous[0], -previous[1].bit_count(), -previous[1]):
                states[key] = candidate

    best_score = None
    best_result = None
    for (used_weight, used_count), (value, mask) in states.items():
        if remaining_count is not None and used_count != remaining_count:
            continue
        item_count = mask.bit_count()
        costs = (used_weight, item_count) if tie_break == "min_weight" else (item_count, used_weight)
        score = (value, -costs[0], -costs[1], -mask)
        if best_score is None or score > best_score:
            best_score = score
            best_result = value, used_weight, mask
    if best_result is None:
        return None
    value, weight, mask = best_result
    selected = [name for index, (name, _, _) in enumerate(items) if mask & (1 << index)]
    return value, weight, selected


def _solve_tsp(nodes, edges, start, end, return_to_start):
    if len(nodes) == 1:
        return 0, [start, start] if return_to_start else [start]
    positions = {name: index for index, name in enumerate(nodes)}
    start_index = positions[start]
    end_index = positions[end] if end is not None else None
    adjacency = [[] for _ in nodes]
    edge_cost = {}
    for source, target, cost in edges:
        source, target = positions[source], positions[target]
        adjacency[source].append((target, cost))
        edge_cost[source, target] = cost

    full_mask = (1 << len(nodes)) - 1
    states = {(1 << start_index, start_index): (0, (start_index,))}
    for mask in range(1 << len(nodes)):
        for last in range(len(nodes)):
            current = states.get((mask, last))
            if current is None:
                continue
            cost, path = current
            for target, weight in adjacency[last]:
                bit = 1 << target
                if mask & bit:
                    continue
                next_mask = mask | bit
                if target == end_index and next_mask != full_mask:
                    continue
                key = next_mask, target
                candidate = cost + weight, (*path, target)
                if key not in states or candidate < states[key]:
                    states[key] = candidate

    best = None
    endpoints = range(len(nodes)) if end_index is None else (end_index,)
    for last in endpoints:
        candidate = states.get((full_mask, last))
        if candidate is None:
            continue
        if return_to_start:
            closing_cost = edge_cost.get((last, start_index))
            if closing_cost is None:
                continue
            candidate = candidate[0] + closing_cost, (*candidate[1], start_index)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return None
    return best[0], [nodes[index] for index in best[1]]


def _solve_interval_scheduling(intervals, required):
    from bisect import bisect_right

    required_names = set(required)
    fixed = sorted(
        (item for item in intervals if item[0] in required_names),
        key=lambda item: (item[1], item[2], item[0]),
    )
    if any(left[2] > right[1] for left, right in zip(fixed, fixed[1:])):
        return None
    choices = sorted(
        (
            item for item in intervals
            if item[0] not in required_names
            and all(item[2] <= mandatory[1] or item[1] >= mandatory[2] for mandatory in fixed)
        ),
        key=lambda item: (item[2], item[1], item[0]),
    )
    finishes = [item[2] for item in choices]
    best = [0] * (len(choices) + 1)
    picked = {}
    for index, item in enumerate(choices, 1):
        previous = bisect_right(finishes, item[1], hi=index - 1)
        candidate = best[previous] + item[3]
        best[index] = best[index - 1]
        if candidate > best[index]:
            best[index] = candidate
            picked[index] = previous

    selected = fixed[:]
    index = len(choices)
    while index:
        if index in picked:
            selected.append(choices[index - 1])
            index = picked[index]
        else:
            index -= 1
    selected.sort(key=lambda item: (item[1], item[2], item[0]))
    return best[-1] + sum(item[3] for item in fixed), [item[0] for item in selected]


def _solve_precedence_scheduling(tasks, dependencies):
    from collections import deque

    durations = dict(tasks)
    outgoing = {name: [] for name in durations}
    indegree = dict.fromkeys(durations, 0)
    for before, after in dependencies:
        outgoing[before].append(after)
        indegree[after] += 1
    ready = deque(name for name, degree in indegree.items() if degree == 0)
    earliest = dict.fromkeys(durations, 0)
    predecessor = {}
    completed = []
    while ready:
        name = ready.popleft()
        finish = earliest[name] + durations[name]
        completed.append((name, earliest[name], finish))
        for after in outgoing[name]:
            if finish > earliest[after]:
                earliest[after] = finish
                predecessor[after] = name
            indegree[after] -= 1
            if indegree[after] == 0:
                ready.append(after)
    if len(completed) != len(tasks):
        return None
    last, _, makespan = max(completed, key=lambda task: task[2])
    critical_path = []
    while last is not None:
        critical_path.append(last)
        last = predecessor.get(last)
    return makespan, completed, critical_path[::-1]


def _bounded_list(value, label, minimum, maximum):
    from .offline_solver import OfflineProblemError, _array

    if isinstance(value, list) and len(value) > maximum:
        raise OfflineProblemError("limit", f"{label} vượt giới hạn {maximum} phần tử.")
    return _array(value, label, minimum, maximum)


def _unique_names(values, label):
    from .offline_solver import OfflineProblemError, _name

    names = [_name(value, label) for value in values]
    if len(set(names)) != len(names):
        raise OfflineProblemError("invalid", f"{label} có tên bị lặp.")
    return names


def _required_names(value, valid_names):
    from .offline_solver import OfflineProblemError, _array

    names = _unique_names(_array(value, "required", 0, len(valid_names)), "required")
    if not set(names).issubset(valid_names):
        raise OfflineProblemError("invalid", "required chứa tên chưa được khai báo.")
    return names


def _solution(problem_type, solver, args, result, summary, diagnostic, metric):
    from .offline_solver import OfflineSolution, _standalone

    code = _standalone((solver,), solver, args, result)
    return OfflineSolution(problem_type, code, summary, (diagnostic,), (metric, None if result is None else result[0]))


def _knapsack(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _integer

    _fields(problem, ("type", "capacity", "items"), ("algorithm", "required", "count", "tie_break"))
    if problem.get("algorithm", "dp") != "dp":
        raise OfflineProblemError("unsupported", "Knapsack 0/1 hỗ trợ thuật toán dp.")
    tie_break = problem.get("tie_break", "min_weight")
    if tie_break not in ("min_weight", "fewest_items"):
        raise OfflineProblemError("unsupported", "tie_break phải là min_weight hoặc fewest_items.")
    capacity = _integer(problem["capacity"], "capacity", 0, 1_000_000)
    rows = [
        _array(item, "Món đồ", 3, 3)
        for item in _bounded_list(problem["items"], "items", 1, 100)
    ]
    names = _unique_names([row[0] for row in rows], "Tên món đồ")
    items = [
        (name, _integer(row[1], "Trọng lượng", 0, 1_000_000), _integer(row[2], "Giá trị", -1_000_000, 1_000_000))
        for name, row in zip(names, rows)
    ]
    required = _required_names(problem.get("required", []), names)
    count = _integer(problem["count"], "count", 0, len(items)) if "count" in problem else None
    args = (items, capacity, required, count, tie_break, 1_000_000)
    result = _solve_knapsack(*args)
    summary = "Không có tập món đồ thỏa ràng buộc." if result is None else f"Giá trị tối đa: {result[0]}."
    return _solution(
        "knapsack", _solve_knapsack, args, result, summary,
        "Mỗi món được chọn tối đa một lần. Kết quả là (giá trị, trọng lượng, danh sách món).", "maximum_value",
    )


def _tsp(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _integer, _name

    _fields(problem, ("type", "nodes", "start", "edges"), ("directed", "return_to_start", "end", "algorithm"))
    if problem.get("algorithm", "held_karp") != "held_karp":
        raise OfflineProblemError("unsupported", "TSP hỗ trợ thuật toán held_karp.")
    nodes = _unique_names(_bounded_list(problem["nodes"], "nodes", 1, 13), "Tên nút")
    directed = problem.get("directed", False)
    return_to_start = problem.get("return_to_start", True)
    if type(directed) is not bool or type(return_to_start) is not bool:
        raise OfflineProblemError("invalid", "directed và return_to_start phải là true hoặc false.")
    if "end" in problem and return_to_start:
        raise OfflineProblemError("unsupported", "Chỉ dùng end khi return_to_start là false.")
    start = _name(problem["start"], "start")
    end = _name(problem["end"], "end") if "end" in problem else None
    if start not in nodes or (end is not None and end not in nodes):
        raise OfflineProblemError("invalid", "start và end phải là các nút đã khai báo.")

    edges = {}
    for row in _bounded_list(problem["edges"], "edges", 0, 156):
        source, target, cost = _array(row, "Cạnh", 3, 3)
        source, target = _name(source, "Nút đi"), _name(target, "Nút đến")
        if source not in nodes or target not in nodes or source == target or (source, target) in edges:
            raise OfflineProblemError("invalid", "Cạnh phải nối hai nút khác nhau đã khai báo và không được lặp.")
        weight = _integer(cost, "Chi phí", -1_000_000, 1_000_000)
        edges[source, target] = weight
        if not directed:
            edges[target, source] = weight
    args = (nodes, [(a, b, cost) for (a, b), cost in edges.items()], start, end, return_to_start)
    result = _solve_tsp(*args)
    summary = "Không có hành trình qua đủ các nút." if result is None else f"Chi phí tối thiểu: {result[0]}."
    return _solution(
        "tsp", _solve_tsp, args, result, summary,
        "Held–Karp xét cạnh đã khai báo, mỗi nút được ghé đúng một lần trước khi quay lại nếu yêu cầu.", "minimum_cost",
    )


def _interval_scheduling(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _integer

    _fields(problem, ("type", "intervals"), ("required", "algorithm"))
    if problem.get("algorithm", "dp") != "dp":
        raise OfflineProblemError("unsupported", "Lập lịch đoạn thời gian hỗ trợ thuật toán dp.")
    rows = [
        _array(row, "Khoảng thời gian", 4, 4)
        for row in _bounded_list(problem["intervals"], "intervals", 1, 1_000)
    ]
    names = _unique_names([row[0] for row in rows], "Tên công việc")
    intervals = []
    for name, row in zip(names, rows):
        start = _integer(row[1], "Bắt đầu", -1_000_000, 1_000_000)
        end = _integer(row[2], "Kết thúc", -1_000_000, 1_000_000)
        if start >= end:
            raise OfflineProblemError("invalid", "Bắt đầu phải trước kết thúc.")
        intervals.append((name, start, end, _integer(row[3], "Giá trị", -1_000_000, 1_000_000)))
    required = _required_names(problem.get("required", []), names)
    args = intervals, required
    result = _solve_interval_scheduling(*args)
    summary = "Các công việc bắt buộc bị trùng lịch." if result is None else f"Tổng giá trị tối đa: {result[0]}."
    return _solution(
        "interval_scheduling", _solve_interval_scheduling, args, result, summary,
        "Lịch một tài nguyên, thời điểm kết thúc có thể trùng thời điểm bắt đầu việc tiếp theo.", "maximum_value",
    )


def _precedence_scheduling(problem):
    from .offline_solver import OfflineProblemError, _array, _fields, _integer, _name

    _fields(problem, ("type", "tasks", "dependencies"), ("algorithm",))
    if problem.get("algorithm", "critical_path") != "critical_path":
        raise OfflineProblemError("unsupported", "Lập lịch thứ tự hỗ trợ thuật toán critical_path.")
    rows = [
        _array(row, "Công việc", 2, 2)
        for row in _bounded_list(problem["tasks"], "tasks", 1, 500)
    ]
    names = _unique_names([row[0] for row in rows], "Tên công việc")
    tasks = [(name, _integer(row[1], "Thời lượng", 1, 1_000_000)) for name, row in zip(names, rows)]
    known_names = set(names)
    dependencies = []
    checked = set()
    for row in _bounded_list(problem["dependencies"], "dependencies", 0, 2_000):
        before, after = _array(row, "Quan hệ thứ tự", 2, 2)
        before, after = _name(before, "Công việc trước"), _name(after, "Công việc sau")
        if before not in known_names or after not in known_names:
            raise OfflineProblemError("invalid", "Quan hệ thứ tự chứa công việc chưa được khai báo.")
        if (before, after) in checked:
            raise OfflineProblemError("invalid", "Quan hệ thứ tự bị lặp.")
        checked.add((before, after))
        dependencies.append((before, after))
    args = tasks, dependencies
    result = _solve_precedence_scheduling(*args)
    summary = "Không thể lập lịch vì có chu trình phụ thuộc." if result is None else f"Thời gian hoàn tất tối thiểu: {result[0]}."
    return _solution(
        "precedence_scheduling", _solve_precedence_scheduling, args, result, summary,
        "Công việc độc lập có thể chạy song song. Kết quả gồm thời gian tối thiểu, lịch sớm nhất và đường găng.", "minimum_time",
    )


OPTIMIZATION_SOLVERS = {
    "knapsack": _knapsack,
    "tsp": _tsp,
    "interval_scheduling": _interval_scheduling,
    "precedence_scheduling": _precedence_scheduling,
}
