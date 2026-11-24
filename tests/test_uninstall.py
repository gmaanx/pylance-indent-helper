"""Regression tests use a temporary installation, never the real user profile."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import runpy
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import go_cai_dat as uninstall


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.profile = self.root / "profile"
        self.install = self.root / "local" / "Programs" / "PylanceHelper"
        self.install.mkdir(parents=True)
        (self.install / "engine.py").touch()
        self.user_site = self.root / "site"
        self.user_site.mkdir()
        (self.user_site / "pylance_helper_pkgs.pth").touch()
        self.tmp = self.root / "temp"
        self.tmp.mkdir()
        (self.tmp / "pylance_lint_test.py").touch()
        (self.tmp / "keep.py").touch()
        for ide in (".vscode", ".antigravity-ide"):
            ext_root = self.profile / ide / "extensions"
            for version in ("1.0.0", "1.2.0"):
                (ext_root / (uninstall.EXT_ID + "-" + version)).mkdir(parents=True)
            (ext_root / "unrelated.extension-1.0.0").mkdir()
            (ext_root / "extensions.json").write_text(json.dumps([
                {"identifier": {"id": uninstall.EXT_ID}},
                {"identifier": {"id": "unrelated.extension"}},
            ]), encoding="utf-8")
        for mock in (
            patch.object(Path, "home", return_value=self.profile),
            patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "local")}),
            patch.object(uninstall.site, "getusersitepackages", return_value=str(self.user_site)),
            patch.object(uninstall.tempfile, "gettempdir", return_value=str(self.tmp)),
            patch.object(uninstall, "stop_daemon_processes"),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def run_uninstall(self, **kwargs):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = uninstall.uninstall_everything(**kwargs)
        return result, output.getvalue()

    def test_base_and_local_shell_can_be_removed_independently(self):
        runtime = self.install / "runtime-base"
        engine = runtime / "core_engine"
        engine.mkdir(parents=True)
        (engine / "cli_entry.py").touch()
        (runtime / "go_cai_dat.py").touch()
        venv_python = runtime / ".venv" / "python.exe"
        venv_python.parent.mkdir()
        venv_python.touch()
        cli = self.root / "code.cmd"
        config_file = self.install / "runtime.json"
        config_file.write_text(json.dumps({
            "engineRoot": str(runtime), "python": str(venv_python),
            "uninstallPython": sys.executable, "baseEnabled": True,
            "dependencyProfile": "simpleai",
            "ides": [{"cli": str(cli), "extension": uninstall.EXT_ID}],
        }), encoding="utf-8")
        local = self.install.parent.parent / "PylanceHelperLocalAI" / "runtime.json"
        local.parent.mkdir()
        local.write_text('{"localModel": "fixture:1b"}', encoding="utf-8")
        with patch.object(uninstall, "run_ide_cli") as command, \
                patch.object(uninstall, "list_extensions", side_effect=[{uninstall.EXT_ID}, set()]):
            self.assertTrue(self.run_uninstall(local_shell_only=True)[0])
            self.assertTrue(venv_python.exists())
            result, output = self.run_uninstall()
            self.assertTrue(result, output)
            config = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertFalse(config["baseEnabled"])
            self.assertEqual(config["dependencyProfile"], "local")
            self.assertEqual(config["python"], sys.executable)
            self.assertTrue((Path(config["engineRoot"]) / "core_engine" / "cli_entry.py").is_file())
            self.assertFalse(runtime.exists())
            self.assertTrue(local.exists())
            self.assertTrue(self.run_uninstall(local_shell_only=True)[0])
            command.assert_not_called()
            local.unlink()
            result, output = self.run_uninstall(local_shell_only=True)
            self.assertTrue(result, output)
            command.assert_called_once_with(cli, "--uninstall-extension", uninstall.EXT_ID)
        self.assertFalse(self.install.exists())

    def test_removes_all_versions_and_preserves_unrelated_files(self):
        result, output = self.run_uninstall()
        self.assertTrue(result, output)
        self.assertFalse(self.install.exists())
        self.assertFalse((self.user_site / "pylance_helper_pkgs.pth").exists())
        self.assertTrue((self.tmp / "pylance_lint_test.py").exists())
        self.assertTrue((self.tmp / "keep.py").exists())
        for ide in (".vscode", ".antigravity-ide"):
            ext_root = self.profile / ide / "extensions"
            self.assertFalse(list(ext_root.glob(uninstall.EXT_ID + "-*")))
            self.assertTrue((ext_root / "unrelated.extension-1.0.0").exists())
            self.assertEqual(json.loads((ext_root / "extensions.json").read_text()), [
                {"identifier": {"id": "unrelated.extension"}},
            ])
        self.assertTrue(self.run_uninstall()[0], "Running uninstall twice should succeed")

    def test_locked_files_report_failure_and_keep_stop_marker(self):
        with patch.object(uninstall.shutil, "rmtree", side_effect=PermissionError("locked")), \
                patch.object(uninstall.time, "sleep"):
            result, output = self.run_uninstall()
        self.assertFalse(result)
        self.assertIn("locked", output)
        self.assertNotIn("DA GO CAI DAT THANH CONG", output)
        self.assertTrue((self.install / ".uninstalling").exists())

    def test_corrupt_manifest_is_reported_without_overwriting_it(self):
        manifest = self.profile / ".vscode" / "extensions" / "extensions.json"
        manifest.write_text("invalid json", encoding="utf-8")
        result, output = self.run_uninstall()
        self.assertFalse(result)
        self.assertIn("Go extension .vscode", output)
        self.assertEqual(manifest.read_text(), "invalid json")

    def test_uninstaller_can_remove_its_own_working_directory(self):
        original_cwd = Path.cwd()
        try:
            os.chdir(self.install)
            result, output = self.run_uninstall()
            self.assertTrue(result, output)
            self.assertFalse(self.install.exists())
            self.assertEqual(Path.cwd(), self.tmp)
        finally:
            os.chdir(original_cwd)

    def test_modern_uninstall_uses_ide_cli_and_preserves_unrelated_settings(self):
        cli = self.root / "code.cmd"
        (self.install / "runtime.json").write_text(json.dumps({
            "ides": [{"cli": str(cli), "extension": uninstall.EXT_ID}]
        }), encoding="utf-8")
        with patch.object(uninstall, "list_extensions", side_effect=[{uninstall.EXT_ID}, set()]), \
                patch.object(uninstall, "run_ide_cli") as command:
            result, output = self.run_uninstall()
        self.assertTrue(result, output)
        command.assert_called_once_with(cli, "--uninstall-extension", uninstall.EXT_ID)
        self.assertFalse(self.install.exists())
        self.assertTrue((self.user_site / "pylance_helper_pkgs.pth").exists())
        uninstall.stop_daemon_processes.assert_not_called()

    def test_ide_uninstall_failure_keeps_runtime_for_retry(self):
        cli = self.root / "code.cmd"
        (self.install / "runtime.json").write_text(json.dumps({
            "ides": [{"cli": str(cli), "extension": uninstall.EXT_ID}]
        }), encoding="utf-8")
        with patch.object(uninstall, "list_extensions", return_value={uninstall.EXT_ID}), \
                patch.object(uninstall, "run_ide_cli", side_effect=RuntimeError("IDE access denied")):
            result, output = self.run_uninstall()
        self.assertFalse(result)
        self.assertIn("IDE access denied", output)
        self.assertTrue((self.install / "runtime.json").exists())
        self.assertTrue((self.install / ".uninstalling").exists())

    def test_manual_uninstall_reports_the_remaining_extension_step(self):
        (self.install / "runtime.json").write_text(json.dumps({
            "manualExtension": True,
        }), encoding="utf-8")
        result, output = self.run_uninstall()
        self.assertTrue(result, output)
        self.assertFalse(self.install.exists())
        self.assertIn("mo Extensions trong IDE va chon Uninstall", output)
        self.assertNotIn("DA GO CAI DAT THANH CONG", output)

    def test_remove_all_uninstalls_base_local_ai_extension_and_logs(self):
        cli = self.root / "code.cmd"
        (self.install / "runtime.json").write_text(json.dumps({
            "baseEnabled": True,
            "ides": [{"cli": str(cli), "extension": uninstall.EXT_ID}],
        }), encoding="utf-8")
        local_dir = self.root / "local" / "PylanceHelperLocalAI"
        local_dir.mkdir(parents=True)
        (local_dir / "runtime.json").write_text(
            '{"localModel":"qwen2.5-coder:1.5b","managedModels":{}}',
            encoding="utf-8",
        )
        logs_dir = self.root / "local" / "PylanceHelperLogs"
        logs_dir.mkdir(parents=True)
        (logs_dir / "go_cai_dat.log").write_text("log", encoding="utf-8")

        from setup_lab import local_ai
        with patch.object(local_ai, "uninstall_local_ai") as remove_local, \
                patch.object(uninstall, "list_extensions", side_effect=[{uninstall.EXT_ID}, set()]), \
                patch.object(uninstall, "run_ide_cli") as command:
            result, output = self.run_uninstall(remove_all=True)

        self.assertTrue(result, output)
        remove_local.assert_called_once_with(remove_configured_model=True, remove_user_ollama=True)
        command.assert_called_once_with(cli, "--uninstall-extension", uninstall.EXT_ID)
        self.assertFalse(self.install.exists())
        self.assertFalse(logs_dir.exists())

    def test_copy_runtime_files_includes_local_ai_helper(self):
        source = Path(uninstall.__file__).resolve().parent
        target = self.root / "copied-runtime"
        target.mkdir()
        uninstall.copy_runtime_files(source, target)
        self.assertTrue((target / "core_engine" / "cli_entry.py").is_file())
        self.assertTrue((target / "go_cai_dat.py").is_file())
        self.assertTrue((target / "setup_lab" / "local_ai.py").is_file())


class DaemonProcessTests(unittest.TestCase):
    def test_only_tool_daemons_are_killed_including_python_exe(self):
        source = Path(uninstall.__file__).resolve().parent
        daemon_path = str(source / "shells" / "stealth_daemon" / "daemon.pyw")
        processes = [
            {"ProcessId": 4101, "Name": "pythonw.exe", "CommandLine": "pythonw other_app.pyw"},
            {"ProcessId": 4102, "Name": "python.exe", "CommandLine": f'python "{daemon_path}"'},
            {"ProcessId": 4103, "Name": "pythonw.exe", "CommandLine": f'pythonw "{daemon_path}"'},
            {"ProcessId": os.getpid(), "Name": "python.exe", "CommandLine": f'python "{daemon_path}"'},
            {"ProcessId": 4104, "Name": "pylance-indent-helper.exe", "ExecutablePath": r"C:\other_app\pylance-indent-helper.exe"},
        ]
        replies = [subprocess.CompletedProcess([], 0, json.dumps(processes), "")]
        replies.extend(subprocess.CompletedProcess([], 0) for _ in range(2))
        with patch.object(uninstall.sys, "platform", "win32"), \
                patch.object(uninstall.subprocess, "run", side_effect=replies) as run:
            uninstall.stop_daemon_processes()
        killed = [call.args[0] for call in run.call_args_list[1:]]
        self.assertEqual(killed, [
            ["taskkill", "/F", "/PID", "4102", "/T"],
            ["taskkill", "/F", "/PID", "4103", "/T"],
        ])

    @unittest.skipUnless(sys.platform == "win32", "Daemon uses Win32 APIs")
    def test_daemon_banner_reflects_actual_uninstall_result(self):
        daemon_script = Path(uninstall.__file__).parent / "shells" / "stealth_daemon" / "daemon.pyw"
        fake_engine = SimpleNamespace(process_request=Mock())
        with patch.dict(sys.modules, {"core_engine.engine_pipeline": fake_engine}):
            module = runpy.run_path(str(daemon_script), run_name="daemon_test")
        app = module["StealthDaemonApp"]()
        namespace = app.self_cleanup_and_exit.__globals__
        for success in (True, False):
            events = []
            clipboard = Mock(side_effect=lambda text: events.append(text))
            overrides = {
                "wait_for_modifiers_release": Mock(), "set_clipboard_text": clipboard,
                "send_ctrl_combo": Mock(), "pulse_scroll_lock_led": Mock(),
            }
            with patch.dict(namespace, overrides), \
                    patch.object(uninstall, "uninstall_everything", side_effect=lambda **_: events.append("uninstall") or success), \
                    patch.object(namespace["time"], "sleep"), \
                    patch.object(namespace["os"], "_exit", side_effect=SystemExit) as exit_process:
                with self.assertRaises(SystemExit):
                    app.self_cleanup_and_exit()
            self.assertEqual(events[0], "uninstall")
            self.assertIn("DA GO CAI DAT." if success else "GO CAI DAT CHUA HOAN TAT", events[1])
            self.assertEqual(exit_process.call_args.args[0], 0 if success else 1)


if __name__ == "__main__":
    unittest.main()
