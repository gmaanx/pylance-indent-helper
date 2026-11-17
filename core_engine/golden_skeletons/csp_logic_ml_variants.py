# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Mo Rong 2:
- Toan bo CSP nang cao cua SimpleAI (`convert_to_binary`, `arc_consistency_3`, `revise`, `min_conflicts`)
  va cac bai toan tren Slide Chuong 5 (He phuong trinh x1..x6, A..E, TWO+TWO=FOUR co nho X1..X3, Sudoku, Job Scheduling).
- Toan bo Slide Chuong 6 (Bang chan ly Truth Table KB |= alpha, Chuyen CNF & Hop giai Resolution, Bai toan SAT bang CSP & Local Search).
- Toan bo module `simpleai.machine_learning` (DecisionTreeLearner ID3, NaiveBayes, KNearestNeighbors, TDQLearner, SARSALearner).
"""

from typing import Any, Dict

SKELETON_CSP_NUMERIC_EQUATIONS = '''import time
from simpleai.search import (
    CspProblem,
    backtrack,
    min_conflicts,
    convert_to_binary,
    MOST_CONSTRAINED_VARIABLE,
    HIGHEST_DEGREE_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)

# Bai toan 1 (Slide 4 Chuong 5):
# Cac bien x1..x6, mien gia tri {0, 1}
# Rang buoc: x1+x2+x6=1, x1-x3+x4=1, x4+x5-x6>0, x2+x5-x6=0
def giai_bai_x1_x6():
    variables = ('x1', 'x2', 'x3', 'x4', 'x5', 'x6')
    domains = {v: [0, 1] for v in variables}

    def r1(vars_, vals):
        x1, x2, x6 = vals
        return x1 + x2 + x6 == 1

    def r2(vars_, vals):
        x1, x3, x4 = vals
        return x1 - x3 + x4 == 1

    def r3(vars_, vals):
        x4, x5, x6 = vals
        return x4 + x5 - x6 > 0

    def r4(vars_, vals):
        x2, x5, x6 = vals
        return x2 + x5 - x6 == 0

    constraints = [
        (('x1', 'x2', 'x6'), r1),
        (('x1', 'x3', 'x4'), r2),
        (('x4', 'x5', 'x6'), r3),
        (('x2', 'x5', 'x6'), r4),
    ]

    # Chuyen rang buoc 3 bien ve nhi phan bang convert_to_binary cua SimpleAI
    b_vars, b_doms, b_consts = convert_to_binary(variables, domains, constraints)
    problem = CspProblem(b_vars, b_doms, b_consts)
    kq = backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    nghiem = {v: kq[v] for v in variables} if kq else None
    print("1. Bai toan x1..x6 (Slide 4 Chuong 5):", nghiem)


# Bai toan 2 (Slide 22-24 Chuong 5):
# Cac bien A, B, C, D, E mien 1..10; rang buoc: A > E, B + 8 < D, C = 5 * E, A = 3 * E
def giai_bai_abcde():
    variables = ('A', 'B', 'C', 'D', 'E')
    domains = {v: list(range(1, 11)) for v in variables}

    constraints = [
        (('A', 'E'), lambda vars_, vals: vals[0] > vals[1]),
        (('B', 'D'), lambda vars_, vals: vals[0] + 8 < vals[1]),
        (('C', 'E'), lambda vars_, vals: vals[0] == 5 * vals[1]),
        (('A', 'E'), lambda vars_, vals: vals[0] == 3 * vals[1]),
    ]
    problem = CspProblem(variables, domains, constraints)
    kq = backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    print("2. Bai toan A,B,C,D,E (Slide 22-24 Chuong 5):", kq)


if __name__ == '__main__':
    giai_bai_x1_x6()
    giai_bai_abcde()
'''

SKELETON_CSP_CONVERT_BINARY_AC3 = '''from copy import deepcopy
from simpleai.search import (
    CspProblem,
    backtrack,
    min_conflicts,
    convert_to_binary,
    MOST_CONSTRAINED_VARIABLE,
    HIGHEST_DEGREE_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)
from simpleai.search.arc import arc_consistency_3, revise, all_arcs

# Minh hoa day du AC-3 (arc_consistency_3, revise, all_arcs) va convert_to_binary tren Slide 35-39 Chuong 5
CAC_VUNG = ('WA', 'NT', 'Q', 'NSW', 'V', 'SA', 'T')
MAU = ['red', 'green', 'blue']

GIAP_RANH = [
    ('WA', 'NT'), ('WA', 'SA'),
    ('NT', 'SA'), ('NT', 'Q'),
    ('SA', 'Q'), ('SA', 'NSW'), ('SA', 'V'),
    ('Q', 'NSW'),
    ('NSW', 'V'),
]


def khac_mau(variables, values):
    return values[0] != values[1]


if __name__ == '__main__':
    domains = {v: list(MAU) for v in CAC_VUNG}
    # Gia su da gan WA = 'red', Q = 'green' nhu tren Slide 35-38 Chuong 5
    domains['WA'] = ['red']
    domains['Q'] = ['green']

    constraints = [(cap, khac_mau) for cap in GIAP_RANH]

    dom_ac3 = deepcopy(domains)
    hop_le = arc_consistency_3(dom_ac3, constraints)
    print(f"Ket qua thuat toan AC-3 (arc_consistency_3): Hop le = {hop_le}")
    for v in CAC_VUNG:
        print(f"  Mien gia tri sau AC-3 cua {v:<4}: {dom_ac3[v]}")

    problem = CspProblem(CAC_VUNG, dom_ac3, constraints)
    nghiem = backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    print("\\nNghiem Backtrack:", nghiem)
'''

SKELETON_CSP_TWO_PLUS_TWO_CARRY = '''import time
from simpleai.search import (
    CspProblem,
    backtrack,
    convert_to_binary,
    MOST_CONSTRAINED_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)

# Bai toan mat ma so hoc TWO + TWO = FOUR voi bien nho X1, X2, X3 (Dung y het Slide 10 Chuong 5)
# Cac bien chu: F, T, U, W, R, O (mien 0..9, T != 0, F != 0)
# Cac bien nho: X1, X2, X3 (mien 0..1)
CHU = ('F', 'T', 'U', 'W', 'R', 'O')
NHO = ('X1', 'X2', 'X3')
VARIABLES = CHU + NHO


def khac_nhau(variables, values):
    return values[0] != values[1]


if __name__ == '__main__':
    domains = {c: list(range(10)) for c in CHU}
    domains['T'] = list(range(1, 10))
    domains['F'] = list(range(1, 10))
    for x in NHO:
        domains[x] = [0, 1]

    constraints = [
        ((c1, c2), khac_nhau)
        for i, c1 in enumerate(CHU)
        for c2 in CHU[i + 1:]
    ]

    # 4 phuong trinh cot tren Slide 10 Chuong 5:
    # 1. O + O = R + 10 * X1
    constraints.append((('O', 'R', 'X1'), lambda v, val: val[0] + val[0] == val[1] + 10 * val[2]))
    # 2. X1 + W + W = U + 10 * X2
    constraints.append((('X1', 'W', 'U', 'X2'), lambda v, val: val[0] + val[1] + val[1] == val[2] + 10 * val[3]))
    # 3. X2 + T + T = O + 10 * X3
    constraints.append((('X2', 'T', 'O', 'X3'), lambda v, val: val[0] + val[1] + val[1] == val[2] + 10 * val[3]))
    # 4. X3 = F
    constraints.append((('X3', 'F'), lambda v, val: val[0] == val[1]))

    # Chuyen toan bo rang buoc >2 bien ve binary CSP bang convert_to_binary
    b_vars, b_doms, b_consts = convert_to_binary(VARIABLES, domains, constraints)
    problem = CspProblem(b_vars, b_doms, b_consts)

    bat_dau = time.perf_counter()
    ket_qua = backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    thoi_gian = time.perf_counter() - bat_dau

    nghiem = {k: ket_qua[k] for k in VARIABLES}
    two = f"{nghiem['T']}{nghiem['W']}{nghiem['O']}"
    four = f"{nghiem['F']}{nghiem['O']}{nghiem['U']}{nghiem['R']}"
    print(f"TWO + TWO = FOUR (Slide 10 Chuong 5): {two} + {two} = {four}")
    print(f"Chi tiet cac bien: {nghiem} ({thoi_gian:.4f}s)")
'''

SKELETON_CSP_SUDOKU = '''import time
from simpleai.search import (
    CspProblem,
    backtrack,
    MOST_CONSTRAINED_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)
from simpleai.search.arc import arc_consistency_3

# Giai Sudoku (4x4 hoac 9x9) bang CspProblem + AC-3 + Backtrack (MRV + LCV)
# 0 la o trong can dien
BANG_SUDOKU = (
    (5, 3, 0, 0, 7, 0, 0, 0, 0),
    (6, 0, 0, 1, 9, 5, 0, 0, 0),
    (0, 9, 8, 0, 0, 0, 0, 6, 0),
    (8, 0, 0, 0, 6, 0, 0, 0, 3),
    (4, 0, 0, 8, 0, 3, 0, 0, 1),
    (7, 0, 0, 0, 2, 0, 0, 0, 6),
    (0, 6, 0, 0, 0, 0, 2, 8, 0),
    (0, 0, 0, 4, 1, 9, 0, 0, 5),
    (0, 0, 0, 0, 8, 0, 0, 7, 9),
)

KICH_THUOC = len(BANG_SUDOKU)
KHOI = int(KICH_THUOC ** 0.5)


def khac_nhau(variables, values):
    return values[0] != values[1]


if __name__ == '__main__':
    variables = [(r, c) for r in range(KICH_THUOC) for c in range(KICH_THUOC)]
    domains = {
        (r, c): [BANG_SUDOKU[r][c]] if BANG_SUDOKU[r][c] != 0 else list(range(1, KICH_THUOC + 1))
        for r, c in variables
    }

    cap_rang_buoc = set()
    for i, (r1, c1) in enumerate(variables):
        for r2, c2 in variables[i + 1:]:
            cung_hang = (r1 == r2)
            cung_cot = (c1 == c2)
            cung_khoi = (r1 // KHOI == r2 // KHOI and c1 // KHOI == c2 // KHOI)
            if cung_hang or cung_cot or cung_khoi:
                cap_rang_buoc.add(((r1, c1), (r2, c2)))

    constraints = [(cap, khac_nhau) for cap in cap_rang_buoc]

    bat_dau = time.perf_counter()
    # Chay AC-3 truoc de thu hep mien gia tri, sau do chay Backtrack voi MRV (inference=False)
    arc_consistency_3(domains, constraints)
    problem = CspProblem(variables, domains, constraints)
    ket_qua = backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        inference=False,
    )
    thoi_gian = time.perf_counter() - bat_dau

    print(f"Ket qua giai Sudoku {KICH_THUOC}x{KICH_THUOC} ({thoi_gian:.4f}s):")
    for r in range(KICH_THUOC):
        print("  " + " ".join(str(ket_qua[(r, c)]) for c in range(KICH_THUOC)))
'''

SKELETON_CSP_JOB_SCHEDULING = '''import time
from simpleai.search import (
    CspProblem,
    backtrack,
    MOST_CONSTRAINED_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)

# Bai toan Xep lich cong viec (Job Scheduling - Slide 8 Chuong 5: StartJob1 + thoi_gian <= StartJob3)
CONG_VIEC = ('Job1', 'Job2', 'Job3', 'Job4')
THOI_GIAN_THUC_HIEN = {'Job1': 3, 'Job2': 2, 'Job3': 4, 'Job4': 2}
NGAY_TOI_DA = 14

# Rang buoc thu tu truoc-sau: Job_truoc phai xong truoc khi Job_sau bat dau
THU_TU_TRUOC_SAU = [
    ('Job1', 'Job3'),  # StartJob1 + 3 <= StartJob3
    ('Job2', 'Job3'),  # StartJob2 + 2 <= StartJob3
    ('Job3', 'Job4'),  # StartJob3 + 4 <= StartJob4
]

# Rang buoc khong trung tai nguyen (khong duoc chay dong thoi)
CUNG_TAI_NGUYEN = [
    ('Job1', 'Job2'),
]


def tao_rang_buoc_thu_tu(d_truoc):
    def kiem_tra(variables, values):
        t_truoc, t_sau = values
        return t_truoc + d_truoc <= t_sau
    return kiem_tra


def tao_rang_buoc_tai_nguyen(d1, d2):
    def khong_chong_lan(variables, values):
        t1, t2 = values
        return (t1 + d1 <= t2) or (t2 + d2 <= t1)
    return khong_chong_lan


if __name__ == '__main__':
    domains = {
        cv: list(range(1, NGAY_TOI_DA - THOI_GIAN_THUC_HIEN[cv] + 2))
        for cv in CONG_VIEC
    }
    constraints = []
    for cv_truoc, cv_sau in THU_TU_TRUOC_SAU:
        constraints.append(
            ((cv_truoc, cv_sau), tao_rang_buoc_thu_tu(THOI_GIAN_THUC_HIEN[cv_truoc]))
        )
    for cv1, cv2 in CUNG_TAI_NGUYEN:
        constraints.append(
            ((cv1, cv2), tao_rang_buoc_tai_nguyen(THOI_GIAN_THUC_HIEN[cv1], THOI_GIAN_THUC_HIEN[cv2]))
        )

    problem = CspProblem(CONG_VIEC, domains, constraints)
    ket_qua = backtrack(
        problem,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    print("Lich thuc hien cong viec (Start -> End):")
    for cv in CONG_VIEC:
        bd = ket_qua[cv]
        kt = bd + THOI_GIAN_THUC_HIEN[cv]
        print(f"  {cv}: Bat dau ngay {bd} -> Ket thuc ngay {kt} (Thoi luong = {THOI_GIAN_THUC_HIEN[cv]})")
'''

SKELETON_LOGIC_TRUTH_TABLE = '''import itertools

# Lap Bang chan ly (Truth Table) & Chung minh KB |= alpha (Slide 20-28 Chuong 6)
# Cac phep toan logic dinh de:
# - Phu dinh: not p
# - Hoi (VA / ^): p and q
# - Tuyen (HOAC / v): p or q
# - Keo theo (=>): implies(p, q)
# - Tuong duong (<=>): iff(p, q)


def implies(p, q):
    return (not p) or q


def iff(p, q):
    return bool(p) == bool(q)


def str_val(b):
    return "dung" if b else "sai"


def kiem_tra_bang_chan_ly( cac_bien, ham_kb, ham_alpha, mo_ta_kb="KB", mo_ta_alpha="alpha"):
    print(f"Bang chan ly kiem tra {mo_ta_kb} |= {mo_ta_alpha}:")
    header = " | ".join(f"{v:^6}" for v in cac_bien) + f" | {'KB':^6} | {'alpha':^6}"
    print(header)
    print("-" * len(header))

    kb_bao_ham_alpha = True
    so_mo_hinh_kb = 0

    for gia_tri in itertools.product([False, True], repeat=len(cac_bien)):
        env = dict(zip(cac_bien, gia_tri))
        val_kb = bool(ham_kb(**env))
        val_alpha = bool(ham_alpha(**env))
        if val_kb:
            so_mo_hinh_kb += 1
            if not val_alpha:
                kb_bao_ham_alpha = False

        dong = " | ".join(f"{str_val(v):^6}" for v in gia_tri)
        danh_dau = " <-- model KB" if val_kb else ""
        print(f"{dong} | {str_val(val_kb):^6} | {str_val(val_alpha):^6}{danh_dau}")

    print(f"\\n=> So mo hinh thoa man KB: {so_mo_hinh_kb}")
    print(f"=> Ket luan KB |= alpha: {'DUNG (Entailed)' if kb_bao_ham_alpha else 'SAI (Not entailed)'}\\n")
    return kb_bao_ham_alpha


if __name__ == '__main__':
    # Vi du 1 (Slide 27 Chuong 6): KB = (p v q) ^ (p <=> q), alpha = (p v ~q) ^ q
    kiem_tra_bang_chan_ly(
        ('p', 'q'),
        ham_kb=lambda p, q: (p or q) and iff(p, q),
        ham_alpha=lambda p, q: (p or (not q)) and q,
        mo_ta_kb="(p v q) ^ (p <=> q)",
        mo_ta_alpha="(p v ~q) ^ q",
    )

    # Vi du 2 (Slide 28 Chuong 6): KB = (p v r) ^ (q v ~r), alpha = (p v q)
    kiem_tra_bang_chan_ly(
        ('p', 'q', 'r'),
        ham_kb=lambda p, q, r: (p or r) and (q or (not r)),
        ham_alpha=lambda p, q, r: p or q,
        mo_ta_kb="(p v r) ^ (q v ~r)",
        mo_ta_alpha="(p v q)",
    )
'''

SKELETON_LOGIC_CNF_RESOLUTION = '''# Chung minh bang Hop giai phan chung (Resolution Refutation) tren CNF (Slide 36-46 Chuong 6)
# Moi menh de (clause) o dang chuan CNF la mot frozenset cac literal (VD: {'~p', 'r'} tuong ung ~p v r)


def phu_dinh_literal(lit):
    return lit[1:] if lit.startswith('~') else f'~{lit}'


def hop_giai_hai_menh_de(c1, c2):
    """Tra ve danh sach cac menh de hop giai (resolvents) tu 2 menh de CNF c1 va c2."""
    ket_qua = []
    for lit in c1:
        doi = phu_dinh_literal(lit)
        if doi in c2:
            resolvent = (c1 - {lit}) | (c2 - {doi})
            # Bo qua menh de tam thuong (chua ca x va ~x)
            if not any(phu_dinh_literal(x) in resolvent for x in resolvent):
                ket_qua.append(frozenset(resolvent))
    return ket_qua


def dinh_dang_clause(c):
    if not c:
        return "{}"
    return " v ".join(sorted(c, key=lambda x: x.lstrip('~')))


def chung_minh_hop_giai(kb_clauses, neg_alpha_clauses):
    clauses = [frozenset(c) for c in kb_clauses] + [frozenset(c) for c in neg_alpha_clauses]
    da_co = set(clauses)
    lich_su = []

    buoc = 1
    for c in clauses:
        lich_su.append(f"  ({buoc}) {dinh_dang_clause(c)} [Gia thiet KB ^ ~alpha]")
        buoc += 1

    while True:
        moi_sinh = []
        n = len(clauses)
        for i in range(n):
            for j in range(i + 1, n):
                for res in hop_giai_hai_menh_de(clauses[i], clauses[j]):
                    if not res:
                        lich_su.append(
                            f"  ({buoc}) {{}} (Mau thuan! Hop giai tu ({i+1}) [{dinh_dang_clause(clauses[i])}] "
                            f"va ({j+1}) [{dinh_dang_clause(clauses[j])}])"
                        )
                        return True, lich_su
                    if res not in da_co:
                        da_co.add(res)
                        moi_sinh.append(res)
                        lich_su.append(
                            f"  ({buoc}) {dinh_dang_clause(res)} "
                            f"[Hop giai ({i+1}) va ({j+1})]"
                        )
                        buoc += 1
        if not moi_sinh:
            return False, lich_su
        clauses.extend(moi_sinh)


if __name__ == '__main__':
    # Vi du tren Slide 44-46 Chuong 6:
    # KB = { p ^ q, p -> r, (q ^ r) -> s }, can chung minh: s
    # Chuyen KB ve CNF: {p}, {q}, {~p, r}, {~q, ~r, s}; Phu dinh ket luan: {~s}
    KB_CNF = [
        {'p'},
        {'q'},
        {'~p', 'r'},
        {'~q', '~r', 's'},
    ]
    NEG_ALPHA = [{'~s'}]

    thanh_cong, cac_buoc = chung_minh_hop_giai(KB_CNF, NEG_ALPHA)
    print("Chung minh bang Hop giai (Slide 44-46 Chuong 6):")
    for dong in cac_buoc:
        print(dong)
    print(f"=> Ket luan: {'Chung minh thanh cong (KB |= alpha)' if thanh_cong else 'Khong chung minh duoc'}")
'''

SKELETON_LOGIC_SAT_CSP_LOCAL = '''import random
from simpleai.search import (
    CspProblem,
    SearchProblem,
    backtrack,
    MOST_CONSTRAINED_VARIABLE,
    LEAST_CONSTRAINING_VALUE,
)
from simpleai.search.local import hill_climbing, simulated_annealing

# Bai toan chung minh thoa man SAT (Slide 38-39 Chuong 6):
# Bieu thuc CNF: (p v q v ~r) ^ (~p v ~r v s) ^ (~p v q v ~t)
# Giai bang ca 2 phuong phap tren slide:
# 1. Dua ve bai toan CSP (Backtracking)
# 2. Dua ve Tim kiem cuc bo (Hill-Climbing / Simulated Annealing toi da hoa so menh de dung)

VARIABLES = ('p', 'q', 'r', 's', 't')

# Moi menh de CNF la danh sach cac literal: ('p', True) nghia la p, ('r', False) nghia la ~r
MENH_DE_CNF = (
    (('p', True), ('q', True), ('r', False)),     # p v q v ~r
    (('p', False), ('r', False), ('s', True)),    # ~p v ~r v s
    (('p', False), ('q', True), ('t', False)),    # ~p v q v ~t
)


def kiem_tra_clause(clause, bang_gan):
    return any(bang_gan[bien] == gia_tri_mong_muon for bien, gia_tri_mong_muon in clause)


def tao_rang_buoc_csp(clause):
    bien_clause = tuple(b for b, _ in clause)

    def thoa_clause(variables, values):
        bang = dict(zip(variables, values))
        return kiem_tra_clause(clause, bang)

    return bien_clause, thoa_clause


class SATLocalProblem(SearchProblem):
    def actions(self, state):
        # Doi gia tri (True <-> False) cua 1 bien bat ky
        return list(range(len(VARIABLES)))

    def result(self, state, action):
        moi = list(state)
        moi[action] = not moi[action]
        return tuple(moi)

    def value(self, state):
        # Heuristic tren Slide 39 Chuong 6: So menh de CNF duoc thoa man
        bang = dict(zip(VARIABLES, state))
        return sum(1 for cl in MENH_DE_CNF if kiem_tra_clause(cl, bang))

    def generate_random_state(self):
        return tuple(random.choice([False, True]) for _ in VARIABLES)


if __name__ == '__main__':
    # Cach 1: Giai SAT bang CSP Backtrack
    domains = {v: [False, True] for v in VARIABLES}
    constraints = [tao_rang_buoc_csp(cl) for cl in MENH_DE_CNF]
    csp_prob = CspProblem(VARIABLES, domains, constraints)
    nghiem_csp = backtrack(
        csp_prob,
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )
    print("1. Giai SAT bang CSP Backtrack (Slide 38-39 Chuong 6):")
    print("   Nghiem:", nghiem_csp)

    # Cach 2: Giai SAT bang Local Search (Hill Climbing & Simulated Annealing)
    random.seed(42)
    init_st = tuple(False for _ in VARIABLES)
    local_prob = SATLocalProblem(init_st)
    kq_hc = hill_climbing(local_prob)
    kq_sa = simulated_annealing(local_prob, iterations_limit=100)
    print("2. Giai SAT bang Hill Climbing:")
    print(f"   Nghiem = {dict(zip(VARIABLES, kq_hc.state))}, So menh de dung = {kq_hc.value}/{len(MENH_DE_CNF)}")
    print("3. Giai SAT bang Simulated Annealing:")
    print(f"   Nghiem = {dict(zip(VARIABLES, kq_sa.state))}, So menh de dung = {kq_sa.value}/{len(MENH_DE_CNF)}")
'''

SKELETON_ML_CLASSIFIERS_SIMPLEAI = '''import math
import sys
import types

# Dam bao simpleai.machine_learning chay duoc ngay ca khi may phong lab chua cai numpy
try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules['numpy'] = types.SimpleNamespace(
        exp=math.exp,
        logaddexp=types.SimpleNamespace(
            reduce=lambda xs: math.log(sum(math.exp(x) for x in xs))
        ),
    )

from simpleai.machine_learning import (
    ClassificationProblem,
    VectorDataClassificationProblem,
    DecisionTreeLearner_Queued,
    KNearestNeighbors,
    is_attribute,
)
from simpleai.machine_learning.classifiers import tree_to_str

# Phan lop du lieu voi simpleai.machine_learning (DecisionTreeLearner ID3 & K-Nearest Neighbors)
# Tap du lieu mau: [Thoi_tiet, Nhiet_do, Do_am, Co_gio, Choi_the_thao]
DU_LIEU = [
    ['Nang', 'Nong', 'Cao', False, 'Khong'],
    ['Nang', 'Nong', 'Cao', True, 'Khong'],
    ['Am u', 'Nong', 'Cao', False, 'Co'],
    ['Mua', 'Mat', 'Cao', False, 'Co'],
    ['Mua', 'Lanh', 'Binh thuong', False, 'Co'],
    ['Mua', 'Lanh', 'Binh thuong', True, 'Khong'],
    ['Am u', 'Lanh', 'Binh thuong', True, 'Co'],
    ['Nang', 'Mat', 'Cao', False, 'Khong'],
    ['Nang', 'Lanh', 'Binh thuong', False, 'Co'],
    ['Mua', 'Mat', 'Binh thuong', False, 'Co'],
    ['Nang', 'Mat', 'Binh thuong', True, 'Co'],
    ['Am u', 'Mat', 'Cao', True, 'Co'],
    ['Am u', 'Nong', 'Binh thuong', False, 'Co'],
    ['Mua', 'Mat', 'Cao', True, 'Khong'],
]


class BaiToanPhanLop(VectorDataClassificationProblem):
    def distance(self, a, b):
        # Khoang cach Hamming cho KNN (khong tinh cot nhan cuoi cung)
        return sum(1 for i in range(len(a) - 1) if a[i] != b[i])


if __name__ == '__main__':
    problem = BaiToanPhanLop(DU_LIEU, target_index=4)

    # 1. Cay quyet dinh ID3 (DecisionTreeLearner_Queued)
    dt = DecisionTreeLearner_Queued(DU_LIEU, problem)
    print("Cay quyet dinh ID3 (DecisionTreeLearner):")
    print(tree_to_str(dt.root))

    mau_thu = ['Nang', 'Mat', 'Binh thuong', False, None]
    print(f"\\nDu doan mau {mau_thu[:-1]}:")
    print("  - DecisionTreeLearner:", dt.classify(mau_thu))

    # 2. K-Nearest Neighbors (KNN)
    knn = KNearestNeighbors(DU_LIEU, problem, k=3)
    print("  - KNearestNeighbors (k=3):", knn.classify(mau_thu))
'''

SKELETON_ML_REINFORCEMENT_SIMPLEAI = '''import math
import random
import sys
import types

try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules['numpy'] = types.SimpleNamespace(
        exp=math.exp,
        logaddexp=types.SimpleNamespace(
            reduce=lambda xs: math.log(sum(math.exp(x) for x in xs))
        ),
    )

from simpleai.environments import RLEnvironment
from simpleai.machine_learning.reinforcement_learning import (
    RLProblem,
    TDQLearner,
    SARSALearner,
    make_exponential_temperature,
)

# Hoc tang cuong (Q-Learning & SARSA) tren luoi 1D (0 -> 1 -> 2 -> 3 -> 4 [Dich])
# bang simpleai.machine_learning.reinforcement_learning
TRANG_THAI_DICH = 4


class BaiToanRL(RLProblem):
    def actions(self, state):
        if state == TRANG_THAI_DICH:
            return []
        ds = []
        if state > 0:
            ds.append('TRAI')
        if state < TRANG_THAI_DICH:
            ds.append('PHAI')
        return ds


class MoiTruongRL(RLEnvironment):
    def do_action(self, state, action, agent):
        if action == 'PHAI':
            return min(TRANG_THAI_DICH, state + 1)
        if action == 'TRAI':
            return max(0, state - 1)
        return state

    def is_completed(self, state):
        return state == TRANG_THAI_DICH

    def reward(self, state, agent):
        return 10.0 if state == TRANG_THAI_DICH else -1.0


if __name__ == '__main__':
    random.seed(42)
    rl_prob = BaiToanRL()
    q_agent = TDQLearner(
        rl_prob,
        temperature_function=make_exponential_temperature(1.0, 0.05),
        discount_factor=0.9,
    )
    env = MoiTruongRL([q_agent], initial_state=0)
    for _ in range(40):
        env.run(steps=20)

    print("Bang Q-Table sau khi hoc voi TDQLearner (SimpleAI):")
    for st in range(TRANG_THAI_DICH):
        print(f"  State {st}: {dict(q_agent.Q[st])}")
'''

CSP_LOGIC_ML_VARIANT_SKELETONS: Dict[str, Dict[str, Any]] = {
    "csp_numeric_equations": {
        "id": "csp_numeric_equations",
        "category": "csp",
        "title": "Giai He phuong trinh / Bat phuong trinh Rang buoc So hoc (x1..x6, A..E - Slide Chuong 5)",
        "keywords": [
            "x1+x2+x6=1", "x1-x3+x4=1", "b+8<d", "c=5*e", "a=3*e",
            "he phuong trinh csp", "convert_to_binary", "mien gia tri {0,1}", "1..10"
        ],
        "code": SKELETON_CSP_NUMERIC_EQUATIONS,
    },
    "csp_convert_to_binary_ac3": {
        "id": "csp_convert_to_binary_ac3",
        "category": "csp",
        "title": "Thuat toan Phu hop canh AC-3 (arc_consistency_3, revise) & convert_to_binary (Slide 35-39 Chuong 5)",
        "keywords": [
            "ac-3", "ac3", "arc_consistency_3", "revise", "all_arcs",
            "phu hop canh", "lan truyen rang buoc", "convert_to_binary"
        ],
        "code": SKELETON_CSP_CONVERT_BINARY_AC3,
    },
    "csp_two_plus_two_carry": {
        "id": "csp_two_plus_two_carry",
        "category": "csp",
        "title": "Bai toan Mat ma so hoc TWO + TWO = FOUR voi bien nho X1, X2, X3 (Slide 10 Chuong 5)",
        "keywords": [
            "two + two = four", "x1", "x2", "x3", "bien nho",
            "o + o = r + 10", "mat ma so hoc", "slide 10"
        ],
        "code": SKELETON_CSP_TWO_PLUS_TWO_CARRY,
    },
    "csp_sudoku": {
        "id": "csp_sudoku",
        "category": "csp",
        "title": "Giai Sudoku 9x9 & 4x4 bang CspProblem + AC-3 + Backtrack (MRV + LCV)",
        "keywords": [
            "sudoku", "bang_sudoku", "9x9", "4x4", "dien so sudoku"
        ],
        "code": SKELETON_CSP_SUDOKU,
    },
    "csp_job_scheduling": {
        "id": "csp_job_scheduling",
        "category": "csp",
        "title": "Bai toan Xep lich cong viec / Job Shop Scheduling (StartJob1 + d <= StartJob3 - Slide 8 Chuong 5)",
        "keywords": [
            "startjob", "xep lich cong viec", "job scheduling", "thoi gian bat dau",
            "cong viec", "job1", "job2", "job3"
        ],
        "code": SKELETON_CSP_JOB_SCHEDULING,
    },
    "logic_truth_table": {
        "id": "logic_truth_table",
        "category": "logic",
        "title": "Lap Bang chan ly (Truth Table) & Chung minh KB |= alpha (Slide 20-28 Chuong 6)",
        "keywords": [
            "bang chan ly", "truth table", "truth-table", "kb |= alpha",
            "bao ham", "tautology", "mau thuan", "contradiction", "logic dinh de"
        ],
        "code": SKELETON_LOGIC_TRUTH_TABLE,
    },
    "logic_cnf_resolution": {
        "id": "logic_cnf_resolution",
        "category": "logic",
        "title": "Chung minh bang Hop giai phan chung (Resolution Refutation) tren CNF (Slide 36-46 Chuong 6)",
        "keywords": [
            "hop giai", "resolution", "refutation", "phan chung", "cnf",
            "dang chuan ket hop", "menh de rong", "{}"
        ],
        "code": SKELETON_LOGIC_CNF_RESOLUTION,
    },
    "logic_sat_csp_local": {
        "id": "logic_sat_csp_local",
        "category": "logic",
        "title": "Bai toan Chung minh Thoa man SAT bang CSP Backtrack & Local Search (Slide 38-39 Chuong 6)",
        "keywords": [
            "bai toan sat", "satisfiability", "walk-sat", "walksat",
            "chung minh thoa man", "menh de cnf"
        ],
        "code": SKELETON_LOGIC_SAT_CSP_LOCAL,
    },
    "ml_classifiers_simpleai": {
        "id": "ml_classifiers_simpleai",
        "category": "logic",
        "title": "Phan lop du lieu bang simpleai.machine_learning (DecisionTreeLearner ID3, KNN)",
        "keywords": [
            "decisiontreelearner", "knearestneighbors", "naivebayes",
            "classificationproblem", "vectordataclassificationproblem",
            "tree_to_str", "id3", "cay quyet dinh", "simpleai.machine_learning"
        ],
        "code": SKELETON_ML_CLASSIFIERS_SIMPLEAI,
    },
    "ml_reinforcement_simpleai": {
        "id": "ml_reinforcement_simpleai",
        "category": "logic",
        "title": "Hoc tang cuong Q-Learning & SARSA bang simpleai.machine_learning.reinforcement_learning",
        "keywords": [
            "tdqlearner", "sarsalearner", "rlenvironment", "rlproblem",
            "q-learning", "qlearner", "hoc tang cuong", "reinforcement_learning"
        ],
        "code": SKELETON_ML_REINFORCEMENT_SIMPLEAI,
    },
}
