import bpy
import re

class RENAME_OT_summary_dialog(bpy.types.Operator):
    """Show rename operation summary"""
    bl_idname = "bst.rename_summary_dialog"
    bl_label = "Rename Summary"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    # Properties to store summary data
    total_selected: bpy.props.IntProperty(default=0)
    renamed_count: bpy.props.IntProperty(default=0)
    shared_count: bpy.props.IntProperty(default=0)
    unused_count: bpy.props.IntProperty(default=0)
    cc3iid_count: bpy.props.IntProperty(default=0)
    flatcolor_count: bpy.props.IntProperty(default=0)
    already_correct_count: bpy.props.IntProperty(default=0)
    rename_details: bpy.props.StringProperty(default="")
    
    def draw(self, context):
        layout = self.layout
        
        # Title
        layout.label(text="Rename by Material - Summary", icon='INFO')
        layout.separator()
        
        # Statistics box
        box = layout.box()
        col = box.column(align=True)
        col.label(text=f"Total selected images: {self.total_selected}")
        col.label(text=f"Successfully renamed: {self.renamed_count}", icon='CHECKMARK')
        
        if self.already_correct_count > 0:
            col.label(text=f"Already correctly named: {self.already_correct_count}", icon='CHECKMARK')
        if self.shared_count > 0:
            col.label(text=f"Shared images skipped: {self.shared_count}", icon='RADIOBUT_OFF')
        if self.unused_count > 0:
            col.label(text=f"Unused images skipped: {self.unused_count}", icon='RADIOBUT_OFF')
        if self.cc3iid_count > 0:
            col.label(text=f"CC3 ID textures skipped: {self.cc3iid_count}", icon='RADIOBUT_OFF')
        if self.flatcolor_count > 0:
            col.label(text=f"Flat colors skipped: {self.flatcolor_count}", icon='RADIOBUT_OFF')
        
        # Detailed results if any renames occurred
        if self.renamed_count > 0 and self.rename_details:
            layout.separator()
            layout.label(text="Renamed Images:", icon='OUTLINER_DATA_FONT')
            
            details_box = layout.box()
            details_col = details_box.column(align=True)
            
            # Parse and display rename details
            for line in self.rename_details.split('\n'):
                if line.strip():
                    details_col.label(text=line, icon='RIGHTARROW_THIN')
        
        layout.separator()
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=500)

