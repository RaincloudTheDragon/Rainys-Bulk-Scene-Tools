import bpy # type: ignore
from bpy.types import Panel, Operator, PropertyGroup # type: ignore
from bpy.props import StringProperty, BoolProperty, EnumProperty, PointerProperty, CollectionProperty # type: ignore
import os.path
import re

def get_image_paths(image_name):
    """
    Get both filepath and filepath_raw for an image using its datablock name
    
    Args:
        image_name (str): The name of the image datablock
        
    Returns:
        tuple: (filepath, filepath_raw) if image exists, (None, None) if not found
    """
    if image_name in bpy.data.images:
        img = bpy.data.images[image_name]
        return (img.filepath, img.filepath_raw)
    else:
        return (None, None)

def get_image_extension(image):
    """
    Get the file extension from an image

    Args:
        image: The image datablock

    Returns:
        str: The file extension including the dot (e.g. '.png') or empty string if not found
    """
    # Debug print statements
    print(f"DEBUG: Getting extension for image: {image.name}")
    print(f"DEBUG: Image file_format is: {image.file_format}")
    
    # Use the file_format property
    format_map = {
        'PNG': '.png',
        'JPEG': '.jpg',
        'JPEG2000': '.jp2',
        'TARGA': '.tga',
        'TARGA_RAW': '.tga',
        'BMP': '.bmp',
        'OPEN_EXR': '.exr',
        'OPEN_EXR_MULTILAYER': '.exr',
        'HDR': '.hdr',
        'TIFF': '.tif',
    }
    
    if image.file_format in format_map:
        ext = format_map[image.file_format]
        print(f"DEBUG: Matched format, using extension: {ext}")
        return ext
    
    # Default to no extension if we can't determine it
    print(f"DEBUG: No matching format found, returning empty extension")
    return ''

def set_image_paths(image_name, new_path):
    """
    Set filepath and filepath_raw for an image using its datablock name
    Also update packed_file.filepath if the file is packed
    
    Args:
        image_name (str): The name of the image datablock
        new_path (str): The new path to assign
        
    Returns:
        bool: True if successful, False if image not found
    """
    if image_name in bpy.data.images:
        img = bpy.data.images[image_name]
        
        # Set the filepath properties
        img.filepath = new_path
        img.filepath_raw = new_path
        
        # For packed files, set the packed_file.filepath too
        # This is the property shown in the UI and is what we need to set
        # for proper handling of packed files
        if img.packed_file:
            try:
                # Try setting the property directly
                # This might be read-only in some versions of Blender, 
                # but we attempt it anyway based on the UI showing this property
                img.packed_file.filepath = new_path
            except Exception as e:
                # If it fails, the original filepaths (img.filepath and img.filepath_raw)
                # are still set, which is better than nothing
                pass
            
        return True
    else:
        return False

def bulk_remap_paths(mapping_dict):
    """
    Remap multiple paths at once
    
    Args:
        mapping_dict (dict): Dictionary mapping datablock names to new paths
        
    Returns:
        tuple: (success_count, failed_list)
    """
    success_count = 0
    failed_list = []
    
    for image_name, new_path in mapping_dict.items():
        success = set_image_paths(image_name, new_path)
        if success:
            success_count += 1
        else:
            failed_list.append(image_name)
    
    return (success_count, failed_list)

# Properties for path management
class BST_PathProperties(PropertyGroup):
    # Active image pointer
    active_image: PointerProperty(
        name="Image",
        type=bpy.types.Image
    ) # type: ignore
    
    show_bulk_operations: BoolProperty(
        name="Show Bulk Operations",
        description="Expand to show bulk operations interface",
        default=False
    ) # type: ignore
    
    # Properties for inline editing
    edit_filepath: BoolProperty(
        name="Edit Path",
        description="Toggle editing mode for filepath",
        default=False
    ) # type: ignore
    
    edit_filepath_raw: BoolProperty(
        name="Edit Raw Path",
        description="Toggle editing mode for filepath_raw",
        default=False
    ) # type: ignore
    
    temp_filepath: StringProperty(
        name="Temporary Path",
        description="Temporary storage for editing filepath",
        default="//textures",
        subtype='FILE_PATH'
    ) # type: ignore
    
    temp_filepath_raw: StringProperty(
        name="Temporary Raw Path",
        description="Temporary storage for editing filepath_raw",
        default="//textures",
        subtype='FILE_PATH'
    ) # type: ignore

    # Track last selected image for shift+click behavior
    last_selected_image: StringProperty(
        name="Last Selected Image",
        description="Name of the last selected image for shift+click behavior",
        default=""
    ) # type: ignore
    
    # Whether to sort by selected in the UI
    sort_by_selected: BoolProperty(
        name="Sort by Selected",
        description="Show selected images at the top of the list",
        default=True
    ) # type: ignore
    
    # Smart pathing properties
    smart_base_path: StringProperty(
        name="Base Path",
        description="Base path for image textures",
        default="//textures/",
        subtype='DIR_PATH'
    ) # type: ignore
    
    use_blend_subfolder: BoolProperty(
        name="Use Blend Subfolder",
        description="Include blend file name as a subfolder",
        default=True
    ) # type: ignore
    
    blend_subfolder: StringProperty(
        name="Blend Subfolder",
        description="Custom subfolder name (leave empty to use blend file name)",
        default="",
        subtype='FILE_NAME'
    ) # type: ignore
    
    use_material_subfolder: BoolProperty(
        name="Use Material Subfolder",
        description="Include material name as a subfolder",
        default=True
    ) # type: ignore
    
    material_subfolder: StringProperty(
        name="Material Subfolder",
        description="Custom subfolder name (leave empty to use active material name)",
        default="",
        subtype='FILE_NAME'
    ) # type: ignore

