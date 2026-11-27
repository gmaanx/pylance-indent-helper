# -*- coding: utf-8 -*-
"""
Kho Phoi Vang bo sung Chuong 1 (OOP Vector24 / NutTimKiem), Chuong 6 (Backward Chaining Hybrid),
Chuong 8 (Ontology TBox/ABox SimpleAI & Frame ke thua da nhanh),
va Chuong 9 (Xac suat Bayes, Mang Bayes CPT & Tap mo / Suy dien mo).
"""

SKELETON_ONTOLOGY_TBOX_ABOX_SIMPLEAI = '''# Chuong 8: Bieu dien tri thuc bang Ontology (TBox + ABox) ket hop SimpleAI & Suy dien tien
from simpleai.search import (
    CspProblem,
    LEAST_CONSTRAINING_VALUE,
    MOST_CONSTRAINED_VARIABLE,
    SearchProblem,
    backtrack,
    breadth_first,
)

# 1. TBox: Cay phan lop subClassOf (is-a), nhom tach lop disjoint, thuoc tinh va quan he
PARENT_OF = {
    "DoiTuong": None,
    "ConNguoi": "DoiTuong",
    "ThiSinh": "ConNguoi",
    "GiamThi": "ConNguoi",
    "VatDung": "DoiTuong",
    "VatDungHopLe": "VatDung",
    "VatDungCam": "VatDung",
    "DeThi": "VatDungHopLe",
    "BaiLam": "VatDungHopLe",
    "DienThoai": "VatDungCam",
    "KhuVuc": "DoiTuong",
    "MatBan": "KhuVuc",
}

DISJOINT_GROUPS = [
    ("ConNguoi", "VatDung", "KhuVuc"),
    ("ThiSinh", "GiamThi"),
    ("VatDungHopLe", "VatDungCam"),
]

CLASS_DEFAULTS = {
    "VatDungHopLe": {"coQuyChe": "duoc_phep"},
    "VatDungCam": {"coQuyChe": "bi_cam"},
}

RELATION_SPECS = {
    "dangCam": {"domain": "ConNguoi", "range": "VatDung", "symmetric": False, "inverse": "biCamBoi"},
    "datTai": {"domain": "VatDung", "range": "KhuVuc", "symmetric": False, "inverse": "chuaVat"},
    "ngoiCanh": {"domain": "ThiSinh", "range": "ThiSinh", "symmetric": True, "inverse": "ngoiCanh"},
}


class SubClassSearchProblem(SearchProblem):
    def __init__(self, start_cls, goal_fn):
        self.goal_fn = goal_fn
        super().__init__(initial_state=start_cls)

    def actions(self, state):
        cha = PARENT_OF.get(state)
        return [] if cha is None else [cha]

    def result(self, state, action):
        return action

    def is_goal(self, state):
        return self.goal_fn(state)


def chuoi_ke_thua(lop_con, lop_dich="DoiTuong"):
    prob = SubClassSearchProblem(lop_con, lambda c: c == lop_dich)
    kq = breadth_first(prob, graph_search=True)
    return None if kq is None else [st for _, st in kq.path()]


def la_lop_con(lop_con, lop_cha):
    return chuoi_ke_thua(lop_con, lop_cha) is not None


class OntologyKB:
    def __init__(self):
        self.instances = {}   # ten -> {"classes": [...], "props": {...}}
        self.relations = []   # (quan_he, chu_the, doi_tuong)

    def them_ca_the(self, ten, lop, props=None):
        self.instances[ten] = {"classes": [lop], "props": dict(props or {})}

    def them_quan_he(self, qh, s, o):
        if (qh, s, o) not in self.relations:
            self.relations.append((qh, s, o))
        if RELATION_SPECS.get(qh, {}).get("symmetric") and (qh, o, s) not in self.relations:
            self.relations.append((qh, o, s))

    def thuoc_lop(self, ca_the, lop):
        rec = self.instances.get(ca_the)
        return bool(rec) and any(la_lop_con(c, lop) for c in rec["classes"])

    def suy_dien_thuoc_tinh(self, ca_the, ten_tt):
        rec = self.instances[ca_the]
        if ten_tt in rec["props"]:
            return rec["props"][ten_tt]
        for ancestor in chuoi_ke_thua(rec["classes"][0]) or []:
            if ten_tt in CLASS_DEFAULTS.get(ancestor, {}):
                return CLASS_DEFAULTS[ancestor][ten_tt]
        return None

    def kiem_tra_nhat_quan(self):
        loi = []
        for ten in self.instances:
            for nhom in DISJOINT_GROUPS:
                trung = [c for c in nhom if self.thuoc_lop(ten, c)]
                if len(trung) > 1:
                    loi.append(f"Vi pham disjoint tai {ten}: {trung}")
        for qh, s, o in self.relations:
            spec = RELATION_SPECS.get(qh)
            if spec:
                if not self.thuoc_lop(s, spec["domain"]):
                    loi.append(f"Sai domain: {qh}({s}, {o})")
                if not self.thuoc_lop(o, spec["range"]):
                    loi.append(f"Sai range: {qh}({s}, {o})")
        return loi


def kiem_chung_csp(kb):
    variables, domains, constraints = [], {}, []

    def hop_le_canh_bao(vars_t, vals_t):
        vai_tro, quy_che, ket_luan = vals_t
        expected = "CANH_BAO" if (vai_tro == "ThiSinh" and quy_che == "bi_cam") else "HOP_LE"
        return ket_luan == expected

    for qh, nguoi, vat in kb.relations:
        if qh == "dangCam":
            v_role = f"role_{nguoi}"
            v_rule = f"rule_{vat}"
            v_alert = f"alert_{nguoi}_{vat}"
            for v, dom in (
                (v_role, [r for r in ("ThiSinh", "GiamThi") if kb.thuoc_lop(nguoi, r)]),
                (v_rule, [kb.suy_dien_thuoc_tinh(vat, "coQuyChe")]),
                (v_alert, ["CANH_BAO", "HOP_LE"]),
            ):
                if v not in domains:
                    variables.append(v)
                    domains[v] = dom
            constraints.append(((v_role, v_rule, v_alert), hop_le_canh_bao))

    return backtrack(
        CspProblem(variables, domains, constraints),
        variable_heuristic=MOST_CONSTRAINED_VARIABLE,
        value_heuristic=LEAST_CONSTRAINING_VALUE,
    )


def main():
    kb = OntologyKB()
    kb.them_ca_the("ts_1", "ThiSinh")
    kb.them_ca_the("gt_1", "GiamThi")
    kb.them_ca_the("dt_1", "DienThoai")
    kb.them_ca_the("de_1", "DeThi")
    kb.them_quan_he("dangCam", "ts_1", "dt_1")
    kb.them_quan_he("dangCam", "gt_1", "de_1")

    print("Chuoi ke thua DienThoai:", " -> ".join(chuoi_ke_thua("DienThoai") or []))
    print("Quy che ke thua cua dt_1:", kb.suy_dien_thuoc_tinh("dt_1", "coQuyChe"))
    print("Kiem tra TBox/ABox:", kb.kiem_tra_nhat_quan() or "Hop le")
    print("Ket qua suy dien CSP:", kiem_chung_csp(kb))


if __name__ == "__main__":
    main()
'''

