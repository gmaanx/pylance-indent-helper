"""Search traces for explicit state graphs and 8-puzzle heuristic comparisons."""

from .sliding_puzzle import _puzzle_neighbors, _puzzle_parity


def _heuristic_check(reverse, goals, heuristic):
    from heapq import heapify, heappop, heappush

    distance = dict.fromkeys(goals, 0)
    queue = [(0, name) for name in goals]
    heapify(queue)
    while queue:
        cost, name = heappop(queue)
        if cost != distance[name]:
            continue
        for previous, weight in reverse[name]:
            candidate = cost + weight
            if candidate < distance.get(previous, float("inf")):
                distance[previous] = candidate
                heappush(queue, (candidate, previous))

    overestimates = [name for name, cost in distance.items() if heuristic[name] > cost]
    inconsistent_edges = [
        (start, end)
        for end, neighbors in reverse.items() for start, weight in neighbors
        if heuristic[start] > weight + heuristic[end]
    ]
    return {
        "admissible": not overestimates,
        "consistent": not inconsistent_edges,
        "overestimates": overestimates,
        "inconsistent_edges": inconsistent_edges,
    }


def _solve_search_trace(start, goals, edges, algorithm, heuristic, directed, depth_limit, budget):
    from collections import deque
    from heapq import heappop, heappush
    from itertools import count

    nodes = {name: [] for name in (start, *goals)}
    for left, right, weight in edges:
        nodes.setdefault(left, []).append((right, weight))
        nodes.setdefault(right, [])
        if not directed:
            nodes[right].append((left, weight))

    trace = []
    goal_set = set(goals)
    rounds = []
    check = None
    if heuristic is not None:
        reverse = {name: [] for name in nodes}
        for left, neighbors in nodes.items():
            for right, weight in neighbors:
                reverse[right].append((left, weight))
        check = _heuristic_check(reverse, goals, heuristic)

    def visit(path, cost, priority):
        if len(trace) >= budget:
            raise OverflowError("Search trace step budget exceeded.")
        name = path[-1]
        trace.append({
            "node": name, "depth": len(path) - 1, "g": cost,
            "h": None if heuristic is None else heuristic[name], "priority": priority,
        })

    def depth_search(limit):
        cutoff = False
        pending = [((start,), 0)]
        while pending:
            path, cost = pending.pop()
            name = path[-1]
            level = len(path) - 1
            visit(path, cost, None)
            if name in goal_set:
                return "found", path, cost
            successors = [(child, weight) for child, weight in nodes[name] if child not in path]
            if level == limit:
                cutoff = cutoff or bool(successors)
                continue
            pending.extend(((*path, child), cost + weight) for child, weight in reversed(successors))
            if len(pending) > budget:
                raise OverflowError("Search trace frontier budget exceeded.")
        return ("cutoff" if cutoff else "unreachable"), None, None

    def frontier_search():
        sequence = count()
        use_best_cost = algorithm in ("ucs", "astar")
        queue = deque()
        heap = []
        best = {start: 0}

        def push(path, cost):
            if algorithm == "bfs":
                queue.append((path, cost))
                return
            estimate = 0 if heuristic is None else heuristic[path[-1]]
            if algorithm == "gbfs":
                priority = estimate
            else:
                priority = cost + estimate
            heappush(heap, (priority, next(sequence), path, cost))

        push((start,), 0)
        while queue or heap:
            if algorithm == "bfs":
                path, cost = queue.popleft()
                priority = None
            else:
                priority, _, path, cost = heappop(heap)
            name = path[-1]
            if use_best_cost and cost != best[name]:
                continue
            visit(path, cost, priority)
            if name in goal_set:
                return "found", path, cost
            for child, weight in nodes[name]:
                candidate = cost + weight
                if child in best and (not use_best_cost or candidate >= best[child]):
                    continue
                best[child] = candidate
                push((*path, child), candidate)
                if len(heap) + len(queue) > budget:
                    raise OverflowError("Search trace frontier budget exceeded.")
        return "unreachable", None, None

    if algorithm == "ids":
        maximum = len(nodes) - 1 if depth_limit is None else min(depth_limit, len(nodes) - 1)
        for limit in range(maximum + 1):
            first = len(trace)
            status, path, cost = depth_search(limit)
            rounds.append({"limit": limit, "status": status, "trace_range": (first, len(trace))})
            if status != "cutoff":
                break
    elif algorithm in ("dfs", "dls"):
        status, path, cost = depth_search(len(nodes) - 1 if depth_limit is None else depth_limit)
    else:
        status, path, cost = frontier_search()

    optimal_for = None
    if status == "found":
        if algorithm == "ucs" or (algorithm == "astar" and check["admissible"]):
            optimal_for = "cost"
        elif algorithm in ("bfs", "ids"):
            optimal_for = "depth"
    return {
        "status": status, "path": None if path is None else list(path), "cost": cost,
        "depth": None if path is None else len(path) - 1,
        "optimal_for": optimal_for, "heuristic_check": check, "trace": trace, "rounds": rounds,
    }


