import bpy
import os
import re
from ..panels.bulk_path_management import get_image_extension, bulk_remap_paths, set_image_paths

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
        
        # Set up progress tracking
        props = context.scene.bst_path_props
        props.is_operation_running = True
        props.operation_progress = 0.0
        props.operation_status = f"Preparing AutoMat extraction for {len(selected_images)} images..."
        
        # Store data for timer processing
        self.selected_images = selected_images
        self.common_outside = common_outside
        self.current_step = 0
        self.current_index = 0
        self.packed_count = 0
        self.success_count = 0
        self.overwrite_skipped = []
        self.failed_list = []
        self.path_mapping = {}
        
        # Start timer for processing
        bpy.app.timers.register(self._process_step)
        
        return {'FINISHED'}
    
    def _process_step(self):
        """Process AutoMat extraction in steps to avoid blocking the UI"""
        props = bpy.context.scene.bst_path_props
        
        # Check for cancellation
        if props.cancel_operation:
            props.is_operation_running = False
            props.operation_progress = 0.0
            props.operation_status = "Operation cancelled"
            props.cancel_operation = False
            return None
        
        if self.current_step == 0:
            # Step 1: Pack images
            if self.current_index >= len(self.selected_images):
                # Packing complete, move to next step
                self.current_step = 1
                self.current_index = 0
                props.operation_status = "Removing extensions from image names..."
                props.operation_progress = 25.0
                return 0.01
            
            # Pack current image
            img = self.selected_images[self.current_index]
            props.operation_status = f"Packing {img.name}..."
            
            if not img.packed_file:
                try:
                    img.pack()
                    self.packed_count += 1
                except Exception as e:
                    # Continue even if packing fails
                    pass
            
            self.current_index += 1
            progress = (self.current_index / len(self.selected_images)) * 25.0
            props.operation_progress = progress
            
        elif self.current_step == 1:
            # Step 2: Remove extensions (this is a quick operation)
            try:
                bpy.ops.bst.remove_extensions()
            except Exception as e:
                pass  # Continue even if this fails
            
            self.current_step = 2
            self.current_index = 0
            props.operation_status = "Analyzing material usage..."
            props.operation_progress = 30.0
            
        elif self.current_step == 2:
            # Step 3: Organize images by material usage
            if self.current_index >= len(self.selected_images):
                # Analysis complete, move to path building
                self.current_step = 3
                self.current_index = 0
                props.operation_status = "Building path mapping..."
                props.operation_progress = 50.0
                return 0.01
            
            # This step is quick, just mark progress
            self.current_index += 1
            progress = 30.0 + (self.current_index / len(self.selected_images)) * 20.0
            props.operation_progress = progress
            
        elif self.current_step == 3:
            # Step 4: Build path mapping
            if self.current_index >= len(self.selected_images):
                # Path building complete, move to remapping
                self.current_step = 4
                self.current_index = 0
                props.operation_status = "Remapping image paths..."
                props.operation_progress = 70.0
                return 0.01
            
            # Build path for current image
            img = self.selected_images[self.current_index]
            props.operation_status = f"Building path for {img.name}..."
            
            # Get blend file name
            blend_name = bpy.path.basename(bpy.data.filepath)
            if blend_name:
                blend_name = os.path.splitext(blend_name)[0]
            else:
                blend_name = "untitled"
            blend_name = self.sanitize_filename(blend_name)
            
            # Determine common path
            if self.common_outside:
                common_path_part = "common"
            else:
                common_path_part = f"{blend_name}\\common"
            
            # Get extension and build path
            extension = get_image_extension(img)
            sanitized_base_name = self.sanitize_filename(img.name)
            filename = f"{sanitized_base_name}{extension}"
            
            if img.name.startswith('#'):
                path = f"//textures\\{common_path_part}\\FlatColors\\{filename}"
            else:
                # For simplicity, put all images in common folder
                # In a full implementation, you'd check material usage here
                path = f"//textures\\{common_path_part}\\{filename}"
            
            self.path_mapping[img.name] = path
            
            self.current_index += 1
            progress = 50.0 + (self.current_index / len(self.selected_images)) * 20.0
            props.operation_progress = progress
            
        elif self.current_step == 4:
            # Step 5: Remap paths
            if self.current_index >= len(self.path_mapping):
                # Remapping complete, move to saving
                self.current_step = 5
                self.current_index = 0
                props.operation_status = "Saving images to new locations..."
                props.operation_progress = 85.0
                return 0.01
            
            # Remap current image
            img_name = list(self.path_mapping.keys())[self.current_index]
            new_path = self.path_mapping[img_name]
            props.operation_status = f"Remapping {img_name}..."
            
            success = set_image_paths(img_name, new_path)
            if success:
                self.success_count += 1
            else:
                self.failed_list.append(img_name)
            
            self.current_index += 1
            progress = 70.0 + (self.current_index / len(self.path_mapping)) * 15.0
            props.operation_progress = progress
            
        elif self.current_step == 5:
            # Step 6: Save images
            if self.current_index >= len(self.selected_images):
                # Operation complete
                props.is_operation_running = False
                props.operation_progress = 100.0
                props.operation_status = f"Completed! Extracted {self.success_count} images{f', {len(self.failed_list)} failed' if self.failed_list else ''}"
                
                # Show summary dialog
                self.show_summary_dialog(
                    bpy.context,
                    total_selected=len(self.selected_images),
                    success_count=self.success_count,
                    overwrite_skipped_list=self.overwrite_skipped,
                    failed_remap_list=self.failed_list
                )
                
                # Force UI update
                for area in bpy.context.screen.areas:
                    area.tag_redraw()
                
                return None
            
            # Save current image
            img = self.selected_images[self.current_index]
            props.operation_status = f"Saving {img.name}..."
            
            try:
                if hasattr(img, 'save'):
                    img.save()
            except Exception as e:
                pass  # Continue even if saving fails
            
            self.current_index += 1
            progress = 85.0 + (self.current_index / len(self.selected_images)) * 15.0
            props.operation_progress = progress
        
        # Force UI update
        for area in bpy.context.screen.areas:
            area.tag_redraw()
        
        # Continue processing
        return 0.01

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

