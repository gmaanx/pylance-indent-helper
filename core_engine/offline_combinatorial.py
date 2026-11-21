"""Exact offline assignment, directed maximum flow, and spanning forest solvers."""

from .offline_optimization import _bounded_list, _solution, _unique_names


def _solve_assignment(left, right, edges, objective):
    """Map all left vertices to distinct right vertices along declared edges."""
    if len(left) > len(right):
        return None

    right_index = {name: index for index, name in enumerate(right)}
    choices = {name: [] for name in left}
    for source, target, cost in edges:
        choices[source].append((right_index[target], cost))

    factor = 1 if objective == "min" else -1
    states = {0: (0, ())}
    for name in left:
        next_states = {}
        for occupied, (score, path) in states.items():
            for index, cost in choices[name]:
                bit = 1 << index
                if occupied & bit:
                    continue
                next_mask = occupied | bit
                candidate = score + factor * cost, (*path, index)
                current = next_states.get(next_mask)
                if current is None or candidate < current:
                    next_states[next_mask] = candidate
        if not next_states:
            return None
        states = next_states

    score, path = min(states.values())
    return factor * score, [(source, right[index]) for source, index in zip(left, path)]


def _solve_max_flow(nodes, edges, source, sink, scan_limit):
    """Return a flow and a cut that witnesses its optimality."""
    from collections import deque

    residual = {name: [] for name in nodes}
    forward_arcs = []
    for start, end, capacity in edges:
        forward_index = len(residual[start])
        backward_index = len(residual[end])
        # Each original arc gets its own reverse arc, even with parallel input arcs.
        residual[start].append([end, capacity, backward_index])
        residual[end].append([start, 0, forward_index])
        forward_arcs.append(forward_index)

    value = 0
    scanned = 0
    while True:
        parent = {source: None}
        pending = deque([source])
        while pending and sink not in parent:
            start = pending.popleft()
            scanned += len(residual[start])
            if scanned > scan_limit:
                raise OverflowError("Maximum flow scan budget exceeded.")
            for index, (end, capacity, _) in enumerate(residual[start]):
                if capacity > 0 and end not in parent:
                    parent[end] = start, index
                    pending.append(end)
        if sink not in parent:
            break

        path = []
        end = sink
        while end != source:
            start, index = parent[end]
            path.append((start, index))
            end = start
        increment = min(residual[start][index][1] for start, index in path)
        for start, index in path:
            end, _, reverse_index = residual[start][index]
            residual[start][index][1] -= increment
            residual[end][reverse_index][1] += increment
        value += increment

    flows = [
        (start, end, capacity - residual[start][index][1], capacity)
        for index, (start, end, capacity) in zip(forward_arcs, edges)
    ]
    source_side = [name for name in nodes if name in parent]
    sink_side = [name for name in nodes if name not in parent]
    cut_capacity = sum(capacity for start, end, capacity in edges if start in parent and end not in parent)
    return value, flows, (source_side, sink_side), cut_capacity


def _solve_minimum_spanning_forest(nodes, edges):
    """Select a minimum-cost tree in each connected component."""
    parent = {name: name for name in nodes}
    size = dict.fromkeys(nodes, 1)

    def find(name):
        while name != parent[name]:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    selected = []
    total = 0
    for start, end, cost in sorted(edges, key=lambda edge: edge[2]):
        a, b = find(start), find(end)
        if a == b:
            continue
        if size[a] < size[b]:
            a, b = b, a
        parent[b] = a
        size[a] += size[b]
        selected.append((start, end, cost))
        total += cost
    components = {}
    for name in nodes:
        components.setdefault(find(name), []).append(name)
    return total, selected, list(components.values())


def _read_edges(value, sources, targets, max_edges, min_weight):
    from .offline_solver import OfflineProblemError, _array, _integer, _name

    edges = []
    for row in _bounded_list(value, "edges", 0, max_edges):
        start, end, weight = _array(row, "Cạnh", 3, 3)
        start, end = _name(start, "Đầu cạnh"), _name(end, "Cuối cạnh")
        if start not in sources or end not in targets:
            raise OfflineProblemError("invalid", "Cạnh chứa đỉnh chưa được khai báo.")
        edges.append((start, end, _integer(weight, "Trọng số cạnh", min_weight, 1_000_000)))
    return edges


