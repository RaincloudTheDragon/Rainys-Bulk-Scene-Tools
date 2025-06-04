import bpy
from ..scripts.NoSubdiv import NoSubdiv
from ..scripts.remove_custom_split_normals import RemoveCustomSplitNormals
from ..scripts.create_ortho_camera import CreateOrthoCamera

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
        
        # Add NoSubdiv button
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

# List of all classes in this module
classes = (
    BulkSceneGeneral,
    NoSubdiv,  # Add NoSubdiv operator class
    RemoveCustomSplitNormals,
    CreateOrthoCamera,
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