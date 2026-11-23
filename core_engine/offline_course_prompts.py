"""Read Vietnamese course exercises whose requirements can be fully checked."""

import ast
import re

from .golden_skeletons import strip_accents

_BOARD_3 = r"\(\s*\(\s*[0-8]\s*,\s*[0-8]\s*,\s*[0-8]\s*\)\s*,\s*\(\s*[0-8]\s*,\s*[0-8]\s*,\s*[0-8]\s*\)\s*,\s*\(\s*[0-8]\s*,\s*[0-8]\s*,\s*[0-8]\s*\)\s*\)"
_PUZZLE = re.compile(
    r"(?:cau\s+\d+\s*:\s*)?cho bai toan 8-puzzle voi trang thai ban dau\s*:\s*"
    rf"(?P<start>{_BOARD_3})\s+va trang thai dich\s*:?\s*(?P<goal>{_BOARD_3})\s*\.\s*"
    r"hay cai dat bang thu vien simpleai va giai bang thuat toan a\* voi (?:2|hai) ham heuristic h1 va h2\.?",
    re.IGNORECASE,
)
_LIST = r"\[\s*(?:'[^'\r\n]+'|\"[^\"\r\n]+\")\s*(?:,\s*(?:'[^'\r\n]+'|\"[^\"\r\n]+\")\s*)*\]"
_SHIFTS = re.compile(
    r"\s*(?:bai toan thoa man rang buoc\s*-\s*csp\s*\(simpleai\.search\.csp\)\s*)?"
    r"(?:de bai:\s*)?phan cong ca truc cho (?P<workers>\d{1,2}) nhan vien"
    rf"\s+variables\s*=\s*(?P<names>{_LIST})\s+vao (?P<count>\d{{1,2}}) ca lam viec\s*(?P<shifts>{_LIST})"
    r"\s+sao cho thoa man cac rang buoc sau\s*:\s*(?P<constraints>.+?)"
    r"\s*yeu cau:\s*su dung cspproblem va backtrack trong simpleai\.search\.csp"
    r"\s+de tim mot bo phan cong hop le\.?\s*",
    re.IGNORECASE | re.DOTALL,
)
_SHIFT = r"""(?:'(?P<single>[^']+)'|"(?P<double>[^"]+)")"""


def _parse_shifts(match, original, offsets):
    def read_list(field):
        start, end = match.span(field)
        return ast.literal_eval(original[offsets[start]:offsets[end]])

    try:
        names, shifts = read_list("names"), read_list("shifts")
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Danh sách nhân viên hoặc ca làm việc chưa hợp lệ.") from exc
    if len(names) != int(match["workers"]) or len(shifts) != int(match["count"]):
        raise ValueError("Số nhân viên hoặc số ca không khớp danh sách.")

    def name_key(value):
        return strip_accents(value).casefold()

    if not 1 <= len(names) <= 24 or not 1 <= len(shifts) <= 32:
        raise ValueError("Bài phân ca hỗ trợ tối đa 24 nhân viên và 32 ca.")
    name_by_key = {name_key(value): value for value in names}
    shift_by_key = {name_key(value): value for value in shifts}
    if len(name_by_key) != len(names) or len(shift_by_key) != len(shifts):
        raise ValueError("Tên nhân viên và tên ca cần phân biệt được.")
    name_pattern = "|".join(re.escape(key) for key in sorted(name_by_key, key=len, reverse=True))
    person = rf"(?P<person>{name_pattern})"
    domains = {name: shifts[:] for name in names}
    constraints = []
    choices = re.compile(person + r" chi co the lam ca (?P<choices>.+)")
    no_shift = re.compile(person + r" khong lam ca " + _SHIFT)
    different = re.compile(
        person + rf" va (?P<other>{name_pattern}) "
        r"(?:khong duoc lam cung mot ca|phai lam khac ca nhau)"
    )

    def lookup_shift(item):
        key = item["single"] or item["double"]
        if key not in shift_by_key:
            raise ValueError("Ràng buộc dùng tên ca chưa khai báo.")
        return shift_by_key[key]

    for clause in re.split(r"\.\s*|[,;]\s*dong thoi\s*", match["constraints"].strip()):
        clause = re.sub(r"\s+", " ", clause.strip()).casefold()
        if not clause:
            continue
        if item := different.fullmatch(clause):
            constraints.append({"op": "ne", "vars": [name_by_key[item["person"]], name_by_key[item["other"]]]})
        elif item := no_shift.fullmatch(clause):
            domain = domains[name_by_key[item["person"]]]
            forbidden = lookup_shift(item)
            domains[name_by_key[item["person"]]] = [value for value in domain if value != forbidden]
        elif item := choices.fullmatch(clause):
            values = re.split(r"\s+hoac\s+", item["choices"])
            parsed = [re.fullmatch(_SHIFT, value) for value in values]
            if not all(parsed):
                return None
            allowed = {lookup_shift(value) for value in parsed}
            name = name_by_key[item["person"]]
            domains[name] = [value for value in domains[name] if value in allowed]
        else:
            return None
    if not constraints and domains == {name: shifts for name in names}:
        return None
    if not all(domains.values()):
        # SimpleAI's adapter validates nonempty initial domains. Encode the
        # impossible condition as an empty unary table on the original domain.
        for name, domain in domains.items():
            if not domain:
                constraints.append({"op": "table", "vars": [name], "allowed": []})
                domains[name] = shifts[:]
    return {"type": "simpleai_csp", "domains": domains, "constraints": constraints}


def read_course_prompt(text):
    normalized = strip_accents(text)
    if match := _PUZZLE.fullmatch(re.sub(r"\s+", " ", normalized).strip()):
        boards = {
            field: [tile for row in ast.literal_eval(match[field]) for tile in row]
            for field in ("start", "goal")
        }
        return {"type": "simpleai_puzzle", "heuristic": "both", **boards}
    if match := _SHIFTS.fullmatch(normalized):
        offsets = list(range(len(text) + 1))
        if len(text) != len(normalized):
            offsets = [
                index for index, char in enumerate(text)
                for _ in strip_accents(char)
            ] + [len(text)]
        return _parse_shifts(match, text, offsets)
    return None
