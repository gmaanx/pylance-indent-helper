# -*- coding: utf-8 -*-
"""
Kho Phoi Vang Nhom 4: Lap trinh Logic miniKanren (kanren, sympy, toolz) & Suy dien Tien/Lui.
Chuan xac 100% theo Buoi06 (puzzle.py, family.py, states.py, prime.py, expression_matcher.py) va Buoi06Nhom.
"""

from typing import Dict, Any

SKELETON_KANREN_ZEBRA = '''from kanren import run, var, eq, membero
from kanren.core import lall

# Khai bao bien
people = var()

# Dinh nghia cac luat (Name, Pet, Color, Country)
rules = lall(
    # Co 4 nguoi
    eq((var(), var(), var(), var()), people),
    # Xe cua Steve mau xanh duong
    membero(('Steve', var(), 'blue', var()), people),
    # Nguoi nuoi meo song o Canada
    membero((var(), 'cat', var(), 'Canada'), people),
    # Matthew song o My
    membero(('Matthew', var(), var(), 'USA'), people),
    # Nguoi co xe mau den song o Uc
    membero((var(), var(), 'black', 'Australia'), people),
    # Jack nuoi meo
    membero(('Jack', 'cat', var(), var()), people),
    # Alfred song o Uc
    membero(('Alfred', var(), var(), 'Australia'), people),
    # Nguoi nuoi cho song o Phap
    membero((var(), 'dog', var(), 'France'), people),
    # Ai la nguoi nuoi tho
    membero((var(), 'rabbit', var(), var()), people),
)

if __name__ == '__main__':
    solutions = run(0, people, rules)
    output = [house for house in solutions[0] if 'rabbit' in house][0][0]

    print('\\n' + output + ' is the owner of the rabbit')
    print('\\nHere are all the details:')
    attribs = ['Name', 'Pet', 'Color', 'Country']
    print('\\n' + '\\t\\t'.join(attribs))
    print('=' * 57)
    for item in solutions[0]:
        print('')
        print('\\t\\t'.join([str(x) for x in item]))
'''

SKELETON_KANREN_FAMILY = '''from toolz import unique
from kanren import Relation, facts, run, conde, var

father = Relation()
mother = Relation()


def parent(x, y):
    return conde([father(x, y)], [mother(x, y)])


def grandparent(x, y):
    temp = var()
    return conde((parent(x, temp), parent(temp, y)))


def sibling(x, y):
    temp = var()
    return conde((parent(temp, x), parent(temp, y)))


def uncle(x, y):
    temp = var()
    return conde((father(temp, x), grandparent(temp, y)))


if __name__ == '__main__':
    facts(
        father,
        ('John', 'William'), ('John', 'David'), ('John', 'Adam'),
        ('William', 'Chris'), ('William', 'Stephanie'),
        ('David', 'Wayne'), ('David', 'Tiffany'), ('David', 'Julie'),
        ('David', 'Neil'), ('David', 'Peter'),
        ('Adam', 'Sophia'),
    )
    facts(
        mother,
        ('Megan', 'William'), ('Megan', 'David'), ('Megan', 'Adam'),
        ('Emma', 'Chris'), ('Emma', 'Stephanie'),
        ('Olivia', 'Wayne'), ('Olivia', 'Tiffany'), ('Olivia', 'Julie'),
        ('Olivia', 'Neil'), ('Olivia', 'Peter'),
        ('Lily', 'Sophia'),
    )

    x = var()

    # Con cua John
    name = 'John'
    output = run(0, x, father(name, x), results_filter=unique)
    print(f"\\nList of {name}'s children:")
    for item in output:
        print(item)

    # Me cua William
    name = 'William'
    output = run(0, x, mother(x, name), results_filter=unique)[0]
    print(f"\\n{name}'s mother:\\n{output}")

    # Cha me cua Adam
    name = 'Adam'
    output = run(0, x, parent(x, name), results_filter=unique)
    print(f"\\nList of {name}'s parents:")
    for item in output:
        print(item)

    # Ong ba cua Wayne
    name = 'Wayne'
    output = run(0, x, grandparent(x, name), results_filter=unique)
    print(f"\\nList of {name}'s grandparents:")
    for item in output:
        print(item)

    # Anh chi em ruot cua David
    name = 'David'
    output = run(0, x, sibling(x, name), results_filter=unique)
    siblings = [s for s in output if s != name]
    print(f"\\nList of {name}'s siblings:")
    for item in siblings:
        print(item)

    # Chu bac cua Tiffany
    name = 'Tiffany'
    name_father = run(0, x, father(x, name), results_filter=unique)[0]
    output = run(0, x, uncle(x, name), results_filter=unique)
    output = [u for u in output if u != name_father]
    print(f"\\nList of {name}'s uncles:")
    for item in output:
        print(item)

    # Tat ca cac cap vo chong
    a, b, c = var(), var(), var()
    output = run(0, (a, b), father(a, c), mother(b, c), results_filter=unique)
    print("\\nList of all spouses:")
    for item in output:
        print('Husband:', item[0], '<==> Wife:', item[1])
'''

