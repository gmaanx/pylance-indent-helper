# -*- coding: utf-8 -*-
"""
Read-only, strictly bounded workspace & notebook context collector.
Helps Offline/Cloud/Ollama understand sibling data files (.json, .txt, .csv)
and helper Python modules (.py) referenced by exam exercises, as well as
teacher-provided starter templates (# TODO / pass / NotImplementedError).
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path
from typing import List, Optional

_DATA_EXTS = {".txt", ".json", ".csv", ".tsv"}
_IGNORE_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", "dist", "build"}
_MAX_FILE_READ_BYTES = 16 * 1024
_MAX_PREVIEW_CHARS = 1200
_MAX_TOTAL_CONTEXT_CHARS = 4500


def is_starter_template(code: str) -> bool:
    """Return True when existing code looks like an unfinished exam template (# TODO / pass / NotImplementedError)."""
    if not code or not code.strip():
        return False
    if re.search(r"#\s*(?:TODO|FIXME|YOUR CODE HERE|VIET CODE|DIEN CODE|CAU\s+\d+)", code, re.IGNORECASE):
        return True
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return False

    has_stub = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                return True
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == "NotImplementedError":
                return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = [
                stmt for stmt in node.body
                if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))
            ]
            if len(body) == 1 and (
                isinstance(body[0], ast.Pass)
                or (isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and body[0].value.value is Ellipsis)
            ):
                has_stub = True
    return has_stub


def _summarize_json(raw_text: str) -> str:
    try:
        data = json.loads(raw_text)
    except (ValueError, RecursionError):
        return raw_text[:_MAX_PREVIEW_CHARS]
    if isinstance(data, dict):
        preview = {}
        for idx, (k, v) in enumerate(data.items()):
            if idx >= 6:
                break
            if isinstance(v, list):
                preview[k] = v[:3]
            elif isinstance(v, dict):
                preview[k] = dict(list(v.items())[:4])
            else:
                preview[k] = v
        return json.dumps(preview, ensure_ascii=False)[:_MAX_PREVIEW_CHARS]
    if isinstance(data, list):
        return json.dumps(data[:4], ensure_ascii=False)[:_MAX_PREVIEW_CHARS]
    return raw_text[:_MAX_PREVIEW_CHARS]


def _summarize_python_module(path: Path, raw_text: str) -> str:
    try:
        tree = ast.parse(raw_text)
    except (SyntaxError, ValueError, RecursionError):
        return ""
    items: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            methods = []
            for m in node.body:
                if isinstance(m, ast.FunctionDef) and (m.name == "__init__" or not m.name.startswith("_")):
                    args = [a.arg for a in m.args.args]
                    methods.append(f"{m.name}({', '.join(args)})")
            items.append(f"class {node.name}: {', '.join(methods[:8])}")
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            args = [a.arg for a in node.args.args]
            items.append(f"def {node.name}({', '.join(args)})")
    return "; ".join(items)[:_MAX_PREVIEW_CHARS]


def collect_workspace_context(
    raw_text: str,
    file_path: Optional[str] = None,
    notebook_context: Optional[str] = None,
) -> str:
    """
    Build a concise, read-only summary of preceding notebook cells and relevant
    sibling data/Python files in the same directory as `file_path`.
    """
    sections: List[str] = []

    if notebook_context and notebook_context.strip():
        nb_trimmed = notebook_context.strip()[-2200:]
        sections.append(f"Ngữ cảnh các ô trước trong Notebook (.ipynb):\n{nb_trimmed}")

    if not file_path or not isinstance(file_path, str):
        return "\n\n".join(sections)

    try:
        current = Path(file_path).resolve()
    except OSError:
        return "\n\n".join(sections)
    parent = current.parent
    if not parent.is_dir():
        return "\n\n".join(sections)

    lowered_text = (raw_text or "").lower()
    candidates: List[tuple[int, Path]] = []
    try:
        entries = sorted(parent.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        entries = []

    for entry in entries[:40]:
        if entry.name.startswith(".") or entry.name in _IGNORE_DIRS:
            continue
        try:
            if not entry.is_file() or entry.resolve() == current:
                continue
            size = entry.stat().st_size
        except OSError:
            continue
        if size == 0 or size > 512 * 1024:
            continue
        ext = entry.suffix.lower()
        if ext not in _DATA_EXTS and ext != ".py":
            continue
        mentioned = entry.name.lower() in lowered_text or entry.stem.lower() in lowered_text
        # Only include unmentioned data files if small; only include sibling .py if mentioned/imported.
        if ext == ".py" and not mentioned:
            continue
        if ext in _DATA_EXTS and not mentioned and size > 32 * 1024:
            continue
        priority = 0 if mentioned else 1
        candidates.append((priority, entry))

    candidates.sort(key=lambda item: (item[0], item[1].name.lower()))
    file_summaries: List[str] = []
    used_chars = sum(len(s) for s in sections)

    for _, entry in candidates[:5]:
        if used_chars >= _MAX_TOTAL_CONTEXT_CHARS:
            break
        try:
            with entry.open("rb") as fh:
                chunk = fh.read(_MAX_FILE_READ_BYTES).decode("utf-8", errors="replace")
        except OSError:
            continue
        ext = entry.suffix.lower()
        if ext == ".json":
            summary = f"- File `{entry.name}` (JSON mẫu): {_summarize_json(chunk)}"
        elif ext == ".py":
            mod_sig = _summarize_python_module(entry, chunk)
            if not mod_sig:
                continue
            summary = f"- Module cùng thư mục `{entry.name}`: {mod_sig}"
        else:
            lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()][:10]
            preview = " | ".join(lines)[:_MAX_PREVIEW_CHARS]
            summary = f"- File dữ liệu `{entry.name}` (các dòng đầu): {preview}"

        file_summaries.append(summary)
        used_chars += len(summary)

    if file_summaries:
        sections.append("Các file có sẵn cùng thư mục bài làm:\n" + "\n".join(file_summaries))

    return "\n\n".join(sections)
