"""Runtime preferences and API credentials scoped to a single request."""

from __future__ import annotations

import base64
import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Mapping

PROVIDERS = ("gemini", "groq", "deepseek", "openrouter", "openai")
_SESSION_KEYS: ContextVar[Mapping[str, str]] = ContextVar("session_keys", default={})
_MODEL_ID = re.compile(r"[A-Za-z0-9_.:-]+(?:/[A-Za-z0-9_.:-]+)*")

# Retained for callers reading old configuration exports. The runtime ignores
# all encoded key fields and never writes configuration containing credentials.
_XOR_MASK = b"PylanceIndentHelper_v2026_UEH_StealthKeyMask"


def _xor_bytes(data: bytes) -> bytes:
    return bytes(value ^ _XOR_MASK[i % len(_XOR_MASK)] for i, value in enumerate(data))


def obfuscate_str(plain: str) -> str:
    return base64.urlsafe_b64encode(_xor_bytes(plain.encode("utf-8"))).decode("ascii")


def deobfuscate_str(encoded: str) -> str:
    try:
        return _xor_bytes(base64.urlsafe_b64decode(encoded)).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""


def _credentials_file(install_dir: Path | None = None) -> Path | None:
    if install_dir is not None:
        return install_dir / "credentials.json"
    local_app = os.environ.get("LOCALAPPDATA")
    if not local_app or not Path(local_app).is_absolute():
        return None
    return Path(local_app).resolve() / "Programs" / "PylanceHelper" / "credentials.json"


def save_encrypted_credential(provider: str, key: str, install_dir: Path | None = None) -> Path:
    provider = provider.strip().lower()
    cleaned = key.strip()
    if provider not in PROVIDERS:
        raise ValueError(f"Nha cung cap khong hop le: {provider}")
    if not cleaned or len(cleaned) > 1024 or any(ch.isspace() for ch in cleaned):
        raise ValueError("API key khong hop le.")
    target = _credentials_file(install_dir)
    if target is None:
        raise RuntimeError("Khong tim thay thu muc LOCALAPPDATA de luu cau hinh.")
    target.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if target.is_file():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("encoded"), dict):
                existing = {
                    k: v for k, v in raw["encoded"].items()
                    if k in PROVIDERS and isinstance(v, str)
                }
        except (OSError, ValueError):
            existing = {}
    existing[provider] = obfuscate_str(cleaned)
    payload = {"activeProvider": provider, "encoded": existing}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_encrypted_credentials(install_dir: Path | None = None) -> dict[str, str]:
    target = _credentials_file(install_dir)
    if target is None or not target.is_file():
        return {}
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict) or not isinstance(raw.get("encoded"), dict):
        return {}
    encoded_map = raw["encoded"]
    active = raw.get("activeProvider")
    ordered_providers = (
        [active, *[p for p in PROVIDERS if p != active]]
        if isinstance(active, str) and active in PROVIDERS
        else list(PROVIDERS)
    )
    decoded: dict[str, str] = {}
    for provider in ordered_providers:
        enc = encoded_map.get(provider)
        if isinstance(enc, str) and enc.strip():
            plain = deobfuscate_str(enc.strip()).strip()
            if plain and len(plain) <= 1024 and not any(ch.isspace() for ch in plain):
                decoded[provider] = plain
    return decoded


def clear_encrypted_credentials(install_dir: Path | None = None) -> None:
    target = _credentials_file(install_dir)
    if target is not None:
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass


DEFAULT_CONFIG: dict[str, Any] = {
    "gemini_model": "gemini-2.5-flash",
    "groq_model": "llama-3.3-70b-versatile",
    "deepseek_model": "deepseek-chat",
    "openrouter_model": "qwen/qwen-2.5-coder-32b-instruct:free",
    "openai_model": "gpt-4o-mini",
    "local_model": "qwen2.5-coder:1.5b",
    "ping_timeout": 0.8,
    "cloud_timeout": 8.0,
    "local_timeout": 90.0,
    "shadow_timeout": 4.0,
}


@contextmanager
def session_credentials(keys: Mapping[str, str]) -> Iterator[None]:
    scoped = {
        provider: key.strip()
        for provider, key in keys.items()
        if provider in PROVIDERS and isinstance(key, str) and key.strip()
    }
    token = _SESSION_KEYS.set(scoped)
    try:
        yield
    finally:
        _SESSION_KEYS.reset(token)


class ConfigManager:
    def __init__(self) -> None:
        self._data = dict(DEFAULT_CONFIG)
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            local_root = Path(local_app)
            install_dir = local_root / "Programs" / "PylanceHelper"
            self._load_models(install_dir / "models.json")
            runtime = self._read_object(install_dir / "runtime.json")
            self._set_model("local_model", runtime.get("localModel"))
            local_runtime = self._read_object(local_root / "PylanceHelperLocalAI" / "runtime.json")
            self._set_model("local_model", local_runtime.get("localModel"))

    @staticmethod
    def _read_object(config_file: Path) -> dict[str, Any]:
        try:
            models = json.loads(config_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return models if isinstance(models, dict) else {}

    def _set_model(self, field: str, value: object) -> None:
        if isinstance(value, str) and len(value) <= 200 and _MODEL_ID.fullmatch(value):
            self._data[field] = value

    def _load_models(self, config_file: Path) -> None:
        models = self._read_object(config_file)
        for name in (*PROVIDERS, "local"):
            field = f"{name}_model"
            self._set_model(field, models.get(field))

    def get_api_key(self, provider: str) -> str:
        return _SESSION_KEYS.get().get(provider, "")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def apply_inline_cfg(self, cfg_tokens: dict[str, str]) -> str:
        return "# Cấu hình trong mã đã ngừng hỗ trợ. Nhập API key trong lệnh Cloud của IDE."


CONFIG = ConfigManager()
