"""Bounded SimpleAI local search for the course's N-queens exercises."""

import inspect
import json
import math
import subprocess
import sys

__all__ = ["SIMPLEAI_LOCAL_SOLVERS"]

_OPTIONS = {
    "hill_climbing": ("initial",),
    "hill_climbing_stochastic": ("initial",),
    "hill_climbing_random_restarts": ("restarts_limit",),
    "beam": ("beam_size",),
    "beam_best_first": ("beam_size",),
    "simulated_annealing": ("initial",),
    "genetic": ("population_size", "mutation_chance"),
}
_EVALUATION_LIMIT = 150_000
_TIMEOUT_SECONDS = 12


def _attacking_pairs(state):
    pairs = 0
    row_counts, diagonal_up, diagonal_down = {}, {}, {}
    for column, row in enumerate(state):
        for counts, key in ((row_counts, row), (diagonal_up, row - column), (diagonal_down, row + column)):
            current = counts.get(key, 0)
            pairs += current
            counts[key] = current + 1
    return pairs


def _search_queens(n, algorithm, seed, iterations, options, evaluation_limit):
    import random

    maximum_fitness = n * (n - 1) // 2
    if n <= 3:
        return {
            "status": "found" if n == 1 else "impossible_size",
            "board": [0] if n == 1 else None,
            "attacking_pairs": 0 if n == 1 else None,
            "fitness": 0 if n == 1 else None,
            "maximum_fitness": maximum_fitness,
            "evaluations": 0,
        }

    from simpleai.search import SearchProblem
    from simpleai.search import local

    class SearchStopped(Exception):
        pass

    class QueensProblem(SearchProblem):
        def __init__(self, initial):
            super().__init__(initial)
            self.evaluations = 0

        def actions(self, state):
            return [(column, row) for column in range(n) for row in range(n) if row != state[column]]

        def result(self, state, action):
            column, row = action
            return state[:column] + (row,) + state[column + 1:]

        def value(self, state):
            if self.evaluations >= evaluation_limit:
                raise SearchStopped()
            self.evaluations += 1
            return maximum_fitness - _attacking_pairs(state)

        def generate_random_state(self):
            return tuple(random.randrange(n) for _ in range(n))

        def crossover(self, first, second):
            split = random.randrange(1, n)
            return first[:split] + second[split:]

        def mutate(self, state):
            column = random.randrange(n)
            previous_row = state[column]
            row = random.randrange(n - 1)
            return self.result(state, (column, row + (row >= previous_row)))

    class TrackAccepted:
        best = None

        def event(self, phase, *args):
            if phase == "new_iteration":
                candidate = args[0][0]
            elif phase == "finished":
                candidate = args[1]
            else:
                return
            if self.best is None or candidate.value > self.best.value:
                self.best = candidate
            if candidate.value == maximum_fitness:
                raise SearchStopped()

    settings = dict(options)
    initial = tuple(settings.pop("initial", (0,) * n))
    problem = QueensProblem(initial)
    track = TrackAccepted()
    saved_state = random.getstate()
    try:
        random.seed(seed)
        getattr(local, algorithm)(problem, iterations_limit=iterations, viewer=track, **settings)
    except SearchStopped:
        pass
    finally:
        random.setstate(saved_state)

    best = track.best
    board = list(best.state) if best else None
    conflicts = maximum_fitness - best.value if best else None
    return {
        "status": "found" if conflicts == 0 else "not_found_within_budget",
        "board": board,
        "attacking_pairs": conflicts,
        "fitness": best.value if best else None,
        "maximum_fitness": maximum_fitness,
        "evaluations": problem.evaluations,
    }


def _isolated_search(args):
    from .offline_solver import OfflineProblemError

    worker = "\n".join((
        "import json, sys",
        inspect.getsource(_attacking_pairs),
        inspect.getsource(_search_queens),
        "try:\n    print(json.dumps(_search_queens(*json.load(sys.stdin))))",
        "except ImportError:\n    sys.exit(5)",
    ))
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    try:
        execution = subprocess.run(
            [sys.executable, "-c", worker], input=json.dumps(args), encoding="utf-8",
            capture_output=True, timeout=_TIMEOUT_SECONDS, **options,
        )
    except subprocess.TimeoutExpired as exc:
        raise OfflineProblemError("limit", "SimpleAI đã hết thời gian tìm kiếm. Giảm số lượt hoặc kích thước quần thể.") from exc
    except OSError as exc:
        raise OfflineProblemError("unsupported", "Không khởi động được tiến trình Python chạy SimpleAI.") from exc
    if execution.returncode == 5:
        raise OfflineProblemError("unsupported", "Tính năng này cần SimpleAI trong môi trường Python đang chạy.")
    if execution.returncode:
        raise OfflineProblemError("unsupported", "SimpleAI gặp lỗi khi chạy thuật toán tìm kiếm cục bộ.")
    try:
        return json.loads(execution.stdout)
    except ValueError as exc:
        raise OfflineProblemError("invalid", "SimpleAI trả về kết quả sai định dạng.") from exc


