"""Check a single Cloud provider with a masked API key prompt."""

import argparse
import getpass
import sys
import warnings

from core_engine.brain_router import call_tier1_cloud_llm
from core_engine.config_manager import PROVIDERS, session_credentials


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Thử API key Cloud. Key chỉ dùng cho lần kiểm tra này.")
    parser.add_argument("--provider", choices=PROVIDERS)
    args = parser.parse_args()

    try:
        provider = args.provider or input(f"Nhà cung cấp ({', '.join(PROVIDERS)}) [gemini] ").strip().lower() or "gemini"
        if provider not in PROVIDERS:
            print("Nhà cung cấp không hợp lệ.", file=sys.stderr)
            return 2
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("API key ").strip()
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Hãy mở terminal tương tác để nhập key mà không hiện ký tự.", file=sys.stderr)
        return 2
    if not key:
        print("Chưa nhập API key.", file=sys.stderr)
        return 2

    with session_credentials({provider: key}):
        result = call_tier1_cloud_llm(
            system_prompt="Chi tra ve mot dong code Python.",
            user_msg="Tra ve chinh xac dong sau: print('API_OK')",
        )
    if result is None:
        print(f"{provider} chưa phản hồi. Kiểm tra key, mạng, model và hạn mức.", file=sys.stderr)
        return 1
    print(f"{provider} đã phản hồi yêu cầu thử. Nhập key trong IDE để dùng Cloud.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
