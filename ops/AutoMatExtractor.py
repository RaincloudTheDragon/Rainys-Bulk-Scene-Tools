import bpy
import os
import re
from ..panels.bulk_path_management import get_image_extension, bulk_remap_paths

class AUTOMAT_OT_summary_dialog(bpy.types.Operator):
    """Show AutoMat Extractor operation summary"""
    bl_idname = "bst.automat_summary_dialog"
    bl_label = "AutoMat Extractor Summary"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    # Properties to store summary data
    total_selected: bpy.props.IntProperty(default=0)
    success_count: bpy.props.IntProperty(default=0)
    overwrite_skipped_count: bpy.props.IntProperty(default=0)
    failed_remap_count: bpy.props.IntProperty(default=0)
    
    overwrite_details: bpy.props.StringProperty(default="")
    failed_remap_details: bpy.props.StringProperty(default="")
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="AutoMat Extractor - Summary", icon='INFO')
        layout.separator()
        
        box = layout.box()
        col = box.column(align=True)
        col.label(text=f"Total selected images: {self.total_selected}")
        col.label(text=f"Successfully extracted: {self.success_count}", icon='CHECKMARK')
        
        if self.overwrite_skipped_count > 0:
            col.label(text=f"Skipped to prevent overwrite: {self.overwrite_skipped_count}", icon='ERROR')
        if self.failed_remap_count > 0:
            col.label(text=f"Failed to remap (path issue): {self.failed_remap_count}", icon='ERROR')

        if self.overwrite_details:
            layout.separator()
            box = layout.box()
            box.label(text="Overwrite Conflicts (Skipped):", icon='FILE_TEXT')
            for line in self.overwrite_details.split('\n'):
                if line.strip():
                    box.label(text=line)

        if self.failed_remap_details:
            layout.separator()
            box = layout.box()
            box.label(text="Failed Remaps:", icon='FILE_TEXT')
            for line in self.failed_remap_details.split('\n'):
                if line.strip():
                    box.label(text=line)

    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=500)

