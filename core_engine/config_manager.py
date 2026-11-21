"""Runtime preferences and API credentials scoped to a single request."""

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


DEFAULT_CONFIG: dict[str, Any] = {
    "gemini_model": "gemini-2.5-flash",
    "groq_model": "llama-3.3-70b-versatile",
    "deepseek_model": "deepseek-chat",
    "openrouter_model": "qwen/qwen-2.5-coder-32b-instruct:free",
    "openai_model": "gpt-4o-mini",
    "local_llm_url": "http://127.0.0.1:11434/api/generate",
    "local_llama_cpp_url": "http://127.0.0.1:8080/completion",
    "local_model": "qwen2.5-coder:1.5b",
    "ping_timeout": 0.8,
    "cloud_timeout": 8.0,
    "local_timeout": 4.5,
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
            self._load_models(Path(local_app) / "Programs" / "PylanceHelper" / "models.json")

    def _load_models(self, config_file: Path) -> None:
        try:
            models = json.loads(config_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(models, dict):
            return
        for name in (*PROVIDERS, "local"):
            field = f"{name}_model"
            value = models.get(field)
            if isinstance(value, str) and len(value) <= 200 and _MODEL_ID.fullmatch(value):
                self._data[field] = value

    def get_api_key(self, provider: str) -> str:
        return _SESSION_KEYS.get().get(provider, "")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def apply_inline_cfg(self, cfg_tokens: dict[str, str]) -> str:
        return "# Cấu hình trong mã đã ngừng hỗ trợ. Nhập API key trong lệnh Cloud của IDE."


CONFIG = ConfigManager()
