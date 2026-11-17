# -*- coding: utf-8 -*-
"""
Cong cu nap va ma hoa API Key truoc khi copy ra USB (hoac chay tren may).
Ho tro: Gemini, Groq, DeepSeek, OpenRouter, OpenAI.
Cach dung nhanh:
    python setup_lab/set_api_key.py --gemini AIzaSy... --groq gsk_...
Hoac chay khong tham so de nhap truc tiep.
"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core_engine.config_manager import CONFIG  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure obfuscated API keys for Pylance Helper")
    parser.add_argument("--gemini", help="Google AI Studio Gemini API Key (AIza...)")
    parser.add_argument("--groq", help="Groq API Key (gsk_...)")
    parser.add_argument("--deepseek", help="DeepSeek API Key (sk-...)")
    parser.add_argument("--openrouter", help="OpenRouter API Key (sk-or-...)")
    parser.add_argument("--openai", help="OpenAI API Key (sk-...)")
    parser.add_argument("--show", action="store_true", help="Check which providers have keys configured")
    args = parser.parse_args()

    updated = []
    for prov in ("gemini", "groq", "deepseek", "openrouter", "openai"):
        val = getattr(args, prov, None)
        if val:
            CONFIG.set_api_key(prov, val.strip(), save_disk=True)
            updated.append(prov)

    if not updated and not args.show and sys.stdin.isatty():
        print("=== CAU HINH API KEY (Enter de bo qua nha cung cap khong dung) ===")
        for prov in ("gemini", "groq", "deepseek", "openrouter"):
            cur = CONFIG.get_api_key(prov)
            masked = f"{cur[:6]}...{cur[-4:]}" if len(cur) > 10 else ("(da co)" if cur else "(chua co)")
            raw = input(f"Nhap {prov.upper()} API Key {masked}: ").strip()
            if raw:
                CONFIG.set_api_key(prov, raw, save_disk=True)
                updated.append(prov)

    print("\nTrang thai API Key hien tai (da ma hoa XOR+Base64 trong .pylance_cache.json):")
    for prov in ("gemini", "groq", "deepseek", "openrouter", "openai"):
        k = CONFIG.get_api_key(prov)
        status = f"OK ({k[:5]}...{k[-3:]})" if len(k) > 8 else ("OK" if k else "Chua cai")
        print(f"  - {prov:<12}: {status}")


if __name__ == "__main__":
    main()