# Operator to remap a single datablock path
class BST_OT_remap_path(Operator):
    bl_idname = "bst.remap_path"
    bl_label = "Remap Path"
    bl_description = "Change the filepath and filepath_raw for a datablock"
    bl_options = {'REGISTER', 'UNDO'}
    
    new_path: StringProperty(
        name="New Path",
        description="Base path for datablock (datablock name will be appended)",
        default="//textures/",
        subtype='DIR_PATH'
    ) # type: ignore
    
    def execute(self, context):
        # Get the active image
        active_image = context.scene.bst_path_props.active_image
        if active_image:
            # Get file extension from the image
            extension = get_image_extension(active_image)
            
            # Get the combined path
            full_path = get_combined_path(context, active_image.name, extension)
            
            # Use the set_image_paths function to ensure proper handling of packed files
            success = set_image_paths(active_image.name, full_path)
            
            if success:
                self.report({'INFO'}, f"Successfully remapped {active_image.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"Failed to remap {active_image.name}")
                return {'CANCELLED'}
        else:
            self.report({'ERROR'}, "No active datablock selected")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # Use the path from properties
        props = context.scene.bst_path_props
        if props.use_smart_pathing:
            self.new_path = props.smart_base_path
        else:
            self.new_path = props.new_path
        return context.window_manager.invoke_props_dialog(self)

# Operator to toggle all image selections
class BST_OT_toggle_select_all(Operator):
    bl_idname = "bst.toggle_select_all"
    bl_label = "Toggle All"
    bl_description = "Toggle selection of all datablocks"
    bl_options = {'REGISTER', 'UNDO'}
    
    select_state: BoolProperty(
        name="Select State",
        description="Whether to select or deselect all",
        default=True
    ) # type: ignore
    
    def execute(self, context):
        # Apply the selection state to all images
        for img in bpy.data.images:
            img.bst_selected = self.select_state
        
        return {'FINISHED'}

# Operator to remap multiple paths at once
class BST_OT_bulk_remap(Operator):
    bl_idname = "bst.bulk_remap"
    bl_label = "Remap Paths"
    bl_description = "Apply the new path to all selected datablocks"
    bl_options = {'REGISTER', 'UNDO'}
    
    # We'll keep these properties for potential future use, but won't show a dialog for them
    source_dir: StringProperty(
        name="Source Directory",
        description="Directory to replace in paths",
        default="",
        subtype='DIR_PATH'
    ) # type: ignore
    
    target_dir: StringProperty(
        name="Target Directory",
        description="New directory to use",
        default="",
        subtype='DIR_PATH'
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        remap_count = 0
        
        # Process all the images that are selected
        for img in bpy.data.images:
            if hasattr(img, "bst_selected") and img.bst_selected:
                # Get file extension for this image
                extension = get_image_extension(img)
                
                # Get the combined path
                full_path = get_combined_path(context, img.name, extension)
                
                success = set_image_paths(img.name, full_path)
                if success:
                    remap_count += 1
                
        if remap_count > 0:
            self.report({'INFO'}, f"Successfully remapped {remap_count} paths")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No paths were remapped")
            return {'CANCELLED'}

# Operator to toggle path editing mode
class BST_OT_toggle_path_edit(Operator):
    bl_idname = "bst.toggle_path_edit"
    bl_label = "Toggle Path Edit"
    bl_description = "Toggle between view and edit mode for paths"
    bl_options = {'REGISTER', 'UNDO'}
    
    is_raw_path: BoolProperty(
        name="Is Raw Path",
        description="Whether toggling filepath_raw instead of filepath",
        default=False
    ) # type: ignore
    
    def execute(self, context):
        scene = context.scene
        path_props = scene.bst_path_props
        active_image = path_props.active_image
        
        if active_image:
            if self.is_raw_path:
                # Toggle edit mode for filepath_raw
                if not path_props.edit_filepath_raw:
                    # Entering edit mode, store current value
                    path_props.temp_filepath_raw = active_image.filepath_raw
                else:
                    # Exiting edit mode, apply the change
                    active_image.filepath_raw = path_props.temp_filepath_raw
                
                path_props.edit_filepath_raw = not path_props.edit_filepath_raw
            else:
                # Toggle edit mode for filepath
                if not path_props.edit_filepath:
                    # Entering edit mode, store current value
                    path_props.temp_filepath = active_image.filepath
                else:
                    # Exiting edit mode, apply the change
                    active_image.filepath = path_props.temp_filepath
                
                path_props.edit_filepath = not path_props.edit_filepath
        
        return {'FINISHED'}

# Operator to select all images used in the current material
class BST_OT_select_material_images(Operator):
    bl_idname = "bst.select_material_images"
    bl_label = "Select Material Images"
    bl_description = "Select all images used in the current material in the node editor"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected_count = 0
        
        # First, make sure we're in a node editor with a shader tree
        if (context.space_data and context.space_data.type == 'NODE_EDITOR' and
            hasattr(context.space_data, 'tree_type') and 
            context.space_data.tree_type == 'ShaderNodeTree' and
            context.space_data.node_tree):
            
            node_tree = context.space_data.node_tree
            
            # Find all image texture nodes in the current material
            for node in node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    # Select this image
                    node.image.bst_selected = True
                    selected_count += 1
            
            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} images from material")
            else:
                self.report({'INFO'}, "No image texture nodes found in current material")
        else:
            self.report({'WARNING'}, "No active shader node tree found")
        
        return {'FINISHED'}

# Operator to select active/selected image texture nodes
class BST_OT_select_active_images(Operator):
    bl_idname = "bst.select_active_images"
    bl_label = "Select Active Images"
    bl_description = "Select all images from currently selected texture nodes in the node editor"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected_count = 0
        
        # First, make sure we're in a node editor with a shader tree
        if (context.space_data and context.space_data.type == 'NODE_EDITOR' and
            hasattr(context.space_data, 'tree_type') and 
            context.space_data.tree_type == 'ShaderNodeTree' and
            context.space_data.node_tree):
            
            node_tree = context.space_data.node_tree
            
            # Find all selected image texture nodes
            for node in node_tree.nodes:
                if node.select and node.type == 'TEX_IMAGE' and node.image:
                    # Select this image
                    node.image.bst_selected = True
                    selected_count += 1
            
            if selected_count > 0:
                self.report({'INFO'}, f"Selected {selected_count} images from active nodes")
            else:
                self.report({'INFO'}, "No selected image texture nodes found")
        else:
            self.report({'WARNING'}, "No active shader node tree found")
        
        return {'FINISHED'}

# Add a class for renaming datablocks
class BST_OT_rename_datablock(Operator):
    """Click to rename datablock"""
    bl_idname = "bst.rename_datablock"
    bl_label = "Rename Datablock"
    bl_options = {'REGISTER', 'UNDO'}
    
    old_name: StringProperty(
        name="Old Name",
        description="Current name of the datablock",
        default=""
    ) # type: ignore
    
    new_name: StringProperty(
        name="New Name",
        description="New name for the datablock",
        default=""
    ) # type: ignore
    
    def invoke(self, context, event):
        self.new_name = self.old_name
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_name", text="Name")
    
    def execute(self, context):
        # Find the datablock
        datablock = bpy.data.images.get(self.old_name)
        if not datablock:
            self.report({'ERROR'}, f"Could not find image with name {self.old_name}")
            return {'CANCELLED'}
        
        # Check if the datablock is linked
        if hasattr(datablock, 'library') and datablock.library is not None:
            self.report({'ERROR'}, "Cannot rename linked image")
            return {'CANCELLED'}
        
        # Rename the datablock
        try:
            datablock.name = self.new_name
            self.report({'INFO'}, f"Renamed image to {self.new_name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to rename image: {str(e)}")
            return {'CANCELLED'}

# Update class for shift+click selection
class BST_OT_toggle_image_selection(Operator):
    """Toggle whether this image should be included in bulk operations"""
    bl_idname = "bst.toggle_image_selection"
    bl_label = "Toggle Image Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    image_name: StringProperty(
        name="Image Name",
        description="Name of the image to toggle",
        default=""
    ) # type: ignore
    
    def invoke(self, context, event):
        # Get the image
        img = bpy.data.images.get(self.image_name)
        if not img:
            return {'CANCELLED'}
            
        props = context.scene.bst_path_props
        last_selected = props.last_selected_image
        
        # If shift is held and we have a previous selection
        if event.shift and last_selected and last_selected in bpy.data.images:
            # Get indices of current and last selected images
            image_list = list(bpy.data.images)
            current_idx = -1
            last_idx = -1
            
            for i, image in enumerate(image_list):
                if image.name == self.image_name:
                    current_idx = i
                if image.name == last_selected:
                    last_idx = i
            
            # Select all images between last selected and current
            if current_idx >= 0 and last_idx >= 0:
                start_idx = min(current_idx, last_idx)
                end_idx = max(current_idx, last_idx)
                
                for i in range(start_idx, end_idx + 1):
                    # Ensure all images in range are selected
                    image_list[i].bst_selected = True
            
        else:
            # Toggle the current image's selection
            img.bst_selected = not img.bst_selected
            
        # Update last selected image
        props.last_selected_image = self.image_name
            
        return {'FINISHED'}