SKELETON_KANREN_STATES = '''from toolz import unique
from kanren import run, fact, Relation, var

adjacent = Relation()
coastal = Relation()

COASTAL_STATES = [
    'Washington', 'Oregon', 'California', 'Texas', 'Louisiana',
    'Mississippi', 'Alabama', 'Georgia', 'Florida', 'South Carolina',
    'North Carolina', 'Virginia', 'Maryland', 'Delaware', 'New Jersey',
    'New York', 'Connecticut', 'Rhode Island', 'Massachusetts', 'Maine',
    'New Hampshire', 'Alaska', 'Hawaii',
]

ADJACENT_DATA = {
    'Oregon': ['Washington', 'Idaho', 'Nevada', 'California'],
    'Mississippi': ['Louisiana', 'Arkansas', 'Tennessee', 'Alabama'],
    'Arkansas': ['Missouri', 'Tennessee', 'Mississippi', 'Louisiana', 'Texas', 'Oklahoma'],
    'Kentucky': ['Indiana', 'Ohio', 'West Virginia', 'Virginia', 'Tennessee', 'Missouri', 'Illinois'],
    'Nevada': ['Idaho', 'Utah', 'Arizona', 'California', 'Oregon'],
    'Louisiana': ['Texas', 'Arkansas', 'Mississippi'],
}

for st in COASTAL_STATES:
    fact(coastal, st)

for head, neighbors in ADJACENT_DATA.items():
    for nb in neighbors:
        fact(adjacent, head, nb)
        fact(adjacent, nb, head)

if __name__ == '__main__':
    x = var()
    y = var()

    output = run(0, x, adjacent('Nevada', 'Louisiana'))
    print('Is Nevada adjacent to Louisiana?:', 'Yes' if len(output) else 'No')

    output = run(0, x, adjacent('Oregon', x), results_filter=unique)
    print('\\nList of states adjacent to Oregon:', list(output))

    output = run(0, x, adjacent('Mississippi', x), coastal(x), results_filter=unique)
    print('\\nList of coastal states adjacent to Mississippi:', list(output))

    output = run(0, x, adjacent('Arkansas', x), adjacent('Kentucky', x), results_filter=unique)
    print('\\nList of states adjacent to both Arkansas and Kentucky:', list(output))
'''

SKELETON_KANREN_PRIME = '''import itertools as it
from kanren import isvar, membero, run, var, eq
import kanren.core as lc
from sympy.ntheory.generate import prime, isprime


def check_prime(x):
    def check_prime_goal(S):
        x_val = lc.reify(x, S)
        if isvar(x_val):
            goal = lc.conde(([eq(x_val, p)] for p in map(prime, it.count(1))))
        else:
            goal = lc.succeed if isprime(x_val) else lc.fail
        yield from goal(S)

    return check_prime_goal


if __name__ == '__main__':
    x = var()
    list_nums = (23, 4, 27, 17, 13, 10, 21, 29, 3, 32, 11, 19)
    print('List of primes in the list:')
    print(set(run(0, x, membero(x, list_nums), check_prime(x))))

    print('\\nList of first 7 prime numbers:')
    print(run(7, x, check_prime(x)))
'''

