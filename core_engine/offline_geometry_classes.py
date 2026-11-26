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


class NutTimKiem:
    def __init__(self, state, parent=None, action=None, g=0.0, h=0.0):
        self.state = state
        self.parent = parent
        self.action = action
        self.g = float(g)
        self.h = float(h)

    def f_cost(self):
        return self.g + self.h

    def truy_vet_duong_di(self):
        duong_di = []
        hien_tai = self
        while hien_tai is not None:
            duong_di.append(hien_tai.state)
            hien_tai = hien_tai.parent
        return duong_di[::-1]


def _real_coord(value, label):
    from .offline_solver import OfflineProblemError

    if type(value) not in (int, float) or not math.isfinite(value):
        raise OfflineProblemError("invalid", f"{label} phải là số thực hữu hạn.")
    return value


def _geometry_solution(problem, klass, example, summary, notes, extra_imports=""):
    from .offline_solver import OfflineSolution

    code = (
        f"{extra_imports}"
        "import math\n\n\n"
        + inspect.getsource(klass).rstrip()
        + '\n\n\nif __name__ == "__main__":\n'
        + example
    )
    return OfflineSolution(problem["type"], code, summary, notes)


def _vector24(problem):
    from .offline_solver import _CURRENT_OUTPUT_SPEC, _array, _fields
    from .runnable_output import render_main_output

    _fields(problem, ("type",), ("sample",))
    if "sample" in problem:
        pair = _array(problem["sample"], "sample", 2, 2)
        left_vals = [_real_coord(v, "Tọa độ vector") for v in _array(pair[0], "sample[0]", 24, 24)]
        right_vals = [_real_coord(v, "Tọa độ vector") for v in _array(pair[1], "sample[1]", 24, 24)]
        setup = (
            f"    left = Vector24({left_vals!r})\n"
            f"    right = Vector24({right_vals!r})\n"
        )
    else:
        setup = (
            "    left = Vector24([1, 2] + [0] * 22)\n"
            "    right = Vector24([3, 4] + [0] * 22)\n"
        )

    output_spec = _CURRENT_OUTPUT_SPEC.get()
    if output_spec:
        result_expr = (
            '{"sum": list((left + right).components), '
            '"dot": left.tich_vo_huong(right), '
            '"angle_radians": left.goc(right)}'
        )
        extra_imports, body = render_main_output(result_expr, output_spec)
        example = setup + body
    else:
        extra_imports = ""
        example = (
            setup
            + "    print((left + right).components)\n"
            + "    print(left.tich_vo_huong(right))\n"
            + "    print(left.goc(right))\n"
        )
    return _geometry_solution(
        problem, Vector24, example,
        "Lớp Vector24 hỗ trợ cộng, tích vô hướng và góc theo radian.",
        ("Khởi tạo bằng một dãy 24 số thực. Góc với vector không báo ValueError.",),
        extra_imports=extra_imports,
    )


def _diem3d(problem):
    from .offline_solver import _CURRENT_OUTPUT_SPEC, _array, _fields
    from .runnable_output import render_main_output

    _fields(problem, ("type",), ("sample",))
    if "sample" in problem:
        coords = [_real_coord(v, "Tọa độ điểm") for v in _array(problem["sample"], "sample", 3, 3)]
        setup = f"    point = Diem3D({coords[0]!r}, {coords[1]!r}, {coords[2]!r})\n"
    else:
        setup = "    point = Diem3D(3, 4, 12)\n"

    output_spec = _CURRENT_OUTPUT_SPEC.get()
    if output_spec:
        extra_imports, body = render_main_output("point.khoang_cach_goc()", output_spec)
        example = setup + body
    else:
        extra_imports = ""
        example = setup + "    print(point.khoang_cach_goc())\n"
    return _geometry_solution(
        problem, Diem3D, example,
        "Lớp Diem3D chuyển tọa độ sang float và tính khoảng cách tới gốc.",
        ("Khoảng cách Euclid tính bằng math.hypot. Tọa độ cần hữu hạn.",),
        extra_imports=extra_imports,
    )


def _nut_tim_kiem(problem):
    from .offline_solver import OfflineSolution, _CURRENT_OUTPUT_SPEC, _fields
    from .runnable_output import render_main_output

    _fields(problem, ("type",))
    setup = (
        '    goc = NutTimKiem("A", parent=None, action=None, g=0.0, h=5.0)\n'
        '    giua = NutTimKiem("B", parent=goc, action="A->B", g=2.0, h=3.0)\n'
        '    dich = NutTimKiem("G", parent=giua, action="B->G", g=5.0, h=0.0)\n'
    )
    output_spec = _CURRENT_OUTPUT_SPEC.get()
    if output_spec:
        expr = '{"f_cost": dich.f_cost(), "path": dich.truy_vet_duong_di()}'
        extra_imports, body = render_main_output(expr, output_spec, default_collection_field="path")
    else:
        extra_imports = ""
        body = (
            '    print("Duong di:", dich.truy_vet_duong_di())\n'
            '    print("Tong chi phi f(n):", dich.f_cost())\n'
        )
    code = (
        f"{extra_imports}"
        + inspect.getsource(NutTimKiem).rstrip()
        + '\n\n\ndef main():\n'
        + setup
        + body
        + '\n\nif __name__ == "__main__":\n    main()\n'
    )
    return OfflineSolution(
        "nut_tim_kiem",
        code,
        "Lớp NutTimKiem tính f(n) = g(n) + h(n) và truy vết đường đi từ gốc tới đích.",
        ("Lưu state, parent, action, g, h và trả danh sách trạng thái theo thứ tự đầu -> đích.",),
    )


GEOMETRY_CLASS_SOLVERS = {
    "vector24": _vector24,
    "diem3d": _diem3d,
    "nut_tim_kiem": _nut_tim_kiem,
}
