import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from core_engine import brain_router
from core_engine.cli_entry import decode_request
from core_engine.config_manager import ConfigManager


class LocalModelTests(unittest.TestCase):
    def request(self, **settings):
        payload = {"text": "# Viết hàm chạy kiểm thử với dữ kiện tự chọn", **settings}
        return decode_request(json.dumps(payload), allow_network=True)

    def test_offline_and_exact_solvers_bypass_ollama(self):
        with patch.object(brain_router, "_post_json") as post:
            self.request(mode="instant", allow_local=True)
            exact = decode_request(json.dumps({
                "text": '# @solve {"type":"vector24"}', "allow_local": True,
            }), allow_network=True)
        post.assert_not_called()
        self.assertTrue(exact["verified_ok"])

    def test_alt_five_sends_recognized_exercises_to_ollama(self):
        for prompt in ('# Liệt kê 3 số nguyên tố đầu tiên.', '# @solve {"type":"vector24"}'):
            with (
                self.subTest(prompt=prompt),
                patch("core_engine.engine_pipeline.solve_offline") as offline,
                patch("core_engine.engine_pipeline.call_tier1_cloud_llm") as cloud,
                patch.object(brain_router, "_post_json", side_effect=[
                    {}, {"done": True, "response": "def result():\n    return 3"},
                ]) as post,
            ):
                result = decode_request(json.dumps({
                    "text": prompt, "mode": "local", "allow_local": True, "allow_cloud": True,
                }), allow_network=True)
                offline.assert_not_called()
                cloud.assert_not_called()
                self.assertEqual(post.call_count, 2)
                self.assertIn(prompt, post.call_args.args[2]["prompt"])
                self.assertEqual(result["tier_used"], "tier2_ollama")
                self.assertEqual(result["validation_status"], "syntax_checked")
                self.assertTrue(result["code"].startswith("# [Alt+5 · Ollama |"))

    def test_alt_five_surfaces_ollama_errors_without_an_offline_result(self):
        error = HTTPError("http://127.0.0.1:11434/api/show", 404, "not found", {}, None)
        with patch.object(brain_router, "_post_json", side_effect=error) as post:
            result = self.request(text='# @solve {"type":"vector24"}', mode="local", allow_local=True)
        post.assert_called_once()
        self.assertFalse(result["code"])
        self.assertIn("Ollama chưa có model", " ".join(result["diagnostics"]))

    def test_alt_five_still_requires_local_authorization(self):
        with patch.object(brain_router, "_post_json") as post:
            result = decode_request(json.dumps({
                "text": '# @solve {"type":"vector24"}', "mode": "local", "allow_local": True,
            }))
        post.assert_not_called()
        self.assertFalse(result["code"])

    def test_local_metadata_probe_precedes_prompt_and_keeps_model(self):
        with (
            patch.object(brain_router.CONFIG, "get", side_effect=lambda field, fallback=None: "fixture:1b" if field == "local_model" else fallback),
            patch.object(brain_router, "_post_json", side_effect=[{}, {"done": True, "response": "def result():\n    return 3"}]) as post,
        ):
            response = self.request(allow_local=True)
        self.assertEqual(response["validation_status"], "syntax_checked")
        self.assertEqual(response["tier_used"], "tier2_ollama")
        self.assertEqual([call.args[1] for call in post.call_args_list], [
            "http://127.0.0.1:11434/api/show", "http://127.0.0.1:11434/api/generate",
        ])
        self.assertEqual(post.call_args_list[0].args[2], {"model": "fixture:1b"})
        self.assertIn("Viết hàm", post.call_args_list[1].args[2]["prompt"])

    def test_remote_and_missing_models_receive_no_prompt(self):
        with patch.object(brain_router, "_post_json", return_value={"remote_host": "fixture"}) as post:
            response = self.request(allow_local=True)
        post.assert_called_once()
        self.assertFalse(response["code"])
        self.assertIn("từ xa", " ".join(response["diagnostics"]))

        error = HTTPError("http://127.0.0.1:11434/api/show", 404, "not found", {}, None)
        with patch.object(brain_router, "_post_json", side_effect=error) as post:
            response = self.request(allow_local=True)
        post.assert_called_once()
        self.assertIn("setup_ollama.bat", " ".join(response["diagnostics"]))

    def test_truncated_generation_cannot_open_a_preview(self):
        with patch.object(brain_router, "_post_json", side_effect=[
            {}, {"done": True, "done_reason": "length", "response": "def ready():\n    pass"},
        ]):
            response = self.request(allow_local=True)
        self.assertFalse(response["code"])
        self.assertIn("chưa trả mã hoàn chỉnh", " ".join(response["diagnostics"]))

    def test_runtime_model_overrides_older_model_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory) / "Programs" / "PylanceHelper"
            install.mkdir(parents=True)
            (install / "runtime.json").write_text('{"localModel":"configured:1b"}', encoding="utf-8")
            (install / "models.json").write_text('{"local_model":"old:1b","groq_model":"custom"}', encoding="utf-8")
            with patch.dict("os.environ", {"LOCALAPPDATA": directory}):
                config = ConfigManager()
                local = Path(directory) / "PylanceHelperLocalAI"
                local.mkdir()
                (local / "runtime.json").write_text('{"localModel":"separate:1b"}', encoding="utf-8")
                separate = ConfigManager()
        self.assertEqual(config.get("local_model"), "configured:1b")
        self.assertEqual(config.get("groq_model"), "custom")
        self.assertEqual(separate.get("local_model"), "separate:1b")
        self.assertEqual(separate.get("groq_model"), "custom")


if __name__ == "__main__":
    unittest.main()
