"""Offline k-NN, categorical ID3, and finite-horizon MDP solvers."""

from fractions import Fraction


MAX_TRAIN_SAMPLES = 400
MAX_FEATURES = 32
MAX_MDP_STATES = 48
MAX_MDP_TRANSITIONS = 2_000
MAX_MDP_BACKUPS = 80_000


def _real(value, field, minimum, maximum):
    from .offline_solver import OfflineProblemError

    if type(value) not in (int, float) or not minimum <= value <= maximum:
        raise OfflineProblemError("invalid", f"{field} phải là số hữu hạn từ {minimum} đến {maximum}.")
    if (Fraction(str(value)) * 1_000_000).denominator != 1:
        raise OfflineProblemError("invalid", f"{field} hỗ trợ tối đa sáu chữ số sau dấu thập phân.")
    return value


def _read_classification_data(problem, feature):
    from .offline_solver import _array, _fields, _name

    raw_query = _array(problem["query"], "query", 1, MAX_FEATURES)
    query = tuple(feature(value) for value in raw_query)
    train = []
    for sample in _array(problem["train"], "train", 1, MAX_TRAIN_SAMPLES):
        _fields(sample, ("x", "label"))
        vector = _array(sample["x"], "x", len(query), len(query))
        train.append((tuple(feature(value) for value in vector), _name(sample["label"], "Nhãn")))
    return train, query


def _solve_knn(train, query, k, normalize):
    """Predict with an exact comparison of squared Euclidean distances."""
    from fractions import Fraction

    numeric_train = [(tuple(Fraction(str(value)) for value in vector), label) for vector, label in train]
    target = tuple(Fraction(str(value)) for value in query)
    scales = [1] * len(target)
    if normalize == "minmax":
        columns = zip(*(vector for vector, _ in numeric_train))
        scales = [max(column) - min(column) for column in columns]

    neighbors = []
    for index, (vector, label) in enumerate(numeric_train):
        distance = sum(
            ((value - expected) / scale) ** 2
            for value, expected, scale in zip(vector, target, scales) if scale != 0
        )
        neighbors.append((distance, index, label))
    neighbors = sorted(neighbors)[:k]

    votes = {}
    closest = {}
    for distance, _, label in neighbors:
        votes[label] = votes.get(label, 0) + 1
        closest.setdefault(label, distance)
    prediction = min(votes, key=lambda label: (-votes[label], closest[label], label))
    return {
        "prediction": prediction,
        "votes": votes,
        "neighbors": [
            {"index": index, "label": label, "distance_squared": float(distance)}
            for distance, index, label in neighbors
        ],
    }


