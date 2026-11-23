"""Generate and check examples that use SimpleAI SearchProblem."""

from .offline_optimization import _bounded_list, _unique_names
from .sliding_puzzle import _puzzle_neighbors, _puzzle_parity

__all__ = ["SIMPLEAI_SEARCH_SOLVERS"]


def _solve_simpleai_graph(start, goals, edges, algorithm, directed, heuristic, depth_limit, visit_limit):
    from simpleai.search import SearchProblem, astar, breadth_first, depth_first, greedy, limited_depth_first, uniform_cost

    adjacency = {node: {} for node in (start, *goals)}
    for source, target, weight in edges:
        adjacency.setdefault(source, {})[target] = weight
        adjacency.setdefault(target, {})
        if not directed:
            adjacency[target][source] = weight
    goal_set = set(goals)
    rounds = []
    visited = 0

    def record_visit():
        nonlocal visited
        visited += 1
        if visited > visit_limit:
            raise OverflowError("SimpleAI graph visit budget exceeded.")

    class GraphProblem(SearchProblem):
        def actions(self, state):
            candidates = adjacency[state]
            return reversed(candidates) if algorithm == "dfs" else candidates

        def result(self, state, action):
            return action

        def cost(self, state, action, state2):
            return adjacency[state][state2]

        def is_goal(self, state):
            record_visit()
            return state in goal_set

        def heuristic(self, state):
            return heuristic[state] if heuristic is not None else 0

    class LimitedGraphProblem(SearchProblem):
        def __init__(self, limit):
            super().__init__((start,))
            self.limit = limit
            self.cutoff = False

        def actions(self, state):
            return [child for child in reversed(adjacency[state[-1]]) if child not in state]

        def result(self, state, action):
            return (*state, action)

        def cost(self, state, action, state2):
            return adjacency[state[-1]][action]

        def is_goal(self, state):
            record_visit()
            node = state[-1]
            if node in goal_set:
                return True
            if len(state) - 1 == self.limit and any(child not in state for child in adjacency[node]):
                self.cutoff = True
            return False

    if algorithm in ("dls", "ids"):
        maximum = len(adjacency) - 1
        if depth_limit is not None:
            maximum = min(maximum, depth_limit)
        depths = (maximum,) if algorithm == "dls" else range(maximum + 1)
        for depth in depths:
            before = visited
            problem = LimitedGraphProblem(depth)
            # SimpleAI's global visited set may prune a shallower revisit in DLS.
            solution = limited_depth_first(problem, depth_limit=depth, graph_search=False)
            status = "found" if solution is not None else ("cutoff" if problem.cutoff else "unreachable")
            rounds.append({"limit": depth, "status": status, "visited": visited - before})
            if status != "cutoff":
                break
        path = None if solution is None else list(solution.state)
    else:
        algorithms = {"bfs": breadth_first, "ucs": uniform_cost, "dfs": depth_first, "greedy": greedy, "astar": astar}
        solution = algorithms[algorithm](GraphProblem(start), graph_search=True)
        path = None if solution is None else [state for _, state in solution.path()]
        status = "unreachable" if solution is None else "found"

    optimal_for = None
    if solution is not None:
        if algorithm in ("bfs", "ids"):
            optimal_for = "depth"
        elif algorithm in ("ucs", "astar"):
            optimal_for = "cost"
    return {
        "status": status, "path": path, "cost": None if solution is None else solution.cost,
        "depth": None if solution is None else solution.depth, "optimal_for": optimal_for,
        "visited": visited, "rounds": rounds,
    }


