"""Spawn scene folders with correct order and case (#18). Sortation is LLM org."""

import bpy
from bpy.props import BoolProperty

from ..utils.outliner_org import load_template, run_spawn
from .org_scene_structure import _get_org_template_path, show_org_summary


class SpawnSceneStructure(bpy.types.Operator):
    """
    Ensure Env / Animation / Lgt folders exist, fix alias case, pin outliner order.

    Does not move objects or nest packs — use Organize with Local Model for that.
    """

    bl_idname = "bst.spawn_scene_structure"
    bl_label = "Spawn Scene Structure"
    bl_options = {"REGISTER", "UNDO"}

    dry_run: BoolProperty(
        name="Dry Run",
        description="Preview folder spawn without modifying the scene",
        default=False,
    )

    def execute(self, context):
        try:
            template = load_template(_get_org_template_path())
            report = run_spawn(context, template=template, dry_run=bool(self.dry_run))
            show_org_summary(report)
            if self.dry_run:
                self.report({"INFO"}, "Spawn dry-run complete")
            else:
                self.report({"INFO"}, "Spawn Scene Structure finished")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Spawn Scene Structure failed: {e}")
            return {"CANCELLED"}
