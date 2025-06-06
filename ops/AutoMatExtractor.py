import bpy
import os
import re
from ..panels.bulk_path_management import get_image_extension, bulk_remap_paths

class AutoMatExtractor(bpy.types.Operator):
    bl_idname = "bst.automatextractor"
    bl_label = "AutoMatExtractor"
    bl_description = "Pack selected images and extract them with organized paths by blend file and material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
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
        shared_count = 0
        flat_color_count = 0
        
        for img in selected_images:
            # Get the proper file extension
            extension = get_image_extension(img)
            base_name = os.path.splitext(img.name)[0]  # Remove existing extension from name
            base_name = self.sanitize_filename(base_name)
            filename = base_name + extension
            
            # Special handling for flat color textures (names starting with #)
            if img.name.startswith('#'):
                path = f"//textures\\common\\FlatColors\\{filename}"
                flat_color_count += 1
            else:
                # Determine if image is shared across multiple materials
                materials = image_to_materials.get(img.name, [])
                
                if len(materials) == 0:
                    # No material usage found, put in common
                    path = f"//textures\\common\\{filename}"
                    shared_count += 1
                elif len(materials) == 1:
                    # Single material usage
                    material_name = self.sanitize_filename(materials[0])
                    path = f"//textures\\{blend_name}\\{material_name}\\{filename}"
                else:
                    # Multiple material usage, put in common
                    path = f"//textures\\common\\{filename}"
                    shared_count += 1
            
            path_mapping[img.name] = path
        
        # Step 5: Use PathMan's bulk remap function
        success_count, failed_list = bulk_remap_paths(path_mapping)
        
        # Step 6: Save all images to their new locations
        try:
            bpy.ops.bst.save_all_images()
            self.report({'INFO'}, f"Saved images to their new organized locations")
        except Exception as e:
            self.report({'WARNING'}, f"Failed to save images: {str(e)}")
        
        # Report results
        if failed_list:
            self.report({'WARNING'}, f"Remapped {success_count}/{len(selected_images)} paths. Failed: {', '.join(failed_list[:3])}")
        else:
            self.report({'INFO'}, f"Successfully remapped {success_count} image paths")
        
        # Build detailed report
        material_based_count = len(selected_images) - shared_count - flat_color_count
        report_parts = []
        
        if material_based_count > 0:
            report_parts.append(f"{material_based_count} organized by material")
        if shared_count > 0:
            report_parts.append(f"{shared_count} shared images in common folder")
        if flat_color_count > 0:
            report_parts.append(f"{flat_color_count} flat colors in FlatColors folder")
        
        self.report({'INFO'}, f"Organized {len(selected_images)} images: {', '.join(report_parts)}")
        
        return {'FINISHED'}
    
    def sanitize_filename(self, filename):
        """Sanitize filename/folder name for filesystem compatibility"""
        # Remove or replace invalid characters for Windows/Mac/Linux
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
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

