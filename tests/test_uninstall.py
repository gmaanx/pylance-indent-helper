"""Regression tests use a temporary installation, never the real user profile."""

import contextlib
import io
import importlib.util
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
            patch.object(uninstall, "_clear_clipboard"),
        ):
            mock.start()
            self.addCleanup(mock.stop)

    def run_uninstall(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = uninstall.uninstall_everything()
        return result, output.getvalue()

    def test_removes_all_versions_and_preserves_unrelated_files(self):
        result, output = self.run_uninstall()
        self.assertTrue(result, output)
        self.assertFalse(self.install.exists())
        self.assertFalse((self.user_site / "pylance_helper_pkgs.pth").exists())
        self.assertFalse((self.tmp / "pylance_lint_test.py").exists())
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

    def test_reinstall_clears_stop_marker_and_launches_installed_daemon(self):
        (self.install / ".uninstalling").touch()
        spec = importlib.util.spec_from_file_location("tool_setup", Path(uninstall.__file__).with_name("setup.py"))
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with patch.object(installer.subprocess, "Popen") as popen, \
                patch.object(installer.subprocess, "run"), \
                contextlib.redirect_stdout(io.StringIO()):
            installer.install_all()
        self.assertFalse((self.install / ".uninstalling").exists())
        self.assertTrue((self.install / "go_cai_dat.py").exists())
        args, kwargs = popen.call_args
        self.assertEqual(Path(args[0][1]), self.install / "shells" / "stealth_daemon" / "daemon.pyw")
        self.assertEqual(kwargs["cwd"], str(self.tmp))


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
