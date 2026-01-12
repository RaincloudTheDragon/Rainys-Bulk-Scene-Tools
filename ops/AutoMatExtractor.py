import bpy
import os
import re
from ..panels.bulk_path_management import (
    get_image_extension,
    bulk_remap_paths,
    set_image_paths,
    ensure_directory_for_path,
)
from ..utils import compat

class RBST_AutoMat_OT_summary_dialog(bpy.types.Operator):
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

class RBST_AutoMat_OT_AutoMatExtractor(bpy.types.Operator):
    bl_idname = "bst.automatextractor"
    bl_label = "AutoMatExtractor"
    bl_description = "Pack selected images and extract them with organized paths by blend file and material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get addon preferences
        addon_name = __package__.split('.')[0]
        addon_entry = context.preferences.addons.get(addon_name)
        prefs = addon_entry.preferences if addon_entry else None
        common_outside = prefs.automat_common_outside_blend if prefs else False
        
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
        self.udim_summary = {
            "found": 0,
            "saved": 0,
        }
        
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
            
            # Get material mapping for all selected images
            if self.current_index == 0:
                self.material_mapping = self.get_image_material_mapping(self.selected_images)
                print(f"DEBUG: Material mapping created for {len(self.selected_images)} images")
            
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
            
            # Get blend file name - respect user preference if set
            if props.use_blend_subfolder:
                blend_name = props.blend_subfolder
                if not blend_name:
                    # Fall back to filename if not specified
                    blend_path = bpy.data.filepath
                    if blend_path:
                        blend_name = os.path.splitext(os.path.basename(blend_path))[0]
                    else:
                        blend_name = "untitled"
            else:
                # Derive from filename
                blend_path = bpy.data.filepath
                if blend_path:
                    blend_name = os.path.splitext(os.path.basename(blend_path))[0]
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
                # Flat colors go to FlatColors subfolder
                base_folder = f"//textures\\{common_path_part}\\FlatColors"
            else:
                # Check material usage for this image
                materials_using_image = self.material_mapping.get(img.name, [])
                
                if not materials_using_image:
                    # No materials found, put in common folder
                    base_folder = f"//textures\\{common_path_part}"
                    print(f"DEBUG: {img.name} - No materials found, using common folder")
                elif len(materials_using_image) == 1:
                    # Used by exactly one material, organize by material name
                    material_name = self.sanitize_filename(materials_using_image[0])
                    base_folder = f"//textures\\{blend_name}\\{material_name}"
                    print(f"DEBUG: {img.name} - Used by {material_name}, organizing by material")
                else:
                    # Used by multiple materials, put in common folder
                    base_folder = f"//textures\\{common_path_part}"
                    print(f"DEBUG: {img.name} - Used by multiple materials: {materials_using_image}, using common folder")
            
            is_udim = self.is_udim_image(img)
            if is_udim:
                udim_mapping = self.build_udim_mapping(base_folder, sanitized_base_name, extension, img)
                self.path_mapping[img.name] = udim_mapping
                self.udim_summary["found"] += 1
                print(f"DEBUG: {img.name} - UDIM detected with {len(udim_mapping.get('tiles', {}))} tiles")
            else:
                path = f"{base_folder}\\{filename}"
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
            mapping_entry = self.path_mapping[img_name]
            props.operation_status = f"Remapping {img_name}..."
            
            if isinstance(mapping_entry, dict) and mapping_entry.get("udim"):
                success = set_image_paths(
                    img_name,
                    mapping_entry.get("template", ""),
                    tile_paths=mapping_entry.get("tiles", {})
                )
            else:
                success = set_image_paths(img_name, mapping_entry)
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
                
                # Console summary
                print(f"\n=== AUTOMAT EXTRACTION SUMMARY ===")
                print(f"Total images processed: {len(self.selected_images)}")
                print(f"Successfully extracted: {self.success_count}")
                print(f"Failed to remap: {len(self.failed_list)}")
                
                # Show organization breakdown
                material_organized = 0
                common_organized = 0
                flat_colors = 0
                
                for img_name, path in self.path_mapping.items():
                    current_path = path["template"] if isinstance(path, dict) else path
                    if "FlatColors" in current_path:
                        flat_colors += 1
                    elif "common" in current_path:
                        common_organized += 1
                    else:
                        material_organized += 1
                
                print(f"\nOrganization breakdown:")
                print(f"  Material-specific folders: {material_organized}")
                print(f"  Common folder: {common_organized}")
                print(f"  Flat colors: {flat_colors}")
                
                # Show material organization details
                if material_organized > 0:
                    print(f"\nMaterial organization details:")
                    material_folders = {}
                    for img_name, path in self.path_mapping.items():
                        if "FlatColors" not in path and "common" not in path:
                            # Extract material name from path
                            if isinstance(path, dict):
                                continue
                            path_parts = path.split('\\')
                            if len(path_parts) >= 3:
                                material_name = path_parts[-2]
                                if material_name not in material_folders:
                                    material_folders[material_name] = []
                                material_folders[material_name].append(img_name)
                    
                    for material_name, images in material_folders.items():
                        print(f"  {material_name}: {len(images)} images")
                
                print(f"=====================================\n")
                if self.udim_summary["found"]:
                    print(f"UDIM images processed: {self.udim_summary['found']} (saved successfully: {self.udim_summary['saved']})")
                
                # Force UI update
                for area in bpy.context.screen.areas:
                    area.tag_redraw()
                
                return None
            
            # Save current image
            img = self.selected_images[self.current_index]
            props.operation_status = f"Saving {img.name}..."
            
            mapping_entry = self.path_mapping.get(img.name)
            if isinstance(mapping_entry, dict) and mapping_entry.get("udim"):
                self.save_udim_image(img, mapping_entry)
            else:
                self.save_standard_image(img)
            
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
        # Remove .001, .002 etc. when followed by _ or space (for CC/iC Pack textures)
        base_name = re.sub(r'\.\d{3}(?=[_\s])', '', filename)  # Remove .001, .002 etc. when followed by _ or space
        base_name = re.sub(r'\.\d{3}$', '', base_name)  # Also remove if at the end
        base_name = os.path.splitext(base_name)[0]  # Remove standard extensions
        
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

    def is_udim_image(self, image):
        """Return True when the image contains UDIM/tiled data"""
        has_tiles = hasattr(image, "source") and image.source == 'TILED'
        tiles_attr = getattr(image, "tiles", None)
        if tiles_attr and len(tiles_attr) > 1:
            return True
        return has_tiles

    def build_udim_mapping(self, base_folder, base_name, extension, image):
        """Create a path mapping structure for UDIM images"""
        udim_token = "<UDIM>"
        template_filename = f"{base_name}.{udim_token}{extension}"
        template_path = f"{base_folder}\\{template_filename}"
        tile_paths = {}

        tiles = getattr(image, "tiles", [])
        for tile in tiles:
            tile_number = str(getattr(tile, "number", "1001"))
            tile_filename = f"{base_name}.{tile_number}{extension}"
            tile_paths[tile_number] = f"{base_folder}\\{tile_filename}"

        return {
            "udim": True,
            "template": template_path,
            "tiles": tile_paths,
        }

    def save_udim_image(self, image, mapping):
        """Attempt to save each tile for a UDIM image"""
        success = False
        try:
            image.save()
            success = True
        except Exception as e:
            print(f"DEBUG: UDIM bulk save failed for {image.name}: {e}")
            success = self._save_udim_tiles_individually(image, mapping)

        if success:
            self.udim_summary["saved"] += 1
        return success

    def save_standard_image(self, image):
        """Save a non-UDIM image safely"""
        try:
            if hasattr(image, 'save'):
                image.save()
                return True
        except Exception as e:
            print(f"DEBUG: Failed to save image {image.name}: {e}")
        return False

    def _save_udim_tiles_individually(self, image, mapping):
        """Fallback saving routine when image.save() fails on UDIMs"""
        tile_paths = mapping.get("tiles", {})
        any_saved = False

        for tile in getattr(image, "tiles", []):
            tile_number = str(getattr(tile, "number", "1001"))
            target_path = tile_paths.get(tile_number)
            if not target_path:
                continue
            try:
                ensure_directory_for_path(target_path)
                self._save_tile_via_image_editor(image, tile_number, target_path)
                any_saved = True
            except Exception as e:
                print(f"DEBUG: Failed to save UDIM tile {tile_number} for {image.name}: {e}")

        return any_saved

    def _save_tile_via_image_editor(self, image, tile_number, filepath):
        """Use an IMAGE_EDITOR override to save a specific tile"""
        # Try to find an existing image editor to reuse Blender UI context
        for area in bpy.context.screen.areas:
            if area.type != 'IMAGE_EDITOR':
                continue
            override = bpy.context.copy()
            override['area'] = area
            override['space_data'] = area.spaces.active
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region is None:
                continue
            override['region'] = region
            space = area.spaces.active
            space.image = image
            if hasattr(space, "image_user"):
                space.image_user.tile = int(tile_number)
            bpy.ops.image.save(override, filepath=filepath)
            return
        # Fallback: attempt to set filepath and invoke save without override
        image.filepath = filepath
        image.save()

# Must register the new dialog class as well
classes = (
    RBST_AutoMat_OT_summary_dialog,
    RBST_AutoMat_OT_AutoMatExtractor,
)

def register():
    for cls in classes:
        compat.safe_register_class(cls)

def unregister():
    for cls in reversed(classes):
        compat.safe_unregister_class(cls)

