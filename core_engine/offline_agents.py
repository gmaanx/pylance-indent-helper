"""Shortest plan for a deterministic agent with uncertain initial state."""

__all__ = ["AGENT_SOLVERS"]


def _plan_vacuum(rooms, positions, initial_masks, dirty_goal, first, limit):
    from collections import deque

    work = 0

    def step(state, action):
        nonlocal work
        work += len(state)
        if work > 1_000_000:
            raise OverflowError("Vacuum belief transition budget exceeded")
        outcomes = set()
        for pos, mask in state:
            if action == "left":
                outcomes.add((max(pos - 1, 0), mask))
            elif action == "right":
                outcomes.add((min(pos + 1, rooms - 1), mask))
            else:
                outcomes.add((pos, mask & ~(1 << pos)))
        return tuple(sorted(outcomes))

    def describe(state):
        cells = lambda mask: [room for room in range(rooms) if mask & (1 << room)]
        pos = state[0][0]
        if all(pos == other for other, _ in state):
            return {"position": pos, "possible_dirty": [cells(mask) for _, mask in state]}
        return {"possible_states": [{"position": pos, "dirty": cells(mask)} for pos, mask in state]}

    start = tuple((pos, mask) for pos in positions for mask in initial_masks)
    initial = step(start, first) if first else start
    queue = deque([initial])
    parents = {initial: None}
    while queue:
        current = queue.popleft()
        if all(mask == dirty_goal for _, mask in current):
            actions = []
            while parents[current] is not None:
                previous, applied = parents[current]
                actions.append(applied)
                current = previous
            actions.reverse()
            if first:
                actions.insert(0, first)
            trace = [start]
            for action in actions:
                trace.append(step(trace[-1], action))
            return {
                "actions": actions,
                "trace": [describe(state) for state in trace],
            }
        for action in ("left", "right", "suck"):
            successor = step(current, action)
            if successor not in parents:
                if len(parents) >= limit:
                    raise OverflowError("Vacuum belief search budget exceeded")
                parents[successor] = (current, action)
                queue.append(successor)
    return None


def _vacuum(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "rooms", "position", "possible_dirty"), ("goal_dirty", "first_action"))
    rooms = _integer(problem["rooms"], "rooms", 1, 9)
    raw_position = problem["position"]
    positions = (
        tuple(sorted({_integer(value, "Vị trí", 0, rooms - 1) for value in _array(raw_position, "position", 1, rooms)}))
        if isinstance(raw_position, list) else (_integer(raw_position, "position", 0, rooms - 1),)
    )

    def mask(values):
        cells = [
            _integer(value, "Phòng bẩn", 0, rooms - 1)
            for value in _array(values, "Phòng bẩn", 0, rooms)
        ]
        if len(cells) != len(set(cells)):
            raise OfflineProblemError("invalid", "Mỗi cấu hình chỉ liệt kê mỗi phòng bẩn một lần.")
        return sum(1 << cell for cell in cells)

    masks = tuple(sorted({mask(cells) for cells in _array(problem["possible_dirty"], "possible_dirty", 1, 512)}))
    target = mask(problem.get("goal_dirty", []))
    first = problem.get("first_action")
    if first not in (None, "left", "right", "suck"):
        raise OfflineProblemError("unsupported", "first_action nhận left, right hoặc suck.")
    args = (rooms, positions, masks, target, first, 10_000)
    result = _plan_vacuum(*args)
    steps = len(result["actions"]) if result is not None else None
    summary = "Không có chuỗi hành động đảm bảo đạt đích." if steps is None else f"Số hành động ít nhất: {steps}."
    return OfflineSolution(
        "vacuum_plan", _standalone((_plan_vacuum,), _plan_vacuum, args, result),
        summary,
        ("BFS trên tập trạng thái có thể xảy ra. Phòng xếp theo hàng và mỗi thao tác hút làm sạch phòng hiện tại.",),
        ("minimum_actions", steps),
    )


AGENT_SOLVERS = {"vacuum_plan": _vacuum}