SKELETON_FRAME_INHERITANCE = '''# Chuong 8: He thong Khung (Frames) da ke thua, ghi de theo do dac thu va phat hien mau thuan
from collections import deque

FRAMES = {
    "Quaker": {"parents": (), "slots": {"pacifist": True}},
    "Republican": {"parents": (), "slots": {"pacifist": False}},
    "Politician": {"parents": (), "slots": {"public_speaker": True}},
    "Nixon": {"parents": ("Quaker", "Republican", "Politician"), "slots": {}},
    "Chim": {"parents": (), "slots": {"bay_duoc": True, "co_long_vu": True}},
    "ChimCanhCut": {"parents": ("Chim",), "slots": {"bay_duoc": False}},
    "Opus": {"parents": ("ChimCanhCut",), "slots": {}},
}


def truy_van_frame(frames, ten_khung, cac_slot):
    duong_di = {ten_khung: (ten_khung,)}
    hang_doi = deque([ten_khung])
    while hang_doi:
        hien_tai = hang_doi.popleft()
        for cha in frames[hien_tai]["parents"]:
            if cha not in duong_di:
                duong_di[cha] = (*duong_di[hien_tai], cha)
                hang_doi.append(cha)

    ket_qua = {}
    for slot in cac_slot:
        nguon = [k for k in duong_di if slot in frames[k]["slots"]]
        if not nguon:
            ket_qua[slot] = {"trang_thai": "chua_biet", "gia_tri": None, "nguon": []}
            continue
        # Khung con cu the hon se ghi de to tien cua chinh no
        bi_ghi_de = set()
        for k in nguon:
            stack = list(frames[k]["parents"])
            while stack:
                anc = stack.pop()
                if anc not in bi_ghi_de:
                    bi_ghi_de.add(anc)
                    stack.extend(frames[anc]["parents"])
        ung_vien = [
            {"khung": k, "vet": " -> ".join(duong_di[k]), "gia_tri": frames[k]["slots"][slot]}
            for k in nguon if k not in bi_ghi_de
        ]
        gt_dau = ung_vien[0]["gia_tri"]
        if all(type(u["gia_tri"]) is type(gt_dau) and u["gia_tri"] == gt_dau for u in ung_vien):
            ket_qua[slot] = {"trang_thai": "xac_dinh", "gia_tri": gt_dau, "nguon": ung_vien}
        else:
            ket_qua[slot] = {"trang_thai": "mau_thuan", "gia_tri": None, "nguon": ung_vien}
    return ket_qua


def main():
    print("1. Ke thua co ghi de (Opus):")
    for slot, info in truy_van_frame(FRAMES, "Opus", ["bay_duoc", "co_long_vu"]).items():
        print(f"  {slot}: {info['trang_thai']} = {info['gia_tri']} ({info['nguon'][0]['vet']})")

    print("\\n2. Da ke thua co mau thuan (Nixon Diamond):")
    for slot, info in truy_van_frame(FRAMES, "Nixon", ["pacifist", "public_speaker"]).items():
        print(f"  {slot}: {info['trang_thai']} | nguon = {info['nguon']}")


if __name__ == "__main__":
    main()
'''

