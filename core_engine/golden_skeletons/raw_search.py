# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Nhom 1B: Tim kiem cai chay khong dung SimpleAI (class Nut, ham gamma).
Chuan xac 100% theo buoi04/baitap1.py (BFS, UCS, DFS, DLS, IDS + mo rong Greedy, A*).
"""

from typing import Dict, Any

SKELETON_RAW_GRAPH_SEARCH = '''"""
    1. BFS  - Tim kiem theo chieu rong
    2. UCS  - Tim kiem voi chi phi cuc tieu
    3. DFS  - Tim kiem theo chieu sau
    4. DLS  - Tim kiem gioi han do sau
    5. IDS  - Tim kiem sau dan
    6. Greedy - Tim kiem tham lam (theo h(n))
    7. A*   - Tim kiem A* (theo f(n) = g(n) + h(n))
"""

import heapq
from collections import deque

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
for _a, _b, _c in _CANH:
    DO_THI.setdefault(_a, []).append((_b, _c))
    if VO_HUONG:
        DO_THI.setdefault(_b, []).append((_a, _c))


def gamma(trang_thai):
    # Gamma(n): tra ve danh sach (trang_thai_con, chi_phi_buoc).
    return DO_THI.get(trang_thai, [])


def h(trang_thai):
    return HEURISTIC.get(trang_thai, 0)


class Nut:
    # Nut cua cay tim kiem: trang thai, nut cha, do sau, chi phi duong di.
    def __init__(self, trang_thai, cha=None, chi_phi=0, do_sau=0):
        self.trang_thai = trang_thai
        self.cha = cha
        self.chi_phi = chi_phi
        self.do_sau = do_sau

    def duong_di(self):
        # SOLUTION(n): chuoi trang thai tu goc den nut hien tai.
        ket_qua, n = [], self
        while n is not None:
            ket_qua.append(n.trang_thai)
            n = n.cha
        return ket_qua[::-1]

    def mo_rong(self):
        # Sinh cac nut con (ham Expand).
        return [Nut(t, self, self.chi_phi + c, self.do_sau + 1) for t, c in gamma(self.trang_thai)]


# 1. BFS - fringe la hang doi FIFO (nut moi them vao cuoi)
def bfs(n0, dich):
    fringe = deque([Nut(n0)])
    closed = set()
    da_vao_fringe = {n0}
    while fringe:
        n = fringe.popleft()
        closed.add(n.trang_thai)
        if n.trang_thai in dich:
            return n
        for con in n.mo_rong():
            if con.trang_thai not in closed and con.trang_thai not in da_vao_fringe:
                da_vao_fringe.add(con.trang_thai)
                fringe.append(con)
    return None


# 2. UCS - fringe la hang doi uu tien theo chi phi duong di g(n)
def ucs(n0, dich):
    dem = 0
    fringe = [(0, dem, Nut(n0))]
    closed = set()
    chi_phi_tot_nhat = {n0: 0}
    while fringe:
        _, _, n = heapq.heappop(fringe)
        if n.trang_thai in closed:
            continue
        closed.add(n.trang_thai)
        if n.trang_thai in dich:
            return n
        for con in n.mo_rong():
            if con.trang_thai not in closed and con.chi_phi < chi_phi_tot_nhat.get(con.trang_thai, float("inf")):
                chi_phi_tot_nhat[con.trang_thai] = con.chi_phi
                dem += 1
                heapq.heappush(fringe, (con.chi_phi, dem, con))
    return None


# 3. DFS - fringe la ngan xep LIFO (nut moi them vao dau)
def dfs(n0, dich):
    fringe = [Nut(n0)]
    while fringe:
        n = fringe.pop()
        if n.trang_thai in dich:
            return n
        duong_di = set(n.duong_di())
        for con in reversed(n.mo_rong()):
            if con.trang_thai not in duong_di:
                fringe.append(con)
    return None


# 4. DLS - DFS co gioi han do sau l
def dls(n0, dich, gioi_han):
    fringe = [Nut(n0)]
    bi_cat = False
    while fringe:
        n = fringe.pop()
        if n.trang_thai in dich:
            return n
        if n.do_sau >= gioi_han:
            bi_cat = True
            continue
        duong_di = set(n.duong_di())
        for con in reversed(n.mo_rong()):
            if con.trang_thai not in duong_di:
                fringe.append(con)
    return "CUT_OFF" if bi_cat else None


# 5. IDS - lap DLS voi gioi han 0, 1, 2, ... cho den khi tim thay
def ids(n0, dich, gioi_han_max=100):
    for l in range(gioi_han_max + 1):
        ket_qua = dls(n0, dich, l)
        if ket_qua != "CUT_OFF":
            return ket_qua
    return None


# 6. Greedy Best-First Search - uu tien theo h(n)
def greedy_search(n0, dich):
    dem = 0
    fringe = [(h(n0), dem, Nut(n0))]
    closed = set()
    while fringe:
        _, _, n = heapq.heappop(fringe)
        if n.trang_thai in closed:
            continue
        closed.add(n.trang_thai)
        if n.trang_thai in dich:
            return n
        for con in n.mo_rong():
            if con.trang_thai not in closed:
                dem += 1
                heapq.heappush(fringe, (h(con.trang_thai), dem, con))
    return None


# 7. A* Search - uu tien theo f(n) = g(n) + h(n)
def a_star(n0, dich):
    dem = 0
    fringe = [(h(n0), dem, Nut(n0))]
    closed = set()
    chi_phi_tot_nhat = {n0: 0}
    while fringe:
        _, _, n = heapq.heappop(fringe)
        if n.trang_thai in closed:
            continue
        closed.add(n.trang_thai)
        if n.trang_thai in dich:
            return n
        for con in n.mo_rong():
            if con.trang_thai not in closed and con.chi_phi < chi_phi_tot_nhat.get(con.trang_thai, float("inf")):
                chi_phi_tot_nhat[con.trang_thai] = con.chi_phi
                dem += 1
                f_val = con.chi_phi + h(con.trang_thai)
                heapq.heappush(fringe, (f_val, dem, con))
    return None


def in_ket_qua(ten, nut):
    if nut is None or nut == "CUT_OFF":
        print(f"{ten:<22}: Khong tim thay loi giai ({nut})")
    else:
        print(f"{ten:<22}: {' -> '.join(nut.duong_di())}")
        print(f"{'':<22}  Do sau = {nut.do_sau}, Chi phi = {nut.chi_phi}")


if __name__ == "__main__":
    bat_dau, dich = "Arad", {"Bucharest"}
    print(f"Bai toan: tim duong tu {bat_dau} den {', '.join(dich)}\\n")

    in_ket_qua("BFS", bfs(bat_dau, dich))
    in_ket_qua("UCS", ucs(bat_dau, dich))
    in_ket_qua("DFS", dfs(bat_dau, dich))
    in_ket_qua("DLS (l=2)", dls(bat_dau, dich, 2))
    in_ket_qua("DLS (l=4)", dls(bat_dau, dich, 4))
    in_ket_qua("IDS", ids(bat_dau, dich))
    in_ket_qua("Greedy", greedy_search(bat_dau, dich))
    in_ket_qua("A*", a_star(bat_dau, dich))
'''

RAW_SEARCH_SKELETONS: Dict[str, Dict[str, Any]] = {
    "raw_graph_search": {
        "id": "raw_graph_search",
        "category": "raw",
        "title": "Tim kiem cai chay tren Do thi (class Nut, gamma, fringe, BFS, UCS, DFS, DLS, IDS, Greedy, A*)",
        "keywords": [
            "class nut", "def gamma", "fringe", "closed", "get_first", "get_lowest_cost",
            "cut_off", "mo_rong", "duong_di", "khong dung thu vien", "cai dat chay",
            "bfs", "ucs", "dfs", "dls", "ids", "arad", "bucharest", "baitap1"
        ],
        "code": SKELETON_RAW_GRAPH_SEARCH,
    },
}
