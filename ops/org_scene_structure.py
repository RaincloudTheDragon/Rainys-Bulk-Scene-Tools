"""Spawn summary dialog + thin alias of Spawn Scene Structure (#18).

`bst.org_scene_structure` aliases SSS (folders / order / case only). Full
sortation lives on Organize with Local Model (`run_org` baseline + decide).
"""

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

from ..utils.outliner_org import (
    format_org_summary,
)


def _get_org_template_path():
    """Read template path from addon preferences if set."""
    pkg = __package__.rsplit(".", 1)[0] if __package__ else ""
    addon = bpy.context.preferences.addons.get(pkg)
    if not addon or not addon.preferences:
        return None
    path = getattr(addon.preferences, "org_template_path", "") or ""
    return path or None


class RBST_Org_OT_summary_dialog(bpy.types.Operator):
    """Show outliner organization summary"""

    bl_idname = "bst.org_summary_dialog"
    bl_label = "Organize Scene Structure Summary"
    bl_options = {"REGISTER", "INTERNAL"}

    created_count: IntProperty(default=0)
    renamed_count: IntProperty(default=0)
    moved_count: IntProperty(default=0)
    nested_count: IntProperty(default=0)
    excluded_count: IntProperty(default=0)
    purged_count: IntProperty(default=0)
    skipped_count: IntProperty(default=0)
    dry_run: BoolProperty(default=False)
    details: StringProperty(default="")

    def draw(self, context):
        layout = self.layout
        title = "Dry-run Summary" if self.dry_run else "Organize Summary"
        layout.label(text=title, icon="INFO")
        layout.separator()

        box = layout.box()
        col = box.column(align=True)
        col.label(text=f"Created: {self.created_count}")
        col.label(text=f"Renamed: {self.renamed_count}")
        col.label(text=f"Objects moved: {self.moved_count}")
        col.label(text=f"Collections reorganized: {self.nested_count}")
        col.label(text=f"View-layer excluded: {self.excluded_count}")
        col.label(text=f"Purged empty: {self.purged_count}")
        if self.skipped_count:
            col.label(text=f"Skipped: {self.skipped_count}", icon="ERROR")

        if self.details:
            layout.separator()
            layout.label(text="Details:", icon="OUTLINER_DATA_FONT")
            details_box = layout.box()
            details_col = details_box.column(align=True)
            for line in self.details.split("\n"):
                if line.strip():
                    details_col.label(text=line, icon="RIGHTARROW_THIN")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)


def show_org_summary(report: dict):
    """Invoke summary popup and mirror the action maps to the console."""
    counts, details = format_org_summary(report)
    mode = "DRY-RUN" if counts.get("dry_run") else "APPLY"
    print(f"\n=== RBST Org Summary ({mode}) ===")
    print(f"Created: {counts['created_count']}")
    print(f"Renamed: {counts['renamed_count']}")
    print(f"Objects moved: {counts['moved_count']}")
    print(f"Collections reorganized: {counts['nested_count']}")
    print(f"View-layer excluded: {counts.get('excluded_count', 0)}")
    print(f"Purged empty: {counts['purged_count']}")
    print(f"Skipped: {counts['skipped_count']}")
    if details.strip():
        print("--- Maps ---")
        print(details)
    else:
        print("--- Maps --- (none)")
    print("=== End Org Summary ===\n")

    bpy.ops.bst.org_summary_dialog(
        "INVOKE_DEFAULT",
        created_count=counts["created_count"],
        renamed_count=counts["renamed_count"],
        moved_count=counts["moved_count"],
        nested_count=counts["nested_count"],
        excluded_count=counts.get("excluded_count", 0),
        purged_count=counts["purged_count"],
        skipped_count=counts["skipped_count"],
        dry_run=counts["dry_run"],
        details=details[:16000],
    )


class OrgSceneStructure(bpy.types.Operator):
    """Alias of Spawn Scene Structure (folders / order / case only)."""

    bl_idname = "bst.org_scene_structure"
    bl_label = "Organize into Scene Structure"
    bl_options = {"REGISTER", "UNDO"}

    dry_run: BoolProperty(
        name="Dry Run",
        description="Preview changes without modifying the scene",
        default=False,
    )

    def execute(self, context):
        # Same light spawn pipeline as SSS — kept for scripts / older UI.
        return bpy.ops.bst.spawn_scene_structure(
            "EXEC_DEFAULT", dry_run=bool(self.dry_run)
        )
