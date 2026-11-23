"""Install and remove the optional per-user Ollama component on Windows."""

import argparse
import json
import os
import re
import shutil
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
OLLAMA_HOST = "127.0.0.1:11434"
OLLAMA_PACKAGE = "Ollama.Ollama"
LOCAL_AI_DIR = "PylanceHelperLocalAI"
_MAX_TAGS_RESPONSE = 1_000_000


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


def install_local_ai(model: str | None = None) -> dict:
    path = _state_path()
    with _state_lock(path):
        state = _read_state(path)
        model = normalize_model(state.get("localModel", DEFAULT_MODEL) if model is None else model)

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


def _remove_managed_models(path: Path, state: dict, ollama: Path, models: list[dict]) -> list[dict]:
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
    return models


def uninstall_local_ai() -> None:
    path = _state_path()
    with _state_lock(path):
        state = _read_state(path)
        managed_app = state.get("managedAppExecutable")
        managed_models = state["managedModels"]
        if managed_app or managed_models:
            ollama = find_ollama()
            if ollama is None and managed_models:
                raise RuntimeError("Can ollama.exe de go cac model da tai. Them CLI Ollama vao PATH roi thu lai.")
            if ollama is not None:
                with _running_ollama(ollama, _models()) as models:
                    remaining = _remove_managed_models(path, state, ollama, models)
                if managed_app == str(ollama) and remaining == []:
                    _run([
                        _winget(), "uninstall", "--id", OLLAMA_PACKAGE, "--exact", "--source", "winget",
                        "--scope", "user", "--accept-source-agreements", "--silent", "--disable-interactivity",
                    ], timeout=900)
                elif managed_app:
                    print("Giu lai ung dung Ollama va cac model dung chung.", flush=True)
        path.unlink(missing_ok=True)
    print("[OK] Da go cau hinh AI cuc bo.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall", "check"))
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.model is not None and args.action == "uninstall":
        parser.error("--model chi dung cho install hoac check.")
    try:
        if args.action == "install":
            install_local_ai(args.model)
        elif args.action == "uninstall":
            uninstall_local_ai()
        else:
            print(f"[OK] {check_managed_local_ai(args.model)}", flush=True)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"[LOI] {exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