SKELETON_KANREN_EXPRESSION = '''from toolz import unique
from kanren import run, var, fact
import kanren.assoccomm as la

add = 'addition'
mul = 'multiplication'

fact(la.commutative, mul)
fact(la.commutative, add)
fact(la.associative, mul)
fact(la.associative, add)

a, b, c = var('a'), var('b'), var('c')

expression_orig = (add, (mul, 3, -2), (mul, (add, 1, (mul, 2, 3)), -1))
expression1 = (add, (mul, (add, 1, (mul, 2, a)), b), (mul, 3, c))
expression2 = (add, (mul, c, 3), (mul, b, (add, (mul, 2, a), 1)))
expression3 = (add, (add, (mul, (mul, 2, a), b), b), (mul, 3, c))

if __name__ == '__main__':
    print(run(0, (a, b, c), la.eq_assoccomm(expression1, expression_orig), results_filter=unique))
    print(run(0, (a, b, c), la.eq_assoccomm(expression2, expression_orig), results_filter=unique))
    print(run(0, (a, b, c), la.eq_assoccomm(expression3, expression_orig), results_filter=unique))
'''

SKELETON_CHAINING_REASONING = '''from simpleai.search import SearchProblem, depth_first

# Tap su kien ban dau (Facts) va Tap luat suy dien (Rules)
FACTS = {'C', 'A', 'R', 'I', 'D'}
RULES = [
    ('R1', ('C', 'A'), 'Q'),
    ('R2', ('R', 'I'), 'H'),
    ('R3', ('Q', 'H', 'D'), 'E'),
    ('R4', ('E',), 'S'),
]
GOAL = 'S'


def forward_chaining(facts, rules, goal):
    da_biet = set(facts)
    vet = []
    thay_doi = True
    while thay_doi:
        thay_doi = False
        for ma_luat, tien_de, ket_luan in rules:
            if ket_luan not in da_biet and all(x in da_biet for x in tien_de):
                da_biet.add(ket_luan)
                vet.append(f"{ma_luat}: {' & '.join(tien_de)} -> {ket_luan}")
                thay_doi = True
                if ket_luan == goal:
                    return True, vet, da_biet
    return (goal in da_biet), vet, da_biet


def backward_chaining(facts, rules, goal):
    tap_facts = set(facts)
    da_cm = set()
    vet = []

    def chung_minh(muc_tieu, dang_xet):
        if muc_tieu in tap_facts:
            vet.append(f"{muc_tieu} thuoc Facts")
            return True
        if muc_tieu in da_cm:
            return True
        if muc_tieu in dang_xet:
            return False
        for ma_luat, tien_de, ket_luan in rules:
            if ket_luan == muc_tieu:
                if all(chung_minh(con, dang_xet | {muc_tieu}) for con in tien_de):
                    da_cm.add(muc_tieu)
                    vet.append(f"{ma_luat}: {' & '.join(tien_de)} -> {muc_tieu}")
                    return True
        return False

    kq = chung_minh(goal, frozenset())
    return kq, vet


class BaiToanBackwardSimpleAI(SearchProblem):
    def __init__(self, facts, rules, goal):
        self.tap_facts = set(facts)
        self.ds_rules = rules
        super().__init__(initial_state=(goal,))

    def actions(self, state):
        if not state:
            return []
        hien_tai = state[0]
        ds = []
        if hien_tai in self.tap_facts:
            ds.append(('FACT', hien_tai, ()))
        for ma, td, kl in self.ds_rules:
            if kl == hien_tai:
                ds.append((ma, hien_tai, td))
        return ds

    def result(self, state, action):
        _, _, muc_tieu_moi = action
        return tuple(dict.fromkeys(muc_tieu_moi + state[1:]))

    def is_goal(self, state):
        return len(state) == 0


if __name__ == '__main__':
    ok_fw, vet_fw, _ = forward_chaining(FACTS, RULES, GOAL)
    print(f"Forward Chaining (Goal={GOAL}): {ok_fw} | Vet: {vet_fw}")

    ok_bw, vet_bw = backward_chaining(FACTS, RULES, GOAL)
    print(f"Backward Chaining (Goal={GOAL}): {ok_bw} | Vet: {vet_bw}")

    kq_simpleai = depth_first(BaiToanBackwardSimpleAI(FACTS, RULES, GOAL), graph_search=True)
    print(f"SimpleAI Backward DFS: {kq_simpleai is not None}")
'''

