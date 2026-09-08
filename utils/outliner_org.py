"""
Outliner organization helpers for RBST (#18).

Deterministic path: ensure/rename/migrate structure only (aliases, type
placement for Cam/Lgt, override-safe nests). Props vs Dressing rulesets and
other guesses belong on the LLM path. Never calls make_local. WGTS_* / WGT-*
widget trees are left alone under their character.
"""

from __future__ import annotations

import json
import os
from typing import Any

import bpy

TEMPLATE_VERSION = 1

# Built-in scene structure (create-if-missing folders).
BUILTIN_TREE = {
    "Env": ["ROOTS", "Dressing"],
    "Animation": ["Cam", "Char"],
    "Lgt": [],
}
# Extra nests: parent_path_tuple -> child name
BUILTIN_EXTRA = {
    ("Animation", "Char"): ["Props"],
}
BUILTIN_EXCLUDE_PATHS = [["Env", "ROOTS"]]
BUILTIN_HIDE_VIEWPORT_PATHS = [["Env", "ROOTS"]]

# Case-insensitive exact rename aliases for local collections.
COLLECTION_ALIASES = {
    "env": "Env",
    "roots": "ROOTS",
    "dressing": "Dressing",
    "animation": "Animation",
    "cam": "Cam",
    "camera": "Cam",
    "cameras": "Cam",
    "char": "Char",
    "character": "Char",
    "characters": "Char",
    "props": "Props",
    "lgt": "Lgt",
    "light": "Lgt",
    "lights": "Lgt",
    "lighting": "Lgt",
}

# Object type -> collection path under structure.
TYPE_PLACEMENT = {
    "CAMERA": ["Animation", "Cam"],
    "LIGHT": ["Lgt"],
}

# Name substrings that suggest a character override blob.
_CHAR_HINTS = ("char", "rig", "hero", "actor", "npc", "creature", "person")

# Name substrings that suggest environment / set dressing (not Props).
_ENV_HINTS = (
    "scene",
    "environment",
    "room",
    "setdress",
    "background",
    "building",
    "interior",
    "exterior",
    "layout",
    "stage",
    "location",
    "backdrop",
    "world",
)

PLAN_ALLOWED_KEYS = frozenset(
    {
        "rename_collections",
        "move_collections",
        "move_objects",
        "merge_collections",
        "view_layer_exclude",
        "notes",
    }
)

# Canonical structure leaf → path under scene.collection.
STRUCTURE_PATHS = {
    "Env": ["Env"],
    "ROOTS": ["Env", "ROOTS"],
    "Dressing": ["Env", "Dressing"],
    "Animation": ["Animation"],
    "Cam": ["Animation", "Cam"],
    "Char": ["Animation", "Char"],
    "Props": ["Animation", "Char", "Props"],
    "Lgt": ["Lgt"],
}


def is_locked_collection(coll) -> bool:
    """True if collection is linked or a library override."""
    return bool(coll.library) or bool(getattr(coll, "override_library", None))


def is_locked_object(obj) -> bool:
    """True if object data is linked or overridden."""
    if obj.library or getattr(obj, "override_library", None):
        return True
    data = getattr(obj, "data", None)
    if data is not None and (data.library or getattr(data, "override_library", None)):
        return True
    return False


def find_layer_collection(layer_collection, collection_name: str):
    """Recursively find a LayerCollection by collection name."""
    if layer_collection.collection.name == collection_name:
        return layer_collection
    for child in layer_collection.children:
        result = find_layer_collection(child, collection_name)
        if result:
            return result
    return None


def find_layer_collection_by_path(layer_collection, path: list[str]):
    """Find LayerCollection by child-name path from a root layer collection."""
    current = layer_collection
    for name in path:
        match = None
        for child in current.children:
            if child.collection.name == name:
                match = child
                break
        if match is None:
            return None
        current = match
    return current


def get_collection_by_path(scene_collection, path: list[str]):
    """Resolve a collection path under scene.collection; None if missing."""
    current = scene_collection
    for name in path:
        match = None
        for child in current.children:
            if child.name == name:
                match = child
                break
        if match is None:
            return None
        current = match
    return current


def collection_parents(coll) -> list:
    """Return local collections that directly contain coll as a child."""
    parents = []
    for candidate in bpy.data.collections:
        if is_locked_collection(candidate):
            continue
        if coll.name in candidate.children:
            parents.append(candidate)
    scene = bpy.context.scene
    if scene and coll.name in scene.collection.children:
        parents.append(scene.collection)
    return parents


def can_unlink_object(obj, from_coll) -> bool:
    """Objects may only be unlinked from unlocked (local) collections."""
    if is_locked_collection(from_coll):
        return False
    if is_locked_object(obj) and is_locked_collection(from_coll):
        return False
    return not is_locked_collection(from_coll)


def _collection_is_instance_source(coll) -> bool:
    """True if any object instances this collection (do not empty it)."""
    if coll is None:
        return False
    for obj in bpy.data.objects:
        if getattr(obj, "instance_type", None) != "COLLECTION":
            continue
        if getattr(obj, "instance_collection", None) == coll:
            return True
    return False


def _collection_under_roots(coll) -> bool:
    """True if coll is ROOTS or nested under a ROOTS structure folder."""
    if coll is None:
        return False
    aliases = COLLECTION_ALIASES
    current = coll
    seen: set[str] = set()
    while current is not None and current.name not in seen:
        seen.add(current.name)
        if _canonical_for_name(current.name, aliases) == "ROOTS":
            return True
        parents = collection_parents(current)
        current = parents[0] if parents else None
    return False


def _is_non_structure_collection(coll) -> bool:
    """True for local content collections (not Env/Dressing/Cam/… folders)."""
    if coll is None:
        return False
    scene = bpy.context.scene
    if scene is not None and coll == scene.collection:
        return False
    if _canonical_for_name(coll.name) in STRUCTURE_PATHS:
        return False
    return True


def object_has_preserved_home(obj) -> bool:
    """
    True if the object already lives in a collection org must not empty.

    Preserve: locked/override, collection-instance sources, anything under
    ROOTS, and any non-structure content collection membership.
    """
    if obj is None:
        return False
    for coll in obj.users_collection:
        if is_locked_collection(coll):
            return True
        if _collection_is_instance_source(coll):
            return True
        if _collection_under_roots(coll):
            return True
        if _is_non_structure_collection(coll):
            return True
    return False


def can_move_collection_as_blob(coll, new_local_parent) -> bool:
    """
    Allowed: unlink a library/override collection from a local parent and
    link under another local parent. Forbidden: unpack children.
    """
    if new_local_parent is None or is_locked_collection(new_local_parent):
        return False
    # Target must already be local (scene root counts as local).
    parents = collection_parents(coll)
    if not parents:
        # Orphan / only in data — still allow linking under local parent.
        return True
    return all(not is_locked_collection(p) for p in parents)


def default_template() -> dict[str, Any]:
    """Built-in template dict used when no user template is loaded."""
    folders = []
    for main, subs in BUILTIN_TREE.items():
        folders.append([main])
        for sub in subs:
            folders.append([main, sub])
    for parent_path, children in BUILTIN_EXTRA.items():
        for child in children:
            folders.append(list(parent_path) + [child])
    return {
        "version": TEMPLATE_VERSION,
        "folders": folders,
        "rename_aliases": dict(COLLECTION_ALIASES),
        "type_placement": {k: list(v) for k, v in TYPE_PLACEMENT.items()},
        "view_layer_exclude": [list(p) for p in BUILTIN_EXCLUDE_PATHS],
        "hide_viewport": [list(p) for p in BUILTIN_HIDE_VIEWPORT_PATHS],
    }


def load_template(path: str | None) -> dict[str, Any]:
    """Load template JSON or return built-in default."""
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and data.get("folders"):
                # Fill missing keys from default.
                base = default_template()
                base.update({k: v for k, v in data.items() if v is not None})
                if "rename_aliases" not in data or not data["rename_aliases"]:
                    base["rename_aliases"] = dict(COLLECTION_ALIASES)
                if "type_placement" not in data or not data["type_placement"]:
                    base["type_placement"] = {
                        k: list(v) for k, v in TYPE_PLACEMENT.items()
                    }
                return base
        except Exception as exc:
            print(f"[RBST] Failed to load org template {path}: {exc}")
    return default_template()


def _find_child(parent, name: str):
    for child in parent.children:
        if child.name == name:
            return child
    return None


def _strip_numeric_suffix(name: str) -> str:
    """ROOTS.001 → ROOTS for structure matching."""
    if "." not in name:
        return name
    head, tail = name.rsplit(".", 1)
    if tail.isdigit():
        return head
    return name


