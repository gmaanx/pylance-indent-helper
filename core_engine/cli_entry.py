"""Read an offline or explicitly authorized Cloud/Local request over stdin."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core_engine.config_manager import PROVIDERS, session_credentials
from core_engine.engine_pipeline import process_request

MODES = ("instant", "full", "ghost", "self_fix", "local")
MAX_INPUT_BYTES = 256 * 1024


def _invalid_request(message: str) -> dict:
    return {
        "code": "",
        "verified_ok": False,
        "validation_status": "invalid",
        "diagnostics": [message],
        "tier_used": "",
        "elapsed_sec": 0,
        "stdout_preview": "",
        "error_detail": message,
    }


def decode_request(raw: str, mode: str = "full", verify: bool = True, *, allow_network: bool = False) -> dict:
    text = raw
    cloud = False
    local = False
    shadow_exec = False
    rag_fallback = False
    file_path = None
    notebook_context = None
    credentials = {}
    if raw.lstrip().startswith("{"):
        try:
            request = json.loads(raw)
        except (ValueError, RecursionError):
            request = None
        if isinstance(request, dict) and "text" in request:
            text = request["text"]
            mode = request.get("mode", mode)
            verify = request.get("verify", verify)
            cloud = allow_network and mode != "local" and request.get("allow_cloud") is True
            local = allow_network and request.get("allow_local") is True
            shadow_exec = allow_network and request.get("shadow_exec") is True
            rag_fallback = request.get("allow_rag_fallback") is True
            raw_fp = request.get("file_path")
            if isinstance(raw_fp, str) and len(raw_fp) <= 4096:
                file_path = raw_fp
            raw_nb = request.get("notebook_context")
            if isinstance(raw_nb, str) and len(raw_nb) <= 32_768:
                notebook_context = raw_nb
            if cloud:
                credentials = request.get("credentials")
                if not isinstance(credentials, dict) or not credentials or any(
                    provider not in PROVIDERS
                    or not isinstance(key, str)
                    or not 0 < len(key.strip()) <= 1024
                    or any(char.isspace() for char in key.strip())
                    for provider, key in credentials.items()
                ):
                    return _invalid_request("Chọn nhà cung cấp và nhập API key cho yêu cầu Cloud.")
    if not isinstance(text, str) or mode not in MODES or not isinstance(verify, bool):
        return _invalid_request("Yêu cầu phải có text dạng chuỗi, mode hợp lệ và verify dạng boolean.")

    with session_credentials(credentials):
        try:
            result = process_request(
                raw_text=text,
                action_mode=mode,
                verify_shadow=verify,
                allow_cloud=cloud,
                allow_local=local,
                allow_shadow_exec=shadow_exec,
                allow_rag_fallback=rag_fallback,
                file_path=file_path,
                notebook_context=notebook_context,
            )
        except (ValueError, RecursionError):
            return _invalid_request("Dữ liệu yêu cầu không hợp lệ.")
    return {
        "code": result.code,
        "verified_ok": result.verified_ok,
        "validation_status": result.validation_status,
        "diagnostics": list(result.diagnostics),
        "tier_used": result.tier_used,
        "elapsed_sec": round(result.elapsed_sec, 4),
        "stdout_preview": result.stdout_preview,
        "error_detail": result.error_detail,
    }


class _OfflineRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= MAX_INPUT_BYTES:
                self.send_error(413)
                return
            body = self.rfile.read(length).decode("utf-8")
        except ValueError:
            self.send_error(400)
            return

        encoded = json.dumps(decode_request(body), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(port: int = 59123) -> None:
    with HTTPServer(("127.0.0.1", port), _OfflineRequestHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="full", choices=MODES)
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--serve", action="store_true", help="Run the offline loopback server.")
    parser.add_argument("--port", type=int, default=59123)
    args = parser.parse_args()

    if args.serve:
        run_server(port=args.port)
        return

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        result = _invalid_request("Yêu cầu vượt quá 256 KiB.")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            result = _invalid_request("Yêu cầu phải dùng UTF-8.")
        else:
            result = decode_request(text, args.mode, not args.no_verify, allow_network=True)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
