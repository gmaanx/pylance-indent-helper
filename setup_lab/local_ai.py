"""Install and remove the optional per-user Ollama component on Windows."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path


DEFAULT_MODEL = "qwen2.5-coder:1.5b"
BALANCED_MODEL = "qwen2.5-coder:3b"
PRO_MODEL = "qwen2.5-coder:7b"
OLLAMA_HOST = "127.0.0.1:11434"
OLLAMA_PACKAGE = "Ollama.Ollama"
LOCAL_AI_DIR = "PylanceHelperLocalAI"
_MAX_TAGS_RESPONSE = 1_000_000


def detect_ram_gb() -> float:
    if sys.platform != "win32":
        return 8.0
    try:
        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return stat.ullTotalPhys / (1024 ** 3)
    except Exception:
        pass
    return 8.0


def detect_nvidia_vram_gb() -> float:
    """Return dedicated NVIDIA GPU VRAM in GB if available, else 0.0 (fast, hidden, zero-lag)."""
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return 0.0
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            [nvsmi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=1.5,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return 0.0
        vals = [float(line.strip()) / 1024.0 for line in proc.stdout.splitlines() if line.strip()]
        return max(vals) if vals else 0.0
    except Exception:
        return 0.0


def recommend_model_for_machine() -> str:
    """
    GPU- and RAM-aware model selector:
    - Dedicated NVIDIA GPU (>= 5.5 GB VRAM) + >= 14 GB RAM -> 7b (fast GPU inference)
    - CPU-only >= 11.5 GB RAM -> 3b (fast 4-8s response, zero UI lag)
    - Weak school lab PC (< 11.5 GB RAM) -> 1.5b (ultra-fast 2-4s response, < 1.2 GB RAM)
    """
    ram_gb = detect_ram_gb()
    vram_gb = detect_nvidia_vram_gb()
    if vram_gb >= 5.5 and ram_gb >= 14.0:
        return PRO_MODEL
    if ram_gb >= 11.5:
        return BALANCED_MODEL
    return DEFAULT_MODEL


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirects())


def normalize_model(value: str) -> str:
    pattern = r"(?:(?:[a-z0-9][a-z0-9_-]*)/)?[a-z0-9][a-z0-9_.-]*(?::[a-z0-9][a-z0-9_.-]*)?"
    if not re.fullmatch(pattern, value, flags=re.ASCII) or len(value) > 120:
        raise ValueError("Ten model Ollama phai co dang ten:tag hoac namespace/ten:tag.")
    name, _, tag = value.partition(":")
    if name.endswith("-cloud") or tag == "cloud" or tag.endswith("-cloud"):
        raise ValueError("Local AI chi ho tro model chay tren may.")
    return name + ":" + (tag or "latest")


def find_ollama() -> Path | None:
    in_path = shutil.which("ollama.exe")
    if in_path:
        return Path(in_path).resolve()
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidate = Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.is_file():
            return candidate.resolve()
    return None


def _models() -> list[dict] | None:
    try:
        with _LOCAL_OPENER.open(f"http://{OLLAMA_HOST}/api/tags", timeout=2) as response:
            raw = response.read(_MAX_TAGS_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Cong localhost 11434 tra ve HTTP {exc.code} thay cho API Ollama.") from exc
    except (OSError, urllib.error.URLError):
        return None
    if len(raw) > _MAX_TAGS_RESPONSE:
        raise RuntimeError("Danh sach model Ollama vuot gioi han phan hoi.")
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise RuntimeError("Cong localhost 11434 khong tra ve danh sach model Ollama hop le.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise RuntimeError("Cong localhost 11434 khong tra ve danh sach model Ollama hop le.")
    return [model for model in data["models"] if isinstance(model, dict)]


def _find_model(models: list[dict] | None, desired: str) -> dict | None:
    for entry in models or ():
        if desired in (entry.get("name"), entry.get("model")):
            return entry
    return None


def _has_local_model(models: list[dict] | None, desired: str) -> bool:
    entry = _find_model(models, desired)
    if entry is None:
        return False
    if entry.get("remote_model") or entry.get("remote_host"):
        raise RuntimeError(f"Model {desired} tro den Ollama Cloud. Hay chon model tai ve chay tren may.")
    return True


def check_local_ai(model: str) -> str:
    if _has_local_model(_models(), model):
        return f"Ollama dang chay va da co {model}."
    if find_ollama() is not None:
        return f"Da co CLI Ollama. Se tai {model} neu can."
    if shutil.which("winget.exe"):
        return f"WinGet co the cai Ollama. Sau do se tai {model} neu can."
    raise RuntimeError("Khong tim thay Ollama hoac WinGet. Cai Ollama tu https://ollama.com/download/windows.")


def _run(command: list[str], timeout: int, env: dict | None = None) -> None:
    try:
        result = subprocess.run(
            command, env=env, timeout=timeout, check=False, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} vuot qua {timeout} giay.") from exc
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} that bai (ma {result.returncode}).")


def _winget() -> str:
    winget = shutil.which("winget.exe")
    if winget is None:
        raise RuntimeError("Khong co WinGet. Cai Ollama tu https://ollama.com/download/windows.")
    return winget


def _install_ollama() -> Path:
    print("Dang cai Ollama bang WinGet cho tai khoan hien tai...", flush=True)
    _run([
        _winget(), "install", "--id", OLLAMA_PACKAGE, "--exact", "--source", "winget",
        "--scope", "user", "--accept-source-agreements", "--accept-package-agreements",
        "--no-upgrade", "--silent", "--disable-interactivity",
    ], timeout=900)
    ollama = find_ollama()
    if ollama is None:
        raise RuntimeError("WinGet da chay xong. Mo lai terminal va chay bo cai Ollama lan nua.")
    return ollama


def _wait_for_ollama(timeout: int = 30) -> list[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        models = _models()
        if models is not None:
            return models
        time.sleep(0.25)
    raise RuntimeError("Khong khoi dong duoc Ollama tren localhost:11434. Mo Ollama va thu cai dat lai.")


def _ollama_env() -> dict[str, str]:
    return dict(os.environ, OLLAMA_HOST=OLLAMA_HOST, OLLAMA_NO_CLOUD="1")


@contextmanager
def _running_ollama(ollama: Path, models: list[dict] | None, *, keep_running: bool = False):
    started = None
    try:
        # The Windows installer may already have started Ollama.
        models = _models() if models is None else models
        if models is None:
            print(f"Dang khoi dong Ollama tren {OLLAMA_HOST}...", flush=True)
            started = subprocess.Popen(
                [str(ollama), "serve"], env=_ollama_env(),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                ),
            )
            # The app started by WinGet can take over the port from this child.
            models = _wait_for_ollama()
        yield models
        if keep_running:
            started = None
    finally:
        if started is not None and started.poll() is None:
            try:
                started.terminate()
                started.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass


def prepare_local_ai(
    model: str,
    *,
    record_install: Callable[[Path], None] | None = None,
    record_pull: Callable[[str, object], None] | None = None,
) -> dict[str, str]:
    model = normalize_model(model)
    models = _models()
    ollama = find_ollama()
    config = {"localModel": model}
    if _has_local_model(models, model):
        print(f"[OK] Ollama da co model {model}.", flush=True)
        if ollama is not None:
            config["localOllamaExecutable"] = str(ollama)
        return config
    if ollama is None:
        if models is not None:
            raise RuntimeError("Ollama dang chay. Them ollama.exe vao PATH de tai model bang bo cai nay.")
        ollama = _install_ollama()
        if record_install is not None:
            record_install(ollama)

    with _running_ollama(ollama, models, keep_running=True) as models:
        if not _has_local_model(models, model):
            print(f"Dang tai model {model}. Lan dau can Internet va co the mat vai phut.", flush=True)
            _run([str(ollama), "pull", model], timeout=1800, env=_ollama_env())
            downloaded = _models()
            if not _has_local_model(downloaded, model):
                raise RuntimeError(f"Ollama chua bao model {model} san sang sau khi tai.")
            if record_pull is not None:
                record_pull(model, _find_model(downloaded, model).get("digest"))
    print(f"[OK] Ollama da co model {model}.", flush=True)
    return {**config, "localOllamaExecutable": str(ollama)}


def _state_path() -> Path:
    local = os.getenv("LOCALAPPDATA")
    if not local or not Path(local).is_absolute():
        raise RuntimeError("Khong tim thay thu muc LOCALAPPDATA cua nguoi dung.")
    directory = Path(local).resolve() / LOCAL_AI_DIR
    if directory.resolve() != directory:
        raise RuntimeError("Thu muc cau hinh Ollama tro sang dia chi khac.")
    return directory / "runtime.json"


@contextmanager
def _state_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        yield
        return
    import msvcrt

    with path.with_suffix(".lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Dang co mot lenh cai hoac go Ollama khac.") from exc
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _valid_digest(digest: object) -> bool:
    return isinstance(digest, str) and re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", digest) is not None


def _read_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"managedModels": {}}
    if not isinstance(state, dict) or not isinstance(state.get("managedModels", {}), dict):
        raise ValueError("runtime.json cua Ollama khong hop le.")
    for key in ("localModel", "localOllamaExecutable", "managedAppExecutable"):
        if key in state and not isinstance(state[key], str):
            raise ValueError("runtime.json cua Ollama khong hop le.")
    models = state.setdefault("managedModels", {})
    if any(normalize_model(name) != name or not _valid_digest(digest) for name, digest in models.items()):
        raise ValueError("runtime.json chua thong tin model Ollama khong hop le.")
    return state


def _write_state(path: Path, state: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def migrate_legacy_local_ai(config: dict) -> None:
    model = config.get("localModel")
    if not isinstance(model, str):
        return
    try:
        model = normalize_model(model)
    except ValueError:
        return
    path = _state_path()
    with _state_lock(path):
        if path.exists():
            return
        state = {"localModel": model, "managedModels": {}}
        executable = config.get("localOllamaExecutable")
        if isinstance(executable, str):
            state["localOllamaExecutable"] = executable
        _write_state(path, state)


def install_local_ai(model: str | None = None, *, auto_model: bool = False) -> dict:
    path = _state_path()
    with _state_lock(path):
        state = _read_state(path)
        if model is None:
            saved = state.get("localModel")
            if isinstance(saved, str) and saved.strip():
                model = normalize_model(saved)
            elif auto_model:
                model = recommend_model_for_machine()
                print(f"[Auto] Chon model {model} theo dung luong RAM cua may.", flush=True)
            else:
                model = DEFAULT_MODEL
        else:
            model = normalize_model(model)

        def record_install(ollama: Path) -> None:
            state["managedAppExecutable"] = str(ollama)
            _write_state(path, state)

        def record_pull(name: str, digest: object) -> None:
            # Only claim a verifiable model version. A replaced tag belongs to the user.
            if _valid_digest(digest):
                state["managedModels"][name] = digest
                _write_state(path, state)

        config = prepare_local_ai(model, record_install=record_install, record_pull=record_pull)
        state.pop("localOllamaExecutable", None)
        state.update(config)
        _write_state(path, state)
        return config


def check_managed_local_ai(model: str | None = None) -> str:
    state = _read_state(_state_path())
    model = normalize_model(state.get("localModel", DEFAULT_MODEL) if model is None else model)
    models = _models()
    if models is None:
        raise RuntimeError(f"Ollama chua chay tren {OLLAMA_HOST}.")
    if not _has_local_model(models, model):
        raise RuntimeError(f"Ollama chua co model {model}.")
    return f"Ollama dang chay va da co {model}."


def _stop_ollama_processes() -> None:
    if sys.platform != "win32":
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for image in ("ollama app.exe", "ollama_llama_server.exe", "ollama.exe"):
        subprocess.run(
            ["taskkill", "/F", "/IM", image, "/T"],
            capture_output=True, stdin=subprocess.DEVNULL,
            creationflags=flags, timeout=15, check=False,
        )


def _force_rmtree(target: Path) -> None:
    def _onerror(func, path, _exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    for attempt in range(8):
        if not target.exists():
            return
        shutil.rmtree(target, onerror=_onerror)
        if not target.exists():
            return
        _stop_ollama_processes()
        time.sleep(0.35)


def _scrub_ollama_windows_traces() -> None:
    if sys.platform != "win32":
        return
    appdata = os.environ.get("APPDATA")
    if appdata:
        start_menu = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        for shortcut in (
            start_menu / "Ollama.lnk",
            start_menu / "Startup" / "Ollama.lnk",
        ):
            try:
                shortcut.unlink(missing_ok=True)
            except OSError:
                pass
    try:
        (Path.home() / "Desktop" / "Ollama.lnk").unlink(missing_ok=True)
    except OSError:
        pass

    try:
        import winreg
    except ImportError:
        return

    # 1. Remove Ollama auto-start Run registry value
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            try:
                winreg.DeleteValue(key, "Ollama")
            except FileNotFoundError:
                pass
    except OSError:
        pass

    # 2. Remove ...\Programs\Ollama from HKCU\Environment\Path
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_READ | winreg.KEY_SET_VALUE,
        ) as env_key:
            raw_path, reg_type = winreg.QueryValueEx(env_key, "Path")
            if isinstance(raw_path, str) and "ollama" in raw_path.casefold():
                parts = [p for p in raw_path.split(";") if "programs\\ollama" not in p.replace("/", "\\").casefold()]
                new_path = ";".join(parts)
                if new_path != raw_path:
                    winreg.SetValueEx(env_key, "Path", 0, reg_type, new_path)
    except OSError:
        pass

    # 3. Remove leftover per-user ARP Uninstall entry if unins000 left it behind
    uninstall_root = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, uninstall_root, 0, winreg.KEY_READ | winreg.KEY_WRITE) as root_key:
            to_delete: list[str] = []
            idx = 0
            while True:
                try:
                    sub_name = winreg.EnumKey(root_key, idx)
                except OSError:
                    break
                idx += 1
                if "ollama" in sub_name.casefold():
                    to_delete.append(sub_name)
                    continue
                try:
                    with winreg.OpenKey(root_key, sub_name, 0, winreg.KEY_READ) as sub_key:
                        disp, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                        if isinstance(disp, str) and disp.strip().casefold() == "ollama":
                            to_delete.append(sub_name)
                except OSError:
                    pass
            for sub_name in to_delete:
                try:
                    winreg.DeleteKey(root_key, sub_name)
                except OSError:
                    pass
    except OSError:
        pass


def purge_ollama_completely() -> None:
    """Scorched-earth removal of Ollama processes, models, app binaries, logs, and registry traces."""
    _stop_ollama_processes()
    ollama = find_ollama()
    local_app = os.environ.get("LOCALAPPDATA")
    default_ollama_dir = Path(local_app).resolve() / "Programs" / "Ollama" if local_app else None

    uninstaller = None
    if ollama is not None and (ollama.parent / "unins000.exe").is_file():
        uninstaller = ollama.parent / "unins000.exe"
    elif default_ollama_dir is not None and (default_ollama_dir / "unins000.exe").is_file():
        uninstaller = default_ollama_dir / "unins000.exe"

    if uninstaller is not None:
        try:
            _run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=300)
        except RuntimeError:
            pass
    elif ollama is not None and shutil.which("winget.exe"):
        try:
            _run([
                _winget(), "uninstall", "--id", OLLAMA_PACKAGE, "--exact",
                "--accept-source-agreements", "--silent", "--disable-interactivity",
            ], timeout=300)
        except RuntimeError:
            pass

    _stop_ollama_processes()
    if local_app:
        local_root = Path(local_app).resolve()
        for folder in (
            local_root / "Programs" / "Ollama",
            local_root / "Ollama",
            local_root / LOCAL_AI_DIR,
        ):
            _force_rmtree(folder)
    _force_rmtree(Path.home() / ".ollama")
    _scrub_ollama_windows_traces()
    print("[OK] Da xoa sach hoan toan Ollama, model, nhat ky va dau vet he thong.", flush=True)


def _is_user_local_ollama(ollama: Path) -> bool:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return False
    expected_dir = (Path(local_appdata) / "Programs" / "Ollama").resolve()
    try:
        resolved = ollama.resolve()
        return resolved == expected_dir or expected_dir in resolved.parents
    except OSError:
        return False


def _uninstall_ollama_package(ollama: Path) -> None:
    _stop_ollama_processes()
    winget_error: RuntimeError | None = None
    uninstalled_via_winget = False
    if shutil.which("winget.exe") or getattr(_winget, "__module__", "") != __name__:
        try:
            _run([
                _winget(), "uninstall", "--id", OLLAMA_PACKAGE, "--exact", "--source", "winget",
                "--scope", "user", "--accept-source-agreements", "--silent", "--disable-interactivity",
            ], timeout=900)
            uninstalled_via_winget = True
        except RuntimeError as exc:
            winget_error = exc
            if not _is_user_local_ollama(ollama):
                raise
    if not uninstalled_via_winget and _is_user_local_ollama(ollama):
        uninstaller = ollama.parent / "unins000.exe"
        if uninstaller.is_file():
            _run([str(uninstaller), "/VERYSILENT", "/NORESTART"], timeout=300)
        elif winget_error is not None:
            raise winget_error
        else:
            raise RuntimeError("Khong tim thay WinGet hoac trinh go Ollama.")


def _remove_managed_models(
    path: Path,
    state: dict,
    ollama: Path,
    models: list[dict],
    *,
    remove_configured_model: bool = False,
) -> list[dict]:
    managed_models = state["managedModels"]
    for model, digest in list(managed_models.items()):
        entry = _find_model(models, model)
        if (
            entry is not None and entry.get("digest") == digest
            and not (entry.get("remote_host") or entry.get("remote_model"))
        ):
            _run([str(ollama), "rm", model], timeout=120, env=_ollama_env())
            models = _models()
            if models is None:
                raise RuntimeError("Mat ket noi Ollama trong khi go model. Chay lai lenh go.")
            if _find_model(models, model) is not None:
                raise RuntimeError(f"Ollama van bao con model {model} sau khi go.")
            if state.get("localModel") == model:
                state.pop("localModel")
        del managed_models[model]
        _write_state(path, state)

    if remove_configured_model:
        configured = state.get("localModel")
        if isinstance(configured, str):
            entry = _find_model(models, configured)
            if entry is not None and not (entry.get("remote_host") or entry.get("remote_model")):
                _run([str(ollama), "rm", configured], timeout=120, env=_ollama_env())
                models = _models()
                if models is None:
                    raise RuntimeError("Mat ket noi Ollama trong khi go model. Chay lai lenh go.")
                if _find_model(models, configured) is not None:
                    raise RuntimeError(f"Ollama van bao con model {configured} sau khi go.")
            state.pop("localModel", None)
            _write_state(path, state)
    return models


def uninstall_local_ai(
    *,
    remove_configured_model: bool = False,
    remove_user_ollama: bool = False,
    purge_all: bool = False,
) -> None:
    if purge_all:
        purge_ollama_completely()
        return
    path = _state_path()
    with _state_lock(path):
        state = _read_state(path)
        managed_app = state.get("managedAppExecutable")
        managed_models = state["managedModels"]
        configured_model = state.get("localModel") if remove_configured_model else None
        needs_ollama = bool(managed_app or managed_models or configured_model or remove_user_ollama)
        if needs_ollama:
            ollama = find_ollama()
            if ollama is None and managed_models:
                raise RuntimeError("Can ollama.exe de go cac model da tai. Them CLI Ollama vao PATH roi thu lai.")
            if ollama is not None:
                with _running_ollama(ollama, _models()) as models:
                    remaining = _remove_managed_models(
                        path, state, ollama, models, remove_configured_model=remove_configured_model,
                    )
                should_uninstall_app = (
                    remaining == []
                    and (managed_app == str(ollama) or (remove_user_ollama and _is_user_local_ollama(ollama)))
                )
                if should_uninstall_app:
                    if remove_user_ollama:
                        _uninstall_ollama_package(ollama)
                    else:
                        _run([
                            _winget(), "uninstall", "--id", OLLAMA_PACKAGE, "--exact", "--source", "winget",
                            "--scope", "user", "--accept-source-agreements", "--silent", "--disable-interactivity",
                        ], timeout=900)
                elif managed_app:
                    print("Giu lai ung dung Ollama va cac model dung chung.", flush=True)
        path.unlink(missing_ok=True)
    if remove_user_ollama:
        shutil.rmtree(path.parent, ignore_errors=True)
    print("[OK] Da go cau hinh AI cuc bo.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall", "check"))
    parser.add_argument("--model")
    parser.add_argument("--auto-model", action="store_true", help="Tu chon model theo RAM may (3b neu >= 12GB, nguoc lai 1.5b).")
    parser.add_argument("--all", action="store_true", dest="remove_all", help="Go ca model da cau hinh va Ollama cua nguoi dung.")
    args = parser.parse_args()
    if args.model is not None and args.action == "uninstall":
        parser.error("--model chi dung cho install hoac check.")
    if args.auto_model and args.action == "uninstall":
        parser.error("--auto-model chi dung cho install hoac check.")
    if args.remove_all and args.action != "uninstall":
        parser.error("--all chi dung voi lenh uninstall.")
    try:
        if args.action == "install":
            install_local_ai(args.model, auto_model=args.auto_model)
        elif args.action == "uninstall":
            uninstall_local_ai(
                remove_configured_model=args.remove_all,
                remove_user_ollama=args.remove_all,
                purge_all=args.remove_all,
            )
        else:
            print(f"[OK] {check_managed_local_ai(args.model)}", flush=True)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"[LOI] {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
