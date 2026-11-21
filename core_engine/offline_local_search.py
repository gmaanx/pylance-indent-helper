"""Deterministic steepest-ascent trace on an explicit state graph."""

__all__ = ["LOCAL_SEARCH_SOLVERS"]


def _hill_trace(scores, edges, start, goal, maximize, sideways_limit, step_limit):
    from collections import defaultdict

    neighbors = defaultdict(list)
    for source, destination in edges:
        neighbors[source].append(destination)
    order = 1 if maximize else -1
    current = start
    sideways = 0
    path = [current]
    seen = {current}
    for step in range(step_limit + 1):
        if current == goal:
            status = "goal"
            break
        if step == step_limit:
            status = "step_limit"
            break
        available = neighbors[current]
        if not available:
            status = "no_neighbors"
            break
        highest = max(order * scores[node] for node in available)
        options = [node for node in available if order * scores[node] == highest]
        improvement = highest - order * scores[current]
        if improvement < 0:
            status = "local_optimum"
            break
        if improvement == 0:
            if sideways >= sideways_limit:
                status = "plateau"
                break
            choices = [node for node in options if node not in seen]
            if not choices:
                status = "plateau_cycle"
                break
            current = choices[0]
            sideways += 1
        else:
            current = options[0]
            sideways = 0
        path.append(current)
        seen.add(current)
    return {"status": status, "path": path, "scores": [scores[node] for node in path]}


def _hill_climbing(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _name, _standalone

    _fields(problem, ("type", "scores", "edges", "start"), ("goal", "objective", "sideways_limit", "step_limit"))
    raw = problem["scores"]
    if not isinstance(raw, dict) or not 1 <= len(raw) <= 400:
        raise OfflineProblemError("invalid", "scores cần từ 1 đến 400 trạng thái có điểm số.")
    scores = {_name(name, "Trạng thái"): _integer(value, "Điểm", -10**9, 10**9) for name, value in raw.items()}

    def state(value):
        name = _name(value, "Trạng thái")
        if name not in scores:
            raise OfflineProblemError("invalid", "Trạng thái cần có trong scores.")
        return name

    start = state(problem["start"])
    goal = state(problem["goal"]) if "goal" in problem else None
    edges = [
        tuple(state(node) for node in _array(pair, "Cạnh có hướng", 2, 2))
        for pair in _array(problem["edges"], "edges", 0, 5000)
    ]
    objective = problem.get("objective", "max")
    if objective not in ("max", "min"):
        raise OfflineProblemError("unsupported", "objective cần là max hoặc min.")
    sideways = _integer(problem.get("sideways_limit", 0), "sideways_limit", 0, 400)
    steps = _integer(problem.get("step_limit", 400), "step_limit", 0, 800)
    args = (scores, edges, start, goal, objective == "max", sideways, steps)
    result = _hill_trace(*args)
    summary = {
        "goal": "Đã chạm trạng thái đích.",
        "step_limit": "Đã chạm giới hạn bước.",
        "no_neighbors": "Trạng thái cuối không có láng giềng.",
        "local_optimum": "Dừng ở cực trị cục bộ.",
        "plateau": "Dừng ở vùng bằng điểm vì đã hết bước ngang.",
        "plateau_cycle": "Dừng vì các bước ngang tốt nhất đều trở lại trạng thái đã gặp.",
    }[result["status"]]
    return OfflineSolution(
        "hill_climbing", _standalone((_hill_trace,), _hill_trace, args, result),
        summary, ("Chọn láng giềng tốt nhất, hòa theo thứ tự cạnh. Vết chạy ghi trạng thái và điểm sau mỗi bước.",),
        ("terminal_score", result["scores"][-1]),
    )


def _prefix_search(start, goal, alphabet, algorithm, depth_limit):
    width = len(alphabet)
    target_depth = len(goal) - len(start)
    suffix = goal[len(start):]
    reachable = goal.startswith(start) and all(letter in alphabet for letter in suffix)
    bound = min(depth_limit, target_depth) if depth_limit is not None else target_depth

    def tree_size(depth):
        return sum(width**level for level in range(depth + 1))

    if not reachable or bound < target_depth:
        visited = (
            sum(tree_size(level) for level in range(bound + 1))
            if algorithm == "ids" else tree_size(bound)
        )
        return {"status": "cutoff" if bound < target_depth else "unreachable", "visited": visited, "path": None}

    digits = [alphabet.index(letter) for letter in suffix]
    if algorithm in ("bfs", "ucs"):
        rank = 0
        for digit in digits:
            rank = rank * width + digit
        visited = tree_size(target_depth - 1) + rank + 1
    else:
        visited = target_depth + 1 + sum(
            digit * tree_size(target_depth - index - 1)
            for index, digit in enumerate(digits)
        )
        if algorithm == "ids":
            visited += sum(tree_size(level) for level in range(target_depth))
    path = [goal[:len(start) + index] for index in range(target_depth + 1)]
    return {"status": "found", "visited": visited, "path": path, "cost": target_depth}


def _string_search(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _fields, _integer, _standalone

    _fields(problem, ("type", "goal", "alphabet", "algorithm"), ("start", "depth_limit"))
    start, goal, alphabet = problem.get("start", ""), problem["goal"], problem["alphabet"]
    if (
        not isinstance(start, str) or not isinstance(goal, str) or not isinstance(alphabet, str)
        or not 0 <= len(start) <= len(goal) <= 64 or not 1 <= len(alphabet) <= 64
        or len(set(alphabet)) != len(alphabet)
    ):
        raise OfflineProblemError("invalid", "Xâu tối đa 64 ký tự; alphabet cần 1–64 ký tự khác nhau.")
    algorithm = problem["algorithm"]
    if algorithm not in ("bfs", "ucs", "dfs", "dls", "ids"):
        raise OfflineProblemError("unsupported", "Chọn bfs, ucs, dfs, dls hoặc ids.")
    if "depth_limit" in problem and algorithm not in ("dls", "ids"):
        raise OfflineProblemError("unsupported", "depth_limit chỉ dùng cho DLS hoặc IDS.")
    if algorithm == "dls" and "depth_limit" not in problem:
        raise OfflineProblemError("needs_input", "DLS cần depth_limit.")
    limit = _integer(problem["depth_limit"], "depth_limit", 0, 64) if "depth_limit" in problem else None
    args = (start, goal, alphabet, algorithm, limit)
    result = _prefix_search(*args)
    summary = {
        "found": f"Đạt xâu đích sau {result.get('cost', 0)} bước thêm ký tự.",
        "cutoff": "Chạm giới hạn độ sâu.",
        "unreachable": "Không thể sinh xâu đích với dữ liệu đã cho.",
    }[result["status"]]
    return OfflineSolution(
        "string_search", _standalone((_prefix_search,), _prefix_search, args, result),
        summary, ("Mỗi bước thêm một ký tự, chi phí 1. Số nút xét theo thứ tự alphabet, tính trực tiếp từ cây tiền tố.",),
        ("visited_count", result["visited"]),
    )


LOCAL_SEARCH_SOLVERS = {"hill_climbing": _hill_climbing, "string_search": _string_search}