# Add new operator for reusing material name in path
class BST_OT_reuse_material_path(Operator):
    """Use the active material's name in the path"""
    bl_idname = "bst.reuse_material_path"
    bl_label = "Use Material Path"
    bl_description = "Set the path to use the active material's name"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        material_name = None
        # Try to get the active material from the active object
        obj = getattr(context, 'active_object', None)
        if obj and hasattr(obj, 'active_material') and obj.active_material:
            material_name = obj.active_material.name
        # Fallback: try to get from node editor's node tree
        elif (context.space_data and context.space_data.type == 'NODE_EDITOR' and
              hasattr(context.space_data, 'tree_type') and 
              context.space_data.tree_type == 'ShaderNodeTree' and
              context.space_data.node_tree):
            node_tree_name = context.space_data.node_tree.name
            if node_tree_name in bpy.data.materials:
                material_name = bpy.data.materials[node_tree_name].name
            else:
                material_name = node_tree_name
        
        if material_name:
            # Update the material subfolder field
            context.scene.bst_path_props.material_subfolder = material_name
            self.report({'INFO'}, f"Set material subfolder to {material_name}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No active material found on the active object or in the node editor")
            return {'CANCELLED'}

# Add new operator for reusing blend file name in path
class BST_OT_reuse_blend_name(Operator):
    """Use the current blend file name in the path"""
    bl_idname = "bst.reuse_blend_name"
    bl_label = "Use Blend Name"
    bl_description = "Set the subfolder to the current blend file name"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        blend_name = None
        # Try to get the current blend filename without extension
        blend_path = bpy.data.filepath
        if blend_path:
            blend_name = os.path.splitext(os.path.basename(blend_path))[0]
        
        if blend_name:
            # Set the blend subfolder
            context.scene.bst_path_props.blend_subfolder = blend_name
            self.report({'INFO'}, f"Set blend subfolder to {blend_name}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Could not determine blend file name (file not saved?)")
            return {'CANCELLED'}

