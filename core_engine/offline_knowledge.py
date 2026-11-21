"""Finite frame inheritance with explicit conflicts and evidence paths."""

__all__ = ["KNOWLEDGE_SOLVERS"]


def _resolve_slots(frames, query, slots):
    from collections import deque

    paths = {query: (query,)}
    pending = deque([query])
    while pending:
        name = pending.popleft()
        for parent in frames[name][0]:
            if parent not in paths:
                paths[parent] = (*paths[name], parent)
                pending.append(parent)

    resolved = {}
    for slot in slots:
        definitions = [name for name in paths if slot in frames[name][1]]
        if not definitions:
            resolved[slot] = {"status": "unknown"}
            continue
        # More specific frames override their own ancestors. Unrelated frames
        # remain candidates even when their shortest paths have different lengths.
        overridden = set()
        for name in definitions:
            sources = list(frames[name][0])
            while sources:
                ancestor = sources.pop()
                if ancestor not in overridden:
                    overridden.add(ancestor)
                    sources.extend(frames[ancestor][0])
        items = [
            {"frame": name, "path": paths[name], "value": frames[name][1][slot]}
            for name in definitions if name not in overridden
        ]
        first = items[0]["value"]
        if all(type(item["value"]) is type(first) and item["value"] == first for item in items):
            resolved[slot] = {"status": "value", "value": first, "sources": items}
        else:
            resolved[slot] = {"status": "conflict", "sources": items}
    return resolved


def _frame(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _name, _standalone

    _fields(problem, ("type", "frames", "query", "slots"))
    raw = problem["frames"]
    if not isinstance(raw, dict) or not 1 <= len(raw) <= 200:
        raise OfflineProblemError("invalid", "frames cần từ 1 đến 200 khung.")
    frames = {}
    for raw_name, frame in raw.items():
        name = _name(raw_name, "Tên khung")
        _fields(frame, (), ("parents", "slots"))
        parents = tuple(dict.fromkeys(
            _name(parent, "Khung cha")
            for parent in _array(frame.get("parents", []), "parents", 0, 12)
        ))
        values = frame.get("slots", {})
        if not isinstance(values, dict) or len(values) > 40:
            raise OfflineProblemError("invalid", "Mỗi khung có tối đa 40 thuộc tính.")
        properties = {}
        for key, value in values.items():
            key = _name(key, "Thuộc tính")
            if not (
                value is None or type(value) is bool
                or (type(value) is int and abs(value) <= 10**12)
                or (isinstance(value, str) and len(value) <= 1000)
            ):
                raise OfflineProblemError("invalid", "Giá trị thuộc tính nhận chuỗi, số nguyên, boolean hoặc null.")
            properties[key] = value
        frames[name] = (parents, properties)
    if any(parent not in frames for parents, _ in frames.values() for parent in parents):
        raise OfflineProblemError("invalid", "Khung cha phải có trong frames.")

    active, complete = set(), set()

    def visit(name):
        if name in active:
            raise OfflineProblemError("invalid", "Phân cấp khung chứa chu trình.")
        if name not in complete:
            active.add(name)
            for parent in frames[name][0]:
                visit(parent)
            active.remove(name)
            complete.add(name)

    for name in frames:
        visit(name)
    query = _name(problem["query"], "Khung cần tìm")
    if query not in frames:
        raise OfflineProblemError("invalid", "Khung cần tìm chưa được khai báo.")
    slots = [_name(slot, "Thuộc tính cần tìm") for slot in _array(problem["slots"], "slots", 1, 40)]
    if len(slots) != len(set(slots)):
        raise OfflineProblemError("invalid", "Danh sách thuộc tính cần tìm bị trùng.")
    args = (frames, query, slots)
    result = _resolve_slots(*args)
    conflicts = sum(item["status"] == "conflict" for item in result.values())
    unknown = sum(item["status"] == "unknown" for item in result.values())
    return OfflineSolution(
        "frame_inheritance", _standalone((_resolve_slots,), _resolve_slots, args, result),
        f"Có {len(slots) - conflicts - unknown} thuộc tính xác định, {conflicts} mâu thuẫn và {unknown} chưa khai báo.",
        ("Khung cụ thể ghi đè thuộc tính của tổ tiên. Các nhánh độc lập bất đồng được giữ làm bằng chứng.",),
    )


KNOWLEDGE_SOLVERS = {"frame_inheritance": _frame}