SKELETON_BACKWARD_CHAINING_HYBRID = '''# Chuong 6: Suy dien lui (Backward Chaining) in vet chung minh + ket hop SimpleAI SearchProblem
from simpleai.search import SearchProblem, depth_first

FACTS = {"C", "A", "R", "I", "D"}
RULES = [
    ("R1", ("C", "A"), "Q"),
    ("R2", ("R", "I"), "H"),
    ("R3", ("Q", "H", "D"), "E"),
    ("R4", ("E",), "S"),
]


def suy_dien_lui(tap_facts, ds_luat, muc_tieu):
    da_chung_minh = set()
    vet = []

    def chung_minh(goal, dang_xet, cap_do):
        le = "  " * cap_do
        if goal in tap_facts:
            vet.append(f"{le}- {goal} = True (Su kien ban dau)")
            return True
        if goal in da_chung_minh:
            vet.append(f"{le}- {goal} = True (Da chung minh)")
            return True
        if goal in dang_xet:
            return False

        for ma_luat, tien_de, ket_luan in ds_luat:
            if ket_luan != goal:
                continue
            vet.append(f"{le}Xet {ma_luat}: {' & '.join(tien_de)} -> {ket_luan}")
            if all(chung_minh(p, dang_xet | {goal}, cap_do + 1) for p in tien_de):
                da_chung_minh.add(goal)
                vet.append(f"{le}=> Chung minh duoc {goal} qua {ma_luat}")
                return True
        vet.append(f"{le}=> Khong chung minh duoc {goal}")
        return False

    thanh_cong = chung_minh(muc_tieu, frozenset(), 0)
    return thanh_cong, vet


class BackwardChainingProblem(SearchProblem):
    """Trang thai la tuple cac muc tieu con chua duoc chung minh."""

    def __init__(self, tap_facts, ds_luat, muc_tieu):
        self.tap_facts = set(tap_facts)
        self.ds_luat = list(ds_luat)
        ban_dau = () if muc_tieu in self.tap_facts else (muc_tieu,)
        super().__init__(initial_state=ban_dau)

    def actions(self, state):
        if not state:
            return []
        dau = state[0]
        if dau in self.tap_facts:
            return [("FACT", dau, ())]
        return [
            (ma_luat, dau, tien_de)
            for ma_luat, tien_de, ket_luan in self.ds_luat
            if ket_luan == dau
        ]

    def result(self, state, action):
        _, _, tien_de = action
        con_lai = list(tien_de) + list(state[1:])
        tiep_theo = []
        for g in con_lai:
            if g not in self.tap_facts and g not in tiep_theo:
                tiep_theo.append(g)
        return tuple(tiep_theo)

    def is_goal(self, state):
        return len(state) == 0


def main():
    ok, vet = suy_dien_lui(FACTS, RULES, "S")
    print(f"Backward Chaining (Goal='S'): {ok}")
    for dong in vet:
        print(" ", dong)

    prob = BackwardChainingProblem(FACTS, RULES, "S")
    kq = depth_first(prob, graph_search=True)
    print("SimpleAI Search duong suy dien:", [act[0] for act, _ in kq.path() if act is not None] if kq else None)


if __name__ == "__main__":
    main()
'''

