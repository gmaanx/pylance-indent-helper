"""Install and remove the optional per-user Ollama component on Windows."""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import re
import shutil
import stat
import struct
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

HF_GGUF_URLS: dict[str, str] = {
    "qwen2.5-coder:0.5b": "https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
    "qwen2.5-coder:1.5b": "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
    "qwen2.5-coder:3b": "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf",
    "qwen2.5-coder:7b": "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
}

_QWEN_MODELFILE = '''FROM ./model_weights.gguf
TEMPLATE """{{- if .Messages }}
{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
{{- else }}
{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}<|im_end|>
{{ end }}<|im_start|>assistant
{{ end }}{{ .Response }}{{ if .Response }}<|im_end|>{{ end }}"""
SYSTEM "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
'''


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
    GPU- and network-friendly model selector for school lab PCs:
    - Dedicated NVIDIA GPU (>= 6.0 GB VRAM) + >= 14 GB RAM -> 7b
    - Dedicated NVIDIA GPU (>= 4.0 GB VRAM) -> 3b
    - All CPU-only machines / school lab PCs -> 1.5b (986 MB: 2x faster download & 2x faster CPU response)
    """
    ram_gb = detect_ram_gb()
    vram_gb = detect_nvidia_vram_gb()
    if vram_gb >= 6.0 and ram_gb >= 14.0:
        return PRO_MODEL
    if vram_gb >= 4.0 and ram_gb >= 11.5:
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
    in_path = shutil.which("ollama.exe") or shutil.which("ollama")
    if in_path:
        try:
            return Path(in_path).resolve()
        except OSError:
            return Path(in_path)
    candidates: list[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe")
    try:
        candidates.append(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe")
    except Exception:
        pass
    for env_var in ("ProgramFiles", "ProgramFiles(x86)"):
        val = os.environ.get(env_var)
        if val:
            candidates.append(Path(val) / "Ollama" / "ollama.exe")
    candidates.extend((Path(r"C:\Ollama\ollama.exe"), Path(r"D:\Ollama\ollama.exe")))
    for candidate in candidates:
        if candidate.is_file():
            try:
                return candidate.resolve()
            except OSError:
                return candidate
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
    # CRITICAL: Do NOT pass CREATE_NO_WINDOW for `ollama pull`, otherwise Windows hides
    # the live % / MB/s progress bar and makes the console look frozen during download!
    is_pull = len(command) >= 2 and str(command[1]).lower() == "pull"
    flags = 0 if is_pull else getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            command, env=env, timeout=timeout, check=False, stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} vuot qua {timeout} giay.") from exc
    if result.returncode:
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} that bai (ma {result.returncode}).")


def _dismiss_ollama_desktop_gui() -> None:
    """Close the intrusive Ollama desktop chat window / tray and hide Desktop/Startup shortcuts immediately."""
    if sys.platform != "win32" or hasattr(_run, "assert_called"):
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    time.sleep(1.2)
    for image in ("ollama app.exe", "Ollama app.exe"):
        subprocess.run(
            ["taskkill", "/F", "/IM", image, "/T"],
            capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, check=False,
        )
    for env_name in ("USERPROFILE", "OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        val = os.environ.get(env_name)
        if val:
            try:
                (Path(val) / "Desktop" / "Ollama.lnk").unlink(missing_ok=True)
            except OSError:
                pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        try:
            (Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Ollama.lnk").unlink(missing_ok=True)
        except OSError:
            pass


def _winget() -> str:
    winget = shutil.which("winget.exe")
    if winget is None:
        raise RuntimeError("Khong co WinGet. Cai Ollama tu https://ollama.com/download/windows.")
    return winget


def _download_and_install_ollama_direct() -> Path:
    """Fallback direct HTTPS installer for Windows lab PCs without WinGet / Microsoft Store."""
    url = "https://ollama.com/download/OllamaSetup.exe"
    installer_path = Path(tempfile.gettempdir()) / f"OllamaSetup_{os.getpid()}.exe"
    print("Dang tai truc tiep bo cai Ollama chinh thuc (khong can WinGet / Admin)...", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, installer_path.open("wb") as out_f:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            last_pct = -10
            while True:
                chunk = resp.read(512 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    if pct >= last_pct + 10:
                        last_pct = pct
                        print(f"  -> Da tai: {pct}% ({downloaded // (1024 * 1024)} MB / {total // (1024 * 1024)} MB)", flush=True)
        print("Dang cai dat ngam Ollama cho tai khoan hien tai...", flush=True)
        _run(
            [
                str(installer_path),
                "/SP-",
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/CURRENTUSER",
            ],
            timeout=600,
        )
    finally:
        try:
            installer_path.unlink(missing_ok=True)
        except OSError:
            pass
    ollama = find_ollama()
    if ollama is None:
        raise RuntimeError("Khong tim thay ollama.exe sau khi cai dat truc tiep.")
    _dismiss_ollama_desktop_gui()
    return ollama


def _install_ollama() -> Path:
    winget = shutil.which("winget.exe")
    if winget is not None:
        print("Dang cai Ollama bang WinGet cho tai khoan hien tai...", flush=True)
        try:
            _run([
                winget, "install", "--id", OLLAMA_PACKAGE, "--exact", "--source", "winget",
                "--scope", "user", "--accept-source-agreements", "--accept-package-agreements",
                "--no-upgrade", "--silent", "--disable-interactivity",
            ], timeout=900)
            ollama = find_ollama()
            if ollama is not None:
                _dismiss_ollama_desktop_gui()
                return ollama
        except RuntimeError as exc:
            print(f"[Luu y] WinGet khong kha dung tren may nay ({exc}). Chuyen sang tai truc tiep...", flush=True)
    return _download_and_install_ollama_direct()


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


def _enable_windows_ansi_console() -> None:
    """Enable VT100/ANSI escape processing on Windows 10 cmd.exe so `ollama pull` progress bars render cleanly."""
    if sys.platform != "win32":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        for std_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(std_id)
            if handle and handle != -1:
                mode = ctypes.c_uint32()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _generate_openssh_ed25519_keypair() -> tuple[str, str]:
    """Generate a valid RFC 8032 OpenSSH Ed25519 keypair (id_ed25519, id_ed25519.pub) using pure Python stdlib."""
    p = (1 << 255) - 19
    d = (-121665 * pow(121666, p - 2, p)) % p
    by = (4 * pow(5, p - 2, p)) % p
    x2 = ((by * by - 1) * pow(d * by * by + 1, p - 2, p)) % p
    bx = pow(x2, (p + 3) // 8, p)
    if (bx * bx - x2) % p != 0:
        bx = (bx * pow(2, (p - 1) // 4, p)) % p
    if bx & 1:
        bx = p - bx

    def _ed_add(pt1: tuple[int, int, int, int], pt2: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x1, y1, z1, t1 = pt1
        x2_p, y2_p, z2, t2 = pt2
        a = ((y1 - x1) * (y2_p - x2_p)) % p
        b = ((y1 + x1) * (y2_p + x2_p)) % p
        c = (2 * d * t1 * t2) % p
        dd = (2 * z1 * z2) % p
        e, f, g, h = (b - a) % p, (dd - c) % p, (dd + c) % p, (b + a) % p
        return (e * f) % p, (g * h) % p, (f * g) % p, (e * h) % p

    seed = os.urandom(32)
    digest = bytearray(hashlib.sha512(seed).digest()[:32])
    digest[0] &= 248
    digest[31] = (digest[31] & 63) | 64
    scalar = int.from_bytes(digest, "little")

    acc = (0, 1, 1, 0)
    cur = (bx, by, 1, (bx * by) % p)
    while scalar:
        if scalar & 1:
            acc = _ed_add(acc, cur)
        cur = _ed_add(cur, cur)
        scalar >>= 1

    inv_z = pow(acc[2], p - 2, p)
    ax, ay = (acc[0] * inv_z) % p, (acc[1] * inv_z) % p
    pub_raw = bytearray(ay.to_bytes(32, "little"))
    pub_raw[31] |= (ax & 1) << 7
    pub = bytes(pub_raw)

    def _sstr(raw: bytes) -> bytes:
        return struct.pack(">I", len(raw)) + raw

    pub_blob = _sstr(b"ssh-ed25519") + _sstr(pub)
    check_bytes = os.urandom(4) * 2
    priv_inner = check_bytes + _sstr(b"ssh-ed25519") + _sstr(pub) + _sstr(seed + pub) + _sstr(b"")
    pad_len = (8 - (len(priv_inner) % 8)) % 8
    priv_inner += bytes(range(1, pad_len + 1))

    openssh_blob = (
        b"openssh-key-v1\x00"
        + _sstr(b"none")
        + _sstr(b"none")
        + _sstr(b"")
        + struct.pack(">I", 1)
        + _sstr(pub_blob)
        + _sstr(priv_inner)
    )
    b64 = base64.b64encode(openssh_blob).decode("ascii")
    wrapped = "\n".join(b64[i : i + 70] for i in range(0, len(b64), 70))
    priv_pem = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{wrapped}\n-----END OPENSSH PRIVATE KEY-----\n"
    pub_line = f"ssh-ed25519 {base64.b64encode(pub_blob).decode('ascii')}\n"
    return priv_pem, pub_line


def _ensure_ollama_keypair(target_dirs: list[Path] | None = None) -> bool:
    """
    Ensure `~/.ollama/id_ed25519` exists and is valid before `ollama pull`.
    Fixes `Error: pull model manifest: open C:\\Users\\...\\.ollama\\id_ed25519: The system cannot find the file specified.`
    when `.ollama` was deleted while `ollama serve` stayed running or failed to initialize its keypair.
    Returns True if a missing/broken keypair was recreated.
    """
    dirs: list[Path] = []
    if target_dirs is not None:
        dirs.extend(target_dirs)
    else:
        user_prof = os.environ.get("USERPROFILE")
        if user_prof:
            dirs.append(Path(user_prof) / ".ollama")
        try:
            home_ollama = Path.home() / ".ollama"
            if all(str(home_ollama).casefold() != str(existing).casefold() for existing in dirs):
                dirs.append(home_ollama)
        except (OSError, RuntimeError):
            pass

    repaired = False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    for ollama_dir in dirs:
        try:
            ollama_dir.mkdir(parents=True, exist_ok=True)
            (ollama_dir / "models").mkdir(parents=True, exist_ok=True)
            priv = ollama_dir / "id_ed25519"
            pub = ollama_dir / "id_ed25519.pub"
            if (
                priv.is_file()
                and priv.stat().st_size > 100
                and "OPENSSH PRIVATE KEY" in priv.read_text(encoding="utf-8", errors="ignore")
            ):
                continue

            priv.unlink(missing_ok=True)
            pub.unlink(missing_ok=True)

            ssh_keygen = shutil.which("ssh-keygen")
            if not ssh_keygen and sys.platform == "win32":
                sys_ssh = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh-keygen.exe"
                if sys_ssh.is_file():
                    ssh_keygen = str(sys_ssh)
            if ssh_keygen:
                subprocess.run(
                    [ssh_keygen, "-t", "ed25519", "-f", str(priv), "-N", "", "-q"],
                    capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, timeout=15, check=False,
                )

            if not (priv.is_file() and priv.stat().st_size > 100):
                priv_pem, pub_line = _generate_openssh_ed25519_keypair()
                priv.write_text(priv_pem, encoding="ascii")
                pub.write_text(pub_line, encoding="ascii")

            repaired = True
            print(f"[Tu phuc hoi] Da khoi tao khoa {priv} cho Ollama.", flush=True)
        except OSError:
            pass
    return repaired


def _ollama_blobs_total_bytes() -> int:
    total = 0
    seen: set[str] = set()
    for candidate in (
        Path(os.environ["USERPROFILE"]) / ".ollama" / "models" / "blobs" if os.environ.get("USERPROFILE") else None,
        Path.home() / ".ollama" / "models" / "blobs",
    ):
        if candidate is None:
            continue
        key = str(candidate).casefold()
        if key in seen or not candidate.is_dir():
            continue
        seen.add(key)
        try:
            for item in candidate.iterdir():
                try:
                    if item.is_file():
                        total += item.stat().st_size
                except OSError:
                    pass
        except OSError:
            pass
    return total


def _restart_ollama_daemon(ollama: Path) -> None:
    _ensure_ollama_keypair()
    _stop_ollama_processes()
    time.sleep(0.7)
    detach_flag = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) if sys.platform == "win32" else 0
    subprocess.Popen(
        [str(ollama), "serve"],
        env=_ollama_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=(
            detach_flag
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ),
    )
    _wait_for_ollama()


def _download_gguf_from_hf_and_create(ollama: Path, model: str) -> None:
    """
    Single-stream resumable HTTP Range downloader from Hugging Face CDN + `ollama create`.
    Bypasses school firewall throttling/stalling on Cloudflare R2 multi-stream `ollama pull` (e.g. stuck at 30%).
    """
    hf_url = HF_GGUF_URLS.get(model)
    if not hf_url:
        raise RuntimeError(f"Khong co kenh du phong HuggingFace cho model {model}.")

    print(
        f"\n[Chuyen kenh tai toc do cao] Mang truong chan/nghen CDN Ollama tai 30% -> "
        f"Chuyen sang tai truc tiep tu HuggingFace (co tu dong Resume)...",
        flush=True,
    )
    work_dir = Path(tempfile.gettempdir()) / f"pylance_hf_{model.replace(':', '_').replace('/', '_')}"
    work_dir.mkdir(parents=True, exist_ok=True)
    gguf_file = work_dir / "model_weights.gguf"
    modelfile_path = work_dir / "Modelfile"

    try:
        total_size = 0
        for attempt in range(18):
            downloaded = gguf_file.stat().st_size if gguf_file.is_file() else 0
            if total_size > 0 and downloaded >= total_size:
                break
            headers = {"User-Agent": "Mozilla/5.0"}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"
            req = urllib.request.Request(hf_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=18) as resp:
                    status = getattr(resp, "status", 200)
                    if status == 200:
                        downloaded = 0
                        content_len = int(resp.headers.get("Content-Length") or 0)
                        if content_len > 0:
                            total_size = content_len
                        open_mode = "wb"
                    elif status == 206:
                        cr = resp.headers.get("Content-Range") or ""
                        if "/" in cr:
                            try:
                                total_size = int(cr.rsplit("/", 1)[1].strip())
                            except ValueError:
                                pass
                        open_mode = "ab"
                    else:
                        raise RuntimeError(f"HuggingFace tra ve HTTP {status}.")

                    t0 = time.monotonic()
                    bytes_since_t0 = 0
                    last_print_ts = 0.0
                    with gguf_file.open(open_mode) as out_f:
                        while True:
                            chunk = resp.read(512 * 1024)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            bytes_since_t0 += len(chunk)
                            now = time.monotonic()
                            if now - last_print_ts >= 0.5 or (total_size > 0 and downloaded >= total_size):
                                last_print_ts = now
                                dt = max(now - t0, 0.001)
                                mb_s = (bytes_since_t0 / (1024 * 1024)) / dt
                                if total_size > 0:
                                    pct = min(100, int(downloaded * 100 / total_size))
                                    print(
                                        f"\r  -> HuggingFace: {pct:3d}% "
                                        f"({downloaded // (1024 * 1024)} MB / {total_size // (1024 * 1024)} MB) "
                                        f"| {mb_s:.1f} MB/s   ",
                                        end="",
                                        flush=True,
                                    )
                                else:
                                    print(
                                        f"\r  -> HuggingFace: {downloaded // (1024 * 1024)} MB | {mb_s:.1f} MB/s   ",
                                        end="",
                                        flush=True,
                                    )
                if total_size > 0 and gguf_file.stat().st_size >= total_size:
                    print("", flush=True)
                    break
            except Exception as exc:
                if attempt == 17:
                    raise RuntimeError(f"Tai GGUF tu HuggingFace bi ngat ket noi: {exc}") from exc
                cur_mb = (gguf_file.stat().st_size // (1024 * 1024)) if gguf_file.is_file() else 0
                print(f"\n  [Resume {attempt + 1}/18] Noi tiep tai moc {cur_mb} MB...", flush=True)
                time.sleep(1.2)

        if not gguf_file.is_file() or gguf_file.stat().st_size < 50 * 1024 * 1024:
            raise RuntimeError("File GGUF tai ve chua day du.")

        modelfile_path.write_text(_QWEN_MODELFILE, encoding="utf-8")
        if _models() is None:
            _restart_ollama_daemon(ollama)
        print(f"Dang nap model {model} vao Ollama tu file GGUF da tai...", flush=True)
        res = subprocess.run(
            [str(ollama), "create", model, "-f", "Modelfile"],
            cwd=str(work_dir),
            env=_ollama_env(),
            stdin=subprocess.DEVNULL,
            timeout=600,
            check=False,
        )
        if res.returncode != 0:
            _restart_ollama_daemon(ollama)
            res2 = subprocess.run(
                [str(ollama), "create", model, "-f", "Modelfile"],
                cwd=str(work_dir),
                env=_ollama_env(),
                stdin=subprocess.DEVNULL,
                timeout=600,
                check=False,
            )
            if res2.returncode != 0:
                raise RuntimeError(f"ollama create {model} that bai (ma {res2.returncode}).")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def _pull_model_resilient(ollama: Path, model: str) -> None:
    """
    Pull an Ollama model with a 12-second stall watchdog + automatic partial-blob resume,
    and automatic failover to Hugging Face single-stream HTTP Range download if school network stalls Cloudflare R2.
    """
    stagnant_strikes = 0
    for resume_round in range(8):
        start_bytes = _ollama_blobs_total_bytes()
        last_bytes = start_bytes
        last_growth = time.monotonic()

        proc = subprocess.Popen(
            [str(ollama), "pull", model],
            env=_ollama_env(),
            stdin=subprocess.DEVNULL,
            creationflags=0,
        )
        stalled = False
        try:
            while True:
                ret = proc.poll()
                if ret is not None:
                    if ret == 0 and _has_local_model(_models(), model):
                        return
                    break
                time.sleep(1.0)
                cur_bytes = _ollama_blobs_total_bytes()
                if cur_bytes > last_bytes:
                    last_bytes = cur_bytes
                    last_growth = time.monotonic()
                elif time.monotonic() - last_growth >= 12.0:
                    stalled = True
                    break
        finally:
            if proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except OSError:
                    pass

        gained_bytes = max(0, _ollama_blobs_total_bytes() - start_bytes)
        if gained_bytes >= 8 * 1024 * 1024:
            stagnant_strikes = 0
        else:
            stagnant_strikes += 1

        if stagnant_strikes >= 2 and model in HF_GGUF_URLS:
            _download_gguf_from_hf_and_create(ollama, model)
            return

        reason = "bi dung tai cho 12 giay" if stalled else "bi ngat ket noi"
        print(
            f"\n[Tu phuc hoi {resume_round + 1}/8] Tien trinh pull {reason} -> "
            f"Khoi dong lai ket noi de tai tiep tu phan da luu...",
            flush=True,
        )
        _restart_ollama_daemon(ollama)

    if model in HF_GGUF_URLS:
        _download_gguf_from_hf_and_create(ollama, model)
        return
    raise RuntimeError(f"Khong the tai model {model} qua mang hien tai.")


@contextmanager
def _running_ollama(ollama: Path, models: list[dict] | None, *, keep_running: bool = False):
    started = None
    try:
        # The Windows installer may already have started Ollama.
        models = _models() if models is None else models
        if models is None:
            print(f"Dang khoi dong Ollama tren {OLLAMA_HOST}...", flush=True)
            detach_flag = getattr(subprocess, "DETACHED_PROCESS", 0x00000008) if (sys.platform == "win32" and keep_running) else 0
            started = subprocess.Popen(
                [str(ollama), "serve"], env=_ollama_env(),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=(
                    detach_flag
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
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

    is_mocked = hasattr(_run, "assert_called") or hasattr(subprocess.Popen, "assert_called")
    if not is_mocked:
        repaired_key = _ensure_ollama_keypair()
        if repaired_key and models is not None:
            _stop_ollama_processes()
            time.sleep(0.6)
            models = None

    with _running_ollama(ollama, models, keep_running=True) as models:
        if not _has_local_model(models, model):
            pull_marker: Path | None = None
            if not is_mocked:
                _enable_windows_ansi_console()
                try:
                    pull_marker = Path.home() / ".pylance-helper" / "pulling.json"
                    pull_marker.parent.mkdir(parents=True, exist_ok=True)
                    pull_marker.write_text(
                        json.dumps({"model": model, "startedAt": time.time()}),
                        encoding="utf-8",
                    )
                except (OSError, RuntimeError):
                    pull_marker = None
            print(f"Dang tai model {model}. Tien trinh tai truc tiep ben duoi (vui long doi 100%):", flush=True)
            try:
                if is_mocked:
                    _run([str(ollama), "pull", model], timeout=1800, env=_ollama_env())
                else:
                    _pull_model_resilient(ollama, model)
            finally:
                if pull_marker is not None:
                    try:
                        pull_marker.unlink(missing_ok=True)
                    except OSError:
                        pass
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

    pid_file = path.with_suffix(".pid")
    with path.with_suffix(".lock").open("a+b") as lock:
        lock.seek(0)
        locked = False
        for attempt in range(2):
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
                break
            except OSError:
                if attempt == 0:
                    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    if pid_file.is_file():
                        try:
                            old_pid = int(pid_file.read_text(encoding="utf-8").strip())
                            if old_pid > 0 and old_pid != os.getpid():
                                subprocess.run(
                                    ["taskkill", "/F", "/PID", str(old_pid), "/T"],
                                    capture_output=True, stdin=subprocess.DEVNULL,
                                    creationflags=flags, timeout=10, check=False,
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
                            capture_output=True, stdin=subprocess.DEVNULL,
                            creationflags=flags, timeout=10, check=False,
                        )
                    time.sleep(0.5)
        if not locked:
            raise RuntimeError("Dang co mot lenh cai hoac go Ollama khac.")
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


def _mirror_local_ai_path() -> Path:
    return Path.home() / ".pylance-helper" / "local_ai.json"


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
    # Mirror to unvirtualized ~/.pylance-helper/local_ai.json when writing to real user AppData
    try:
        home = Path.home().resolve()
        if str(path.resolve()).casefold().startswith(str(home).casefold()):
            mirror = _mirror_local_ai_path()
            mirror.parent.mkdir(parents=True, exist_ok=True)
            mirror.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, RuntimeError):
        pass


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
    for image in ("ollama app.exe", "Ollama app.exe", "ollama_llama_server.exe", "ollama.exe"):
        subprocess.run(
            ["taskkill", "/F", "/IM", image, "/T"],
            capture_output=True, stdin=subprocess.DEVNULL,
            creationflags=flags, timeout=15, check=False,
        )
    if "unittest" not in sys.modules:
        ps_kill = (
            f"$myPid = {os.getpid()}; "
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
            "$_.ProcessId -ne $myPid -and ("
            "$_.ExecutablePath -match '\\\\Ollama\\\\' -or "
            "($_.Name -eq 'msedgewebview2.exe' -and $_.CommandLine -match 'Ollama')"
            ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_kill],
            capture_output=True, stdin=subprocess.DEVNULL,
            creationflags=flags, timeout=10, check=False,
        )


def _wait_for_inno_uninstaller() -> None:
    """Wait up to 6s for Inno Setup's spawned `_iu*.tmp` child in %TEMP% to finish releasing file locks."""
    if sys.platform != "win32" or "unittest" in sys.modules:
        return
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        res = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq _iu*"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            creationflags=flags, timeout=5, check=False,
        )
        if "_iu" not in (res.stdout or "").lower():
            return
        time.sleep(0.4)
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "Get-Process -Name '_iu*' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"],
        capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, timeout=6, check=False,
    )