# Make Paths Relative Operator
class BST_OT_make_paths_relative(Operator):
    bl_idname = "bst.make_paths_relative"
    bl_label = "Make Paths Relative"
    bl_description = "Convert absolute paths to relative paths for all datablocks"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        bpy.ops.file.make_paths_relative()
        self.report({'INFO'}, "Converted absolute paths to relative paths")
        return {'FINISHED'}

# Pack Images Operator
class BST_OT_pack_images(Operator):
    bl_idname = "bst.pack_images"
    bl_label = "Pack Images"
    bl_description = "Pack selected images into the .blend file"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        packed_count = 0
        failed_count = 0
        
        # Get all selected images or all images if none selected
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        if not selected_images:
            selected_images = list(bpy.data.images)
        
        for img in selected_images:
            if not img.packed_file and not img.is_generated:
                try:
                    print(f"DEBUG: Packing image: {img.name}")
                    img.pack()
                    packed_count += 1
                except Exception as e:
                    print(f"DEBUG: Failed to pack {img.name}: {str(e)}")
                    failed_count += 1
        
        if packed_count > 0:
            self.report({'INFO'}, f"Successfully packed {packed_count} images" + 
                       (f", {failed_count} failed" if failed_count > 0 else ""))
        else:
            self.report({'WARNING'}, "No images were packed" +
                        (f", {failed_count} failed" if failed_count > 0 else ""))
        
        return {'FINISHED'}

# Unpack Images Operator
class BST_OT_unpack_images(Operator):
    bl_idname = "bst.unpack_images"
    bl_label = "Unpack Images (Use Local)"
    bl_description = "Unpack selected images to their file paths using the 'USE_LOCAL' option"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        unpacked_count = 0
        failed_count = 0
        
        # Get all selected images or all images if none selected
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        if not selected_images:
            selected_images = list(bpy.data.images)
        
        for img in selected_images:
            if img.packed_file:
                try:
                    print(f"DEBUG: Unpacking image: {img.name} (USE_LOCAL)")
                    img.unpack(method='USE_LOCAL')
                    unpacked_count += 1
                except Exception as e:
                    print(f"DEBUG: Failed to unpack {img.name}: {str(e)}")
                    failed_count += 1
        
        if unpacked_count > 0:
            self.report({'INFO'}, f"Successfully unpacked {unpacked_count} images" + 
                       (f", {failed_count} failed" if failed_count > 0 else ""))
        else:
            self.report({'WARNING'}, "No images were unpacked" +
                        (f", {failed_count} failed" if failed_count > 0 else ""))
        
        return {'FINISHED'}

