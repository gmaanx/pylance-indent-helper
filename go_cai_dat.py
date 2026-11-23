# -*- coding: utf-8 -*-
"""Gỡ bản cài qua go_cai_dat.bat hoặc python go_cai_dat.py.

Các IDE đang mở cần Reload Window để bỏ hẳn phím tắt đã nạp vào bộ nhớ.
Extension mới sẽ tự ngừng xử lý ngay khi bản cài bị gỡ.
"""

import argparse
from contextlib import contextmanager
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


def install_root() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if not local or not Path(local).is_absolute():
        raise RuntimeError("Khong tim thay thu muc LOCALAPPDATA cua nguoi dung.")
    parent = (Path(local) / "Programs").resolve()
    root = parent / "PylanceHelper"
    if root.resolve() != root:
        raise RuntimeError(f"Thu muc cai dat tro sang dia chi khac: {root}")
    return root


@contextmanager
def install_lock(root: Path):
    root.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        yield
        return
    import msvcrt

    with (root.parent / "PylanceHelper.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Dang co mot lenh cai hoac go khac. Hay doi va thu lai.") from exc
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def load_runtime(root: Path) -> dict | None:
    try:
        config = json.loads((root / "runtime.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(config, dict) or not isinstance(config.get("ides", []), list):
        raise ValueError("runtime.json khong hop le.")
    for ide in config.get("ides", []):
        if not isinstance(ide, dict) or not isinstance(ide.get("cli"), str) or not isinstance(ide.get("extension"), str):
            raise ValueError("runtime.json chua thong tin IDE khong hop le.")
    return config


def save_runtime(root: Path, config: dict) -> None:
    fd, name = tempfile.mkstemp(prefix="runtime-", suffix=".json", dir=root)
    staging = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(config, stream, ensure_ascii=False)
        staging.replace(root / "runtime.json")
    finally:
        staging.unlink(missing_ok=True)


def copy_runtime_files(source: Path, target: Path) -> None:
    shutil.copytree(
        source / "core_engine", target / "core_engine",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pylance_cache.json"),
    )
    shutil.copy2(source / "go_cai_dat.py", target / "go_cai_dat.py")


def run_ide_cli(cli: Path, *args: str) -> str:
    if not cli.is_absolute() or not cli.is_file():
        raise RuntimeError(f"Khong tim thay lenh IDE: {cli}")
    env = os.environ.copy()
    if cli.suffix.lower() in (".cmd", ".bat"):
        # cmd.exe needs an explicit command string. Passing arguments through
        # environment expansion preserves literal paths with spaces or shell symbols.
        variables = [f"PYLANCE_HELPER_IDE_{index}" for index in range(len(args) + 1)]
        for variable, value in zip(variables, (str(cli), *args)):
            if '"' in value:
                raise ValueError("Duong dan IDE chua ky tu khong hop le.")
            env[variable] = value
        tokens = " ".join(f'"%{variable}%"' for variable in variables)
        command = f'cmd.exe /d /v:off /s /c "{tokens}"'
    else:
        command = [str(cli), *args]
    result = subprocess.run(
        command, env=env, capture_output=True, encoding="utf-8", errors="replace",
        timeout=45, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        detail = (result.stderr.strip() or result.stdout.strip())[-2000:]
        raise RuntimeError(f"Lenh IDE thoat voi ma {result.returncode}. {detail}")
    return result.stdout


def list_extensions(cli: Path, show_versions: bool = False) -> set[str]:
    args = ("--list-extensions", "--show-versions") if show_versions else ("--list-extensions",)
    return {line.strip().casefold() for line in run_ide_cli(cli, *args).splitlines()}


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


def remove_obsolete_runtimes(root: Path, config: dict, *, strict: bool = False) -> None:
    engine = Path(config["engineRoot"]).resolve()
    python = Path(config["python"]).resolve()
    for obsolete in root.glob("runtime-*"):
        resolved = obsolete.resolve()
        if resolved == engine or resolved in python.parents:
            continue
        if not (obsolete / "core_engine" / "cli_entry.py").is_file() and not (obsolete / ".venv" / "pyvenv.cfg").is_file():
            continue
        try:
            _remove_tree(obsolete, root)
        except OSError as exc:
            if strict:
                raise
            print(f"[CANH BAO] Khong xoa duoc ban cu {obsolete.name}. {exc}")


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


def uninstall_legacy(root: Path) -> list[str]:
    errors = []

    def attempt(label, action):
        try:
            action()
        except Exception as exc:
            errors.append(f"{label}: {exc}")
            print(f"[LOI] {errors[-1]}")

    if root.exists():
        attempt("Dung chuong trinh nen cu", stop_daemon_processes)
    for ide_name in (".vscode", ".antigravity-ide"):
        ext_root = Path.home() / ide_name / "extensions"
        attempt(f"Go extension {ide_name}", lambda root=ext_root: _unregister_extension_from_ide(root))

    def remove_pth():
        pth_file = Path(site.getusersitepackages()) / "pylance_helper_pkgs.pth"
        if pth_file.exists():
            pth_file.unlink()

    attempt("Xoa lien ket thu vien", remove_pth)
    return errors


def _keep_local_runtime(root: Path, config: dict) -> None:
    if config.get("dependencyProfile") != "local":
        previous_engine = Path(config.get("engineRoot", "")).resolve()
        python = Path(config.get("uninstallPython", ""))
        if (
            previous_engine.parent != root or not previous_engine.name.startswith("runtime-")
            or not python.is_absolute() or not python.is_file()
        ):
            raise ValueError("Cau hinh Python cho Ollama khong hop le. Chay lai trinh cai de sua.")
        runtime = Path(tempfile.mkdtemp(prefix="runtime-", dir=root))
        try:
            copy_runtime_files(previous_engine, runtime)
            config = {
                **config,
                "engineRoot": str(runtime),
                "python": str(python),
                "dependencyProfile": "local",
                "baseEnabled": False,
            }
            save_runtime(root, config)
        except BaseException:
            _remove_tree(runtime, root)
            raise
    remove_obsolete_runtimes(root, config, strict=True)
    print("[OK] Da go Offline va API. Tich hop Ollama van san sang.")


def uninstall_everything(kill_self_process: bool = False, *, local_shell_only: bool = False) -> bool:
    # Legacy callers still pass kill_self_process. The PID check excludes this process.
    manual_extension = False
    try:
        root = install_root()
        with install_lock(root):
            config = load_runtime(root)
            local_record = root.parent.parent / "PylanceHelperLocalAI" / "runtime.json"
            if local_shell_only:
                if config is None or config.get("baseEnabled", True) or local_record.exists():
                    return True
            elif config is not None and local_record.exists():
                _keep_local_runtime(root, config)
                return True
            if root.exists():
                (root / ".uninstalling").touch()
                cwd = Path.cwd().resolve()
                if cwd == root or root in cwd.parents:
                    os.chdir(tempfile.gettempdir())
            if config is not None:
                for ide in config.get("ides", []):
                    cli = Path(ide["cli"])
                    extension = ide["extension"]
                    if extension.casefold() not in list_extensions(cli):
                        continue
                    run_ide_cli(cli, "--uninstall-extension", extension)
                    if extension.casefold() in list_extensions(cli):
                        raise RuntimeError(f"IDE van hien extension {extension}.")
                manual_extension = config.get("manualExtension", False)
            elif uninstall_legacy(root):
                return False
            _remove_tree(root, root.parent)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"[LOI] Go cai dat chua hoan tat. {exc}", file=sys.stderr)
        return False
    if manual_extension:
        print("\n[OK] Da go moi truong Python cua cong cu.")
        print("Neu tung cai VSIX thu cong, mo Extensions trong IDE va chon Uninstall.")
    else:
        print("\n=== DA GO CAI DAT THANH CONG ===")
    print("IDE dang mo: Ctrl+Shift+P > Reload Window de bo phim tat da nap trong bo nho.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    component = parser.add_mutually_exclusive_group()
    component.add_argument("--base-only", action="store_true", help="Go Offline va API.")
    component.add_argument("--local-shell-only", action="store_true", help="Go tich hop IDE sau khi go Ollama.")
    args = parser.parse_args()
    return 0 if uninstall_everything(local_shell_only=args.local_shell_only) else 1


if __name__ == "__main__":
    sys.exit(main())
