# -*- coding: utf-8 -*-
"""
Stealth Configuration & Obfuscated API Key Manager.
Stores keys with XOR + Base64 obfuscation so plain-text keys never appear on disk.
Supports live key updates via Python comments: # @cfg gemini:AIza...
"""

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_XOR_MASK = b"PylanceIndentHelper_v2026_UEH_StealthKeyMask"


def _xor_bytes(data: bytes, mask: bytes = _XOR_MASK) -> bytes:
    return bytes(b ^ mask[i % len(mask)] for i, b in enumerate(data))


def obfuscate_str(plain: str) -> str:
    if not plain:
        return ""
    raw = plain.encode("utf-8")
    xored = _xor_bytes(raw)
    return base64.urlsafe_b64encode(xored).decode("ascii")


def deobfuscate_str(encoded: str) -> str:
    if not encoded:
        return ""
    try:
        xored = base64.urlsafe_b64decode(encoded.encode("ascii"))
        raw = _xor_bytes(xored)
        return raw.decode("utf-8")
    except Exception:
        return ""


def get_stealth_dir() -> Path:
    local_app = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or "."
    stealth_path = Path(local_app) / "Programs" / "PylanceHelper"
    try:
        stealth_path.mkdir(parents=True, exist_ok=True)
        return stealth_path
    except Exception:
        fallback = Path(__file__).resolve().parent
        return fallback


def get_config_file() -> Path:
    local_cfg = Path(__file__).resolve().parent / ".pylance_cache.json"
    if local_cfg.exists():
        return local_cfg
    return get_stealth_dir() / ".pylance_cache.json"


DEFAULT_CONFIG: Dict[str, Any] = {
    "gemini_key_enc": "",
    "groq_key_enc": "",
    "deepseek_key_enc": "",
    "openrouter_key_enc": "",
    "openai_key_enc": "",
    "gemini_model": "gemini-2.5-flash",
    "groq_model": "llama-3.3-70b-versatile",
    "deepseek_model": "deepseek-chat",
    "openrouter_model": "qwen/qwen-2.5-coder-32b-instruct:free",
    "openai_model": "gpt-4o-mini",
    "local_llm_url": "http://127.0.0.1:11434/api/generate",
    "local_llama_cpp_url": "http://127.0.0.1:8080/completion",
    "local_model": "qwen2.5-coder:1.5b",
    "append_verified_comment": False,
    "verified_comment_format": "# kq: {summary}",
    "ping_timeout": 0.8,
    "cloud_timeout": 8.0,
    "local_timeout": 4.5,
    "shadow_timeout": 4.0,
}


class ConfigManager:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        paths_to_check = [
            Path(__file__).resolve().parent / ".pylance_cache.json",
            get_stealth_dir() / ".pylance_cache.json",
        ]
        for p in paths_to_check:
            if p.exists():
                try:
                    loaded = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        self._data.update(loaded)
                except Exception:
                    pass

        # Also allow environment variables if set
        env_map = {
            "GEMINI_API_KEY": "gemini",
            "GROQ_API_KEY": "groq",
            "DEEPSEEK_API_KEY": "deepseek",
            "OPENROUTER_API_KEY": "openrouter",
            "OPENAI_API_KEY": "openai",
        }
        for env_name, provider in env_map.items():
            val = os.environ.get(env_name, "").strip()
            if val and not self.get_api_key(provider):
                self.set_api_key(provider, val, save_disk=False)

    def save(self) -> None:
        target = Path(__file__).resolve().parent / ".pylance_cache.json"
        try:
            target.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            stealth_target = get_stealth_dir() / ".pylance_cache.json"
            stealth_target.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def set_api_key(self, provider: str, raw_key: str, save_disk: bool = True) -> None:
        provider = provider.lower().strip()
        field = f"{provider}_key_enc"
        self._data[field] = obfuscate_str(raw_key.strip())
        if save_disk:
            self.save()

    def get_api_key(self, provider: str) -> str:
        provider = provider.lower().strip()
        field = f"{provider}_key_enc"
        enc = self._data.get(field, "")
        return deobfuscate_str(enc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any, save_disk: bool = True) -> None:
        self._data[key] = value
        if save_disk:
            self.save()

    def apply_inline_cfg(self, cfg_tokens: Dict[str, str]) -> str:
        """
        Applies inline configuration from comment e.g.:
        # @cfg gemini:AIzaSy... groq:gsk_... verified:off
        Returns a stealth status Python comment.
        """
        updated = []
        for k, v in cfg_tokens.items():
            kl = k.lower().strip()
            if kl in ("gemini", "groq", "deepseek", "openrouter", "openai"):
                self.set_api_key(kl, v, save_disk=True)
                updated.append(kl)
            elif kl in ("verified", "verified_tag", "append_verified_comment"):
                flag = v.lower() in ("1", "true", "on", "yes")
                self.set("append_verified_comment", flag)
                updated.append(f"verified={flag}")
            elif kl in ("model", "gemini_model", "groq_model"):
                target_key = "gemini_model" if kl == "model" else kl
                self.set(target_key, v)
                updated.append(f"{target_key}={v}")
            elif kl in ("local_url", "local"):
                self.set("local_llm_url", v)
                updated.append("local_url")
        if updated:
            return f"# Pylance config updated: {', '.join(updated)}"
        return "# Pylance config unchanged"


CONFIG = ConfigManager()
