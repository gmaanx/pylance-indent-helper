# -*- coding: utf-8 -*-
"""Gỡ bản cài qua Alt+0, go_cai_dat.bat hoặc python go_cai_dat.py.

Các IDE đang mở cần Reload Window để bỏ hẳn phím tắt đã nạp vào bộ nhớ.
Extension mới sẽ tự ngừng xử lý ngay khi bản cài bị gỡ.
"""

import ctypes
import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
import time
from pathlib import Path

EXT_ID = "ms-python-tools.pylance-indent-helper"
EXT_FOLDER_NAME = EXT_ID + "-1.0.0"


def _remove_tree(target: Path, parent: Path) -> None:
    # Chỉ xóa một thư mục con trực tiếp trong vị trí cài đã xác định.
    if target.resolve().parent != parent.resolve():
        raise ValueError(f"Duong dan xoa khong hop le: {target}")
    for attempt in range(6):
        try:
            if target.exists():
                shutil.rmtree(target)
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(0.15)


def _unregister_extension_from_ide(ide_ext_root: Path) -> None:
    for ext_dir in ide_ext_root.glob(EXT_ID + "-[0-9]*"):
        if ext_dir.is_dir():
            _remove_tree(ext_dir, ide_ext_root)
            print(f"[OK] Da go Extension: {ext_dir}")

    manifest_file = ide_ext_root / "extensions.json"
    if manifest_file.exists():
        entries = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        if not isinstance(entries, list):
            raise ValueError(f"Danh sach extension khong hop le: {manifest_file}")
        filtered = [
            e for e in entries
            if not (
                isinstance(e, dict)
                and isinstance(e.get("identifier"), dict)
                and str(e["identifier"].get("id", "")).casefold() == EXT_ID
            )
        ]
        if len(filtered) != len(entries):
            manifest_file.write_text(json.dumps(filtered, ensure_ascii=False), encoding="utf-8")


def stop_daemon_processes() -> None:
    """Dừng đúng daemon của công cụ, kể cả bản chạy bằng python.exe."""
    if sys.platform != "win32":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    query = (
        "$ErrorActionPreference = 'Stop'; "
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "@(Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -in @('python.exe', 'pythonw.exe', 'pylance-indent-helper.exe') "
        "} | Select-Object ProcessId, Name, CommandLine, ExecutablePath) | ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=flags, timeout=20, check=True,
    )
    processes = json.loads(result.stdout.strip() or "[]")
    if isinstance(processes, dict):
        processes = [processes]
    roots = [Path(__file__).resolve().parent, Path(r"D:\UEH\ai\midtermtool")]
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "PylanceHelper")
    daemon_paths = [str(root / "shells" / "stealth_daemon" / "daemon.pyw").casefold() for root in roots]
    for proc in processes:
        pid = int(proc["ProcessId"])
        if pid == os.getpid():
            continue
        command = (proc.get("CommandLine") or "").replace("/", "\\").casefold()
        is_daemon = any(p in command for p in daemon_paths)
        if proc.get("Name", "").casefold() == "pylance-indent-helper.exe":
            executable = Path(proc.get("ExecutablePath") or "")
            is_daemon = any(root.resolve() in executable.resolve().parents for root in roots)
        if is_daemon:
            stopped = subprocess.run(
                ["taskkill", "/F", "/PID", str(pid), "/T"],
                capture_output=True, creationflags=flags, timeout=10, check=False,
            )
            # 128: tiến trình vừa tự thoát trong lúc truy vấn.
            if stopped.returncode not in (0, 128):
                raise RuntimeError(f"Khong dung duoc daemon PID {pid} (ma {stopped.returncode})")
    print("[OK] Da dung daemon cua cong cu.")


def _clear_clipboard() -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    for _ in range(8):
        if user32.OpenClipboard(None):
            try:
                if not user32.EmptyClipboard():
                    raise OSError("Khong xoa duoc Clipboard")
            finally:
                user32.CloseClipboard()
            return
        time.sleep(0.02)
    raise OSError("Clipboard dang bi khoa")


def uninstall_everything(kill_self_process: bool = False) -> bool:
    # Giữ tham số tương thích với daemon cũ; luôn bỏ qua PID của chính mình.
    errors = []

    def attempt(label, action):
        try:
            action()
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            print(f"[LOI] {errors[-1]}")

    local_app = os.environ.get("LOCALAPPDATA")
    install_root = Path(local_app) / "Programs" / "PylanceHelper" if local_app else None
    if install_root and install_root.exists():
        # Các cửa sổ IDE khác cũng ngừng lệnh khi thấy cờ này.
        attempt("Khoa ban cai", lambda: (install_root / ".uninstalling").touch())
        if Path.cwd().resolve() == install_root.resolve() or install_root.resolve() in Path.cwd().resolve().parents:
            # Windows không cho xóa thư mục đang là cwd của chính tiến trình gỡ.
            os.chdir(tempfile.gettempdir())

    attempt("Dung daemon", stop_daemon_processes)
    for ide_name in (".vscode", ".antigravity-ide"):
        ext_root = Path.home() / ide_name / "extensions"
        attempt(f"Go extension {ide_name}", lambda root=ext_root: _unregister_extension_from_ide(root))

    if install_root:
        attempt("Xoa thu muc cai", lambda: _remove_tree(install_root, install_root.parent))

    def remove_pth():
        pth_file = Path(site.getusersitepackages()) / "pylance_helper_pkgs.pth"
        if pth_file.exists():
            pth_file.unlink()

    attempt("Xoa lien ket thu vien", remove_pth)
    for tmp_file in Path(tempfile.gettempdir()).glob("pylance_lint_*.py"):
        attempt(f"Xoa file tam {tmp_file.name}", tmp_file.unlink)
    attempt("Xoa Clipboard", _clear_clipboard)

    if errors:
        print("\n=== GO CAI DAT CHUA HOAN TAT. XEM CAC LOI BEN TREN. ===")
        return False
    print("\n=== DA GO CAI DAT THANH CONG ===")
    print("IDE dang mo: Ctrl+Shift+P > Reload Window de bo phim tat da nap trong bo nho.")
    return True


if __name__ == "__main__":
    sys.exit(0 if uninstall_everything() else 1)
