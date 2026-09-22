import bpy # type: ignore
from bpy.types import AddonPreferences, Panel # type: ignore
from bpy.props import BoolProperty, StringProperty, FloatProperty # type: ignore
from .panels import bulk_viewport_display
from .panels import bulk_data_remap
from .panels import bulk_path_management
from .panels import bulk_scene_general
from .ops.AutoMatExtractor import RBST_AutoMat_OT_AutoMatExtractor, RBST_AutoMat_OT_summary_dialog
from .ops.Rename_images_by_mat import RBST_RenameImg_OT_Rename_images_by_mat, RBST_RenameImg_OT_summary_dialog
from .ops.FreeGPU import RBST_FreeGPU
from . import rainys_repo_bootstrap
from .utils import compat
from .utils.org_runtime import org_runtime_status


def _rbst_persist_prefs_sidecar(self, context):
    """Write reload-safe prefs sidecar after AddonPreferences changes."""
    try:
        from .utils.prefs_sidecar import is_restoring, save_sidecar
        if is_restoring():
            return
        save_sidecar(self)
    except Exception:
        pass


# Addon preferences class for update settings
class RBST_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    # AutoMat Extractor settings
    automat_common_outside_blend: BoolProperty(
        name="Place 'common' folder outside 'blend' folder",
        description="If enabled, the 'common' folder for shared textures will be placed directly in 'textures/'. If disabled, it will be placed inside 'textures/<blend_name>/'",
        default=False,
        update=_rbst_persist_prefs_sidecar,
    )

    # Outliner org (#18)
    org_template_path: StringProperty(
        name="Org Template",
        description="JSON template for outliner organization (create-if-missing folders, excludes)",
        default="",
        subtype="FILE_PATH",
        update=_rbst_persist_prefs_sidecar,
    )
    org_active_template_json: StringProperty(
        name="Active Org Template JSON",
        description="Prefs/sidecar snapshot of the outliner template used across blend files",
        default="",
        options={"HIDDEN"},
        update=_rbst_persist_prefs_sidecar,
    )
    org_active_template_label: StringProperty(
        name="Active Org Template Label",
        description="Short status for the active org template context",
        default="",
        update=_rbst_persist_prefs_sidecar,
    )
    org_gguf_path: StringProperty(
        name="GGUF Path",
        description="Optional explicit path to a local instruct GGUF for org-with-model",
        default="",
        subtype="FILE_PATH",
        update=_rbst_persist_prefs_sidecar,
    )
    org_gguf_filename: StringProperty(
        name="Cached GGUF Filename",
        description="Filename inside the addon org model cache",
        default="",
        update=_rbst_persist_prefs_sidecar,
    )
    org_llama_cli_path: StringProperty(
        name="llama-cli Path",
        description="Optional override for the downloaded llama-cli binary",
        default="",
        subtype="FILE_PATH",
        update=_rbst_persist_prefs_sidecar,
    )
    org_llm_allow_heuristic: BoolProperty(
        name="Allow Basic Rules Without AI",
        description="Enable Organize with Local Model using simple heuristics when llama-cli/GGUF are not installed",
        default=False,
        update=_rbst_persist_prefs_sidecar,
    )
    org_llm_timeout: FloatProperty(
        name="Worker Timeout (s)",
        description="Kill the org worker if it exceeds this many seconds",
        default=120.0,
        min=10.0,
        max=600.0,
        update=_rbst_persist_prefs_sidecar,
    )
    is_downloading_org_model: BoolProperty(
        name="Downloading Org Model",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    org_download_progress: FloatProperty(
        name="Download Progress",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    org_download_label: StringProperty(
        name="Download Label",
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    is_inferring_org: BoolProperty(
        name="Org Inferring",
        default=False,
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def draw(self, context):
        layout = self.layout

        # AutoMat Extractor settings
        box = layout.box()
        box.label(text="AutoMat Extractor Settings")
        row = box.row()
        row.prop(self, "automat_common_outside_blend")

        box = layout.box()
        box.label(text="Outliner Organization")
        box.prop(self, "org_template_path")
        label = (self.org_active_template_label or "").strip()
        if (self.org_active_template_json or "").strip():
            box.label(
                text=f"Active context: {label or 'set'}",
                icon="CHECKMARK",
            )
            box.operator(
                "bst.reset_outliner_template_context",
                text="Reset Active Org Context",
                icon="X",
            )
        else:
            box.label(text="Active context: none (file path / builtin)", icon="INFO")
        box.prop(self, "org_llm_timeout")
        box.prop(self, "org_llm_allow_heuristic")

        status = org_runtime_status(__package__, self)
        if status["ready"]:
            box.label(text="Local runtime: Ready (Vulkan llama-cli + GGUF)", icon="CHECKMARK")
        elif status.get("needs_upgrade"):
            box.label(text="Local runtime: outdated (reinstall for Vulkan GPU)", icon="ERROR")
        elif self.is_downloading_org_model:
            box.label(
                text=self.org_download_label or "Installing… Esc cancels",
                icon="TIME",
            )
            try:
                box.progress(
                    factor=float(self.org_download_progress),
                    type="BAR",
                    text=f"{int(self.org_download_progress * 100)}%",
                )
            except Exception:
                box.prop(self, "org_download_progress", text="Progress", slider=True)
        elif not status["platform_supported"]:
            box.label(text="Local runtime: platform not supported", icon="ERROR")
        else:
            box.label(text="Local runtime: not installed", icon="INFO")

        row = box.row(align=True)
        row.enabled = not self.is_downloading_org_model
        label = (
            "Reinstall Local Org Runtime"
            if status.get("needs_upgrade")
            else "Install Local Org Runtime"
        )
        row.operator("bst.install_org_runtime", text=label, icon="IMPORT")

        # Advanced overrides (collapsed look via secondary props)
        col = box.column(align=True)
        col.enabled = not self.is_downloading_org_model
        col.prop(self, "org_gguf_path")
        col.prop(self, "org_llama_cli_path")

        if self.is_inferring_org:
            box.label(text="Org worker running…", icon="TIME")
# Main panel for Bulk Scene Tools
class VIEW3D_PT_BulkSceneTools(Panel):
    """Bulk Scene Tools Panel"""
    bl_label = "Bulk Scene Tools"
    bl_idname = "VIEW3D_PT_bulk_scene_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'

    def draw_header(self, context):
        # Prefs cog — same pattern as Atomic / Dynamic Library Manager
        layout = self.layout
        layout.operator(
            "preferences.addon_show",
            text="",
            icon="PREFERENCES",
        ).module = __package__

    def draw(self, context):
        layout = self.layout
        layout.label(text="Tools for bulk operations on scene data")

# List of all classes in this module
classes = (
    VIEW3D_PT_BulkSceneTools,
    RBST_AddonPreferences,
    RBST_AutoMat_OT_AutoMatExtractor,
    RBST_AutoMat_OT_summary_dialog,
    RBST_RenameImg_OT_Rename_images_by_mat,
    RBST_RenameImg_OT_summary_dialog,
    RBST_FreeGPU,
)

def register():
    # Register classes from this module (do this first to ensure preferences are available)
    for cls in classes:
        compat.safe_register_class(cls)

    try:
        from .utils.prefs_sidecar import restore_sidecar_into_prefs
        restore_sidecar_into_prefs()
    except Exception as e:
        print(f"[RBST] Prefs sidecar restore failed: {e}")
    
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
    try:
        from .utils.prefs_sidecar import save_sidecar
        save_sidecar()
    except Exception:
        pass
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
        compat.safe_unregister_class(cls)

if __name__ == "__main__":
    register()
