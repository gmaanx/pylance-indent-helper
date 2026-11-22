"""Pure Python class exercises with explicitly supported contracts."""

import inspect
import math


class Vector24:
    def __init__(self, components):
        values = tuple(components)
        if len(values) != 24:
            raise ValueError("Vector24 cần đúng 24 tọa độ.")
        if any(type(value) not in (int, float) for value in values):
            raise TypeError("Tọa độ phải là số thực.")
        if any(isinstance(value, float) and not math.isfinite(value) for value in values):
            raise ValueError("Tọa độ phải hữu hạn.")
        self.components = values

    def __add__(self, other):
        if not isinstance(other, Vector24):
            return NotImplemented
        return Vector24(a + b for a, b in zip(self.components, other.components))

    def tich_vo_huong(self, other):
        if not isinstance(other, Vector24):
            raise TypeError("Cần một Vector24 để tính tích vô hướng.")
        return sum(a * b for a, b in zip(self.components, other.components))

    def _don_vi(self):
        # Scale first so a norm or product of large coordinates stays finite.
        scale = max(map(abs, self.components))
        if scale == 0:
            raise ValueError("Góc với vector không chưa được xác định.")
        values = tuple(value / scale for value in self.components)
        norm = math.hypot(*values)
        return tuple(value / norm for value in values)

    def goc(self, other):
        if not isinstance(other, Vector24):
            raise TypeError("Cần một Vector24 để tính góc.")
        cosine = math.fsum(a * b for a, b in zip(self._don_vi(), other._don_vi()))
        return math.acos(max(-1.0, min(1.0, cosine)))


class Diem3D:
    def __init__(self, x, y, z):
        try:
            self.x, self.y, self.z = float(x), float(y), float(z)
        except OverflowError as exc:
            raise ValueError("Tọa độ vượt giới hạn của float.") from exc
        if not all(map(math.isfinite, (self.x, self.y, self.z))):
            raise ValueError("Tọa độ phải hữu hạn.")

    def khoang_cach_goc(self):
        return math.hypot(self.x, self.y, self.z)


def _geometry_solution(problem, klass, summary, notes):
    from .offline_solver import OfflineSolution, _fields

    _fields(problem, ("type",))
    code = "import math\n\n\n" + inspect.getsource(klass)
    return OfflineSolution(problem["type"], code, summary, notes)


def _vector24(problem):
    return _geometry_solution(
        problem, Vector24,
        "Lớp Vector24 hỗ trợ cộng, tích vô hướng và góc theo radian.",
        ("Khởi tạo bằng một dãy 24 số thực. Góc với vector không báo ValueError.",),
    )


def _diem3d(problem):
    return _geometry_solution(
        problem, Diem3D,
        "Lớp Diem3D chuyển tọa độ sang float và tính khoảng cách tới gốc.",
        ("Khoảng cách Euclid tính bằng math.hypot. Tọa độ cần hữu hạn.",),
    )


GEOMETRY_CLASS_SOLVERS = {"vector24": _vector24, "diem3d": _diem3d}