def _solve_simpleai_puzzle(start, goal, heuristic, visit_limit):
    from simpleai.search import SearchProblem, astar

    target_positions = {tile: divmod(index, 3) for index, tile in enumerate(goal)}
    visited = 0

    class PuzzleProblem(SearchProblem):
        def actions(self, state):
            return _puzzle_neighbors(state)

        def result(self, state, action):
            return action

        def is_goal(self, state):
            nonlocal visited
            visited += 1
            if visited > visit_limit:
                raise OverflowError("SimpleAI puzzle visit budget exceeded.")
            return state == goal

        def heuristic(self, state):
            if heuristic == "misplaced":
                return sum(tile != 0 and tile != goal[index] for index, tile in enumerate(state))
            distance = 0
            for index, tile in enumerate(state):
                if tile != 0:
                    row, col = divmod(index, 3)
                    target_row, target_col = target_positions[tile]
                    distance += abs(row - target_row) + abs(col - target_col)
            return distance

    problem = PuzzleProblem(start)
    solution = astar(problem, graph_search=True) if _puzzle_parity(start) == _puzzle_parity(goal) else None
    return {
        "status": "unreachable" if solution is None else "found",
        "moves": None if solution is None else solution.depth,
        "path": None if solution is None else [state for _, state in solution.path()],
        "initial_heuristic": problem.heuristic(start),
        "visited": visited,
    }


def _run_with_dependency(solver, *args):
    from .offline_solver import OfflineProblemError

    try:
        return solver(*args)
    except ImportError as exc:
        raise OfflineProblemError(
            "unsupported", "Không nạp được SimpleAI. Cài mô-đun qua bộ wheel offline đi kèm.",
        ) from exc


def _compare_simpleai_puzzle(start, goal, visit_limit):
    h1 = _solve_simpleai_puzzle(start, goal, "misplaced", visit_limit)
    h2 = _solve_simpleai_puzzle(start, goal, "manhattan", visit_limit)
    if (h1["status"], h1["moves"]) != (h2["status"], h2["moves"]):
        raise RuntimeError("A* heuristics disagree on the optimal path length.")
    return {"status": h2["status"], "moves": h2["moves"], "h1": h1, "h2": h2}


