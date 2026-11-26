"""Solve supported problems, inject Golden Skeletons/workspace context, and self-heal runtime errors."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .brain_router import (
    build_context_injected_prompt,
    call_tier1_cloud_llm,
    call_tier2_local_llm,
    select_relevant_skeletons,
)
from .cloud_review import review_cloud_draft, syntax_error as _syntax_error
from .dual_parser import parse_user_input
from .golden_skeletons import ALL_SKELETONS, customize_skeleton_with_prompt
from .offline_solver import OfflineProblemError, solve_offline
from .runnable_output import ensure_runnable_print
from .shadow_runner_healer import shadow_execute, static_auto_heal, static_auto_heal_preserve_style
from .workspace_context import collect_workspace_context, is_starter_template


_SUGGEST_MODEL = "Có thể dùng Alt+2 (Auto-Pilot), Alt+5 (Ollama) hoặc Alt+3 (Cloud)."


@dataclass
class EngineResponse:
    code: str
    verified_ok: bool
    tier_used: str
    elapsed_sec: float
    stdout_preview: str = ""
    error_detail: str = ""
    validation_status: str = "unsupported"
    diagnostics: Tuple[str, ...] = ()


def _explicit_reference(parsed):
    if parsed.mode != "dsl":
        return None
    sample = ALL_SKELETONS.get(parsed.target_skeleton_id)
    if sample is None or sample.get("category") != parsed.category:
        return None
    if "\n" in parsed.prompt_text or set(parsed.dsl_params) - {"bai"}:
        return None
    tokens = parsed.prompt_text.split()
    if len(tokens) != 2:
        return None
    return sample


def process_request(
    raw_text: str,
    action_mode: str = "full",
    verify_shadow: bool = True,
    *,
    allow_cloud: bool = False,
    allow_local: bool = False,
    allow_shadow_exec: bool = False,
    allow_rag_fallback: bool = False,
    file_path: Optional[str] = None,
    notebook_context: Optional[str] = None,
) -> EngineResponse:
    """Process a user request across Offline, Cloud, Ollama, and BM25 RAG tiers."""
    started = time.perf_counter()
    diagnostics = []
    working_dir: Optional[str] = None
    if file_path:
        try:
            parent = Path(file_path).resolve().parent
            if parent.is_dir():
                working_dir = str(parent)
        except OSError:
            working_dir = None

    def finish(status, tier, code="", summary="", error="", notes=()):
        elapsed = time.perf_counter() - started
        if code:
            code = f"{code.rstrip()}\n"
        return EngineResponse(
            code=code,
            verified_ok=status == "verified",
            tier_used=tier,
            elapsed_sec=elapsed,
            stdout_preview=summary,
            error_detail=error,
            validation_status=status,
            diagnostics=tuple(diagnostics) + tuple(notes),
        )

    def _prepare_candidate_code(code: str, *, editing_existing: bool = False) -> Tuple[str, list[str]]:
        local_notes: list[str] = []
        healed = static_auto_heal_preserve_style(code)
        if healed != code and not _syntax_error(healed):
            code = healed
        enhanced, has_output = ensure_runnable_print(
            code, raw_text, editing_existing=editing_existing,
        )
        if enhanced != code and not _syntax_error(enhanced):
            code = enhanced
            local_notes.append('Đã tự bổ sung khối if __name__ == "__main__" để in kết quả khi chạy.')
        elif not has_output and not editing_existing:
            local_notes.append("Mã đề xuất chưa có lệnh print khi chạy trực tiếp; hãy bổ sung lời gọi hàm nếu cần.")
        return code, local_notes

    def finish_model(
        candidate: Tuple[str, str],
        *,
        editing_existing: bool = False,
        prompt_for_repair: str = "",
        ws_context: str = "",
        skeletons_for_repair: list = None,
    ) -> EngineResponse:
        code, tier = candidate
        error = _syntax_error(code)
        if error:
            return finish("invalid", tier, error=error)

        code, prep_notes = _prepare_candidate_code(code, editing_existing=editing_existing)
        notes = ["Mã đề xuất đã qua kiểm tra cú pháp.", *prep_notes]

        if not allow_shadow_exec or not verify_shadow:
            return finish("syntax_checked", tier, code, notes=tuple(notes))

        # Closed-loop Shadow Run & Auto-Heal (up to 2 repair rounds on runtime Traceback/Timeout)
        run_res = shadow_execute(code, timeout=3.5, working_dir=working_dir)
        if not run_res.ok:
            aggressive = static_auto_heal(code)
            if aggressive != code and not _syntax_error(aggressive):
                retry_res = shadow_execute(aggressive, timeout=3.5, working_dir=working_dir)
                if retry_res.ok:
                    code, run_res = aggressive, retry_res

        repair_prompt = prompt_for_repair or raw_text
        skels = skeletons_for_repair or []
        best_skel = skels[0] if skels else None
        for _round in range(2):
            if run_res.ok:
                break
            tb_text = (run_res.stderr or run_res.stdout or "Lỗi khi chạy thử mã Python.")[-1800:]
            repaired_candidate = None
            if tier.startswith("tier1_") and allow_cloud:
                provider_only = tier[6:]
                sys_p, usr_m = build_context_injected_prompt(
                    repair_prompt, skels, existing_code=code,
                    error_traceback=tb_text, workspace_context=ws_context,
                )
                repaired_candidate = call_tier1_cloud_llm(
                    sys_p, usr_m, diagnostics=diagnostics, provider_id=provider_only, max_attempts=1,
                )
            elif allow_local:
                repaired_candidate = call_tier2_local_llm(
                    repair_prompt, best_skel, existing_code=code,
                    error_traceback=tb_text, workspace_context=ws_context, diagnostics=diagnostics,
                )
            if repaired_candidate is None:
                break
            new_code, new_tier = repaired_candidate
            if _syntax_error(new_code):
                break
            new_code, _ = _prepare_candidate_code(new_code, editing_existing=editing_existing)
            new_run = shadow_execute(new_code, timeout=3.5, working_dir=working_dir)
            code, tier, run_res = new_code, new_tier, new_run

        if run_res.ok:
            return finish(
                "runtime_checked",
                tier,
                code,
                summary=run_res.summary,
                notes=(f"Đã chạy kiểm thử ngầm thành công ({run_res.elapsed_sec:.2f}s).",),
            )
        tb_short = (run_res.stderr.strip().splitlines()[-1] if run_res.stderr.strip() else "Lỗi runtime khi chạy thử.")
        return finish(
            "syntax_checked",
            tier,
            code,
            notes=(*notes, f"Lưu ý khi chạy thử: {tb_short[:160]}"),
        )

    if not raw_text.strip():
        return finish("needs_input", "empty", error="Nhập yêu cầu hoặc mã Python để bắt đầu.")
    if len(raw_text) > 100_000:
        return finish("limit", "input_limit", error="Yêu cầu vượt giới hạn 100.000 ký tự.")

    parsed = parse_user_input(raw_text, force_mode="self_fix" if action_mode == "self_fix" else None)
    if parsed.mode == "cfg":
        return finish("unsupported", "config", error="Nhập cấu hình và API key qua nhap_api_key.bat, tránh đặt trong mã nguồn.")

    ws_context = collect_workspace_context(raw_text, file_path=file_path, notebook_context=notebook_context)
    query_for_rag = parsed.prompt_text or raw_text
    top_skeletons = select_relevant_skeletons(query_for_rag, top_k=2)
    best_skeleton = top_skeletons[0] if top_skeletons else None
    completing_template = (
        bool(parsed.existing_code)
        and action_mode != "self_fix"
        and parsed.mode == "natural"
        and is_starter_template(parsed.existing_code)
    )
    editing_existing = bool(parsed.existing_code) and not completing_template

    if action_mode == "local":
        if not allow_local:
            return finish("unsupported", "tier2_ollama", error="Yêu cầu chưa bật Ollama cục bộ.")
        prompt_text = parsed.prompt_text or raw_text if completing_template else raw_text
        existing_arg = parsed.existing_code if completing_template else ""
        candidate = call_tier2_local_llm(
            prompt_text, best_skeleton, existing_arg,
            workspace_context=ws_context, diagnostics=diagnostics,
        )
        if candidate is None:
            error = diagnostics[-1] if diagnostics else "Ollama chưa tạo được đề xuất."
            return finish("unsupported", "tier2_ollama", error=error)
        return finish_model(
            candidate,
            editing_existing=editing_existing,
            prompt_for_repair=prompt_text,
            ws_context=ws_context,
            skeletons_for_repair=top_skeletons,
        )

    if parsed.mode in ("structured", "dsl") and parsed.existing_code:
        return finish(
            "invalid", "offline_solver",
            error="Chọn riêng đặc tả bài toán để chạy. Đặc tả này còn kèm nội dung ngoài yêu cầu.",
        )

    offline_error: Optional[OfflineProblemError] = None
    if not parsed.existing_code:
        try:
            solution = solve_offline(parsed.prompt_text, parsed.target_skeleton_id)
        except OfflineProblemError as exc:
            if parsed.mode in ("structured", "dsl") or exc.status in ("invalid", "limit"):
                return finish(exc.status, "offline_solver", error=str(exc))
            offline_error = exc
        else:
            if solution is not None:
                return finish(
                    solution.validation_status, f"offline_{solution.problem_type}", solution.code,
                    summary=solution.summary, notes=(solution.summary, *solution.diagnostics),
                )

    syntax_problem = _syntax_error(parsed.existing_code) if parsed.mode == "self_fix" else ""
    runtime_problem = ""
    if parsed.mode == "self_fix" and not syntax_problem:
        suggested = static_auto_heal_preserve_style(parsed.existing_code)
        if suggested != parsed.existing_code and not _syntax_error(suggested):
            if allow_shadow_exec and verify_shadow:
                check_run = shadow_execute(suggested, timeout=3.5, working_dir=working_dir)
                if check_run.ok:
                    return finish(
                        "runtime_checked", "static_healer", suggested,
                        summary=check_run.summary,
                        notes=("Đã tự động sửa lỗi SimpleAI và kiểm thử chạy thành công.",),
                    )
                runtime_problem = (check_run.stderr or check_run.stdout)[-1800:]
            elif not allow_cloud:
                return finish(
                    "syntax_checked", "static_healer", suggested,
                    notes=("Bản đề xuất sửa lỗi SimpleAI đã qua kiểm tra cú pháp.",),
                )
        elif allow_shadow_exec and verify_shadow:
            probe_run = shadow_execute(parsed.existing_code, timeout=3.5, working_dir=working_dir)
            if not probe_run.ok:
                runtime_problem = (probe_run.stderr or probe_run.stdout or "Lỗi khi thực thi mã.")[-1800:]

    detected_issue = syntax_problem or runtime_problem

    if action_mode != "instant" and parsed.mode not in ("structured", "dsl"):
        if parsed.mode != "self_fix" or detected_issue or parsed.prompt_text:
            candidate = None
            model_prompt = (
                (parsed.prompt_text or "Sửa lỗi cú pháp và lỗi chạy trong đoạn mã Python dưới đây, giữ đúng yêu cầu bài toán.")
                if parsed.mode == "self_fix"
                else ((parsed.prompt_text or "Hoàn thiện khung mã Python dưới đây.") if completing_template else raw_text)
            )
            model_existing = parsed.existing_code if (parsed.mode == "self_fix" or completing_template) else ""
            if allow_cloud:
                system_prompt, user_msg = build_context_injected_prompt(
                    model_prompt, top_skeletons,
                    existing_code=model_existing,
                    error_traceback=detected_issue,
                    workspace_context=ws_context,
                )
                candidate = call_tier1_cloud_llm(system_prompt, user_msg, diagnostics=diagnostics, max_attempts=1)
                if candidate is not None:
                    draft, tier = candidate
                    reviewed = review_cloud_draft(raw_text, draft, tier, diagnostics)
                    if reviewed is None:
                        return finish("invalid", tier, error="Kết quả Cloud mâu thuẫn với ca đối chiếu offline.")
                    candidate = (reviewed, tier)
            if candidate is None and allow_local:
                candidate = call_tier2_local_llm(
                    model_prompt, best_skeleton, model_existing,
                    error_traceback=detected_issue,
                    workspace_context=ws_context,
                    diagnostics=diagnostics,
                )
            if candidate is not None:
                return finish_model(
                    candidate,
                    editing_existing=editing_existing,
                    prompt_for_repair=model_prompt,
                    ws_context=ws_context,
                    skeletons_for_repair=top_skeletons,
                )

    if offline_error is not None and not allow_rag_fallback:
        return finish(offline_error.status, "offline_solver", error=str(offline_error), notes=(_SUGGEST_MODEL,))
    if parsed.mode == "self_fix":
        error = detected_issue or "Mã này qua kiểm tra cú pháp. Cần lỗi cụ thể hoặc bật Ollama/Cloud để phân tích logic."
        return finish("invalid" if detected_issue else "unsupported", "self_fix", error=error)
    sample = _explicit_reference(parsed)
    if sample is None and allow_rag_fallback and best_skeleton is not None:
        sample = best_skeleton
    if sample:
        code = customize_skeleton_with_prompt(sample["id"], sample["code"], parsed.prompt_text, parsed.dsl_params)
        summary = ""
        if allow_shadow_exec and verify_shadow:
            rag_run = shadow_execute(code, timeout=3.5, working_dir=working_dir)
            if rag_run.ok:
                summary = rag_run.summary
        return finish(
            "reference", f"tier3_offline({sample['id']})", code, summary=summary,
            notes=("Mẫu tham khảo gần nhất đã khớp tham số cơ bản. Hãy đối chiếu với đề bài.",),
        )
    if offline_error is not None:
        return finish(offline_error.status, "offline_solver", error=str(offline_error), notes=(_SUGGEST_MODEL,))
    return finish(
        "unsupported", "no_match",
        error="Offline chưa nhận diện đủ yêu cầu. Hãy dùng Alt+2 (Auto-Pilot) hoặc ghi rõ dữ liệu đầu vào.",
        notes=(_SUGGEST_MODEL,),
    )
