# -*- coding: utf-8 -*-
"""Gỡ bản cài qua go_cai_dat.bat hoặc python go_cai_dat.py.

Các IDE đang mở cần Reload Window để bỏ hẳn phím tắt đã nạp vào bộ nhớ.
Extension mới sẽ tự ngừng xử lý ngay khi bản cài bị gỡ.
"""

from __future__ import annotations

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

sys.dont_write_bytecode = True
_SCRIPT_ROOT = str(Path(__file__).resolve().parent)
if _SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, _SCRIPT_ROOT)

EXT_ID = "ms-python-tools.pylance-indent-helper"
EXT_FOLDER_NAME = EXT_ID + "-1.0.0"


def _is_msix_python() -> bool:
    exes = (sys.executable or "", getattr(sys, "_base_executable", "") or "")
    return any("WindowsApps" in p or "PythonSoftwareFoundation.Python." in p for p in exes)


def _home_mirror_dir() -> Path:
    return Path.home() / ".pylance-helper"


def install_root() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if not local or not Path(local).is_absolute():
        raise RuntimeError("Khong tim thay thu muc LOCALAPPDATA cua nguoi dung.")
    local_path = Path(local).resolve()
    home = Path.home().resolve()
    # Escape Windows Store Python MSIX AppData virtualization so Win32 VS Code sees exact NTFS paths
    if _is_msix_python() and str(local_path).casefold().startswith(str(home).casefold()):
        return _home_mirror_dir() / "engine"
    parent = (local_path / "Programs").resolve()
    root = parent / "PylanceHelper"
    if root.resolve() != root:
        raise RuntimeError(f"Thu muc cai dat tro sang dia chi khac: {root}")
    return root


def _terminate_stale_pid(pid_file: Path) -> None:
    if sys.platform != "win32":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if pid_file.is_file():
        try:
            old_pid = int(pid_file.read_text(encoding="utf-8").strip())
            if old_pid > 0 and old_pid != os.getpid():
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(old_pid), "/T"],
                    capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, timeout=10, check=False,
                )
        except (OSError, ValueError):
            pass
    if "unittest" not in sys.modules:
        ps_kill = (
            f"$myPid = {os.getpid()}; "
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
            "$_.ProcessId -ne $myPid -and ("
            "($_.Name -match '^python' -and $_.CommandLine -match 'setup\\.py') -or "
            "($_.Name -eq 'ollama.exe' -and $_.CommandLine -match '\\bpull\\b')"
            ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_kill],
            capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, timeout=10, check=False,
        )
    time.sleep(0.5)


