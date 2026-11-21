"""Request code suggestions from explicitly enabled model providers."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .config_manager import CONFIG
from .golden_skeletons import SIMPLEAI_STRICT_RULES


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_CLOUD_OPENER = build_opener(_NoRedirect())
_LOCAL_OPENER = build_opener(ProxyHandler({}), _NoRedirect())
_RESPONSE_LIMIT = 2_000_000
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


def build_context_injected_prompt(
    user_prompt: str,
    top_skeletons: List[Dict[str, Any]],
    existing_code: str = "",
    error_traceback: str = "",
) -> Tuple[str, str]:
    system_prompt = (
        "Bạn là trợ lý viết chương trình Python. Hãy giữ nguyên toàn bộ dữ liệu, thuật toán, "
        "định dạng đầu ra và các ràng buộc nêu trong yêu cầu. Nếu dùng mẫu tham khảo, bỏ dữ liệu "
        "ví dụ và thay bằng dữ liệu của yêu cầu. Tránh giả định làm thay đổi bài toán. "
        "Xử lý dữ liệu thiếu hoặc không có nghiệm rõ ràng. Chỉ trả về mã Python. "
        "Áp dụng hướng dẫn SimpleAI và miniKanren dưới đây nếu dùng các thư viện đó.\n\n"
        + SIMPLEAI_STRICT_RULES
    )
    if top_skeletons:
        examples = "\n\n".join(
            f"Mẫu tham khảo {item['title']}\n{item['code']}" for item in top_skeletons[:2]
        )
        system_prompt += "\n\n" + examples
    parts = [f"Yêu cầu:\n{user_prompt}"]
    if existing_code.strip():
        parts.append(f"Mã hiện tại:\n{existing_code}")
    if error_traceback.strip():
        parts.append(f"Chi tiết lỗi:\n{error_traceback}")
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
    prompt = system_prompt + "\n\n" + user_msg
    timeout = float(CONFIG.get("local_timeout", 4.5))
    configs = (
        ("ollama", "http://127.0.0.1:11434/api/generate", "response", {
            "model": CONFIG.get("local_model", "qwen2.5-coder:1.5b"),
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 4096},
        }),
        ("llamacpp", "http://127.0.0.1:8080/completion", "content", {
            "prompt": prompt,
            "temperature": 0.1,
            "n_predict": 4096,
        }),
    )
    for provider, endpoint, response_key, payload in configs:
        try:
            body = _post_json(_LOCAL_OPENER, endpoint, payload, timeout)
        except (OSError, ValueError, RecursionError) as exc:
            messages.append(_provider_error(provider, exc))
            continue
        code = extract_python_code(body.get(response_key, ""))
        if code and body.get("done_reason") != "length" and not body.get("truncated"):
            return code, f"tier2_{provider}"
        messages.append(f"{provider} không trả về mã hoàn chỉnh.")
    return None