# Remove Packed Images Operator
class BST_OT_remove_packed_images(Operator):
    bl_idname = "bst.remove_packed_images"
    bl_label = "Remove Packed Data"
    bl_description = "Remove packed image data without saving to disk"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        removed_count = 0
        failed_count = 0
        
        # Get all selected images or all images if none selected
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        if not selected_images:
            selected_images = list(bpy.data.images)
        
        for img in selected_images:
            if img.packed_file:
                try:
                    print(f"DEBUG: Removing packed data for image: {img.name}")
                    img.unpack(method='REMOVE')
                    removed_count += 1
                except Exception as e:
                    print(f"DEBUG: Failed to remove packed data for {img.name}: {str(e)}")
                    failed_count += 1
        
        if removed_count > 0:
            self.report({'INFO'}, f"Successfully removed packed data from {removed_count} images" + 
                       (f", {failed_count} failed" if failed_count > 0 else ""))
        else:
            self.report({'WARNING'}, "No packed data was removed" +
                        (f", {failed_count} failed" if failed_count > 0 else ""))
        
        return {'FINISHED'}

# Save All Images Operator
class BST_OT_save_all_images(Operator):
    bl_idname = "bst.save_all_images"
    bl_label = "Save All Images"
    bl_description = "Save all selected images to image paths"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        saved_count = 0
        failed_count = 0
        
        # Get all selected images or all images if none selected
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        if not selected_images:
            selected_images = list(bpy.data.images)
        
        for img in selected_images:
            try:
                print(f"DEBUG: Attempting to save image: {img.name}")
                
                # Try to save using available methods
                if hasattr(img, 'save'):
                    # Try direct save method first
                    img.save()
                    saved_count += 1
                    print(f"DEBUG: Saved using img.save()")
                else:
                    # Alternative method - try to find an image editor space
                    for area in context.screen.areas:
                        if area.type == 'IMAGE_EDITOR':
                            # Found an image editor, use it to save the image
                            override = context.copy()
                            override['area'] = area
                            override['space_data'] = area.spaces.active
                            override['region'] = area.regions[0]
                            
                            # Set the active image
                            area.spaces.active.image = img
                            
                            # Try to save with override
                            bpy.ops.image.save(override)
                            saved_count += 1
                            print(f"DEBUG: Saved using image editor override")
                            break
                    else:
                        # No image editor found
                        print(f"DEBUG: No image editor found, skipping {img.name}")
                        failed_count += 1
            except Exception as e:
                print(f"DEBUG: Failed to save {img.name}: {str(e)}")
                failed_count += 1
        
        if saved_count > 0:
            self.report({'INFO'}, f"Successfully saved {saved_count} images" + 
                       (f", {failed_count} failed" if failed_count > 0 else ""))
        else:
            self.report({'WARNING'}, "No images were saved" +
                        (f", {failed_count} failed" if failed_count > 0 else ""))
        
        return {'FINISHED'}

# Remove Extensions Operator
class BST_OT_remove_extensions(Operator):
    bl_idname = "bst.remove_extensions"
    bl_label = "Remove Extensions"
    bl_description = "Remove common file extensions from selected image names"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        renamed_count = 0
        failed_count = 0
        
        # Common image extensions to remove
        extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', 
                      '.exr', '.hdr', '.tga', '.jp2', '.webp']
        
        # Get all selected images or all images if none selected
        selected_images = [img for img in bpy.data.images if hasattr(img, "bst_selected") and img.bst_selected]
        if not selected_images:
            selected_images = list(bpy.data.images)
        
        for img in selected_images:
            # Skip linked images
            if hasattr(img, 'library') and img.library is not None:
                print(f"DEBUG: Skipping linked image: {img.name}")
                failed_count += 1
                continue
                
            original_name = img.name
            
            # Check for any of the extensions at the end of the name
            for ext in extensions:
                if img.name.lower().endswith(ext.lower()):
                    # Remove the extension
                    new_name = img.name[:-len(ext)]
                    try:
                        print(f"DEBUG: Renaming {img.name} to {new_name}")
                        img.name = new_name
                        renamed_count += 1
                        break  # Stop after finding the first matching extension
                    except Exception as e:
                        print(f"DEBUG: Failed to rename {img.name}: {str(e)}")
                        failed_count += 1
        
        if renamed_count > 0:
            self.report({'INFO'}, f"Successfully renamed {renamed_count} images" + 
                       (f", {failed_count} failed" if failed_count > 0 else ""))
        else:
            self.report({'WARNING'}, "No images were renamed" +
                        (f", {failed_count} failed" if failed_count > 0 else ""))
        
        return {'FINISHED'}