def _simpleai_graph(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _name, _standalone

    _fields(
        problem, ("type", "start", "goals", "edges", "algorithm"),
        ("heuristic", "directed", "depth_limit"),
    )
    algorithm = problem["algorithm"]
    if algorithm == "gbfs":
        algorithm = "greedy"
    if algorithm not in ("bfs", "ucs", "dfs", "dls", "ids", "greedy", "astar"):
        raise OfflineProblemError("unsupported", "SimpleAI hỗ trợ bfs, ucs, dfs, dls, ids, greedy và astar.")

    start = _name(problem["start"], "start")
    goals = _unique_names(_bounded_list(problem["goals"], "goals", 1, 120), "Tên đích")
    directed = problem.get("directed", True)
    if type(directed) is not bool:
        raise OfflineProblemError("invalid", "directed phải là true hoặc false.")
    if algorithm == "dls" and "depth_limit" not in problem:
        raise OfflineProblemError("needs_input", "DLS cần depth_limit.")
    if "depth_limit" in problem and algorithm not in ("dls", "ids"):
        raise OfflineProblemError("unsupported", "depth_limit chỉ dùng với DLS và IDS.")
    depth_limit = _integer(problem["depth_limit"], "depth_limit", 0, 120) if "depth_limit" in problem else None

    edges = []
    edge_keys = set()
    nodes = {start, *goals}
    for row in _bounded_list(problem["edges"], "edges", 0, 600):
        row = _array(row, "Cạnh", 2, 3)
        source, target = _name(row[0], "Đỉnh đầu"), _name(row[1], "Đỉnh cuối")
        key = (source, target) if directed else tuple(sorted((source, target)))
        if key in edge_keys:
            raise OfflineProblemError("invalid", "Mỗi cặp đỉnh chỉ được khai báo cạnh một lần.")
        edge_keys.add(key)
        weight = _integer(row[2], "Chi phí", 0, 1_000_000) if len(row) == 3 else 1
        edges.append((source, target, weight))
        nodes.update((source, target))
    if len(nodes) > 120:
        raise OfflineProblemError("limit", "Đồ thị vượt giới hạn 120 đỉnh.")

    heuristic = None
    if algorithm in ("greedy", "astar"):
        if "heuristic" not in problem:
            raise OfflineProblemError("needs_input", "Greedy và A* cần heuristic cho các đỉnh.")
        values = problem["heuristic"]
        if not isinstance(values, dict) or values.keys() - nodes:
            raise OfflineProblemError("invalid", "heuristic chỉ được chứa các đỉnh trong đồ thị.")
        if nodes - values.keys():
            raise OfflineProblemError("needs_input", "Thiếu heuristic cho: " + ", ".join(sorted(nodes - values.keys())) + ".")
        heuristic = {name: _integer(value, "Giá trị heuristic", 0, 1_000_000) for name, value in values.items()}
    elif "heuristic" in problem:
        raise OfflineProblemError("unsupported", "heuristic chỉ dùng với Greedy hoặc A*.")
    if algorithm == "astar":
        if any(heuristic[goal] != 0 for goal in goals):
            raise OfflineProblemError("invalid", "A* cần h(goal) = 0 với mọi đích.")
        for source, target, weight in edges:
            if heuristic[source] > weight + heuristic[target] or (
                not directed and heuristic[target] > weight + heuristic[source]
            ):
                raise OfflineProblemError(
                    "unsupported",
                    f"A* đồ thị của SimpleAI cần heuristic nhất quán. Kiểm tra cạnh {source} → {target}.",
                )

    args = start, goals, edges, algorithm, directed, heuristic, depth_limit, 4_000
    result = _run_with_dependency(_solve_simpleai_graph, *args)
    if result["status"] == "found":
        summary = f"SimpleAI tìm được đường đi {result['depth']} bước, chi phí {result['cost']}."
    elif result["status"] == "cutoff":
        summary = "Đã chạm giới hạn độ sâu và còn nhánh chưa xét."
    else:
        summary = "SimpleAI đã duyệt hết các nhánh mà chưa tới đích."
    notes = ["Chi phí là tổng trọng số các cạnh được dùng. BFS tối ưu độ sâu, kể cả khi trọng số không đều."]
    if algorithm in ("dls", "ids"):
        notes.append("DLS/IDS dùng đường đang xét làm trạng thái và tránh quay lại tổ tiên.")
    if result["optimal_for"] == "cost":
        notes.append("Tổng chi phí tối ưu với các giả thiết đã kiểm tra.")
    elif result["optimal_for"] == "depth":
        notes.append("Đường đi tối ưu theo số cạnh.")
    return OfflineSolution(
        "simpleai_graph",
        _standalone((_solve_simpleai_graph,), _solve_simpleai_graph, args, result),
        summary, tuple(notes),
        ("minimum_cost", result["cost"]) if result["optimal_for"] == "cost" else (
            ("minimum_depth", result["depth"]) if result["optimal_for"] == "depth" else None
        ),
    )


def _simpleai_puzzle(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "start", "goal"), ("heuristic",))
    heuristic = problem.get("heuristic", "manhattan")
    if heuristic not in ("manhattan", "misplaced", "both"):
        raise OfflineProblemError("unsupported", "Heuristic của 8-puzzle nhận manhattan, misplaced hoặc both.")
    boards = []
    for key in ("start", "goal"):
        board = tuple(_integer(tile, key, 0, 8) for tile in _array(problem[key], key, 9, 9))
        if len(set(board)) != 9:
            raise OfflineProblemError("invalid", f"{key} phải chứa mỗi số từ 0 đến 8 đúng một lần.")
        boards.append(board)

    functions = (_puzzle_parity, _puzzle_neighbors, _solve_simpleai_puzzle)
    if heuristic == "both":
        args = (*boards, 3_000)
        solver = _compare_simpleai_puzzle
        functions += (solver,)
    else:
        args = (*boards, heuristic, 3_000)
        solver = _solve_simpleai_puzzle
    result = _run_with_dependency(solver, *args)
    if result["status"] == "found":
        summary = f"A* của SimpleAI tìm được lời giải tối thiểu {result['moves']} bước trượt."
    else:
        summary = "Hai bảng khác tính chẵn lẻ, không thể trượt tới đích."
    if heuristic == "both" and result["status"] == "found":
        summary += f" h1 xét {result['h1']['visited']} nút, h2 xét {result['h2']['visited']} nút."
    return OfflineSolution(
        "simpleai_puzzle",
        _standalone(functions, solver, args, result),
        summary, ("Dùng A* với trạng thái tuple. Heuristic bỏ qua ô trống 0.",),
        ("minimum_moves", result["moves"]),
    )


SIMPLEAI_SEARCH_SOLVERS = {"simpleai_graph": _simpleai_graph, "simpleai_puzzle": _simpleai_puzzle}
