# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Nhom 1: Classical Search voi thu vien SimpleAI (SearchProblem).
Phong cach chuan Lab buoi04: ten bien tieng Viet khong dau, dem so_nut_xet, time.perf_counter().
"""

from typing import Dict, Any

SKELETON_8PUZZLE_ASTAR = '''import time
from simpleai.search import SearchProblem, astar, breadth_first, uniform_cost, greedy

GOAL = (
    (1, 2, 3),
    (4, 5, 6),
    (7, 8, 0),
)

INITIAL = (
    (2, 0, 6),
    (5, 3, 4),
    (1, 7, 8),
)

HUONG = {
    'UP': (-1, 0),
    'DOWN': (1, 0),
    'LEFT': (0, -1),
    'RIGHT': (0, 1),
}

VI_TRI_DICH = {GOAL[i][j]: (i, j) for i in range(3) for j in range(3)}


def tim_o(state, gia_tri=0):
    for i in range(3):
        for j in range(3):
            if state[i][j] == gia_tri:
                return i, j
    return 0, 0


class Puzzle_H1(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        i, j = tim_o(state, 0)
        return [ten for ten, (di, dj) in HUONG.items()
                if 0 <= i + di < 3 and 0 <= j + dj < 3]

    def result(self, state, action):
        i, j = tim_o(state, 0)
        di, dj = HUONG[action]
        mt = [list(hang) for hang in state]
        mt[i][j], mt[i + di][j + dj] = mt[i + di][j + dj], mt[i][j]
        return tuple(tuple(hang) for hang in mt)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        # h1: so o sai vi tri (khong tinh o trong 0)
        return sum(state[i][j] != 0 and state[i][j] != GOAL[i][j]
                   for i in range(3) for j in range(3))


class Puzzle_H2(Puzzle_H1):
    def heuristic(self, state):
        # h2: tong khoang cach Manhattan
        tong = 0
        for i in range(3):
            for j in range(3):
                gia_tri = state[i][j]
                if gia_tri != 0:
                    hang_dich, cot_dich = VI_TRI_DICH[gia_tri]
                    tong += abs(i - hang_dich) + abs(j - cot_dich)
        return tong


def in_ma_tran(state, le='    '):
    for hang in state:
        print(le + ' '.join(str(x) if x != 0 else '_' for x in hang))


def giai(ten, problem, thuat_toan=astar):
    print(f'{ten}: h(initial) = {problem.heuristic(problem.initial_state)}')
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    if ket_qua is None:
        print('  Khong tim thay loi giai\\n')
        return None

    cac_buoc = [action for action, _ in ket_qua.path() if action is not None]
    print(f"  So buoc = {ket_qua.cost}: {' -> '.join(cac_buoc)}")
    print(f'  So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.3f}s\\n')
    return ket_qua


if __name__ == '__main__':
    print('Trang thai ban dau:')
    in_ma_tran(INITIAL)
    print('Trang thai dich:')
    in_ma_tran(GOAL)
    print()

    giai('A* voi h1 (so o sai vi tri)', Puzzle_H1(INITIAL))
    ket_qua = giai('A* voi h2 (Manhattan)', Puzzle_H2(INITIAL))

    if ket_qua is not None:
        print('Chi tiet cac buoc (theo h2):')
        for buoc, (action, state) in enumerate(ket_qua.path()):
            print(f"  Buoc {buoc}: {action or 'Bat dau'}")
            in_ma_tran(state)
'''

SKELETON_STRING_GEN = '''import time
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

GOAL = 'GMAN'
KY_TU = ' ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class SinhXauProblem(SearchProblem):
    def __init__(self, initial_state=''):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        if len(state) < len(GOAL):
            return list(KY_TU)
        return []

    def result(self, state, action):
        return state + action

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        sai = sum(1 for i in range(len(state)) if state[i] != GOAL[i])
        thieu = len(GOAL) - len(state)
        return sai + thieu


def chay(ten, thuat_toan, **kwargs):
    problem = SinhXauProblem(initial_state='')
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    if ket_qua is None:
        print(f"{ten:<14}: Khong tim thay loi giai")
    else:
        cac_buoc = ' -> '.join(repr(s) for _, s in ket_qua.path())
        print(f"{ten:<14}: {cac_buoc}")
        print(f"{'':<14}  Do sau = {ket_qua.depth}, Chi phi = {ket_qua.cost}")
    print(f"{'':<14}  So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.3f}s\\n")


if __name__ == '__main__':
    print(f"Bai toan: sinh xau {GOAL!r} tu xau rong\\n")
    if len(GOAL) <= 3:
        chay("BFS", breadth_first)
        chay("UCS", uniform_cost)
        chay("DFS", depth_first)
        chay("DLS (l=2)", limited_depth_first, depth_limit=2)
        chay(f"DLS (l={len(GOAL)})", limited_depth_first, depth_limit=len(GOAL))
        chay("IDS", iterative_limited_depth_first)
    chay("Greedy", greedy, graph_search=True)
    chay("A*", astar, graph_search=True)
'''

SKELETON_WATER_JUGS = '''import time
from simpleai.search import (
    SearchProblem,
    breadth_first,
    depth_first,
    uniform_cost,
    astar,
)

DUNG_TICH = (3, 5, 8)
INITIAL = (0, 0, 8)
MUC_TIEU = 4


class DongNuocProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        n = len(DUNG_TICH)
        ds_hanh_dong = []
        # 1. Do day binh i tu voi
        for i in range(n):
            if state[i] < DUNG_TICH[i]:
                ds_hanh_dong.append(('DO_DAY', i, None, DUNG_TICH[i] - state[i]))
        # 2. Do bo binh i
        for i in range(n):
            if state[i] > 0:
                ds_hanh_dong.append(('DO_BO', i, None, state[i]))
        # 3. Rot tu binh i sang binh j
        for i in range(n):
            for j in range(n):
                if i != j and state[i] > 0 and state[j] < DUNG_TICH[j]:
                    luong = min(state[i], DUNG_TICH[j] - state[j])
                    ds_hanh_dong.append(('ROT', i, j, luong))
        return ds_hanh_dong

    def result(self, state, action):
        loai, i, j, luong = action
        moi = list(state)
        if loai == 'DO_DAY':
            moi[i] = DUNG_TICH[i]
        elif loai == 'DO_BO':
            moi[i] = 0
        elif loai == 'ROT':
            moi[i] -= luong
            moi[j] += luong
        return tuple(moi)

    def is_goal(self, state):
        self.so_nut_xet += 1
        if isinstance(MUC_TIEU, tuple):
            return all(m is None or s == m for s, m in zip(state, MUC_TIEU))
        return MUC_TIEU in state

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        if isinstance(MUC_TIEU, tuple):
            return sum(1 for s, m in zip(state, MUC_TIEU) if m is not None and s != m)
        return 0 if MUC_TIEU in state else min(abs(x - MUC_TIEU) for x in state) / max(DUNG_TICH)


def mo_ta_buoc(action):
    if action is None:
        return "Bat dau"
    loai, i, j, luong = action
    if loai == 'DO_DAY':
        return f"Do day binh {i+1} (+{luong}L)"
    if loai == 'DO_BO':
        return f"Do bo binh {i+1} (-{luong}L)"
    return f"Rot {luong}L tu binh {i+1} sang binh {j+1}"


def chay(ten, thuat_toan):
    problem = DongNuocProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"{ten}:")
    if ket_qua is None:
        print("  Khong tim thay loi giai\\n")
        return None
    print(f"  So buoc = {ket_qua.cost}, So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
    for buoc, (act, st) in enumerate(ket_qua.path()):
        print(f"    Buoc {buoc}: {mo_ta_buoc(act):<32} -> {st}")
    print()
    return ket_qua


if __name__ == '__main__':
    print(f"Bai toan dong nuoc: Dung tich = {DUNG_TICH}, Ban dau = {INITIAL}, Dich = {MUC_TIEU}\\n")
    chay("BFS", breadth_first)
    chay("UCS", uniform_cost)
    chay("DFS", depth_first)
    chay("A*", astar)
'''

SKELETON_RIVER_CROSSING = '''import time
from simpleai.search import SearchProblem, breadth_first, depth_first, astar

# Trang thai: (so_nha_truyen_giao_bo_trai, so_tho_dan_bo_trai, vi_tri_thuyen)
# vi_tri_thuyen: 0 = bo trai (ban dau), 1 = bo phai (dich)
TONG_M = 3
TONG_C = 3
SUC_CHUA_THUYEN = 2
INITIAL = (TONG_M, TONG_C, 0)
GOAL = (0, 0, 1)

CAC_CHUYEN_DI = [
    (dm, dc)
    for dm in range(SUC_CHUA_THUYEN + 1)
    for dc in range(SUC_CHUA_THUYEN + 1)
    if 1 <= dm + dc <= SUC_CHUA_THUYEN
]


def hop_le(m_trai, c_trai):
    if not (0 <= m_trai <= TONG_M and 0 <= c_trai <= TONG_C):
        return False
    m_phai = TONG_M - m_trai
    c_phai = TONG_C - c_trai
    if m_trai > 0 and m_trai < c_trai:
        return False
    if m_phai > 0 and m_phai < c_phai:
        return False
    return True


class QuaSongProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        m, c, thuyen = state
        ds = []
        for dm, dc in CAC_CHUYEN_DI:
            if thuyen == 0:
                m_moi, c_moi = m - dm, c - dc
            else:
                m_moi, c_moi = m + dm, c + dc
            if hop_le(m_moi, c_moi):
                ds.append((dm, dc))
        return ds

    def result(self, state, action):
        m, c, thuyen = state
        dm, dc = action
        if thuyen == 0:
            return (m - dm, c - dc, 1)
        return (m + dm, c + dc, 0)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        m, c, _ = state
        return (m + c) / SUC_CHUA_THUYEN


def chay(ten, thuat_toan):
    problem = QuaSongProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"{ten}:")
    if ket_qua is None:
        print("  Khong tim thay loi giai\\n")
        return
    print(f"  So buoc = {ket_qua.cost}, So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
    for buoc, (act, st) in enumerate(ket_qua.path()):
        bo = "Bo Trai" if st[2] == 0 else "Bo Phai"
        print(f"    Buoc {buoc:2d}: Chuyen {str(act):<8} -> Trai=({st[0]}M, {st[1]}C) | Thuyen o {bo}")
    print()


if __name__ == '__main__':
    print("Bai toan 3 nha truyen giao va 3 tho dan qua song:\\n")
    chay("BFS", breadth_first)
    chay("DFS", depth_first)
    chay("A*", astar)
'''

SKELETON_MAZE_GRID = '''import time
from simpleai.search import SearchProblem, breadth_first, uniform_cost, greedy, astar

# 0: duong di, 1: tuong chan
ME_CUNG = (
    (0, 0, 0, 0, 1),
    (1, 1, 0, 1, 0),
    (0, 0, 0, 0, 0),
    (0, 1, 1, 1, 0),
    (0, 0, 0, 0, 0),
)

SO_HANG = len(ME_CUNG)
SO_COT = len(ME_CUNG[0])
INITIAL = (0, 0)
GOAL = (SO_HANG - 1, SO_COT - 1)

HUONG = {
    'UP': (-1, 0),
    'DOWN': (1, 0),
    'LEFT': (0, -1),
    'RIGHT': (0, 1),
}


class MeCungProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        r, c = state
        hop_le = []
        for ten, (dr, dc) in HUONG.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr < SO_HANG and 0 <= nc < SO_COT and ME_CUNG[nr][nc] != 1:
                hop_le.append(ten)
        return hop_le

    def result(self, state, action):
        r, c = state
        dr, dc = HUONG[action]
        return (r + dr, c + dc)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        r, c = state
        gr, gc = GOAL
        return abs(r - gr) + abs(c - gc)


def in_duong_di(duong):
    tap_o = {st for _, st in duong}
    for r in range(SO_HANG):
        dong = []
        for c in range(SO_COT):
            if (r, c) == INITIAL:
                dong.append('S')
            elif (r, c) == GOAL:
                dong.append('G')
            elif (r, c) in tap_o:
                dong.append('*')
            elif ME_CUNG[r][c] == 1:
                dong.append('#')
            else:
                dong.append('.')
        print('    ' + ' '.join(dong))


def chay(ten, thuat_toan):
    problem = MeCungProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"{ten}:")
    if ket_qua is None:
        print("  Khong tim thay duong di\\n")
        return None
    toa_do = ' -> '.join(str(st) for _, st in ket_qua.path())
    print(f"  Duong di: {toa_do}")
    print(f"  Chi phi = {ket_qua.cost}, So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
    in_duong_di(ket_qua.path())
    print()
    return ket_qua


if __name__ == '__main__':
    print(f"Bai toan tim duong me cung {SO_HANG}x{SO_COT} tu {INITIAL} den {GOAL}:\\n")
    chay("BFS", breadth_first)
    chay("UCS", uniform_cost)
    chay("Greedy", greedy)
    chay("A*", astar)
'''

SKELETON_GRAPH_SIMPLEAI = '''import time
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

_CANH = [
    ("Arad", "Zerind", 75), ("Arad", "Sibiu", 140), ("Arad", "Timisoara", 118),
    ("Zerind", "Oradea", 71), ("Oradea", "Sibiu", 151),
    ("Timisoara", "Lugoj", 111), ("Lugoj", "Mehadia", 70),
    ("Mehadia", "Drobeta", 75), ("Drobeta", "Craiova", 120),
    ("Craiova", "Rimnicu Vilcea", 146), ("Craiova", "Pitesti", 138),
    ("Sibiu", "Fagaras", 99), ("Sibiu", "Rimnicu Vilcea", 80),
    ("Rimnicu Vilcea", "Pitesti", 97), ("Fagaras", "Bucharest", 211),
    ("Pitesti", "Bucharest", 101), ("Bucharest", "Giurgiu", 90),
    ("Bucharest", "Urziceni", 85), ("Urziceni", "Hirsova", 98),
    ("Urziceni", "Vaslui", 142), ("Hirsova", "Eforie", 86),
    ("Vaslui", "Iasi", 92), ("Iasi", "Neamt", 87),
]

HEURISTIC = {
    "Arad": 366, "Bucharest": 0, "Craiova": 160, "Drobeta": 242,
    "Eforie": 161, "Fagaras": 176, "Giurgiu": 77, "Hirsova": 151,
    "Iasi": 226, "Lugoj": 244, "Mehadia": 241, "Neamt": 234,
    "Oradea": 380, "Pitesti": 100, "Rimnicu Vilcea": 193, "Sibiu": 253,
    "Timisoara": 329, "Urziceni": 80, "Vaslui": 199, "Zerind": 374,
}

VO_HUONG = True
DO_THI = {}
for _u, _v, _w in _CANH:
    DO_THI.setdefault(_u, []).append((_v, _w))
    if VO_HUONG:
        DO_THI.setdefault(_v, []).append((_u, _w))

INITIAL = "Arad"
GOAL = "Bucharest"


class DoThiProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        return [ke for ke, _ in DO_THI.get(state, [])]

    def result(self, state, action):
        return action

    def is_goal(self, state):
        self.so_nut_xet += 1
        if isinstance(GOAL, (set, list, tuple)):
            return state in GOAL
        return state == GOAL

    def cost(self, state, action, state2):
        for ke, trong_so in DO_THI.get(state, []):
            if ke == state2:
                return trong_so
        return 1

    def heuristic(self, state):
        return HEURISTIC.get(state, 0)


def chay(ten, thuat_toan, **kwargs):
    problem = DoThiProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    if ket_qua is None:
        print(f"{ten:<18}: Khong tim thay loi giai")
    else:
        duong = ' -> '.join(str(s) for _, s in ket_qua.path())
        print(f"{ten:<18}: {duong}")
        print(f"{'':<18}  Do sau = {ket_qua.depth}, Chi phi = {ket_qua.cost}, "
              f"So nut xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")


if __name__ == '__main__':
    print(f"Bai toan tim duong tren do thi tu {INITIAL} den {GOAL}:\\n")
    chay("BFS", breadth_first, graph_search=True)
    chay("UCS", uniform_cost, graph_search=True)
    chay("DFS", depth_first, graph_search=True)
    chay("DLS (l=3)", limited_depth_first, depth_limit=3)
    chay("IDS", iterative_limited_depth_first)
    chay("Greedy", greedy, graph_search=True)
    chay("A*", astar, graph_search=True)
'''

SKELETON_TSP_SEARCH = '''import time
from simpleai.search import SearchProblem, uniform_cost, astar

CAC_THANH_PHO = ('A', 'B', 'C', 'D')
KHOANG_CACH = {
    ('A', 'B'): 10, ('A', 'C'): 15, ('A', 'D'): 20,
    ('B', 'C'): 35, ('B', 'D'): 25,
    ('C', 'D'): 30,
}

MA_TRAN = {}
for (u, v), w in KHOANG_CACH.items():
    MA_TRAN[(u, v)] = w
    MA_TRAN[(v, u)] = w

CANH_NHO_NHAT = min(KHOANG_CACH.values())
XUAT_PHAT = 'A'
INITIAL = (XUAT_PHAT,)


class TSPProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        if len(state) < len(CAC_THANH_PHO):
            hien_tai = state[-1]
            return [tp for tp in CAC_THANH_PHO
                    if tp not in state and (hien_tai, tp) in MA_TRAN]
        if len(state) == len(CAC_THANH_PHO) and (state[-1], XUAT_PHAT) in MA_TRAN:
            return [XUAT_PHAT]
        return []

    def result(self, state, action):
        return state + (action,)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return len(state) == len(CAC_THANH_PHO) + 1 and state[-1] == XUAT_PHAT

    def cost(self, state, action, state2):
        return MA_TRAN[(state[-1], action)]

    def heuristic(self, state):
        so_buoc_con = (len(CAC_THANH_PHO) + 1) - len(state)
        return max(0, so_buoc_con * CANH_NHO_NHAT)


if __name__ == '__main__':
    for ten, thuat_toan in [('UCS', uniform_cost), ('A*', astar)]:
        problem = TSPProblem(INITIAL)
        bat_dau = time.perf_counter()
        ket_qua = thuat_toan(problem, graph_search=True)
        thoi_gian = time.perf_counter() - bat_dau
        print(f"{ten}: Chu trinh = {' -> '.join(ket_qua.state)}, "
              f"Tong chi phi = {ket_qua.cost}, So nut xet = {problem.so_nut_xet}, "
              f"Thoi gian = {thoi_gian:.4f}s")
'''

SKELETON_HANOI_TOWER = '''import time
from simpleai.search import SearchProblem, breadth_first, astar

SO_DIA = 3
INITIAL = (tuple(range(SO_DIA, 0, -1)), (), ())
GOAL = ((), (), tuple(range(SO_DIA, 0, -1)))


class ThapHaNoiProblem(SearchProblem):
    def __init__(self, initial_state=INITIAL):
        super().__init__(initial_state)
        self.so_nut_xet = 0

    def actions(self, state):
        ds = []
        for c_di in range(3):
            if not state[c_di]:
                continue
            dia_tren = state[c_di][-1]
            for c_den in range(3):
                if c_di != c_den and (not state[c_den] or state[c_den][-1] > dia_tren):
                    ds.append((c_di, c_den))
        return ds

    def result(self, state, action):
        c_di, c_den = action
        coc = [list(c) for c in state]
        dia = coc[c_di].pop()
        coc[c_den].append(dia)
        return tuple(tuple(c) for c in coc)

    def is_goal(self, state):
        self.so_nut_xet += 1
        return state == GOAL

    def cost(self, state, action, state2):
        return 1

    def heuristic(self, state):
        return SO_DIA - len(state[2])


if __name__ == '__main__':
    problem = ThapHaNoiProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = astar(problem, graph_search=True)
    thoi_gian = time.perf_counter() - bat_dau

    print(f"Thap Ha Noi ({SO_DIA} dia):")
    print(f"  So buoc = {ket_qua.cost}, So nut da xet = {problem.so_nut_xet}, Thoi gian = {thoi_gian:.4f}s")
    for buoc, (act, st) in enumerate(ket_qua.path()):
        mo_ta = "Bat dau" if act is None else f"Chuyen dia tu coc {act[0]+1} -> coc {act[1]+1}"
        print(f"  Buoc {buoc:2d}: {mo_ta:<30} | {st}")
'''

CLASSICAL_SEARCH_SKELETONS: Dict[str, Dict[str, Any]] = {
    "search_8puzzle_astar": {
        "id": "search_8puzzle_astar",
        "category": "search",
        "title": "8-Puzzle A* (h1 Misplaced Tiles & h2 Manhattan Distance - SimpleAI)",
        "keywords": [
            "8-puzzle", "8 puzzle", "eight puzzle", "tro choi 8 so", "8 chu so",
            "o trong", "manhattan", "misplaced", "so o sai vi tri", "khoang cach manhattan",
            "h1", "h2", "puzzle_h1", "puzzle_h2", "baitap3", "astar", "a*", "tim_o", "in_ma_tran"
        ],
        "code": SKELETON_8PUZZLE_ASTAR,
    },
    "search_string_gen": {
        "id": "search_string_gen",
        "category": "search",
        "title": "Bai toan sinh xau ky tu (BFS, UCS, DFS, DLS, IDS, Greedy, A* - SimpleAI)",
        "keywords": [
            "sinh xau", "xau rong", "chuoi dich", "hello world", "gman",
            "sinhxauproblem", "helloproblem", "them 1 ky tu", "ky_tu",
            "breadth_first", "uniform_cost", "depth_first", "limited_depth_first",
            "iterative_limited_depth_first", "baitap2"
        ],
        "code": SKELETON_STRING_GEN,
    },
    "search_water_jugs": {
        "id": "search_water_jugs",
        "category": "search",
        "title": "Bai toan Dong nuoc / Water Jugs (SimpleAI SearchProblem)",
        "keywords": [
            "dong nuoc", "binh nuoc", "water jug", "water jugs", "jug", "can nuoc",
            "rot nuoc", "do day", "do bo", "dung tich", "lit nuoc"
        ],
        "code": SKELETON_WATER_JUGS,
    },
    "search_river_crossing": {
        "id": "search_river_crossing",
        "category": "search",
        "title": "Bai toan Qua song: Nha truyen giao va Tho dan / Missionaries & Cannibals",
        "keywords": [
            "qua song", "nha truyen giao", "tho dan", "ke an thit nguoi",
            "missionaries", "cannibals", "thuyen", "bo trai", "bo phai",
            "soi de bap cai", "river crossing"
        ],
        "code": SKELETON_RIVER_CROSSING,
    },
    "search_maze_grid": {
        "id": "search_maze_grid",
        "category": "search",
        "title": "Bai toan Tim duong Me cung luoi 2D / Grid Pathfinding (SimpleAI)",
        "keywords": [
            "me cung", "luoi 2d", "maze", "grid", "tim duong", "chuong ngai vat",
            "tuong chan", "toa do", "hang cot", "manhattan", "robot tim duong"
        ],
        "code": SKELETON_MAZE_GRID,
    },
    "search_graph_simpleai": {
        "id": "search_graph_simpleai",
        "category": "search",
        "title": "Tim kiem tren Do thi co trong so & Heuristic bang SimpleAI (Romania / Do thi)",
        "keywords": [
            "do thi simpleai", "ban do romania", "arad", "bucharest",
            "dothiproblem", "tim duong tren do thi", "canh trong so",
            "breadth_first", "uniform_cost", "depth_first", "astar", "greedy"
        ],
        "code": SKELETON_GRAPH_SIMPLEAI,
    },
    "search_tsp": {
        "id": "search_tsp",
        "category": "search",
        "title": "Bai toan Nguoi du lich TSP bang SimpleAI (UCS & A*)",
        "keywords": [
            "nguoi du lich", "tsp", "traveling salesman", "chu trinh",
            "di qua tat ca thanh pho", "quay ve diem xuat phat"
        ],
        "code": SKELETON_TSP_SEARCH,
    },
    "search_hanoi": {
        "id": "search_hanoi",
        "category": "search",
        "title": "Bai toan Thap Ha Noi / Tower of Hanoi (SimpleAI)",
        "keywords": [
            "thap ha noi", "tower of hanoi", "hanoi", "chuyen dia", "3 coc", "dia lon tren dia nho"
        ],
        "code": SKELETON_HANOI_TOWER,
    },
}