# Add new operator for flat color texture renaming
class BST_OT_rename_flat_colors(Operator):
    """Rename flat color textures to their hex color values"""
    bl_idname = "bst.rename_flat_colors"
    bl_label = "Rename Flat Colors"
    bl_description = "Find and rename flat color textures to their hex color values"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        from ..scripts.flat_color_texture_renamer import rename_flat_color_textures
        
        try:
            renamed_count = rename_flat_color_textures()
            if renamed_count > 0:
                self.report({'INFO'}, f"Successfully renamed {renamed_count} flat color textures")
            else:
                self.report({'INFO'}, "No flat color textures found to rename")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to rename textures: {str(e)}")
            return {'CANCELLED'}

# Update get_combined_path function for path construction
def get_combined_path(context, datablock_name, extension=""):
    """
    Get the combined path based on pathing settings.
    
    Args:
        context: The current context
        datablock_name: Name of the datablock to append
        extension: Optional file extension to append
        
    Returns:
        str: The combined path
    """
    props = context.scene.bst_path_props
    
    # Start with base path
    path = props.smart_base_path
    if not path.endswith(('\\', '/')):
        path += '/'
        
    # Add blend subfolder if enabled
    if props.use_blend_subfolder:
        subfolder = props.blend_subfolder
        if not subfolder:
            # Try to get blend name if not specified
            blend_path = bpy.data.filepath
            if blend_path:
                subfolder = os.path.splitext(os.path.basename(blend_path))[0]
            else:
                subfolder = "untitled"
        
        path += subfolder + '/'
        
    # Add material subfolder if enabled
    if props.use_material_subfolder:
        subfolder = props.material_subfolder
        if not subfolder:
            # Try to get material name if not specified
            material_name = None
            # Try to get from active object
            obj = getattr(context, 'active_object', None)
            if obj and hasattr(obj, 'active_material') and obj.active_material:
                material_name = obj.active_material.name
            # Fallback: try to get from node editor's node tree
            elif (context.space_data and context.space_data.type == 'NODE_EDITOR' and
                  hasattr(context.space_data, 'tree_type') and 
                  context.space_data.tree_type == 'ShaderNodeTree' and
                  context.space_data.node_tree):
                node_tree_name = context.space_data.node_tree.name
                if node_tree_name in bpy.data.materials:
                    material_name = bpy.data.materials[node_tree_name].name
                else:
                    material_name = node_tree_name
            
            if material_name:
                subfolder = material_name
            else:
                subfolder = "material"
        
        path += subfolder + '/'
    
    # Append datablock name and extension
    return path + datablock_name + extension

