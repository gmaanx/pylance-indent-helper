"""Small Python exercises grounded in the introductory course material."""

__all__ = ["PYTHON_BASICS_SOLVERS"]


def _numeric(value):
    from math import isfinite
    from .offline_solver import OfflineProblemError

    if type(value) not in (int, float) or abs(value) > 10**12 or not isfinite(value):
        raise OfflineProblemError("invalid", "Dữ liệu cần là số hữu hạn với trị tuyệt đối không quá 10^12.")
    return value


def _sum_parity(values):
    even = sum(value for value in values if value % 2 == 0)
    odd = sum(value for value in values if value % 2 != 0)
    return {"even_sum": even, "odd_sum": odd}


def _parity(problem):
    from .offline_solver import OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "values"))
    values = [_integer(value, "Phần tử", -10**12, 10**12) for value in _array(problem["values"], "values", 0, 5000)]
    result = _sum_parity(values)
    return OfflineSolution(
        "parity_sum", _standalone((_sum_parity,), _sum_parity, (values,), result),
        f"Tổng chẵn {result['even_sum']}, tổng lẻ {result['odd_sum']}.",
        ("Chẵn lẻ được tính cả với số nguyên âm và 0.",),
    )


def _fibonacci_numbers(count, first, second):
    def fibonacci():
        a, b = first, second
        for _ in range(count):
            yield a
            a, b = b, a + b

    return list(fibonacci())


def _fibonacci(problem):
    from .offline_solver import OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "count"), ("initial",))
    count = _integer(problem["count"], "count", 0, 500)
    seeds = [_integer(value, "Số đầu", -10**12, 10**12) for value in _array(problem.get("initial", [0, 1]), "initial", 2, 2)]
    args = (count, *seeds)
    result = _fibonacci_numbers(*args)
    return OfflineSolution(
        "fibonacci", _standalone((_fibonacci_numbers,), _fibonacci_numbers, args, result),
        f"Tạo {count} phần tử Fibonacci.", ("Generator dùng đúng hai số đầu được khai báo.",),
        ("last_value", result[-1] if result else None),
    )


def _vector_measures(left, right):
    from math import acos, hypot

    dot = sum(a * b for a, b in zip(left, right))
    norm_left, norm_right = hypot(*left), hypot(*right)
    cosine = max(-1.0, min(1.0, dot / (norm_left * norm_right))) if norm_left and norm_right else None
    return {
        "sum": [a + b for a, b in zip(left, right)],
        "dot": dot,
        "norms": [norm_left, norm_right],
        "cosine": cosine,
        "angle_radians": acos(cosine) if cosine is not None else None,
    }


def _vector(problem):
    from .offline_solver import OfflineSolution, _array, _fields, _standalone

    _fields(problem, ("type", "left", "right"))
    left = [_numeric(value) for value in _array(problem["left"], "left", 1, 2048)]
    right = [_numeric(value) for value in _array(problem["right"], "right", len(left), len(left))]
    result = _vector_measures(left, right)
    note = "Góc và cosine không xác định nếu ít nhất một vector bằng 0."
    return OfflineSolution(
        "vector_metrics", _standalone((_vector_measures,), _vector_measures, (left, right), result),
        f"Tích vô hướng {result['dot']}.", (note,), ("dot", result["dot"]),
    )


def _text_cosine(left, right, alphabet, fold_accents, case_sensitive):
    from collections import Counter
    from unicodedata import category, normalize

    def vector(text):
        text = normalize("NFC", text)
        if fold_accents:
            text = normalize("NFD", text).translate(str.maketrans("đĐ", "dD"))
            text = "".join(character for character in text if category(character) != "Mn")
        if not case_sensitive:
            text = text.casefold()
        frequency = Counter(text)
        return [frequency[character] for character in alphabet]

    left_vector, right_vector = vector(left), vector(right)
    cosine = _vector_measures(left_vector, right_vector)["cosine"]
    return {"alphabet": alphabet, "left": left_vector, "right": right_vector, "cosine": cosine}


def _cosine(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _fields, _standalone

    _fields(problem, ("type", "left", "right"), ("alphabet", "fold_accents", "case_sensitive"))
    left, right = problem["left"], problem["right"]
    alphabet = problem.get("alphabet", "abcdefghijklmnopqrstuvwx")
    fold = problem.get("fold_accents", True)
    sensitive = problem.get("case_sensitive", False)
    if any(not isinstance(value, str) or len(value) > 20_000 for value in (left, right)):
        raise OfflineProblemError("invalid", "Mỗi văn bản cần là chuỗi dài tối đa 20.000 ký tự.")
    if not isinstance(alphabet, str) or not 1 <= len(alphabet) <= 128 or len(set(alphabet)) != len(alphabet):
        raise OfflineProblemError("invalid", "alphabet cần từ 1 đến 128 ký tự khác nhau.")
    if type(fold) is not bool or type(sensitive) is not bool:
        raise OfflineProblemError("invalid", "fold_accents và case_sensitive phải là boolean.")
    from unicodedata import category, normalize
    normalized = normalize("NFC", alphabet)
    if fold:
        normalized = "".join(ch for ch in normalize("NFD", normalized).translate(str.maketrans("đĐ", "dD")) if category(ch) != "Mn")
    if not sensitive:
        normalized = normalized.casefold()
    if alphabet != normalized:
        raise OfflineProblemError("invalid", "alphabet phải ở dạng đã chuẩn hóa theo tùy chọn khử dấu và hoa thường.")
    args = (left, right, alphabet, fold, sensitive)
    result = _text_cosine(*args)
    cosine = result["cosine"]
    summary = "Cosine không xác định vì có vector tần suất bằng 0." if cosine is None else f"Độ tương đồng cosine {cosine:.8g}."
    return OfflineSolution(
        "text_cosine", _standalone((_vector_measures, _text_cosine), _text_cosine, args, result),
        summary, ("Mỗi chiều đếm một ký tự trong alphabet. Mặc định dùng 24 chữ từ a đến x.",),
        ("cosine", cosine),
    )


PYTHON_BASICS_SOLVERS = {
    "parity_sum": _parity,
    "fibonacci": _fibonacci,
    "vector_metrics": _vector,
    "text_cosine": _cosine,
}
