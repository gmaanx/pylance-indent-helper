# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Mo Rong 1: Toan bo cac bai toan trong Slide Chuong 2, 3, 4 (UEH)
va cac bien the de thi Tìm kiem / Local Search / Environments cua SimpleAI.
"""

from typing import Any, Dict

SKELETON_VACUUM_WORLD = '''import time
from simpleai.search import (
    SearchProblem,
    breadth_first,
    depth_first,
    uniform_cost,
    astar,
)

# Bai toan May hut bui (Vacuum World - Chuong 3 Slide 8-17)
# Trang thai: (vi_tri_may, trang_thai_phong_A, trang_thai_phong_B)
# vi_tri_may: 'A' hoac 'B'; trang_thai_phong: 'Ban' hoac 'Sach'
# 8 trang thai chuan tren slide:
# #1: ('A','Ban','Ban'), #2: ('B','Ban','Ban'), #3: ('A','Ban','Sach'), #4: ('B','Ban','Sach')
# #5: ('A','Sach','Ban'), #6: ('B','Sach','Ban'), #7: ('A','Sach','Sach'), #8: ('B','Sach','Sach')
INITIAL = ('A', 'Sach', 'Ban')  # Trang thai #5 tren slide


class MayHutBuiProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        vi_tri, phong_a, phong_b = state
        ds = []
        if (vi_tri == 'A' and phong_a == 'Ban') or (vi_tri == 'B' and phong_b == 'Ban'):
            ds.append('Hut bui')
        if vi_tri == 'A':
            ds.append('Sang phai')
        else:
            ds.append('Sang trai')
        return ds

    def result(self, state, action):
        vi_tri, phong_a, phong_b = state
        if action == 'Hut bui':
            if vi_tri == 'A':
                return ('A', 'Sach', phong_b)
            return ('B', phong_a, 'Sach')
        if action == 'Sang phai':
            return ('B', phong_a, phong_b)
        if action == 'Sang trai':
            return ('A', phong_a, phong_b)
        return state

    def is_goal(self, state):
        self.so_nut_xet += 1
        _, phong_a, phong_b = state
        return phong_a == 'Sach' and phong_b == 'Sach'

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        _, phong_a, phong_b = state
        return (1 if phong_a == 'Ban' else 0) + (1 if phong_b == 'Ban' else 0)


def chay(ten, thuat_toan):
    problem = MayHutBuiProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    cac_hanh_dong = [act for act, _ in ket_qua.path() if act is not None]
    print(f"{ten:<10}: Giai phap = {cac_hanh_dong} | Dich = {ket_qua.state} | "
          f"Chi phi = {ket_qua.cost}, So nut xet = {problem.so_nut_xet}, {thoi_gian:.4f}s")


if __name__ == '__main__':
    print(f"Bai toan May hut bui (Trang thai don) - Bat dau: {INITIAL}\\n")
    chay("BFS", breadth_first)
    chay("UCS", uniform_cost)
    chay("DFS", depth_first)
    chay("A*", astar)
'''

SKELETON_SENSORLESS_VACUUM = '''import time
from simpleai.search import SearchProblem, breadth_first, astar

# Bai toan May hut bui thieu cam nhan (Sensorless Vacuum World - Chuong 3 Slide 10-11)
# Moi trang thai vat ly: (vi_tri, ban_A, ban_B) trong do ban_A, ban_B in {0, 1} (1 la ban, 0 la sach)
# Trang thai niem tin (Belief state): frozenset chua cac trang thai vat ly co the xay ra.
TAT_CA_TRANG_THAI = frozenset(
    (vt, a, b)
    for vt in ('A', 'B')
    for a in (0, 1)
    for b in (0, 1)
)


def chuyen_vat_ly(st, action):
    vt, a, b = st
    if action == 'Sang phai':
        return ('B', a, b)
    if action == 'Sang trai':
        return ('A', a, b)
    if action == 'Hut bui':
        return ('A', 0, b) if vt == 'A' else ('B', a, 0)
    return st


class MayHutBuiThieuCamNhan(SearchProblem):
    def __init__(self, initial_state=TAT_CA_TRANG_THAI):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        return ['Sang phai', 'Hut bui', 'Sang trai']

    def result(self, state, action):
        return frozenset(chuyen_vat_ly(s, action) for s in state)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return all(a == 0 and b == 0 for _, a, b in state)

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        return max((a + b for _, a, b in state), default=0)


if __name__ == '__main__':
    problem = MayHutBuiThieuCamNhan(TAT_CA_TRANG_THAI)
    bat_dau = time.perf_counter()
    ket_qua = breadth_first(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    giai_phap = [act for act, _ in ket_qua.path() if act is not None]
    print(f"Bai toan May hut bui thieu cam nhan (Bat dau voi {len(TAT_CA_TRANG_THAI)} trang thai):")
    print(f"  Giai phap: {giai_phap}")
    print(f"  So buoc = {ket_qua.cost}, So nut xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
    for buoc, (act, st) in enumerate(ket_qua.path()):
        print(f"  Buoc {buoc}: {str(act or 'Bat dau'):<12} -> Con {len(st)} trang thai kha di: {sorted(st)}")
'''

SKELETON_SIMPLEAI_ENVIRONMENT = '''from simpleai.environments import Environment

# Mo phong Tac tu (Agent) va Moi truong (Environment) bang simpleai.environments


class TacTuMayHutBui:
    def __init__(self):
        self.lich_su = []

    def program(self, percept):
        vi_tri, trang_thai_o = percept
        if trang_thai_o == 'Ban':
            hanh_dong = 'Hut bui'
        elif vi_tri == 'A':
            hanh_dong = 'Sang phai'
        else:
            hanh_dong = 'Sang trai'
        self.lich_su.append((percept, hanh_dong))
        return hanh_dong


class MoiTruongHutBui(Environment):
    def percept(self, agent, state):
        vi_tri, phong = state
        return (vi_tri, phong[vi_tri])

    def do_action(self, state, action, agent):
        vi_tri, phong = state
        phong_moi = dict(phong)
        if action == 'Hut bui':
            phong_moi[vi_tri] = 'Sach'
        elif action == 'Sang phai':
            vi_tri = 'B'
        elif action == 'Sang trai':
            vi_tri = 'A'
        return (vi_tri, phong_moi)

    def is_completed(self, state):
        _, phong = state
        return all(v == 'Sach' for v in phong.values())


if __name__ == '__main__':
    tac_tu = TacTuMayHutBui()
    trang_thai_dau = ('A', {'A': 'Sach', 'B': 'Ban'})
    mt = MoiTruongHutBui([tac_tu], trang_thai_dau)
    mt.run(steps=10)

    print("Mo phong Tac tu trong Moi truong (simpleai.environments.Environment):")
    for buoc, (nhan_thuc, hanh_dong) in enumerate(tac_tu.lich_su, start=1):
        print(f"  Buoc {buoc}: Nhan thuc = {nhan_thuc} -> Hanh dong = {hanh_dong}")
    print(f"Trang thai cuoi: {mt.state}")
'''

SKELETON_TREE_ABC_SLIDE = '''import time
from simpleai.search import (
    SearchProblem,
    breadth_first,
    uniform_cost,
    depth_first,
    limited_depth_first,
    iterative_limited_depth_first,
    greedy,
    astar,
)
from simpleai.search.viewers import BaseViewer

# Cay tim kiem tren Slide Chuong 3 (A -> B, C -> D, E, F, G -> H..O)
CAY = {
    'A': [('B', 1), ('C', 1)],
    'B': [('D', 1), ('E', 1)],
    'C': [('F', 1), ('G', 1)],
    'D': [('H', 1), ('I', 1)],
    'E': [('J', 1), ('K', 1)],
    'F': [('L', 1), ('M', 1)],
    'G': [('N', 1), ('O', 1)],
}

HEURISTIC = {
    'A': 3, 'B': 2, 'C': 2, 'D': 1, 'E': 1, 'F': 1, 'G': 1,
    'H': 0, 'I': 0, 'J': 0, 'K': 0, 'L': 0, 'M': 0, 'N': 0, 'O': 0,
}

INITIAL = 'A'
GOAL = 'M'


class CayTimKiemProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.thu_tu_duyet = []

    def actions(self, state):
        return [con for con, _ in CAY.get(state, [])]

    def result(self, state, action):
        return action

    def is_goal(self, state):
        self.thu_tu_duyet.append(state)
        return state == GOAL

    def cost(self, state, action, state2):
        for con, chi_phi in CAY.get(state, []):
            if con == state2:
                return chi_phi
        return 1

    def heuristic(self, state):
        return HEURISTIC.get(state, 0)


def chay(ten, thuat_toan, **kwargs):
    problem = CayTimKiemProblem(INITIAL)
    viewer = BaseViewer()
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, viewer=viewer, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    duyet = ' -> '.join(problem.thu_tu_duyet)
    if ket_qua is None:
        print(f"{ten:<16}: Khong tim thay | Thu tu xet: {duyet}")
    else:
        duong = ' -> '.join(s for _, s in ket_qua.path())
        print(f"{ten:<16}: Duong di = {duong:<18} | Chi phi = {ket_qua.cost} | "
              f"Max fringe = {viewer.stats['max_fringe_size']:2d} | Thu tu xet ({len(problem.thu_tu_duyet)} nut): {duyet}")


if __name__ == '__main__':
    print(f"Tim kiem tren cay tu {INITIAL} den {GOAL}:\\n")
    chay("BFS", breadth_first)
    chay("UCS", uniform_cost)
    chay("DFS", depth_first)
    chay("DLS (l=2)", limited_depth_first, depth_limit=2)
    chay("DLS (l=3)", limited_depth_first, depth_limit=3)
    chay("IDS", iterative_limited_depth_first)
    chay("Greedy", greedy)
    chay("A*", astar)
'''

SKELETON_LOCAL_8PUZZLE_HILL_CLIMBING = '''import random
import time
from simpleai.search import SearchProblem
from simpleai.search.local import (
    hill_climbing,
    hill_climbing_stochastic,
    hill_climbing_random_restarts,
    beam,
    beam_best_first,
    simulated_annealing,
    genetic,
)

# Tim kiem cuc bo (Leo doi / Simulated Annealing / Beam / Genetic) cho bai toan 8-Puzzle
# Bam sat Slide 34-35 Chuong 4: f(n) = -(So luong cac o chu nam sai vi tri) hoac -(Khoang cach Manhattan)
GOAL = (
    (1, 2, 3),
    (8, 0, 4),
    (7, 6, 5),
)

INITIAL = (
    (2, 8, 3),
    (1, 6, 4),
    (7, 0, 5),
)

HUONG = {
    'UP': (-1, 0),
    'DOWN': (1, 0),
    'LEFT': (0, -1),
    'RIGHT': (0, 1),
}

VI_TRI_DICH = {GOAL[r][c]: (r, c) for r in range(3) for c in range(3)}


def tim_o_trong(state):
    for r in range(3):
        for c in range(3):
            if state[r][c] == 0:
                return r, c
    return 0, 0


class PuzzleLocalProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL, mode='manhattan'):
        super().__init__(initial_state)
        self.mode = mode

    def actions(self, state):
        r, c = tim_o_trong(state)
        return [ten for ten, (dr, dc) in HUONG.items()
                if 0 <= r + dr < 3 and 0 <= c + dc < 3]

    def result(self, state, action):
        r, c = tim_o_trong(state)
        dr, dc = HUONG[action]
        mt = [list(hang) for hang in state]
        mt[r][c], mt[r + dr][c + dc] = mt[r + dr][c + dc], mt[r][c]
        return tuple(tuple(hang) for hang in mt)

    def so_o_sai(self, state):
        return sum(
            state[r][c] != 0 and state[r][c] != GOAL[r][c]
            for r in range(3) for c in range(3)
        )

    def khoang_cach_manhattan(self, state):
        tong = 0
        for r in range(3):
            for c in range(3):
                val = state[r][c]
                if val != 0:
                    gr, gc = VI_TRI_DICH[val]
                    tong += abs(r - gr) + abs(c - gc)
        return tong

    def value(self, state):
        # SimpleAI cuc dai hoa value -> lay am cua do lech so voi GOAL (toi da = 0 khi dat GOAL)
        if self.mode == 'misplaced':
            return -self.so_o_sai(state)
        return -self.khoang_cach_manhattan(state)

    def generate_random_state(self):
        # Sinh trang thai ngau nhien giai duoc bang cach di ngau nhien tu GOAL
        st = GOAL
        for _ in range(12):
            act = random.choice(self.actions(st))
            st = self.result(st, act)
        return st

    def crossover(self, state1, state2):
        flat1 = [x for row in state1 for x in row]
        flat2 = [x for row in state2 for x in row]
        cut = random.randrange(1, 8)
        con = flat1[:cut] + [x for x in flat2 if x not in flat1[:cut]]
        return (tuple(con[0:3]), tuple(con[3:6]), tuple(con[6:9]))

    def mutate(self, state):
        acts = self.actions(state)
        return self.result(state, random.choice(acts))


def in_ma_tran(state):
    for hang in state:
        print('    ' + ' '.join(str(x) if x != 0 else '_' for x in hang))


def chay(ten, thuat_toan, mode='manhattan', **kwargs):
    random.seed(42)
    problem = PuzzleLocalProblem(INITIAL, mode=mode)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    st = ket_qua.state
    print(f"\\n{ten} ({mode}):")
    in_ma_tran(st)
    print(f"  Value = {problem.value(st)} | Sai vi tri = {problem.so_o_sai(st)} | "
          f"Manhattan = {problem.khoang_cach_manhattan(st)} | Dat dich = {st == GOAL} | {thoi_gian:.4f}s")


if __name__ == '__main__':
    print("Bai toan 8-Puzzle bang Tim kiem cuc bo (Slide 34-35 Chuong 4):")
    chay("Hill climbing", hill_climbing, mode='misplaced')
    chay("Hill climbing", hill_climbing, mode='manhattan')
    chay("Stochastic hill climbing", hill_climbing_stochastic, iterations_limit=100)
    chay("Hill climbing random restarts", hill_climbing_random_restarts, restarts_limit=10, iterations_limit=50)
    chay("Beam search", beam, beam_size=15, iterations_limit=50)
    chay("Simulated annealing", simulated_annealing, iterations_limit=300)
'''

SKELETON_15PUZZLE_NPuzzle = '''import time
from simpleai.search import SearchProblem, astar

# Bai toan N-Puzzle tong quat (15-Puzzle 4x4 hoac KxK bat ky)
GOAL = (
    (1, 2, 3, 4),
    (5, 6, 7, 8),
    (9, 10, 11, 12),
    (13, 14, 15, 0),
)

INITIAL = (
    (1, 2, 3, 4),
    (5, 6, 0, 8),
    (9, 10, 7, 11),
    (13, 14, 15, 12),
)

KICH_THUOC = len(GOAL)
HUONG = {'UP': (-1, 0), 'DOWN': (1, 0), 'LEFT': (0, -1), 'RIGHT': (0, 1)}
VI_TRI_DICH = {
    GOAL[r][c]: (r, c)
    for r in range(KICH_THUOC)
    for c in range(KICH_THUOC)
}


class NPuzzleProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def tim_khong(self, state):
        for r in range(KICH_THUOC):
            for c in range(KICH_THUOC):
                if state[r][c] == 0:
                    return r, c
        return 0, 0

    def actions(self, state):
        r, c = self.tim_khong(state)
        return [ten for ten, (dr, dc) in HUONG.items()
                if 0 <= r + dr < KICH_THUOC and 0 <= c + dc < KICH_THUOC]

    def result(self, state, action):
        r, c = self.tim_khong(state)
        dr, dc = HUONG[action]
        mt = [list(hang) for hang in state]
        mt[r][c], mt[r + dr][c + dc] = mt[r + dr][c + dc], mt[r][c]
        return tuple(tuple(hang) for hang in mt)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        tong = 0
        for r in range(KICH_THUOC):
            for c in range(KICH_THUOC):
                val = state[r][c]
                if val != 0:
                    gr, gc = VI_TRI_DICH[val]
                    tong += abs(r - gr) + abs(c - gc)
        return tong


if __name__ == '__main__':
    problem = NPuzzleProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = astar(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    cac_buoc = [act for act, _ in ket_qua.path() if act is not None]
    print(f"Bai toan {KICH_THUOC*KICH_THUOC - 1}-Puzzle ({KICH_THUOC}x{KICH_THUOC}):")
    print(f"  So buoc = {ket_qua.cost}: {' -> '.join(cac_buoc)}")
    print(f"  So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
'''

SKELETON_MULTI_GOAL_GRID = '''import time
from simpleai.search import SearchProblem, breadth_first, uniform_cost, astar

# Bai toan Robot tim duong tren luoi 2D thu thap tat ca cac diem dich / chia khoa / kho bau
# 0: o trong (chi phi 1), 1: tuong chan, >1: chi phi dia hinh cua o
LUOI = (
    (0, 0, 1, 0, 0),
    (0, 1, 1, 0, 1),
    (0, 0, 0, 0, 0),
    (1, 0, 1, 1, 0),
    (0, 0, 0, 0, 0),
)
SO_HANG = len(LUOI)
SO_COT = len(LUOI[0])

XUAT_PHAT = (0, 0)
CAC_DIEM_CAN_THU_THAP = frozenset({(0, 4), (4, 0)})
CUA_RA = (4, 4)

# Trang thai: (hang, cot, frozenset_cac_diem_da_di_qua)
INITIAL = (XUAT_PHAT[0], XUAT_PHAT[1], frozenset())

HUONG = {'UP': (-1, 0), 'DOWN': (1, 0), 'LEFT': (0, -1), 'RIGHT': (0, 1)}


class RobotThuThapProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        r, c, _ = state
        ds = []
        for ten, (dr, dc) in HUONG.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr < SO_HANG and 0 <= nc < SO_COT and LUOI[nr][nc] != 1:
                ds.append(ten)
        return ds

    def result(self, state, action):
        r, c, da_thu = state
        dr, dc = HUONG[action]
        nr, nc = r + dr, c + dc
         if (nr, nc) in CAC_DIEM_CAN_THU_THAP:
            da_thu = da_thu | {(nr, nc)}
        return (nr, nc, da_thu)

    def is_goal(self, state):
        self.so_nut_xet += 1
        r, c, da_thu = state
        return da_thu == CAC_DIEM_CAN_THU_THAP and (r, c) == CUA_RA

    def cost(self, state, action, state2):
        nr, nc, _ = state2
        val = LUOI[nr][nc]
        return val if val > 1 else 1

    def heuristic(self, state):
        r, c, da_thu = state
        con_thieu = CAC_DIEM_CAN_THU_THAP - da_thu
        if not con_thieu:
            return abs(r - CUA_RA[0]) + abs(c - CUA_RA[1])
        kc_gan_nhat = min(abs(r - kr) + abs(c - kc) for kr, kc in con_thieu)
        kc_ra_cua = min(abs(kr - CUA_RA[0]) + abs(kc - CUA_RA[1]) for kr, kc in con_thieu)
        return kc_gan_nhat + kc_ra_cua


if __name__ == '__main__':
    problem = RobotThuThapProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = astar(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    duong_di = [(st[0], st[1]) for _, st in ket_qua.path()]
    print(f"Robot thu thap {sorted(CAC_DIEM_CAN_THU_THAP)} va toi {CUA_RA}:")
    print(f"  So buoc = {ket_qua.cost}, So nut xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
    print(f"  Lo trinh: {' -> '.join(str(p) for p in duong_di)}")
'''

SKELETON_MULTI_GOAL_GRID = SKELETON_MULTI_GOAL_GRID.replace("\n         if (nr, nc)", "\n        if (nr, nc)")

SKELETON_KNIGHT_SHORTEST_PATH = '''import time
from simpleai.search import SearchProblem, breadth_first, astar

# Bai toan Tim duong di ngan nhat cua Quan Ma (Knight) tren ban co NxN
N = 8
INITIAL = (0, 0)
GOAL = (7, 7)

BUOC_NHAY_MA = (
    (-2, -1), (-2, 1), (-1, -2), (-1, 2),
    (1, -2), (1, 2), (2, -1), (2, 1),
)


class QuanMaProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        r, c = state
        return [
            (dr, dc) for dr, dc in BUOC_NHAY_MA
            if 0 <= r + dr < N and 0 <= c + dc < N
        ]

    def result(self, state, action):
        return (state[0] + action[0], state[1] + action[1])

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        return (abs(state[0] - GOAL[0]) + abs(state[1] - GOAL[1])) / 3.0


if __name__ == '__main__':
    for ten, thuat_toan in [('BFS', breadth_first), ('A*', astar)]:
        problem = QuanMaProblem(INITIAL)
        bat_dau = time.perf_counter()
        ket_qua = thuat_toan(problem, graph_search=True)
        thoi_gian = time.perf_counter() - bat_dau
        duong = ' -> '.join(str(st) for _, st in ket_qua.path())
        print(f"{ten:<5}: {duong} | So buoc = {ket_qua.cost}, So nut xet = {problem.so_nut_xet}, {thoi_gian:.4f}s")
'''

SKELETON_WOLF_GOAT_CABBAGE = '''import time
from simpleai.search import SearchProblem, breadth_first, depth_first, astar

# Bai toan Nguoi nong dan qua song voi Soi, De, Bap cai (Wolf, Goat, Cabbage)
# Trang thai: (Nong_dan, Soi, De, Bap_cai) trong do 0 = Bo Trai, 1 = Bo Phai
INITIAL = (0, 0, 0, 0)
GOAL = (1, 1, 1, 1)


def an_toan(state):
    nd, soi, de, bap = state
    # Soi an De neu o cung bo ma khong co Nong dan
    if soi == de and nd != soi:
        return False
    # De an Bap cai neu o cung bo ma khong co Nong dan
    if de == bap and nd != de:
        return False
    return True


class SoiDeBapCaiProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        nd, soi, de, bap = state
        bo_moi = 1 - nd
        ung_vien = [
            ('Di mot minh', (bo_moi, soi, de, bap)),
            ('Cho Soi', (bo_moi, bo_moi, de, bap) if soi == nd else None),
            ('Cho De', (bo_moi, soi, bo_moi, bap) if de == nd else None),
            ('Cho Bap cai', (bo_moi, soi, de, bo_moi) if bap == nd else None),
        ]
        return [ten for ten, st_moi in ung_vien if st_moi is not None and an_toan(st_moi)]

    def result(self, state, action):
        nd, soi, de, bap = state
        bo_moi = 1 - nd
        if action == 'Di mot minh':
            return (bo_moi, soi, de, bap)
        if action == 'Cho Soi':
            return (bo_moi, bo_moi, de, bap)
        if action == 'Cho De':
            return (bo_moi, soi, bo_moi, bap)
        return (bo_moi, soi, de, bo_moi)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        return sum(1 - x for x in state) / 2.0


if __name__ == '__main__':
    problem = SoiDeBapCaiProblem(INITIAL)
    ket_qua = breadth_first(problem, graph_search=True)
    print(f"Bai toan Soi - De - Bap cai: So buoc = {ket_qua.cost}, So nut xet = {problem.so_nut_xet}")
    for buoc, (act, st) in enumerate(ket_qua.path()):
        print(f"  Buoc {buoc}: {str(act or 'Bat dau'):<15} -> {st}")
'''

SKELETON_COIN_CHANGE_NUMBER = '''import time
from simpleai.search import SearchProblem, breadth_first, uniform_cost, astar

# Bai toan Doi tien it to nhat / Bien doi so bang SimpleAI SearchProblem
MENH_GIA = (1, 2, 5, 10, 20, 50)
SO_TIEN_CAN_DOI = 68
INITIAL = 0
GOAL = SO_TIEN_CAN_DOI


class DoiTienProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        return [mg for mg in MENH_GIA if state + mg <= GOAL]

    def result(self, state, action):
        return state + action

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        return (GOAL - state) / max(MENH_GIA)


if __name__ == '__main__':
    problem = DoiTienProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = astar(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    cac_to = [act for act, _ in ket_qua.path() if act is not None]
    print(f"Doi so tien {GOAL} voi menh gia {MENH_GIA}:")
    print(f"  So to it nhat = {ket_qua.cost}: {cac_to} (Tong = {sum(cac_to)})")
    print(f"  So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
'''

SLIDE_AND_VARIANT_SKELETONS: Dict[str, Dict[str, Any]] = {
    "search_vacuum_world": {
        "id": "search_vacuum_world",
        "category": "search",
        "title": "Bai toan May hut bui / Vacuum World Trang thai don (Chuong 3 Slide 8-17 - SimpleAI)",
        "keywords": [
            "may hut bui", "vacuum", "vacuum world", "hut bui", "sang phai", "sang trai",
            "mayhutbuiproblem", "trang thai #5", "ban", "sach"
        ],
        "code": SKELETON_VACUUM_WORLD,
    },
    "search_sensorless_vacuum": {
        "id": "search_sensorless_vacuum",
        "category": "search",
        "title": "Bai toan May hut bui Thieu cam nhan / Sensorless Vacuum World (Chuong 3 Slide 10-11)",
        "keywords": [
            "thieu cam nhan", "sensorless", "belief state", "trang thai niem tin",
            "#1,#2,#3,#4,#5,#6,#7,#8", "khong quan sat duoc"
        ],
        "code": SKELETON_SENSORLESS_VACUUM,
    },
    "env_vacuum_agent": {
        "id": "env_vacuum_agent",
        "category": "search",
        "title": "Mo phong Tac tu & Moi truong bang simpleai.environments.Environment",
        "keywords": [
            "simpleai.environments", "environment", "percept", "do_action",
            "is_completed", "tac tu", "agent program"
        ],
        "code": SKELETON_SIMPLEAI_ENVIRONMENT,
    },
    "search_tree_abc_slide": {
        "id": "search_tree_abc_slide",
        "category": "search",
        "title": "Tim kiem tren Cay A-B-C-D-E-F-G-H-O va Thong ke BaseViewer (Slide Chuong 3)",
        "keywords": [
            "cay tim kiem", "baseviewer", "visited_nodes", "max_fringe_size",
            "thu tu duyet", "thu tu xet", "cay phan nhanh"
        ],
        "code": SKELETON_TREE_ABC_SLIDE,
    },
    "local_8puzzle_hill_climbing": {
        "id": "local_8puzzle_hill_climbing",
        "category": "local",
        "title": "Tim kiem Leo doi / Local Search cho Bai toan 8-Puzzle (Slide 34-35 Chuong 4)",
        "keywords": [
            "leo doi 8-puzzle", "leo doi bai toan o chu", "8-puzzle hill climbing",
            "8 puzzle local search", "puzzlelocalproblem", "slide 34", "f(n) = -(so luong"
        ],
        "code": SKELETON_LOCAL_8PUZZLE_HILL_CLIMBING,
    },
    "search_15puzzle": {
        "id": "search_15puzzle",
        "category": "search",
        "title": "Bai toan 15-Puzzle (4x4) va N-Puzzle Tong quat bang A* (SimpleAI)",
        "keywords": [
            "15-puzzle", "15 puzzle", "n-puzzle", "npuzzle", "4x4 puzzle", "15 o so"
        ],
        "code": SKELETON_15PUZZLE_NPuzzle,
    },
    "search_multi_goal_grid": {
        "id": "search_multi_goal_grid",
        "category": "search",
        "title": "Robot tim duong luoi 2D thu thap nhieu diem dich / chia khoa / kho bau (SimpleAI)",
        "keywords": [
            "nhieu diem dich", "thu thap", "chia khoa", "kho bau", "multi goal",
            "robotthuthapproblem", "trong so o"
        ],
        "code": SKELETON_MULTI_GOAL_GRID,
    },
    "search_knight_path": {
        "id": "search_knight_path",
        "category": "search",
        "title": "Bai toan Quan Ma di tuan / Duong di ngan nhat cua Quan Ma (Knight Shortest Path)",
        "keywords": [
            "quan ma", "ma di tuan", "knight", "buoc nhay ma", "ban co 8x8"
        ],
        "code": SKELETON_KNIGHT_SHORTEST_PATH,
    },
    "search_wolf_goat_cabbage": {
        "id": "search_wolf_goat_cabbage",
        "category": "search",
        "title": "Bai toan Nguoi nong dan qua song voi Soi, De, Bap cai (Wolf-Goat-Cabbage)",
        "keywords": [
            "soi de bap cai", "nong dan", "wolf", "goat", "cabbage", "cuu", "bap cai"
        ],
        "code": SKELETON_WOLF_GOAT_CABBAGE,
    },
    "search_coin_change": {
        "id": "search_coin_change",
        "category": "search",
        "title": "Bai toan Doi tien it to nhat / Bien doi so bang SimpleAI SearchProblem",
        "keywords": [
            "doi tien", "menh gia", "coin change", "so to it nhat", "doitienproblem"
        ],
        "code": SKELETON_COIN_CHANGE_NUMBER,
    },
}