SKELETON_PROB_BAYES_JOINT = '''# Chuong 9: Bang xac suat dong thoi, xac suat co dieu kien, doc lap va Dinh ly Bayes
from fractions import Fraction
from math import prod

# 1. Bang phan phoi xac suat dong thoi (hoac bang tan so quan sat)
BIEN = ("ThoiTiet", "ChoiTheThao")
BANG_QUAN_SAT = [
    (("Nang", "Co"), 3),
    (("Nang", "Khong"), 5),
    (("Mat", "Co"), 4),
    (("Mat", "Khong"), 2),
]


def tinh_xac_suat_bang( ds_bien, bang, truy_van, bang_chung=None):
    bang_chung = bang_chung or {}
    chi_so = {ten: i for i, ten in enumerate(ds_bien)}

    def khop(dong, su_kien):
        return all(dong[chi_so[k]] == v for k, v in su_kien.items())

    tong = Fraction(0)
    w_q = Fraction(0)
    w_e = Fraction(0)
    w_qe = Fraction(0)
    for gia_tri, trong_so in bang:
        w = Fraction(trong_so)
        c_q = khop(gia_tri, truy_van)
        c_e = khop(gia_tri, bang_chung)
        tong += w
        if c_q:
            w_q += w
        if c_e:
            w_e += w
        if c_q and c_e:
            w_qe += w

    p_q = w_q / tong
    p_e = w_e / tong
    p_qe = w_qe / tong
    p_q_given_e = (w_qe / w_e) if w_e != 0 else None
    doc_lap = (w_qe * tong == w_q * w_e)
    return {
        "P(Q)": p_q,
        "P(E)": p_e,
        "P(Q,E)": p_qe,
        "P(Q|E)": p_q_given_e,
        "doc_lap": doc_lap,
    }


def suy_dien_bayes(priors, likelihoods):
    """priors: {H: P(H)}, likelihoods: {H: [P(E1|H), P(E2|H), ...]}."""
    trong_so = {
        h: Fraction(str(p_h)) * prod(Fraction(str(lk)) for lk in likelihoods[h])
        for h, p_h in priors.items()
    }
    p_evidence = sum(trong_so.values(), Fraction(0))
    hau_nghiem = {h: w / p_evidence for h, w in trong_so.items()}
    tot_nhat = max(hau_nghiem, key=lambda h: hau_nghiem[h])
    return p_evidence, hau_nghiem, tot_nhat


def main():
    kq_bang = tinh_xac_suat_bang(
        BIEN,
        BANG_QUAN_SAT,
        truy_van={"ChoiTheThao": "Co"},
        bang_chung={"ThoiTiet": "Nang"},
    )
    print("1. Xac suat co dieu kien P(Choi='Co' | ThoiTiet='Nang'):", kq_bang["P(Q|E)"], f"({float(kq_bang['P(Q|E)']):.4f})")
    print("   Hai bien doc lap?:", kq_bang["doc_lap"])

    priors = {"Benh": "1/100", "KhongBenh": "99/100"}
    likelihoods = {"Benh": ["95/100"], "KhongBenh": ["5/100"]}
    p_e, post, map_h = suy_dien_bayes(priors, likelihoods)
    print("\\n2. Dinh ly Bayes P(Benh | DuongTinh):", post["Benh"], f"({float(post['Benh']):.4f}) | MAP = {map_h}")


if __name__ == "__main__":
    main()
'''

