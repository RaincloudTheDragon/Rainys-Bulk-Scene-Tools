bl_info = {
    "name": "Raincloud's Bulk Scene Tools",
    "author": "RaincloudTheDragon",
    "version": (0, 2, 2),
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
from . import updater
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

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        col = box.column()

        row = col.row()
        row.scale_y = 1.2
        row.prop(self, "auto_check_update")

        row = col.row()
        row.prop(self, "update_check_interval")

        # Show current version
        box = layout.box()
        col = box.column()
        row = col.row()
        row.label(text=f"Current Version: {updater.get_current_version()}")  # type: ignore

        if updater.UpdaterState.checking_for_updates:
            row = col.row()
            row.label(text="Checking for updates...", icon='SORTTIME')
        elif updater.UpdaterState.error_message:
            row = col.row()
            row.label(text=f"Error: {updater.UpdaterState.error_message}", icon='ERROR')  # type: ignore
        elif updater.UpdaterState.update_available:
            row = col.row()
            row.label(text=f"Update available: {updater.UpdaterState.update_version}", icon='PACKAGE')  # type: ignore

            row = col.row()
            row.scale_y = 1.2
            op = row.operator("bst.install_update", text="Install Update", icon='IMPORT')
        else:
            row = col.row()
            if updater.UpdaterState.last_check_time > 0:
                check_time = datetime.datetime.fromtimestamp(updater.UpdaterState.last_check_time).strftime('%Y-%m-%d %H:%M')  # type: ignore
                row.label(text=f"Addon is up to date (last checked: {check_time})", icon='CHECKMARK')  # type: ignore
            else:
                row.label(text="Click to check for updates", icon='URL')

        row = col.row()
        row.operator("bst.check_for_updates", text="Check Now", icon='FILE_REFRESH')

# Operation to check for updates
class BST_OT_check_for_updates(Operator):
    bl_idname = "bst.check_for_updates"
    bl_label = "Check for Updates"
    bl_description = "Check if a new version is available"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        # Set the global update interval from the preferences
        prefs = context.preferences.addons[__name__].preferences
        updater.UPDATE_CHECK_INTERVAL = prefs.update_check_interval * 3600  # Convert to seconds

        # Force a check for updates (not async so we can show results immediately)
        success = updater.check_for_updates(async_check=False)

        if success:
            if updater.UpdaterState.update_available:
                self.report({'INFO'}, f"Update available: {updater.UpdaterState.update_version}")  # type: ignore
            else:
                self.report({'INFO'}, "Addon is up to date")
        else:
            self.report({'ERROR'}, f"Error checking for updates: {updater.UpdaterState.error_message}")  # type: ignore

        return {'FINISHED'}

# Operation to install updates
class BST_OT_install_update(Operator):
    bl_idname = "bst.install_update"
    bl_label = "Install Update"
    bl_description = "Download and install the latest version"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        self.report({'INFO'}, "Downloading and installing update...")
        success = updater.download_and_install_update()

        if success:
            self.report({'INFO'}, f"Successfully updated to version {updater.UpdaterState.update_version}")  # type: ignore
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, f"Error installing update: {updater.UpdaterState.error_message}")  # type: ignore
            return {'CANCELLED'}

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
    BST_OT_check_for_updates,
    BST_OT_install_update,
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
