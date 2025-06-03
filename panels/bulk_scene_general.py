import bpy
from ..scripts.NoSubdiv import NoSubdiv
from ..scripts.remove_custom_split_normals import RemoveCustomSplitNormals

class VIEW3D_PT_BulkSceneGeneral(bpy.types.Panel):
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
        row = box.row(align=True)
        row.operator("bst.no_subdiv", text="No Subdiv", icon='MOD_SUBSURF')
        row.operator("bst.remove_custom_split_normals", text="Remove Custom Split Normals", icon='X')

# List of all classes in this module
classes = (
    VIEW3D_PT_BulkSceneGeneral,
    NoSubdiv,  # Add NoSubdiv operator class
    RemoveCustomSplitNormals,
)

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass