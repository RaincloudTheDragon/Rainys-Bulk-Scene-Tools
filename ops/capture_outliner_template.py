"""Capture current outliner tree as an org template JSON (#18).

Merges with any existing template at the chosen path (agentic llama merge when
runtime is ready; deterministic additive merge otherwise). Also syncs the
merged result into the prefs active org-template slot.
"""

import json
import os

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..utils.org_template_context import (
    apply_active_org_template,
    make_active_template_label,
)
from ..utils.org_template_merge_llm import (
    load_previous_template,
    merge_capture_templates,
)
from ..utils.outliner_org import capture_template_from_scene


def _addon_prefs():
    pkg = __package__.rsplit(".", 1)[0] if __package__ else ""
    addon = bpy.context.preferences.addons.get(pkg)
    return addon.preferences if addon else None


class CaptureOutlinerTemplate(bpy.types.Operator, ExportHelper):
    """Merge scene outliner into template JSON (agentic when runtime ready)"""

    bl_idname = "bst.capture_outliner_template"
    bl_label = "Capture Outliner Template"
    bl_description = (
        "Merge this scene's structure into the org template file. "
        "Uses the local model when runtime is ready; otherwise additive "
        "deterministic merge. Syncs prefs org context across blends."
    )
    bl_options = {"REGISTER"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        prefs = _addon_prefs()
        if prefs and getattr(prefs, "org_template_path", ""):
            self.filepath = prefs.org_template_path
        elif not self.filepath:
            self.filepath = "rbst_outliner_template.json"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            new_snap = capture_template_from_scene(context)
            path = bpy.path.abspath(self.filepath)
            prefs = _addon_prefs()
            old = load_previous_template(path, prefs)
            data, merge_path = merge_capture_templates(old, new_snap, prefs)

            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
                handle.write("\n")

            if prefs is not None and hasattr(prefs, "org_template_path"):
                prefs.org_template_path = path
            # Keep prefs active context in sync across blends (additive).
            n_ex = len(data.get("placement_examples") or [])
            n_folders = len(data.get("folders") or [])
            if prefs is not None:
                label = make_active_template_label(context)
                apply_active_org_template(prefs, data, label=label)

            self.report(
                {"INFO"},
                f"Template merged ({merge_path}): +{n_ex} examples, "
                f"{n_folders} folders → {path}",
            )
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Capture failed: {e}")
            return {"CANCELLED"}