def _knn(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _fields, _integer, _standalone

    _fields(problem, ("type", "train", "query", "k"), ("normalize",))
    normalize = problem.get("normalize", "none")
    if normalize not in ("none", "minmax"):
        raise OfflineProblemError("unsupported", "normalize chỉ hỗ trợ none hoặc minmax.")
    train, query = _read_classification_data(
        problem, lambda value: _real(value, "Giá trị đặc trưng", -1_000_000, 1_000_000),
    )
    args = (train, query, _integer(problem["k"], "k", 1, len(train)), normalize)
    result = _solve_knn(*args)
    return OfflineSolution(
        "knn", _standalone((_solve_knn,), _solve_knn, args, result),
        f"Nhãn dự đoán theo k-NN: {result['prediction']!r}.",
        (
            "Dùng khoảng cách Euclid. Khi bằng khoảng cách, ưu tiên thứ tự mẫu trong train. "
            "Khi hòa phiếu, ưu tiên nhãn có mẫu gần nhất, rồi theo thứ tự chữ.",
            "Min-max học khoảng giá trị từ train. Đặc trưng có cùng giá trị trong train đóng góp 0 vào khoảng cách.",
        ),
        ("prediction", result["prediction"]),
    )


def _solve_id3(train, query):
    """Build a categorical ID3 tree with deterministic feature and label ties."""
    from collections import Counter
    from fractions import Fraction

    def conditional_entropy_ratio(groups):
        # Multiplying entropy by sample count gives log2 of this ratio.
        # Comparing the ratios exactly preserves equal information gains.
        numerator = denominator = 1
        for group in groups.values():
            counts = Counter(label for _, label in group)
            count = len(group)
            numerator *= count ** count
            for frequency in counts.values():
                denominator *= frequency ** frequency
        return Fraction(numerator, denominator)

    def build(rows, features):
        counts = Counter(label for _, label in rows)
        majority = min(counts, key=lambda label: (-counts[label], label))
        node = {"prediction": majority}
        if len(counts) == 1 or not features:
            return node

        best = None
        for index in features:
            groups = {}
            for vector, label in rows:
                groups.setdefault(vector[index], []).append((vector, label))
            if len(groups) < 2:
                continue
            score = conditional_entropy_ratio(groups)
            if best is None or score < best[0]:
                best = score, index, groups
        if best is None:
            return node
        _, index, groups = best
        remaining = [feature for feature in features if feature != index]
        node["feature"] = index
        node["branches"] = {value: build(groups[value], remaining) for value in sorted(groups)}
        return node

    tree = build(train, list(range(len(query))))
    node = tree
    used_fallback = False
    path = []
    while "feature" in node:
        index = node["feature"]
        value = query[index]
        path.append((index, value))
        child = node["branches"].get(value)
        if child is None:
            used_fallback = True
            break
        node = child
    return {
        "prediction": node["prediction"], "used_fallback": used_fallback, "path": path, "tree": tree,
    }


def _id3(problem):
    from .offline_solver import OfflineSolution, _fields, _name, _standalone

    _fields(problem, ("type", "train", "query"))
    args = _read_classification_data(problem, lambda value: _name(value, "Đặc trưng phân loại"))
    result = _solve_id3(*args)
    summary = f"Nhãn dự đoán theo ID3: {result['prediction']!r}."
    if result["used_fallback"]:
        summary += " Gặp giá trị chưa thấy trong nhánh; dùng nhãn phổ biến tại nút."
    return OfflineSolution(
        "id3", _standalone((_solve_id3,), _solve_id3, args, result), summary,
        (
            "ID3 dùng information gain với thuộc tính phân loại. Chỉ số thuộc tính bắt đầu từ 0.",
            "Khi bằng độ lợi thông tin, chọn thuộc tính xuất hiện trước. Khi bằng số phiếu, lấy nhãn theo thứ tự chữ.",
        ),
        ("prediction", result["prediction"]),
    )


def _solve_mdp(states, discount, horizon):
    """Compute optimal finite-horizon values and policies with Bellman backups."""
    from fractions import Fraction

    transition_model = {
        state: {
            action: [
                (target, Fraction(str(probability)), Fraction(str(reward)))
                for target, probability, reward in outcomes if probability != 0
            ]
            for action, outcomes in actions.items()
        }
        for state, actions in states.items()
    }
    gamma = Fraction(str(discount))
    order = sorted(states)
    previous = {state: Fraction(0) for state in order}
    all_values = [{state: 0.0 for state in order}]
    all_policies = [{state: None for state in order}]

    for _ in range(horizon):
        values = {}
        policy = {}
        for state in order:
            best_value, best_action = Fraction(0), None
            for action, outcomes in sorted(transition_model[state].items()):
                value = sum(probability * (reward + gamma * previous[target])
                            for target, probability, reward in outcomes)
                if best_action is None or value > best_value:
                    best_value, best_action = value, action
            values[state] = best_value
            policy[state] = best_action
        all_values.append({state: float(value) for state, value in values.items()})
        all_policies.append(policy)
        previous = values

    return {
        "values": all_values[-1], "policy": all_policies[-1],
        "values_by_horizon": all_values, "policies_by_horizon": all_policies,
    }


def _mdp(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _name, _standalone

    _fields(problem, ("type", "states", "discount", "horizon"))
    raw_states = problem["states"]
    if not isinstance(raw_states, dict) or not 1 <= len(raw_states) <= MAX_MDP_STATES:
        raise OfflineProblemError("invalid", f"states phải khai báo từ 1 đến {MAX_MDP_STATES} trạng thái.")
    horizon = _integer(problem["horizon"], "horizon", 0, 60)
    discount = _real(problem["discount"], "discount", 0, 1)

    states = {}
    transition_count = 0
    for state, actions in raw_states.items():
        _name(state, "Trạng thái")
        if not isinstance(actions, dict) or len(actions) > 16:
            raise OfflineProblemError("invalid", "Mỗi trạng thái phải khai báo đối tượng có tối đa 16 hành động.")
        states[state] = {}
        for action, outcomes in actions.items():
            _name(action, "Hành động")
            outcomes = _array(outcomes, "Kết quả chuyển trạng thái", 1, 64)
            transition_count += len(outcomes)
            if transition_count > MAX_MDP_TRANSITIONS or horizon * transition_count > MAX_MDP_BACKUPS:
                raise OfflineProblemError("limit", "Mô hình vượt giới hạn số chuyển trạng thái hoặc lượt cập nhật.")
            validated = []
            total_probability = Fraction(0)
            for outcome in outcomes:
                _fields(outcome, ("to", "p", "reward"))
                target = _name(outcome["to"], "Trạng thái đích")
                if target not in raw_states:
                    raise OfflineProblemError("invalid", f"Chưa khai báo trạng thái đích {target!r}.")
                probability = _real(outcome["p"], "Xác suất", 0, 1)
                reward = _real(outcome["reward"], "Phần thưởng", -1_000_000, 1_000_000)
                total_probability += Fraction(str(probability))
                validated.append((target, probability, reward))
            if total_probability != 1:
                raise OfflineProblemError("invalid", f"Tổng xác suất cho {state!r}, hành động {action!r} phải bằng 1.")
            states[state][action] = validated

    args = (states, discount, horizon)
    result = _solve_mdp(*args)
    return OfflineSolution(
        "mdp", _standalone((_solve_mdp,), _solve_mdp, args, result),
        f"Tính xong giá trị và chính sách tối ưu khi còn {horizon} bước.",
        (
            "Bellman hữu hạn với V₀ = 0. Trạng thái có đối tượng hành động rỗng là trạng thái kết thúc.",
            "Các giá trị được hiển thị dạng số thập phân. Khi hòa giá trị, chọn tên hành động theo thứ tự chữ.",
        ),
    )


LEARNING_SOLVERS = {"knn": _knn, "id3": _id3, "mdp": _mdp}
