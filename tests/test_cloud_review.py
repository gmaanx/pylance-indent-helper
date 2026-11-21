"""Exercise the Cloud draft/review boundary with deterministic providers."""

import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

from core_engine import brain_router, cloud_review
from core_engine.cli_entry import decode_request


REQUEST = "# Viết hàm solve chỉ dùng số chẵn.\n# In ở dạng JSON, trả danh sách rỗng khi không có kết quả.\n"
DRAFT = "def solve(values):\n    return list(values)"
CORRECTED = "def solve(values):\n    return [value for value in values if value % 2 == 0]"
AREAS = ("input", "algorithm", "constraints", "output", "edge_cases")


def make_review(code=CORRECTED, *, unresolved=False):
    checks = {area: {"status": "ok", "detail": "Đã đối chiếu"} for area in AREAS}
    if unresolved:
        checks["output"] = {"status": "unresolved", "detail": "Còn thiếu định dạng JSON."}
    return json.dumps({"decision": "revise" if code else "keep", "code": code, "checks": checks})


def request(text=REQUEST, *, enabled=True, keys=None, mode="full", allow_network=True):
    return decode_request(json.dumps({
        "text": text,
        "mode": mode,
        "allow_cloud": enabled,
        "credentials": {"groq": "fixture-key"} if keys is None else keys,
    }), allow_network=allow_network)