LOGIC_KANREN_SKELETONS: Dict[str, Dict[str, Any]] = {
    "kanren_zebra_puzzle": {
        "id": "kanren_zebra_puzzle",
        "category": "logic",
        "title": "Bai toan Zebra / Logic Grid Puzzle bang miniKanren (lall, eq, membero - Buoi06/puzzle.py)",
        "keywords": [
            "kanren", "minikanren", "lall", "membero", "zebra", "steve", "matthew",
            "rabbit", "nuoi tho", "nuoi meo", "nuoi cho", "puzzle.py", "buoi06"
        ],
        "code": SKELETON_KANREN_ZEBRA,
    },
    "kanren_family": {
        "id": "kanren_family",
        "category": "logic",
        "title": "Cay gia pha / Quan he gia dinh bang miniKanren (Relation, facts, conde - Buoi06/family.py)",
        "keywords": [
            "family", "gia dinh", "gia pha", "father", "mother", "parent",
            "grandparent", "sibling", "uncle", "spouses", "conde", "relation", "facts"
        ],
        "code": SKELETON_KANREN_FAMILY,
    },
    "kanren_states_map": {
        "id": "kanren_states_map",
        "category": "logic",
        "title": "Truy van Bang giap ranh & Ven bien bang miniKanren (adjacent, coastal - Buoi06/states.py)",
        "keywords": [
            "adjacent", "coastal", "bang ven bien", "bang giap ranh", "oregon",
            "mississippi", "nevada", "louisiana", "arkansas", "kentucky", "states.py"
        ],
        "code": SKELETON_KANREN_STATES,
    },
    "kanren_prime": {
        "id": "kanren_prime",
        "category": "logic",
        "title": "Kiem tra va Sinh so nguyen to bang miniKanren & SymPy (check_prime - Buoi06/prime.py)",
        "keywords": [
            "check_prime", "so nguyen to", "prime", "isprime", "sympy", "reify", "isvar"
        ],
        "code": SKELETON_KANREN_PRIME,
    },
    "kanren_expression_matcher": {
        "id": "kanren_expression_matcher",
        "category": "logic",
        "title": "So khop bieu thuc Giao hoan & Ket hop bang miniKanren (assoccomm - Buoi06/expression_matcher.py)",
        "keywords": [
            "assoccomm", "commutative", "associative", "eq_assoccomm",
            "giao hoan", "ket hop", "bieu thuc", "expression_matcher"
        ],
        "code": SKELETON_KANREN_EXPRESSION,
    },
    "logic_chaining": {
        "id": "logic_chaining",
        "category": "logic",
        "title": "Suy dien Tien (Forward Chaining) & Suy dien Lui (Backward Chaining + SimpleAI)",
        "keywords": [
            "backward_chaining", "forward_chaining", "suy dien lui", "suy dien tien",
            "tap luat", "tap su kien", "facts", "rules", "chung minh muc tieu"
        ],
        "code": SKETON_CHAINING if False else SKELETON_CHAINING_REASONING,
    },
}
