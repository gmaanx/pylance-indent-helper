# -*- coding: utf-8 -*-
"""
Công cụ Nạp, Mã hóa & Kiểm tra kết nối API Key (Tầng 1 Cloud AI: Gemini / Groq / DeepSeek / OpenRouter).
Cách dùng:
  1. Chạy trực tiếp:
       D:\\UEH\\ai\\.venv\\Scripts\\python.exe d:\\UEH\\ai\\midtermtool\\nhap_api_key.py
  2. Hoặc truyền qua tham số dòng lệnh:
       D:\\UEH\\ai\\.venv\\Scripts\\python.exe d:\\UEH\\ai\\midtermtool\\nhap_api_key.py --gemini AIzaSy...
"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core_engine.brain_router import call_tier1_cloud_llm  # noqa: E402
from core_engine.config_manager import CONFIG  # noqa: E402


def mask_key(k: str) -> str:
    if not k:
        return "(Chưa cài)"
    if len(k) <= 10:
        return "Đã cài (***)"
    return f"Đã cài ({k[:6]}...{k[-4:]})"


def test_live_api() -> None:
    print("\n[*] Đang kiểm tra kết nối thực tế tới Cloud API (Tầng 1)...")
    res = call_tier1_cloud_llm(
        system_prompt="Chi tra ve code Python.",
        user_msg="Viet 1 dong code Python: print('API_OK')",
    )
    if res is not None:
        code, provider_used = res
        print(f"[THÀNH CÔNG] Tầng 1 ({provider_used}) đã phản hồi code chuẩn xác:")
        print(f"  -> {code.strip()}")
        print("=> Khi bạn bấm Alt + 2 hoặc Alt + 3, hệ thống sẽ ưu tiên dùng Cloud AI Tầng 1 này!")
    else:
        print("[CHƯA KẾT NỐI ĐƯỢC TẦNG 1] Chưa có API Key hợp lệ hoặc đang mất mạng.")
        print("=> Hệ thống sẽ tự động dùng Tầng 3 (Kho 47 Phôi Vàng Offline) khi bạn bấm Alt + 1 / Alt + 2.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nạp & Kiểm tra API Key cho midtermtool")
    parser.add_argument("--gemini", help="Google Gemini API Key (bắt đầu bằng AIza...)")
    parser.add_argument("--groq", help="Groq API Key (bắt đầu bằng gsk_...)")
    parser.add_argument("--deepseek", help="DeepSeek API Key (bắt đầu bằng sk-...)")
    parser.add_argument("--openrouter", help="OpenRouter API Key (bắt đầu bằng sk-or-...)")
    parser.add_argument("--openai", help="OpenAI API Key (bắt đầu bằng sk-...)")
    parser.add_argument("--test", action="store_true", help="Chạy thử kết nối tới Cloud API")
    args = parser.parse_args()

    updated = []
    for prov in ("gemini", "groq", "deepseek", "openrouter", "openai"):
        val = getattr(args, prov, None)
        if val is not None:
            CONFIG.set_api_key(prov, val.strip(), save_disk=True)
            updated.append(prov)

    if not updated and not args.test and sys.stdin.isatty():
        print("==================================================================")
        print("   CẤU HÌNH API KEY CHO TẦNG 1 (CLOUD AI - ALT + 2 & ALT + 3)    ")
        print("==================================================================")
        print("Gợi ý lấy Key miễn phí trong 30 giây:")
        print("  1. Gemini (Khuyên dùng): https://aistudio.google.com/app/apikey")
        print("  2. Groq (Siêu nhanh):    https://console.groq.com/keys")
        print("------------------------------------------------------------------")
        print("(Nhấn Enter bỏ qua nếu muốn giữ nguyên hoặc không dùng hãng đó)\n")

        for prov, hint in [
            ("gemini", "AIzaSy..."),
            ("groq", "gsk_..."),
            ("deepseek", "sk-..."),
            ("openrouter", "sk-or-..."),
        ]:
            cur = CONFIG.get_api_key(prov)
            raw = input(f"Nhập {prov.upper()} API Key [{mask_key(cur)}] (VD: {hint}): ").strip()
            if raw:
                CONFIG.set_api_key(prov, raw, save_disk=True)
                updated.append(prov)

    print("\n--- TRẠNG THÁI API KEY HIỆN TẠI (Đã mã hóa ẩn XOR+Base64) ---")
    for prov in ("gemini", "groq", "deepseek", "openrouter", "openai"):
        print(f"  + {prov.upper():<12}: {mask_key(CONFIG.get_api_key(prov))}")

    if any(CONFIG.get_api_key(p) for p in ("gemini", "groq", "deepseek", "openrouter", "openai")):
        test_live_api()


if __name__ == "__main__":
    main()
