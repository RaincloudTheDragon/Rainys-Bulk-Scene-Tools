"""
Sidecar JSON for Rainy's Bulk Scene Tools addon preferences.

Survives Blender disable/enable (VS Code Reload Addons) via user CONFIG dir.
"""

import json
import os

import bpy

SIDECAR_VERSION = 1
SIDECAR_FILENAME = "rbst_prefs.json"

_restoring = False
_last_written = None


def is_restoring():
    return _restoring


def sidecar_path():
    base = bpy.utils.user_resource("CONFIG")
    if not base:
        return None
    return os.path.join(base, SIDECAR_FILENAME)


def _get_addon_prefs():
    for addon in bpy.context.preferences.addons.values():
        ap = getattr(addon, "preferences", None)
        if ap and hasattr(ap, "automat_common_outside_blend"):
            return ap
    return None


def prefs_snapshot(prefs):
    if prefs is None:
        return None
    return {
        "version": SIDECAR_VERSION,
        "automat_common_outside_blend": bool(prefs.automat_common_outside_blend),
        "org_template_path": str(getattr(prefs, "org_template_path", "") or ""),
        "org_active_template_json": str(
            getattr(prefs, "org_active_template_json", "") or ""
        ),
        "org_active_template_label": str(
            getattr(prefs, "org_active_template_label", "") or ""
        ),
        "org_gguf_path": str(getattr(prefs, "org_gguf_path", "") or ""),
        "org_gguf_filename": str(getattr(prefs, "org_gguf_filename", "") or ""),
        "org_llama_cli_path": str(getattr(prefs, "org_llama_cli_path", "") or ""),
        "org_llm_allow_heuristic": bool(
            getattr(prefs, "org_llm_allow_heuristic", False)
        ),
        "org_llm_timeout": float(getattr(prefs, "org_llm_timeout", 120.0) or 120.0),
    }


def apply_snapshot(data, prefs):
    if not data or prefs is None:
        return False

    global _restoring
    _restoring = True
    try:
        if "automat_common_outside_blend" in data:
            prefs.automat_common_outside_blend = bool(
                data["automat_common_outside_blend"]
            )
        if "org_template_path" in data and hasattr(prefs, "org_template_path"):
            prefs.org_template_path = str(data["org_template_path"] or "")
        if "org_active_template_json" in data and hasattr(
            prefs, "org_active_template_json"
        ):
            prefs.org_active_template_json = str(
                data["org_active_template_json"] or ""
            )
        if "org_active_template_label" in data and hasattr(
            prefs, "org_active_template_label"
        ):
            prefs.org_active_template_label = str(
                data["org_active_template_label"] or ""
            )
        if "org_gguf_path" in data and hasattr(prefs, "org_gguf_path"):
            prefs.org_gguf_path = str(data["org_gguf_path"] or "")
        if "org_gguf_filename" in data and hasattr(prefs, "org_gguf_filename"):
            prefs.org_gguf_filename = str(data["org_gguf_filename"] or "")
        if "org_llama_cli_path" in data and hasattr(prefs, "org_llama_cli_path"):
            prefs.org_llama_cli_path = str(data["org_llama_cli_path"] or "")
        if "org_llm_allow_heuristic" in data and hasattr(
            prefs, "org_llm_allow_heuristic"
        ):
            prefs.org_llm_allow_heuristic = bool(data["org_llm_allow_heuristic"])
        if "org_llm_timeout" in data and hasattr(prefs, "org_llm_timeout"):
            prefs.org_llm_timeout = float(data["org_llm_timeout"] or 120.0)
        return True
    finally:
        _restoring = False

def load_sidecar():
    path = sidecar_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except Exception as e:
        print(f"[RBST] Could not read prefs sidecar {path}: {e}")
        return None


def save_sidecar(prefs=None):
    global _last_written
    if _restoring:
        return False

    prefs = prefs or _get_addon_prefs()
    path = sidecar_path()
    if not prefs or not path:
        return False

    snapshot = prefs_snapshot(prefs)
    if snapshot is None:
        return False

    encoded = json.dumps(snapshot, indent=2, sort_keys=True)
    if encoded == _last_written:
        return False

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.write("\n")
        _last_written = encoded
        return True
    except Exception as e:
        print(f"[RBST] Could not write prefs sidecar {path}: {e}")
        return False


def restore_sidecar_into_prefs(prefs=None):
    prefs = prefs or _get_addon_prefs()
    data = load_sidecar()
    if not data or not prefs:
        return False

    ok = apply_snapshot(data, prefs)
    if ok:
        global _last_written
        try:
            _last_written = json.dumps(
                prefs_snapshot(prefs), indent=2, sort_keys=True
            )
        except Exception:
            _last_written = None
    return ok