class AutoMatExtractor(bpy.types.Operator):
    bl_idname = "bst.automatextractor"
    bl_label = "AutoMatExtractor"
    bl_description = "Pack selected images and extract them with organized paths by blend file and material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get addon preferences
        addon_name = __package__.split('.')[0]
        prefs = context.preferences.addons.get(addon_name).preferences
        common_outside = prefs.automat_common_outside_blend
        
        # Get selected images
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        
        if not selected_images:
            self.report({'WARNING'}, "No images selected for extraction")
            return {'CANCELLED'}
        
        # Get blend file name (without extension)
        blend_name = bpy.path.basename(bpy.data.filepath)
        if blend_name:
            blend_name = os.path.splitext(blend_name)[0]
        else:
            blend_name = "untitled"
        
        # Sanitize blend name for filesystem
        blend_name = self.sanitize_filename(blend_name)
        
        # Determine common path based on preference
        if common_outside:
            common_path_part = "common"
        else:
            common_path_part = f"{blend_name}\\common"
            
        # Step 1: Pack all selected images (if possible)
        packed_count = 0
        for img in selected_images:
            if not img.packed_file:
                try:
                    img.pack()
                    packed_count += 1
                except Exception as e:
                    # Continue even if packing fails - we can still save to new paths
                    pass
        
        if packed_count > 0:
            self.report({'INFO'}, f"Packed {packed_count} images")
        
        # Step 2: Remove extensions from selected images
        try:
            bpy.ops.bst.remove_extensions()
            self.report({'INFO'}, "Removed extensions from image names")
        except Exception as e:
            self.report({'WARNING'}, f"Failed to remove extensions: {str(e)}")
        
        # Step 3: Organize images by material usage
        image_to_materials = self.get_image_material_mapping(selected_images)
        
        # Step 4: Build path mapping for bulk remap
        path_mapping = {}
        overwrite_skipped = []
        existing_paths = set()
        
        for img in selected_images:
            # Get the proper file extension
            extension = get_image_extension(img)
            
            # Sanitize the base name for the file path
            sanitized_base_name = self.sanitize_filename(img.name)
            filename = f"{sanitized_base_name}{extension}"

            # Special handling for flat color textures (names starting with #)
            if img.name.startswith('#'):
                path = f"//textures\\{common_path_part}\\FlatColors\\{filename}"
            else:
                materials = image_to_materials.get(img.name, [])
                
                if len(materials) == 0 or len(materials) > 1:
                    # Unused or shared images go to the common folder
                    path = f"//textures\\{common_path_part}\\{filename}"
                else: # Single material usage
                    material_name = self.sanitize_filename(materials[0])
                    path = f"//textures\\{blend_name}\\{material_name}\\{filename}"

            # Check for potential overwrites
            absolute_path = bpy.path.abspath(path)
            if absolute_path.lower() in existing_paths:
                overwrite_skipped.append((img.name, path))
                continue

            existing_paths.add(absolute_path.lower())
            path_mapping[img.name] = path
            
        # Step 5: Use PathMan's bulk remap function
        success_count, failed_list = bulk_remap_paths(path_mapping)
        
        # Step 6: Save all images to their new locations
        if success_count > 0:
            try:
                bpy.ops.bst.save_all_images()
            except Exception as e:
                self.report({'WARNING'}, f"Failed to save images: {str(e)}")
        
        # Step 7: Show summary dialog
        self.show_summary_dialog(
            context,
            total_selected=len(selected_images),
            success_count=success_count,
            overwrite_skipped_list=overwrite_skipped,
            failed_remap_list=failed_list
        )
        
        return {'FINISHED'}

    def show_summary_dialog(self, context, total_selected, success_count, overwrite_skipped_list, failed_remap_list):
        """Show a popup dialog with the extraction summary"""
        overwrite_details = ""
        if overwrite_skipped_list:
            for name, path in overwrite_skipped_list:
                overwrite_details += f"'{name}' -> '{path}'\n"

        failed_remap_details = ""
        if failed_remap_list:
            for name, path in failed_remap_list:
                failed_remap_details += f"'{name}' -> '{path}'\n"

        bpy.ops.bst.automat_summary_dialog('INVOKE_DEFAULT',
            total_selected=total_selected,
            success_count=success_count,
            overwrite_skipped_count=len(overwrite_skipped_list),
            failed_remap_count=len(failed_remap_list),
            overwrite_details=overwrite_details.strip(),
            failed_remap_details=failed_remap_details.strip()
        )

    def sanitize_filename(self, filename):
        """Sanitize filename/folder name for filesystem compatibility"""
        # First, remove potential file extensions, including numerical ones like .001
        base_name = re.sub(r'\.\d{3}$', '', filename) # Remove .001, .002 etc.
        base_name = os.path.splitext(base_name)[0] # Remove standard extensions
        
        # Remove or replace invalid characters for Windows/Mac/Linux
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', base_name)
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        # Ensure it's not empty
        if not sanitized:
            sanitized = "unnamed"
        return sanitized
    
    def get_image_material_mapping(self, images):
        """Create mapping of image names to materials that use them"""
        image_to_materials = {}
        
        # Initialize mapping
        for img in images:
            image_to_materials[img.name] = []
        
        # Check all materials for image usage
        for material in bpy.data.materials:
            if not material.use_nodes:
                continue
                
            material_images = set()
            
            # Find all image texture nodes in this material
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    material_images.add(node.image.name)
            
            # Add this material to each image's usage list
            for img_name in material_images:
                if img_name in image_to_materials:
                    image_to_materials[img_name].append(material.name)
        
        return image_to_materials

# Must register the new dialog class as well
classes = (
    AUTOMAT_OT_summary_dialog,
    AutoMatExtractor,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

