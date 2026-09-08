"""Spawn / deterministic organize into Env · Animation · Lgt (#18)."""

import bpy
from bpy.props import BoolProperty

from ..utils.outliner_org import load_template, run_org
from .org_scene_structure import _get_org_template_path, show_org_summary


class SpawnSceneStructure(bpy.types.Operator):
    """
    Ensure scene structure and run deterministic outliner org.

    Same pipeline as Organize into Scene Structure (aliases, merges, props,
    override nests, Env-first order). Kept as the primary Scene Structure button.
    """

    bl_idname = "bst.spawn_scene_structure"
    bl_label = "Spawn Scene Structure"
    bl_options = {"REGISTER", "UNDO"}

    dry_run: BoolProperty(
        name="Dry Run",
        description="Preview organization without modifying the scene",
        default=False,
    )

    def execute(self, context):
        try:
            template = load_template(_get_org_template_path())
            report = run_org(context, template=template, dry_run=bool(self.dry_run))
            show_org_summary(report)
            if self.dry_run:
                self.report({"INFO"}, "Spawn/org dry-run complete")
            else:
                self.report({"INFO"}, "Spawn Scene Structure finished")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, f"Spawn Scene Structure failed: {e}")
            return {"CANCELLED"}
