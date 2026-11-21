"""Check logic solvers and emitted standalone programs through the engine."""

import ast
import contextlib
import io
import itertools
import json
import random
import unittest
from unittest.mock import patch

from core_engine.engine_pipeline import process_request


def solve(problem):
    return process_request("# @solve " + json.dumps(problem, ensure_ascii=False), "instant")


class CourseLogicTests(unittest.TestCase):
    def output(self, problem):
        response = solve(problem)
        self.assertEqual(response.validation_status, "verified", response.error_detail)
        self.assertEqual(response.tier_used, "offline_" + problem["type"])
        destination = io.StringIO()
        with contextlib.redirect_stdout(destination):
            exec(compile(response.code, "<offline-course-logic>", "exec"), {"__name__": "__main__"})
        return ast.literal_eval(destination.getvalue())

    def test_entailment_reports_models_and_vacuous_truth(self):
        premise = ["iff", "P", ["not", "Q"]]
        query = ["xor", "P", "Q"]
        result = self.output({"type": "entailment", "premises": [premise], "query": query})
        self.assertEqual(result, {"entailed": True, "premises_satisfiable": True, "counterexample": None})
        result = self.output({"type": "entailment", "premises": [premise], "query": ["and", "P", "Q"]})
        self.assertEqual(result, {
            "entailed": False, "premises_satisfiable": True, "counterexample": {"P": False, "Q": True},
        })
        result = self.output({"type": "entailment", "premises": ["P", ["not", "P"]], "query": "Q"})
        self.assertEqual(result, {"entailed": True, "premises_satisfiable": False, "counterexample": None})
        self.assertTrue(self.output({"type": "entailment", "premises": [], "query": ["or", "P", ["not", "P"]]})["entailed"])

    def test_resolution_matches_exhaustive_models_and_proof_is_checkable(self):
        rng = random.Random(701)
        atoms = ("A", "B", "C")
        literals = [*atoms, *("!" + atom for atom in atoms)]
        cases = [
            ([[ "A" ], ["!A", "B"]], ["B"]),
            ([["A", "B"], ["!A", "C"], ["!B", "C"]], ["C"]),
            ([["A", "!A"]], ["B"]),
            ([[]], []),
            ([], []),
            ([], ["A", "!A"]),
        ]
        for _ in range(20):
            clauses = [rng.sample(literals, rng.randrange(1, 4)) for _ in range(rng.randrange(1, 9))]
            cases.append((clauses, rng.sample(literals, rng.randrange(1, 3))))

        for clauses, query in cases:
            with self.subTest(clauses=clauses, query=query):
                def true_in(literal, model):
                    atom = literal.lstrip("!")
                    return model[atom] != literal.startswith("!")

                models = [dict(zip(atoms, vector)) for vector in itertools.product((False, True), repeat=3)]
                expected = all(any(true_in(lit, model) for lit in query) for model in models
                               if all(any(true_in(lit, model) for lit in clause) for clause in clauses))
                result = self.output({"type": "resolution", "clauses": clauses, "query": query})
                self.assertEqual(result["entailed"], expected)
                if not expected:
                    self.assertEqual(result["proof"], [])
                    continue

                def opposite(literal):
                    return literal[1:] if literal.startswith("!") else "!" + literal

                verified = {}
                for step in result["proof"]:
                    output = set(step["clause"])
                    if step["source"] == "premise":
                        self.assertTrue(any(output == set(clause) for clause in clauses))
                    elif step["source"] == "negated_query":
                        self.assertTrue(any(output == {opposite(literal)} for literal in query))
                    else:
                        left, right = (verified[parent] for parent in step["parents"])
                        literal = step["pivot"]
                        self.assertIn(literal, left)
                        self.assertIn(opposite(literal), right)
                        self.assertEqual(output, (left - {literal}) | (right - {opposite(literal)}))
                    verified[step["id"]] = output
                self.assertEqual(result["proof"][-1]["clause"], [])

    def test_backward_chain_proves_goal_despite_cycle_and_checks_each_proof_step(self):
        rules = [
            {"if": ["B"], "then": "A"},
            {"if": ["A"], "then": "B"},
            {"if": ["Start"], "then": "A"},
            {"if": ["B", "Start"], "then": "Goal"},
            {"if": [], "then": "Irrelevant"},
            {"if": ["D"], "then": "C"},
            {"if": ["C"], "then": "D"},
        ]
        problem = {"type": "backward_horn", "facts": ["Start"], "rules": rules, "query": "Goal"}
        result = self.output(problem)
        self.assertTrue(result["entailed"])
        self.assertNotIn("Irrelevant", result["visited"])
        known = set(problem["facts"])
        for step in result["proof"]:
            rule = step["rule"]
            if rule is None:
                self.assertIn(step["goal"], known)
            else:
                self.assertEqual(rules[rule], {"if": step["premises"], "then": step["goal"]})
            self.assertTrue(set(step["premises"]) <= known)
            known.add(step["goal"])
        self.assertIn("Goal", known)
        missing = self.output({**problem, "query": "C"})
        self.assertEqual(missing, {"entailed": False, "proof": [], "visited": ["C", "D"]})

    def test_relation_joins_filter_duplicates_and_bind_repeated_variables(self):
        var = lambda name: {"var": name}
        facts = {
            "parent": [["H", "M"], ["H", "M"], ["M", "X"], ["M", "Y"], ["N", "W"]],
            "coastal": [["X"], ["W"]],
        }
        where = [
            {"relation": "parent", "args": ["H", var("middle")]},
            {"relation": "parent", "args": [var("middle"), var("child")]},
            {"relation": "coastal", "args": [var("child")]},
        ]
        problem = {"type": "relation", "facts": facts, "where": where, "select": ["child"]}
        self.assertEqual(self.output(problem), {"matched": True, "rows": [["X"]]})
        paired = self.output({
            **problem,
            "where": [
                {"relation": "parent", "args": [var("person"), var("left")]},
                {"relation": "parent", "args": [var("person"), var("right")]},
            ],
            "select": ["left", "right"],
            "distinct": [["left", "right"]],
        })
        self.assertEqual(paired["rows"], [["X", "Y"], ["Y", "X"]])
        absent = self.output({
            **problem, "select": [], "where": [{"relation": "parent", "args": [var("p"), var("p")]}],
        })
        self.assertEqual(absent, {"matched": False, "rows": []})
        exists = self.output({**problem, "select": []})
        self.assertEqual(exists, {"matched": True, "rows": [[]]})

    def test_primes_against_trial_division_and_large_composite(self):
        values = [*range(-25, 200), 2, 49, 123456789, 999999937, 999950884]
        result = self.output({"type": "primes", "values": values, "count": 50})

        def prime(value):
            return value > 1 and all(value % divisor for divisor in range(2, int(value ** 0.5) + 1))

        self.assertEqual(result["selected"], [value for value in values if prime(value)])
        self.assertEqual(result["first"], [value for value in range(400) if prime(value)][:50])
        self.assertEqual(self.output({"type": "primes", "values": [-5, -8]})["selected"], [])

    def test_expression_match_flattens_same_operator_and_keeps_nested_operators(self):
        problem = {
            "type": "expression_match",
            "pattern": ["+", ["*", 2, {"var": "X"}], ["+", "k", {"var": "Y"}]],
            "target": ["+", ["+", 4, "k"], ["*", 3, 2]],
            "domains": {"X": [3, 4], "Y": [3, 4]},
        }
        self.assertEqual(self.output(problem), {"matched": True, "bindings": [{"X": 3, "Y": 4}]})
        ground = {"type": "expression_match", "target": ["*", "a", 2, 3]}
        self.assertEqual(self.output({**ground, "pattern": ["*", 3, ["*", 2, "a"]]}),
                         {"matched": True, "bindings": [{}]})
        compared = self.output({
            "type": "expression_match",
            "pattern": ["*", 2, ["+", "a", "b"]],
            "target": ["+", ["*", 2, "a"], ["*", 2, "b"]],
        })
        self.assertEqual(compared, {"matched": False, "bindings": []})
        self.assertFalse(self.output({"type": "expression_match", "pattern": ["+", 2, 3], "target": 5})["matched"])

    def test_expression_match_reuses_variable_bindings_and_deduplicates_domain_terms(self):
        variable = {"var": "X"}
        problem = {
            "type": "expression_match",
            "pattern": ["+", variable, variable],
            "target": ["+", 1, 3, 2, ["+", 2, 3, 1]],
            "domains": {"X": [["+", 1, ["+", 2, 3]], ["+", 3, 1, 2], ["+", 1, 2]]},
        }
        self.assertEqual(self.output(problem), {"matched": True, "bindings": [{"X": ["+", 1, ["+", 2, 3]]}]})
        self.assertFalse(self.output({**problem, "target": ["+", 1, 3, 1, 2]})["matched"])
        pair = {
            "type": "expression_match", "pattern": ["+", variable, {"var": "Y"}],
            "target": ["+", "b", "a"], "domains": {"X": ["a", "b"], "Y": ["a", "b"]},
        }
        self.assertEqual(self.output(pair)["bindings"], [{"X": "a", "Y": "b"}, {"X": "b", "Y": "a"}])

    def test_limits_and_unsupported_syntax_do_not_claim_success(self):
        cases = [
            ("invalid", {"type": "entailment", "premises": [], "query": ["not", "A", "B"]}),
            ("invalid", {"type": "resolution", "clauses": [["!!P"]], "query": ["P"]}),
            ("invalid", {"type": "relation", "facts": {"parent": [["A", "B"]]},
                         "where": [{"relation": "parent", "args": ["A", "B"]}], "select": ["missing"]}),
            ("needs_input", {"type": "primes"}),
            ("needs_input", {"type": "expression_match", "pattern": {"var": "X"}, "target": 1}),
            ("invalid", {"type": "expression_match", "pattern": 1, "target": {"var": "X"}}),
            ("unsupported", {"type": "expression_match", "pattern": ["-", 1, 2], "target": 1}),
        ]
        for status, problem in cases:
            with self.subTest(problem=problem):
                result = solve(problem)
                self.assertEqual(result.validation_status, status, result.error_detail)
                self.assertFalse(result.code)
        limits = [
            ("MAX_RESOLUTION_PAIRS", {"type": "resolution", "clauses": [["P"]], "query": ["P"]}),
            ("MAX_HORN_STEPS", {"type": "backward_horn", "facts": ["P"], "query": "P", "rules": []}),
            ("MAX_JOIN_STEPS", {"type": "relation", "facts": {"r": [[1]]}, "select": [],
                               "where": [{"relation": "r", "args": [1]}]}),
            ("MAX_EXPRESSION_WORK", {"type": "expression_match", "pattern": 1, "target": 1}),
            ("MAX_EXPRESSION_BINDINGS", {"type": "expression_match", "pattern": 1, "target": 1}),
        ]
        for constant, problem in limits:
            with patch("core_engine.offline_course_logic." + constant, 0):
                result = solve(problem)
            self.assertEqual(result.validation_status, "limit")
            self.assertFalse(result.code)


if __name__ == "__main__":
    unittest.main()
