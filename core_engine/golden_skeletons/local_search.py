# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Nhom 2: Local Search voi SimpleAI (simpleai.search.local).
Chuan xac 100% theo buoi05/baitap1.py va buoi04/baitap3(genetic).py.
"""

from typing import Dict, Any

SKELETON_LOCAL_NQUEENS = '''import random
import time

# Thu vien SimpleAI
from simpleai.search import SearchProblem
from simpleai.search.local import (
    beam,
    beam_best_first,
    genetic,
    hill_climbing,
    hill_climbing_random_restarts,
    hill_climbing_stochastic,
    simulated_annealing,
)

N = 5
INITIAL = tuple(0 for _ in range(N))
SO_CAP = N * (N - 1) // 2


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
        return SO_CAP - self.so_cap_tan_cong(state)

    def so_cap_tan_cong(self, state):
        return sum(
            state[cot1] == state[cot2]
            or abs(state[cot1] - state[cot2]) == cot2 - cot1
            for cot1 in range(N) for cot2 in range(cot1 + 1, N)
        )

    def generate_random_state(self):
        return tuple(random.randrange(N) for _ in range(N))

    def crossover(self, state1, state2):
        diem_cat = random.randrange(1, N)
        return state1[:diem_cat] + state2[diem_cat:]

    def mutate(self, state):
        cot = random.randrange(N)
        hang_moi = random.choice([hang for hang in range(N) if hang != state[cot]])
        return self.result(state, (cot, hang_moi))


def in_ban_co(state):
    for hang in range(N):
        print('  ' + ' '.join('Q' if state[cot] == hang else '.'
                              for cot in range(N)))


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
    print(f'  Value = {problem.value(ket_qua.state)}/{SO_CAP}')
    print(f'  So cap tan cong = {problem.so_cap_tan_cong(ket_qua.state)}')
    print(f'  Dat loi giai = {problem.value(ket_qua.state) == SO_CAP}')
    print(f'  Thoi gian = {thoi_gian:.4f}s')
    return ket_qua


if __name__ == '__main__':
    print(f'Bai toan {N} quan hau tren ban co {N}x{N}')
    print(f'Trang thai ban dau: {INITIAL}')
    in_ban_co(INITIAL)

    chay('Hill climbing', hill_climbing)
    chay('Stochastic hill climbing', hill_climbing_stochastic, iterations_limit=100)
    chay('Hill climbing random restarts', hill_climbing_random_restarts, restarts_limit=10)
    chay('Beam search', beam, beam_size=15, iterations_limit=50)
    chay('Beam best first', beam_best_first, beam_size=15, iterations_limit=50)
    chay('Simulated annealing', simulated_annealing, iterations_limit=500)
    chay('Genetic search', genetic, population_size=60, mutation_chance=0.2, iterations_limit=100)
'''

SKELETON_LOCAL_8PUZZLE_GENETIC = '''import random
import time

# Thu vien SimpleAI
from simpleai.search import SearchProblem
from simpleai.search.local import genetic

GOAL = (1, 2, 3, 4, 5, 6, 7, 8, 0)
VI_TRI_DICH = {gia_tri: vi_tri for vi_tri, gia_tri in enumerate(GOAL)}


class PuzzleGenetic(SearchProblem):
    def generate_random_state(self):
        state = list(range(9))
        random.shuffle(state)
        return tuple(state)

    def crossover(self, state1, state2):
        dau, cuoi = sorted(random.sample(range(9), 2))
        child = [None] * 9
        child[dau:cuoi + 1] = state1[dau:cuoi + 1]

        vi_tri_trong = list(range(cuoi + 1, 9)) + list(range(dau))
        thu_tu_state2 = state2[cuoi + 1:] + state2[:cuoi + 1]
        gia_tri_con_lai = [x for x in thu_tu_state2 if x not in child]

        for vi_tri, gia_tri in zip(vi_tri_trong, gia_tri_con_lai):
            child[vi_tri] = gia_tri

        return tuple(child)

    def mutate(self, state):
        mutated = list(state)
        vi_tri_1, vi_tri_2 = random.sample(range(9), 2)
        mutated[vi_tri_1], mutated[vi_tri_2] = mutated[vi_tri_2], mutated[vi_tri_1]
        return tuple(mutated)

    def value(self, state):
        return (33 - self.heuristic(state)) ** 6

    def heuristic(self, state):
        tong = 0
        for vi_tri, gia_tri in enumerate(state):
            if gia_tri != 0:
                dich = VI_TRI_DICH[gia_tri]
                hang, cot = divmod(vi_tri, 3)
                hang_dich, cot_dich = divmod(dich, 3)
                tong += abs(hang - hang_dich) + abs(cot - cot_dich)
        return tong


def in_cau_hinh(state):
    for i in range(0, 9, 3):
        print('    ' + ' '.join(str(x) if x != 0 else '_' for x in state[i:i + 3]))


def giai_di_truyen(seed=42):
    random.seed(seed)
    problem = PuzzleGenetic()

    bat_dau = time.perf_counter()
    ket_qua = genetic(
        problem,
        population_size=200,
        mutation_chance=0.25,
        iterations_limit=200,
    )
    thoi_gian = time.perf_counter() - bat_dau

    print('Cau hinh tot nhat:')
    in_cau_hinh(ket_qua.state)
    print(f'Value = {ket_qua.value}')
    print(f'Heuristic = {problem.heuristic(ket_qua.state)}')
    print(f'Dat dich = {ket_qua.state == GOAL}')
    print(f'Thoi gian = {thoi_gian:.3f}s')
    return ket_qua


if __name__ == '__main__':
    print('Cau hinh dich:')
    in_cau_hinh(GOAL)
    print()
    giai_di_truyen()
'''

SKELETON_LOCAL_KNAPSACK = '''import random
import time
from simpleai.search import SearchProblem
from simpleai.search.local import (
    hill_climbing,
    hill_climbing_random_restarts,
    simulated_annealing,
    genetic,
)

# Danh sach do vat: (ten, trong_luong, gia_tri)
DO_VAT = (
    ('Vat 1', 10, 60),
    ('Vat 2', 20, 100),
    ('Vat 3', 30, 120),
    ('Vat 4', 15, 80),
    ('Vat 5', 25, 95),
    ('Vat 6', 12, 70),
)
SUC_CHUA_TOI_DA = 50
SO_VAT = len(DO_VAT)
INITIAL = tuple(0 for _ in range(SO_VAT))


class CaiTuiProblem(SearchProblem):
    def actions(self, state):
        # Lat trang thai chon/khong chon (0 <-> 1) cua vat thu i
        return list(range(SO_VAT))

    def result(self, state, action):
        moi = list(state)
        moi[action] = 1 - moi[action]
        return tuple(moi)

    def tong_trong_luong(self, state):
        return sum(DO_VAT[i][1] for i in range(SO_VAT) if state[i] == 1)

    def tong_gia_tri(self, state):
        return sum(DO_VAT[i][2] for i in range(SO_VAT) if state[i] == 1)

    def value(self, state):
        tl = self.tong_trong_luong(state)
        gt = self.tong_gia_tri(state)
        if tl > SUC_CHUA_TOI_DA:
            # Phat nang neu vuot qua suc chua
            return -(tl - SUC_CHUA_TOI_DA) * 100
        return gt

    def generate_random_state(self):
        st = [0] * SO_VAT
        thu_tu = list(range(SO_VAT))
        random.shuffle(thu_tu)
        tl = 0
        for idx in thu_tu:
            if tl + DO_VAT[idx][1] <= SUC_CHUA_TOI_DA and random.random() < 0.6:
                st[idx] = 1
                tl += DO_VAT[idx][1]
        return tuple(st)

    def crossover(self, state1, state2):
        cat = random.randrange(1, SO_VAT)
        return state1[:cat] + state2[cat:]

    def mutate(self, state):
        idx = random.randrange(SO_VAT)
        return self.result(state, idx)


def chay(ten, thuat_toan, **kwargs):
    random.seed(42)
    problem = CaiTuiProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    st = ket_qua.state
    chon = [DO_VAT[i][0] for i in range(SO_VAT) if st[i] == 1]
    print(f"{ten:<30}: State={st} | Chon={chon} | "
          f"Trong luong={problem.tong_trong_luong(st)}/{SUC_CHUA_TOI_DA} | "
          f"Gia tri={problem.tong_gia_tri(st)} | {thoi_gian:.4f}s")


if __name__ == '__main__':
    print(f"Bai toan Cai tui (Knapsack) - Suc chua toi da = {SUC_CHUA_TOI_DA}:\\n")
    chay("Hill climbing", hill_climbing)
    chay("Hill climbing random restarts", hill_climbing_random_restarts, restarts_limit=20)
    chay("Simulated annealing", simulated_annealing, iterations_limit=500)
    chay("Genetic", genetic, population_size=80, mutation_chance=0.2, iterations_limit=150)
'''

SKELETON_LOCAL_TSP = '''import random
import time
from simpleai.search import SearchProblem
from simpleai.search.local import (
    hill_climbing,
    hill_climbing_random_restarts,
    simulated_annealing,
    genetic,
)

CAC_THANH_PHO = ('A', 'B', 'C', 'D', 'E')
N = len(CAC_THANH_PHO)
MA_TRAN_KC = (
    (0, 12, 10, 19, 8),
    (12, 0, 3, 7, 2),
    (10, 3, 0, 6, 20),
    (19, 7, 6, 0, 4),
    (8, 2, 20, 4, 0),
)
INITIAL = tuple(range(N))


class TSPLocalProblem(SearchProblem):
    def actions(self, state):
        # Hoan doi 2 vi tri i, j trong hanh trinh (2-swap)
        return [(i, j) for i in range(N) for j in range(i + 1, N)]

    def result(self, state, action):
        i, j = action
        moi = list(state)
        moi[i], moi[j] = moi[j], moi[i]
        return tuple(moi)

    def chi_phi_chu_trinh(self, state):
        return sum(MA_TRAN_KC[state[k]][state[(k + 1) % N]] for k in range(N))

    def value(self, state):
        # Local search cua SimpleAI cuc dai hoa value -> lay am chi phi
        return -self.chi_phi_chu_trinh(state)

    def generate_random_state(self):
        st = list(range(N))
        random.shuffle(st)
        return tuple(st)

    def crossover(self, state1, state2):
        dau, cuoi = sorted(random.sample(range(N), 2))
        con = [None] * N
        con[dau:cuoi + 1] = state1[dau:cuoi + 1]
        con_lai = [x for x in state2 if x not in con]
        idx = 0
        for i in range(N):
            if con[i] is None:
                con[i] = con_lai[idx]
                idx += 1
        return tuple(con)

    def mutate(self, state):
        i, j = random.sample(range(N), 2)
        return self.result(state, (i, j))


def chay(ten, thuat_toan, **kwargs):
    random.seed(42)
    problem = TSPLocalProblem(INITIAL)
    bat_dau = time.perf_counter()
    ket_qua = thuat_toan(problem, **kwargs)
    thoi_gian = time.perf_counter() - bat_dau

    st = ket_qua.state
    hanh_trinh = ' -> '.join(CAC_THANH_PHO[i] for i in st) + f' -> {CAC_THANH_PHO[st[0]]}'
    print(f"{ten:<30}: {hanh_trinh} | Chi phi = {problem.chi_phi_chu_trinh(st)} | {thoi_gian:.4f}s")


if __name__ == '__main__':
    print("Bai toan TSP bang Tim kiem cuc bo (Local Search):\\n")
    chay("Hill climbing", hill_climbing)
    chay("Hill climbing random restarts", hill_climbing_random_restarts, restarts_limit=15)
    chay("Simulated annealing", simulated_annealing, iterations_limit=500)
    chay("Genetic", genetic, population_size=60, mutation_chance=0.2, iterations_limit=100)
'''

LOCAL_SEARCH_SKELETONS: Dict[str, Dict[str, Any]] = {
    "local_nqueens": {
        "id": "local_nqueens",
        "category": "local",
        "title": "N-Queens / 5 Quan Hau bang Tim kiem cuc bo (Hill Climbing, Beam, SA, Genetic - SimpleAI)",
        "keywords": [
            "namquanhau", "n-queens", "n quan hau", "5 quan hau", "8 quan hau",
            "so_cap_tan_cong", "hill_climbing", "hill_climbing_stochastic",
            "hill_climbing_random_restarts", "beam", "beam_best_first",
            "simulated_annealing", "genetic", "in_ban_co", "buoi05", "tim kiem cuc bo"
        ],
        "code": SKELETON_LOCAL_NQUEENS,
    },
    "local_8puzzle_genetic": {
        "id": "local_8puzzle_genetic",
        "category": "local",
        "title": "8-Puzzle bang Thuat toan Di truyen / Genetic Search (PuzzleGenetic - SimpleAI)",
        "keywords": [
            "puzzlegenetic", "8-puzzle genetic", "8 puzzle di truyen", "giai_di_truyen",
            "crossover", "mutate", "generate_random_state", "population_size", "mutation_chance",
            "baitap3(genetic)"
        ],
        "code": SKELETON_LOCAL_8PUZZLE_GENETIC,
    },
    "local_knapsack": {
        "id": "local_knapsack",
        "category": "local",
        "title": "Bai toan Cai tui / Knapsack bang Local Search (Hill Climbing, SA, Genetic)",
        "keywords": [
            "cai tui", "knapsack", "ba lo", "trong luong", "suc chua", "gia tri",
            "caituiproblem"
        ],
        "code": SKELETON_LOCAL_KNAPSACK,
    },
    "local_tsp": {
        "id": "local_tsp",
        "category": "local",
        "title": "Bai toan TSP bang Local Search (Hill Climbing, Simulated Annealing, Genetic)",
        "keywords": [
            "tsp local", "nguoi du lich cuc bo", "tsplocalproblem", "hoan doi thanh pho"
        ],
        "code": SKELETON_LOCAL_TSP,
    },
}