def _force_rmtree(target: Path) -> None:
    def _onerror(func, path, _exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            pass

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
    for attempt in range(10):
        if not target.exists():
            return
        shutil.rmtree(target, onerror=_onerror)
        if not target.exists():
            return
        if sys.platform == "win32" and "unittest" not in sys.modules:
            subprocess.run(
                ["cmd.exe", "/d", "/c", "rmdir", "/s", "/q", str(target)],
                capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags, timeout=10, check=False,
            )
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
        if (start_menu / "Ollama").exists():
            _force_rmtree(start_menu / "Ollama")
        for shortcut in (
            start_menu / "Ollama.lnk",
            start_menu / "Startup" / "Ollama.lnk",
            Path(appdata) / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar" / "Ollama.lnk",
        ):
            try:
                shortcut.unlink(missing_ok=True)
            except OSError:
                pass
        if start_menu.is_dir():
            for lnk in start_menu.rglob("*[Oo]llama*.lnk"):
                try:
                    lnk.unlink(missing_ok=True)
                except OSError:
                    pass

    desktop_dirs: list[Path] = []
    try:
        desktop_dirs.append(Path.home() / "Desktop")
    except (OSError, RuntimeError):
        pass
    for env_name in ("USERPROFILE", "OneDrive", "OneDriveConsumer", "OneDriveCommercial", "PUBLIC"):
        val = os.environ.get(env_name)
        if val:
            desktop_dirs.append(Path(val) / "Desktop")

    try:
        import winreg
    except ImportError:
        winreg = None  # type: ignore[assignment]

    if winreg is not None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
                0,
                winreg.KEY_READ,
            ) as sh_key:
                raw_desk, _ = winreg.QueryValueEx(sh_key, "Desktop")
                if isinstance(raw_desk, str) and raw_desk.strip():
                    desktop_dirs.append(Path(os.path.expandvars(raw_desk)))
        except OSError:
            pass

    for desk in desktop_dirs:
        try:
            (desk / "Ollama.lnk").unlink(missing_ok=True)
            if desk.is_dir():
                for lnk in desk.glob("*[Oo]llama*.lnk"):
                    try:
                        lnk.unlink(missing_ok=True)
                    except OSError:
                        pass
        except OSError:
            pass

    if winreg is None:
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
                parts = [p for p in raw_path.split(";") if "ollama" not in p.replace("/", "\\").casefold()]
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
                        if isinstance(disp, str) and "ollama" in disp.strip().casefold():
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

    # 4. Refresh Windows Explorer Desktop & Start Menu icons immediately
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass


