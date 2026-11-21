import json
import unittest
from unittest.mock import patch

from core_engine.cli_entry import decode_request
from core_engine.config_manager import CONFIG, session_credentials
from core_engine.engine_pipeline import EngineResponse


class CliPrivacyTests(unittest.TestCase):
    @staticmethod
    def request(**fields):
        return json.dumps({"text": "# Yêu cầu mẫu", **fields})

    @staticmethod
    def response():
        return EngineResponse(code="", verified_ok=False, tier_used="", elapsed_sec=0)

    def test_credentials_alone_do_not_enable_cloud(self):
        with patch("core_engine.cli_entry.process_request", return_value=self.response()) as process:
            result = decode_request(self.request(credentials={"gemini": "test-key"}), allow_network=True)
        self.assertFalse(process.call_args.kwargs["allow_cloud"])
        self.assertFalse(process.call_args.kwargs["allow_local"])
        self.assertNotIn("test-key", json.dumps(result))

    def test_explicit_cloud_credentials_available_for_one_request(self):
        seen = []

        def observe(**kwargs):
            seen.append((kwargs["allow_cloud"], CONFIG.get_api_key("groq")))
            return self.response()

        with patch("core_engine.cli_entry.process_request", side_effect=observe):
            result = decode_request(
                self.request(allow_cloud=True, credentials={"groq": "fixture-key"}),
                allow_network=True,
            )
            decode_request(self.request(), allow_network=True)
        self.assertEqual(seen, [(True, "fixture-key"), (False, "")])
        self.assertEqual(CONFIG.get_api_key("groq"), "")
        self.assertNotIn("fixture-key", json.dumps(result))

    def test_loopback_request_cannot_enable_cloud_or_local(self):
        with patch("core_engine.cli_entry.process_request", return_value=self.response()) as process:
            decode_request(self.request(allow_cloud=True, allow_local=True, credentials={"groq": "fixture-key"}))
        self.assertFalse(process.call_args.kwargs["allow_cloud"])
        self.assertFalse(process.call_args.kwargs["allow_local"])

    def test_cloud_wrong_provider_is_rejected_without_running_engine(self):
        with patch("core_engine.cli_entry.process_request") as process:
            result = decode_request(self.request(allow_cloud=True, credentials={"other": "fixture-key"}), allow_network=True)
        process.assert_not_called()
        self.assertEqual(result["validation_status"], "invalid")

    def test_nested_credentials_reset_after_failure(self):
        with session_credentials({"groq": "outer"}):
            with self.assertRaises(RuntimeError), session_credentials({"groq": "inner"}):
                self.assertEqual(CONFIG.get_api_key("groq"), "inner")
                raise RuntimeError("test fixture")
            self.assertEqual(CONFIG.get_api_key("groq"), "outer")
        self.assertEqual(CONFIG.get_api_key("groq"), "")

    def test_legacy_environment_key_not_loaded(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "should-not-load"}):
            self.assertEqual(CONFIG.get_api_key("gemini"), "")


if __name__ == "__main__":
    unittest.main()