def _canonical_for_name(name: str, aliases: dict[str, str] | None = None) -> str | None:
    """Map a collection name to its canonical structure leaf, if any."""
    aliases = aliases or COLLECTION_ALIASES
    base = _strip_numeric_suffix(name)
    if base in STRUCTURE_PATHS:
        return base
    return aliases.get(base.lower())


def ensure_folders(context, folders: list[list[str]], dry_run: bool = False) -> dict:
    """
    Create-if-missing folder paths under scene.collection.

    If a local datablock with the leaf name already exists elsewhere, adopt it
    under the parent instead of creating a .001 duplicate.
    """
    scene_collection = context.scene.collection
    created: list[str] = []
    adopted: list[str] = []
    skipped: list[str] = []

    for path in folders:
        if not path:
            continue
        parent = scene_collection
        dry_missing = False
        for i, name in enumerate(path):
            rel = "/".join(path[: i + 1])
            if dry_missing:
                # Still record remaining segments as would-create only if no global adopt.
                global_named = bpy.data.collections.get(name)
                if global_named and not is_locked_collection(global_named):
                    adopted.append(f"{rel} (adopt existing)")
                else:
                    created.append(rel)
                continue

            existing = _find_child(parent, name)
            if existing is not None:
                skipped.append(rel)
                parent = existing
                continue

            # Prefer adopting an existing local datablock with this exact name.
            global_named = bpy.data.collections.get(name)
            if global_named is not None and not is_locked_collection(global_named):
                if dry_run:
                    # Do not claim "Created"; reconcile/move will adopt.
                    skipped.append(f"{rel} (exists elsewhere)")
                    dry_missing = True
                    continue
                try:
                    for p in list(collection_parents(global_named)):
                        if global_named.name in p.children:
                            p.children.unlink(global_named)
                    if global_named.name not in parent.children:
                        parent.children.link(global_named)
                    adopted.append(rel)
                    parent = global_named
                except Exception as exc:
                    skipped.append(f"{rel} (adopt failed: {exc})")
                    dry_missing = True
                continue

            if dry_run:
                created.append(rel)
                dry_missing = True
                continue

            new_coll = bpy.data.collections.new(name)
            # Blender may have renamed on collision (should be rare after adopt).
            parent.children.link(new_coll)
            if new_coll.name != name:
                created.append(f"{rel} (as {new_coll.name})")
            else:
                created.append(rel)
            parent = new_coll

    return {"created": created, "adopted": adopted, "skipped": skipped}


def apply_view_layer_excludes(
    context, exclude_paths: list[list[str]], hide_paths: list[list[str]] | None = None
) -> list[str]:
    """Exclude and/or hide_viewport collections by path. Returns applied paths."""
    applied: list[str] = []
    view_layer = context.view_layer
    root_lc = view_layer.layer_collection
    scene_collection = context.scene.collection

    for path in exclude_paths or []:
        lc = find_layer_collection_by_path(root_lc, path)
        if lc is None:
            continue  # No leaf-name fallback — avoids excluding the wrong ROOTS.
        lc.exclude = True
        applied.append("/".join(path))

    for path in hide_paths or []:
        coll = get_collection_by_path(scene_collection, path)
        if coll is not None and not is_locked_collection(coll):
            coll.hide_viewport = True
            applied.append("/".join(path) + " (hide_viewport)")

    return applied


def ensure_builtin_structure(context, template: dict | None = None, dry_run: bool = False) -> dict:
    """Ensure template folders exist; pin Env/Animation/Lgt order at the top."""
    tmpl = template or default_template()
    result = ensure_folders(context, tmpl.get("folders", []), dry_run=dry_run)
    order = reorder_structure_collections(context, dry_run=dry_run)
    result["excludes"] = []
    result["reordered"] = order.get("reordered") or []
    return result


def reorder_structure_collections(context, dry_run: bool = False) -> dict:
    """
    Pin structure folders to a stable outliner order.

    Scene root: Env, Animation, Lgt, then everything else.
    Env: ROOTS, Dressing. Animation: Cam, Char. Char: Props.

    Blender 5.x Collection.children has link/unlink only (no move).
    """
    scene_collection = context.scene.collection
    reordered: list[str] = []

    def _reorder(parent, preferred: list[str], label: str) -> None:
        if parent is None or is_locked_collection(parent):
            return
        names = [c.name for c in parent.children]
        head = [n for n in preferred if n in names]
        if not head:
            return
        tail = [n for n in names if n not in preferred]
        desired = head + tail
        if desired == names:
            return
        reordered.append(f"{label}: {', '.join(desired[:12])}")
        if dry_run:
            return
        # Blender 5.x: Collection.children has link/unlink only (no move).
        by_name = {c.name: c for c in parent.children}
        ordered = [by_name[n] for n in desired]
        for child in list(parent.children):
            parent.children.unlink(child)
        for child in ordered:
            parent.children.link(child)

    _reorder(scene_collection, ["Env", "Animation", "Lgt"], "Scene")
    _reorder(
        get_collection_by_path(scene_collection, ["Env"]),
        ["ROOTS", "Dressing"],
        "Env",
    )
    _reorder(
        get_collection_by_path(scene_collection, ["Animation"]),
        ["Cam", "Char"],
        "Animation",
    )
    _reorder(
        get_collection_by_path(scene_collection, ["Animation", "Char"]),
        ["Props"],
        "Char",
    )
    return {"reordered": reordered}


def _alias_target(name: str, aliases: dict[str, str]) -> str | None:
    key = name.lower()
    target = aliases.get(key)
    if target and target != name:
        return target
    return None


def plan_renames(context, aliases: dict[str, str] | None = None) -> list[dict]:
    """Propose local collection renames when the target name is free."""
    aliases = aliases or COLLECTION_ALIASES
    scene_collection = context.scene.collection
    proposals: list[dict] = []

    def walk(parent):
        for child in list(parent.children):
            if is_locked_collection(child):
                walk(child)
                continue
            target = _alias_target(child.name, aliases)
            if target:
                name_taken = any(
                    c.name == target or c.name.lower() == target.lower()
                    for c in bpy.data.collections
                    if c != child
                )
                if not name_taken:
                    proposals.append(
                        {
                            "from": child.name,
                            "to": target,
                            "parent": parent.name,
                        }
                    )
            walk(child)

    walk(scene_collection)
    return proposals


def apply_renames(proposals: list[dict], dry_run: bool = False) -> dict:
    """Apply rename proposals; skip locked or colliding."""
    renamed: list[str] = []
    skipped: list[str] = []
    for item in proposals:
        coll = bpy.data.collections.get(item["from"])
        if coll is None:
            skipped.append(f"{item['from']} (missing)")
            continue
        if is_locked_collection(coll):
            skipped.append(f"{item['from']} (locked)")
            continue
        if coll.name == item["to"]:
            continue
        existing = bpy.data.collections.get(item["to"])
        if existing is not None and existing != coll:
            skipped.append(f"{item['from']}→{item['to']} (name exists)")
            continue
        if any(
            c.name.lower() == item["to"].lower() and c != coll
            for c in bpy.data.collections
        ):
            skipped.append(f"{item['from']}→{item['to']} (name exists)")
            continue
        if dry_run:
            renamed.append(f"{item['from']}→{item['to']}")
            continue
        try:
            coll.name = item["to"]
            renamed.append(f"{item['from']}→{coll.name}")
        except Exception as exc:
            skipped.append(f"{item['from']} ({exc})")
    return {"renamed": renamed, "skipped": skipped}


def _structure_collection_names(template: dict) -> set[str]:
    names = set()
    for path in template.get("folders", []):
        names.update(path)
    return names


