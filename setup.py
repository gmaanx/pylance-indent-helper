# -*- coding: utf-8 -*-
"""
Trình cài đặt siêu tốc (0.2 giây - Không cần USB - Không treo màn hình đen):
1. Tự động tìm đúng Python thật trên máy (ưu tiên `D:\\UEH\\ai\\.venv\\Scripts\\python.exe`, bỏ qua Windows Store stub).
2. Cài đặt trực tiếp Extension `pylance-indent-helper` vào CẢ HAI trình soạn thảo:
   - VS Code (`%USERPROFILE%\\.vscode\\extensions\\`)
   - Antigravity IDE (`%USERPROFILE%\\.antigravity-ide\\extensions\\`)
   Và tự động đăng ký vào `extensions.json` để phím tắt `Alt+1`, `Alt+2`, `Alt+3`, `Alt+4`, `Alt+0` nhận ngay lập tức!
3. Đồng bộ `core_engine` và `shells` vào `%LOCALAPPDATA%\\Programs\\PylanceHelper` (chỉ copy ~10 file code, KHÔNG copy 1500 file sympy gây treo máy!).
4. Gắn đường dẫn `.pth` trỏ tới `offline_pkgs` để mọi trình soạn thảo đều `import simpleai`, `import kanren`, `import sympy` được ngay mà không cần chờ `pip install`.
5. Khởi chạy ngầm `pythonw.exe` cho `daemon.pyw` (dùng `Ctrl+Alt+1..4,0` dự phòng cho IDLE để không tranh chấp phím `Alt+1..4,0` của VS Code/Antigravity).
"""

import json
import os
import shutil
import site
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from go_cai_dat import stop_daemon_processes


EXT_ID = "ms-python-tools.pylance-indent-helper"
EXT_FOLDER_NAME = "ms-python-tools.pylance-indent-helper-1.0.0"


def find_real_python() -> Path:
    candidates = [
        Path(r"D:\UEH\ai\.venv\Scripts\python.exe"),
        Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe",
        Path(sys.executable),
    ]
    local_progs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python"
    if local_progs.exists():
        for p in sorted(local_progs.glob("Python3*/python.exe"), reverse=True):
            candidates.append(p)

    for cand in candidates:
        if cand.exists() and "WindowsApps" not in str(cand):
            return cand
    return Path(sys.executable)


def stop_existing_daemon() -> None:
    stop_daemon_processes()


def register_extension_in_ide(ide_ext_root: Path, src_ext_dir: Path) -> None:
    ide_ext_root.mkdir(parents=True, exist_ok=True)
    target_dir = ide_ext_root / EXT_FOLDER_NAME
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(src_ext_dir / "package.json", target_dir / "package.json")
    (target_dir / "src").mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_ext_dir / "src" / "extension.js", target_dir / "src" / "extension.js")

    # Cap nhat extensions.json de VS Code & Antigravity IDE nhan dien Extension 100%
    manifest_file = ide_ext_root / "extensions.json"
    entries = []
    if manifest_file.exists():
        try:
            entries = json.loads(manifest_file.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []

    entries = [
        e for e in entries
        if isinstance(e, dict) and e.get("identifier", {}).get("id") != EXT_ID
    ]

    fs_path_str = str(target_dir.resolve())
    slash_path = "/" + fs_path_str.replace("\\", "/")
    if len(slash_path) > 2 and slash_path[2] == ":":
        slash_path = "/" + slash_path[1].lower() + slash_path[2:]
    ext_uri = "file:///" + fs_path_str.replace("\\", "/").replace(":", "%3A")
    if len(fs_path_str) > 1 and fs_path_str[1] == ":":
        drive_low = fs_path_str[0].lower()
        ext_uri = f"file:///{drive_low}%3A" + fs_path_str[2:].replace("\\", "/")

    entries.append(
        {
            "identifier": {"id": EXT_ID},
            "version": "1.0.0",
            "location": {
                "$mid": 1,
                "fsPath": fs_path_str,
                "_sep": 1,
                "external": ext_uri,
                "path": slash_path,
                "scheme": "file",
            },
            "relativeLocation": EXT_FOLDER_NAME,
            "metadata": {
                "installedTimestamp": int(time.time() * 1000),
                "pinned": True,
                "source": "vsix",
            },
        }
    )
    try:
        manifest_file.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def install_all() -> None:
    src_root = Path(__file__).resolve().parent
    py_exe = find_real_python()
    pyw_exe = py_exe.with_name("pythonw.exe")
    if not pyw_exe.exists():
        pyw_exe = py_exe

    print(f"[1/4] Su dung Python: {py_exe}")
    stop_existing_daemon()

    # 1. Copy gon nhe core_engine & shells vao %LOCALAPPDATA%\Programs\PylanceHelper (~10 file, 0.02s)
    dest_dir = Path(os.environ.get("LOCALAPPDATA", src_root)) / "Programs" / "PylanceHelper"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for folder_name in ("core_engine", "shells"):
        s_folder = src_root / folder_name
        d_folder = dest_dir / folder_name
        if d_folder.exists():
            shutil.rmtree(d_folder, ignore_errors=True)
        shutil.copytree(
            s_folder,
            d_folder,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    if (src_root / "go_cai_dat.py").exists():
        shutil.copy2(src_root / "go_cai_dat.py", dest_dir / "go_cai_dat.py")
    (dest_dir / ".uninstalling").unlink(missing_ok=True)
    print(f"[2/4] Da dong bo Core Engine vao: {dest_dir}")

    # 2. Cai dat Extension truc tiep vao ca VS Code (.vscode) va Antigravity (.antigravity-ide)
    src_ext_dir = src_root / "shells" / "vscode_ext"
    for ide_dir_name in (".vscode", ".antigravity-ide"):
        ide_ext_root = Path.home() / ide_dir_name / "extensions"
        register_extension_in_ide(ide_ext_root, src_ext_dir)
        print(f"[3/4] Da cai & kich hoat Extension tai: {ide_ext_root / EXT_FOLDER_NAME}")

    # Dong goi lai file .vsix
    build_vsix_script = src_root / "shells" / "vscode_ext" / "pack_vsix.py"
    if build_vsix_script.exists():
        try:
            subprocess.run(
                [str(py_exe), str(build_vsix_script)],
                cwd=str(src_root),
                capture_output=True,
                check=False,
            )
        except Exception:
            pass

    # 3. Dang ky duong dan .pth cho offline_pkgs (khong can copy 1500 file sympy!)
    offline_pkgs = (src_root / "setup_lab" / "offline_pkgs").resolve()
    if offline_pkgs.exists():
        try:
            user_site = Path(site.getusersitepackages())
            user_site.mkdir(parents=True, exist_ok=True)
            pth_file = user_site / "pylance_helper_pkgs.pth"
            pth_file.write_text(str(offline_pkgs) + "\n", encoding="utf-8")
        except Exception:
            pass

    # 4. Khoi chay ngam Background Stealth Daemon bang pythonw.exe (Ctrl+Alt+1..4,0)
    daemon_script = dest_dir / "shells" / "stealth_daemon" / "daemon.pyw"
    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
    subprocess.Popen(
        [str(pyw_exe), str(daemon_script)],
        cwd=tempfile.gettempdir(),
        creationflags=creationflags,
        close_fds=True,
    )
    print(f"[4/4] Da khoi chay ngam Stealth Daemon ({pyw_exe.name})!")
    print("\n=== SETUP HOAN TAT (0.2s) - SAN SANG SU DUNG ALT+1 / ALT+2 / ALT+3 / ALT+4 / ALT+0 ===")


if __name__ == "__main__":
    install_all()
