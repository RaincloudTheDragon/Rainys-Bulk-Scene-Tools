"""
Agentic org-template merge for Capture (#18 smarter templates).

Prefer local llama-cli merge when runtime is ready; on missing runtime or
unparseable output, fall back to deterministic merge_org_templates (same
spirit as Apply / org LLM heuristic fallback). Never aborts for runtime.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any

from .org_runtime import org_runtime_ready, resolve_gguf_path, resolve_llama_cli
from .org_template_context import (
    compact_user_template,
    merge_org_templates,
)
from .outliner_org import TEMPLATE_VERSION, default_template, load_template

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _addon_package() -> str:
    """Addon root package name (utils → parent)."""
    pkg = __package__ or ""
    if pkg.endswith(".utils"):
        return pkg.rsplit(".", 1)[0]
    return pkg or "Rainys_Bulk_Scene_Tools"


def _worker_dir() -> str:
    addon_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon_root, "worker", "rbst_org_worker")


def template_merge_grammar_path() -> str:
    """GBNF constraining Capture merge output to a template-shaped object."""
    return os.path.join(_worker_dir(), "template_merge.gbnf")


def extract_json_object(text: str, *, require_keys: tuple[str, ...] = ("folders",)):
    """
    Pull first/best JSON object from llama-cli stdout (prompt + banner noise).

    Shared pattern with org LLM: scan for '{' and raw_decode.
    """
    text = text or ""
    decoder = json.JSONDecoder()
    best = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if require_keys and not all(k in obj for k in require_keys):
            # Prefer objects that look like templates; keep last dict otherwise.
            if best is None and "folders" not in require_keys:
                best = obj
            continue
        best = obj
    return best


def sanitize_merged_template(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate LLM merge output; None if unusable."""
    if not isinstance(data, dict):
        return None
    folders = data.get("folders")
    if not isinstance(folders, list) or not folders:
        return None
    clean_folders: list[list[str]] = []
    for path in folders:
        if isinstance(path, list) and path:
            clean_folders.append([str(p) for p in path])
    if not clean_folders:
        return None

    examples: list[dict[str, Any]] = []
    for ex in data.get("placement_examples") or []:
        if not isinstance(ex, dict) or not ex.get("name"):
            continue
        path = ex.get("path")
        if not isinstance(path, list) or not path:
            continue
        examples.append(
            {
                "name": str(ex["name"]),
                "path": [str(p) for p in path],
                "signals": [str(s) for s in (ex.get("signals") or []) if s][:8],
            }
        )
        if len(examples) >= 80:
            break

    aliases = data.get("rename_aliases")
    if not isinstance(aliases, dict) or not aliases:
        aliases = dict(default_template().get("rename_aliases") or {})
    else:
        aliases = {str(k): str(v) for k, v in aliases.items()}

    type_placement = data.get("type_placement")
    if not isinstance(type_placement, dict) or not type_placement:
        type_placement = dict(default_template().get("type_placement") or {})
    else:
        type_placement = {
            str(k): list(v) if isinstance(v, list) else v
            for k, v in type_placement.items()
        }

    def _paths(key: str) -> list[list[str]]:
        out: list[list[str]] = []
        for path in data.get(key) or []:
            if isinstance(path, list) and path:
                out.append([str(p) for p in path])
        return out

    return {
        "version": int(data.get("version") or TEMPLATE_VERSION),
        "folders": clean_folders,
        "view_layer_exclude": _paths("view_layer_exclude")
        or list(default_template().get("view_layer_exclude") or []),
        "hide_viewport": _paths("hide_viewport")
        or list(default_template().get("hide_viewport") or []),
        "rename_aliases": aliases,
        "type_placement": type_placement,
        "placement_examples": examples,
    }


def _build_merge_prompt(old: dict[str, Any], new: dict[str, Any]) -> str:
    """Compact old+new → one merged template JSON (GBNF-shaped keys)."""
    old_c = compact_user_template(old)
    new_c = compact_user_template(new)
    # Folders from full templates matter more than compact alone.
    old_c["folders"] = list(old.get("folders") or old_c.get("folders") or [])
    new_c["folders"] = list(new.get("folders") or new_c.get("folders") or [])
    example = (
        '{"version":1,"folders":[["Env"],["Env","Dressing"],["Animation","Char"]],'
        '"view_layer_exclude":[["Env","ROOTS"]],'
        '"hide_viewport":[["Env","ROOTS"]],'
        '"placement_examples":[{"name":"HeroPack","path":["Animation","Char"],'
        '"signals":["armature","override"]}]}'
    )
    return (
        "Merge two org templates into ONE JSON object. Additive union only.\n"
        "Rules:\n"
        "- Union folders / view_layer_exclude / hide_viewport (no drops).\n"
        "- Union placement_examples by name+path; keep structural signals.\n"
        "- Do not invent project-specific name lists; keep signals short.\n"
        "- Output keys: version, folders, view_layer_exclude, hide_viewport, "
        "placement_examples. No markdown.\n"
        f"Example:\n{example}\n"
        f"old:\n{json.dumps(old_c, separators=(',', ':'))}\n"
        f"new:\n{json.dumps(new_c, separators=(',', ':'))}\n"
    )


