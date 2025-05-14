import bpy
from bpy.types import Panel, Operator, PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty, PointerProperty, CollectionProperty

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

def set_image_paths(image_name, new_path):
    """
    Set both filepath and filepath_raw for an image using its datablock name
    
    Args:
        image_name (str): The name of the image datablock
        new_path (str): The new path to assign
        
    Returns:
        bool: True if successful, False if image not found
    """
    if image_name in bpy.data.images:
        img = bpy.data.images[image_name]
        img.filepath = new_path
        img.filepath_raw = new_path
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
    )
    
    new_path: StringProperty(
        name="New Path",
        description="Base path for datablocks (datablock name will be appended)",
        default="//textures/",
        subtype='DIR_PATH'
    )
    
    show_bulk_operations: BoolProperty(
        name="Show Bulk Operations",
        description="Expand to show bulk operations interface",
        default=False
    )
    
    # Properties for inline editing
    edit_filepath: BoolProperty(
        name="Edit Path",
        description="Toggle editing mode for filepath",
        default=False
    )
    
    edit_filepath_raw: BoolProperty(
        name="Edit Raw Path",
        description="Toggle editing mode for filepath_raw",
        default=False
    )
    
    temp_filepath: StringProperty(
        name="Temporary Path",
        description="Temporary storage for editing filepath",
        default="//textures",
        subtype='FILE_PATH'
    )
    
    temp_filepath_raw: StringProperty(
        name="Temporary Raw Path",
        description="Temporary storage for editing filepath_raw",
        default="//textures",
        subtype='FILE_PATH'
    )

    # Track last selected image for shift+click behavior
    last_selected_image: StringProperty(
        name="Last Selected Image",
        description="Name of the last selected image for shift+click behavior",
        default=""
    )
    
    # Sort by selected images
    sort_by_selected: BoolProperty(
        name="Sort by Selected",
        description="Show selected images at the top of the list",
        default=False
    )

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
    )
    
    def execute(self, context):
        # Get the active image
        active_image = context.scene.bst_path_props.active_image
        if active_image:
            # Ensure path ends with separator
            base_path = self.new_path
            if not base_path.endswith(('\\', '/')):
                base_path += '/'
            # Append datablock name
            full_path = base_path + active_image.name
            active_image.filepath = full_path
            active_image.filepath_raw = full_path
            self.report({'INFO'}, f"Successfully remapped {active_image.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "No active datablock selected")
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        # Use the path from properties
        self.new_path = context.scene.bst_path_props.new_path
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
    )
    
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
    )
    
    target_dir: StringProperty(
        name="Target Directory",
        description="New directory to use",
        default="",
        subtype='DIR_PATH'
    )
    
    def execute(self, context):
        scene = context.scene
        remap_count = 0
        
        # Get base path from properties
        base_path = scene.bst_path_props.new_path
        if not base_path.endswith(('\\', '/')):
            base_path += '/'
        
        # Process all the images that are selected
        for img in bpy.data.images:
            if hasattr(img, "bst_selected") and img.bst_selected:
                # Use base path + datablock name
                full_path = base_path + img.name
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
    )
    
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
    )
    
    new_name: StringProperty(
        name="New Name",
        description="New name for the datablock",
        default=""
    )
    
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
    )
    
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
    bl_description = "Set the base path to use the active material's name"
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
            # Set the base path with material name
            base_path = "//textures/" + material_name + "/"
            context.scene.bst_path_props.new_path = base_path
            self.report({'INFO'}, f"Set base path to {base_path}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "No active material found on the active object or in the node editor")
            return {'CANCELLED'}

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
        
        # Bulk operations section
        box = layout.box()
        row = box.row()
        row.prop(path_props, "show_bulk_operations", 
                 icon="TRIA_DOWN" if path_props.show_bulk_operations else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Bulk Operations")
        
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
            
            # Update path UI to clarify behavior
            row = box.row(align=True)
            row.prop(path_props, "new_path", text="Base Path")
            reuse_op = row.operator("bst.reuse_material_path", text="", icon='FILE_REFRESH')
            # Move the hint to its own row
            box.label(text="(datablock name will be appended)")
            
            # Sorting option
            row = box.row()
            row.prop(path_props, "sort_by_selected", text="Sort by Selected")
            
            # Bulk remap button - always visible, disabled if none selected
            row = box.row()
            any_selected = any(hasattr(img, "bst_selected") and img.bst_selected for img in bpy.data.images)
            row.enabled = any_selected
            row.operator("bst.bulk_remap", text="Remap Selected", icon='FILE_REFRESH')
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
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        path_props = scene.bst_path_props
        
        # Bulk operations section
        box = layout.box()
        row = box.row()
        row.prop(path_props, "show_bulk_operations", 
                 icon="TRIA_DOWN" if path_props.show_bulk_operations else "TRIA_RIGHT",
                 icon_only=True, emboss=False)
        row.label(text="Bulk Operations")
        
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
            
            # Update path UI to clarify behavior
            row = box.row(align=True)
            row.prop(path_props, "new_path", text="Base Path")
            reuse_op = row.operator("bst.reuse_material_path", text="", icon='FILE_REFRESH')
            # Move the hint to its own row
            box.label(text="(datablock name will be appended)")
            
            # Sorting option
            row = box.row()
            row.prop(path_props, "sort_by_selected", text="Sort by Selected")
            
            # Bulk remap button - always visible, disabled if none selected
            row = box.row()
            any_selected = any(hasattr(img, "bst_selected") and img.bst_selected for img in bpy.data.images)
            row.enabled = any_selected
            row.operator("bst.bulk_remap", text="Remap Selected", icon='FILE_REFRESH')
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