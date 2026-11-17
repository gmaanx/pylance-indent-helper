# -*- coding: utf-8 -*-
"""
CLI & Local Loopback Micro-Server Entrypoint cho VS Code Extension (`pylance-indent-helper`).
- Goi 1 lan qua stdin/stdout JSON (khong can mo cong mang):
    pythonw.exe -m core_engine.cli_entry --mode full
- Hoac chay micro HTTP loopback server tai 127.0.0.1:59123:
    pythonw.exe -m core_engine.cli_entry --serve --port 59123
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Dam bao import duoc core_engine du goi tu bat ky thu muc nao
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core_engine.engine_pipeline import process_request  # noqa: E402


class _StealthRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        # Tuyet doi im lang, khong ghi log console
        return

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/shutdown":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            raise SystemExit(0)

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            req_data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            req_data = {"text": body}

        text = req_data.get("text", "")
        mode = req_data.get("mode", "full")
        verify = bool(req_data.get("verify", mode != "instant"))

        res = process_request(raw_text=text, action_mode=mode, verify_shadow=verify)
        resp_payload = {
            "code": res.code,
            "verified_ok": res.verified_ok,
            "tier_used": res.tier_used,
            "elapsed_sec": round(res.elapsed_sec, 4),
            "stdout_preview": res.stdout_preview,
            "error_detail": res.error_detail,
        }
        encoded = json.dumps(resp_payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(port: int = 59123) -> None:
    server = HTTPServer(("127.0.0.1", port), _StealthRequestHandler)
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", default="full", choices=["instant", "full", "ghost", "self_fix"])
    parser.add_argument("--no-verify", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=59123)
    args, _ = parser.parse_known_args()

    if args.serve:
        run_server(port=args.port)
        return

    if hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8")
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    raw_in = sys.stdin.read()
    # Ho tro ca JSON input hoac raw text input
    mode = args.mode
    verify = not args.no_verify
    text = raw_in
    if raw_in.lstrip().startswith("{"):
        try:
            parsed_json = json.loads(raw_in)
            if isinstance(parsed_json, dict) and "text" in parsed_json:
                text = parsed_json["text"]
                mode = parsed_json.get("mode", mode)
                verify = bool(parsed_json.get("verify", verify))
        except Exception:
            pass

    res = process_request(raw_text=text, action_mode=mode, verify_shadow=verify)
    out = {
        "code": res.code,
        "verified_ok": res.verified_ok,
        "tier_used": res.tier_used,
        "elapsed_sec": round(res.elapsed_sec, 4),
        "stdout_preview": res.stdout_preview,
        "error_detail": res.error_detail,
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