def plan_merges_and_relinks(context, template: dict | None = None) -> dict:
    """
    When an alias collection collides with a canonical folder, merge into the
    canonical path (or move the real folder under the correct parent).
    """
    tmpl = template or default_template()
    aliases = tmpl.get("rename_aliases") or COLLECTION_ALIASES
    scene_collection = context.scene.collection
    merges: list[dict] = []
    moves: list[dict] = []
    seen_sources: set[str] = set()

    # Group local collections by canonical role.
    by_canon: dict[str, list] = {}
    for coll in bpy.data.collections:
        if is_locked_collection(coll):
            continue
        canon = _canonical_for_name(coll.name, aliases)
        if not canon or canon not in STRUCTURE_PATHS:
            continue
        by_canon.setdefault(canon, []).append(coll)

    for canon, path in STRUCTURE_PATHS.items():
        candidates = list(by_canon.get(canon, []))
        if not candidates:
            continue
        dest = get_collection_by_path(scene_collection, path)
        parent_path = path[:-1]
        parent = (
            scene_collection
            if not parent_path
            else get_collection_by_path(scene_collection, parent_path)
        )

        # Prefer collection already at the canonical path; else exact name; else richest.
        def richness(c):
            return len(c.objects) + len(c.children) * 10

        exact = bpy.data.collections.get(canon)
        if dest is not None and dest in candidates:
            primary = dest
        elif exact is not None and exact in candidates:
            primary = exact
        else:
            primary = max(candidates, key=richness)

        # Ensure primary sits under the correct parent.
        if parent is not None and primary.name not in parent.children:
            if primary.name not in seen_sources and can_move_collection_as_blob(primary, parent):
                moves.append({"name": primary.name, "to": list(parent_path) if parent_path else []})
                seen_sources.add(primary.name)

        for other in candidates:
            if other == primary:
                continue
            if other.name in seen_sources:
                continue
            # Merge duplicate / misplaced alias into primary (or into dest path).
            target_name = primary.name if dest is None else dest.name
            if dest is not None:
                target_name = dest.name
            merges.append({"from": other.name, "into": target_name, "into_path": list(path)})
            seen_sources.add(other.name)

    return {"merge_collections": merges, "move_collections": moves}


def apply_merges(context, proposals: list[dict], dry_run: bool = False) -> dict:
    """Merge local source collection contents into a destination collection."""
    scene_collection = context.scene.collection
    merged: list[str] = []
    skipped: list[str] = []

    for item in proposals:
        src = bpy.data.collections.get(item["from"])
        if src is None:
            skipped.append(f"{item['from']} (missing)")
            continue
        if is_locked_collection(src):
            skipped.append(f"{item['from']} (locked)")
            continue

        dest = bpy.data.collections.get(item.get("into") or "")
        if dest is None and item.get("into_path"):
            dest = get_collection_by_path(scene_collection, item["into_path"])
        if dest is None or is_locked_collection(dest):
            skipped.append(f"{item['from']} (dest missing/locked)")
            continue
        if src == dest:
            continue

        label = f"{src.name}⇒{dest.name}"
        if dry_run:
            merged.append(label)
            continue

        try:
            # Move child collections as blobs into dest.
            for child in list(src.children):
                if child.name in dest.children:
                    continue
                if is_locked_collection(child) or can_move_collection_as_blob(child, dest):
                    if child.name in src.children:
                        src.children.unlink(child)
                    if child.name not in dest.children:
                        dest.children.link(child)

            # Move local-unlinkable objects.
            for obj in list(src.objects):
                if not can_unlink_object(obj, src):
                    continue
                src.objects.unlink(obj)
                if dest not in obj.users_collection:
                    dest.objects.link(obj)

            # Unlink empty source from parents.
            if len(src.children) == 0 and len(src.objects) == 0:
                for p in list(collection_parents(src)):
                    if src.name in p.children:
                        p.children.unlink(src)
            merged.append(label)
        except Exception as exc:
            skipped.append(f"{item['from']} ({exc})")

    return {"merged": merged, "skipped": skipped}


def plan_object_moves(context, template: dict | None = None) -> list[dict]:
    """
    Deterministic object migrate only (no Props/Dressing ruleset guesses).

    - Cameras → Cam; camera DOF/constraint/parent helpers → Cam
    - Lights → Lgt; light helpers → Lgt
    - WGTS_* collections and WGT-* widgets: never touch (stay under their char)
    - Everything else stays put; ambiguous placement is the LLM path
    """
    tmpl = template or default_template()
    placement = tmpl.get("type_placement", TYPE_PLACEMENT)
    aliases = tmpl.get("rename_aliases") or COLLECTION_ALIASES
    scene_collection = context.scene.collection
    proposals: list[dict] = []
    seen: set[str] = set()
    cam_path = list(STRUCTURE_PATHS.get("Cam") or ["Animation", "Cam"])
    lgt_path = list(STRUCTURE_PATHS.get("Lgt") or ["Lgt"])
    camera_helpers = _build_camera_helper_names(context)
    light_helpers = _build_light_helper_names(context)

    def _in_fx_collection(obj) -> bool:
        for coll in obj.users_collection:
            lower = coll.name.lower()
            if any(h in lower for h in ("fx", "physics", "sim", "fluid", "cloth", "vfx")):
                return True
        return False

    def _propose(obj, dest_path: list[str]) -> None:
        if obj.name in seen:
            return
        dest = get_collection_by_path(scene_collection, dest_path)
        if dest is None:
            return
        if dest in obj.users_collection:
            seen.add(obj.name)
            return
        dest_leaf = dest_path[-1]
        for c in obj.users_collection:
            if _canonical_for_name(c.name, aliases) == dest_leaf:
                seen.add(obj.name)
                return
        sources = [c for c in obj.users_collection if can_unlink_object(obj, c)]
        if not sources:
            return
        proposals.append(
            {
                "name": obj.name,
                "to": list(dest_path),
                "from": sources[0].name,
            }
        )
        seen.add(obj.name)

    def _keep(obj) -> None:
        seen.add(obj.name)

    for obj in context.scene.objects:
        # Rigify widget trees / meshes — leave under the character hierarchy.
        if _is_rig_widget(obj) or _object_in_wgt_collection(obj):
            _keep(obj)
            continue

        if _in_fx_collection(obj):
            _keep(obj)
            continue

        # Hard type placement (camera/light datablocks).
        type_dest = placement.get(obj.type)
        if type_dest:
            _propose(obj, list(type_dest))
            continue

        # Relation-inferred camera / light helpers (DOF, track-to, parents…).
        if obj.name in camera_helpers:
            _propose(obj, cam_path)
            continue
        if obj.name in light_helpers:
            _propose(obj, lgt_path)
            continue

    return proposals


def apply_object_moves(context, proposals: list[dict], dry_run: bool = False) -> dict:
    """Unlink local objects from local parents and link under destination."""
    scene_collection = context.scene.collection
    moved: list[str] = []
    skipped: list[str] = []

    for item in proposals:
        obj = context.scene.objects.get(item["name"])
        if obj is None:
            skipped.append(f"{item['name']} (missing)")
            continue
        # Never flatten objects already housed in preserved content collections.
        if object_has_preserved_home(obj):
            skipped.append(f"{item['name']} (preserve content collection)")
            continue
        dest = get_collection_by_path(scene_collection, item["to"])
        if dest is None or is_locked_collection(dest):
            skipped.append(f"{item['name']} (dest locked/missing)")
            continue
        if dest in obj.users_collection:
            continue

        sources = [c for c in obj.users_collection if can_unlink_object(obj, c)]
        if not sources and obj.users_collection:
            skipped.append(f"{item['name']} (locked parent)")
            continue

        label = f"{item['name']}→{'/'.join(item['to'])}"
        why = str(item.get("why") or "").strip()
        if why:
            label = f"{label} | why: {why}"
        if dry_run:
            moved.append(label)
            continue
        try:
            for src in sources:
                src.objects.unlink(obj)
            if dest not in obj.users_collection:
                dest.objects.link(obj)
            moved.append(label)
        except Exception as exc:
            skipped.append(f"{item['name']} ({exc})")

    return {"moved": moved, "skipped": skipped}


def _char_like(name: str) -> bool:
    lower = name.lower()
    return any(h in lower for h in _CHAR_HINTS)


def _is_wgt_collection(name: str) -> bool:
    """Rigify/ARP widget collections (WGTS_* / WGT_*) — leave under their char."""
    compact = name.upper().replace(" ", "").replace("-", "_")
    return compact.startswith("WGTS") or compact.startswith("WGT_")


def _is_rig_widget(obj) -> bool:
    """Rigify/ARP widget meshes (WGT-* / WGT - *) — leave in place."""
    n = obj.name
    upper = n.upper().replace(" ", "")
    return (
        upper.startswith("WGT")
        or n.lower().startswith("wgt")
        or "WGT-" in n.upper()
        or "WGT_" in upper
    )


def _object_in_wgt_collection(obj) -> bool:
    """True if object is linked into a WGTS_* collection (or nested under one)."""
    for coll in obj.users_collection:
        if _is_wgt_collection(coll.name):
            return True
        current = coll
        seen: set[str] = set()
        while current is not None and current.name not in seen:
            seen.add(current.name)
            if _is_wgt_collection(current.name):
                return True
            parents = collection_parents(current)
            current = parents[0] if parents else None
    return False