def _run_llama_merge(
    old: dict[str, Any],
    new: dict[str, Any],
    *,
    cli: str,
    model: str,
    timeout: float,
) -> dict[str, Any] | None:
    """Blocking llama-cli merge; returns sanitized template or None."""
    prompt = _build_merge_prompt(old, new)
    gram = template_merge_grammar_path()
    prompt_path = None
    out_path = None
    err_path = None
    try:
        fd, prompt_path = tempfile.mkstemp(suffix=".merge.prompt.txt")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(prompt)
        out_fd, out_path = tempfile.mkstemp(suffix=".merge.out.txt")
        err_fd, err_path = tempfile.mkstemp(suffix=".merge.err.txt")
        out_h = os.fdopen(out_fd, "wb", buffering=0)
        err_h = os.fdopen(err_fd, "wb", buffering=0)
        cmd = [
            cli,
            "-m",
            model,
            "-no-cnv",
            "-st",
            "-n",
            "768",
            "--temp",
            "0.1",
            "-ngl",
            "99",
            "--no-display-prompt",
            "--log-disable",
            "-f",
            prompt_path,
        ]
        if os.path.isfile(gram):
            cmd.extend(["--grammar-file", gram])
        popen_kw: dict = {
            "cwd": os.path.dirname(cli) or None,
            "stdout": out_h,
            "stderr": err_h,
            "stdin": subprocess.DEVNULL,
        }
        if _CREATE_NO_WINDOW:
            popen_kw["creationflags"] = _CREATE_NO_WINDOW
        print(
            f"[RBST] capture merge: starting llama-cli "
            f"(timeout={timeout:.0f}s)"
        )
        proc = subprocess.Popen(cmd, **popen_kw)
        started = time.monotonic()
        while proc.poll() is None:
            if time.monotonic() - started > timeout:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
                print("[RBST] capture merge: llama-cli timed out")
                return None
            time.sleep(0.2)
        try:
            out_h.close()
        except Exception:
            pass
        try:
            err_h.close()
        except Exception:
            pass
        raw = ""
        try:
            with open(out_path, "r", encoding="utf-8", errors="replace") as handle:
                raw = handle.read()
        except Exception as exc:
            print(f"[RBST] capture merge: read stdout failed: {exc}")
            return None
        parsed = extract_json_object(raw, require_keys=("folders",))
        return sanitize_merged_template(parsed)
    except Exception as exc:
        print(f"[RBST] capture merge: llama failed: {exc}")
        return None
    finally:
        for path in (prompt_path, out_path, err_path):
            if path and os.path.isfile(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass


def load_previous_template(filepath: str, prefs=None) -> dict[str, Any] | None:
    """
    Previous base for Capture merge.

    Prefer existing filepath JSON; if missing/empty, use prefs active snapshot.
    """
    path = bpy_abspath(filepath) if filepath else ""
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and data.get("folders"):
                # load_template fills missing keys from builtin.
                return load_template(path)
        except Exception as exc:
            print(f"[RBST] capture merge: failed reading {path}: {exc}")
    # Secondary base when file empty / missing.
    try:
        from .org_template_context import get_active_org_template

        active = get_active_org_template(prefs)
        if active is not None:
            return active
    except Exception:
        pass
    return None


def bpy_abspath(filepath: str) -> str:
    """Resolve Blender relative // paths when bpy is available."""
    try:
        import bpy

        return bpy.path.abspath(filepath)
    except Exception:
        return os.path.abspath(filepath)


def merge_capture_templates(
    old: dict[str, Any] | None,
    new: dict[str, Any],
    prefs=None,
) -> tuple[dict[str, Any], str]:
    """
    Merge Capture snapshot into previous template.

    Returns (merged_template, path) where path is 'llm' or 'deterministic'.
    """
    if not isinstance(new, dict) or not new.get("folders"):
        raise ValueError("new template must include folders")
    if old is None or not old.get("folders"):
        return new, "deterministic"

    # Prefer llama when runtime ready; never require it.
    pkg = _addon_package()
    if prefs is not None and org_runtime_ready(pkg, prefs):
        cli = resolve_llama_cli(pkg, prefs)
        model = resolve_gguf_path(pkg, prefs)
        timeout = float(getattr(prefs, "org_llm_timeout", 120.0) or 120.0)
        if cli and model:
            llm_merged = _run_llama_merge(
                old, new, cli=cli, model=model, timeout=timeout
            )
            if llm_merged is not None:
                # Deterministic union first so GBNF-slim output cannot drop
                # folders/examples; LLM result refreshes signals on overlap.
                try:
                    det = merge_org_templates(old, new)
                    return merge_org_templates(det, llm_merged), "llm"
                except Exception:
                    return llm_merged, "llm"
            print("[RBST] capture merge: LLM unusable; deterministic fallback")

    return merge_org_templates(old, new), "deterministic"
