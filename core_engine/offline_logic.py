"""Exact offline solvers for bounded logic and puzzle specifications."""

import re
from collections import defaultdict, deque


MAX_SAT_VARIABLES = 128
MAX_SAT_CLAUSES = 1500
MAX_SAT_WORK = 3_000_000
MAX_HORN_RULES = 2000
MAX_SUDOKU_STEPS = 100_000
MAX_CRYPTARITHM_STEPS = 200_000


def _solve_sat(variable_count, clauses, work_limit):
    """Use DPLL to return a satisfying Boolean assignment or None."""
    remaining_work = work_limit

    def simplify(current, literal):
        nonlocal remaining_work
        reduced = []
        for clause in current:
            remaining_work -= len(clause) + 1
            if remaining_work < 0:
                raise OverflowError("SAT work limit exceeded")
            if literal in clause:
                continue
            reduced.append(tuple(item for item in clause if item != -literal))
        return reduced

    def search(current, assignment):
        # Unit clauses force values without introducing a search branch.
        while current:
            shortest = min(current, key=len)
            if not shortest:
                return None
            if len(shortest) > 1:
                break
            literal = shortest[0]
            assignment[abs(literal)] = literal > 0
            current = simplify(current, literal)
        if not current:
            return {variable: assignment.get(variable, False) for variable in range(1, variable_count + 1)}

        literal = shortest[0]
        for choice in (literal, -literal):
            child_assignment = dict(assignment)
            child_assignment[abs(choice)] = choice > 0
            result = search(simplify(current, choice), child_assignment)
            if result is not None:
                return result
        return None

    normalized = []
    for clause in clauses:
        unique = set(clause)
        if not any(-literal in unique for literal in unique):
            normalized.append(tuple(sorted(unique)))
    return search(normalized, {})


def _sat(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "variables", "clauses"))
    count = _integer(problem["variables"], "variables", 0, MAX_SAT_VARIABLES)
    clauses = []
    for clause in _array(problem["clauses"], "clauses", 0, MAX_SAT_CLAUSES):
        literals = []
        for literal in _array(clause, "Mệnh đề tuyển", 0, MAX_SAT_VARIABLES * 2):
            literal = _integer(literal, "Literal", -count, count)
            if literal == 0:
                raise OfflineProblemError("invalid", "Mỗi literal phải là chỉ số khác 0, có dấu âm nếu phủ định.")
            literals.append(literal)
        clauses.append(tuple(literals))
    args = (count, clauses, MAX_SAT_WORK)
    assignment = _solve_sat(*args)
    summary = "Công thức CNF vô nghiệm." if assignment is None else "Tìm được phép gán thỏa mọi mệnh đề."
    return OfflineSolution(
        "sat", _standalone((_solve_sat,), _solve_sat, args, assignment), summary,
        ("DPLL với lan truyền mệnh đề đơn vị. Kết quả là một phép gán Boolean, hoặc None nếu vô nghiệm.",),
        ("satisfiable", assignment is not None),
    )


def _solve_horn(facts, rules, query):
    """Compute the least fixed point of positive Horn rules."""
    known = set(facts)
    waiting = defaultdict(list)
    remaining = []
    for index, (premises, consequence) in enumerate(rules):
        missing = set(premises) - known
        remaining.append(len(missing))
        for atom in missing:
            waiting[atom].append(index)

    # Build all premise counts before feeding any missing atom into the queue.
    pending = deque(consequence for index, (_, consequence) in enumerate(rules) if remaining[index] == 0)
    while pending:
        atom = pending.popleft()
        if atom in known:
            continue
        known.add(atom)
        for index in waiting.pop(atom, []):
            remaining[index] -= 1
            if remaining[index] == 0:
                pending.append(rules[index][1])
    return {"entailed": query in known, "closure": sorted(known)}


