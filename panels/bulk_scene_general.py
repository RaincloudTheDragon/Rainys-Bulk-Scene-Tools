import bpy
from ..ops.NoSubdiv import NoSubdiv
from ..ops.remove_custom_split_normals import RemoveCustomSplitNormals
from ..ops.create_ortho_camera import CreateOrthoCamera
from ..ops.spawn_scene_structure import SpawnSceneStructure
from ..ops.org_scene_structure import OrgSceneStructure, RBST_Org_OT_summary_dialog
from ..ops.capture_outliner_template import CaptureOutlinerTemplate
from ..ops.org_scene_structure_llm import (
    OrgSceneStructureLLM,
    DownloadOrgModel,
    InstallOrgRuntime,
)
from ..ops.delete_single_keyframe_actions import DeleteSingleKeyframeActions
from ..ops.remove_unused_material_slots import RemoveUnusedMaterialSlots
from ..ops.convert_relations_to_constraint import ConvertRelationsToConstraint
from ..ops.remove_action_fake_users import RemoveActionFakeUsers
from ..ops.white_world import WhiteWorld
from ..utils import compat
from ..utils.org_runtime import org_runtime_ready


def _addon_prefs(context):
    pkg = __package__.rsplit(".", 1)[0] if __package__ else ""
    addon = context.preferences.addons.get(pkg)
    return addon.preferences if addon else None


class RBST_SceneGen_PT_BulkSceneGeneral(bpy.types.Panel):
    """Bulk Scene General Panel"""
    bl_label = "Scene General"
    bl_idname = "RBST_SceneGen_PT_bulk_scene_general"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 0  # This will make it appear at the very top of the main panel
    
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        prefs = _addon_prefs(context)

        # Scene Structure section
        box = layout.box()
        box.label(text="Scene Structure")
        row = box.row(align=True)
        row.prop(wm, "bst_org_dry_run", text="Dry Run")
        row = box.row()
        row.scale_y = 1.2
        op = row.operator(
            "bst.spawn_scene_structure",
            text="Spawn Scene Structure",
            icon="OUTLINER_COLLECTION",
        )
        op.dry_run = wm.bst_org_dry_run

        row = box.row()
        row.scale_y = 1.1
        llm_row = row.row()
        has_runtime = False
        if prefs is not None:
            pkg = __package__.rsplit(".", 1)[0] if __package__ else ""
            has_runtime = org_runtime_ready(pkg, prefs) or getattr(
                prefs, "org_llm_allow_heuristic", False
            )
        llm_row.enabled = has_runtime and not getattr(prefs, "is_inferring_org", False)
        op_llm = llm_row.operator(
            "bst.org_scene_structure_llm",
            text="Organize with Local Model…",
            icon="WORDWRAP_ON",
        )
        op_llm.dry_run = wm.bst_org_dry_run

        row = box.row(align=True)
        row.operator(
            "bst.capture_outliner_template",
            text="Capture Template from this File",
            icon="FILE_TICK",
        )

        row = box.row(align=True)
        row.operator("bst.white_world", text="White World", icon='WORLD')
        
        # Mesh section
        box = layout.box()
        box.label(text="Mesh")
        # Add checkbox for only_selected property
        row = box.row()
        row.prop(context.window_manager, "bst_no_subdiv_only_selected", text="Selected Only")
        row = box.row(align=True)
        row.operator("bst.no_subdiv", text="No Subdiv", icon='MOD_SUBSURF').only_selected = context.window_manager.bst_no_subdiv_only_selected
        row.operator("bst.remove_custom_split_normals", text="Remove Custom Split Normals", icon='X').only_selected = context.window_manager.bst_no_subdiv_only_selected

        row = box.row(align=True)
        row.operator("bst.create_ortho_camera", text="Create Ortho Camera", icon='OUTLINER_DATA_CAMERA')
        row = box.row(align=True)
        row.operator("bst.free_gpu", text="Free GPU", icon='MEMORY')

        # Materials section
        box = layout.box()
        box.label(text="Materials")
        row = box.row(align=True)
        row.operator("bst.remove_unused_material_slots", text="Remove Unused Material Slots", icon='MATERIAL')

        # Animation Data section
        box = layout.box()
        box.label(text="Animation Data")
        row = box.row(align=True)
        row.operator("bst.remove_action_fake_users", text="Remove Action FU", icon='FAKE_USER_OFF')
        row = box.row(align=True)
        row.operator("bst.delete_single_keyframe_actions", text="Delete Single Keyframe Actions", icon='ANIM_DATA')
        row = box.row(align=True)
        row.operator("bst.convert_relations_to_constraint", text="Convert Relations to Constraint", icon_value=405)

# List of all classes in this module
classes = (
    RBST_SceneGen_PT_BulkSceneGeneral,
    NoSubdiv,
    RemoveCustomSplitNormals,
    CreateOrthoCamera,
    SpawnSceneStructure,
    OrgSceneStructure,
    RBST_Org_OT_summary_dialog,
    CaptureOutlinerTemplate,
    OrgSceneStructureLLM,
    DownloadOrgModel,
    InstallOrgRuntime,
    WhiteWorld,
    DeleteSingleKeyframeActions,
    RemoveUnusedMaterialSlots,
    ConvertRelationsToConstraint,
    RemoveActionFakeUsers,
)

# Registration
def register():
    for cls in classes:
        compat.safe_register_class(cls)
    # Register the window manager property for the checkbox
    bpy.types.WindowManager.bst_no_subdiv_only_selected = bpy.props.BoolProperty(
        name="Selected Only",
        description="Apply only to selected objects",
        default=True
    )
    bpy.types.WindowManager.bst_org_dry_run = bpy.props.BoolProperty(
        name="Dry Run",
        description="Preview outliner organization without modifying the scene",
        default=False,
    )

def unregister():
    for cls in reversed(classes):
        compat.safe_unregister_class(cls)
    if hasattr(bpy.types.WindowManager, "bst_no_subdiv_only_selected"):
        del bpy.types.WindowManager.bst_no_subdiv_only_selected
    if hasattr(bpy.types.WindowManager, "bst_org_dry_run"):
        del bpy.types.WindowManager.bst_org_dry_run