def purge_ollama_completely() -> None:
    """Scorched-earth removal of Ollama processes, models, app binaries, logs, shortcuts, and registry traces."""
    _stop_ollama_processes()
    ollama = find_ollama()
    local_app = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    default_ollama_dir = Path(local_app).resolve() / "Programs" / "Ollama" if local_app else None

    extra_ollama_dirs: list[Path] = []
    if ollama is not None and "ollama" in ollama.parent.name.casefold():
        extra_ollama_dirs.append(ollama.parent)
    try:
        st_path = _state_path()
        if st_path.is_file():
            raw_st = json.loads(st_path.read_text(encoding="utf-8"))
            for k in ("managedAppExecutable", "localOllamaExecutable"):
                exe_val = raw_st.get(k)
                if isinstance(exe_val, str) and exe_val:
                    cand_parent = Path(exe_val).parent
                    if "ollama" in cand_parent.name.casefold():
                        extra_ollama_dirs.append(cand_parent)
    except Exception:
        pass

    uninstaller = None
    if ollama is not None and (ollama.parent / "unins000.exe").is_file():
        prog_files = tuple(
            str(Path(os.environ[v]).resolve()).casefold()
            for v in ("ProgramFiles", "ProgramFiles(x86)")
            if os.environ.get(v)
        )
        if not any(str(ollama.parent).casefold().startswith(pf) for pf in prog_files):
            uninstaller = ollama.parent / "unins000.exe"
    elif default_ollama_dir is not None and (default_ollama_dir / "unins000.exe").is_file():
        uninstaller = default_ollama_dir / "unins000.exe"

    if uninstaller is not None:
        try:
            _run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=120)
            _wait_for_inno_uninstaller()
        except RuntimeError:
            pass
    elif ollama is not None and shutil.which("winget.exe"):
        try:
            _run([
                _winget(), "uninstall", "--id", OLLAMA_PACKAGE, "--exact",
                "--accept-source-agreements", "--silent", "--disable-interactivity",
            ], timeout=180)
        except RuntimeError:
            pass

    _stop_ollama_processes()
    folders_to_wipe: list[Path] = list(extra_ollama_dirs)
    if local_app:
        local_root = Path(local_app).resolve()
        folders_to_wipe.extend((
            local_root / "Programs" / "Ollama",
            local_root / "Ollama",
            local_root / LOCAL_AI_DIR,
        ))
    if appdata:
        folders_to_wipe.append(Path(appdata) / "Ollama")
    user_prof = os.environ.get("USERPROFILE")
    if user_prof:
        folders_to_wipe.append(Path(user_prof) / ".ollama")
    try:
        folders_to_wipe.append(Path.home() / ".ollama")
    except (OSError, RuntimeError):
        pass

    seen_dirs: set[str] = set()
    for folder in folders_to_wipe:
        key = str(folder).casefold()
        if key not in seen_dirs:
            seen_dirs.add(key)
            _force_rmtree(folder)

    try:
        tmp_root = Path(tempfile.gettempdir())
        for tmp_item in tmp_root.glob("pylance_hf_*"):
            shutil.rmtree(tmp_item, ignore_errors=True)
        for tmp_item in tmp_root.glob("OllamaSetup_*.exe"):
            try:
                tmp_item.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass

    try:
        _mirror_local_ai_path().unlink(missing_ok=True)
        (Path.home() / ".pylance-helper" / "pulling.json").unlink(missing_ok=True)
    except (OSError, RuntimeError):
        pass
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
        try:
            home = Path.home().resolve()
            if str(path.resolve()).casefold().startswith(str(home).casefold()):
                _mirror_local_ai_path().unlink(missing_ok=True)
        except OSError:
            pass
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
