"""Optional per-user Ollama setup for the Windows installer."""

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_MODEL = "qwen2.5-coder:1.5b"
OLLAMA_HOST = "127.0.0.1:11434"
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


def _has_local_model(models: list[dict] | None, desired: str) -> bool:
    for entry in models or ():
        if desired not in (entry.get("name"), entry.get("model")):
            continue
        if entry.get("remote_model") or entry.get("remote_host"):
            raise RuntimeError(f"Model {desired} tro den Ollama Cloud. Hay chon model tai ve chay tren may.")
        return True
    return False


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
        result = subprocess.run(command, env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} vuot qua {timeout} giay.") from exc
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} that bai (ma {result.returncode}).")


def _install_ollama() -> Path:
    winget = shutil.which("winget.exe")
    if winget is None:
        raise RuntimeError("Khong co WinGet. Cai Ollama tu https://ollama.com/download/windows.")
    print("Dang cai Ollama bang WinGet cho tai khoan hien tai...", flush=True)
    _run([
        winget, "install", "--id", "Ollama.Ollama", "--exact", "--source", "winget",
        "--scope", "user", "--accept-source-agreements", "--accept-package-agreements",
        "--disable-interactivity",
    ], timeout=900)
    ollama = find_ollama()
    if ollama is None:
        raise RuntimeError("WinGet da chay xong. Mo lai terminal va thu setup_nhanh.bat --local.")
    return ollama


def _wait_for_ollama(process: subprocess.Popen, timeout: int = 30) -> list[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        models = _models()
        if models is not None:
            return models
        if process.poll() is not None:
            break
        time.sleep(0.25)
    raise RuntimeError("Khong khoi dong duoc Ollama tren localhost:11434. Mo Ollama va thu cai dat lai.")


def prepare_local_ai(model: str) -> dict[str, str]:
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
        ollama = _install_ollama()

    env = dict(os.environ, OLLAMA_HOST=OLLAMA_HOST, OLLAMA_NO_CLOUD="1")
    started = None
    try:
        # The Windows installer may already have started the Ollama application.
        if models is None:
            models = _models()
        if models is None:
            print(f"Dang khoi dong Ollama tren {OLLAMA_HOST}...", flush=True)
            started = subprocess.Popen(
                [str(ollama), "serve"], env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=(
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                ),
            )
            models = _wait_for_ollama(started)
        if not _has_local_model(models, model):
            print(f"Dang tai model {model}. Lan dau can Internet va co the mat vai phut.", flush=True)
            _run([str(ollama), "pull", model], timeout=1800, env=env)
            if not _has_local_model(_models(), model):
                raise RuntimeError(f"Ollama chua bao model {model} san sang sau khi tai.")
    except BaseException:
        if started is not None and started.poll() is None:
            try:
                started.terminate()
                started.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        raise
    print(f"[OK] Ollama da co model {model}.", flush=True)
    return {**config, "localOllamaExecutable": str(ollama)}
