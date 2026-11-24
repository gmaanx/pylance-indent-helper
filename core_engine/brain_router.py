"""Request code suggestions from explicitly enabled model providers."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .config_manager import CONFIG
from .golden_skeletons import SIMPLEAI_STRICT_RULES, strip_accents
from .runnable_output import ensure_runnable_print, has_meaningful_runnable_main, prompt_forbids_print


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_CLOUD_OPENER = build_opener(_NoRedirect())
_LOCAL_OPENER = build_opener(ProxyHandler({}), _NoRedirect())
_RESPONSE_LIMIT = 2_000_000
_OLLAMA_URL = "http://127.0.0.1:11434"
_CLOUD_CONFIG = (
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/models/", "gemini-2.5-flash"),
    ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    ("deepseek", "https://api.deepseek.com/chat/completions", "deepseek-chat"),
    ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "qwen/qwen-2.5-coder-32b-instruct:free"),
    ("openai", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
)


def extract_python_code(raw_response: str) -> str:
    if not isinstance(raw_response, str) or not raw_response.strip():
        return ""
    text = raw_response.strip()
    match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    text = re.sub(r"^```(?:python|py)?\s*", "", text, flags=re.IGNORECASE)
    return re.sub(r"```\s*$", "", text).strip()


_AI_RULE_KEYWORDS = (
    "simpleai", "kanren", "minikanren", "searchproblem", "cspproblem",
    "hill_climbing", "simulated_annealing", "arc_consistency",
    "convert_to_binary", "most_constrained_variable", "least_constraining_value",
)


def _needs_ai_library_rules(text: str) -> bool:
    folded = strip_accents(text).casefold()
    if "khong dung simpleai" in folded or ("python thuan" in folded and "simpleai" not in folded and "kanren" not in folded):
        return False
    return any(keyword in folded for keyword in _AI_RULE_KEYWORDS)

_STDIN_KEYWORDS = (
    "stdin", "ban phim", "input()", "nhap tu ban phim", "doc tu ban phim",
    "nhap vao tu", "doc dau vao", "sys.stdin",
)


def _prompt_requests_stdin(text: str) -> bool:
    folded = strip_accents(text).casefold()
    return any(keyword in folded for keyword in _STDIN_KEYWORDS)


def _runnable_output_guidance(user_prompt: str) -> str:
    if _prompt_requests_stdin(user_prompt):
        io_rule = (
            "- Đọc đúng dữ liệu đầu vào theo quy định của đề và chỉ in kết quả theo đúng định dạng yêu cầu."
        )
    else:
        io_rule = (
            "- Nếu đề có yêu cầu định dạng đầu ra (làm tròn, JSON, từng dòng, nhãn...), "
            "chỉ in kết quả theo đúng định dạng yêu cầu của đề.\n"
            "- Không dùng `input()`; gán sẵn dữ liệu mẫu từ đề (hoặc dữ liệu minh họa nhỏ hợp lệ) ngay trong `main()`."
        )
    return (
        "QUY TẮC BẮT BUỘC VỀ HÀM main() VÀ IN KẾT QUẢ KHI CHẠY:\n"
        "- Khi viết lời giải mới (không phải sửa mã có sẵn và đề không cấm ví dụ chạy thử), "
        "LUÔN định nghĩa `def main():` và kết thúc file bằng:\n"
        'if __name__ == "__main__":\n'
        "    main()\n"
        "- Trong `main()`, BẮT BUỘC gọi đúng hàm hoặc khởi tạo đúng lớp và gọi các phương thức vừa cài đặt theo đề, "
        "rồi print kết quả thực tế ra màn hình.\n"
        "- Không viết `main()` rỗng hoặc chỉ in chuỗi giữ chỗ vô nghĩa không gọi lời giải.\n"
        "- Định nghĩa hàm/lớp trước rồi viết `def main():` ở cuối file; đặt tên biến trong `main()` khác tên hàm/lớp (vd: `ket_qua = ...`).\n"
        f"{io_rule}\n"
        "- Giữ nguyên tên lớp, tên hàm và chữ ký API theo đề. Tôn trọng mọi yêu cầu bỏ ví dụ hoặc giữ nguyên đầu ra khi sửa mã có sẵn."
    )


def build_context_injected_prompt(
    user_prompt: str,
    top_skeletons: List[Dict[str, Any]],
    existing_code: str = "",
    error_traceback: str = "",
) -> Tuple[str, str]:
    sections = [
        "Bạn là trợ lý viết chương trình Python. Hãy giữ nguyên toàn bộ dữ liệu, thuật toán, "
        "định dạng đầu ra và các ràng buộc nêu trong yêu cầu. Nếu dùng mẫu tham khảo, bỏ dữ liệu "
        "ví dụ và thay bằng dữ liệu của yêu cầu. Tránh giả định làm thay đổi bài toán. "
        "Xử lý dữ liệu thiếu hoặc không có nghiệm rõ ràng. Chỉ trả về mã Python. "
        "Dùng thư viện chuẩn khi đề yêu cầu Python thuần hoặc không cần thư viện ngoài. "
        "Giữ đúng tên lớp, tên hàm, số chiều và chữ ký phương thức mà đề đã nêu."
    ]
    if top_skeletons or _needs_ai_library_rules(f"{user_prompt}\n{existing_code}"):
        sections.append(SIMPLEAI_STRICT_RULES.strip())
    if top_skeletons:
        examples = "\n\n".join(
            f"Mẫu tham khảo {item['title']}\n{item['code']}" for item in top_skeletons[:2]
        )
        sections.append(examples)
    sections.append(_runnable_output_guidance(user_prompt))
    system_prompt = "\n\n".join(sections)

    parts = [f"Yêu cầu:\n{user_prompt}"]
    if existing_code.strip():
        parts.append(f"Mã hiện tại:\n{existing_code}")
    if error_traceback.strip():
        parts.append(f"Chi tiết lỗi:\n{error_traceback}")
    if not existing_code.strip() and not error_traceback.strip() and not prompt_forbids_print(user_prompt):
        input_hint = "" if _prompt_requests_stdin(user_prompt) else " (gán sẵn dữ liệu mẫu, không dùng `input()`)"
        parts.append(
            f'Viết chương trình Python hoàn chỉnh gồm `def main():` gọi đúng hàm/lớp theo đề{input_hint}, '
            'print kết quả thực tế theo đúng định dạng yêu cầu nếu có, và `if __name__ == "__main__":\\n    main()`.'
        )
    return system_prompt, "\n\n".join(parts)


def _post_json(opener, url, payload, timeout, headers=None):
    req = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with opener.open(req, timeout=timeout) as response:
        message = response.read(_RESPONSE_LIMIT + 1)
    if len(message) > _RESPONSE_LIMIT:
        raise ValueError("Provider response exceeds size limit")
    body = json.loads(message)
    if not isinstance(body, dict):
        raise ValueError("Unexpected provider response")
    return body


def _request_cloud(provider, endpoint, model, key, system_prompt, user_message, timeout):
    if provider == "gemini":
        body = _post_json(
            _CLOUD_OPENER,
            f"{endpoint}{quote(model, safe='')}:generateContent",
            {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
            },
            timeout,
            {"x-goog-api-key": key},
        )
        candidates = body.get("candidates") or []
        if not candidates or candidates[0].get("finishReason") in ("MAX_TOKENS", "SAFETY"):
            return ""
        parts = candidates[0].get("content", {}).get("parts") or []
        return "".join(part.get("text", "") for part in parts if not part.get("thought"))

    body = _post_json(
        _CLOUD_OPENER,
        endpoint,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 8192,
        },
        timeout,
        {"Authorization": f"Bearer {key}", "User-Agent": "PythonPracticeHelper/2.0"},
    )
    choices = body.get("choices") or []
    if not choices or choices[0].get("finish_reason") in ("length", "content_filter"):
        return ""
    return choices[0].get("message", {}).get("content", "")


def _provider_error(provider, exc):
    if isinstance(exc, HTTPError):
        detail = {
            400: "yêu cầu hoặc model không được hỗ trợ",
            401: "API key bị từ chối",
            403: "không có quyền gọi model",
            404: "không tìm thấy model hoặc API",
            429: "đã chạm hạn mức",
        }.get(exc.code, "lỗi từ máy chủ")
        return f"{provider}: HTTP {exc.code}, {detail}."
    if isinstance(exc, (URLError, TimeoutError, OSError)):
        return f"{provider} không kết nối được hoặc hết thời gian chờ."
    return f"{provider} trả về dữ liệu sai định dạng."


def call_tier1_cloud_llm(
    system_prompt: str,
    user_msg: str,
    *,
    diagnostics: Optional[List[str]] = None,
    provider_id: Optional[str] = None,
    max_attempts: Optional[int] = None,
    raw_response: bool = False,
) -> Optional[Tuple[str, str]]:
    messages = diagnostics if diagnostics is not None else []
    timeout = float(CONFIG.get("cloud_timeout", 8.0))
    attempts = 0
    for provider, endpoint, default_model in _CLOUD_CONFIG:
        if max_attempts is not None and attempts >= max_attempts:
            break
        if provider_id is not None and provider_id != provider:
            continue
        key = CONFIG.get_api_key(provider)
        if not key:
            continue
        attempts += 1
        model = CONFIG.get(f"{provider}_model", default_model)
        try:
            result = _request_cloud(provider, endpoint, model, key, system_prompt, user_msg, timeout)
        except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
            messages.append(_provider_error(provider, exc))
            continue
        if isinstance(result, str):
            result = result.strip() if raw_response else extract_python_code(result)
        if result and isinstance(result, str):
            return result, f"tier1_{provider}"
        messages.append(f"{provider} không trả về dữ liệu hoàn chỉnh.")
    if not attempts:
        messages.append("Chưa có API key cho phiên Cloud này.")
    return None


def _repair_ollama_main(model: str, user_prompt: str, draft_code: str, timeout: float) -> Optional[str]:
    repair_system = (
        "Bạn là trợ lý Python. Chỉ trả về mã Python hoàn chỉnh (không giải thích). "
        "Giữ nguyên toàn bộ các lớp và hàm trong mã hiện có, sau đó viết (hoặc thay thế) "
        '`def main():` và `if __name__ == "__main__":\\n    main()` để gọi đúng hàm/lớp đã cài đặt '
        "với dữ liệu mẫu hợp lệ theo đề bài và print kết quả thực tế (theo đúng định dạng đề nếu đề có yêu cầu; "
        'KHÔNG in chuỗi giả như "Xin chào"/"Hello"; KHÔNG dùng `input()` trừ khi đề yêu cầu nhập từ bàn phím).'
    )
    repair_prompt = (
        f"Đề bài:\n{user_prompt}\n\n"
        f"Mã hiện có (thiếu hoặc sai hàm main):\n```python\n{draft_code}\n```\n\n"
        'Hãy trả về lại toàn bộ mã Python đầy đủ kèm `def main():` thực sự gọi lời giải trên và in kết quả.'
    )
    payload = {
        "model": model,
        "system": repair_system,
        "prompt": repair_prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 2048},
    }
    try:
        body = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/generate", payload, timeout)
    except (OSError, ValueError, RecursionError):
        return None
    if body.get("done") is not True or body.get("done_reason") in ("length", "load"):
        return None
    candidate = extract_python_code(body.get("response", ""))
    if not candidate:
        return None
    try:
        compile(candidate, "<ollama-repair>", "exec")
    except (SyntaxError, ValueError, OverflowError, RecursionError, MemoryError):
        return None
    if has_meaningful_runnable_main(candidate, user_prompt):
        return candidate
    return None


def call_tier2_local_llm(
    user_prompt: str,
    best_skeleton: Optional[Dict[str, Any]],
    existing_code: str = "",
    *,
    diagnostics: Optional[List[str]] = None,
) -> Optional[Tuple[str, str]]:
    messages = diagnostics if diagnostics is not None else []
    system_prompt, user_msg = build_context_injected_prompt(
        user_prompt, [best_skeleton] if best_skeleton else [], existing_code,
    )
    # Guard against silent prompt truncation on a small local model.
    if len(user_msg.encode("utf-8")) > 12_000:
        messages.append("Đề quá dài cho chế độ AI cục bộ. Bôi đen một bài hoặc một phần mã ngắn hơn.")
        return None

    model = CONFIG.get("local_model")
    if not isinstance(model, str) or model.casefold().endswith(("-cloud", ":cloud")) or "@cloud" in model.casefold():
        messages.append("Chọn model Ollama được tải trên máy để dùng AI cục bộ.")
        return None
    timeout = float(CONFIG.get("local_timeout", 90.0))
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": user_msg,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 2048},
    }
    try:
        details = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/show", {"model": model}, 5.0)
        if details.get("remote_host") or details.get("remote_model"):
            messages.append("Model đã chọn dùng máy chủ từ xa. Hãy chọn model Ollama được tải trên máy.")
            return None
        body = _post_json(_LOCAL_OPENER, _OLLAMA_URL + "/api/generate", payload, timeout)
    except HTTPError as exc:
        if exc.code == 404:
            messages.append(f"Ollama chưa có model {model}. Chạy setup_ollama.bat để tải model.")
        else:
            messages.append(_provider_error("Ollama", exc))
        return None
    except (URLError, TimeoutError, ConnectionError):
        messages.append("Không kết nối được Ollama cục bộ hoặc hết thời gian chờ. Mở Ollama và thử lại.")
        return None
    except (OSError, ValueError, RecursionError):
        messages.append("Ollama trả dữ liệu không đọc được. Kiểm tra ứng dụng Ollama rồi thử lại.")
        return None

    code = extract_python_code(body.get("response", ""))
    if body.get("done") is True and body.get("done_reason") not in ("length", "load") and code:
        if not existing_code.strip() and not prompt_forbids_print(user_prompt):
            _, has_meaningful = ensure_runnable_print(code, user_prompt)
            if not has_meaningful:
                repaired = _repair_ollama_main(model, user_prompt, code, timeout)
                if repaired:
                    code = repaired
        return code, "tier2_ollama"
    messages.append("Ollama chưa trả mã hoàn chỉnh. Thử yêu cầu ngắn hơn hoặc chọn model khác.")
    return None