def _assignment(problem):
    from .offline_solver import OfflineProblemError, _fields

    _fields(problem, ("type", "left", "right", "edges"), ("objective", "algorithm"))
    if problem.get("algorithm", "dp") != "dp":
        raise OfflineProblemError("unsupported", "Bài toán phân công hỗ trợ thuật toán dp.")
    objective = problem.get("objective", "min")
    if objective not in ("min", "max"):
        raise OfflineProblemError("unsupported", "objective phải là min hoặc max.")
    left = _unique_names(_bounded_list(problem["left"], "left", 1, 15), "Đỉnh phía trái")
    right = _unique_names(_bounded_list(problem["right"], "right", 1, 15), "Đỉnh phía phải")
    edges = _read_edges(problem["edges"], set(left), set(right), 225, -1_000_000)
    if len({(source, target) for source, target, _ in edges}) != len(edges):
        raise OfflineProblemError("invalid", "Một cặp phân công chỉ được khai báo một lần.")
    args = left, right, edges, objective
    result = _solve_assignment(*args)
    summary = "Không tồn tại phân công đủ cho phía trái." if result is None else f"Tổng chi phí tối ưu: {result[0]}."
    return _solution(
        "assignment", _solve_assignment, args, result, summary,
        "Mỗi đỉnh trái nhận đúng một đỉnh phải khác nhau trên cạnh đã khai báo. Kết quả gồm tổng chi phí và các cặp.",
        "assignment_cost",
    )


def _max_flow(problem):
    from .offline_solver import OfflineProblemError, _fields, _name

    _fields(problem, ("type", "nodes", "edges", "source", "sink"), ("algorithm",))
    if problem.get("algorithm", "edmonds_karp") != "edmonds_karp":
        raise OfflineProblemError("unsupported", "Luồng cực đại hỗ trợ thuật toán edmonds_karp.")
    nodes = _unique_names(_bounded_list(problem["nodes"], "nodes", 2, 120), "Đỉnh")
    node_set = set(nodes)
    source, sink = _name(problem["source"], "source"), _name(problem["sink"], "sink")
    if source == sink or source not in node_set or sink not in node_set:
        raise OfflineProblemError("invalid", "source và sink phải khác nhau và có trong nodes.")
    edges = _read_edges(problem["edges"], node_set, node_set, 500, 0)
    if any(start == end for start, end, _ in edges):
        raise OfflineProblemError("invalid", "Luồng cực đại yêu cầu mỗi cạnh nối hai đỉnh khác nhau.")
    args = nodes, edges, source, sink, 3_000_000
    result = _solve_max_flow(*args)
    return _solution(
        "max_flow", _solve_max_flow, args, result, f"Luồng cực đại: {result[0]}. Dung lượng lát cắt: {result[3]}.",
        "Kết quả gồm giá trị luồng, (đầu, cuối, luồng, dung lượng) từng cạnh, hai phía lát cắt và dung lượng lát cắt.",
        "max_flow",
    )


def _minimum_spanning_forest(problem):
    from .offline_solver import OfflineProblemError, _fields

    _fields(problem, ("type", "nodes", "edges"), ("algorithm",))
    if problem.get("algorithm", "kruskal") != "kruskal":
        raise OfflineProblemError("unsupported", "Rừng khung nhỏ nhất hỗ trợ thuật toán kruskal.")
    nodes = _unique_names(_bounded_list(problem["nodes"], "nodes", 1, 2_000), "Đỉnh")
    node_set = set(nodes)
    edges = _read_edges(problem["edges"], node_set, node_set, 5_000, -1_000_000)
    if any(start == end for start, end, _ in edges):
        raise OfflineProblemError("invalid", "Rừng khung yêu cầu mỗi cạnh nối hai đỉnh khác nhau.")
    args = nodes, edges
    result = _solve_minimum_spanning_forest(*args)
    return _solution(
        "minimum_spanning_forest", _solve_minimum_spanning_forest, args, result,
        f"Tổng trọng số nhỏ nhất: {result[0]}. Số thành phần: {len(result[2])}.",
        "Kruskal chọn cạnh vô hướng có trọng số nhỏ nhất nối hai cây khác nhau. Kết quả gồm tổng trọng số, cạnh và thành phần.",
        "spanning_forest_weight",
    )


COMBINATORIAL_SOLVERS = {
    "assignment": _assignment,
    "max_flow": _max_flow,
    "minimum_spanning_forest": _minimum_spanning_forest,
}
