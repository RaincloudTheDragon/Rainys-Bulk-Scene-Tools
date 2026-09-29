"""
Active org-template context in addon prefs / sidecar (#18).

Resolution order for spawn/org/LLM:
  1. prefs org_active_template_json (validated)
  2. org_template_path file via load_template
  3. default_template()

Apply merges each capture into the active snapshot (additive); Reset clears it.
Capture merges into the chosen JSON file (llama when runtime ready, else
merge_org_templates) and also apply_active_org_template so prefs stay in sync.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import bpy

from .outliner_org import default_template, load_template


def get_addon_prefs(context=None):
    """Resolve RBST AddonPreferences from context or bpy.context."""
    ctx = context or bpy.context
    pkg = __package__.rsplit(".", 1)[0] if __package__ else ""
    # Prefer caller's package root (utils -> addon).
    if pkg.endswith(".utils"):
        pkg = pkg.rsplit(".", 1)[0]
    addon = ctx.preferences.addons.get(pkg)
    return addon.preferences if addon else None


def _addon_prefs(context=None):
    """Alias for get_addon_prefs (internal call sites)."""
    return get_addon_prefs(context)


def _org_template_path(prefs) -> str | None:
    path = getattr(prefs, "org_template_path", "") or ""
    return path or None


def _normalize_template(data: dict[str, Any]) -> dict[str, Any]:
    """Fill missing keys from builtin default (same as load_template merge)."""
    base = default_template()
    base.update({k: v for k, v in data.items() if v is not None})
    if not data.get("rename_aliases"):
        base["rename_aliases"] = dict(base.get("rename_aliases") or {})
    if not data.get("type_placement"):
        base["type_placement"] = dict(base.get("type_placement") or {})
    if "placement_examples" not in data or data.get("placement_examples") is None:
        base["placement_examples"] = list(base.get("placement_examples") or [])
    return base


def get_active_org_template(prefs=None) -> dict[str, Any] | None:
    """
    Parse prefs org_active_template_json; None if unset or corrupt.

    Requires a dict with a non-empty folders list.
    """
    prefs = prefs if prefs is not None else _addon_prefs()
    if prefs is None:
        return None
    raw = str(getattr(prefs, "org_active_template_json", "") or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    folders = data.get("folders")
    if not isinstance(folders, list) or not folders:
        return None
    return _normalize_template(data)


def _path_list_key(path) -> tuple[str, ...] | None:
    if not isinstance(path, list) or not path:
        return None
    return tuple(str(p) for p in path)


def _merge_path_lists(*sources: list | None) -> list[list[str]]:
    """Union path lists in order; first occurrence wins."""
    out: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for src in sources:
        if not src:
            continue
        for path in src:
            key = _path_list_key(path)
            if key is None or key in seen:
                continue
            seen.add(key)
            out.append(list(key))
    return out


def merge_org_templates(
    base: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    """
    Additive merge: union folders / excludes / hides / placement_examples;
    later aliases win.

    Used so Apply / Capture from successive blend files accumulates context.
    """
    if not isinstance(incoming, dict) or not incoming.get("folders"):
        raise ValueError("incoming template must include folders")
    base = base if isinstance(base, dict) else None
    aliases: dict[str, str] = {}
    type_placement: dict[str, Any] = {}
    for src in (base, incoming):
        if not src:
            continue
        for key, val in (src.get("rename_aliases") or {}).items():
            aliases[str(key)] = str(val)
        for key, val in (src.get("type_placement") or {}).items():
            type_placement[str(key)] = list(val) if isinstance(val, list) else val

    # placement_examples: key by (name, path); incoming refreshes signals.
    examples_by_key: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
    for src in (base, incoming):
        if not src:
            continue
        for ex in src.get("placement_examples") or []:
            if not isinstance(ex, dict) or not ex.get("name"):
                continue
            path = ex.get("path")
            path_key = _path_list_key(path)
            if path_key is None:
                continue
            key = (str(ex["name"]), path_key)
            examples_by_key[key] = {
                "name": str(ex["name"]),
                "path": list(path_key),
                "signals": [
                    str(s) for s in (ex.get("signals") or []) if s
                ][:8],
            }
    placement_examples = list(examples_by_key.values())[:80]

    merged = {
        "version": incoming.get("version")
        or (base.get("version") if base else None)
        or default_template().get("version"),
        "folders": _merge_path_lists(
            (base or {}).get("folders"),
            incoming.get("folders"),
        ),
        "view_layer_exclude": _merge_path_lists(
            (base or {}).get("view_layer_exclude"),
            incoming.get("view_layer_exclude"),
        ),
        "hide_viewport": _merge_path_lists(
            (base or {}).get("hide_viewport"),
            incoming.get("hide_viewport"),
        ),
        "rename_aliases": aliases,
        "type_placement": type_placement,
        "placement_examples": placement_examples,
    }
    return _normalize_template(merged)


def set_active_org_template(
    prefs, template: dict[str, Any], *, label: str = ""
) -> None:
    """Write template JSON into prefs (sidecar update via property update)."""
    if prefs is None:
        raise ValueError("prefs required")
    if not isinstance(template, dict) or not template.get("folders"):
        raise ValueError("template must include folders")
    # Compact JSON to keep prefs/sidecar smaller.
    prefs.org_active_template_json = json.dumps(
        template, separators=(",", ":"), ensure_ascii=False
    )
    if hasattr(prefs, "org_active_template_label"):
        prefs.org_active_template_label = (label or "")[:256]


def apply_active_org_template(
    prefs, incoming: dict[str, Any], *, label: str = ""
) -> tuple[dict[str, Any], int]:
    """
    Merge incoming into the active prefs template (additive).

    Returns (merged_template, folders_added_count).
    """
    existing = get_active_org_template(prefs)
    before = {
        _path_list_key(p)
        for p in ((existing or {}).get("folders") or [])
        if _path_list_key(p) is not None
    }
    merged = merge_org_templates(existing, incoming)
    after = {
        _path_list_key(p)
        for p in (merged.get("folders") or [])
        if _path_list_key(p) is not None
    }
    added = len(after - before)
    # Append last source onto prior label when merging.
    prior = str(getattr(prefs, "org_active_template_label", "") or "").strip()
    if existing and prior and label:
        combined = f"{prior} + {label}"
    else:
        combined = label or prior
    n = len(merged.get("folders") or [])
    status = f"{combined} ({n} folders)" if combined else f"{n} folders"
    set_active_org_template(prefs, merged, label=status)
    return merged, added


def clear_active_org_template(prefs) -> None:
    """Reset active template slot (fall back to file path / builtin)."""
    if prefs is None:
        return
    prefs.org_active_template_json = ""
    if hasattr(prefs, "org_active_template_label"):
        prefs.org_active_template_label = ""


def has_active_org_template(prefs=None) -> bool:
    """True when a validated active template is stored."""
    return get_active_org_template(prefs) is not None


def active_org_template_status(prefs=None) -> str:
    """Short UI status string, or empty if unset."""
    prefs = prefs if prefs is not None else _addon_prefs()
    if prefs is None:
        return ""
    if not has_active_org_template(prefs):
        return ""
    label = str(getattr(prefs, "org_active_template_label", "") or "").strip()
    return label or "Active org context set"


def make_active_template_label(context) -> str:
    """Scene name + UTC stamp for prefs status line."""
    scene = getattr(context, "scene", None)
    name = scene.name if scene else "scene"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    return f"{name} @ {stamp}"


def resolve_org_template(context=None) -> dict[str, Any]:
    """
    Active prefs snapshot → org_template_path file → builtin default.
    """
    prefs = _addon_prefs(context)
    active = get_active_org_template(prefs)
    if active is not None:
        return active
    path = _org_template_path(prefs) if prefs else None
    return load_template(path)


def compact_user_template(template: dict[str, Any] | None) -> dict[str, Any]:
    """Trim template for LLM inventory (folders, excludes, placement examples)."""
    if not template:
        template = default_template()
    examples = []
    for ex in template.get("placement_examples") or []:
        if not isinstance(ex, dict) or not ex.get("name"):
            continue
        path = ex.get("path")
        if not isinstance(path, list) or not path:
            continue
        examples.append(
            {
                "name": str(ex["name"]),
                "path": [str(p) for p in path],
                "signals": [str(s) for s in (ex.get("signals") or []) if s][:6],
            }
        )
        if len(examples) >= 24:
            break
    return {
        "folders": list(template.get("folders") or []),
        "view_layer_exclude": list(template.get("view_layer_exclude") or []),
        "hide_viewport": list(template.get("hide_viewport") or []),
        "placement_examples": examples,
    }
