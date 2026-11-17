# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Nhom 5: Tim kiem Doi khang / Adversarial Search (Minimax & Alpha-Beta Pruning).
Bao gom: Cay tro choi Minimax/Alpha-Beta (in chi tiet cat tia), Co Caro/Tic-Tac-Toe 3x3, va Tro choi Nim.
"""

from typing import Dict, Any

SKELETON_GAME_TREE_ALPHABETA = '''# Minimax va Cat tia Alpha-Beta (Alpha-Beta Pruning) tren Cay tro choi

# Bieu dien cay tro choi (Mac dinh theo dung Slide 57 & 61-65 Chuong 4):
# - Nut trong: dict {ten_nut_con: nut_con}
# - Nut la: so nguyen (gia tri luong gia)
CAY_TRO_CHOI = {
    'A1': {'A11': 3, 'A12': 12, 'A13': 8},
    'A2': {'A21': 2, 'A22': 4, 'A23': 6},
    'A3': {'A31': 14, 'A32': 5, 'A33': 2},
}


def minimax(nut, la_max=True):
    if isinstance(nut, (int, float)):
        return nut, []

    if la_max:
        tot_nhat = float('-inf')
        duong_tot_nhat = []
        for ten_con, nut_con in nut.items():
            gia_tri, duong = minimax(nut_con, False)
            if gia_tri > tot_nhat:
                tot_nhat = gia_tri
                duong_tot_nhat = [ten_con] + duong
        return tot_nhat, duong_tot_nhat
    else:
        tot_nhat = float('inf')
        duong_tot_nhat = []
        for ten_con, nut_con in nut.items():
            gia_tri, duong = minimax(nut_con, True)
            if gia_tri < tot_nhat:
                tot_nhat = gia_tri
                duong_tot_nhat = [ten_con] + duong
        return tot_nhat, duong_tot_nhat


def alpha_beta(nut, alpha=float('-inf'), beta=float('inf'), la_max=True, ten_nut='Root', bi_cat=None):
    if bi_cat is None:
        bi_cat = []
    if isinstance(nut, (int, float)):
        return nut, []

    cac_con = list(nut.items())
    if la_max:
        gia_tri = float('-inf')
        duong_tot = []
        for idx, (ten_con, nut_con) in enumerate(cac_con):
            val, duong = alpha_beta(nut_con, alpha, beta, False, ten_con, bi_cat)
            if val > gia_tri:
                gia_tri = val
                duong_tot = [ten_con] + duong
            alpha = max(alpha, gia_tri)
            if alpha >= beta:
                con_lai = [k for k, _ in cac_con[idx + 1:]]
                if con_lai:
                    bi_cat.append((ten_nut, con_lai, f"alpha={alpha} >= beta={beta}"))
                break
        return gia_tri, duong_tot
    else:
        gia_tri = float('inf')
        duong_tot = []
        for idx, (ten_con, nut_con) in enumerate(cac_con):
            val, duong = alpha_beta(nut_con, alpha, beta, True, ten_con, bi_cat)
            if val < gia_tri:
                gia_tri = val
                duong_tot = [ten_con] + duong
            beta = min(beta, gia_tri)
            if alpha >= beta:
                con_lai = [k for k, _ in cac_con[idx + 1:]]
                if con_lai:
                    bi_cat.append((ten_nut, con_lai, f"alpha={alpha} >= beta={beta}"))
                break
        return gia_tri, duong_tot


if __name__ == '__main__':
    gt_mm, duong_mm = minimax(CAY_TRO_CHOI, la_max=True)
    print(f"Minimax: Gia tri toi uu = {gt_mm}, Nhanh chon = {' -> '.join(duong_mm)}")

    ds_cat = []
    gt_ab, duong_ab = alpha_beta(CAY_TRO_CHOI, la_max=True, bi_cat=ds_cat)
    print(f"Alpha-Beta: Gia tri toi uu = {gt_ab}, Nhanh chon = {' -> '.join(duong_ab)}")
    print("Cac nhanh bi cat tia (Pruned):")
    for cha, nhanh, ly_do in ds_cat:
        print(f"  Tai nut {cha}: cat {nhanh} ({ly_do})")
'''

SKELETON_GAME_TICTACTOE = '''# Tro choi Tic-Tac-Toe (Co Caro 3x3) voi Minimax & Alpha-Beta Pruning

BAN_CO_DAU = (
    'X', 'O', 'X',
    'O', 'X', '.',
    '.', '.', 'O',
)

 DUONG_THANG = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


def nguoi_thang(state):
    for a, b, c in DUONG_THANG:
        if state[a] != '.' and state[a] == state[b] == state[c]:
            return state[a]
    if '.' not in state:
        return 'HOA'
    return None


def alpha_beta_ttt(state, luot_x=True, alpha=float('-inf'), beta=float('inf')):
    kq = nguoi_thang(state)
    if kq == 'X':
        return 1, None
    if kq == 'O':
        return -1, None
    if kq == 'HOA':
        return 0, None

    o_trong = [i for i, v in enumerate(state) if v == '.']
    nuoc_tot = o_trong[0]

    if luot_x:
        gia_tri = float('-inf')
        for o in o_trong:
            moi = list(state)
            moi[o] = 'X'
            diem, _ = alpha_beta_ttt(tuple(moi), False, alpha, beta)
            if diem > gia_tri:
                gia_tri = diem
                nuoc_tot = o
            alpha = max(alpha, gia_tri)
            if alpha >= beta:
                break
        return gia_tri, nuoc_tot
    else:
        gia_tri = float('inf')
        for o in o_trong:
            moi = list(state)
            moi[o] = 'O'
            diem, _ = alpha_beta_ttt(tuple(moi), True, alpha, beta)
            if diem < gia_tri:
                gia_tri = diem
                nuoc_tot = o
            beta = min(beta, gia_tri)
            if alpha >= beta:
                break
        return gia_tri, nuoc_tot


def in_ban_co(state):
    for r in range(0, 9, 3):
        print('  ' + ' '.join(state[r:r + 3]))


if __name__ == '__main__':
    st = tuple(x.strip() for x in BAN_CO_DAU)
    print("Trang thai ban co hien tai:")
    in_ban_co(st)
    diem, nuoc = alpha_beta_ttt(st, luot_x=True)
    hang, cot = divmod(nuoc, 3) if nuoc is not None else (-1, -1)
    print(f"\\nNuoc di toi uu cho X: o {nuoc} (hang {hang}, cot {cot}), Diem luong gia = {diem}")
'''

# Fix accidental leading space in SKELETON_GAME_TICTACTOE
SKELETON_GAME_TICTACTOE = SKELETON_GAME_TICTACTOE.replace("\n DUONG_THANG =", "\nDUONG_THANG =")

SKELETON_GAME_NIM = '''# Tro choi Nim (boc soi) voi thuat toan Minimax & Alpha-Beta Pruning

DONG_SOI_DAU = (3, 4, 5)


def alpha_beta_nim(state, la_max=True, alpha=float('-inf'), beta=float('inf'), memo=None):
    if memo is None:
        memo = {}
    khoa = (tuple(sorted(state)), la_max)
    if khoa in memo:
        return memo[khoa]

    # Luat Normal Play: ai boc vien soi cuoi cung la THANG
    if sum(state) == 0:
        return (-1 if la_max else 1), None

    cac_nuoc = []
    for i, so_soi in enumerate(state):
        for boc in range(1, so_soi + 1):
            cac_nuoc.append((i, boc))

    nuoc_tot = cac_nuoc[0]
    if la_max:
        tot_nhat = float('-inf')
        for i, boc in cac_nuoc:
            moi = list(state)
            moi[i] -= boc
            diem, _ = alpha_beta_nim(tuple(moi), False, alpha, beta, memo)
            if diem > tot_nhat:
                tot_nhat = diem
                nuoc_tot = (i, boc)
            alpha = max(alpha, tot_nhat)
            if alpha >= beta:
                break
    else:
        tot_nhat = float('inf')
        for i, boc in cac_nuoc:
            moi = list(state)
            moi[i] -= boc
            diem, _ = alpha_beta_nim(tuple(moi), True, alpha, beta, memo)
            if diem < tot_nhat:
                tot_nhat = diem
                nuoc_tot = (i, boc)
            beta = min(beta, tot_nhat)
            if alpha >= beta:
                break

    memo[khoa] = (tot_nhat, nuoc_tot)
    return tot_nhat, nuoc_tot


if __name__ == '__main__':
    diem, nuoc = alpha_beta_nim(DONG_SOI_DAU, la_max=True)
    dong, so_boc = nuoc
    moi = list(DONG_SOI_DAU)
    moi[dong] -= so_boc
    print(f"Tro choi Nim - Trang thai dau: {DONG_SOI_DAU}")
    print(f"Nuoc di toi uu: Boc {so_boc} vien o dong {dong + 1} -> Trang thai moi: {tuple(moi)}")
    print(f"Ket qua du kien cho nguoi di truoc: {'THANG (1)' if diem > 0 else 'THUA (-1)'}")
'''

ADVERSARIAL_GAME_SKELETONS: Dict[str, Dict[str, Any]] = {
    "game_minimax_alphabeta_tree": {
        "id": "game_minimax_alphabeta_tree",
        "category": "game",
        "title": "Thuat toan Minimax & Cat tia Alpha-Beta tren Cay tro choi (Game Tree)",
        "keywords": [
            "minimax", "alpha-beta", "alpha beta", "cat tia", "pruning",
            "cay tro choi", "game tree", "nut max", "nut min", "luong gia"
        ],
        "code": SKELETON_GAME_TREE_ALPHABETA,
    },
    "game_tictactoe": {
        "id": "game_tictactoe",
        "category": "game",
        "title": "Tro choi Tic-Tac-Toe / Co Caro 3x3 voi Minimax & Alpha-Beta",
        "keywords": [
            "tic-tac-toe", "tictactoe", "tic tac toe", "co caro", "x o", "ban co 3x3"
        ],
        "code": SKELETON_GAME_TICTACTOE,
    },
    "game_nim": {
        "id": "game_nim",
        "category": "game",
        "title": "Tro choi Nim (Boc soi) voi Minimax & Alpha-Beta",
        "keywords": [
            "nim", "boc soi", "dong soi", "chia soi"
        ],
        "code": SKELETON_GAME_NIM,
    },
}