SKELETON_BAYESIAN_NETWORK_ENUMERATION = '''# Chuong 9: Mang Bayes (Bayesian Network) & Suy dien chinh xac bang Liet ke (Enumeration-Ask)
# Vi du kinh dien: Burglary - Earthquake - Alarm - JohnCalls - MaryCalls (Slide Chuong 9)

MANG_BAYES = [
    ("Burglary", (), {(): 0.001}),
    ("Earthquake", (), {(): 0.002}),
    (
        "Alarm",
        ("Burglary", "Earthquake"),
        {
            (True, True): 0.95,
            (True, False): 0.94,
            (False, True): 0.29,
            (False, False): 0.001,
        },
    ),
    ("JohnCalls", ("Alarm",), {(True,): 0.90, (False,): 0.05}),
    ("MaryCalls", ("Alarm",), {(True,): 0.70, (False,): 0.01}),
]

CPT_MAP = {ten: (cha, bang) for ten, cha, bang in MANG_BAYES}
THU_TU_BIEN = [ten for ten, _, _ in MANG_BAYES]


def xac_suat_nut(bien, gia_tri, gan_bien):
    cha, bang = CPT_MAP[bien]
    khoa = tuple(gan_bien[p] for p in cha)
    p_true = bang[khoa]
    return p_true if gia_tri else (1.0 - p_true)


def enumerate_all(ds_bien, gan_bien):
    if not ds_bien:
        return 1.0
    y, con_lai = ds_bien[0], ds_bien[1:]
    if y in gan_bien:
        return xac_suat_nut(y, gan_bien[y], gan_bien) * enumerate_all(con_lai, gan_bien)
    tong = 0.0
    for val in (True, False):
        gan_moi = dict(gan_bien)
        gan_moi[y] = val
        tong += xac_suat_nut(y, val, gan_moi) * enumerate_all(con_lai, gan_moi)
    return tong


def enumeration_ask(bien_truy_van, bang_chung):
    phan_phoi = {}
    for x_val in (True, False):
        gan = dict(bang_chung)
        gan[bien_truy_van] = x_val
        phan_phoi[x_val] = enumerate_all(THU_TU_BIEN, gan)
    tong = sum(phan_phoi.values())
    return {k: v / tong for k, v in phan_phoi.items()}


def main():
    kq = enumeration_ask("Burglary", {"JohnCalls": True, "MaryCalls": True})
    print("Phan phoi P(Burglary | JohnCalls=True, MaryCalls=True):")
    print(f"  True : {kq[True]:.6f}")
    print(f"  False: {kq[False]:.6f}")


if __name__ == "__main__":
    main()
'''

SKELETON_FUZZY_SETS_INFERENCE = '''# Chuong 9: Tap mo (Fuzzy Sets), phep toan tap mo, lat cat alpha va Giai mo trong tam (Centroid)
from fractions import Fraction


def hop_mo(a, b):
    tap_x = sorted(set(a) | set(b))
    return {x: max(a.get(x, Fraction(0)), b.get(x, Fraction(0))) for x in tap_x}


def giao_mo(a, b):
    tap_x = sorted(set(a) | set(b))
    return {x: min(a.get(x, Fraction(0)), b.get(x, Fraction(0))) for x in tap_x}


def phan_bu_mo(a):
    return {x: Fraction(1) - mu for x, mu in a.items()}


def tich_dai_so(a, b):
    tap_x = sorted(set(a) | set(b))
    return {x: a.get(x, Fraction(0)) * b.get(x, Fraction(0)) for x in tap_x}


def tong_dai_so(a, b):
    tap_x = sorted(set(a) | set(b))
    return {
        x: a.get(x, Fraction(0)) + b.get(x, Fraction(0)) - a.get(x, Fraction(0)) * b.get(x, Fraction(0))
        for x in tap_x
    }


def lat_cat_alpha(a, alpha, chat=False):
    nguong = Fraction(str(alpha))
    return [x for x, mu in a.items() if (mu > nguong if chat else mu >= nguong)]


def giai_mo_trong_tam(tap_mo_so):
    """Centroid defuzzification: sum(x * mu(x)) / sum(mu(x))."""
    tu = sum(float(x) * float(mu) for x, mu in tap_mo_so.items())
    mau = sum(float(mu) for mu in tap_mo_so.values())
    return 0.0 if mau == 0 else tu / mau


def main():
    A = {"x1": Fraction(2, 10), "x2": Fraction(7, 10), "x3": Fraction(1, 1)}
    B = {"x1": Fraction(5, 10), "x2": Fraction(4, 10), "x3": Fraction(8, 10)}

    print("Hop A u B :", {k: str(v) for k, v in hop_mo(A, B).items()})
    print("Giao A n B:", {k: str(v) for k, v in giao_mo(A, B).items()})
    print("Bu ~A     :", {k: str(v) for k, v in phan_bu_mo(A).items()})
    print("Alpha-cut (alpha=0.5) cua A:", lat_cat_alpha(A, "0.5"))

    dau_ra_mo = {10: 0.2, 20: 0.5, 30: 0.9, 40: 0.6}
    print(f"Gia tri giai mo trong tam (Centroid): {giai_mo_trong_tam(dau_ra_mo):.2f}")


if __name__ == "__main__":
    main()
'''

