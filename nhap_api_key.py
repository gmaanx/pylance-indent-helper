"""Test and save an encrypted Cloud API key so Alt+2 / Alt+3 run silently with zero popups."""

from __future__ import annotations

import argparse
import getpass
import sys
import warnings

from core_engine.brain_router import call_tier1_cloud_llm
from core_engine.config_manager import (
    PROVIDERS,
    clear_encrypted_credentials,
    save_encrypted_credential,
    session_credentials,
)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Kiểm tra và lưu mã hóa API key Cloud để Alt+2 / Alt+3 chạy thẳng không hiện popup."
    )
    parser.add_argument("--provider", choices=PROVIDERS, help="Nhà cung cấp Cloud (gemini, groq, deepseek, openrouter, openai).")
    parser.add_argument("--key", help="API key (nếu bỏ trống sẽ hỏi ẩn ký tự trong terminal).")
    parser.add_argument("--no-save", action="store_true", help="Chỉ kiểm tra kết nối, không lưu vào máy.")
    parser.add_argument("--skip-check", action="store_true", help="Lưu mã hóa luôn không cần kiểm tra mạng ngay lúc này.")
    parser.add_argument("--clear", action="store_true", help="Xóa toàn bộ API key đã lưu trên máy.")
    args = parser.parse_args()

    if args.clear:
        clear_encrypted_credentials()
        print("[OK] Đã xóa toàn bộ API key đã lưu.")
        return 0

    try:
        provider = (
            args.provider
            or input(f"Nhà cung cấp ({', '.join(PROVIDERS)}) [gemini]: ").strip().lower()
            or "gemini"
        )
        if provider not in PROVIDERS:
            print("Nhà cung cấp không hợp lệ.", file=sys.stderr)
            return 2
        if args.key:
            key = args.key.strip()
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                key = getpass.getpass("API key (ẩn ký tự): ").strip()
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Hãy mở terminal tương tác hoặc truyền --provider ... --key ...", file=sys.stderr)
        return 2

    if not key:
        print("Chưa nhập API key.", file=sys.stderr)
        return 2

    if not args.skip_check:
        with session_credentials({provider: key}):
            result = call_tier1_cloud_llm(
                system_prompt="Chi tra ve mot dong code Python.",
                user_msg="Tra ve chinh xac dong sau: print('API_OK')",
            )
        if result is None:
            print(
                f"{provider} chưa phản hồi. Kiểm tra key, mạng, model và hạn mức "
                "(hoặc thêm --skip-check nếu muốn lưu sẵn khi chưa mở mạng).",
                file=sys.stderr,
            )
            return 1
        print(f"[OK] {provider} đã phản hồi thành công.")

    if not args.no_save:
        saved_path = save_encrypted_credential(provider, key)
        print(f"[OK] Đã mã hóa và lưu key {provider} ({saved_path.name}). Bấm Alt+2 hoặc Alt+3 trong IDE sẽ chạy ngầm ngay không hiện popup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