class Rename_images_by_mat(bpy.types.Operator):
    bl_idname = "bst.rename_images_by_mat"
    bl_label = "Rename Images by Material"
    bl_description = "Rename selected images based on their material usage, preserving texture type suffixes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Get selected images
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        
        if not selected_images:
            self.report({'WARNING'}, "No images selected for renaming")
            return {'CANCELLED'}
        
        # Get image to material mapping
        image_to_materials = self.get_image_material_mapping(selected_images)
        
        renamed_count = 0
        shared_count = 0
        unused_count = 0
        cc3iid_count = 0  # Track CC3 ID textures
        flatcolor_count = 0  # Track flat color textures
        already_correct_count = 0  # Track images already correctly named
        renamed_list = []  # Track renamed images for debug
        
        for img in selected_images:
            # Skip CC3 ID textures (ignore case)
            if img.name.lower().startswith('cc3iid'):
                cc3iid_count += 1
                print(f"DEBUG: Skipped CC3 ID texture: {img.name}")
                continue
            
            # Skip flat color textures (start with #)
            if img.name.startswith('#'):
                flatcolor_count += 1
                print(f"DEBUG: Skipped flat color texture: {img.name}")
                continue
                
            materials = image_to_materials.get(img.name, [])
            
            if len(materials) == 0:
                # Unused image - skip
                unused_count += 1
                print(f"DEBUG: Skipped unused image: {img.name}")
                continue
            elif len(materials) == 1:
                # Single material usage - check if already correctly named
                material_name = materials[0]
                suffix = self.extract_texture_suffix(img.name)
                original_name = img.name
                
                if suffix:
                    # Capitalize the suffix properly
                    capitalized_suffix = self.capitalize_suffix(suffix)
                    expected_name = f"{material_name}_{capitalized_suffix}"
                else:
                    expected_name = material_name
                
                # Check if the image is already correctly named
                if img.name == expected_name:
                    already_correct_count += 1
                    print(f"DEBUG: Skipped already correctly named: {img.name}")
                    continue
                
                # Avoid duplicate names
                new_name = self.ensure_unique_name(expected_name)
                
                img.name = new_name
                renamed_count += 1
                renamed_list.append((original_name, new_name, material_name, capitalized_suffix if suffix else None))
                print(f"DEBUG: Renamed '{original_name}' → '{new_name}' (Material: {material_name}, Suffix: {capitalized_suffix if suffix else 'none'})")
            else:
                # Shared across multiple materials - skip
                shared_count += 1
                print(f"DEBUG: Skipped shared image: {img.name} (used by {len(materials)} materials: {', '.join(materials[:3])}{'...' if len(materials) > 3 else ''})")
        
        # Console debug summary (keep for development)
        print(f"\n=== RENAME BY MATERIAL SUMMARY ===")
        print(f"Total selected: {len(selected_images)}")
        print(f"Renamed: {renamed_count}")
        print(f"Already correct (skipped): {already_correct_count}")
        print(f"Shared (skipped): {shared_count}")
        print(f"Unused (skipped): {unused_count}")
        print(f"CC3 ID textures (skipped): {cc3iid_count}")
        print(f"Flat colors (skipped): {flatcolor_count}")
        
        if renamed_list:
            print(f"\nDetailed rename log:")
            for original, new, material, suffix in renamed_list:
                suffix_info = f" (suffix: {suffix})" if suffix else " (no suffix)"
                print(f"  '{original}' → '{new}' for material '{material}'{suffix_info}")
        
        print(f"===================================\n")
        
        # Show popup summary dialog
        self.show_summary_dialog(context, len(selected_images), renamed_count, shared_count, unused_count, cc3iid_count, flatcolor_count, already_correct_count, renamed_list)
        
        return {'FINISHED'}
    
    def show_summary_dialog(self, context, total_selected, renamed_count, shared_count, unused_count, cc3iid_count, flatcolor_count, already_correct_count, renamed_list):
        """Show a popup dialog with the rename summary"""
        # Prepare detailed rename information for display
        details_text = ""
        if renamed_list:
            for original, new, material, suffix in renamed_list:
                suffix_info = f" ({suffix})" if suffix else ""
                details_text += f"'{original}' → '{new}'{suffix_info}\n"
        
        # Invoke the summary dialog
        dialog = bpy.ops.bst.rename_summary_dialog('INVOKE_DEFAULT',
                                              total_selected=total_selected,
                                              renamed_count=renamed_count,
                                              shared_count=shared_count,
                                              unused_count=unused_count,
                                              cc3iid_count=cc3iid_count,
                                              flatcolor_count=flatcolor_count,
                                              already_correct_count=already_correct_count,
                                              rename_details=details_text.strip())
    
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
    
    def extract_texture_suffix(self, name):
        """Extract texture type suffix from image name (case-insensitive)"""
        # Comprehensive list of texture suffixes
        suffixes = [
            # Standard PBR suffixes
            'diffuse', 'basecolor', 'base_color', 'albedo', 'color', 'col',
            'normal', 'norm', 'nrm', 'bump',
            'roughness', 'rough', 'rgh',
            'metallic', 'metal', 'mtl',
            'specular', 'spec', 'spc',
            'ao', 'ambient_occlusion', 'ambientocclusion', 'occlusion',
            'height', 'displacement', 'disp', 'displace',
            'opacity', 'alpha', 'mask',
            'emission', 'emissive', 'emit',
            'subsurface', 'sss', 'transmission',
            
            # Character Creator / iClone suffixes
            'base', 'diffusemap', 'normalmap', 'roughnessmap', 'metallicmap',
            'aomap', 'opacitymap', 'emissionmap', 'heightmap', 'displacementmap',
            'detail_normal', 'detail_diffuse', 'detail_mask',
            'blend', 'id', 'cavity', 'curvature', 'transmap', 'rgbamask', 'sssmap',
            
            # Hair-related multi-word suffixes (spaces)
            'hair flow map', 'hair id map', 'hair root map', 'hair depth map',
            'flow map', 'id map', 'root map', 'depth map',
            
            # Additional common variations
            'tex', 'map', 'img', 'texture',
            'd', 'n', 'r', 'm', 's', 'a', 'h', 'o', 'e'  # Single letter abbreviations
        ]
        
        # Remove file extension first
        base_name = re.sub(r'\.[^.]+$', '', name)
        
        # Sort suffixes by length (longest first) to prioritize more specific matches
        sorted_suffixes = sorted(suffixes, key=len, reverse=True)
        
        # First, try to find multi-word suffixes with spaces (case-insensitive)
        for suffix in sorted_suffixes:
            if ' ' in suffix:  # Multi-word suffix
                # Pattern: ends with space + suffix
                pattern = rf'\s+({re.escape(suffix)})$'
                match = re.search(pattern, base_name, re.IGNORECASE)
                if match:
                    return match.group(1).lower()
                
                # Pattern: ends with suffix (no space separator, but exact match)
                if base_name.lower().endswith(suffix.lower()) and len(base_name) > len(suffix):
                    # Check if there's a word boundary before the suffix
                    prefix_end = len(base_name) - len(suffix)
                    if prefix_end > 0 and base_name[prefix_end - 1] in ' _-':
                        return suffix.lower()
        
        # Then try single-word suffixes with traditional separators
        for suffix in sorted_suffixes:
            if ' ' not in suffix:  # Single word suffix
                # Pattern: ends with _suffix or -suffix or .suffix
                pattern = rf'[._-]({re.escape(suffix)})$'
                match = re.search(pattern, base_name, re.IGNORECASE)
                if match:
                    return match.group(1).lower()
                
                # Pattern: ends with suffix (no separator)
                if base_name.lower().endswith(suffix.lower()) and len(base_name) > len(suffix):
                    return suffix.lower()
        
        # Check for numeric suffixes (like _01, _02, etc.)
        numeric_match = re.search(r'[._-](\d+)$', base_name)
        if numeric_match:
            return numeric_match.group(1)
        
        return None
    
    def ensure_unique_name(self, proposed_name):
        """Ensure the proposed name is unique among all images"""
        if proposed_name not in bpy.data.images:
            return proposed_name
        
        # If name exists, add numerical suffix
        counter = 1
        while f"{proposed_name}.{counter:03d}" in bpy.data.images:
            counter += 1
        
        return f"{proposed_name}.{counter:03d}"
    
    def capitalize_suffix(self, suffix):
        """Properly capitalize texture type suffixes with correct formatting"""
        # Dictionary of common texture suffixes with proper capitalization
        suffix_mapping = {
            # Standard PBR suffixes
            'diffuse': 'Diffuse',
            'basecolor': 'BaseColor',
            'base_color': 'BaseColor',
            'albedo': 'Albedo',
            'color': 'Color',
            'col': 'Color',
            
            'normal': 'Normal',
            'norm': 'Normal',
            'nrm': 'Normal',
            'bump': 'Bump',
            
            'roughness': 'Roughness',
            'rough': 'Roughness',
            'rgh': 'Roughness',
            
            'metallic': 'Metallic',
            'metal': 'Metallic',
            'mtl': 'Metallic',
            
            'specular': 'Specular',
            'spec': 'Specular',
            'spc': 'Specular',
            
            'ao': 'AO',
            'ambient_occlusion': 'AmbientOcclusion',
            'ambientocclusion': 'AmbientOcclusion',
            'occlusion': 'Occlusion',
            
            'height': 'Height',
            'displacement': 'Displacement',
            'disp': 'Displacement',
            'displace': 'Displacement',
            
            'opacity': 'Opacity',
            'alpha': 'Alpha',
            'mask': 'Mask',
            'transmap': 'TransMap',
            
            'emission': 'Emission',
            'emissive': 'Emission',
            'emit': 'Emission',
            
            'subsurface': 'Subsurface',
            'sss': 'SSS',
            'transmission': 'Transmission',
            
            # Character Creator / iClone suffixes
            'base': 'Base',
            'diffusemap': 'DiffuseMap',
            'normalmap': 'NormalMap',
            'roughnessmap': 'RoughnessMap',
            'metallicmap': 'MetallicMap',
            'aomap': 'AOMap',
            'opacitymap': 'OpacityMap',
            'emissionmap': 'EmissionMap',
            'heightmap': 'HeightMap',
            'displacementmap': 'DisplacementMap',
            'detail_normal': 'DetailNormal',
            'detail_diffuse': 'DetailDiffuse',
            'detail_mask': 'DetailMask',
            'blend': 'Blend',
            'id': 'ID',
            'cavity': 'Cavity',
            'curvature': 'Curvature',
            'transmap': 'TransMap',
            'rgbamask': 'RGBAMask',
            'sssmap': 'SSSMap',
            
            # Hair-related multi-word suffixes
            'hair flow map': 'HairFlowMap',
            'hair id map': 'HairIDMap',
            'hair root map': 'HairRootMap',
            'hair depth map': 'HairDepthMap',
            'flow map': 'FlowMap',
            'id map': 'IDMap',
            'root map': 'RootMap',
            'depth map': 'DepthMap',
            
            # Additional common variations
            'tex': 'Texture',
            'map': 'Map',
            'img': 'Image',
            'texture': 'Texture',
            
            # Single letter abbreviations
            'd': 'Diffuse',
            'n': 'Normal',
            'r': 'Roughness',
            'm': 'Metallic',
            's': 'Specular',
            'a': 'Alpha',
            'h': 'Height',
            'o': 'Occlusion',
            'e': 'Emission'
        }
        
        # Get the proper capitalization from mapping, or capitalize first letter as fallback
        return suffix_mapping.get(suffix.lower(), suffix.capitalize())


# Registration classes - need to register both operators
classes = (
    RENAME_OT_summary_dialog,
    Rename_images_by_mat,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

