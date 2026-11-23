"""Bounded solvers for explicitly supported search and constraint problems."""

import contextvars
import inspect
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Optional, Tuple

from .golden_skeletons import strip_accents
from .offline_input import read_known_format
from .runnable_output import extract_output_clause, render_main_output, validate_output_spec
from .sliding_puzzle import _puzzle_neighbors, _puzzle_parity, _solve_sliding_puzzle

_CURRENT_OUTPUT_SPEC: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "_CURRENT_OUTPUT_SPEC", default=None,
)
_DEFAULT_COLLECTION_FIELDS = {
    "_solve_simpleai_graph": "path",
    "_solve_simpleai_puzzle": "path",
    "_solve_search_trace": "path",
    "_grid_path": "path",
    "_hill_trace": "path",
    "_prefix_search": "path",
    "_plan_vacuum": "actions",
    "_join_relations": "rows",
}

MAX_STATES = 20_000
MAX_CSP_STEPS = 50_000
MAX_SPEC_LENGTH = 80_000
MAX_GRAPH_EDGES = 5_000
MAX_GRAPH_NODES = 2_000


class OfflineProblemError(ValueError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class OfflineSolution:
    problem_type: str
    code: str
    summary: str
    diagnostics: Tuple[str, ...]
    # Scalar answer for an independently computed check of a Cloud example.
    metric: Optional[Tuple[str, object]] = None
    validation_status: str = "verified"


def _reconstruct(parent, state):
    path = [state]
    while parent[state] is not None:
        state = parent[state]
        path.append(state)
    return path[::-1]


def _bfs(start, is_goal, neighbors, limit):
    queue = deque([start])
    parent = {start: None}
    while queue:
        state = queue.popleft()
        if is_goal(state):
            return _reconstruct(parent, state)
        for child in neighbors(state):
            if child in parent:
                continue
            if len(parent) == limit:
                raise OverflowError("Search state limit exceeded")
            parent[child] = state
            queue.append(child)
    return None


def _solve_water_jugs(capacities, start, goal, limit, max_pour=None, blocked=()):
    def is_goal(state):
        if isinstance(goal, int):
            return goal in state
        return all(target is None or amount == target for amount, target in zip(state, goal))

    transitions = 0

    def neighbors(state):
        nonlocal transitions
        for source, amount in enumerate(state):
            if amount == 0 or source in blocked:
                continue
            for target, capacity in enumerate(capacities):
                if source == target or target in blocked:
                    continue
                pour = min(amount, capacity - state[target])
                if pour == 0:
                    continue
                amounts = (pour,) if max_pour is None else range(1, min(pour, max_pour) + 1)
                for volume in amounts:
                    transitions += 1
                    if transitions > 2_000_000:
                        raise OverflowError("Pour transition limit exceeded")
                    child = list(state)
                    child[source] -= volume
                    child[target] += volume
                    yield tuple(child)

    return _bfs(start, is_goal, neighbors, limit)


def _solve_coin_change(amount, denominations, limit):
    def neighbors(current):
        for coin in denominations:
            if current + coin <= amount:
                yield current + coin

    path = _bfs(0, lambda current: current == amount, neighbors, limit)
    if path is None:
        return None
    return [right - left for left, right in zip(path, path[1:])]


def _solve_bounded_coins(amount, stock, step_limit):
    # Split a denomination's stock into 0/1 groups that cover every quantity
    # from zero to that stock count.
    best = {0: (0, ())}
    steps = 0
    for coin, available in stock:
        remaining = min(available, amount // coin)
        group = 1
        while remaining:
            count = min(group, remaining)
            weight = count * coin
            # Snapshot this layer so no group can be used more than once.
            for subtotal, (used, plan) in tuple(best.items()):
                steps += 1
                if steps > step_limit:
                    raise OverflowError("Bounded coin DP limit exceeded")
                total = subtotal + weight
                current = best.get(total)
                if total <= amount and (current is None or used + count < current[0]):
                    best[total] = (used + count, (*plan, (coin, count)))
            remaining -= count
            group *= 2
    if amount not in best:
        return None
    return [coin for coin, count in best[amount][1] for _ in range(count)]


def _bellman_ford(start, goal, edges):
    # Only cycles from which the target is reachable affect this query.
    reverse = defaultdict(list)
    for source, target, _ in edges:
        reverse[target].append(source)
    relevant = {goal}
    queue = deque([goal])
    while queue:
        for predecessor in reverse[queue.popleft()]:
            if predecessor not in relevant:
                relevant.add(predecessor)
                queue.append(predecessor)
    if start not in relevant:
        return None

    arcs = [(source, target, weight) for source, target, weight in edges if source in relevant and target in relevant]
    costs = {start: 0}
    parent = {start: None}
    for _ in range(len(relevant) - 1):
        changed = False
        for source, target, weight in arcs:
            if source in costs:
                candidate = costs[source] + weight
                if target not in costs or candidate < costs[target]:
                    costs[target] = candidate
                    parent[target] = source
                    changed = True
        if not changed:
            break
    for source, target, weight in arcs:
        if source in costs and (target not in costs or costs[source] + weight < costs[target]):
            return {"status": "unbounded"}
    return costs[goal], _reconstruct(parent, goal)


def _solve_graph(start, goal, edges, algorithm, directed):
    if algorithm == "bellman_ford":
        if not directed:
            edges = edges + [(target, source, weight) for source, target, weight in edges]
        return _bellman_ford(start, goal, edges)

    graph = defaultdict(list)
    for source, target, cost in edges:
        graph[source].append((target, cost))
        if not directed:
            graph[target].append((source, cost))

    if algorithm == "bfs":
        path = _bfs(
            start,
            lambda node: node == goal,
            lambda node: (target for target, _ in graph[node]),
            len({start, goal} | {node for edge in edges for node in edge[:2]}),
        )
        return None if path is None else (len(path) - 1, path)

    queue = [(0, start)]
    costs = {start: 0}
    parent = {start: None}
    while queue:
        cost, node = heappop(queue)
        if cost != costs[node]:
            continue
        if node == goal:
            return cost, _reconstruct(parent, node)
        for target, weight in graph[node]:
            new_cost = cost + weight
            if target not in costs or new_cost < costs[target]:
                costs[target] = new_cost
                parent[target] = node
                heappush(queue, (new_cost, target))
    return None


def _check_csp_constraint(values, op, constant):
    if op == "all_different":
        return len(values) == len(set(values))
    if op == "sum_eq":
        return sum(values) == constant
    left, right = values
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "lt":
        return left < right
    return left <= right


def _solve_csp(domains, constraints, step_limit):
    variables = sorted(domains, key=lambda name: (len(domains[name]), name))
    incident = defaultdict(list)
    for constraint in constraints:
        for name in constraint[1]:
            incident[name].append(constraint)
    assignment = {}
    steps = 0

    def backtrack(index):
        nonlocal steps
        if index == len(variables):
            return dict(assignment)
        variable = variables[index]
        for value in domains[variable]:
            steps += 1
            if steps > step_limit:
                raise OverflowError("CSP assignment limit exceeded")
            assignment[variable] = value
            for op, names, constant in incident[variable]:
                known_values = [assignment[name] for name in names if name in assignment]
                if op == "all_different" or len(known_values) == len(names):
                    if not _check_csp_constraint(known_values, op, constant):
                        break
            else:
                result = backtrack(index + 1)
                if result is not None:
                    return result
            del assignment[variable]
        return None

    return backtrack(0)


def _no_duplicate_keys(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise OfflineProblemError("invalid", f"Trường JSON lặp lại: {key}")
        values[key] = value
    return values


def _integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise OfflineProblemError("invalid", f"{name} phải là số nguyên từ {minimum} đến {maximum}.")
    return value


def _array(value, name, minimum, maximum):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise OfflineProblemError("invalid", f"{name} phải là danh sách có {minimum}–{maximum} phần tử.")
    return value


def _fields(problem, required, optional=()):
    if not isinstance(problem, dict):
        raise OfflineProblemError("invalid", "Đặc tả bài toán phải là đối tượng JSON.")
    missing = set(required) - problem.keys()
    extra = problem.keys() - set(required) - set(optional)
    if missing:
        raise OfflineProblemError("needs_input", "Thiếu trường " + ", ".join(sorted(missing)) + ".")
    if extra:
        raise OfflineProblemError("unsupported", "Chưa hỗ trợ trường " + ", ".join(sorted(extra)) + ".")


_NUMBER_LIST = r"\(\s*(?P<{name}>[0-9]{{1,5}}(?:\s*,\s*[0-9]{{1,5}})+)\s*\)"
_JUGS_PATTERN = re.compile(
    r"(?:(?:cho|giai)\s+)?(?:bai toan\s+)?dong nuoc"
    r"(?:\s+bang\s+(?P<algorithm>bfs))?"
    r"(?:\s+voi)?(?:\s+(?P<count>\d{1,2})\s+binh)?"
    r"(?:[.\s,:]+(?:co\s+)?dung tich(?:\s+cac binh)?\s*:?)?\s*"
    + _NUMBER_LIST.format(name="capacities")
    + r"[.\s,;]+(?:trang thai )?(?:ban dau|dau)\s*:?\s*"
    + _NUMBER_LIST.format(name="start")
    + r"[.\s,;]+(?:muc tieu|dich)\s*:?\s*"
    r"(?:(?:can )?dong duoc |co mot binh chua )?(?P<goal>[0-9]{1,5})\s*lit"
    r"(?:[.\s,;]+moi buoc (?:chi )?(?:chuyen|rot) toi da (?P<max_pour>[0-9]{1,5})\s*lit)?[.\s]*"
)
_COINS_PATTERN = re.compile(
    r"(?:(?:cho|giai)\s+)?(?:bai toan\s+)?doi tien"
    r"(?:\s+bang\s+(?P<algorithm>bfs))?\s*:?\s*"
    r"(?:so tien\s+)?(?P<amount>[0-9]{1,6})"
    r"(?:\s+voi|[.\s,;]+)\s*menh gia\s*:?\s*"
    r"(?P<denominations>[0-9]{1,6}(?:\s*(?:,|va)\s*[0-9]{1,6})*)"
    r"(?:[.\s,;]+(?:dung|tim|can)\s+(?:so\s+)?(?:dong\s+)?(?:xu\s+)?it nhat)?[.\s]*"
)
_COINS_SENTENCE_PATTERN = re.compile(
    r"(?:(?:cho|giai)\s+)?(?:bai toan\s+)?doi tien"
    r"(?:\s+bang\s+(?:tim kiem|(?P<algorithm>bfs)))?[.\s:]+"
    r"doi\s+(?P<amount>[0-9]{1,6})\s+dong[,\s]+"
    r"chi duoc dung (?:cac )?menh gia\s*:?\s*"
    r"(?P<denominations>[0-9]{1,6}(?:\s*(?:,|va)\s*[0-9]{1,6})*)[.\s]*"
)


def _parse_decimal_list(text, name):
    if not re.fullmatch(r"[0-9]{1,5}(?:,[0-9]{1,5})*", text):
        raise OfflineProblemError("invalid", f"{name} phải là danh sách số nguyên ngăn bằng dấu phẩy.")
    return [int(value) for value in text.split(",")]


def _jug_dsl(prompt):
    first, *lines = prompt.splitlines()
    if any(line.strip() for line in lines):
        raise OfflineProblemError("unsupported", "DSL chỉ nhận một dòng. Dùng @solve để khai báo đầy đủ.")
    command, *tokens = first.split()
    if command.casefold() not in ("@search", "@s"):
        raise OfflineProblemError("unsupported", "Dùng @search hoặc @solve cho bài đong nước.")
    params = {}
    positional = iter(("bai", "thuat_toan"))
    for token in tokens:
        if ":" in token:
            name, value = token.split(":", 1)
        else:
            name, value = next(positional, ""), token
        name = name.casefold()
        if name in params:
            raise OfflineProblemError("invalid", f"Trường DSL lặp lại: {name}.")
        if name not in ("bai", "thuat_toan", "binh", "dau", "dich") or not value:
            raise OfflineProblemError("unsupported", "Có tham số DSL chưa hỗ trợ. Dùng @solve để khai báo dữ liệu.")
        params[name] = value
    _fields(params, ("bai", "binh", "dau", "dich"), ("thuat_toan",))
    goals = _parse_decimal_list(params["dich"], "dich")
    return {
        "type": "water_jugs",
        "capacities": _parse_decimal_list(params["binh"], "binh"),
        "start": _parse_decimal_list(params["dau"], "dau"),
        "goal": goals[0] if len(goals) == 1 else goals,
        "algorithm": params.get("thuat_toan", "bfs").casefold(),
    }


def _read_natural_problem(prompt):
    try:
        problem = read_known_format(prompt)
    except (ValueError, RecursionError) as exc:
        raise OfflineProblemError("invalid", str(exc)) from exc
    if problem is not None:
        return problem

    normalized = re.sub(r"\s+", " ", strip_accents(prompt).casefold()).strip()
    if "dong nuoc" in normalized:
        match = _JUGS_PATTERN.fullmatch(normalized)
        if match is None:
            return None
        capacities = [int(value) for value in match["capacities"].split(",")]
        if match["count"] and int(match["count"]) != len(capacities):
            raise OfflineProblemError("invalid", "Số bình không khớp với danh sách dung tích.")
        problem = {
            "type": "water_jugs",
            "capacities": capacities,
            "start": [int(value) for value in match["start"].split(",")],
            "goal": int(match["goal"]),
            "algorithm": match["algorithm"] or "bfs",
        }
        if match["max_pour"]:
            problem["max_pour"] = int(match["max_pour"])
        return problem
    if "doi tien" in normalized:
        match = _COINS_PATTERN.fullmatch(normalized) or _COINS_SENTENCE_PATTERN.fullmatch(normalized)
        if match is None:
            return None
        return {
            "type": "coin_change",
            "amount": int(match["amount"]),
            "denominations": [int(value) for value in re.findall(r"[0-9]+", match["denominations"])],
            "algorithm": match["algorithm"] or "bfs",
        }
    return None


def _read_problem(prompt, target_skeleton_id):
    if re.match(r"^@solve\b", prompt, re.IGNORECASE):
        source = prompt[len("@solve"):].strip()
        if source.startswith("```") and source.endswith("```"):
            source = source[3:-3].strip()
            if source.lower().startswith("json"):
                source = source[4:].lstrip()
        if len(source) > MAX_SPEC_LENGTH:
            raise OfflineProblemError("limit", "Đặc tả JSON vượt giới hạn kích thước.")
        try:
            return json.loads(source, object_pairs_hook=_no_duplicate_keys)
        except (json.JSONDecodeError, RecursionError) as exc:
            location = getattr(exc, "lineno", None)
            column = getattr(exc, "colno", None)
            raise OfflineProblemError(
                "invalid",
                f"JSON của @solve chưa hợp lệ tại dòng {location or 1}, cột {column or 1}. "
                "Ví dụ: # @solve {\"type\":\"diem3d\"}.",
            ) from exc
        except ValueError as exc:
            if isinstance(exc, OfflineProblemError):
                raise
            raise OfflineProblemError("invalid", "Giá trị số trong đặc tả JSON không hợp lệ.") from exc

    if target_skeleton_id == "search_water_jugs":
        return _jug_dsl(prompt)

    problem = _read_natural_problem(prompt)
    if problem is not None:
        return problem

    # Check if the prompt is a recognized offline problem followed by a printing format clause.
    core_prompt, output_spec = extract_output_clause(prompt)
    if output_spec is not None and core_prompt != prompt:
        problem = _read_natural_problem(core_prompt)
        if problem is not None:
            return {**problem, "output": output_spec}

    normalized = re.sub(r"\s+", " ", strip_accents(prompt).casefold()).strip()
    geometry_names = re.search(r"\blop\s+(vector24|diem3d)\b", normalized)
    if geometry_names:
        class_type = geometry_names.group(1)
        raise OfflineProblemError(
            "needs_input",
            "Offline chưa xác nhận được toàn bộ yêu cầu cho lớp này. "
            f'Để lấy phiên bản cơ bản, dùng @solve {{"type":"{class_type}"}}.',
        )
    if "dong nuoc" in normalized:
        raise OfflineProblemError(
            "needs_input",
            'Cần xác định rõ dung tích, trạng thái đầu, đích và phép rót. '
            'Dùng @solve với type "water_jugs" để khai báo dữ liệu đầy đủ.',
        )
    if "doi tien" in normalized:
        raise OfflineProblemError(
            "needs_input",
            'Cần xác định rõ số tiền, mệnh giá và mục tiêu. '
            'Dùng @solve với type "coin_change" cho bài đổi tiền ít đồng nhất.',
        )
    return None


def _standalone(functions, function, arguments, result):
    sources = "\n\n".join(inspect.getsource(fn).rstrip() for fn in functions)
    call = function.__name__ + "(" + ", ".join(repr(arg) for arg in arguments) + ")"
    output_spec = _CURRENT_OUTPUT_SPEC.get()
    default_field = _DEFAULT_COLLECTION_FIELDS.get(function.__name__)
    if function.__name__ == "_solve_primes" and arguments and not arguments[0]:
        default_field = "first"
    extra_imports, main_body = render_main_output(
        call, output_spec, default_collection_field=default_field,
    )
    expected = repr(result)
    expected_line = f"# Kết quả dự kiến: {expected}\n" if not output_spec and len(expected) <= 400 else ""
    return (
        f"{extra_imports}"
        "from collections import defaultdict, deque\n"
        "from heapq import heappop, heappush\n\n\n"
        f"{sources}\n\n\n"
        'if __name__ == "__main__":\n'
        f"{main_body}"
        f"{expected_line}"
    )


def _water_jugs(problem):
    _fields(problem, ("type", "capacities", "start", "goal"), ("algorithm", "max_pour", "blocked_jugs"))
    if problem.get("algorithm", "bfs") != "bfs":
        raise OfflineProblemError("unsupported", "Bộ giải đong nước hỗ trợ BFS với mỗi lần rót tính một bước.")
    capacities = tuple(
        _integer(value, "Dung tích", 1, 10_000)
        for value in _array(problem["capacities"], "capacities", 2, 8)
    )
    start = tuple(
        _integer(amount, "Nước ban đầu", 0, capacity)
        for amount, capacity in zip(_array(problem["start"], "start", len(capacities), len(capacities)), capacities)
    )
    goal = problem["goal"]
    if isinstance(goal, list):
        goal = tuple(
            None if value is None else _integer(value, "Đích", 0, capacity)
            for value, capacity in zip(_array(goal, "goal", len(capacities), len(capacities)), capacities)
        )
    else:
        goal = _integer(goal, "Đích", 0, max(capacities))
    max_pour = _integer(problem["max_pour"], "max_pour", 1, 10_000) if "max_pour" in problem else None
    blocked = tuple(
        _integer(index, "Chỉ số bình bị cấm", 0, len(capacities) - 1)
        for index in _array(problem.get("blocked_jugs", []), "blocked_jugs", 0, len(capacities))
    )
    if len(set(blocked)) != len(blocked):
        raise OfflineProblemError("invalid", "blocked_jugs chứa chỉ số lặp.")
    args = (capacities, start, goal, MAX_STATES, max_pour, blocked)
    result = _solve_water_jugs(*args)
    summary = "Không có lời giải." if result is None else f"Số lần rót tối thiểu: {len(result) - 1}."
    rule = (
        "BFS, chỉ rót giữa các bình tới khi bình nguồn cạn hoặc bình đích đầy."
        if max_pour is None else f"BFS, mỗi lần được chọn rót từ 1 đến {max_pour} lít giữa hai bình."
    )
    if blocked:
        rule += f" Không dùng các bình có chỉ số {blocked} (từ 0)."
    return OfflineSolution(
        "water_jugs",
        _standalone((_reconstruct, _bfs, _solve_water_jugs), _solve_water_jugs, args, result),
        summary,
        (rule,),
        ("minimum_pours", None if result is None else len(result) - 1),
    )


def _coin_change(problem):
    _fields(problem, ("type", "amount", "denominations"), ("algorithm", "inventory"))
    amount = _integer(problem["amount"], "amount", 0, 100_000)
    supplied = [
        _integer(coin, "Mệnh giá", 1, 100_000)
        for coin in _array(problem["denominations"], "denominations", 1, 40)
    ]
    if "inventory" in problem:
        if problem.get("algorithm", "dp") != "dp":
            raise OfflineProblemError("unsupported", "Đổi tiền có giới hạn dùng algorithm='dp'.")
        if len(supplied) != len(set(supplied)):
            raise OfflineProblemError("invalid", "Mỗi mệnh giá chỉ xuất hiện một lần khi có inventory.")
        counts = _array(problem["inventory"], "inventory", len(supplied), len(supplied))
        stock = sorted((coin, _integer(count, "Số đồng có sẵn", 0, 100_000)) for coin, count in zip(supplied, counts))
        args = (amount, stock, 2_000_000)
        result = _solve_bounded_coins(*args)
        code = _standalone((_solve_bounded_coins,), _solve_bounded_coins, args, result)
        rule = "Quy hoạch động tìm số đồng ít nhất và giữ giới hạn của từng mệnh giá."
    else:
        if problem.get("algorithm", "bfs") != "bfs":
            raise OfflineProblemError("unsupported", "Đổi tiền không giới hạn dùng algorithm='bfs'.")
        args = (amount, tuple(sorted(set(supplied))), MAX_STATES)
        result = _solve_coin_change(*args)
        code = _standalone((_reconstruct, _bfs, _solve_coin_change), _solve_coin_change, args, result)
        rule = "BFS với số lượng không giới hạn cho mỗi mệnh giá."
    summary = "Không đổi được đúng số tiền." if result is None else f"Số đồng tối thiểu: {len(result)}."
    return OfflineSolution(
        "coin_change", code, summary, (rule,),
        ("minimum_coins", None if result is None else len(result)),
    )


def _name(value, field):
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise OfflineProblemError("invalid", f"{field} phải là chuỗi có 1–100 ký tự.")
    return value


def _graph(problem):
    _fields(problem, ("type", "algorithm", "start", "goal", "edges"), ("directed",))
    algorithm = problem["algorithm"]
    if algorithm not in ("bfs", "ucs", "bellman_ford"):
        raise OfflineProblemError("unsupported", "Bộ giải đồ thị hỗ trợ bfs, ucs và bellman_ford.")
    directed = problem.get("directed", True)
    if type(directed) is not bool:
        raise OfflineProblemError("invalid", "directed phải là true hoặc false.")
    start = _name(problem["start"], "start")
    goal = _name(problem["goal"], "goal")
    arity = 2 if algorithm == "bfs" else 3
    edges = []
    nodes = {start, goal}
    for edge in _array(problem["edges"], "edges", 0, MAX_GRAPH_EDGES):
        edge = _array(edge, "Cạnh", arity, arity)
        source, target = (_name(node, "Nút") for node in edge[:2])
        minimum_weight = -1_000_000 if algorithm == "bellman_ford" else 0
        weight = 1 if algorithm == "bfs" else _integer(edge[2], "Chi phí", minimum_weight, 1_000_000)
        edges.append((source, target, weight))
        nodes.update((source, target))
    if len(nodes) > MAX_GRAPH_NODES:
        raise OfflineProblemError("limit", f"Đồ thị vượt giới hạn {MAX_GRAPH_NODES} nút.")
    args = (start, goal, edges, algorithm, directed)
    result = _solve_graph(*args)
    if isinstance(result, dict):
        summary = "Chi phí không có cận dưới vì có chu trình âm trên đường tới đích."
        metric = "unbounded"
    elif result is None:
        summary = "Không có đường đi."
        metric = None
    else:
        metric = result[0]
        summary = f"Chi phí tối ưu: {metric}."
    return OfflineSolution(
        "graph",
        _standalone((_reconstruct, _bfs, _bellman_ford, _solve_graph), _solve_graph, args, result),
        summary,
        ("BFS đếm cạnh. UCS dùng trọng số không âm. Bellman–Ford xử lý trọng số âm và chu trình âm ảnh hưởng đến đích.",),
        ("minimum_cost", metric),
    )


def _csp(problem):
    _fields(problem, ("type", "domains", "constraints"))
    raw_domains = problem["domains"]
    if not isinstance(raw_domains, dict) or not 1 <= len(raw_domains) <= 24:
        raise OfflineProblemError("invalid", "domains phải khai báo từ 1 đến 24 biến.")
    domains = {
        _name(name, "Tên biến"): tuple(dict.fromkeys(
            _integer(value, "Giá trị miền", -10_000, 10_000)
            for value in _array(raw, "Miền", 1, 40)
        ))
        for name, raw in raw_domains.items()
    }
    constraints = []
    for constraint in _array(problem["constraints"], "constraints", 0, 100):
        _fields(constraint, ("op", "vars"), ("value",))
        op = constraint["op"]
        if op not in ("eq", "ne", "lt", "le", "all_different", "sum_eq"):
            raise OfflineProblemError("unsupported", "CSP hỗ trợ eq, ne, lt, le, all_different và sum_eq.")
        max_arity = len(domains) if op in ("all_different", "sum_eq") else 2
        names = tuple(
            _name(name, "Biến ràng buộc")
            for name in _array(constraint["vars"], "vars", 2, max_arity)
        )
        if len(set(names)) != len(names) or any(name not in domains for name in names):
            raise OfflineProblemError("invalid", "vars phải gồm các biến khác nhau đã khai báo trong domains.")
        constant = None
        if op == "sum_eq":
            _fields(constraint, ("op", "vars", "value"))
            constant = _integer(constraint["value"], "value", -240_000, 240_000)
        elif "value" in constraint:
            raise OfflineProblemError("unsupported", "Chỉ ràng buộc sum_eq nhận trường value.")
        constraints.append((op, names, constant))
    args = (domains, constraints, MAX_CSP_STEPS)
    result = _solve_csp(*args)
    summary = "Không có nghiệm." if result is None else "Tìm được một gán thỏa mọi ràng buộc."
    return OfflineSolution(
        "csp",
        _standalone((_check_csp_constraint, _solve_csp), _solve_csp, args, result),
        summary,
        ("Backtracking tìm một nghiệm với miền số nguyên hữu hạn.",),
        ("satisfiable", result is not None),
    )


def _sliding_puzzle(problem):
    _fields(problem, ("type", "start", "goal"), ("algorithm",))
    if problem.get("algorithm", "astar") != "astar":
        raise OfflineProblemError("unsupported", "Bộ giải 8-puzzle hỗ trợ A* với khoảng cách Manhattan.")

    boards = []
    for field in ("start", "goal"):
        board = tuple(_integer(tile, field, 0, 8) for tile in _array(problem[field], field, 9, 9))
        if len(set(board)) != 9:
            raise OfflineProblemError("invalid", f"{field} phải chứa đủ các số từ 0 đến 8, mỗi số đúng một lần.")
        boards.append(board)

    result = _solve_sliding_puzzle(*boards)
    summary = (
        "Không thể đi tới cấu hình đích."
        if result is None else f"Số bước trượt tối thiểu: {len(result) - 1}."
    )
    code = _standalone((_puzzle_parity, _puzzle_neighbors, _solve_sliding_puzzle), _solve_sliding_puzzle, boards, result)
    return OfflineSolution(
        "sliding_puzzle", code, summary,
        ("A* với khoảng cách Manhattan. Giá trị 0 đại diện cho ô trống.",),
        ("minimum_moves", None if result is None else len(result) - 1),
    )


def solve_offline(prompt: str, target_skeleton_id: Optional[str]) -> Optional[OfflineSolution]:
    problem = _read_problem(prompt, target_skeleton_id)
    if problem is None and not re.match(r"^@solve\b", prompt, re.IGNORECASE):
        return None
    return solve_spec(problem)


def solve_spec(problem: object) -> OfflineSolution:
    from .offline_agents import AGENT_SOLVERS
    from .offline_combinatorial import COMBINATORIAL_SOLVERS
    from .offline_course_csp import COURSE_CSP_SOLVERS
    from .offline_course_logic import COURSE_LOGIC_SOLVERS
    from .offline_course_search import COURSE_SEARCH_SOLVERS
    from .offline_geometry_classes import GEOMETRY_CLASS_SOLVERS
    from .offline_knowledge import KNOWLEDGE_SOLVERS
    from .offline_learning import LEARNING_SOLVERS
    from .offline_local_search import LOCAL_SEARCH_SOLVERS
    from .offline_logic import LOGIC_SOLVERS
    from .offline_optimization import OPTIMIZATION_SOLVERS
    from .offline_python_basics import PYTHON_BASICS_SOLVERS
    from .offline_search import SEARCH_SOLVERS
    from .offline_simpleai_csp import SIMPLEAI_CSP_SOLVERS
    from .offline_simpleai_local import SIMPLEAI_LOCAL_SOLVERS
    from .offline_simpleai_search import SIMPLEAI_SEARCH_SOLVERS
    from .offline_uncertainty import UNCERTAINTY_SOLVERS

    if not isinstance(problem, dict):
        raise OfflineProblemError("invalid", "@solve nhận một đối tượng JSON.")
    if "type" not in problem:
        raise OfflineProblemError("needs_input", "Thiếu trường type trong đặc tả.")
    problem_type = problem["type"]
    solvers = {
        "water_jugs": _water_jugs, "coin_change": _coin_change,
        "graph": _graph, "csp": _csp, "sliding_puzzle": _sliding_puzzle,
        **LOGIC_SOLVERS, **OPTIMIZATION_SOLVERS, **SEARCH_SOLVERS,
        **COMBINATORIAL_SOLVERS, **LEARNING_SOLVERS,
        **AGENT_SOLVERS, **COURSE_CSP_SOLVERS, **COURSE_LOGIC_SOLVERS,
        **COURSE_SEARCH_SOLVERS, **KNOWLEDGE_SOLVERS, **PYTHON_BASICS_SOLVERS,
        **GEOMETRY_CLASS_SOLVERS,
        **UNCERTAINTY_SOLVERS, **LOCAL_SEARCH_SOLVERS,
        **SIMPLEAI_CSP_SOLVERS, **SIMPLEAI_SEARCH_SOLVERS, **SIMPLEAI_LOCAL_SOLVERS,
    }
    if not isinstance(problem_type, str) or problem_type not in solvers:
        raise OfflineProblemError("unsupported", "type cần là một trong các dạng: " + ", ".join(sorted(solvers)) + ".")
    output_spec = validate_output_spec(problem.get("output")) if "output" in problem else None
    clean_problem = {k: v for k, v in problem.items() if k != "output"} if "output" in problem else problem
    token = _CURRENT_OUTPUT_SPEC.set(output_spec)
    try:
        return solvers[problem_type](clean_problem)
    except OverflowError as exc:
        raise OfflineProblemError("limit", "Đã chạm giới hạn tìm kiếm. Chưa thể kết luận có nghiệm hay vô nghiệm.") from exc
    finally:
        _CURRENT_OUTPUT_SPEC.reset(token)
