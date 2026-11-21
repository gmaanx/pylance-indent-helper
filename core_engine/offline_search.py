"""Solvers for grid navigation and finite, two-player game trees."""

from heapq import heappop, heappush

from .offline_solver import _bfs, _reconstruct

__all__ = ["SEARCH_SOLVERS"]

_GRID_STATES = 80_000
_TREE_NODES = 12_000


def _grid_path(rows, start, goal, moves, no_corner_cut, costs, checkpoints, ordered, algorithm, limit):
    cardinal = ((-1, 0), (0, -1), (0, 1), (1, 0))
    if moves == "diagonal":
        steps = cardinal + ((-1, -1), (-1, 1), (1, -1), (1, 1))
    elif moves == "knight":
        steps = ((-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1))
    else:
        steps = cardinal

    checkpoint_index = {position: index for index, position in enumerate(checkpoints)}
    finished = len(checkpoints) if ordered else (1 << len(checkpoints)) - 1

    def enter(row, col, keys):
        if not (0 <= row < len(rows) and 0 <= col < len(rows[0])):
            return None
        tile = rows[row][col]
        if tile == "#" or ("A" <= tile <= "F" and not (keys & (1 << (ord(tile) - ord("A"))))):
            return None
        return tile

    def collect(position, tile, keys, progress):
        if "a" <= tile <= "f":
            keys |= 1 << (ord(tile) - ord("a"))
        index = checkpoint_index.get(position)
        if index is not None:
            if ordered:
                if index > progress:
                    return None
                if index == progress:
                    progress += 1
            else:
                progress |= 1 << index
        return position, keys, progress

    initial = collect(start, rows[start[0]][start[1]], 0, 0)
    if initial is None:
        return None

    def complete(state):
        return state[0] == goal and state[2] == finished

    def neighbors(state):
        (row, col), keys, progress = state
        for dr, dc in steps:
            nr, nc = row + dr, col + dc
            tile = enter(nr, nc, keys)
            if tile is None:
                continue
            if moves == "diagonal" and no_corner_cut and dr and dc:
                if enter(row + dr, col, keys) is None or enter(row, col + dc, keys) is None:
                    continue
            child = collect((nr, nc), tile, keys, progress)
            if child is not None:
                yield child, costs.get(tile, 1)

    if algorithm == "bfs":
        path = _bfs(initial, complete, lambda state: (child for child, _ in neighbors(state)), limit)
        return None if path is None else {"cost": len(path) - 1, "path": [state[0] for state in path]}

    frontier = [(0, initial)]
    distance = {initial: 0}
    parent = {initial: None}
    while frontier:
        cost, state = heappop(frontier)
        if cost != distance[state]:
            continue
        if complete(state):
            return {"cost": cost, "path": [entry[0] for entry in _reconstruct(parent, state)]}
        for child, weight in neighbors(state):
            candidate = cost + weight
            if candidate >= distance.get(child, float("inf")):
                continue
            if child not in distance and len(distance) >= limit:
                raise OverflowError("Grid search state limit exceeded")
            distance[child] = candidate
            parent[child] = state
            heappush(frontier, (candidate, child))
    return None