class CloudReviewTests(unittest.TestCase):
    def test_review_sees_exact_original_and_repairs_omission_at_same_provider(self):
        with patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, make_review()]) as provider:
            response = request()

        self.assertEqual(provider.call_count, 2)
        first, second = (call.args for call in provider.call_args_list)
        self.assertEqual(first[:4], second[:4])  # Same endpoint, model and credential.
        self.assertEqual(first[0], "groq")
        self.assertIn(REQUEST, first[5])
        self.assertEqual(json.loads(second[5]), {"original_request": REQUEST, "draft": DRAFT, "syntax_issue": ""})
        self.assertNotIn("fixture-key", second[5])
        self.assertIn(CORRECTED, response["code"])
        self.assertEqual(response["validation_status"], "syntax_checked")
        self.assertFalse(response["verified_ok"])

    def test_malformed_invalid_or_hollow_revision_leaves_the_draft_available(self):
        ambiguous = make_review().replace('"decision": "revise"', '"decision": "keep", "decision": "revise"')
        replies = ("not JSON", ambiguous, make_review("if ???"), make_review("print('done')"),
                   make_review("def solve(values):\n    raise NotImplementedError()"))
        for reply in replies:
            with self.subTest(reply=reply), patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, reply]):
                response = request()
                self.assertIn(DRAFT, response["code"])
                self.assertFalse(response["verified_ok"])
                self.assertTrue(any("rà soát" in note or "bản nháp" in note for note in response["diagnostics"]))

    def test_unresolved_constraint_is_reported_and_does_not_replace_draft(self):
        with patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, make_review(unresolved=True)]):
            response = request()

        self.assertIn(DRAFT, response["code"])
        self.assertTrue(any("thiếu định dạng JSON" in note for note in response["diagnostics"]))
        self.assertFalse(response["verified_ok"])

    def test_second_request_can_repair_syntax_but_draft_is_not_executed(self):
        repaired = "raise AssertionError('Candidate must not execute')"
        with patch.object(brain_router, "_request_cloud", side_effect=["x = ", make_review(repaired)]) as provider:
            response = request()

        self.assertIn(repaired, response["code"])
        self.assertEqual(response["validation_status"], "syntax_checked")
        self.assertFalse(response["verified_ok"])
        self.assertIn("lỗi cú pháp", provider.call_args.args[5])

    def test_failed_network_does_not_try_other_providers_or_expose_error_content(self):
        keys = {"groq": "ignored-key", "gemini": "fixture-key"}
        with patch.object(brain_router, "_request_cloud", side_effect=URLError("fixture-key")) as provider:
            response = request(keys=keys)

        provider.assert_called_once()
        self.assertEqual(provider.call_args.args[0], "gemini")
        self.assertNotIn("fixture-key", str(response))
        self.assertFalse(response["verified_ok"])

    def test_failed_review_keeps_draft_without_requesting_another_model(self):
        keys = {"groq": "ignored-key", "gemini": "fixture-key"}
        with patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, TimeoutError()]) as provider:
            response = request(keys=keys)

        self.assertEqual(provider.call_count, 2)
        self.assertEqual([call.args[0] for call in provider.call_args_list], ["gemini", "gemini"])
        self.assertIn(DRAFT, response["code"])
        self.assertTrue(any("chưa hoàn tất" in note for note in response["diagnostics"]))

    def test_offline_exact_solver_and_opt_out_skip_cloud(self):
        coin = '# @solve {"type":"coin_change","amount":17,"denominations":[4,7,9]}'
        with patch.object(brain_router, "_request_cloud") as provider:
            self.assertFalse(request(enabled=False)["verified_ok"])
            self.assertFalse(request(allow_network=False)["verified_ok"])
            self.assertTrue(request(coin)["verified_ok"])

        provider.assert_not_called()

    def test_locally_computes_reference_instead_of_trusting_model_claim(self):
        excerpt = "Đổi 17 với mệnh giá 4, 7, 9, số đồng không giới hạn."
        text = "# Viết một hàm tổng quát. Ca đối chiếu: " + excerpt
        case = {
            "source_excerpt": excerpt,
            "spec": {"type": "coin_change", "amount": 17, "denominations": [4, 7, 9]},
        }
        report = json.loads(make_review())
        for claimed, matches in ((3, True), (2, False)):
            with self.subTest(claimed=claimed):
                report["offline_case"] = {**case, "expected": claimed}
                with patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, json.dumps(report)]) as provider:
                    response = request(text)
                self.assertEqual(provider.call_count, 2)
                if matches:
                    self.assertIn(CORRECTED, response["code"])
                    self.assertEqual(response["validation_status"], "syntax_checked")
                else:
                    self.assertEqual(response["code"], "")
                    self.assertEqual(response["validation_status"], "invalid")
                self.assertTrue(any("Số đồng tối thiểu: 3" in note for note in response["diagnostics"]))
                self.assertFalse(response["verified_ok"])

        report["offline_case"] = {**case, "source_excerpt": "Không có trong đề", "expected": 3}
        with patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, json.dumps(report)]):
            response = request(text)
        self.assertFalse(any("Bộ giải offline" in note for note in response["diagnostics"]))

    def test_later_contradiction_blocks_draft_even_with_unresolved_review_item(self):
        first = "Đổi 17 với mệnh giá 4, 7, 9, số đồng không giới hạn."
        second = "Đổi 1 với mệnh giá 4, 7, 9, số đồng không giới hạn."
        text = f"# Viết một hàm tổng quát.\n# {first}\n# {second}"
        report = json.loads(make_review(unresolved=True))
        report["offline_cases"] = [
            {
                "source_excerpt": first,
                "spec": {"type": "coin_change", "amount": 17, "denominations": [4, 7, 9]},
                "expected": 3,
            },
            {
                "source_excerpt": second,
                "spec": {"type": "coin_change", "amount": 1, "denominations": [4, 7, 9]},
                "expected": 0,
            },
        ]
        with patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, json.dumps(report)]) as provider:
            response = request(text)

        self.assertEqual(provider.call_count, 2)
        self.assertEqual(response["code"], "")
        self.assertEqual(response["validation_status"], "invalid")
        self.assertFalse(response["verified_ok"])
        notes = "\n".join(response["diagnostics"])
        self.assertIn("khớp ca 1", notes)
        self.assertIn("lệch ca 2", notes)

    def test_matching_cases_remain_syntax_checked_and_respect_the_local_case_limit(self):
        excerpts = [f"Đổi {amount} với mệnh giá 4, số đồng không giới hạn." for amount in (4, 8, 12, 16, 20)]
        text = "# Viết hàm tổng quát.\n# " + "\n# ".join(excerpts)
        report = json.loads(make_review())
        report["offline_cases"] = [
            {
                "source_excerpt": excerpt,
                "spec": {"type": "coin_change", "amount": count * 4, "denominations": [4]},
                "expected": count,
            }
            for count, excerpt in enumerate(excerpts, start=1)
        ]
        with (
            patch.object(brain_router, "_request_cloud", side_effect=[DRAFT, json.dumps(report)]) as provider,
            patch.object(cloud_review, "solve_spec", wraps=cloud_review.solve_spec) as solver,
        ):
            response = request(text)

        self.assertEqual(provider.call_count, 2)
        self.assertEqual(solver.call_count, 4)
        self.assertIn(CORRECTED, response["code"])
        self.assertIn("khớp ca 4", "\n".join(response["diagnostics"]))
        self.assertEqual(response["validation_status"], "syntax_checked")
        self.assertFalse(response["verified_ok"])


if __name__ == "__main__":
    unittest.main()