def _env_like(name: str) -> bool:
    """True for scene/room/dock/environment-style names (belong under Env)."""
    lower = name.lower().replace("-", " ").replace("_", " ")
    return any(h in lower for h in _ENV_HINTS)


def _env_dest_path_for_name(name: str) -> list[str]:
    """Env vs Env/Dressing for environment-like content."""
    lower = name.lower()
    if "dress" in lower:
        return list(STRUCTURE_PATHS.get("Dressing") or ["Env", "Dressing"])
    return list(STRUCTURE_PATHS.get("Env") or ["Env"])


def _build_camera_helper_names(context) -> set[str]:
    """
    Objects that belong with cameras: DOF focus, constraint targets/parents,
    children, or anything that constrains/parents to a camera.
    """
    helpers: set[str] = set()
    cam_names: set[str] = set()
    for obj in context.scene.objects:
        if obj.type != "CAMERA":
            continue
        cam_names.add(obj.name)
        if obj.parent is not None:
            helpers.add(obj.parent.name)
        for child in obj.children:
            helpers.add(child.name)
        for con in obj.constraints:
            target = getattr(con, "target", None)
            if target is not None:
                helpers.add(target.name)
        data = getattr(obj, "data", None)
        dof = getattr(data, "dof", None) if data is not None else None
        focus = getattr(dof, "focus_object", None) if dof is not None else None
        if focus is not None:
            helpers.add(focus.name)

    for obj in context.scene.objects:
        if obj.parent is not None and obj.parent.name in cam_names:
            helpers.add(obj.name)
        for con in obj.constraints:
            target = getattr(con, "target", None)
            if target is not None and target.name in cam_names:
                helpers.add(obj.name)
    helpers -= cam_names
    return helpers


def _collection_object_type_counts(coll) -> dict[str, int]:
    """Count object types in a collection subtree."""
    counts: dict[str, int] = {}
    if coll is None:
        return counts

    def _walk(c):
        for obj in c.objects:
            counts[obj.type] = counts.get(obj.type, 0) + 1
        for child in c.children:
            _walk(child)

    _walk(coll)
    return counts


def _is_light_dominated_collection(coll) -> bool:
    """
    True when a collection is primarily lights (a light pack), not an env/set
    that merely contains a few lights among many meshes.
    """
    counts = _collection_object_type_counts(coll)
    lights = counts.get("LIGHT", 0)
    if lights == 0:
        return False
    geo = (
        counts.get("MESH", 0)
        + counts.get("CURVE", 0)
        + counts.get("FONT", 0)
        + counts.get("SURFACE", 0)
        + counts.get("VOLUME", 0)
    )
    # Env/set packs have more geo than lights — never treat as light groups.
    if geo > lights:
        return False
    total = sum(counts.values())
    return lights * 2 >= total  # lights are at least half the content


def _is_light_group_object(obj) -> bool:
    """
    Empty/helper that groups lights (parent of lights, or instances a light pack).

    Structural only — no name matching. Large scene instances that merely
    contain some lights are not light groups.
    """
    if obj is None or obj.type == "LIGHT":
        return False
    if any(child.type == "LIGHT" for child in obj.children):
        return True
    if getattr(obj, "instance_type", "") == "COLLECTION":
        inst = getattr(obj, "instance_collection", None)
        if inst is None:
            return False
        # Linked/override scene packs belong under Env as blobs, not Lgt.
        if is_locked_collection(inst):
            return False
        return _is_light_dominated_collection(inst)
    return False


def _build_light_helper_names(context) -> set[str]:
    """Objects that belong with lights: parents, constraints, light-group empties."""
    helpers: set[str] = set()
    light_names = {o.name for o in context.scene.objects if o.type == "LIGHT"}
    for obj in context.scene.objects:
        if obj.type == "LIGHT":
            if obj.parent is not None:
                helpers.add(obj.parent.name)
            for child in obj.children:
                helpers.add(child.name)
            for con in obj.constraints:
                target = getattr(con, "target", None)
                if target is not None:
                    helpers.add(target.name)
            continue
        if obj.parent is not None and obj.parent.name in light_names:
            helpers.add(obj.name)
        for con in obj.constraints:
            target = getattr(con, "target", None)
            if target is not None and target.name in light_names:
                helpers.add(obj.name)
        if _is_light_group_object(obj):
            helpers.add(obj.name)
    helpers -= light_names
    return helpers


def _has_armature_relation(obj, armature_targets: set[str] | None = None) -> bool:
    """
    True if this object is tied to an armature (prop interaction).

    Parent-to-armature, constraints to an armature, or being a constraint
    target of an armature all count. No relation → prefer Env/Dressing.
    """
    if obj.parent is not None and obj.parent.type == "ARMATURE":
        return True
    for con in obj.constraints:
        target = getattr(con, "target", None)
        if target is not None and target.type == "ARMATURE":
            return True
    if armature_targets is not None and obj.name in armature_targets:
        return True
    return False


def plan_override_nests(context, template: dict | None = None) -> list[dict]:
    """
    Nest only orphan locked collections that sit directly under Scene Collection.

    Do not pull locked blobs out of Env / Animation / alias parents (e.g. leave
    DOCK SCENE BSDF under env→Env). Interactive prop rigs are handled by
    plan_prop_rig_nests. ROOTS is not a dump for every non-character override.
    """
    tmpl = template or default_template()
    scene_collection = context.scene.collection
    structure_names = _structure_collection_names(tmpl)
    char_path = ["Animation", "Char"]
    env_path = ["Env"]
    proposals: list[dict] = []

    for child in list(scene_collection.children):
        if not is_locked_collection(child):
            continue
        if child.name in structure_names or _is_wgt_collection(child.name):
            continue
        dest_path = char_path if _char_like(child.name) else env_path
        dest = get_collection_by_path(scene_collection, dest_path)
        if dest is not None and child.name in dest.children:
            continue
        if dest is not None and not can_move_collection_as_blob(child, dest):
            continue
        proposals.append({"name": child.name, "to": list(dest_path)})

    return proposals


def _iter_collection_objects(coll):
    """Yield all objects in a collection subtree."""
    for obj in coll.objects:
        yield obj
    for child in coll.children:
        yield from _iter_collection_objects(child)


def _constraint_targets(obj) -> list:
    """Object + pose-bone constraint targets."""
    targets = []
    for con in obj.constraints:
        target = getattr(con, "target", None)
        if target is not None:
            targets.append(target)
    if obj.type == "ARMATURE" and obj.pose is not None:
        for pose_bone in obj.pose.bones:
            for con in pose_bone.constraints:
                target = getattr(con, "target", None)
                if target is not None:
                    targets.append(target)
    return targets


def _locked_blob_root_for_object(obj):
    """Topmost locked/override collection that contains this object."""
    locked = [c for c in obj.users_collection if is_locked_collection(c)]
    if not locked:
        return None

    def _topmost(coll):
        current = coll
        while True:
            parents = [
                p for p in collection_parents(current) if is_locked_collection(p)
            ]
            if not parents:
                return current
            current = parents[0]

    return _topmost(locked[0])


def _collection_has_armed_override_rig(coll) -> bool:
    """True if subtree has an override/library armature with an action."""
    for obj in _iter_collection_objects(coll):
        if obj.type != "ARMATURE":
            continue
        if not (obj.library or getattr(obj, "override_library", None)):
            continue
        anim = obj.animation_data
        if anim is not None and anim.action is not None:
            return True
    return False


def _objects_under_collection(coll) -> set[str]:
    return {obj.name for obj in _iter_collection_objects(coll)}


def _is_descendant_collection(coll, ancestor) -> bool:
    """True if ancestor appears above coll in the collection tree."""
    if coll is None or ancestor is None:
        return False
    if coll == ancestor:
        return True
    for parent in collection_parents(coll):
        if parent == ancestor or _is_descendant_collection(parent, ancestor):
            return True
    return False