SKELETON_OOP_VECTOR24_PLAGIARISM = '''# Chuong 1 / Buoi 1: Lop Vector24, khu dau tieng Viet va do tuong dong van ban Cosine
import math
import re
import unicodedata


class Vector24:
    def __init__(self, components):
        values = tuple(float(x) for x in components)
        if len(values) != 24:
            raise ValueError("Vector24 can dung 24 toa do.")
        self.components = values

    def __add__(self, other):
        if not isinstance(other, Vector24):
            return NotImplemented
        return Vector24(a + b for a, b in zip(self.components, other.components))

    @property
    def do_lon(self):
        return math.hypot(*self.components)

    def tich_vo_huong(self, other):
        if not isinstance(other, Vector24):
            raise TypeError("Can doi tuong Vector24.")
        return sum(a * b for a, b in zip(self.components, other.components))

    def goc(self, other):
        d1, d2 = self.do_lon, other.do_lon
        if d1 == 0 or d2 == 0:
            raise ValueError("Khong tinh duoc goc voi vector 0.")
        cos_val = max(-1.0, min(1.0, self.tich_vo_huong(other) / (d1 * d2)))
        return math.acos(cos_val)


def khu_dau(van_ban):
    nfd = unicodedata.normalize("NFD", van_ban)
    khong_dau = re.sub(r"[\\u0300-\\u036f]", "", nfd)
    return khong_dau.replace("đ", "d").replace("Đ", "D")


def vector_hoa_24(van_ban):
    bang_chu = "abcdefghijklmnopqrstuvwx"
    sach = khu_dau(van_ban).lower()
    return Vector24([sach.count(ch) for ch in bang_chu])


def do_tuong_dong_cosin(vb1, vb2):
    v1, v2 = vector_hoa_24(vb1), vector_hoa_24(vb2)
    if v1.do_lon == 0 or v2.do_lon == 0:
        return 0.0
    return max(-1.0, min(1.0, v1.tich_vo_huong(v2) / (v1.do_lon * v2.do_lon)))


def main():
    cau_1 = "Trí tuệ nhân tạo hỗ trợ giải bài toán tìm kiếm và suy diễn"
    cau_2 = "Tri tue nhan tao giai quyet cac bai toan tim kiem tren do thi"
    sim = do_tuong_dong_cosin(cau_1, cau_2)
    print(f"Do tuong dong Cosine: {sim:.4f} ({sim * 100:.2f}%)")


if __name__ == "__main__":
    main()
'''

SKELETON_OOP_SEARCH_NODE = '''# Chuong 1 & 3: Lop NutTimKiem bieu dien nut trong thuat toan tim kiem A* / BFS / UCS
import heapq


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


def main():
    # Minh hoa truy vet duong di va f_cost cho A*
    n0 = NutTimKiem("Arad", parent=None, action=None, g=0, h=366)
    n1 = NutTimKiem("Sibiu", parent=n0, action="Arad->Sibiu", g=140, h=253)
    n2 = NutTimKiem("Rimnicu Vilcea", parent=n1, action="Sibiu->RV", g=220, h=193)
    n3 = NutTimKiem("Pitesti", parent=n2, action="RV->Pitesti", g=317, h=100)
    n4 = NutTimKiem("Bucharest", parent=n3, action="Pitesti->Bucharest", g=418, h=0)

    print("Duong di truy vet:", " -> ".join(n4.truy_vet_duong_di()))
    print(f"Tong chi phi f(n) tai dich: {n4.f_cost():.1f}")


if __name__ == "__main__":
    main()
'''

SKELETON_PURE_VOWEL_COSINE = '''# Bai 2.1: Vector hoa nguyen am & Do tuong dong Cosine
import math


def vector_nguyen_am(text: str) -> list[int]:
    lowered = text.lower()
    return [lowered.count(ch) for ch in "aeiou"]


def do_tuong_dong_cosine(v1: list[int], v2: list[int]) -> float:
    if len(v1) != len(v2):
        raise ValueError("Hai vector phai co cung do dai.")
    norm1 = math.sqrt(sum(x * x for x in v1))
    norm2 = math.sqrt(sum(y * y for y in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    dot_val = sum(x * y for x, y in zip(v1, v2))
    return float(dot_val / (norm1 * norm2))


def main():
    s1 = "Artificial Intelligence"
    s2 = "Automated Reasoning"
    v1 = vector_nguyen_am(s1)
    v2 = vector_nguyen_am(s2)
    v0 = vector_nguyen_am("Rhythm")
    print("Vector 1:", v1)
    print("Vector 2:", v2)
    print(f"Cosine(v1, v2): {do_tuong_dong_cosine(v1, v2):.6f}")
    print(f"Bien vector 0 : {do_tuong_dong_cosine(v1, v0):.1f}")


if __name__ == "__main__":
    main()
'''

