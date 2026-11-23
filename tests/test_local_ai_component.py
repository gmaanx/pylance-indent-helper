"""Exercise the standalone Ollama component without changing the machine."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from setup_lab import local_ai


class LocalAiComponentTests(unittest.TestCase):
    executable = Path("C:/Ollama/ollama.exe")
    digest = "a" * 64
    model = local_ai.DEFAULT_MODEL

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / "local-ai" / "runtime.json"
        state_path = patch.object(local_ai, "_state_path", return_value=self.state)
        state_path.start()
        self.addCleanup(state_path.stop)

    def tag(self, model=None, digest=None):
        return {"name": model or self.model, "digest": digest or self.digest}

    def read(self):
        return json.loads(self.state.read_text(encoding="utf-8"))

    def write(self, **state):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(json.dumps(state), encoding="utf-8")

    def test_existing_app_and_model_are_reused_without_claiming_them(self):
        with patch.object(local_ai, "_models", return_value=[self.tag()]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run") as run:
            local_ai.install_local_ai()
            self.assertEqual(self.read()["localModel"], self.model)
            self.assertEqual(self.read()["managedModels"], {})
            self.assertNotIn("managedAppExecutable", self.read())
            local_ai.uninstall_local_ai()
        self.assertFalse(self.state.exists())
        run.assert_not_called()

    def test_new_app_and_model_are_recorded_and_removed(self):
        with patch.object(local_ai, "_models", side_effect=[None, [], [self.tag()]]), \
                patch.object(local_ai, "find_ollama", return_value=None), \
                patch.object(local_ai, "_install_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run") as run:
            local_ai.install_local_ai()
        self.assertEqual(run.call_args.args[0], [str(self.executable), "pull", self.model])
        self.assertEqual(self.read()["managedModels"], {self.model: self.digest})
        self.assertEqual(self.read()["managedAppExecutable"], str(self.executable))

        with patch.object(local_ai, "_models", side_effect=[[self.tag()], []]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_winget", return_value="winget.exe"), \
                patch.object(local_ai, "_run") as run:
            local_ai.uninstall_local_ai()
        remove, uninstall = run.call_args_list
        self.assertEqual(remove.args[0], [str(self.executable), "rm", self.model])
        self.assertEqual(uninstall.args[0][:5], ["winget.exe", "uninstall", "--id", "Ollama.Ollama", "--exact"])
        self.assertIn("--silent", uninstall.args[0])
        self.assertFalse(self.state.exists())

    def test_user_model_added_to_managed_app_preserves_the_app(self):
        self.write(localModel=self.model, managedModels={self.model: self.digest}, managedAppExecutable=str(self.executable))
        user_tag = self.tag("other:latest")
        with patch.object(local_ai, "_models", side_effect=[[self.tag(), user_tag], [user_tag]]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_winget") as winget, \
                patch.object(local_ai, "_run") as run:
            local_ai.uninstall_local_ai()
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0], [str(self.executable), "rm", self.model])
        winget.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_model_replaced_at_same_tag_is_preserved(self):
        self.write(localModel=self.model, managedModels={self.model: self.digest}, managedAppExecutable=str(self.executable))
        with patch.object(local_ai, "_models", return_value=[self.tag(digest="b" * 64)]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run") as run:
            local_ai.uninstall_local_ai()
        run.assert_not_called()
        self.assertFalse(self.state.exists())

    def test_install_failure_keeps_new_package_ownership_and_previous_selection(self):
        prior = "old:latest"
        self.write(localModel=prior, managedModels={})
        with patch.object(local_ai, "_models", side_effect=[None, []]), \
                patch.object(local_ai, "find_ollama", return_value=None), \
                patch.object(local_ai, "_install_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run", side_effect=RuntimeError("pull failed")):
            with self.assertRaisesRegex(RuntimeError, "pull failed"):
                local_ai.install_local_ai(self.model)
        self.assertEqual(self.read()["localModel"], prior)
        self.assertEqual(self.read()["managedAppExecutable"], str(self.executable))
        self.assertEqual(self.read()["managedModels"], {})

    def test_uninstall_failure_keeps_pending_package_ownership(self):
        self.write(localModel=self.model, managedModels={self.model: self.digest}, managedAppExecutable=str(self.executable))
        with patch.object(local_ai, "_models", side_effect=[[self.tag()], []]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_winget", return_value="winget.exe"), \
                patch.object(local_ai, "_run", side_effect=[None, RuntimeError("uninstall failed")]):
            with self.assertRaisesRegex(RuntimeError, "uninstall failed"):
                local_ai.uninstall_local_ai()
        self.assertEqual(self.read()["managedAppExecutable"], str(self.executable))
        self.assertEqual(self.read()["managedModels"], {})
        self.assertNotIn("localModel", self.read())

    def test_migration_preserves_existing_independent_install_and_claims_no_resources(self):
        local_ai.migrate_legacy_local_ai({"localModel": "custom", "localOllamaExecutable": str(self.executable)})
        local_ai.migrate_legacy_local_ai({"localModel": self.model})
        self.assertEqual(self.read(), {
            "localModel": "custom:latest",
            "localOllamaExecutable": str(self.executable),
            "managedModels": {},
        })

    def test_check_uses_saved_model_and_requires_running_service(self):
        self.write(localModel="custom:latest")
        with patch.object(local_ai, "_models", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "chua chay"):
                local_ai.check_managed_local_ai()
        with patch.object(local_ai, "_models", return_value=[self.tag("custom:latest")]):
            self.assertIn("custom:latest", local_ai.check_managed_local_ai())

    def test_child_process_requests_no_window_and_no_interactive_stdin(self):
        with patch.object(local_ai.subprocess, "CREATE_NO_WINDOW", 0x08000000, create=True), \
                patch.object(local_ai.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            local_ai._run(["winget.exe", "install"], timeout=5)
        self.assertEqual(run.call_args.kwargs["creationflags"], 0x08000000)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_install_waits_for_native_service_when_its_serve_child_exits(self):
        with patch.object(local_ai, "_models", side_effect=[None, None, None, [self.tag()]]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai.subprocess, "Popen") as launch, \
                patch.object(local_ai.time, "sleep") as wait, \
                patch.object(local_ai, "_run") as run:
            launch.return_value.poll.return_value = 1
            local_ai.install_local_ai()
        wait.assert_called_once_with(0.25)
        run.assert_not_called()
        self.assertEqual(self.read()["managedModels"], {})


if __name__ == "__main__":
    unittest.main()
