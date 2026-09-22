"""Apply / reset prefs-backed outliner org template context (#18)."""

import bpy

from ..utils.org_template_context import (
    active_org_template_status,
    apply_active_org_template,
    clear_active_org_template,
    get_addon_prefs,
    make_active_template_label,
)
from ..utils.outliner_org import capture_template_from_scene


class ApplyOutlinerTemplateContext(bpy.types.Operator):
    """
    Add the current outliner into addon prefs/sidecar (additive merge).

    Successive blends accumulate folders/excludes until Reset. Used by
    spawn/org and the local-model prompt. Does not write a template JSON
    file (use Capture).
    """

    bl_idname = "bst.apply_outliner_template_context"
    bl_label = "Add Current Outliner to Org Context"
    bl_options = {"REGISTER"}

    def execute(self, context):
        prefs = get_addon_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences unavailable")
            return {"CANCELLED"}
        try:
            data = capture_template_from_scene(context)
            label = make_active_template_label(context)
            merged, added = apply_active_org_template(prefs, data, label=label)
            total = len(merged.get("folders") or [])
            self.report(
                {"INFO"},
                f"Org context updated (+{added} folders, {total} total): {label}",
            )
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Apply org context failed: {e}")
            return {"CANCELLED"}


class ResetOutlinerTemplateContext(bpy.types.Operator):
    """Clear the prefs/sidecar org template; fall back to file path / builtin."""

    bl_idname = "bst.reset_outliner_template_context"
    bl_label = "Reset Active Org Context"
    bl_options = {"REGISTER"}

    def execute(self, context):
        prefs = get_addon_prefs(context)
        if prefs is None:
            self.report({"ERROR"}, "Addon preferences unavailable")
            return {"CANCELLED"}
        prior = active_org_template_status(prefs)
        clear_active_org_template(prefs)
        if prior:
            self.report(
                {"INFO"},
                "Active org context cleared; using file path / builtin",
            )
        else:
            self.report({"INFO"}, "No active org context to clear")
        return {"FINISHED"}