def plan_prop_rig_nests(context, template: dict | None = None) -> list[dict]:
    """
    Nest interactive override prop-rig collections under Animation/Char/Props.

    A locked blob qualifies when a Char-side object constrains into that blob,
    or it sits under Animation with an armed override rig — and it is **not**
    environment/scene-like (those go to Env via plan_env_like_nests).
    """
    tmpl = template or default_template()
    scene_collection = context.scene.collection
    structure_names = _structure_collection_names(tmpl)
    props_path = list(STRUCTURE_PATHS.get("Props") or ["Animation", "Char", "Props"])
    props = get_collection_by_path(scene_collection, props_path)
    char = get_collection_by_path(scene_collection, ["Animation", "Char"])
    anim = get_collection_by_path(scene_collection, ["Animation"])
    if props is None:
        return []

    char_names = _objects_under_collection(char) if char is not None else set()
    blob_names: set[str] = set()

    for name in list(char_names):
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        for target in _constraint_targets(obj):
            current = target
            seen_obj: set[str] = set()
            while current is not None and current.name not in seen_obj:
                seen_obj.add(current.name)
                if current.name not in char_names:
                    blob = _locked_blob_root_for_object(current)
                    if (
                        blob is not None
                        and blob.name not in structure_names
                        and not _char_like(blob.name)
                        and not _env_like(blob.name)
                    ):
                        blob_names.add(blob.name)
                current = current.parent

    if anim is not None:
        for child in list(anim.children):
            if not is_locked_collection(child):
                continue
            if child.name in structure_names or _char_like(child.name):
                continue
            if _env_like(child.name):
                continue
            if _collection_has_armed_override_rig(child):
                blob_names.add(child.name)

    proposals: list[dict] = []
    for name in sorted(blob_names):
        if _is_wgt_collection(name):
            continue
        coll = bpy.data.collections.get(name)
        if coll is None:
            continue
        if _is_descendant_collection(coll, props):
            continue
        if coll.name in props.children:
            continue
        if not can_move_collection_as_blob(coll, props):
            continue
        proposals.append({"name": coll.name, "to": list(props_path)})

    return proposals


def plan_env_like_nests(context, template: dict | None = None) -> list[dict]:
    """
    Nest scene/room/dock/environment-like collections under Env.

    Pulls them out of Animation / Props when misplaced.
    """
    tmpl = template or default_template()
    scene_collection = context.scene.collection
    structure_names = _structure_collection_names(tmpl)
    env_path = list(STRUCTURE_PATHS.get("Env") or ["Env"])
    env = get_collection_by_path(scene_collection, env_path)
    if env is None:
        return []

    hosts = []
    for path in (["Animation"], ["Animation", "Char", "Props"], ["Animation", "Char"]):
        host = get_collection_by_path(scene_collection, path)
        if host is not None:
            hosts.append(host)

    proposals: list[dict] = []
    seen: set[str] = set()
    for host in hosts:
        for child in list(host.children):
            if (
                child.name in structure_names
                or _char_like(child.name)
                or _is_wgt_collection(child.name)
            ):
                continue
            if not _env_like(child.name):
                continue
            if child.name in seen:
                continue
            dest_path = _env_dest_path_for_name(child.name)
            dest_coll = get_collection_by_path(scene_collection, dest_path)
            if dest_coll is None:
                dest_path = env_path
                dest_coll = env
            if child.name in dest_coll.children or _is_descendant_collection(
                child, dest_coll
            ):
                continue
            if not can_move_collection_as_blob(child, dest_coll):
                continue
            proposals.append({"name": child.name, "to": list(dest_path)})
            seen.add(child.name)

    return proposals


def clear_accidental_structure_excludes(context, dry_run: bool = False) -> dict:
    """
    Ensure Env / Animation / Lgt / Cam / Char are not view-layer excluded.

    Tiny local models sometimes exclude whole buckets; ROOTS may stay excluded.
    """
    keep_excluded = {tuple(p) for p in BUILTIN_EXCLUDE_PATHS}
    cleared: list[str] = []
    root_lc = context.view_layer.layer_collection
    protected = {"Env", "Animation", "Lgt", "Cam", "Char", "Props", "Dressing"}

    def walk(lc, path: list[str]):
        name = lc.collection.name if lc.collection else ""
        if path and name in protected and tuple(path) not in keep_excluded and lc.exclude:
            label = "/".join(path)
            if not dry_run:
                lc.exclude = False
            cleared.append(label)
        for child in lc.children:
            walk(child, path + [child.collection.name])

    walk(root_lc, [])
    return {"cleared": cleared}


def apply_collection_moves(context, proposals: list[dict], dry_run: bool = False) -> dict:
    """Nest collections as wholes under a local parent (override-safe)."""
    scene_collection = context.scene.collection
    nested: list[str] = []
    skipped: list[str] = []

    for item in proposals:
        coll = bpy.data.collections.get(item["name"])
        if coll is None:
            skipped.append(f"{item['name']} (missing)")
            continue
        dest_path = item.get("to") or []
        if not dest_path:
            dest = scene_collection
            path_label = "Scene Collection"
        else:
            dest = get_collection_by_path(scene_collection, dest_path)
            path_label = "/".join(dest_path)
        if dest is None:
            skipped.append(f"{item['name']}→{path_label} (dest missing)")
            continue
        if is_locked_collection(dest) and dest != scene_collection:
            skipped.append(f"{item['name']} (dest locked)")
            continue
        if coll.name in dest.children:
            continue
        if not can_move_collection_as_blob(coll, dest):
            skipped.append(f"{item['name']} (cannot move blob)")
            continue

        label = f"{item['name']}→{path_label}"
        if dry_run:
            nested.append(label)
            continue

        try:
            parents = list(collection_parents(coll))
            if any(is_locked_collection(p) for p in parents):
                skipped.append(f"{item['name']} (locked parent)")
                continue
            for parent in parents:
                if coll.name in parent.children:
                    parent.children.unlink(coll)
            if coll.name not in dest.children:
                dest.children.link(coll)
            nested.append(label)
        except Exception as exc:
            skipped.append(f"{item['name']} ({exc})")

    return {"nested": nested, "skipped": skipped}


def apply_view_layer_exclude_plan(
    context, paths: list[list[str]], dry_run: bool = False
) -> dict:
    """Apply view-layer exclude paths from a plan (path must resolve)."""
    applied: list[str] = []
    skipped: list[str] = []
    root_lc = context.view_layer.layer_collection
    scene_collection = context.scene.collection

    for path in paths:
        # Dry-run: only claim exclude if path exists now, or leaf exists and
        # will be adopted under that path (reported separately as adopt).
        lc = find_layer_collection_by_path(root_lc, path)
        if lc is None:
            # After adopt/move, leaf may exist under the intended parent soon.
            leaf = bpy.data.collections.get(path[-1]) if path else None
            parent = (
                scene_collection
                if len(path) == 1
                else get_collection_by_path(scene_collection, path[:-1])
            )
            if leaf is not None and parent is not None and (
                leaf.name in parent.children or dry_run
            ):
                if dry_run:
                    applied.append("/".join(path))
                    continue
            skipped.append("/".join(path) + " (missing)")
            continue
        if dry_run:
            applied.append("/".join(path))
            continue
        lc.exclude = True
        applied.append("/".join(path))
        coll = get_collection_by_path(scene_collection, path)
        if coll is not None and not is_locked_collection(coll):
            coll.hide_viewport = True
    return {"excluded": applied, "skipped": skipped}


def purge_empty_local_collections(dry_run: bool = False) -> dict:
    """Remove unused empty local collections (not library/override)."""
    purged: list[str] = []
    skipped: list[str] = []
    # Also unlink empty local duplicates still parented but unused as content
    # (e.g. ROOTS.001) when users==1 only via a parent link — handled by
    # removing after unlink in merge. Here: zero-user orphans + empty .001 shells
    # that match a canonical name with a richer twin.
    for _ in range(5):
        candidates = []
        for c in bpy.data.collections:
            if is_locked_collection(c):
                continue
            if len(c.children) != 0 or len(c.objects) != 0:
                continue
            if c.users == 0:
                candidates.append(c)
                continue
            # Empty numbered shell (ROOTS.001) while ROOTS exists with content.
            if "." in c.name:
                base = c.name.rsplit(".", 1)[0]
                twin = bpy.data.collections.get(base)
                if twin is not None and twin != c and (
                    len(twin.objects) > 0 or len(twin.children) > 0
                ):
                    candidates.append(c)
        if not candidates:
            break
        for coll in candidates:
            name = coll.name
            if dry_run:
                purged.append(name)
                continue
            try:
                for p in list(collection_parents(coll)):
                    if coll.name in p.children:
                        p.children.unlink(coll)
                if coll.users == 0:
                    bpy.data.collections.remove(coll)
                purged.append(name)
            except Exception as exc:
                skipped.append(f"{name} ({exc})")
        if dry_run:
            break
    return {"purged": purged, "skipped": skipped}