def _horn(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _name, _standalone

    _fields(problem, ("type", "facts", "rules", "query"))

    def atom(value):
        name = _name(value, "Tên mệnh đề")
        if not name.isidentifier():
            raise OfflineProblemError("invalid", "Dùng tên mệnh đề dương gồm chữ, số hoặc dấu gạch dưới.")
        return name

    facts = [atom(item) for item in _array(problem["facts"], "facts", 0, 2000)]
    rules = []
    for rule in _array(problem["rules"], "rules", 0, MAX_HORN_RULES):
        _fields(rule, ("if", "then"))
        premises = tuple(atom(item) for item in _array(rule["if"], "if", 0, 64))
        rules.append((premises, atom(rule["then"])))
    args = (facts, rules, atom(problem["query"]))
    result = _solve_horn(*args)
    summary = "Suy ra được mệnh đề đích." if result["entailed"] else "Không suy ra được mệnh đề đích."
    return OfflineSolution(
        "horn", _standalone((_solve_horn,), _solve_horn, args, result), summary,
        ("Suy diễn tiến với luật Horn dương. closure là tập mệnh đề suy ra được.",),
        ("entailed", result["entailed"]),
    )


def _solve_sudoku(givens, step_limit):
    """Find up to two solutions, enough to decide whether a grid has a unique completion."""
    size = len(givens)
    box_size = 2 if size == 4 else 3
    all_digits = (1 << size) - 1
    row_digits = [0] * size
    column_digits = [0] * size
    box_digits = [0] * size
    grid = [list(row) for row in givens]
    empty = []
    for row in range(size):
        for column in range(size):
            box = row // box_size * box_size + column // box_size
            value = grid[row][column]
            if value == 0:
                empty.append((row, column, box))
                continue
            bit = 1 << (value - 1)
            if bit & (row_digits[row] | column_digits[column] | box_digits[box]):
                return "conflicting_givens", None
            row_digits[row] |= bit
            column_digits[column] |= bit
            box_digits[box] |= bit

    solutions = []
    steps = 0

    def search(index):
        nonlocal steps
        if index == len(empty):
            solutions.append([row[:] for row in grid])
            return

        fewest = size + 1
        best, options = index, 0
        for position in range(index, len(empty)):
            row, column, box = empty[position]
            candidates = all_digits & ~(row_digits[row] | column_digits[column] | box_digits[box])
            count = candidates.bit_count()
            if count == 0:
                return
            if count < fewest:
                best, options, fewest = position, candidates, count

        empty[index], empty[best] = empty[best], empty[index]
        row, column, box = empty[index]
        while options and len(solutions) < 2:
            steps += 1
            if steps > step_limit:
                raise OverflowError("Sudoku branch limit exceeded")
            bit = options & -options
            options ^= bit
            grid[row][column] = bit.bit_length()
            row_digits[row] |= bit
            column_digits[column] |= bit
            box_digits[box] |= bit
            search(index + 1)
            row_digits[row] ^= bit
            column_digits[column] ^= bit
            box_digits[box] ^= bit
        empty[index], empty[best] = empty[best], empty[index]

    search(0)
    if not solutions:
        return "none", None
    return ("unique" if len(solutions) == 1 else "multiple"), solutions[0]


def _sudoku(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "grid"))
    grid = problem["grid"]
    if not isinstance(grid, list) or len(grid) not in (4, 9):
        raise OfflineProblemError("invalid", "Sudoku hỗ trợ lưới vuông 4×4 hoặc 9×9.")
    size = len(grid)
    validated = [
        [_integer(value, "Ô Sudoku", 0, size) for value in _array(row, "Hàng Sudoku", size, size)]
        for row in grid
    ]
    args = (validated, MAX_SUDOKU_STEPS)
    status, solution = _solve_sudoku(*args)
    if status == "conflicting_givens":
        raise OfflineProblemError("invalid", "Các ô cho sẵn bị trùng số trong một hàng, cột hoặc khối.")
    summary = {
        "none": "Lưới Sudoku vô nghiệm.",
        "unique": "Lưới Sudoku có đúng một nghiệm.",
        "multiple": "Lưới Sudoku có nhiều nghiệm. Kết quả hiển thị một nghiệm.",
    }[status]
    result = {"status": status, "solution": solution}
    # Keep the standalone program's output identical to this result mapping.
    return OfflineSolution(
        "sudoku",
        _standalone((_solve_sudoku, _sudoku_result), _sudoku_result, args, result),
        summary,
        ("0 là ô trống. Bộ giải tìm đến hai nghiệm để phân biệt nghiệm duy nhất và nhiều nghiệm.",),
        ("sudoku_status", status),
    )


