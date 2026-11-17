# -*- coding: utf-8 -*-
"""
Bo Dieu Phoi Tong The (engine_pipeline.py).
Ket noi Dual-Parser -> Brain Router (3 Tang) -> Static Auto-Healer -> Shadow Execution & Self-Fix.
"""

import time
from dataclasses import dataclass
from typing import Optional

from .brain_router import (
    build_context_injected_prompt,
    call_tier1_cloud_llm,
    call_tier2_local_llm,
    call_tier3_offline_rag,
    route_and_generate,
)
from .config_manager import CONFIG
from .dual_parser import parse_user_input
from .golden_skeletons import RETRIEVER
from .shadow_runner_healer import (
    ShadowRunResult,
    shadow_execute,
    static_auto_heal,
    static_auto_heal_preserve_style,
)


@dataclass
class EngineResponse:
    code: str
    verified_ok: bool
    tier_used: str
    elapsed_sec: float
    stdout_preview: str = ""
    error_detail: str = ""


def _finalize_code_output(
    code: str,
    run_res: Optional[ShadowRunResult],
    action_mode: str = "full",
    tier_used: str = "",
    total_elapsed: float = 0.0,
) -> str:
    # Loai bo dòng # [Alt+...] cu neu co de khong bi lap
    lines = [
        ln for ln in code.strip().splitlines()
        if not ln.strip().lower().startswith("# [alt+")
    ]
    body = "\n".join(lines).rstrip() + "\n"

    mode_labels = {
        "instant": "Alt+1 OK | Giai nhanh Offline",
        "full": "Alt+2 OK | AI 3 Tang + Kiem dinh",
        "ghost": "Alt+3 OK | Che do Go Tu Dong (Bam Esc de dung)",
        "self_fix": "Alt+4 OK | Tu dong sua loi & Kiem dinh",
    }
    label = mode_labels.get(action_mode, "Alt OK")
    status_tag = "Verified" if (run_res is None or run_res.ok) else "Unverified"
    header = f"# [{label} | {tier_used} | {status_tag} {total_elapsed:.2f}s]\n"

    clean_code = header + body
    if CONFIG.get("append_verified_comment", True) and run_res and run_res.ok:
        fmt = CONFIG.get("verified_comment_format", "# kq: {summary} ({elapsed})")
        tag = fmt.format(summary=run_res.summary, elapsed=f"{run_res.elapsed_sec:.2f}s")
        if not body.rstrip().endswith(tag):
            clean_code += f"{tag}\n"
    return clean_code