def sanitize_plan(raw: Any) -> dict[str, Any]:
    """Allowlist plan keys; drop make_local and unknown actions."""
    if not isinstance(raw, dict):
        return {
            "rename_collections": [],
            "move_collections": [],
            "move_objects": [],
            "merge_collections": [],
            "view_layer_exclude": [],
            "notes": ["invalid plan dropped"],
        }
    plan: dict[str, Any] = {
        "rename_collections": [],
        "move_collections": [],
        "move_objects": [],
        "merge_collections": [],
        "view_layer_exclude": [],
        "notes": [],
    }
    for key in PLAN_ALLOWED_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if key == "notes":
            if isinstance(value, list):
                plan["notes"] = [str(n) for n in value]
            continue
        if isinstance(value, list):
            plan[key] = value
    for bad in ("make_local", "unlink_override", "actions", "python"):
        if bad in raw:
            plan["notes"].append(f"stripped forbidden key: {bad}")
    return plan


def _normalize_structure_segment(name: str) -> str:
    """Map alias spelling to canonical structure leaf (Roots→ROOTS)."""
    if name in STRUCTURE_PATHS:
        return name
    return COLLECTION_ALIASES.get(name.lower(), name)


def _normalize_structure_path(path: list) -> list[str]:
    return [_normalize_structure_segment(str(p)) for p in path]


def filter_plan_against_inventory(plan: dict, inventory: dict) -> dict[str, Any]:
    """
    Drop LLM actions that cannot apply (tiny models invent names/paths).

    Keeps only renames that match known aliases, moves to structure paths,
    and override nests under Env or Animation/Char. Preserves move `why`
    strings and records drop reasons in notes for console debug.
    """
    plan = sanitize_plan(plan)
    nodes = {
        n.get("name"): n
        for n in (inventory.get("collections") or [])
        if isinstance(n, dict) and n.get("name")
    }
    obj_names: set[str] = set()
    for n in nodes.values():
        for o in n.get("objects") or []:
            if isinstance(o, str):
                obj_names.add(o)
            elif isinstance(o, dict) and o.get("name"):
                obj_names.add(o["name"])
    for o in inventory.get("loose_objects") or []:
        if isinstance(o, dict) and o.get("name"):
            obj_names.add(o["name"])
    for o in inventory.get("decide_objects") or []:
        if isinstance(o, dict) and o.get("name"):
            obj_names.add(o["name"])
    # Allow heuristic sweep names that exist in the live scene.
    for item in plan.get("move_objects") or []:
        if isinstance(item, dict) and item.get("name"):
            name = item["name"]
            if bpy.data.objects.get(name) is not None:
                obj_names.add(name)

    valid_dests = {tuple(p) for p in STRUCTURE_PATHS.values()}
    dropped = 0
    drop_log: list[str] = []

    def _drop(reason: str) -> None:
        nonlocal dropped
        dropped += 1
        drop_log.append(reason)

    renames = []
    for item in plan.get("rename_collections") or []:
        if not isinstance(item, dict):
            _drop("rename: not an object")
            continue
        fr, to = item.get("from"), item.get("to")
        if not fr or not to or fr not in nodes:
            _drop(f"rename: unknown/missing {fr!r}->{to!r}")
            continue
        node = nodes[fr]
        if node.get("library") or node.get("override"):
            _drop(f"rename: locked {fr}")
            continue
        canonical = COLLECTION_ALIASES.get(str(fr).lower())
        to_norm = _normalize_structure_segment(str(to))
        if canonical and to_norm == canonical and fr != to_norm:
            renames.append({"from": fr, "to": to_norm})
        else:
            _drop(f"rename: not an alias {fr}->{to}")

    moves_c = []
    for item in plan.get("move_collections") or []:
        if not isinstance(item, dict):
            _drop("move_coll: not an object")
            continue
        name, dest = item.get("name"), item.get("to")
        if not name or name not in nodes or not isinstance(dest, list):
            _drop(f"move_coll: unknown {name!r}")
            continue
        path = _normalize_structure_path(dest)
        if tuple(path) not in valid_dests:
            _drop(f"move_coll: bad dest {name}->{path}")
            continue
        node = nodes[name]
        locked = bool(node.get("library") or node.get("override"))
        if locked:
            if _env_like(name):
                expected = _env_dest_path_for_name(name)
            elif any(h in name.lower() for h in _CHAR_HINTS):
                expected = ["Animation", "Char"]
            else:
                expected = ["Env"]
            if path != expected:
                _drop(f"move_coll: locked expected {expected} got {path} ({name})")
                continue
        if name in STRUCTURE_PATHS:
            _drop(f"move_coll: structure folder {name}")
            continue
        if _is_wgt_collection(name):
            _drop(f"move_coll: WGTS ignored {name}")
            continue
        if _env_like(name) and path[:1] != ["Env"] and "Props" in path:
            _drop(f"move_coll: env into Props {name}")
            continue
        moves_c.append({"name": name, "to": path})

    moves_o = []
    for item in plan.get("move_objects") or []:
        if not isinstance(item, dict):
            _drop("move_obj: not an object")
            continue
        name, dest = item.get("name"), item.get("to")
        why = str(item.get("why") or "").strip()
        if not name or name not in obj_names or not isinstance(dest, list):
            _drop(
                f"move_obj: not in inventory {name!r}"
                + (f" (why={why})" if why else "")
            )
            continue
        path = _normalize_structure_path(dest)
        if tuple(path) not in valid_dests:
            _drop(
                f"move_obj: bad dest {name}->{path}"
                + (f" — {why}" if why else "")
            )
            continue
        obj = bpy.data.objects.get(name)
        if obj is not None and (
            _is_rig_widget(obj) or _object_in_wgt_collection(obj)
        ):
            _drop(
                f"move_obj: WGT ignored {name}" + (f" — {why}" if why else "")
            )
            continue
        if name.upper().replace(" ", "").startswith("WGT"):
            _drop(
                f"move_obj: WGT ignored {name}" + (f" — {why}" if why else "")
            )
            continue
        if obj is not None and object_has_preserved_home(obj):
            _drop(
                f"move_obj: preserve pack {name}"
                + (f" — {why}" if why else "")
            )
            continue
        if _env_like(name) and (
            path == list(STRUCTURE_PATHS.get("Props") or []) or "Props" in path
        ):
            path = _env_dest_path_for_name(name)
        entry = {"name": name, "to": path}
        if why:
            entry["why"] = why
        moves_o.append(entry)

    merges = []
    for item in plan.get("merge_collections") or []:
        if not isinstance(item, dict):
            _drop("merge: not an object")
            continue
        fr, into = item.get("from"), item.get("into") or item.get("to")
        if not fr or not into or fr not in nodes:
            _drop(f"merge: unknown {fr!r}")
            continue
        into_norm = _normalize_structure_segment(str(into))
        if into_norm not in STRUCTURE_PATHS and into_norm not in nodes:
            _drop(f"merge: bad into {fr}->{into}")
            continue
        merges.append({"from": fr, "into": into_norm})

    excludes = []
    allowed_excludes = {tuple(p) for p in BUILTIN_EXCLUDE_PATHS}
    for path in plan.get("view_layer_exclude") or []:
        if not isinstance(path, list) or not path:
            _drop("exclude: bad path")
            continue
        norm = _normalize_structure_path(path)
        if tuple(norm) not in allowed_excludes:
            _drop(f"exclude: not allowed {norm}")
            continue
        excludes.append(norm)

    notes = list(plan.get("notes") or [])
    if moves_c:
        dropped += len(moves_c)
        for m in moves_c:
            drop_log.append(
                f"move_coll ignored (deterministic nests): {m.get('name')}"
            )
        moves_c = []
        notes.append("ignored model collection moves (deterministic handles nests)")
    if merges:
        dropped += len(merges)
        merges = []
        notes.append("ignored model merges (deterministic handles merges)")

    if drop_log:
        notes.append("filter drops:")
        notes.extend(f"  · {line}" for line in drop_log[:40])
        if len(drop_log) > 40:
            notes.append(f"  · … +{len(drop_log) - 40} more")
    if dropped:
        notes.append(f"filtered {dropped} invalid model action(s)")
    seen_notes: set[str] = set()
    uniq_notes = []
    for n in notes:
        if n not in seen_notes:
            seen_notes.add(n)
            uniq_notes.append(n)
    return sanitize_plan(
        {
            "rename_collections": renames,
            "move_collections": moves_c,
            "move_objects": moves_o,
            "merge_collections": merges,
            "view_layer_exclude": excludes,
            "notes": uniq_notes,
        }
    )



def plan_action_count(plan: dict) -> int:
    """Count actionable entries in a sanitized plan."""
    plan = sanitize_plan(plan)
    return sum(
        len(plan.get(k) or [])
        for k in (
            "rename_collections",
            "move_collections",
            "move_objects",
            "merge_collections",
            "view_layer_exclude",
        )
    )


