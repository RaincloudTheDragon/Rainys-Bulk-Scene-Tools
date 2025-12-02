import bpy # type: ignore
from bpy.types import AddonPreferences, Panel # type: ignore
from bpy.props import BoolProperty # type: ignore
from .panels import bulk_viewport_display
from .panels import bulk_data_remap
from .panels import bulk_path_management
from .panels import bulk_scene_general
from .ops.AutoMatExtractor import AutoMatExtractor, AUTOMAT_OT_summary_dialog
from .ops.Rename_images_by_mat import Rename_images_by_mat, RENAME_OT_summary_dialog
from .ops.FreeGPU import BST_FreeGPU
from .ops import ghost_buster
from . import rainys_repo_bootstrap

# Addon preferences class for update settings
class BST_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    # AutoMat Extractor settings
    automat_common_outside_blend: BoolProperty(
        name="Place 'common' folder outside 'blend' folder",
        description="If enabled, the 'common' folder for shared textures will be placed directly in 'textures/'. If disabled, it will be placed inside 'textures/<blend_name>/'",
        default=False,
    )

    def draw(self, context):
        layout = self.layout

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

    rainys_repo_bootstrap.register()

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
    rainys_repo_bootstrap.unregister()
    # Unregister classes from this module
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass

if __name__ == "__main__":
    register()