def _sudoku_result(grid, step_limit):
    status, solution = _solve_sudoku(grid, step_limit)
    return {"status": status, "solution": solution}


def _solve_cryptarithm(addends, result_word, base, step_limit):
    """Assign digits column by column, propagating carry into the next column."""
    leading = {word[0] for word in (*addends, result_word) if len(word) > 1}
    letters = set("".join((*addends, result_word)))
    if len(letters) > base:
        return None
    columns = []
    width = max(len(word) for word in (*addends, result_word))
    for index in range(1, width + 1):
        counts = {}
        for word in addends:
            if len(word) >= index:
                letter = word[-index]
                counts[letter] = counts.get(letter, 0) + 1
        output = result_word[-index] if len(result_word) >= index else None
        columns.append((tuple(counts.items()), output))

    assignment = {}
    used_digits = set()
    steps = 0

    def count_step():
        nonlocal steps
        steps += 1
        if steps > step_limit:
            raise OverflowError("Cryptarithm assignment limit exceeded")

    def solve_column(column, carry):
        if column == len(columns):
            return dict(sorted(assignment.items())) if carry == 0 else None
        inputs, output = columns[column]

        def assign_sources(index, total):
            count_step()
            if index == len(inputs):
                new_carry, digit = divmod(total, base)
                if output is None:
                    return solve_column(column + 1, new_carry) if digit == 0 else None
                if output in assignment:
                    return solve_column(column + 1, new_carry) if assignment[output] == digit else None
                if digit in used_digits or (digit == 0 and output in leading):
                    return None
                assignment[output] = digit
                used_digits.add(digit)
                result = solve_column(column + 1, new_carry)
                used_digits.remove(digit)
                del assignment[output]
                return result

            letter, count = inputs[index]
            if letter in assignment:
                return assign_sources(index + 1, total + assignment[letter] * count)
            for digit in range(1 if letter in leading else 0, base):
                if digit in used_digits:
                    continue
                assignment[letter] = digit
                used_digits.add(digit)
                result = assign_sources(index + 1, total + digit * count)
                used_digits.remove(digit)
                del assignment[letter]
                if result is not None:
                    return result
            return None

        return assign_sources(0, carry)

    return solve_column(0, 0)


def _cryptarithm(problem):
    from .offline_solver import OfflineProblemError, OfflineSolution, _array, _fields, _integer, _standalone

    _fields(problem, ("type", "addends", "result"), ("base",))
    base = _integer(problem.get("base", 10), "base", 2, 16)

    def word(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Z]{1,24}", value):
            raise OfflineProblemError("invalid", "Mỗi từ trong phép cộng cần từ 1 đến 24 chữ cái in hoa A–Z.")
        return value

    addends = tuple(word(item) for item in _array(problem["addends"], "addends", 2, 8))
    result_word = word(problem["result"])
    args = (addends, result_word, base, MAX_CRYPTARITHM_STEPS)
    result = _solve_cryptarithm(*args)
    summary = "Phép cộng chữ số vô nghiệm." if result is None else "Tìm được một phép gán chữ số thỏa phép cộng."
    return OfflineSolution(
        "cryptarithm", _standalone((_solve_cryptarithm,), _solve_cryptarithm, args, result), summary,
        ("Mỗi chữ có một chữ số khác nhau. Chữ đầu của từ nhiều ký tự lớn hơn 0.",),
        ("satisfiable", result is not None),
    )


LOGIC_SOLVERS = {
    "sat": _sat,
    "horn": _horn,
    "sudoku": _sudoku,
    "cryptarithm": _cryptarithm,
}
