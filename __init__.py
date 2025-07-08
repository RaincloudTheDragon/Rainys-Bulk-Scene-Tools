bl_info = {
    "name": "Raincloud's Bulk Scene Tools",
    "author": "RaincloudTheDragon",
    "version": (0, 8, 0),
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
from .ops.AutoMatExtractor import AutoMatExtractor, AUTOMAT_OT_summary_dialog
from .ops.Rename_images_by_mat import Rename_images_by_mat, RENAME_OT_summary_dialog
from .ops.FreeGPU import BST_FreeGPU
from .ops import ghost_buster
from . import updater

# Addon preferences class for update settings
class BST_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    # Auto Updater settings
    check_for_updates: BoolProperty(
        name="Check for Updates on Startup",
        description="Automatically check for new versions of the addon when Blender starts",
        default=True,
    )
    
    update_check_interval: IntProperty(  # type: ignore
        name="Update check interval (hours)",
        description="How often to check for updates (in hours)",
        default=24,
        min=1,
        max=168  # 1 week max
    )

    # AutoMat Extractor settings
    automat_common_outside_blend: BoolProperty(
        name="Place 'common' folder outside 'blend' folder",
        description="If enabled, the 'common' folder for shared textures will be placed directly in 'textures/'. If disabled, it will be placed inside 'textures/<blend_name>/'",
        default=False,
    )

    def draw(self, context):
        layout = self.layout

        # Custom updater UI
        box = layout.box()
        box.label(text="Update Settings")
        row = box.row()
        row.prop(self, "check_for_updates")
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

        # AutoMat Extractor settings
        box = layout.box()
        box.label(text="AutoMat Extractor Settings")
        row = box.row()
        row.prop(self, "automat_common_outside_blend")

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
    AutoMatExtractor,
    AUTOMAT_OT_summary_dialog,
    Rename_images_by_mat,
    RENAME_OT_summary_dialog,
    BST_FreeGPU,
)

def register():
    # Register classes from this module (do this first to ensure preferences are available)
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Print debug info about preferences
    try:
        prefs = bpy.context.preferences.addons.get(__package__)
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
    ghost_buster.register()
    
    # Add keybind for Free GPU (global context)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        # Use Screen keymap for global shortcuts that work everywhere
        km = kc.keymaps.new(name='Screen', space_type='EMPTY')
        kmi = km.keymap_items.new('bst.free_gpu', 'M', 'PRESS', ctrl=True, alt=True, shift=True)
        # Store keymap for cleanup
        addon_keymaps = getattr(bpy.types.Scene, '_bst_keymaps', [])
        addon_keymaps.append((km, kmi))
        bpy.types.Scene._bst_keymaps = addon_keymaps

def unregister():
    # Remove keybinds
    addon_keymaps = getattr(bpy.types.Scene, '_bst_keymaps', [])
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except:
            pass
    addon_keymaps.clear()
    if hasattr(bpy.types.Scene, '_bst_keymaps'):
        delattr(bpy.types.Scene, '_bst_keymaps')
    
    # Unregister modules
    try:
        ghost_buster.unregister()
    except Exception:
        pass
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