def _search_trace(problem):
    from .offline_optimization import _bounded_list, _unique_names
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _name, _standalone

    _fields(
        problem, ("type", "start", "goals", "edges", "algorithm"),
        ("heuristic", "directed", "depth_limit"),
    )
    algorithm = problem["algorithm"]
    if algorithm not in ("bfs", "ucs", "dfs", "dls", "ids", "gbfs", "astar"):
        raise OfflineProblemError("unsupported", "Chọn bfs, ucs, dfs, dls, ids, gbfs hoặc astar.")
    start = _name(problem["start"], "start")
    goals = _unique_names(_bounded_list(problem["goals"], "goals", 1, 120), "Tên đích")
    directed = problem.get("directed", True)
    if type(directed) is not bool:
        raise OfflineProblemError("invalid", "directed phải là true hoặc false.")
    if algorithm == "dls" and "depth_limit" not in problem:
        raise OfflineProblemError("needs_input", "DLS cần depth_limit.")
    if "depth_limit" in problem and algorithm not in ("dls", "ids"):
        raise OfflineProblemError("unsupported", "depth_limit chỉ dùng cho DLS và IDS.")
    depth_limit = _integer(problem["depth_limit"], "depth_limit", 0, 120) if "depth_limit" in problem else None

    edges = []
    declared = set()
    nodes = {start, *goals}
    for row in _bounded_list(problem["edges"], "edges", 0, 600):
        row = _array(row, "Cạnh", 2, 3)
        left, right = _name(row[0], "Đỉnh đầu"), _name(row[1], "Đỉnh cuối")
        weight = _integer(row[2], "Chi phí", 0, 1_000_000) if len(row) == 3 else 1
        key = (left, right) if directed else tuple(sorted((left, right)))
        if key in declared:
            raise OfflineProblemError("invalid", "Mỗi cặp đỉnh chỉ được khai báo cạnh một lần.")
        declared.add(key)
        if left == right and not directed:
            raise OfflineProblemError("invalid", "Cạnh vô hướng phải nối hai đỉnh khác nhau.")
        nodes.update((left, right))
        edges.append((left, right, weight))
    if len(nodes) > 120:
        raise OfflineProblemError("limit", "Đồ thị vượt giới hạn 120 đỉnh.")

    heuristic = None
    if algorithm in ("gbfs", "astar"):
        if "heuristic" not in problem:
            raise OfflineProblemError("needs_input", "GBFS và A* cần heuristic cho các đỉnh.")
        heuristic = problem["heuristic"]
        if not isinstance(heuristic, dict) or heuristic.keys() - nodes:
            raise OfflineProblemError("invalid", "heuristic chỉ được chứa các đỉnh trong đồ thị.")
        missing = nodes - heuristic.keys()
        if missing:
            raise OfflineProblemError("needs_input", "Thiếu heuristic cho: " + ", ".join(sorted(missing)) + ".")
        heuristic = {name: _integer(value, "Giá trị heuristic", 0, 1_000_000) for name, value in heuristic.items()}
    elif "heuristic" in problem:
        raise OfflineProblemError("unsupported", "heuristic chỉ dùng cho GBFS và A*.")

    args = start, goals, edges, algorithm, heuristic, directed, depth_limit, 4_000
    result = _solve_search_trace(*args)
    if result["status"] == "found":
        summary = f"Tìm thấy đường đi có {result['depth']} bước, chi phí {result['cost']}."
    elif result["status"] == "cutoff":
        summary = "Đã chạm giới hạn độ sâu và còn nhánh chưa xét."
    else:
        summary = "Đã duyệt hết các nhánh. Không tìm được đường tới đích."
    diagnostic = ["trace ghi các trạng thái được lấy ra xét. Khi hòa, thuật toán ưu tiên thứ tự cạnh khai báo."]
    if result["optimal_for"] == "depth":
        diagnostic.append("Kết quả tối ưu theo số cạnh.")
    elif result["optimal_for"] == "cost":
        diagnostic.append("Kết quả tối ưu theo tổng chi phí.")
    if result["heuristic_check"] is not None and not result["heuristic_check"]["admissible"]:
        diagnostic.append("Heuristic vượt chi phí thật ở ít nhất một đỉnh. Đường đi tìm được có thể chưa tối ưu.")
    metric = ("search_path_cost", result["cost"]) if result["status"] == "found" else None
    return OfflineSolution(
        "search_trace",
        _standalone((_heuristic_check, _solve_search_trace), _solve_search_trace, args, result),
        summary, tuple(diagnostic), metric,
    )


