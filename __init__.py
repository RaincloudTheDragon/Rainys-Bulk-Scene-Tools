bl_info = {
    "name": "Raincloud's Bulk Scene Tools",
    "author": "RaincloudTheDragon",
    "version": (0, 3, 0),
    "blender": (4, 4, 1),
    "location": "View3D > Sidebar > Edit Tab",
    "description": "Tools for bulk operations on scene data",
    "warning": "",
    "doc_url": "https://github.com/RaincloudTheDragon/Rainys-Bulk-Scene-Tools",
    "category": "Scene",
    "maintainer": "RaincloudTheDragon",
    "support": "COMMUNITY",
}

import bpy # type: ignore
from bpy.types import AddonPreferences, Operator, Panel # type: ignore
from bpy.props import BoolProperty, IntProperty # type: ignore
from . import bulk_viewport_display
from . import bulk_data_remap
from . import bulk_path_management
# Import updater ops
from . import addon_updater_ops
from . import updater_cgc
import datetime

# Addon preferences class for update settings
class BST_AddonPreferences(AddonPreferences):
    bl_idname = __name__

    # Updater preferences
    auto_check_update: BoolProperty(  # type: ignore
        name="Auto-check for Updates",
        description="Automatically check for updates when Blender starts",
        default=True
    )

    update_check_interval: IntProperty(  # type: ignore
        name="Update check interval (hours)",
        description="How often to check for updates (in hours)",
        default=24,
        min=1,
        max=168  # 1 week max
    )

    updater_interval_months: IntProperty(
        name="Months",
        description="Number of months between update checks",
        default=0,
        min=0,
        max=12
    )
    updater_interval_days: IntProperty(
        name="Days",
        description="Number of days between update checks",
        default=0,
        min=0,
        max=31
    )
    updater_interval_hours: IntProperty(
        name="Hours",
        description="Number of hours between update checks",
        default=24,
        min=0,
        max=23
    )
    updater_interval_minutes: IntProperty(
        name="Minutes",
        description="Number of minutes between update checks",
        default=0,
        min=0,
        max=59
    )

    def draw(self, context):
        layout = self.layout

        # Call the updater draw function
        addon_updater_ops.update_settings_ui(self, context)

# Main panel for Bulk Scene Tools
class VIEW3D_PT_BulkSceneTools(Panel):
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
    BST_AddonPreferences,
)

def register():
    # Configure and register the updater
    updater_cgc.configure_updater()
    addon_updater_ops.register(bl_info)
    
    # Register classes from this module
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register modules
    bulk_viewport_display.register()
    bulk_data_remap.register()
    bulk_path_management.register()

def unregister():
    # Unregister modules
    bulk_path_management.unregister()
    bulk_data_remap.unregister()
    bulk_viewport_display.unregister()
    
    # Unregister classes from this module
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Unregister the updater
    addon_updater_ops.unregister()

if __name__ == "__main__":
    register()