def merge_org_reports(*reports: dict) -> dict:
    """Concatenate org report lists from baseline + LLM apply."""
    out: dict[str, Any] = {
        "created": [],
        "adopted": [],
        "renamed": [],
        "moved": [],
        "nested": [],
        "merged": [],
        "excluded": [],
        "purged": [],
        "skipped": [],
        "notes": [],
        "dry_run": False,
    }
    for report in reports:
        if not report:
            continue
        for key in out:
            if key == "dry_run":
                out["dry_run"] = bool(out["dry_run"] or report.get("dry_run"))
                continue
            out[key].extend(list(report.get(key) or []))
    return out


def apply_plan(context, plan: dict, dry_run: bool = False) -> dict:
    """Apply a sanitized plan through safety-checked helpers."""
    plan = sanitize_plan(plan)
    report: dict[str, Any] = {
        "renamed": [],
        "moved": [],
        "nested": [],
        "merged": [],
        "excluded": [],
        "skipped": [],
        "notes": list(plan.get("notes") or []),
    }

    rename_props = []
    for item in plan.get("rename_collections") or []:
        if not isinstance(item, dict):
            continue
        fr = item.get("from")
        to = item.get("to")
        if fr and to:
            rename_props.append({"from": fr, "to": to, "parent": ""})
    r = apply_renames(rename_props, dry_run=dry_run)
    report["renamed"].extend(r["renamed"])
    report["skipped"].extend(r["skipped"])

    # Relink structure folders before merges/nests.
    c = apply_collection_moves(
        context,
        [i for i in (plan.get("move_collections") or []) if isinstance(i, dict)],
        dry_run=dry_run,
    )
    report["nested"].extend(c["nested"])
    report["skipped"].extend(c["skipped"])

    m = apply_merges(
        context,
        [i for i in (plan.get("merge_collections") or []) if isinstance(i, dict)],
        dry_run=dry_run,
    )
    report["merged"].extend(m["merged"])
    report["skipped"].extend(m["skipped"])

    o = apply_object_moves(
        context,
        [i for i in (plan.get("move_objects") or []) if isinstance(i, dict)],
        dry_run=dry_run,
    )
    report["moved"].extend(o["moved"])
    report["skipped"].extend(o["skipped"])

    e = apply_view_layer_exclude_plan(
        context,
        [p for p in (plan.get("view_layer_exclude") or []) if isinstance(p, list)],
        dry_run=dry_run,
    )
    report["excluded"].extend(e["excluded"])
    report["skipped"].extend(e["skipped"])

    return report


def build_deterministic_plan(context, template: dict | None = None) -> dict:
    """Build a plan from deterministic heuristics (no LLM)."""
    tmpl = template or default_template()
    aliases = tmpl.get("rename_aliases") or COLLECTION_ALIASES
    reconcile = plan_merges_and_relinks(context, tmpl)
    nests = plan_override_nests(context, tmpl)
    prop_nests = plan_prop_rig_nests(context, tmpl)
    env_nests = plan_env_like_nests(context, tmpl)
    # De-dupe moves: reconcile, orphans, env-like, then prop-rig nests.
    move_names = {m["name"] for m in reconcile.get("move_collections") or []}
    for n in nests + env_nests + prop_nests:
        if n["name"] not in move_names:
            reconcile.setdefault("move_collections", []).append(n)
            move_names.add(n["name"])

    return sanitize_plan(
        {
            "rename_collections": [
                {"from": p["from"], "to": p["to"]}
                for p in plan_renames(context, aliases)
            ],
            "move_collections": reconcile.get("move_collections") or [],
            "merge_collections": reconcile.get("merge_collections") or [],
            "move_objects": [
                {"name": p["name"], "to": p["to"]}
                for p in plan_object_moves(context, tmpl)
            ],
            "view_layer_exclude": list(tmpl.get("view_layer_exclude") or []),
            "notes": [],
        }
    )


def run_org(context, template: dict | None = None, dry_run: bool = False) -> dict:
    """
    Full deterministic org: ensure/adopt tree, reconcile merges, apply plan, purge.
    """
    tmpl = template or default_template()
    ensure = ensure_builtin_structure(context, tmpl, dry_run=dry_run)
    plan = build_deterministic_plan(context, tmpl)
    applied = apply_plan(context, plan, dry_run=dry_run)
    cleared = clear_accidental_structure_excludes(context, dry_run=dry_run)
    purge = purge_empty_local_collections(dry_run=dry_run)
    # Re-pin after merges/nests so Env stays above Animation/Lgt.
    order = reorder_structure_collections(context, dry_run=dry_run)

    notes = list(applied.get("notes", []))
    for label in cleared.get("cleared") or []:
        notes.append(f"cleared exclude: {label}")
    for label in order.get("reordered") or []:
        notes.append(f"ordered {label}")

    return {
        "created": ensure.get("created", []),
        "adopted": ensure.get("adopted", []),
        "ensure_skipped": ensure.get("skipped", []),
        "renamed": applied.get("renamed", []),
        "moved": applied.get("moved", []),
        "nested": applied.get("nested", []),
        "merged": applied.get("merged", []),
        "excluded": applied.get("excluded", []),
        "purged": purge.get("purged", []),
        "skipped": (
            list(applied.get("skipped", []))
            + list(purge.get("skipped", []))
        ),
        "notes": notes,
        "dry_run": dry_run,
    }


def capture_template_from_scene(context) -> dict[str, Any]:
    """Walk current scene tree into a template JSON-serializable dict."""
    scene_collection = context.scene.collection
    folders: list[list[str]] = []
    exclude_paths: list[list[str]] = []
    hide_paths: list[list[str]] = []

    structure_names = _structure_collection_names(default_template())

    def walk(coll, path: list[str]):
        # Record local folder-like collections as create-if-missing.
        # Skip wrappers that only exist to hold locked/linked blobs.
        has_locked_child = any(is_locked_collection(c) for c in coll.children)
        is_structure = bool(path) and path[-1] in structure_names
        if (
            path
            and not is_locked_collection(coll)
            and len(coll.objects) == 0
            and (is_structure or not has_locked_child)
        ):
            folders.append(list(path))
            if coll.hide_viewport:
                hide_paths.append(list(path))
        for child in coll.children:
            if is_locked_collection(child):
                # Keep exclude discovery via layer walk; do not create locked blobs.
                continue
            # Do not recurse into non-structure content wrappers.
            if len(child.objects) > 0 and child.name not in structure_names:
                continue
            if any(is_locked_collection(c) for c in child.children) and child.name not in structure_names:
                continue
            walk(child, path + [child.name])

    walk(scene_collection, [])

    root_lc = context.view_layer.layer_collection

    def walk_lc(lc, path: list[str]):
        if path and lc.exclude:
            exclude_paths.append(list(path))
        for child in lc.children:
            walk_lc(child, path + [child.collection.name])

    walk_lc(root_lc, [])

    # Ensure built-in structure paths are present even if scene is incomplete.
    base = default_template()
    existing = {"/".join(p) for p in folders}
    for path in base["folders"]:
        key = "/".join(path)
        if key not in existing:
            folders.append(list(path))

    return {
        "version": TEMPLATE_VERSION,
        "folders": folders,
        "rename_aliases": dict(COLLECTION_ALIASES),
        "type_placement": {k: list(v) for k, v in TYPE_PLACEMENT.items()},
        "view_layer_exclude": exclude_paths or list(base["view_layer_exclude"]),
        "hide_viewport": hide_paths or list(base["hide_viewport"]),
    }


def _structure_home_name(obj, aliases: dict[str, str] | None = None) -> str | None:
    aliases = aliases or COLLECTION_ALIASES
    for coll in obj.users_collection:
        canon = _canonical_for_name(coll.name, aliases)
        if canon in STRUCTURE_PATHS:
            return canon
    return None


def _object_has_action(obj) -> bool:
    anim = getattr(obj, "animation_data", None)
    if anim is None:
        return False
    if anim.action is not None:
        return True
    for track in getattr(anim, "nla_tracks", []) or []:
        if track.strips:
            return True
    return False


def _empty_is_anim_helper(obj) -> bool:
    """Helper empties: parented and/or constrained (no name matching)."""
    if obj is None or obj.type != "EMPTY":
        return False
    if obj.parent is not None:
        return True
    return len(obj.constraints) > 0


def _object_relates_to_armature(obj) -> bool:
    """Parented/constrained to an armature."""
    if obj is None:
        return False
    if obj.parent is not None and obj.parent.type == "ARMATURE":
        return True
    for con in obj.constraints:
        target = getattr(con, "target", None)
        if target is not None and target.type == "ARMATURE":
            return True
    return False


