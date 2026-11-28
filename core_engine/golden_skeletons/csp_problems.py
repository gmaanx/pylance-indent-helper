# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Nhom 3: Constraint Satisfaction Problems (CspProblem, backtrack, min_conflicts).
Chuan xac 100% theo buoi05/baitap2.py + To mau ban do + Cryptarithmetic + Sudoku/Magic Square + Xep lich.
"""

from typing import Dict, Any

SKELETON_CSP_NQUEENS_HYBRID = '''import random
import time

# Thu vien SimpleAI
from simpleai.search import (
    CspProblem,
    HIGHEST_DEGREE_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
    MOST_CONSTRAINED_VARIABLE,
    SearchProblem,
    backtrack,
    min_conflicts,
)
from simpleai.search.local import (
    beam,
    beam_best_first,
    hill_climbing,
    hill_climbing_random_restarts,
    hill_climbing_stochastic,
    simulated_annealing,
)

N = 5
INITIAL = tuple(0 for _ in range(N))


def khong_xung_dot(variables, values):
    cot1, cot2 = variables
    hang1, hang2 = values
    return hang1 != hang2 and abs(hang1 - hang2) != abs(cot1 - cot2)


def so_xung_dot(state):
    return sum(
        state[cot1] == state[cot2]
        or abs(state[cot1] - state[cot2]) == cot2 - cot1
        for cot1 in range(N) for cot2 in range(cot1 + 1, N)
    )


class NamQuanHau(SearchProblem):
    def actions(self, state):
        return [(cot, hang) for cot in range(N) for hang in range(N)
                if hang != state[cot]]

    def result(self, state, action):
        cot, hang_moi = action
        state_moi = list(state)
        state_moi[cot] = hang_moi
        return tuple(state_moi)

    def value(self, state):
        return -so_xung_dot(state)

    def generate_random_state(self):
        return tuple(random.randrange(N) for _ in range(N))


def in_ban_co(state):
    for hang in range(N):
        print('  ' + ' '.join('Q' if state[cot] == hang else '.'
                              for cot in range(N)))


def chay_backtrack(ten, **kwargs):
    variables = list(range(N))
    domains = {cot: list(range(N)) for cot in variables}
    constraints = [
        ((cot1, cot2), khong_xung_dot)
        for cot1 in range(N) for cot2 in range(cot1 + 1, N)
    ]
    problem = CspProblem(variables, domains, constraints)
    bat_dau = time.perf_counter()
    ket_qua = backtrack(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    print(f'\\n{ten}:')
    if ket_qua is None:
        print('  Khong tim duoc ket qua')
        return None

    state = tuple(ket_qua[cot] for cot in range(N))
    print(f'  State = {state}')
    in_ban_co(state)
    print(f'  So xung dot = {so_xung_dot(state)}')
    print(f'  Dat loi giai = {so_xung_dot(state) == 0}')
    print(f'  Thoi gian = {thoi_gian:.4f}s')
    return ket_qua


def chay(ten, thuat_toan, **kwargs):
    random.seed(42)
    problem = NamQuanHau(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    print(f'\\n{ten}:')
    if ket_qua is None:
        print('  Khong tim duoc ket qua')
        return None

    print(f'  State = {ket_qua.state}')
    in_ban_co(ket_qua.state)
    print(f'  Value = {problem.value(ket_qua.state)}')
    print(f'  So xung dot = {so_xung_dot(ket_qua.state)}')
    print(f'  Dat loi giai = {so_xung_dot(ket_qua.state) == 0}')
    print(f'  Thoi gian = {thoi_gian:.4f}s')
    return ket_qua


if __name__ == '__main__':
    print(f'Bai toan {N} quan hau tren ban co {N}x{N} (CSP Backtrack & Local Search)')

    chay_backtrack(
        'Backtrack (MRV + LCV)',
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    chay_backtrack(
        'Backtrack (Highest Degree + LCV)',
        variable_heuristic=HIGHEST_DEGREE_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )

    print(f'\\nTrang thai ban dau: {INITIAL}')
    in_ban_co(INITIAL)

    chay('Hill climbing', hill_climbing)
    chay('Stochastic hill climbing', hill_climbing_stochastic, iterations_limit=100)
    chay('Hill climbing random restarts', hill_climbing_random_restarts, restarts_limit=10)
    chay('Beam search', beam, beam_size=15, iterations_limit=50)
    chay('Beam best first', beam_best_first, beam_size=15, iterations_limit=50)
    chay('Simulated annealing', simulated_annealing, iterations_limit=500)
'''

SKELETON_CSP_MAP_COLORING = '''import time
from simpleai.search import (
    CspProblem,
    backtrack,
    min_conflicts,
    MOST_CONSTRAINED_VARIABLE,
    HIGHEST_DEGREE_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)

CAC_VUNG = ('WA', 'NT', 'SA', 'Q', 'NSW', 'V', 'T')
MAU_SAC = ['Do', 'XanhLa', 'XanhDuong']

GIAP_RANH = [
    ('WA', 'NT'), ('WA', 'SA'),
    ('NT', 'SA'), ('NT', 'Q'),
    ('SA', 'Q'), ('SA', 'NSW'), ('SA', 'V'),
    ('Q', 'NSW'),
    ('NSW', 'V'),
]


def khac_mau(variables, values):
    return values[0] != values[1]


def giai_to_mau(ten, thuat_toan=backtrack, **kwargs):
    domains = {vung: list(MAU_SAC) for vung in CAC_VUNG}
    constraints = [(cap, khac_mau) for cap in GIAP_RANH]

    problem = CspProblem(CAC_VUNG, domains, constraints)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"{ten}:")
    if ket_qua is None:
        print("  Khong tim thay nghiem\\n")
        return None
    for vung in CAC_VUNG:
        print(f"  {vung:<5}: {ket_qua[vung]}")
    print(f"  Thoi gian = {thoi_gian:.4f}s\\n")
    return ket_qua


if __name__ == '__main__':
    print("Bai toan To mau ban do (CSP):\\n")
    giai_to_mau("Backtrack co ban", backtrack)
    giai_to_mau(
        "Backtrack (MRV + LCV)",
        backtrack,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    giai_to_mau(
        "Backtrack (Highest Degree + LCV)",
        backtrack,
        variable_heuristic=HIGHEST_DEGREE_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    giai_to_mau("Min Conflicts", min_conflicts, iterations_limit=100)
'''

SKELETON_CSP_CRYPTARITHMETIC = '''import time
from simpleai.search import CspProblem, backtrack

# Bai toan giai mat ma chu so: SEND + MORE = MONEY
TU_1 = 'SEND'
TU_2 = 'MORE'
TONG = 'MONEY'

# Sap xep bien theo tung cot tu phai sang trai (hang don vi -> chuc -> tram -> nghin)
_thu_tu = []
for _k in range(1, max(len(TU_1), len(TU_2), len(TONG)) + 1):
    for _tu in (TU_1, TU_2, TONG):
        if _k <= len(_tu) and _tu[-_k] not in _thu_tu:
            _thu_tu.append(_tu[-_k])
CHU_CAI = tuple(_thu_tu)
CHU_DAU = {TU_1[0], TU_2[0], TONG[0]}


def khac_nhau(variables, values):
    return values[0] != values[1]


def tao_rang_buoc_cot(k):
    duoi_1 = TU_1[-k:]
    duoi_2 = TU_2[-k:]
    duoi_tong = TONG[-k:]
    mod_k = 10 ** k

    def kiem_tra_cot(variables, values):
        bang = dict(zip(variables, values))
        s1 = int(''.join(str(bang[c]) for c in duoi_1))
        s2 = int(''.join(str(bang[c]) for c in duoi_2))
        st = int(''.join(str(bang[c]) for c in duoi_tong))
        return (s1 + s2) % mod_k == st

    bien_cot = tuple(dict.fromkeys(duoi_1 + duoi_2 + duoi_tong))
    return bien_cot, kiem_tra_cot


def kiem_tra_tong(variables, values):
    bang = dict(zip(variables, values))
    so_1 = int(''.join(str(bang[c]) for c in TU_1))
    so_2 = int(''.join(str(bang[c]) for c in TU_2))
    so_tong = int(''.join(str(bang[c]) for c in TONG))
    return so_1 + so_2 == so_tong


if __name__ == '__main__':
    domains = {
        c: list(range(1, 10)) if c in CHU_DAU else list(range(0, 10))
        for c in CHU_CAI
    }
    if len(TONG) > max(len(TU_1), len(TU_2)):
        domains[TONG[0]] = [1]

    constraints = [
        ((c1, c2), khac_nhau)
        for i, c1 in enumerate(CHU_CAI)
        for c2 in CHU_CAI[i + 1:]
    ]
    # Them rang buoc dong du modulo 10^k cho tung cot de cat tia tuc thi
    for k in range(1, min(len(TU_1), len(TU_2)) + 1):
        constraints.append(tao_rang_buoc_cot(k))
    constraints.append((CHU_CAI, kiem_tra_tong))

    problem = CspProblem(CHU_CAI, domains, constraints)
    bat_dau = time.perf_counter()
    ket_qua = backtrack(problem, inference=False)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"Bai toan {TU_1} + {TU_2} = {TONG}:")
    if ket_qua is None:
        print("  Khong tim thay nghiem")
    else:
        so_1 = ''.join(str(ket_qua[c]) for c in TU_1)
        so_2 = ''.join(str(ket_qua[c]) for c in TU_2)
        so_tong = ''.join(str(ket_qua[c]) for c in TONG)
        print(f"  Nghiem = {ket_qua}")
        print(f"  Phep tinh: {so_1} + {so_2} = {so_tong}")
        print(f"  Thoi gian = {thoi_gian:.4f}s")
'''

SKELETON_CSP_MAGIC_SQUARE = '''import time
from simpleai.search import CspProblem, backtrack

# Hinh vuong ma thuat 3x3: dien cac so 1..9 sao cho tong moi hang, cot, duong cheo = 15
N = 3
TONG_CHUAN = N * (N * N + 1) // 2
# Sap xep o giua va cac duong cheo truoc de cat tia som
VARIABLES = (
    (1, 1), (0, 0), (2, 2),
    (0, 2), (2, 0), (0, 1),
    (2, 1), (1, 0), (1, 2),
)


def khac_nhau(variables, values):
    return values[0] != values[1]


def tong_bang_chuan(variables, values):
    return sum(values) == TONG_CHUAN


if __name__ == '__main__':
    domains = {v: list(range(1, N * N + 1)) for v in VARIABLES}
    domains[(1, 1)] = [5]

    constraints = [
        ((v1, v2), khac_nhau)
        for i, v1 in enumerate(VARIABLES)
        for v2 in VARIABLES[i + 1:]
    ]

    for r in range(N):
        constraints.append((tuple((r, c) for c in range(N)), tong_bang_chuan))
    for c in range(N):
        constraints.append((tuple((r, c) for r in range(N)), tong_bang_chuan))
    constraints.append((tuple((i, i) for i in range(N)), tong_bang_chuan))
    constraints.append((tuple((i, N - 1 - i) for i in range(N)), tong_bang_chuan))

    problem = CspProblem(VARIABLES, domains, constraints)
    bat_dau = time.perf_counter()
    ket_qua = backtrack(problem, inference=False)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"Hinh vuong ma thuat {N}x{N} (Tong = {TONG_CHUAN}):")
    if ket_qua:
        for r in range(N):
            print("  " + " ".join(f"{ket_qua[(r, c)]:2d}" for c in range(N)))
        print(f"Thoi gian = {thoi_gian:.4f}s")
'''

SKELETON_CSP_SCHEDULING = '''from simpleai.search import (
    CspProblem,
    backtrack,
    MOST_CONSTRAINED_VARIABLE,
    HIGHEST_DEGREE_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)


def khong_trung_ca(variables, values):
    return values[0] != values[1]


def giai_csp_phan_ca(domains, pairs):
    if not domains:
        return {}
    clean_domains = {m: list(ds) for m, ds in domains.items()}
    if any(len(ds) == 0 for ds in clean_domains.values()):
        return None
    variables = list(clean_domains.keys())
    constraints = [(tuple(cap), khong_trung_ca) for cap in pairs]
    problem = CspProblem(variables, clean_domains, constraints)
    return backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )


def main():
    ca_thi = ['Sang_T2', 'Chieu_T2', 'Sang_T3']
    mon_hoc = ('M1', 'M2', 'M3', 'M4', 'M5')
    domains = {m: list(ca_thi) for m in mon_hoc}
    domains['M1'] = ['Sang_T2', 'Sang_T3']
    xung_dot = [
        ('M1', 'M2'), ('M1', 'M3'),
        ('M2', 'M3'), ('M2', 'M4'),
        ('M3', 'M5'), ('M4', 'M5'),
    ]
    ket_qua = giai_csp_phan_ca(domains, xung_dot)
    print("Ket qua xep lich (CSP):", ket_qua)


if __name__ == '__main__':
    main()
'''

CSP_SKELETONS: Dict[str, Dict[str, Any]] = {
    "csp_nqueens_hybrid": {
        "id": "csp_nqueens_hybrid",
        "category": "csp",
        "title": "N-Queens CSP Backtrack (MRV, Highest Degree, LCV) & Local Search (buoi05/baitap2.py)",
        "keywords": [
            "cspproblem", "backtrack", "most_constrained_variable", "highest_degree_variable",
            "least_constraining_value", "khong_xung_dot", "so_xung_dot", "chay_backtrack",
            "mrv", "lcv", "n-queens csp", "5 quan hau csp", "8 quan hau csp", "baitap2"
        ],
        "code": SKELETON_CSP_NQUEENS_HYBRID,
    },
    "csp_map_coloring": {
        "id": "csp_map_coloring",
        "category": "csp",
        "title": "Bai toan To mau ban do / Map Coloring (CspProblem, backtrack, min_conflicts)",
        "keywords": [
            "to mau ban do", "map coloring", "australia", "wa", "nt", "sa", "nsw",
            "khac_mau", "min_conflicts", "giap ranh", "to mau do thi"
        ],
        "code": SKELETON_CSP_MAP_COLORING,
    },
    "csp_cryptarithmetic": {
        "id": "csp_cryptarithmetic",
        "category": "csp",
        "title": "Bai toan Giai mat ma chu so / Cryptarithmetic (SEND + MORE = MONEY - SimpleAI CSP)",
        "keywords": [
            "send + more = money", "send", "more", "money", "cryptarithmetic",
            "mat ma chu so", "chu thay so", "two + two = four"
        ],
        "code": SKELETON_CSP_CRYPTARITHMETIC,
    },
    "csp_magic_square": {
        "id": "csp_magic_square",
        "category": "csp",
        "title": "Bai toan Hinh vuong ma thuat / Magic Square & Sudoku (SimpleAI CSP)",
        "keywords": [
            "hinh vuong ma thuat", "magic square", "ma phuong", "sudoku",
            "tong hang cot duong cheo", "15"
        ],
        "code": SKELETON_CSP_MAGIC_SQUARE,
    },
    "csp_scheduling": {
        "id": "csp_scheduling",
        "category": "csp",
        "title": "Bai toan Xep lich thi / Phan cong ca truc / CSP Tong quat (SimpleAI CspProblem)",
        "keywords": [
            "xep lich", "lich thi", "phan cong", "ca truc", "scheduling",
            "khong trung ca", "rang buoc", "mien gia tri", "variables", "domains", "constraints"
        ],
        "code": SKELETON_CSP_SCHEDULING,
    },
}
