"""Exercise optional installation without contacting a registry or starting Ollama."""

import argparse
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup
from setup_lab import local_ai


class OllamaPreparationTests(unittest.TestCase):
    executable = Path("C:/Ollama/ollama.exe")

    def test_model_accepts_local_tags_only(self):
        self.assertEqual(local_ai.normalize_model("namespace/example"), "namespace/example:latest")
        self.assertEqual(local_ai.normalize_model(local_ai.DEFAULT_MODEL), local_ai.DEFAULT_MODEL)
        for value in ("https://ollama.com/my-model", "example:-bad", "example:cloud", "example:1b-cloud", "../a", "--host"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                local_ai.normalize_model(value)

    def test_existing_local_model_skips_install_and_pull(self):
        current = [{"model": local_ai.DEFAULT_MODEL}]
        with patch.object(local_ai, "_models", return_value=current), \
                patch.object(local_ai, "find_ollama", return_value=None), \
                patch.object(local_ai, "_install_ollama") as install, \
                patch.object(local_ai, "_run") as run:
            cfg = local_ai.prepare_local_ai(local_ai.DEFAULT_MODEL)
        self.assertEqual(cfg, {"localModel": local_ai.DEFAULT_MODEL})
        install.assert_not_called()
        run.assert_not_called()

    def test_model_metadata_can_reject_remote_alias(self):
        current = [{"name": local_ai.DEFAULT_MODEL, "remote_host": "https://ollama.com"}]
        with patch.object(local_ai, "_models", return_value=current), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run") as run:
            with self.assertRaisesRegex(RuntimeError, "Ollama Cloud"):
                local_ai.prepare_local_ai(local_ai.DEFAULT_MODEL)
        run.assert_not_called()

    def test_missing_model_is_pulled_then_confirmed_on_loopback(self):
        available = [{"name": local_ai.DEFAULT_MODEL}]
        with patch.object(local_ai, "_models", side_effect=[[], available]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run") as run, \
                patch.object(local_ai.os, "environ", {"OLLAMA_HOST": "https://remote.invalid"}):
            cfg = local_ai.prepare_local_ai(local_ai.DEFAULT_MODEL)
        self.assertEqual(cfg["localOllamaExecutable"], str(self.executable))
        args, kwargs = run.call_args
        self.assertEqual(args[0], [str(self.executable), "pull", local_ai.DEFAULT_MODEL])
        self.assertEqual(kwargs["env"]["OLLAMA_HOST"], "127.0.0.1:11434")
        self.assertEqual(kwargs["env"]["OLLAMA_NO_CLOUD"], "1")

    def test_starts_ollama_when_needed_and_stops_own_process_on_failure(self):
        with patch.object(local_ai, "_models", side_effect=[None, None]), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai.subprocess, "Popen") as launch, \
                patch.object(local_ai, "_wait_for_ollama", return_value=[]), \
                patch.object(local_ai, "_run", side_effect=RuntimeError("pull failed")):
            launch.return_value.poll.return_value = None
            with self.assertRaisesRegex(RuntimeError, "pull failed"):
                local_ai.prepare_local_ai(local_ai.DEFAULT_MODEL)
        args, kwargs = launch.call_args
        self.assertEqual(args[0], [str(self.executable), "serve"])
        self.assertEqual(kwargs["env"]["OLLAMA_HOST"], "127.0.0.1:11434")
        launch.return_value.terminate.assert_called_once()

    def test_winget_uses_exact_id_and_user_scope(self):
        with patch.object(local_ai.shutil, "which", return_value="winget.exe"), \
                patch.object(local_ai, "find_ollama", return_value=self.executable), \
                patch.object(local_ai, "_run") as run:
            self.assertEqual(local_ai._install_ollama(), self.executable)
        args = run.call_args.args[0]
        self.assertEqual(args[:5], ["winget.exe", "install", "--id", "Ollama.Ollama", "--exact"])
        self.assertEqual(args[args.index("--scope") + 1], "user")

    def test_loopback_tags_refuses_unexpected_service_response(self):
        body = io.BytesIO(b'{"unexpected": []}')
        with patch.object(local_ai._LOCAL_OPENER, "open", return_value=body) as request:
            with self.assertRaisesRegex(RuntimeError, "danh sach model Ollama hop le"):
                local_ai._models()
        request.assert_called_once_with("http://127.0.0.1:11434/api/tags", timeout=2)

    def test_timeout_is_reported_with_command_context(self):
        with patch.object(local_ai.subprocess, "run", side_effect=subprocess.TimeoutExpired("winget", 1)):
            with self.assertRaisesRegex(RuntimeError, "winget.exe install vuot qua 1 giay"):
                local_ai._run(["winget.exe", "install"], timeout=1)


class OptionalInstallerTests(unittest.TestCase):
    def test_check_preflights_local_without_installing(self):
        args = argparse.Namespace(
            ide="manual", ide_cli=None, profile="simpleai", check=True,
            local=False, local_shell=True, local_model=None,
        )
        with patch.object(argparse.ArgumentParser, "parse_args", return_value=args), \
                patch.object(setup, "check_install", return_value=(None, Path(sys.executable))) as preflight, \
                patch.object(setup, "check_managed_local_ai", return_value="Ollama ready") as check, \
                patch.object(setup, "install_all") as install:
            self.assertEqual(setup.main(), 0)
        preflight.assert_called_once_with("manual", None, "local")
        check.assert_called_once_with(None)
        install.assert_not_called()

    def test_base_install_and_previous_model_survive_failed_optional_setup(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "helper"
            root.mkdir()
            runtime_json = root / "runtime.json"
            prior_model = "existing:1b"
            runtime_json.write_text(json.dumps({"localModel": prior_model, "localOllamaExecutable": "old"}), encoding="utf-8")
            with patch.object(setup, "install_root", return_value=root), \
                    patch.object(setup, "prepare_engine", return_value=Path(sys.executable)), \
                    patch.object(setup, "smoke_test"), \
                    patch.object(setup, "build_vsix", side_effect=lambda path: path), \
                    patch.object(setup, "migrate_legacy_local_ai") as migrate, \
                    patch.object(setup, "install_local_ai", side_effect=RuntimeError("download denied")):
                with self.assertRaisesRegex(RuntimeError, "Da cai tich hop IDE.*download denied"):
                    setup.install_all(None, Path(sys.executable), local_model=local_ai.DEFAULT_MODEL)
            config = json.loads(runtime_json.read_text(encoding="utf-8"))
            migrate.assert_called_once_with({"localModel": prior_model, "localOllamaExecutable": "old"})
            self.assertTrue(Path(config["engineRoot"]).is_dir())
            self.assertTrue(config["baseEnabled"])
            self.assertNotIn("localModel", config)

    def test_local_shell_uses_bootstrap_python_without_offline_wheels(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "helper"
            model = "custom:1b"
            with patch.object(setup, "install_root", return_value=root), \
                    patch.object(setup, "smoke_test"), \
                    patch.object(setup, "build_vsix", side_effect=lambda path: path), \
                    patch.object(setup, "migrate_legacy_local_ai"), \
                    patch.object(setup, "run_python") as run, \
                    patch.object(setup, "install_local_ai", return_value={"localModel": model}) as prepare:
                setup.install_all(None, Path(sys.executable), "local", local_model=model)
            prepare.assert_called_once_with(model)
            run.assert_not_called()
            config = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
            self.assertEqual(config["python"], sys.executable)
            self.assertFalse(config["baseEnabled"])
            self.assertFalse((Path(config["engineRoot"]) / "runtime.json").exists())

    def test_local_setup_reuses_existing_full_python(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "helper"
            old_runtime = root / "runtime-existing"
            old_venv = old_runtime / ".venv"
            old_venv.mkdir(parents=True)
            (old_venv / "pyvenv.cfg").touch()
            executable = old_venv / "python.exe"
            executable.touch()
            (root / "runtime.json").write_text(json.dumps({
                "engineRoot": str(old_runtime), "python": str(executable),
                "baseEnabled": True, "dependencyProfile": "full",
            }), encoding="utf-8")
            with patch.object(setup, "install_root", return_value=root), \
                    patch.object(setup, "smoke_test"), \
                    patch.object(setup, "build_vsix", side_effect=lambda path: path), \
                    patch.object(setup, "migrate_legacy_local_ai"), \
                    patch.object(setup, "prepare_engine") as prepare, \
                    patch.object(setup, "install_local_ai", return_value={"localModel": "fixture:1b"}):
                setup.install_all(None, Path(sys.executable), "local", wants_local=True)
            config = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
            self.assertTrue(config["baseEnabled"])
            self.assertEqual(config["dependencyProfile"], "full")
            self.assertEqual(config["python"], str(executable))
            self.assertTrue(executable.exists())
            prepare.assert_not_called()


if __name__ == "__main__":
    unittest.main()