def build_decide_candidates(context, limit: int = 40) -> list[dict[str, Any]]:
    """
    Ambiguous loose objects for the LLM (props vs dressing).

    Structural signals only — no asset-name heuristics. Skips objects that
    already live in a preserved (non-structure / instance / ROOTS) home.
    """
    scored: list[tuple[int, dict[str, Any]]] = []
    seen: set[str] = set()

    def _add(obj, hint: str, priority: int) -> None:
        if obj is None or obj.name in seen:
            return
        if _is_rig_widget(obj) or _object_in_wgt_collection(obj):
            return
        if obj.type in {"CAMERA", "LIGHT"}:
            return
        if _structure_home_name(obj) in {"Props", "Lgt", "Cam"}:
            return
        if object_has_preserved_home(obj):
            return
        seen.add(obj.name)
        parent = obj.parent.name if obj.parent else None
        cons = []
        for con in obj.constraints:
            target = getattr(con, "target", None)
            if target is not None:
                cons.append(target.name)
        scored.append(
            (
                priority,
                {
                    "name": obj.name,
                    "type": obj.type,
                    "parent": parent,
                    "home": _structure_home_name(obj),
                    "collections": [c.name for c in obj.users_collection][:4],
                    "constraints": cons[:4],
                    "hint": hint,
                },
            )
        )

    for obj in context.scene.objects:
        if _is_light_group_object(obj):
            _add(obj, "light_group", 110)
        elif obj.type == "EMPTY" and _empty_is_anim_helper(obj):
            hint = (
                "empty_on_parent" if obj.parent is not None else "anim_helper_empty"
            )
            _add(obj, hint, 100)
        elif _object_has_action(obj) and obj.type not in {
            "CAMERA",
            "LIGHT",
            "ARMATURE",
        }:
            _add(obj, "animated", 90)
        elif _object_relates_to_armature(obj):
            if obj.parent is not None and obj.parent.type == "ARMATURE":
                _add(obj, "armature_child", 70)
            else:
                _add(obj, "constrained", 85)
        elif obj.type in {"MESH", "CURVE", "FONT", "SURFACE", "EMPTY"}:
            if (
                obj.parent is None
                and not obj.constraints
                and not _object_has_action(obj)
                and not _is_light_group_object(obj)
            ):
                _add(obj, "loose", 20)

    scored.sort(key=lambda t: (-t[0], t[1]["name"]))
    return [item for _prio, item in scored[:limit]]


def heuristic_decide_object_moves(inventory: dict, context=None) -> list[dict[str, Any]]:
    """
    Fallback Props/Dressing moves when the tiny local model returns nothing.

    Structural signals only. Never empties preserved content collections.
    """
    props = list(STRUCTURE_PATHS.get("Props") or ["Animation", "Char", "Props"])
    dressing = list(STRUCTURE_PATHS.get("Dressing") or ["Env", "Dressing"])
    lgt = list(STRUCTURE_PATHS.get("Lgt") or ["Lgt"])
    moves: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _emit(name: str, dest: list[str], why: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        moves.append({"name": name, "to": list(dest), "why": why})

    props_hints = {
        "empty_on_parent",
        "anim_helper_empty",
        "animated",
        "constrained",
    }
    for item in inventory.get("decide_objects") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        hint = str(item.get("hint") or "")
        if not name:
            continue
        live = bpy.data.objects.get(name)
        if live is not None and object_has_preserved_home(live):
            continue
        if hint == "light_group":
            _emit(name, lgt, "heuristic (light_group) → Lgt")
        elif hint in props_hints:
            _emit(name, props, f"heuristic ({hint}) → Props")
        elif hint == "armature_child":
            _emit(
                name,
                dressing,
                "heuristic (armature_child, static) → Dressing",
            )
        elif hint == "loose":
            _emit(name, dressing, "heuristic (loose leftover) → Dressing")

    if context is not None:
        for obj in context.scene.objects:
            if obj.name in seen:
                continue
            if _is_rig_widget(obj) or _object_in_wgt_collection(obj):
                continue
            if _structure_home_name(obj) in {"Props", "Lgt", "Cam"}:
                continue
            if object_has_preserved_home(obj):
                continue
            if _is_light_group_object(obj):
                _emit(obj.name, lgt, "heuristic (light_group) → Lgt")
            elif obj.type == "EMPTY" and _empty_is_anim_helper(obj):
                _emit(obj.name, props, "heuristic (anim helper empty) → Props")
            elif _object_has_action(obj) and obj.type not in {
                "CAMERA",
                "LIGHT",
                "ARMATURE",
            }:
                _emit(obj.name, props, "heuristic (animated) → Props")
            elif _object_relates_to_armature(obj) and obj.type != "ARMATURE":
                if obj.parent is not None and obj.parent.type == "ARMATURE":
                    if not _object_has_action(obj) and not any(
                        getattr(c, "target", None) for c in obj.constraints
                    ):
                        _emit(
                            obj.name,
                            dressing,
                            "heuristic (static armature child) → Dressing",
                        )
                    else:
                        _emit(obj.name, props, "heuristic (rig-related) → Props")
                else:
                    _emit(obj.name, props, "heuristic (constrained to rig) → Props")
            elif (
                obj.type in {"MESH", "CURVE", "FONT", "SURFACE", "EMPTY"}
                and obj.parent is None
                and not obj.constraints
                and not _object_has_action(obj)
                and not _is_light_group_object(obj)
            ):
                _emit(obj.name, dressing, "heuristic (loose leftover) → Dressing")

    return moves



def build_inventory(context) -> dict[str, Any]:
    """Compact scene inventory for the org worker (no library filepaths)."""
    scene = context.scene
    scene_collection = scene.collection

    def coll_node(coll) -> dict:
        objects = []
        wgt_count = 0
        for obj in coll.objects:
            if obj.name.upper().startswith("WGT"):
                wgt_count += 1
            else:
                objects.append(obj.name)
        children = []
        for child in coll.children:
            children.append(child.name)
        node = {
            "name": coll.name,
            "library": bool(coll.library),
            "override": bool(getattr(coll, "override_library", None)),
            "objects": objects,
            "wgt_count": wgt_count,
            "children": children,
        }
        return node

    tree = []
    for child in scene_collection.children:
        tree.append(coll_node(child))
        # One level of nested detail for structure + blobs
        for grand in child.children:
            tree.append({**coll_node(grand), "parent": child.name})

    loose = []
    for obj in scene_collection.objects:
        loose.append(
            {
                "name": obj.name,
                "type": obj.type,
                "parent": obj.parent.name if obj.parent else None,
                "override": bool(getattr(obj, "override_library", None)),
            }
        )

    blend_path = bpy.data.filepath or ""
    return {
        "blend_path": blend_path,
        "scene": scene.name,
        "collections": tree,
        "loose_objects": loose,
        "decide_objects": build_decide_candidates(context),
    }


def format_org_summary(report: dict) -> tuple[dict, str]:
    """Build summary dialog numbers and multiline details string."""
    details_lines = []
    for key, label in (
        ("created", "Created"),
        ("adopted", "Adopted"),
        ("renamed", "Renamed"),
        ("merged", "Merged"),
        ("moved", "Moved"),
        ("nested", "Nested"),
        ("excluded", "Excluded"),
        ("purged", "Purged"),
        ("skipped", "Skipped"),
        ("notes", "Notes"),
    ):
        items = report.get(key) or []
        for item in items:
            details_lines.append(f"{label}: {item}")

    counts = {
        "created_count": len(report.get("created") or []),
        "renamed_count": len(report.get("renamed") or []),
        "moved_count": len(report.get("moved") or []),
        "nested_count": len(report.get("nested") or [])
        + len(report.get("merged") or [])
        + len(report.get("adopted") or []),
        "excluded_count": len(report.get("excluded") or []),
        "purged_count": len(report.get("purged") or []),
        "skipped_count": len(report.get("skipped") or []),
        "dry_run": bool(report.get("dry_run")),
    }
    return counts, "\n".join(details_lines)


def org_model_cache_dir(addon_package: str) -> str:
    """User cache directory for org GGUF models."""
    from .org_runtime import org_model_cache_dir as _impl

    return _impl(addon_package)


def resolve_gguf_path(addon_package: str, prefs=None) -> str | None:
    """Return existing GGUF path from prefs or cache, else None."""
    from .org_runtime import resolve_gguf_path as _impl

    return _impl(addon_package, prefs)
