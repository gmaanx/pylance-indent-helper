# -*- coding: utf-8 -*-
"""
Module 3: Bo Nao 3 Tang Tu Dong Chuyen Kenh (brain_router.py).
- Tang 1: Cloud API (Gemini -> Groq -> DeepSeek -> OpenRouter -> OpenAI) voi Context Injection
          (2 Phoi Vang BM25 sat nhat + Bang quy tac cung SimpleAI/miniKanren).
- Tang 2: Local LLM (Ollama 11434 / llama-server 8080) neu may phong lab co bat server local.
- Tang 3: Pure Offline BM25 RAG + Smart Parameter Extractor (Bat tu 100% khi cat mang).
"""

import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from .config_manager import CONFIG
from .dual_parser import ParsedInput
from .golden_skeletons import (
    ALL_SKELETONS,
    RETRIEVER,
    SIMPLEAI_STRICT_RULES,
    customize_skeleton_with_prompt,
)


def extract_python_code(raw_response: str) -> str:
    """Bóc tách khối code Python sạch từ phản hồi của LLM."""
    if not raw_response:
        return ""
    text = raw_response.strip()
    m_fence = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m_fence:
        return m_fence.group(1).strip()
    # Neu LLM khong dong fence hoac tra thang code
    text = re.sub(r"^```(?:python|py)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()


def _quick_tcp_check(host: str, port: int, timeout: float = 0.7) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_internet_alive(timeout: Optional[float] = None) -> bool:
    t = timeout if timeout is not None else float(CONFIG.get("ping_timeout", 0.8))
    for host, port in (("generativelanguage.googleapis.com", 443), ("1.1.1.1", 53), ("8.8.8.8", 53)):
        if _quick_tcp_check(host, port, timeout=t):
            return True
    return False


def is_local_server_alive() -> Optional[Tuple[str, str]]:
    """
    Kiểm tra cực nhanh (0.12s) xem máy có chạy Ollama (11434) hoặc llama-server (8080) không.
    """
    if _quick_tcp_check("127.0.0.1", 11434, timeout=0.12):
        return ("ollama", CONFIG.get("local_llm_url", "http://127.0.0.1:11434/api/generate"))
    if _quick_tcp_check("127.0.0.1", 8080, timeout=0.12):
        return ("llamacpp", CONFIG.get("local_llama_cpp_url", "http://127.0.0.1:8080/completion"))
    return None


def build_context_injected_prompt(
    user_prompt: str,
    top_skeletons: List[Dict[str, Any]],
    existing_code: str = "",
    error_traceback: str = "",
) -> Tuple[str, str]:
    """
    Tạo cặp (system_prompt, user_message) kẹp 2 Phôi Vàng giống đề nhất + Quy tắc cứng SimpleAI.
    """
    skeleton_context = []
    for idx, sk in enumerate(top_skeletons[:2], start=1):
        skeleton_context.append(
            f"=== PHOI VANG MAU #{idx}: {sk['title']} ===\n{sk['code']}\n"
        )
    joined_skeletons = "\n".join(skeleton_context)

    system_prompt = (
        "Ban la tro ly giai bai thi thuc hanh mon Tri Tue Nhan Tao bang Python (thu vien simpleai, miniKanren, hoac cai chay).\n"
        "NHIEM VU: Dua tren PHONG CACH CODE va CU PHAP CHUAN trong PHOI VANG MAU duoi day, hay viet code Python HOAN CHINH, "
        "CHAY DUOC NGAY LAP TUC (returncode == 0) giai dung yeu cau va so lieu cua de bai.\n"
        "CHI TRA VE DUY NHAT KHOI CODE PYTHON, KHONG GIAI THICH, KHONG VIET VAN BAN NGOAI CODE.\n\n"
        f"{SIMPLEAI_STRICT_RULES}\n\n"
        f"THAM KHAO 2 PHOI VANG CHUAN XAC 100% TREN LOP:\n{joined_skeletons}"
    )

    parts = [f"DE BAI / YEU CAU:\n{user_prompt}"]
    if existing_code.strip():
        parts.append(f"CODE KHUNG CO SAN TRONG FILE (giu nguyen hoac hoan thien):\n```python\n{existing_code}\n```")
    if error_traceback.strip():
        parts.append(
            f"CODE TRUOC DO BI LOI TRACEBACK SAU, HAY SUA TRIET DE:\n{error_traceback}"
        )
    parts.append("Chi xuat ra code Python hoan chinh:")
    return system_prompt, "\n\n".join(parts)


def _call_gemini_api(system_prompt: str, user_msg: str, timeout: float) -> Optional[str]:
    api_key = CONFIG.get_api_key("gemini")
    if not api_key:
        return None
    model = CONFIG.get("gemini_model", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    candidates = body.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return extract_python_code(text)
    return None


def _call_openai_compatible_api(
    provider: str,
    endpoint_url: str,
    model_name: str,
    system_prompt: str,
    user_msg: str,
    timeout: float,
) -> Optional[str]:
    api_key = CONFIG.get_api_key(provider)
    if not api_key:
        return None
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "PylanceIndentHelper/1.0",
    }
    req = urllib.request.Request(endpoint_url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    choices = body.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
        return extract_python_code(content)
    return None


def call_tier1_cloud_llm(
    system_prompt: str,
    user_msg: str,
) -> Optional[Tuple[str, str]]:
    """
    Thử lần lượt các nhà cung cấp Cloud API đã cấu hình Key (Gemini -> Groq -> DeepSeek -> OpenRouter -> OpenAI).
    Trả về (code, ten_kenh) nếu thành công, hoặc None.
    """
    has_any_key = any(
        CONFIG.get_api_key(p) for p in ("gemini", "groq", "deepseek", "openrouter", "openai")
    )
    if not has_any_key:
        return None

    if not is_internet_alive():
        return None

    timeout = float(CONFIG.get("cloud_timeout", 8.0))

    # 1. Gemini API
    if CONFIG.get_api_key("gemini"):
        try:
            code = _call_gemini_api(system_prompt, user_msg, timeout=timeout)
            if code:
                return code, "tier1_gemini"
        except Exception:
            pass

    # 2. Groq / DeepSeek / OpenRouter / OpenAI
    providers = [
        ("groq", "https://api.groq.com/openai/v1/chat/completions", CONFIG.get("groq_model", "llama-3.3-70b-versatile")),
        ("deepseek", "https://api.deepseek.com/chat/completions", CONFIG.get("deepseek_model", "deepseek-chat")),
        ("openrouter", "https://openrouter.ai/api/v1/chat/completions", CONFIG.get("openrouter_model", "qwen/qwen-2.5-coder-32b-instruct:free")),
        ("openai", "https://api.openai.com/v1/chat/completions", CONFIG.get("openai_model", "gpt-4o-mini")),
    ]
    for prov, url, model in providers:
        if CONFIG.get_api_key(prov):
            try:
                code = _call_openai_compatible_api(prov, url, model, system_prompt, user_msg, timeout=timeout)
                if code:
                    return code, f"tier1_{prov}"
            except Exception:
                continue

    return None


def call_tier2_local_llm(
    user_prompt: str,
    best_skeleton: Dict[str, Any],
    existing_code: str = "",
) -> Optional[Tuple[str, str]]:
    """
    Tầng 2: Local LLM (Ollama hoặc llama.cpp server).
    Sử dụng kỹ thuật neo chặt vào Phôi Vàng gần nhất để model nhỏ 1.5B/3B sinh code trong 2-4s.
    """
    server_info = is_local_server_alive()
    if not server_info:
        return None

    kind, url = server_info
    timeout = float(CONFIG.get("local_timeout", 4.5))
    compact_prompt = (
        f"{SIMPLEAI_STRICT_RULES}\n\n"
        f"PHOI VANG GOC:\n```python\n{best_skeleton['code']}\n```\n\n"
        f"DE BAI MOI:\n{user_prompt}\n"
    )
    if existing_code.strip():
        compact_prompt += f"\nCODE KHUNG:\n```python\n{existing_code}\n```\n"
    compact_prompt += "\nHay chinh sua so lieu/ham trong PHOI VANG GOC de giai dung DE BAI MOI. Chi tra ve code Python:"

    try:
        if kind == "ollama":
            payload = {
                "model": CONFIG.get("local_model", "qwen2.5-coder:1.5b"),
                "prompt": compact_prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            code = extract_python_code(body.get("response", ""))
            if code:
                return code, "tier2_ollama"
        else:
            payload = {
                "prompt": compact_prompt,
                "temperature": 0.1,
                "n_predict": 2048,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            code = extract_python_code(body.get("content", ""))
            if code:
                return code, "tier2_llamacpp"
    except Exception:
        pass
    return None


def call_tier3_offline_rag(parsed: ParsedInput) -> Tuple[str, str, Dict[str, Any]]:
    """
    Tầng 3: 100% Offline BM25 RAG + Parameter Injector (< 0.01s).
    Đảm bảo bất tử trong mọi hoàn cảnh cắt mạng / không có API key.
    """
    if parsed.target_skeleton_id and parsed.target_skeleton_id in ALL_SKELETONS:
        best_sk = ALL_SKELETONS[parsed.target_skeleton_id]
    else:
        search_q = parsed.prompt_text.strip()
        if not search_q and parsed.existing_code:
            search_q = parsed.existing_code.strip()
        candidates = RETRIEVER.retrieve(
            search_q,
            top_k=1,
            category_filter=parsed.category,
        )
        if not candidates:
            candidates = RETRIEVER.retrieve(search_q, top_k=1)
        best_sk = candidates[0]

    prompt_for_customizer = parsed.prompt_text.strip() or parsed.raw_input
    customized_code = customize_skeleton_with_prompt(
        skeleton_id=best_sk["id"],
        code=best_sk["code"],
        raw_prompt=prompt_for_customizer,
        dsl_params=parsed.dsl_params,
    )
    return customized_code, f"tier3_offline({best_sk['id']})", best_sk


def route_and_generate(
    parsed: ParsedInput,
    prefer_offline_only: bool = False,
    error_traceback: str = "",
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Điều phối sinh code qua 3 tầng:
    - Nếu `prefer_offline_only=True` (Alt+1 hoặc mode DSL): trả kết quả tức thì từ Tầng 3 (< 0.01s).
    - Nếu `prefer_offline_only=False` (Alt+2 / Alt+3): thử Tầng 1 (Cloud) -> Tầng 2 (Local) -> Tầng 3 (Offline RAG).
    Trả về `(code, source_tier, fallback_skeleton)`.
    """
    search_q = parsed.prompt_text.strip() or parsed.existing_code.strip()
    top_skeletons = RETRIEVER.retrieve(search_q, top_k=2, category_filter=parsed.category)
    if not top_skeletons:
        top_skeletons = RETRIEVER.retrieve(search_q, top_k=2)

    offline_code, offline_tag, best_sk = call_tier3_offline_rag(parsed)

    if prefer_offline_only or parsed.mode == "dsl":
        return offline_code, offline_tag, best_sk

    # Tang 1: Cloud LLM voi Context Injection
    sys_prompt, usr_msg = build_context_injected_prompt(
        user_prompt=parsed.prompt_text,
        top_skeletons=top_skeletons,
        existing_code=parsed.existing_code,
        error_traceback=error_traceback,
    )
    t1_res = call_tier1_cloud_llm(sys_prompt, usr_msg)
    if t1_res is not None:
        return t1_res[0], t1_res[1], best_sk

    # Tang 2: Local LLM
    t2_res = call_tier2_local_llm(parsed.prompt_text, best_sk, parsed.existing_code)
    if t2_res is not None:
        return t2_res[0], t2_res[1], best_sk

    # Tang 3: Pure Offline RAG + Parameter Injector
    return offline_code, offline_tag, best_sk
