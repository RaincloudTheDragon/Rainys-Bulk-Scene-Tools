bl_info = {
    "name": "Raincloud's Bulk Scene Tools",
    "author": "RaincloudTheDragon",
    "version": (0, 2, 1),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Edit Tab",
    "description": "Tools for bulk operations on scene data",
    "warning": "",
    "doc_url": "https://github.com/RaincloudTheDragon/Rainys-Bulk-Scene-Tools",
    "category": "Scene",
    "maintainer": "RaincloudTheDragon",
    "support": "COMMUNITY",
}

import bpy # type: ignore
from . import bulk_viewport_display
from . import bulk_data_remap

# Main panel for Bulk Scene Tools
class VIEW3D_PT_BulkSceneTools(bpy.types.Panel):
    """Bulk Scene Tools Panel"""
    bl_label = "Bulk Scene Tools"
    bl_idname = "VIEW3D_PT_bulk_scene_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Tools for bulk operations on scene data")

# List of all classes in this module
classes = (
    VIEW3D_PT_BulkSceneTools,
)

def register():
    # Register classes from this module
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register modules
    bulk_viewport_display.register()
    bulk_data_remap.register()

def unregister():
    # Unregister modules
    bulk_data_remap.unregister()
    bulk_viewport_display.unregister()
    
    # Unregister classes from this module
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