def _grid(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(
        problem, ("type", "rows", "start", "goal"),
        ("moves", "no_corner_cut", "costs", "visit", "visit_order", "algorithm"),
    )
    rows = _array(problem["rows"], "rows", 1, 80)
    alphabet = set(".#0123456789abcdefABCDEF")
    if not all(isinstance(row, str) and 1 <= len(row) <= 80 and set(row) <= alphabet for row in rows):
        raise OfflineProblemError("invalid", "Mỗi hàng cần 1–80 ô gồm dấu '.', '#', số, chìa a–f hoặc cửa A–F.")
    if any(len(row) != len(rows[0]) for row in rows):
        raise OfflineProblemError("invalid", "Các hàng phải cùng độ dài.")

    def position(value, name):
        row, col = _array(value, name, 2, 2)
        row = _integer(row, name + " hàng", 0, len(rows) - 1)
        col = _integer(col, name + " cột", 0, len(rows[0]) - 1)
        if rows[row][col] == "#":
            raise OfflineProblemError("invalid", f"{name} nằm trên tường.")
        return row, col

    start = position(problem["start"], "start")
    goal = position(problem["goal"], "goal")
    if "A" <= rows[start[0]][start[1]] <= "F":
        raise OfflineProblemError("invalid", "Điểm xuất phát nằm trên một cửa chưa có chìa.")
    checkpoints = [position(point, "visit") for point in _array(problem.get("visit", []), "visit", 0, 12)]
    if len(checkpoints) != len(set(checkpoints)):
        raise OfflineProblemError("invalid", "Các ô trong visit phải khác nhau.")
    order = problem.get("visit_order", "any")
    if order not in ("any", "ordered"):
        raise OfflineProblemError("unsupported", "visit_order nhận 'any' hoặc 'ordered'.")

    moves = problem.get("moves", "cardinal")
    if moves not in ("cardinal", "diagonal", "knight"):
        raise OfflineProblemError("unsupported", "moves nhận 'cardinal', 'diagonal' hoặc 'knight'.")
    no_corner_cut = problem.get("no_corner_cut", True)
    if type(no_corner_cut) is not bool or ("no_corner_cut" in problem and moves != "diagonal"):
        raise OfflineProblemError("invalid", "no_corner_cut nhận boolean và chỉ dùng với moves='diagonal'.")
    costs = problem.get("costs", {})
    if not isinstance(costs, dict) or any(tile not in alphabet or tile == "#" for tile in costs):
        raise OfflineProblemError("invalid", "costs phải ánh xạ ký hiệu ô đi được sang chi phí nguyên.")
    costs = {tile: _integer(cost, "Chi phí ô", 0, 10_000) for tile, cost in costs.items()}
    weighted = any(cost != 1 for cost in costs.values())
    algorithm = problem.get("algorithm", "ucs" if weighted else "bfs")
    if algorithm not in ("bfs", "ucs") or (algorithm == "bfs" and weighted):
        raise OfflineProblemError("unsupported", "Dùng BFS cho mỗi bước giá 1 hoặc UCS cho chi phí không âm.")
    args = (rows, start, goal, moves, no_corner_cut, costs, checkpoints, order == "ordered", algorithm, _GRID_STATES)
    result = _grid_path(*args)
    summary = "Không có đường thỏa điều kiện." if result is None else f"Chi phí đường đi tối thiểu: {result['cost']}."
    return OfflineSolution(
        "grid", _standalone((_reconstruct, _bfs, _grid_path), _grid_path, args, result),
        summary,
        ("Tọa độ hàng/cột từ 0. Chi phí tính khi vào ô. Trạng thái giữ chìa khóa và các điểm đã ghé.",),
        ("minimum_cost", None if result is None else result["cost"]),
    )


def _solve_minimax(tree, maximizing, pruning, depth_limit):
    visited, evaluated, skipped = 0, 0, 0

    def choose(node, max_turn, level, alpha, beta):
        nonlocal visited, evaluated, skipped
        visited += 1
        if isinstance(node, int):
            evaluated += 1
            return node, []
        children, heuristic = node
        if level == depth_limit:
            evaluated += 1
            return heuristic, []
        best_value = float("-inf") if max_turn else float("inf")
        best_path = []
        for index, child in enumerate(children):
            value, path = choose(child, not max_turn, level + 1, alpha, beta)
            if (max_turn and value > best_value) or (not max_turn and value < best_value):
                best_value, best_path = value, [index, *path]
            if max_turn:
                alpha = max(alpha, best_value)
            else:
                beta = min(beta, best_value)
            if pruning and alpha >= beta:
                skipped += len(children) - index - 1
                break
        return best_value, best_path

    value, path = choose(tree, maximizing, 0, float("-inf"), float("inf"))
    return {"value": value, "path": path, "visited": visited, "evaluated": evaluated, "skipped_branches": skipped}


def _minimax(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "tree"), ("root", "algorithm", "depth_limit"))
    root = problem.get("root", "max")
    algorithm = problem.get("algorithm", "alpha_beta")
    if root not in ("max", "min") or algorithm not in ("minimax", "alpha_beta"):
        raise OfflineProblemError("unsupported", "root nhận max/min, algorithm nhận minimax/alpha_beta.")
    depth_limit = _integer(problem["depth_limit"], "depth_limit", 0, 40) if "depth_limit" in problem else None
    count = 0
    scored_cutoffs = 0

    def read(node, depth):
        nonlocal count, scored_cutoffs
        count += 1
        if count > _TREE_NODES or depth > 40:
            raise OfflineProblemError("limit", "Cây vượt giới hạn 12.000 nút hoặc 40 tầng.")
        if type(node) is int:
            return _integer(node, "Điểm nút lá", -10**9, 10**9)
        heuristic = None
        if isinstance(node, dict):
            _fields(node, ("children", "heuristic"))
            heuristic = _integer(node["heuristic"], "heuristic", -10**9, 10**9)
            node = node["children"]
        children = _array(node, "Con của nút", 1, 120)
        if depth == depth_limit:
            if heuristic is None:
                raise OfflineProblemError("needs_input", "Nút trong tại độ sâu cắt cần trường heuristic.")
            scored_cutoffs += 1
        return ([read(child, depth + 1) for child in children], heuristic)

    tree = read(problem["tree"], 0)
    args = (tree, root == "max", algorithm == "alpha_beta", depth_limit)
    result = _solve_minimax(*args)
    scope = "Giá trị theo độ sâu cắt" if scored_cutoffs else "Giá trị minimax"
    return OfflineSolution(
        "minimax", _standalone((_solve_minimax,), _solve_minimax, args, result),
        f"{scope}: {result['value']}. Số nút đánh giá: {result['evaluated']}.",
        ("MAX/MIN xen kẽ. Thứ tự xét và hòa theo vị trí trong danh sách con, chỉ số bắt đầu từ 0.",),
        ("minimax_value", result["value"]),
    )


SEARCH_SOLVERS = {"grid": _grid, "minimax": _minimax}
