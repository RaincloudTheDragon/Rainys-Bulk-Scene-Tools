"""Capture current outliner tree as an org template JSON (#18)."""

import json
import os

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..utils.outliner_org import capture_template_from_scene


def _addon_prefs():
    pkg = __package__.rsplit(".", 1)[0] if __package__ else ""
    addon = bpy.context.preferences.addons.get(pkg)
    return addon.preferences if addon else None


class CaptureOutlinerTemplate(bpy.types.Operator, ExportHelper):
    """Write current scene collection tree to an org template JSON"""

    bl_idname = "bst.capture_outliner_template"
    bl_label = "Capture Outliner Template"
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
            data = capture_template_from_scene(context)
            path = bpy.path.abspath(self.filepath)
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2)
                handle.write("\n")
            prefs = _addon_prefs()
            if prefs is not None and hasattr(prefs, "org_template_path"):
                prefs.org_template_path = path
            self.report({"INFO"}, f"Template written: {path}")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Capture failed: {e}")
            return {"CANCELLED"}