@contextmanager
def install_lock(root: Path):
    root.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        yield
        return
    import msvcrt

    pid_file = root.parent / "PylanceHelper.pid"
    with (root.parent / "PylanceHelper.lock").open("a+b") as lock:
        lock.seek(0)
        locked = False
        for attempt in range(2):
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
                break
            except OSError:
                if attempt == 0:
                    _terminate_stale_pid(pid_file)
                    time.sleep(0.5)
        if not locked:
            raise RuntimeError("Dang co mot lenh cai hoac go khac. Hay doi va thu lai.")
        try:
            pid_file.write_text(str(os.getpid()), encoding="utf-8")
        except OSError:
            pass
        try:
            yield
        finally:
            try:
                pid_file.unlink(missing_ok=True)
            except OSError:
                pass
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
    # Mirror runtime pointer into unvirtualized ~/.pylance-helper when installing under real user profile
    try:
        home = Path.home().resolve()
        if str(root.resolve()).casefold().startswith(str(home).casefold()):
            mirror_dir = _home_mirror_dir()
            mirror_dir.mkdir(parents=True, exist_ok=True)
            (mirror_dir / "runtime.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    except (OSError, RuntimeError):
        pass


def copy_runtime_files(source: Path, target: Path) -> None:
    shutil.copytree(
        source / "core_engine", target / "core_engine",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pylance_cache.json"),
    )
    shutil.copy2(source / "go_cai_dat.py", target / "go_cai_dat.py")
    local_ai_src = source / "setup_lab" / "local_ai.py"
    if local_ai_src.is_file():
        setup_lab_dir = target / "setup_lab"
        setup_lab_dir.mkdir(exist_ok=True)
        shutil.copy2(local_ai_src, setup_lab_dir / "local_ai.py")


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
    try:
        python = Path(config["python"]).resolve()
    except OSError:
        python = Path(config["python"])
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

    obsolete_file = ide_ext_root / ".obsolete"
    if obsolete_file.is_file():
        try:
            obs = json.loads(obsolete_file.read_text(encoding="utf-8-sig"))
            if isinstance(obs, dict):
                cleaned_obs = {k: v for k, v in obs.items() if not str(k).casefold().startswith(EXT_ID)}
                if len(cleaned_obs) != len(obs):
                    if cleaned_obs:
                        obsolete_file.write_text(json.dumps(cleaned_obs, ensure_ascii=False), encoding="utf-8")
                    else:
                        obsolete_file.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass


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


def _remove_local_ai_for_full_uninstall(root: Path) -> None:
    """Scorched-earth removal of Alt+5 local AI config, models, Ollama app, logs, and registry traces."""
    script_dir = str(Path(__file__).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    try:
        from setup_lab.local_ai import uninstall_local_ai
    except ImportError:
        local_dir = root.parent.parent / "PylanceHelperLocalAI"
        if local_dir.exists():
            shutil.rmtree(local_dir, ignore_errors=True)
        return
    uninstall_local_ai(remove_configured_model=True, remove_user_ollama=True, purge_all=True)


def _scrub_all_ide_extension_dirs() -> None:
    for ide_name in (".vscode", ".vscode-insiders", ".antigravity-ide", ".antigravity", ".cursor", ".windsurf", ".vscodium"):
        ext_root = Path.home() / ide_name / "extensions"
        if ext_root.is_dir():
            try:
                _unregister_extension_from_ide(ext_root)
            except Exception:
                pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        for app_ide in ("Code", "Code - Insiders", "Antigravity", "Cursor", "Windsurf", "VSCodium"):
            cached = Path(appdata) / app_ide / "CachedExtensionVSIXs"
            if cached.is_dir():
                for item in cached.glob("*pylance-indent-helper*"):
                    try:
                        item.unlink(missing_ok=True)
                    except OSError:
                        pass
            global_st = Path(appdata) / app_ide / "User" / "globalStorage" / EXT_ID
            if global_st.exists():
                shutil.rmtree(global_st, ignore_errors=True)


def _scrub_dot_pylance_traces() -> None:
    """Remove ~/.pylance-helper and any .pylance* files/folders in user home or temp."""
    home_candidates: list[Path] = []
    try:
        home_candidates.append(Path.home())
    except (OSError, RuntimeError):
        pass
    if "unittest" not in sys.modules and os.environ.get("USERPROFILE"):
        up = Path(os.environ["USERPROFILE"])
        if all(str(up).casefold() != str(h).casefold() for h in home_candidates):
            home_candidates.append(up)

    for h_dir in home_candidates:
        try:
            mirror = h_dir / ".pylance-helper"
            if mirror.exists():
                shutil.rmtree(mirror, ignore_errors=True)
            if h_dir.is_dir():
                for item in h_dir.glob(".pylance*"):
                    try:
                        if item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                        else:
                            item.unlink(missing_ok=True)
                    except OSError:
                        pass
        except OSError:
            pass


def _scrub_temp_and_pth_traces() -> None:
    try:
        pth_file = Path(site.getusersitepackages()) / "pylance_helper_pkgs.pth"
        if pth_file.exists():
            pth_file.unlink()
    except Exception:
        pass
    try:
        tmp_dir = Path(tempfile.gettempdir())
        for pattern in ("pylance_lint_*.py", "pylance_uninst_*.tmp", "pylance_go_ollama_*.tmp", "pylance_hf_*"):
            for item in tmp_dir.glob(pattern):
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                except OSError:
                    pass
    except Exception:
        pass
    _scrub_dot_pylance_traces()


def _stop_runtime_python_processes(root: Path) -> None:
    """Kill any lingering python.exe/pythonw.exe running out of PylanceHelper/.pylance-helper (excluding self)."""
    if sys.platform != "win32" or "unittest" in sys.modules:
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    ps_kill = (
        f"$myPid = {os.getpid()}; "
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
        "$_.ProcessId -ne $myPid -and $_.Name -match '^python' -and ("
        "$_.ExecutablePath -match 'PylanceHelper|\\.pylance-helper' -or "
        "$_.CommandLine -match 'PylanceHelper|\\.pylance-helper'"
        ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_kill],
        capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, timeout=10, check=False,
    )


def _schedule_post_exit_sweep(root: Path) -> None:
    """Spawn a 1-second delayed background cmd sweep so even locked runtime/lock files vanish after python.exe exits."""
    if sys.platform != "win32" or "unittest" in sys.modules:
        return
    targets = [
        str(root),
        str(root.parent / "PylanceHelper.lock"),
        str(root.parent / "PylanceHelper.pid"),
        str(root.parent.parent / "PylanceHelperLocalAI"),
        str(root.parent.parent / "PylanceHelperLogs"),
    ]
    try:
        targets.append(str(_home_mirror_dir()))
    except (OSError, RuntimeError):
        pass
    if os.environ.get("USERPROFILE"):
        targets.append(str(Path(os.environ["USERPROFILE"]) / ".pylance-helper"))
        targets.append(str(Path(os.environ["USERPROFILE"]) / ".ollama"))
    if os.environ.get("LOCALAPPDATA"):
        targets.append(str(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama"))
        targets.append(str(Path(os.environ["LOCALAPPDATA"]) / "Ollama"))

    rm_cmds = []
    for t in targets:
        if '"' not in t:
            if t.endswith((".lock", ".pid")):
                rm_cmds.append(f'del /f /q "{t}" >nul 2>&1')
            else:
                rm_cmds.append(f'if exist "{t}" rmdir /s /q "{t}" >nul 2>&1')
    if not rm_cmds:
        return
    joined = " & ".join(rm_cmds)
    flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    )
    try:
        subprocess.Popen(
            f'cmd.exe /d /s /c "ping -n 2 127.0.0.1 >nul & {joined}"',
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except OSError:
        pass


def uninstall_everything(
    kill_self_process: bool = False,
    *,
    local_shell_only: bool = False,
    remove_all: bool = False,
) -> bool:
    # Legacy callers still pass kill_self_process. The PID check excludes this process.
    manual_extension = False
    try:
        root = install_root()
        with install_lock(root):
            config = load_runtime(root)
            local_record = root.parent.parent / "PylanceHelperLocalAI" / "runtime.json"
            if remove_all:
                _remove_local_ai_for_full_uninstall(root)
            elif local_shell_only:
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
                    try:
                        if extension.casefold() not in list_extensions(cli):
                            continue
                        run_ide_cli(cli, "--uninstall-extension", extension)
                        if extension.casefold() in list_extensions(cli):
                            raise RuntimeError(f"IDE van hien extension {extension}.")
                    except (RuntimeError, OSError):
                        if not remove_all:
                            raise
                manual_extension = config.get("manualExtension", False) and not remove_all
                if remove_all:
                    try:
                        stop_daemon_processes()
                    except Exception:
                        pass
                    _stop_runtime_python_processes(root)
                    _scrub_all_ide_extension_dirs()
                    _scrub_temp_and_pth_traces()
            elif uninstall_legacy(root):
                return False
            elif remove_all:
                _stop_runtime_python_processes(root)
                _scrub_all_ide_extension_dirs()
                _scrub_temp_and_pth_traces()
            try:
                _remove_tree(root, root.parent)
            finally:
                if remove_all:
                    _scrub_dot_pylance_traces()
                    for extra_dir in (
                        root.parent.parent / "PylanceHelperLocalAI",
                        root.parent.parent / "PylanceHelperLogs",
                        _home_mirror_dir(),
                    ):
                        if extra_dir.exists():
                            shutil.rmtree(extra_dir, ignore_errors=True)
                    local_env = os.environ.get("LOCALAPPDATA")
                    if local_env:
                        pkgs_dir = Path(local_env) / "Packages"
                        if pkgs_dir.is_dir():
                            for pkg_dir in pkgs_dir.glob("PythonSoftwareFoundation.Python.*"):
                                for rel in ("Programs/PylanceHelper", "PylanceHelperLocalAI", "PylanceHelperLogs"):
                                    target_v = pkg_dir / "LocalCache" / "Local" / rel
                                    if target_v.exists():
                                        shutil.rmtree(target_v, ignore_errors=True)
                else:
                    try:
                        if _home_mirror_dir().exists():
                            (_home_mirror_dir() / "runtime.json").unlink(missing_ok=True)
                    except (OSError, RuntimeError):
                        pass
        if remove_all:
            for lock_f in (root.parent / "PylanceHelper.lock", root.parent / "PylanceHelper.pid"):
                try:
                    lock_f.unlink(missing_ok=True)
                except OSError:
                    pass
            _schedule_post_exit_sweep(root)
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
    component.add_argument("--all", action="store_true", dest="remove_all", help="Go toan bo (Alt+1..5, extension va Ollama).")
    component.add_argument("--base-only", action="store_true", help="Go Offline va API (giu lai Ollama neu co).")
    component.add_argument("--local-shell-only", action="store_true", help="Go tich hop IDE sau khi go Ollama.")
    args = parser.parse_args()
    return 0 if uninstall_everything(local_shell_only=args.local_shell_only, remove_all=args.remove_all) else 1


if __name__ == "__main__":
    sys.exit(main())