SKELETON_PURE_GRAPH_DICT_BFS_DFS = '''# Bai 4.1: Cai dat BFS (FIFO) va DFS (LIFO) tren do thi bieu dien bang dict
from collections import deque


def bfs(graph, start, goal):
    if start == goal:
        return [start]
    if start not in graph:
        return None
    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        current, path = queue.popleft()
        for neighbor in graph.get(current, []):
            if neighbor == goal:
                return path + [neighbor]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None


def dfs(graph, start, goal):
    if start == goal:
        return [start]
    if start not in graph:
        return None
    stack = [(start, [start])]
    visited = set()
    while stack:
        current, path = stack.pop()
        if current in visited:
            continue
        if current == goal:
            return path
        visited.add(current)
        for neighbor in reversed(graph.get(current, [])):
            if neighbor not in visited:
                stack.append((neighbor, path + [neighbor]))
    return None


def main():
    graph = {
        "A": ["B", "C"],
        "B": ["D", "E"],
        "C": ["F"],
        "D": [],
        "E": ["F"],
        "F": [],
    }
    print("Duong di BFS:", bfs(graph, "A", "F"))
    print("Duong di DFS:", dfs(graph, "A", "F"))


if __name__ == "__main__":
    main()
'''

SKELETON_PURE_PROP_FORWARD_CLAUSES = '''# Bai 4.2: Suy dien tien logic menh de & Dem rang buoc menh de tuyen vi pham
def suy_dien_tien(facts: dict[str, bool]) -> dict[str, bool]:
    ket_qua = {k: bool(v) for k, v in facts.items()}
    ket_qua["Q"] = bool(ket_qua.get("Q", False) or (ket_qua.get("C", False) and ket_qua.get("A", False)))
    ket_qua["H"] = bool(ket_qua.get("H", False) or (ket_qua.get("R", False) and ket_qua.get("I", False)))
    ket_qua["E"] = bool(ket_qua.get("E", False) or (ket_qua["Q"] and ket_qua["H"] and ket_qua.get("D", False)))
    ket_qua["S"] = bool(ket_qua.get("S", False) or ket_qua["E"])
    return ket_qua


def dem_rang_buoc_vi_pham(assignment: dict[str, bool], clauses: list[list[tuple[str, bool]]]) -> int:
    vi_pham = 0
    for clause in clauses:
        thoa_man = any(
            bien in assignment and bool(assignment[bien]) == bool(gia_tri_dung)
            for bien, gia_tri_dung in clause
        )
        if not thoa_man:
            vi_pham += 1
    return vi_pham


def main():
    facts = {"C": True, "A": True, "R": True, "I": False, "D": True}
    kq = suy_dien_tien(facts)
    print("Ket qua suy dien tien:", kq)
    clauses = [
        [("C", False), ("A", False), ("Q", True)],
        [("R", False), ("I", False), ("H", True)],
        [("Q", False), ("H", False), ("D", False), ("E", True)],
        [("E", False), ("S", True)],
    ]
    print("So menh de vi pham:", dem_rang_buoc_vi_pham(kq, clauses))


if __name__ == "__main__":
    main()
'''