def _validate_board(n, result):
    from .offline_solver import OfflineProblemError

    board = result["board"]
    if board is None:
        if result["status"] == "found":
            raise OfflineProblemError("invalid", "SimpleAI báo có nghiệm nhưng thiếu cấu hình hậu.")
        return
    if len(board) != n or any(type(row) is not int or not 0 <= row < n for row in board):
        raise OfflineProblemError("invalid", "SimpleAI trả về cấu hình hậu không hợp lệ.")
    # Direct pairwise test independent of the count maps used by the fitness function.
    conflicts = sum(
        board[left] == board[right] or abs(board[left] - board[right]) == right - left
        for left in range(n) for right in range(left + 1, n)
    )
    fitness = n * (n - 1) // 2 - conflicts
    if (
        conflicts != result["attacking_pairs"] or fitness != result["fitness"]
        or (conflicts == 0) != (result["status"] == "found")
    ):
        raise OfflineProblemError("invalid", "Số cặp hậu tấn công không khớp với cấu hình SimpleAI trả về.")


def _simpleai_local_nqueens(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    algorithm = problem.get("algorithm", "hill_climbing_random_restarts")
    if not isinstance(algorithm, str) or algorithm not in _OPTIONS:
        raise OfflineProblemError("unsupported", "Thuật toán tìm kiếm cục bộ SimpleAI chưa được hỗ trợ.")
    _fields(problem, ("type", "n"), ("algorithm", "seed", "iterations_limit", *_OPTIONS[algorithm]))
    n = _integer(problem["n"], "n", 1, 25)
    seed = _integer(problem.get("seed", 42), "seed", 0, 2**32 - 1)
    default_iterations = {"simulated_annealing": 1000, "genetic": 200}.get(algorithm, 100)
    iterations = _integer(problem.get("iterations_limit", default_iterations), "iterations_limit", 1, 2_000)
    options = {}
    if "initial" in problem:
        options["initial"] = tuple(
            _integer(row, "Vị trí hậu", 0, n - 1) for row in _array(problem["initial"], "initial", n, n)
        )
    if algorithm == "hill_climbing_random_restarts":
        options["restarts_limit"] = _integer(problem.get("restarts_limit", 20), "restarts_limit", 1, 100)
    if algorithm in ("beam", "beam_best_first"):
        options["beam_size"] = _integer(problem.get("beam_size", 15), "beam_size", 1, 40)
    if algorithm == "genetic":
        options["population_size"] = _integer(problem.get("population_size", 60), "population_size", 2, 150)
        chance = problem.get("mutation_chance", 0.2)
        if type(chance) not in (int, float) or not 0 <= chance <= 1 or not math.isfinite(chance):
            raise OfflineProblemError("invalid", "mutation_chance cần là xác suất trong [0, 1].")
        options["mutation_chance"] = chance

    args = (n, algorithm, seed, iterations, options, _EVALUATION_LIMIT)
    result = _search_queens(*args) if n <= 3 else _isolated_search(args)
    _validate_board(n, result)
    status = result["status"]
    notes = ("Mỗi cột có một hậu. Chỉ số hàng bắt đầu từ 0. Fitness đếm các cặp hậu không tấn công nhau.",)
    metric = None
    if status == "found":
        summary = "Đã kiểm tra từng cặp hậu. Cấu hình hợp lệ."
        metric = ("satisfiable", True)
    elif status == "impossible_size":
        summary = f"Bài toán {n} hậu chuẩn vô nghiệm."
        metric = ("satisfiable", False)
    else:
        summary = "Tìm kiếm cục bộ chưa tìm thấy nghiệm trong số lượt cho phép."
        notes += ("Kết quả là cấu hình tốt nhất trong các cấu hình thuật toán đã chấp nhận.",)
    return OfflineSolution(
        "simpleai_local_nqueens",
        _standalone((_attacking_pairs, _search_queens), _search_queens, args, result),
        summary, notes, metric,
        validation_status="reference" if status == "not_found_within_budget" else "verified",
    )


SIMPLEAI_LOCAL_SOLVERS = {"simpleai_local_nqueens": _simpleai_local_nqueens}