# Panel for Shader Editor sidebar
class NODE_PT_bulk_path_tools(Panel):
    bl_label = "Bulk Pathing"
    bl_idname = "NODE_PT_bulk_path_tools"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Node'
    bl_context = 'shader'
    
    @classmethod
    def poll(cls, context):
        return hasattr(context.space_data, 'tree_type') and context.space_data.tree_type == 'ShaderNodeTree'
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        path_props = scene.bst_path_props        
        
        # Workflow section
        box = layout.box(align=True)
        row = box.row()
        row.label(text="Workflow")
        
        # Pack/Unpack row
        row = box.row(align=True)
        row.operator("bst.pack_images", text="Pack", icon='PACKAGE')
        row.operator("bst.unpack_images", text="Unpack Local", icon='UGLYPACKAGE')
        
        # Remove packed/Save row
        row = box.row(align=True)
        row.operator("bst.remove_packed_images", text="Remove Pack", icon='TRASH')
        row.operator("bst.remove_extensions", text="Remove Extensions", icon='X')
        
        # Flat color renaming row
        row = box.row(align=True)
        row.operator("bst.rename_flat_colors", text="Rename Flat Colors", icon='COLOR')
        
        # Save images row
        row = box.row(align=True)
        row.operator("bst.save_all_images", text="Save All", icon='EXPORT')
        
        # Path Settings UI
        box.separator()
        
        # Base path
        row = box.row(align=True)
        row.prop(path_props, "smart_base_path", text="Base Path")
        
        # Blend subfolder
        row = box.row()
        subrow = row.row()
        subrow.prop(path_props, "use_blend_subfolder", text="")
        subrow = row.row()
        subrow.enabled = path_props.use_blend_subfolder
        subrow.prop(path_props, "blend_subfolder", text="Blend Subfolder")
        reuse_blend = subrow.operator("bst.reuse_blend_name", text="", icon='FILE_REFRESH')
        
        # Material subfolder
        row = box.row()
        subrow = row.row()
        subrow.prop(path_props, "use_material_subfolder", text="")
        subrow = row.row()
        subrow.enabled = path_props.use_material_subfolder
        subrow.prop(path_props, "material_subfolder", text="Material Subfolder")
        reuse_material = subrow.operator("bst.reuse_material_path", text="", icon='FILE_REFRESH')
        
        # Example path
        example_path = get_combined_path(context, "texture_name", ".png")
        row = box.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Preview: {example_path}")
        
        # Bulk operations section
        box = layout.box()
        row = box.row()
        row.prop(path_props, "show_bulk_operations", 
                 icon="TRIA_DOWN" if path_props.show_bulk_operations else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Image Selection")
        
        # Show bulk operations UI only when expanded
        if path_props.show_bulk_operations:
            # Select all row
            row = box.row()
            row.label(text="Select:")
            select_all = row.operator("bst.toggle_select_all", text="All")
            select_all.select_state = True
            deselect_all = row.operator("bst.toggle_select_all", text="None")
            deselect_all.select_state = False
            
            # Node editor selection buttons
            row = box.row(align=True)
            row.operator("bst.select_material_images", text="Material Images")
            row.operator("bst.select_active_images", text="Active Images")
            
            # Sorting option
            row = box.row()
            row.prop(path_props, "sort_by_selected", text="Sort by Selected")
            
            # Bulk remap button - always visible, disabled if none selected
            row = box.row()
            any_selected = any(hasattr(img, "bst_selected") and img.bst_selected for img in bpy.data.images)
            row.enabled = any_selected
            row.operator("bst.bulk_remap", text="Remap Selected", icon='FILE_REFRESH')
            
            # Make paths relative button
            row = box.row()
            row.operator("bst.make_paths_relative", text="Make Paths Relative", icon='FILE_FOLDER')
            
            box.separator()
            
            # Image selection list with thumbnails
            if len(bpy.data.images) > 0:
                # Sort images if enabled
                if path_props.sort_by_selected:
                    # Create a sorted list with selected images first
                    sorted_images = sorted(bpy.data.images, 
                                           key=lambda img: not getattr(img, "bst_selected", False))
                else:
                    # Use original order
                    sorted_images = bpy.data.images
                
                for img in sorted_images:
                    # Add bst_selected attribute if it doesn't exist
                    if not hasattr(img, "bst_selected"):
                        img.bst_selected = False
                    
                    row = box.row(align=True)
                    
                    # Checkbox for selection - use operator for shift+click support
                    op = row.operator("bst.toggle_image_selection", text="", 
                                    icon='CHECKBOX_HLT' if img.bst_selected else 'CHECKBOX_DEHLT',
                                    emboss=False)
                    op.image_name = img.name
                    
                    # Image thumbnail
                    if hasattr(img, 'preview'):
                        # Use the actual image thumbnail
                        row.template_icon(icon_value=img.preview_ensure().icon_id, scale=1.0)
                    else:
                        row.label(text="", icon='IMAGE_DATA')
                    
                    # Image name with rename operator
                    rename_op = row.operator("bst.rename_datablock", text=img.name, emboss=False)
                    rename_op.old_name = img.name
            else:
                box.label(text="No images in blend file")

# Sub-panel for existing Bulk Scene Tools
class VIEW3D_PT_bulk_path_subpanel(Panel):
    bl_label = "Bulk Path Management"
    bl_idname = "VIEW3D_PT_bulk_path_subpanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_options = {'DEFAULT_CLOSED'}
    bl_order = 1
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        path_props = scene.bst_path_props
        
        # Workflow section
        box = layout.box()
        row = box.row()
        row.label(text="Workflow")
        
        # Pack/Unpack row
        row = box.row(align=True)
        row.operator("bst.pack_images", text="Pack", icon='PACKAGE')
        row.operator("bst.unpack_images", text="Unpack Local", icon='UNPINNED')
        
        # Remove packed/Save row
        row = box.row(align=True)
        row.operator("bst.remove_packed_images", text="Remove Pack", icon='TRASH')
        row.operator("bst.remove_extensions", text="Remove Extensions", icon='FILE_TICK')
        
        # Flat color renaming row
        row = box.row(align=True)
        row.operator("bst.rename_flat_colors", text="Rename Flat Colors", icon='COLOR')
        
        # Save images row
        row = box.row(align=True)
        row.operator("bst.save_all_images", text="Save All", icon='FILE_TICK')
        
        # Path Settings UI
        box.separator()
        
        # Base path
        row = box.row(align=True)
        row.prop(path_props, "smart_base_path", text="Base Path")
        
        # Blend subfolder
        row = box.row()
        subrow = row.row()
        subrow.prop(path_props, "use_blend_subfolder", text="")
        subrow = row.row()
        subrow.enabled = path_props.use_blend_subfolder
        subrow.prop(path_props, "blend_subfolder", text="Blend Subfolder")
        reuse_blend = subrow.operator("bst.reuse_blend_name", text="", icon='FILE_REFRESH')
        
        # Material subfolder
        row = box.row()
        subrow = row.row()
        subrow.prop(path_props, "use_material_subfolder", text="")
        subrow = row.row()
        subrow.enabled = path_props.use_material_subfolder
        subrow.prop(path_props, "material_subfolder", text="Material Subfolder")
        reuse_material = subrow.operator("bst.reuse_material_path", text="", icon='FILE_REFRESH')
        
        # Example path
        example_path = get_combined_path(context, "texture_name", ".png")
        row = box.row()
        row.alignment = 'RIGHT'
        row.label(text=f"Preview: {example_path}")
        
        # Bulk operations section
        box = layout.box()
        row = box.row()
        row.prop(path_props, "show_bulk_operations", 
                 icon="TRIA_DOWN" if path_props.show_bulk_operations else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Image Selection")
        
        # Show bulk operations UI only when expanded
        if path_props.show_bulk_operations:
            # Select all row
            row = box.row()
            row.label(text="Select:")
            select_all = row.operator("bst.toggle_select_all", text="All")
            select_all.select_state = True
            deselect_all = row.operator("bst.toggle_select_all", text="None")
            deselect_all.select_state = False
            
            # Node editor selection buttons
            row = box.row(align=True)
            row.operator("bst.select_material_images", text="Material Images")
            row.operator("bst.select_active_images", text="Active Images")
            
            # Sorting option
            row = box.row()
            row.prop(path_props, "sort_by_selected", text="Sort by Selected")
            
            # Bulk remap button - always visible, disabled if none selected
            row = box.row()
            any_selected = any(hasattr(img, "bst_selected") and img.bst_selected for img in bpy.data.images)
            row.enabled = any_selected
            row.operator("bst.bulk_remap", text="Remap Selected", icon='FILE_REFRESH')
            
            # Make paths relative button
            row = box.row()
            row.operator("bst.make_paths_relative", text="Make Paths Relative", icon='FILE_FOLDER')
            
            box.separator()
            
            # Image selection list with thumbnails
            if len(bpy.data.images) > 0:
                # Sort images if enabled
                if path_props.sort_by_selected:
                    # Create a sorted list with selected images first
                    sorted_images = sorted(bpy.data.images, 
                                           key=lambda img: not getattr(img, "bst_selected", False))
                else:
                    # Use original order
                    sorted_images = bpy.data.images
                
                col = box.column(align=True)
                for img in sorted_images:
                    # Add bst_selected attribute if it doesn't exist
                    if not hasattr(img, "bst_selected"):
                        img.bst_selected = False
                    
                    row = col.row(align=True)
                    
                    # Checkbox for selection - use operator for shift+click support
                    op = row.operator("bst.toggle_image_selection", text="", 
                                    icon='CHECKBOX_HLT' if img.bst_selected else 'CHECKBOX_DEHLT',
                                    emboss=False)
                    op.image_name = img.name
                    
                    # Image thumbnail
                    if hasattr(img, 'preview'):
                        # Use the actual image thumbnail
                        row.template_icon(icon_value=img.preview_ensure().icon_id, scale=1.0)
                    else:
                        row.label(text="", icon='IMAGE_DATA')
                    
                    # Image name with rename operator
                    rename_op = row.operator("bst.rename_datablock", text=img.name, emboss=False)
                    rename_op.old_name = img.name
            else:
                box.label(text="No images in blend file")

# Registration function for this module
classes = (
    BST_PathProperties,
    BST_OT_remap_path,
    BST_OT_toggle_select_all,
    BST_OT_bulk_remap,
    BST_OT_toggle_path_edit,
    BST_OT_select_material_images,
    BST_OT_select_active_images,
    BST_OT_rename_datablock,
    BST_OT_toggle_image_selection,
    BST_OT_reuse_material_path,
    BST_OT_reuse_blend_name,
    BST_OT_make_paths_relative,
    BST_OT_pack_images,
    BST_OT_unpack_images,
    BST_OT_remove_packed_images,
    BST_OT_save_all_images,
    BST_OT_remove_extensions,
    BST_OT_rename_flat_colors,
    NODE_PT_bulk_path_tools,
    VIEW3D_PT_bulk_path_subpanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties
    bpy.types.Scene.bst_path_props = PointerProperty(type=BST_PathProperties)
    
    # Add custom property to images for selection
    bpy.types.Image.bst_selected = BoolProperty(
        name="Selected for Bulk Operations",
        default=False
    )
    
    # For debugging only
    print("Bulk Path Management registered successfully")

def unregister():
    # Remove custom property
    if hasattr(bpy.types.Image, "bst_selected"):
        del bpy.types.Image.bst_selected
    
    # Unregister properties
    del bpy.types.Scene.bst_path_props
    
    # Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()