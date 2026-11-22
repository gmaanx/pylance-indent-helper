"""Solve supported problems and label the checks applied to each result."""

import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .brain_router import (
    build_context_injected_prompt,
    call_tier1_cloud_llm,
    call_tier2_local_llm,
)
from .cloud_review import review_cloud_draft, syntax_error as _syntax_error
from .dual_parser import parse_user_input
from .golden_skeletons import ALL_SKELETONS, customize_skeleton_with_prompt
from .offline_solver import OfflineProblemError, solve_offline
from .shadow_runner_healer import static_auto_heal_preserve_style


_SUGGEST_MODEL = "Có thể thử Alt+5 (Ollama cục bộ) hoặc Alt+3 (Cloud) để lấy bản nháp."


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
) -> EngineResponse:
    """Keep the legacy verify flag for callers. Candidate code is never executed."""
    started = time.perf_counter()
    diagnostics = []

    def finish(status, tier, code="", summary="", error="", notes=()):
        elapsed = time.perf_counter() - started
        if code:
            header_labels = {
                "instant": "Alt+1",
                "full": "Alt+2",
                "ghost": "Alt+3",
                "self_fix": "Alt+4",
            }
            labels = {
                "verified": "Đã giải theo đặc tả",
                "syntax_checked": "Đã kiểm tra cú pháp",
                "reference": "Mẫu tham khảo",
            }
            if tier.startswith("tier1_"):
                action_label = "Cloud"
            elif tier.startswith("tier2_"):
                action_label = "AI cục bộ"
            else:
                action_label = header_labels.get(action_mode, "Python Helper")
            code = f"# [{action_label} | {tier} | {labels[status]}]\n{code.rstrip()}\n"
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

    if not raw_text.strip():
        return finish("needs_input", "empty", error="Nhập yêu cầu hoặc mã Python để bắt đầu.")
    if len(raw_text) > 100_000:
        return finish("limit", "input_limit", error="Yêu cầu vượt giới hạn 100.000 ký tự.")

    parsed = parse_user_input(raw_text, force_mode="self_fix" if action_mode == "self_fix" else None)
    if parsed.mode == "cfg":
        return finish("unsupported", "config", error="Nhập cấu hình và API key trong công cụ, tránh đặt trong mã nguồn.")
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
    if parsed.mode == "self_fix" and not syntax_problem and not allow_cloud:
        suggested = static_auto_heal_preserve_style(parsed.existing_code)
        if suggested != parsed.existing_code and not _syntax_error(suggested):
            return finish(
                "syntax_checked", "static_healer", suggested,
                notes=("Bản đề xuất sửa lỗi SimpleAI đã qua kiểm tra cú pháp.",),
            )

    if action_mode != "instant" and parsed.mode not in ("structured", "dsl"):
        candidate = None
        if allow_cloud:
            system_prompt, user_msg = build_context_injected_prompt(
                raw_text, [], error_traceback=syntax_problem,
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
                raw_text, None, diagnostics=diagnostics,
            )
        if candidate is not None:
            code, tier = candidate
            error = _syntax_error(code)
            if error:
                return finish("invalid", tier, error=error)
            return finish(
                "syntax_checked", tier, code,
                notes=("Mã đề xuất đã qua kiểm tra cú pháp. Hãy đối chiếu với dữ liệu và ràng buộc.",),
            )

    if offline_error is not None:
        return finish(offline_error.status, "offline_solver", error=str(offline_error), notes=(_SUGGEST_MODEL,))
    if parsed.mode == "self_fix":
        error = syntax_problem or "Mã này qua kiểm tra cú pháp. Cần lỗi cụ thể hoặc bộ test để tìm vấn đề logic."
        return finish("invalid" if syntax_problem else "unsupported", "self_fix", error=error)
    sample = _explicit_reference(parsed)
    if sample:
        code = customize_skeleton_with_prompt(sample["id"], sample["code"], parsed.prompt_text, parsed.dsl_params)
        return finish(
            "reference", f"tier3_offline({sample['id']})", code,
            notes=("Mẫu tham khảo, có thể còn dữ liệu hoặc ràng buộc mặc định. Hãy kiểm tra trước khi áp dụng.",),
        )
    return finish(
        "unsupported", "no_match",
        error="Offline chưa nhận diện đủ yêu cầu. Hãy nêu dữ liệu, ràng buộc và kết quả cần tìm hoặc dùng đặc tả @solve.",
        notes=(_SUGGEST_MODEL,),
    )