KNOWLEDGE_UNCERTAINTY_OOP_SKELETONS = {
    "ontology_tbox_abox_simpleai": {
        "id": "ontology_tbox_abox_simpleai",
        "category": "logic",
        "title": "Bieu dien tri thuc Ontology (TBox/ABox, subClassOf, disjoint, domain/range) ket hop SimpleAI (Chuong 8)",
        "keywords": [
            "ontology", "tbox", "abox", "subclassof", "is-a", "disjoint",
            "domain", "range", "inverse", "symmetric", "mang ngu nghia",
            "semantic network", "bieu dien tri thuc", "ca the", "instance",
        ],
        "code": SKELETON_ONTOLOGY_TBOX_ABOX_SIMPLEAI,
    },
    "frame_inheritance_conflict": {
        "id": "frame_inheritance_conflict",
        "category": "logic",
        "title": "He thong Khung (Frames) da ke thua, ghi de va phat hien mau thuan Nixon Diamond (Chuong 8)",
        "keywords": [
            "frame", "khung", "da ke thua", "multiple inheritance", "slots",
            "ghi de", "override", "nixon", "mau thuan ke thua", "chuong 8",
        ],
        "code": SKELETON_FRAME_INHERITANCE,
    },
    "logic_backward_chaining_hybrid": {
        "id": "logic_backward_chaining_hybrid",
        "category": "logic",
        "title": "Suy dien lui (Backward Chaining) in vet chung minh ket hop SimpleAI SearchProblem (Chuong 6)",
        "keywords": [
            "backward chaining", "suy dien lui", "chung minh muc tieu",
            "luat horn", "vet suy luan", "backwardchainingproblem",
        ],
        "code": SKELETON_BACKWARD_CHAINING_HYBRID,
    },
    "prob_joint_conditional_bayes": {
        "id": "prob_joint_conditional_bayes",
        "category": "logic",
        "title": "Bang xac suat dong thoi, xac suat co dieu kien, doc lap va Dinh ly Bayes / Naive Bayes (Chuong 9)",
        "keywords": [
            "xac suat co dieu kien", "conditional probability", "phan phoi dong thoi",
            "joint probability", "dinh ly bayes", "naive bayes", "hau nghiem",
            "posterior", "prior", "likelihood", "chuong 9",
        ],
        "code": SKELETON_PROB_BAYES_JOINT,
    },
    "prob_bayesian_network_cpt": {
        "id": "prob_bayesian_network_cpt",
        "category": "logic",
        "title": "Mang Bayes (Bayesian Network CPT) & Suy dien chinh xac Enumeration-Ask (Chuong 9)",
        "keywords": [
            "mang bayes", "bayesian network", "cpt", "enumeration_ask",
            "burglary", "earthquake", "alarm", "suy dien xac suat",
        ],
        "code": SKELETON_BAYESIAN_NETWORK_ENUMERATION,
    },
    "fuzzy_sets_inference": {
        "id": "fuzzy_sets_inference",
        "category": "logic",
        "title": "Tap mo (Fuzzy Sets), phep toan mo, lat cat alpha va Giai mo trong tam Centroid (Chuong 9)",
        "keywords": [
            "tap mo", "fuzzy", "alpha cut", "lat cat alpha", "ham thuoc",
            "membership", "giai mo", "defuzzification", "centroid", "mamdani",
        ],
        "code": SKELETON_FUZZY_SETS_INFERENCE,
    },
    "oop_vector24_cosine_plagiarism": {
        "id": "oop_vector24_cosine_plagiarism",
        "category": "raw",
        "title": "Lop Vector24, khu dau tieng Viet va do tuong dong van ban Cosine (Buoi 1)",
        "keywords": [
            "vector24", "tich_vo_huong", "do_tuong_dong_cosin", "cosine",
            "khu_dau", "khudau", "dao van", "unicodedata",
        ],
        "code": SKELETON_OOP_VECTOR24_PLAGIARISM,
    },
    "oop_search_node_nuttimkiem": {
        "id": "oop_search_node_nuttimkiem",
        "category": "raw",
        "title": "Lop NutTimKiem (state, parent, action, g, h, f_cost, truy_vet_duong_di)",
        "keywords": [
            "nuttimkiem", "f_cost", "truy_vet_duong_di", "node cho bai toan tim kiem",
        ],
        "code": SKELETON_OOP_SEARCH_NODE,
    },
    "pure_vowel_vector_cosine": {
        "id": "pure_vowel_vector_cosine",
        "category": "raw",
        "title": "Vector hoa nguyen am aeiou va do tuong dong Cosine (vector_nguyen_am, do_tuong_dong_cosine)",
        "keywords": [
            "vector_nguyen_am", "do_tuong_dong_cosine", "aeiou", "nguyen am", "cosine",
        ],
        "code": SKELETON_PURE_VOWEL_COSINE,
    },
    "pure_graph_dict_bfs_dfs": {
        "id": "pure_graph_dict_bfs_dfs",
        "category": "raw",
        "title": "BFS (FIFO deque) va DFS (LIFO stack) tren do thi tu dien dict (bfs, dfs)",
        "keywords": [
            "bfs", "dfs", "fifo", "lifo", "deque", "visited", "do thi", "dict",
        ],
        "code": SKELETON_PURE_GRAPH_DICT_BFS_DFS,
    },
    "pure_prop_forward_clauses": {
        "id": "pure_prop_forward_clauses",
        "category": "logic",
        "title": "Suy dien tien logic menh de va dem rang buoc menh de tuyen vi pham (suy_dien_tien, dem_rang_buoc_vi_pham)",
        "keywords": [
            "suy_dien_tien", "dem_rang_buoc_vi_pham", "menh de tuyen", "clauses", "assignment", "facts",
        ],
        "code": SKELETON_PURE_PROP_FORWARD_CLAUSES,
    },
}