def _compare_puzzle_heuristics(start, goal, state_limit):
    from heapq import heappop, heappush
    from itertools import count

    target_positions = {tile: divmod(index, 3) for index, tile in enumerate(goal)}

    def misplaced(board):
        return sum(tile != 0 and tile != goal[index] for index, tile in enumerate(board))

    def manhattan(board):
        distance = 0
        for index, tile in enumerate(board):
            if tile:
                row, col = divmod(index, 3)
                target_row, target_col = target_positions[tile]
                distance += abs(row - target_row) + abs(col - target_col)
        return distance

    def search(estimate):
        sequence = count()
        queue = [(estimate(start), next(sequence), start, 0)]
        best = {start: 0}
        parent = {start: None}
        expanded = 0
        while queue:
            _, _, board, distance = heappop(queue)
            if distance != best[board]:
                continue
            if board == goal:
                path = []
                while board is not None:
                    path.append(board)
                    board = parent[board]
                return expanded, path[::-1]
            expanded += 1
            for neighbor in _puzzle_neighbors(board):
                candidate = distance + 1
                if candidate >= best.get(neighbor, float("inf")):
                    continue
                if neighbor not in best and len(best) >= state_limit:
                    raise OverflowError("8-puzzle state budget exceeded.")
                best[neighbor] = candidate
                parent[neighbor] = board
                heappush(queue, (candidate + estimate(neighbor), next(sequence), neighbor, candidate))
        raise RuntimeError("No path found between boards with matching parity.")

    reachable = _puzzle_parity(start) == _puzzle_parity(goal)
    result = {"status": "found" if reachable else "unreachable", "moves": None}
    for name, estimate in (("h1", misplaced), ("h2", manhattan)):
        expanded, path = search(estimate) if reachable else (0, None)
        result[name] = {"initial": estimate(start), "expanded": expanded, "path": path}
    if reachable:
        result["moves"] = len(result["h2"]["path"]) - 1
    return result


def _puzzle_heuristics(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "start", "goal"))
    boards = []
    for name in ("start", "goal"):
        board = tuple(_integer(number, name, 0, 8) for number in _array(problem[name], name, 9, 9))
        if len(set(board)) != 9:
            raise OfflineProblemError("invalid", f"{name} phải có đủ mỗi số từ 0 đến 8 đúng một lần.")
        boards.append(board)
    args = (*boards, 181_440)
    result = _compare_puzzle_heuristics(*args)
    h1, h2 = result["h1"], result["h2"]
    if result["status"] == "found":
        summary = f"{result['moves']} bước tối thiểu. h1 mở rộng {h1['expanded']} nút, h2 mở rộng {h2['expanded']} nút."
    else:
        summary = "Hai bảng khác tính chẵn lẻ, không thể trượt tới đích."
    return OfflineSolution(
        "puzzle_heuristics",
        _standalone(
            (_puzzle_parity, _puzzle_neighbors, _compare_puzzle_heuristics),
            _compare_puzzle_heuristics, args, result,
        ),
        summary,
        (
            "h1 đếm ô sai chỗ, h2 tính tổng khoảng cách Manhattan. Cả hai bỏ qua ô trống 0.",
            "expanded đếm các nút sinh con. Hai lần chạy cùng dùng A* và cùng ưu tiên nút vào hàng đợi trước khi hòa.",
        ),
        ("minimum_moves", result["moves"]),
    )


COURSE_SEARCH_SOLVERS = {"search_trace": _search_trace, "puzzle_heuristics": _puzzle_heuristics}