def process_request(
    raw_text: str,
    action_mode: str = "full",
    verify_shadow: bool = True,
) -> EngineResponse:
    """
    Xử lý yêu cầu từ VS Code Extension hoặc Stealth Daemon:
    - `action_mode == "instant"` (Alt+1): Chỉ dùng Tầng 3 (Offline BM25 RAG + Parameter Injector + DSL) < 0.05s.
    - `action_mode == "full"` (Alt+2) / `"ghost"` (Alt+3): 3 Tầng Não + Auto-Healer + Shadow Verify (tối đa 2 vòng tự sửa).
    - `action_mode == "self_fix"` (Alt+4): Tự động bắt Traceback của đoạn code đang lỗi và sửa cho đến khi chạy OK.
    """
    t0 = time.perf_counter()
    force_mode = "self_fix" if action_mode == "self_fix" else None
    parsed = parse_user_input(raw_text, force_mode=force_mode)

    if not parsed.raw_input:
        return EngineResponse(
            code="",
            verified_ok=False,
            tier_used="empty",
            elapsed_sec=0.0,
            error_detail="Empty input",
        )

    # 1. Xu ly lenh cau hinh ngam: # @cfg gemini:AIza...
    if parsed.mode == "cfg":
        msg = CONFIG.apply_inline_cfg(parsed.dsl_params)
        return EngineResponse(
            code=msg + "\n",
            verified_ok=True,
            tier_used="config",
            elapsed_sec=time.perf_counter() - t0,
            stdout_preview=msg,
        )

    shadow_timeout = float(CONFIG.get("shadow_timeout", 2.5))

    # 2. Che do Alt + 4: Silent Self-Fix Mode (Sua code Python dang bi loi hoac giai theo """ yeu cau """)
    if parsed.mode == "self_fix":
        broken_code = parsed.existing_code or parsed.raw_input
        # Buoc 2A: Thu sua tinh bang Static AST Auto-Healer truoc
        healed_code = static_auto_heal(broken_code)
        run1 = shadow_execute(healed_code, timeout=shadow_timeout)
        if run1.ok:
            el = time.perf_counter() - t0
            return EngineResponse(
                code=_finalize_code_output(
                    healed_code, run1, action_mode="self_fix", tier_used="static_healer", total_elapsed=el
                ),
                verified_ok=True,
                tier_used="static_healer",
                elapsed_sec=el,
                stdout_preview=run1.summary,
            )

        # Buoc 2B: Goi LLM Tang 1 / Tang 2 kem Traceback va 2 Phoi Vang gan nhat (toi da 2 vong)
        search_query = f"{parsed.prompt_text}\n{broken_code}".strip()
        top_sks = RETRIEVER.retrieve(search_query, top_k=2)
        current_code = healed_code
        current_err = run1.stderr or run1.stdout
        fix_prompt = (
            parsed.prompt_text
            if parsed.prompt_text
            else "Hay sua triet de loi trong doan code Python duoi day ma giu nguyen y dinh bai toan va phong cach ten bien."
        )
        for attempt in range(2):
            sys_p, usr_m = build_context_injected_prompt(
                user_prompt=fix_prompt,
                top_skeletons=top_sks,
                existing_code=current_code,
                error_traceback=current_err,
            )
            llm_res = call_tier1_cloud_llm(sys_p, usr_m)
            if llm_res is None and top_sks:
                llm_res = call_tier2_local_llm(
                    f"{fix_prompt}\nSua loi Traceback:\n{current_err}", top_sks[0], current_code
                )
            if llm_res is None:
                break
            candidate = static_auto_heal(llm_res[0])
            run_retry = shadow_execute(candidate, timeout=shadow_timeout)
            if run_retry.ok:
                el = time.perf_counter() - t0
                t_used = f"{llm_res[1]}_fix_{attempt+1}"
                return EngineResponse(
                    code=_finalize_code_output(
                        candidate, run_retry, action_mode="self_fix", tier_used=t_used, total_elapsed=el
                    ),
                    verified_ok=True,
                    tier_used=t_used,
                    elapsed_sec=el,
                    stdout_preview=run_retry.summary,
                )
            current_code = candidate
            current_err = run_retry.stderr or run_retry.stdout

        # Neu co """ yeu cau """ hoac # yeu cau ma code cu hong nang, lay Phoi Vang Tang 3 thay the
        if parsed.prompt_text:
            fb_code, fb_tier, _ = call_tier3_offline_rag(parsed)
            fb_run = shadow_execute(fb_code, timeout=shadow_timeout)
            if fb_run.ok:
                el = time.perf_counter() - t0
                return EngineResponse(
                    code=_finalize_code_output(
                        fb_code, fb_run, action_mode="self_fix", tier_used=f"rag_{fb_tier}", total_elapsed=el
                    ),
                    verified_ok=True,
                    tier_used=f"rag_{fb_tier}",
                    elapsed_sec=el,
                    stdout_preview=fb_run.summary,
                )

        el = time.perf_counter() - t0
        return EngineResponse(
            code=_finalize_code_output(
                current_code, None, action_mode="self_fix", tier_used="self_fix_unverified", total_elapsed=el
            ),
            verified_ok=False,
            tier_used="self_fix_unverified",
            elapsed_sec=el,
            error_detail=current_err[:300],
        )

    # 3. Che do Alt + 1: Instant Template / Offline RAG / DSL (< 0.05s)
    if action_mode == "instant":
        code, tier, _ = route_and_generate(parsed, prefer_offline_only=True)
        code = static_auto_heal_preserve_style(code)
        if verify_shadow:
            run_inst = shadow_execute(code, timeout=shadow_timeout)
            el = time.perf_counter() - t0
            return EngineResponse(
                code=_finalize_code_output(
                    code, run_inst, action_mode="instant", tier_used=tier, total_elapsed=el
                ),
                verified_ok=run_inst.ok,
                tier_used=tier,
                elapsed_sec=el,
                stdout_preview=run_inst.summary,
                error_detail="" if run_inst.ok else run_inst.stderr[:200],
            )
        el = time.perf_counter() - t0
        return EngineResponse(
            code=_finalize_code_output(
                code, None, action_mode="instant", tier_used=tier, total_elapsed=el
            ),
            verified_ok=True,
            tier_used=tier,
            elapsed_sec=el,
        )

    # 4. Che do Alt + 2 ("full") & Alt + 3 ("ghost") & Alt + 4 khi chi co """ yeu cau """:
    candidate_code, tier_used, _ = route_and_generate(parsed, prefer_offline_only=False)
    candidate_code = static_auto_heal_preserve_style(candidate_code)
    run_res = shadow_execute(candidate_code, timeout=shadow_timeout)

    if run_res.ok:
        el = time.perf_counter() - t0
        return EngineResponse(
            code=_finalize_code_output(
                candidate_code, run_res, action_mode=action_mode, tier_used=tier_used, total_elapsed=el
            ),
            verified_ok=True,
            tier_used=tier_used,
            elapsed_sec=el,
            stdout_preview=run_res.summary,
        )

    # Neu chay nhap bi loi, thu ep Static Auto-Heal manh (co boc _to_hashable va graph_search=True)
    forced_healed = static_auto_heal(candidate_code)
    if forced_healed != candidate_code:
        run_forced = shadow_execute(forced_healed, timeout=shadow_timeout)
        if run_forced.ok:
            el = time.perf_counter() - t0
            t_used = f"{tier_used}+ast_healed"
            return EngineResponse(
                code=_finalize_code_output(
                    forced_healed, run_forced, action_mode=action_mode, tier_used=t_used, total_elapsed=el
                ),
                verified_ok=True,
                tier_used=t_used,
                elapsed_sec=el,
                stdout_preview=run_forced.summary,
            )
        candidate_code = forced_healed
        run_res = run_forced

    # Vong lap tu sua loi voi LLM (toi da 2 lan neu dang dung Tang 1/Tang 2)
    last_err = run_res.stderr or run_res.stdout
    if tier_used.startswith(("tier1_", "tier2_")):
        for retry_idx in range(2):
            retry_code, retry_tier, _ = route_and_generate(
                parsed,
                prefer_offline_only=False,
                error_traceback=last_err,
            )
            retry_code = static_auto_heal(retry_code)
            retry_run = shadow_execute(retry_code, timeout=shadow_timeout)
            if retry_run.ok:
                el = time.perf_counter() - t0
                t_used = f"{retry_tier}_retry{retry_idx+1}"
                return EngineResponse(
                    code=_finalize_code_output(
                        retry_code, retry_run, action_mode=action_mode, tier_used=t_used, total_elapsed=el
                    ),
                    verified_ok=True,
                    tier_used=t_used,
                    elapsed_sec=el,
                    stdout_preview=retry_run.summary,
                )
            last_err = retry_run.stderr or retry_run.stdout

    # Chot chan cuoi cung (Fail-safe): Luon roi ve Phoi Vang Tang 3 da kiem dinh 100%
    fallback_code, fallback_tier, _ = call_tier3_offline_rag(parsed)
    fb_run = shadow_execute(fallback_code, timeout=shadow_timeout)
    el = time.perf_counter() - t0
    t_used = f"fallback_{fallback_tier}"
    return EngineResponse(
        code=_finalize_code_output(
            fallback_code, fb_run, action_mode=action_mode, tier_used=t_used, total_elapsed=el
        ),
        verified_ok=fb_run.ok,
        tier_used=t_used,
        elapsed_sec=el,
        stdout_preview=fb_run.summary,
        error_detail="" if fb_run.ok else fb_run.stderr[:200],
    )
