import bpy
from ..ops.NoSubdiv import NoSubdiv
from ..ops.remove_custom_split_normals import RemoveCustomSplitNormals
from ..ops.create_ortho_camera import CreateOrthoCamera
from ..ops.spawn_scene_structure import SpawnSceneStructure
from ..ops.delete_single_keyframe_actions import DeleteSingleKeyframeActions
from ..ops.find_material_users import FindMaterialUsers
from ..ops.remove_unused_material_slots import RemoveUnusedMaterialSlots

class BulkSceneGeneral(bpy.types.Panel):
    """Bulk Scene General Panel"""
    bl_label = "Scene General"
    bl_idname = "VIEW3D_PT_bulk_scene_general"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 0  # This will make it appear at the very top of the main panel
    
    def draw(self, context):
        layout = self.layout
        
        # Scene Structure section
        box = layout.box()
        box.label(text="Scene Structure")
        row = box.row()
        row.scale_y = 1.2
        row.operator("bst.spawn_scene_structure", text="Spawn Scene Structure", icon='OUTLINER_COLLECTION')
        
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
        row = box.row(align=True)
        row.operator("bst.find_material_users", text="Find Material Users", icon='VIEWZOOM')

        # Animation Data section
        box = layout.box()
        box.label(text="Animation Data")
        row = box.row(align=True)
        row.operator("bst.delete_single_keyframe_actions", text="Delete Single Keyframe Actions", icon='ANIM_DATA')

# List of all classes in this module
classes = (
    BulkSceneGeneral,
    NoSubdiv,  # Add NoSubdiv operator class
    RemoveCustomSplitNormals,
    CreateOrthoCamera,
    SpawnSceneStructure,
    DeleteSingleKeyframeActions,
    FindMaterialUsers,
    RemoveUnusedMaterialSlots,
)

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Register the window manager property for the checkbox
    bpy.types.WindowManager.bst_no_subdiv_only_selected = bpy.props.BoolProperty(
        name="Selected Only",
        description="Apply only to selected objects",
        default=True
    )

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    # Unregister the window manager property
    if hasattr(bpy.types.WindowManager, "bst_no_subdiv_only_selected"):
        del bpy.types.WindowManager.bst_no_subdiv_only_selected