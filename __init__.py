bl_info = {
    "name": "Raincloud's Bulk Scene Tools",
    "author": "RaincloudTheDragon",
    "version": (0, 4, 0),
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
from .panels import bulk_viewport_display
from .panels import bulk_data_remap
from .panels import bulk_path_management
from .panels import bulk_scene_general
from . import updater

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
    ) # type: ignore
    updater_interval_days: IntProperty(
        name="Days",
        description="Number of days between update checks",
        default=0,
        min=0,
        max=31
    ) # type: ignore
    updater_interval_hours: IntProperty(
        name="Hours",
        description="Number of hours between update checks",
        default=24,
        min=0,
        max=23
    ) # type: ignore
    updater_interval_minutes: IntProperty(
        name="Minutes",
        description="Number of minutes between update checks",
        default=0,
        min=0,
        max=59
    ) # type: ignore

    def draw(self, context):
        layout = self.layout

        # Custom updater UI
        box = layout.box()
        box.label(text="Update Settings")
        row = box.row()
        row.prop(self, "auto_check_update")
        row = box.row()
        row.prop(self, "update_check_interval")
        
        # Check for updates button
        row = box.row()
        row.operator("bst.check_for_updates", icon='FILE_REFRESH')
        
        # Show update status if available
        if updater.UpdaterState.update_available:
            box.label(text=f"Update available: v{updater.UpdaterState.update_version}")
            row = box.row()
            row.operator("bst.install_update", icon='IMPORT')
            row = box.row()
            row.operator("wm.url_open", text="Download Update").url = updater.UpdaterState.update_download_url
        elif updater.UpdaterState.checking_for_updates:
            box.label(text="Checking for updates...")
        elif updater.UpdaterState.error_message:
            box.label(text=f"Error checking for updates: {updater.UpdaterState.error_message}")

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
    # Register classes from this module (do this first to ensure preferences are available)
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Print debug info about preferences
    try:
        prefs = bpy.context.preferences.addons.get("rainys_bulk_scene_tools")
        if prefs:
            print(f"Addon preferences registered successfully: {prefs}")
        else:
            print("WARNING: Addon preferences not found after registration!")
            print(f"Available addons: {', '.join(bpy.context.preferences.addons.keys())}")
    except Exception as e:
        print(f"Error accessing preferences: {str(e)}")
    
    # Register the updater module
    updater.register()
    
    # Check for updates on startup
    if hasattr(updater, "check_for_updates"):
        updater.check_for_updates()
    
    # Register modules
    bulk_scene_general.register()
    bulk_viewport_display.register()
    bulk_data_remap.register()
    bulk_path_management.register()

def unregister():
    # Unregister modules
    try:
        bulk_path_management.unregister()
    except Exception:
        pass
    try:
        bulk_data_remap.unregister()
    except Exception:
        pass
    try:
        bulk_viewport_display.unregister()
    except Exception:
        pass
    try:
        bulk_scene_general.unregister()
    except Exception:
        pass
    # Unregister the updater module
    try:
        updater.unregister()
    except Exception:
        pass
    # Unregister classes from this module
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

if __name__ == "__main__":
    register()
