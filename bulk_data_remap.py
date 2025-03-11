import bpy
import re

# Regular expression to match numbered suffixes like .001, .002, etc.
NUMBERED_SUFFIX_PATTERN = re.compile(r'(.*?)\.(\d{3,})$')

# Register properties for data remap settings
def register_dataremap_properties():
    bpy.types.Scene.dataremap_images = bpy.props.BoolProperty(
        name="Images",
        description="Find and remap duplicate images",
        default=True
    )
    
    bpy.types.Scene.dataremap_materials = bpy.props.BoolProperty(
        name="Materials",
        description="Find and remap duplicate materials",
        default=True
    )
    
    bpy.types.Scene.dataremap_fonts = bpy.props.BoolProperty(
        name="Fonts",
        description="Find and remap duplicate fonts",
        default=True
    )
    
    # Add properties for showing duplicate lists
    bpy.types.Scene.show_image_duplicates = bpy.props.BoolProperty(
        name="Show Image Duplicates",
        description="Show list of duplicate images",
        default=False
    )
    
    bpy.types.Scene.show_material_duplicates = bpy.props.BoolProperty(
        name="Show Material Duplicates",
        description="Show list of duplicate materials",
        default=False
    )
    
    bpy.types.Scene.show_font_duplicates = bpy.props.BoolProperty(
        name="Show Font Duplicates",
        description="Show list of duplicate fonts",
        default=False
    )
    
    # Dictionary to store excluded groups
    if not hasattr(bpy.types.Scene, "excluded_remap_groups"):
        bpy.types.Scene.excluded_remap_groups = {}

def unregister_dataremap_properties():
    del bpy.types.Scene.dataremap_images
    del bpy.types.Scene.dataremap_materials
    del bpy.types.Scene.dataremap_fonts
    del bpy.types.Scene.show_image_duplicates
    del bpy.types.Scene.show_material_duplicates
    del bpy.types.Scene.show_font_duplicates
    if hasattr(bpy.types.Scene, "excluded_remap_groups"):
        del bpy.types.Scene.excluded_remap_groups

def get_base_name(name):
    """Extract the base name without numbered suffix"""
    match = NUMBERED_SUFFIX_PATTERN.match(name)
    if match:
        return match.group(1)  # Return the base name
    return name

def find_data_groups(data_collection):
    """Group data blocks by their base name"""
    groups = {}
    
    for data in data_collection:
        base_name = get_base_name(data.name)
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(data)
    
    # Filter out groups with only one item (no duplicates)
    return {name: items for name, items in groups.items() if len(items) > 1}

def find_target_data(data_group):
    """Find the target data block to remap to"""
    # First, try to find a data block without a numbered suffix
    for data in data_group:
        if get_base_name(data.name) == data.name:
            return data
    
    # If no unnumbered version exists, find the "youngest" version (highest number)
    youngest = data_group[0]
    highest_suffix = 0
    
    for data in data_group:
        match = NUMBERED_SUFFIX_PATTERN.match(data.name)
        if match:
            suffix_num = int(match.group(2))
            if suffix_num > highest_suffix:
                highest_suffix = suffix_num
                youngest = data
    
    return youngest

def clean_data_names(data_collection):
    """Remove numbered suffixes from all data blocks"""
    cleaned_count = 0
    
    for data in data_collection:
        base_name = get_base_name(data.name)
        if base_name != data.name:
            data.name = base_name
            cleaned_count += 1
    
    return cleaned_count

def remap_data_blocks(context, remap_images, remap_materials, remap_fonts):
    """Remap redundant data blocks to their base versions like Blender's Remap Users function, and clean up names."""
    remapped_count = 0
    cleaned_count = 0
    
    # Process images
    if remap_images:
        # First remap duplicates
        image_groups = find_data_groups(bpy.data.images)
        for base_name, images in image_groups.items():
            # Skip excluded groups
            if f"images:{base_name}" in context.scene.excluded_remap_groups:
                continue
                
            target_image = find_target_data(images)
            
            # Rename the target if it has a numbered suffix and is the youngest
            if get_base_name(target_image.name) != target_image.name:
                target_image.name = get_base_name(target_image.name)
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for image in images:
                    if image != target_image:
                        # Use the low-level ID remap functionality
                        image.user_remap(target_image)
                        remapped_count += 1
            except Exception as e:
                print(f"Error using built-in remap for images: {e}")
                # Fall back to manual remapping
                for image in images:
                    if image != target_image:
                        # Find all users of this image and replace with target
                        for mat in bpy.data.materials:
                            if mat.use_nodes:
                                for node in mat.node_tree.nodes:
                                    if node.type == 'TEX_IMAGE' and node.image == image:
                                        node.image = target_image
                                        remapped_count += 1
                        
                        # Check for other possible users (like brushes, world textures, etc.)
                        for brush in bpy.data.brushes:
                            if hasattr(brush, 'texture') and brush.texture and brush.texture.type == 'IMAGE':
                                if hasattr(brush.texture, 'image') and brush.texture.image == image:
                                    brush.texture.image = target_image
                                    remapped_count += 1
                        
                        # Check for world textures
                        for world in bpy.data.worlds:
                            if world.use_nodes:
                                for node in world.node_tree.nodes:
                                    if node.type == 'TEX_IMAGE' and node.image == image:
                                        node.image = target_image
                                        remapped_count += 1
            
            # Keep duplicates with 0 users (don't remove them)
            # This matches Blender's Remap Users behavior
        
        # Then clean up any remaining numbered suffixes
        cleaned_count += clean_data_names(bpy.data.images)
    
    # Process materials
    if remap_materials:
        # First remap duplicates
        material_groups = find_data_groups(bpy.data.materials)
        for base_name, materials in material_groups.items():
            # Skip excluded groups
            if f"materials:{base_name}" in context.scene.excluded_remap_groups:
                continue
                
            target_material = find_target_data(materials)
            
            # Rename the target if it has a numbered suffix and is the youngest
            if get_base_name(target_material.name) != target_material.name:
                target_material.name = get_base_name(target_material.name)
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for material in materials:
                    if material != target_material:
                        # Use the low-level ID remap functionality
                        material.user_remap(target_material)
                        remapped_count += 1
            except Exception as e:
                print(f"Error using built-in remap for materials: {e}")
                # Fall back to manual remapping
                for material in materials:
                    if material != target_material:
                        # Find all users of this material and replace with target
                        
                        # Check mesh objects
                        for obj in bpy.data.objects:
                            if obj.type == 'MESH':
                                for i, mat_slot in enumerate(obj.material_slots):
                                    if mat_slot.material == material:
                                        obj.material_slots[i].material = target_material
                                        remapped_count += 1
                        
                        # Check node groups that might use materials
                        for node_group in bpy.data.node_groups:
                            for node in node_group.nodes:
                                if hasattr(node, 'material') and node.material == material:
                                    node.material = target_material
                                    remapped_count += 1
                        
                        # Check other materials' node trees for material references
                        for other_mat in bpy.data.materials:
                            if other_mat.use_nodes:
                                for node in other_mat.node_tree.nodes:
                                    if hasattr(node, 'material') and node.material == material:
                                        node.material = target_material
                                        remapped_count += 1
                        
                        # Check for material overrides in collections
                        for coll in bpy.data.collections:
                            if hasattr(coll, 'override_library'):
                                if coll.override_library:
                                    for override in coll.override_library.properties:
                                        if override.rna_type.identifier == 'MaterialSlot' and override.value == material:
                                            override.value = target_material
                                            remapped_count += 1
                        
                        # Check for grease pencil materials - compatible with Blender 4.3.2
                        # In Blender 4.3, grease pencil layers don't have direct material references
                        # Instead, materials are assigned to the grease pencil data object itself or to the object using the grease pencil data
                        for gpencil in bpy.data.grease_pencils:
                            # Check material slots on the grease pencil object
                            if hasattr(gpencil, 'materials'):
                                for i, mat_slot in enumerate(gpencil.materials):
                                    if mat_slot == material:
                                        gpencil.materials[i] = target_material
                                        remapped_count += 1
                            
                            # Check for any objects using this grease pencil data
                            for obj in bpy.data.objects:
                                if obj.type == 'GPENCIL' and hasattr(obj, 'material_slots'):
                                    for i, mat_slot in enumerate(obj.material_slots):
                                        if mat_slot.material == material:
                                            obj.material_slots[i].material = target_material
                                            remapped_count += 1
            
            # Keep duplicates with 0 users (don't remove them)
            # This matches Blender's Remap Users behavior
        
        # Then clean up any remaining numbered suffixes
        cleaned_count += clean_data_names(bpy.data.materials)
    
    # Process fonts
    if remap_fonts:
        # First remap duplicates
        font_groups = find_data_groups(bpy.data.fonts)
        for base_name, fonts in font_groups.items():
            # Skip excluded groups
            if f"fonts:{base_name}" in context.scene.excluded_remap_groups:
                continue
                
            target_font = find_target_data(fonts)
            
            # Rename the target if it has a numbered suffix and is the youngest
            if get_base_name(target_font.name) != target_font.name:
                target_font.name = get_base_name(target_font.name)
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for font in fonts:
                    if font != target_font:
                        # Use the low-level ID remap functionality
                        font.user_remap(target_font)
                        remapped_count += 1
            except Exception as e:
                print(f"Error using built-in remap for fonts: {e}")
                # Fall back to manual remapping
                for font in fonts:
                    if font != target_font:
                        # Find all users of this font and replace with target
                        for text in bpy.data.curves:
                            if text.type == 'FONT':
                                # Check all font slots
                                if text.font == font:
                                    text.font = target_font
                                    remapped_count += 1
                                if hasattr(text, 'font_bold') and text.font_bold == font:
                                    text.font_bold = target_font
                                    remapped_count += 1
                                if hasattr(text, 'font_italic') and text.font_italic == font:
                                    text.font_italic = target_font
                                    remapped_count += 1
                                if hasattr(text, 'font_bold_italic') and text.font_bold_italic == font:
                                    text.font_bold_italic = target_font
                                    remapped_count += 1
            
            # Keep duplicates with 0 users (don't remove them)
            # This matches Blender's Remap Users behavior
        
        # Then clean up any remaining numbered suffixes
        cleaned_count += clean_data_names(bpy.data.fonts)
    
    # Force an update of the dependency graph to ensure all users are properly updated
    if context.view_layer:
        context.view_layer.update()
    
    return remapped_count, cleaned_count

class DATAREMAP_OT_RemapData(bpy.types.Operator):
    """Remap redundant data blocks to reduce duplicates"""
    bl_idname = "scene.bulk_data_remap"
    bl_label = "Remap Data"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Get settings from scene properties
        remap_images = context.scene.dataremap_images
        remap_materials = context.scene.dataremap_materials
        remap_fonts = context.scene.dataremap_fonts
        
        # Count duplicates before remapping
        image_groups = find_data_groups(bpy.data.images) if remap_images else {}
        material_groups = find_data_groups(bpy.data.materials) if remap_materials else {}
        font_groups = find_data_groups(bpy.data.fonts) if remap_fonts else {}
        
        total_duplicates = sum(len(group) - 1 for groups in [image_groups, material_groups, font_groups] for group in groups.values())
        
        # Count data blocks with numbered suffixes
        total_numbered = 0
        if remap_images:
            total_numbered += sum(1 for img in bpy.data.images if get_base_name(img.name) != img.name)
        if remap_materials:
            total_numbered += sum(1 for mat in bpy.data.materials if get_base_name(mat.name) != mat.name)
        if remap_fonts:
            total_numbered += sum(1 for font in bpy.data.fonts if get_base_name(font.name) != font.name)
        
        if total_duplicates == 0 and total_numbered == 0:
            self.report({'INFO'}, "No data blocks to process")
            return {'CANCELLED'}
        
        # Perform the remapping and cleaning
        remapped_count, cleaned_count = remap_data_blocks(
            context,
            remap_images,
            remap_materials,
            remap_fonts
        )
        
        # Report results
        if remapped_count > 0 and cleaned_count > 0:
            self.report({'INFO'}, f"Remapped {remapped_count} data blocks and cleaned {cleaned_count} names")
        elif remapped_count > 0:
            self.report({'INFO'}, f"Remapped {remapped_count} data blocks")
        elif cleaned_count > 0:
            self.report({'INFO'}, f"Cleaned {cleaned_count} data block names")
        else:
            self.report({'INFO'}, "No changes made")
        
        return {'FINISHED'}

# Add a new operator for purging unused data
class DATAREMAP_OT_PurgeUnused(bpy.types.Operator):
    """Purge all unused data-blocks from the file (equivalent to File > Clean Up > Purge Unused Data)"""
    bl_idname = "scene.purge_unused_data"
    bl_label = "Purge Unused Data"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Call Blender's built-in purge operator
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        
        # Report success
        self.report({'INFO'}, "Purged all unused data blocks")
        return {'FINISHED'}

# Add a new operator for toggling group exclusion
class DATAREMAP_OT_ToggleGroupExclusion(bpy.types.Operator):
    """Toggle whether this group should be included in remapping"""
    bl_idname = "scene.toggle_group_exclusion"
    bl_label = "Toggle Group"
    bl_options = {'REGISTER', 'UNDO'}
    
    group_key: bpy.props.StringProperty(
        name="Group Key",
        description="Unique identifier for the group",
        default=""
    )
    
    data_type: bpy.props.StringProperty(
        name="Data Type",
        description="Type of data (images, materials, fonts)",
        default=""
    )
    
    def execute(self, context):
        # Initialize the dictionary if it doesn't exist
        if not hasattr(context.scene, "excluded_remap_groups"):
            context.scene.excluded_remap_groups = {}
        
        # Create a unique key for this group
        key = f"{self.data_type}:{self.group_key}"
        
        # Toggle the exclusion state
        if key in context.scene.excluded_remap_groups:
            del context.scene.excluded_remap_groups[key]
        else:
            context.scene.excluded_remap_groups[key] = True
        
        return {'FINISHED'}

class VIEW3D_PT_BulkDataRemap(bpy.types.Panel):
    """Bulk Data Remap Panel"""
    bl_label = "Bulk Data Remap"
    bl_idname = "VIEW3D_PT_bulk_data_remap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 1  # Lower number means higher in the list
    
    def draw(self, context):
        layout = self.layout
        
        # Data Remapper section
        box = layout.box()
        box.label(text="Data Remapper")
        
        # Add description
        col = box.column()
        col.label(text="Find and remap redundant data")
        col.label(text="blocks like .001, .002 duplicates")
        
        # Add data type options with checkboxes
        col = box.column(align=True)
        
        # Count duplicates and numbered suffixes for each type
        image_groups = find_data_groups(bpy.data.images)
        material_groups = find_data_groups(bpy.data.materials)
        font_groups = find_data_groups(bpy.data.fonts)
        
        image_duplicates = sum(len(group) - 1 for group in image_groups.values())
        material_duplicates = sum(len(group) - 1 for group in material_groups.values())
        font_duplicates = sum(len(group) - 1 for group in font_groups.values())
        
        image_numbered = sum(1 for img in bpy.data.images if get_base_name(img.name) != img.name)
        material_numbered = sum(1 for mat in bpy.data.materials if get_base_name(mat.name) != mat.name)
        font_numbered = sum(1 for font in bpy.data.fonts if get_base_name(font.name) != font.name)
        
        # Initialize excluded_remap_groups if it doesn't exist
        if not hasattr(context.scene, "excluded_remap_groups"):
            context.scene.excluded_remap_groups = {}
        
        # Add checkboxes with counts and dropdown toggles
        # Images
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("scene.toggle_data_type", text="", icon='IMAGE_DATA', depress=context.scene.dataremap_images)
        op.data_type = "images"
        
        # Use different text color based on activation
        if context.scene.dataremap_images:
            sub_row.label(text="Images")
        else:
            # Create a row with a different color for inactive text
            sub_row.label(text="Images", icon='RADIOBUT_OFF')
        
        sub_row = split.row()
        if image_duplicates > 0:
            sub_row.prop(context.scene, "show_image_duplicates", 
                         text=f"{image_duplicates} duplicates", 
                         icon='DISCLOSURE_TRI_DOWN' if context.scene.show_image_duplicates else 'DISCLOSURE_TRI_RIGHT',
                         emboss=False)
        elif image_numbered > 0:
            sub_row.label(text=f"{image_numbered} numbered")
        else:
            sub_row.label(text="0 duplicates")
        
        # Show image duplicates if enabled
        if context.scene.show_image_duplicates and image_duplicates > 0 and context.scene.dataremap_images:
            box_dup = col.box()
            for base_name, images in image_groups.items():
                if len(images) > 1:
                    row = box_dup.row()
                    
                    # Add checkbox to include/exclude this group
                    group_key = f"images:{base_name}"
                    is_excluded = group_key in context.scene.excluded_remap_groups
                    
                    op = row.operator("scene.toggle_group_exclusion", 
                                      text="", 
                                      icon='CHECKBOX_HLT' if not is_excluded else 'CHECKBOX_DEHLT',
                                      emboss=False)
                    op.group_key = base_name
                    op.data_type = "images"
                    
                    row.label(text=f"{base_name}: {len(images)} versions")
                    
                    # Only show details if not excluded
                    if not is_excluded:
                        for img in images:
                            sub_row = box_dup.row()
                            sub_row.label(text=f"  • {img.name}")
        
        # Materials
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("scene.toggle_data_type", text="", icon='MATERIAL', depress=context.scene.dataremap_materials)
        op.data_type = "materials"
        
        # Use different text color based on activation
        if context.scene.dataremap_materials:
            sub_row.label(text="Materials")
        else:
            # Create a row with a different color for inactive text
            sub_row.label(text="Materials", icon='RADIOBUT_OFF')
        
        sub_row = split.row()
        if material_duplicates > 0:
            sub_row.prop(context.scene, "show_material_duplicates", 
                         text=f"{material_duplicates} duplicates", 
                         icon='DISCLOSURE_TRI_DOWN' if context.scene.show_material_duplicates else 'DISCLOSURE_TRI_RIGHT',
                         emboss=False)
        elif material_numbered > 0:
            sub_row.label(text=f"{material_numbered} numbered")
        else:
            sub_row.label(text="0 duplicates")
        
        # Show material duplicates if enabled
        if context.scene.show_material_duplicates and material_duplicates > 0 and context.scene.dataremap_materials:
            box_dup = col.box()
            for base_name, materials in material_groups.items():
                if len(materials) > 1:
                    row = box_dup.row()
                    
                    # Add checkbox to include/exclude this group
                    group_key = f"materials:{base_name}"
                    is_excluded = group_key in context.scene.excluded_remap_groups
                    
                    op = row.operator("scene.toggle_group_exclusion", 
                                      text="", 
                                      icon='CHECKBOX_HLT' if not is_excluded else 'CHECKBOX_DEHLT',
                                      emboss=False)
                    op.group_key = base_name
                    op.data_type = "materials"
                    
                    row.label(text=f"{base_name}: {len(materials)} versions")
                    
                    # Only show details if not excluded
                    if not is_excluded:
                        for mat in materials:
                            sub_row = box_dup.row()
                            sub_row.label(text=f"  • {mat.name}")
        
        # Fonts
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("scene.toggle_data_type", text="", icon='FONT_DATA', depress=context.scene.dataremap_fonts)
        op.data_type = "fonts"
        
        # Use different text color based on activation
        if context.scene.dataremap_fonts:
            sub_row.label(text="Fonts")
        else:
            # Create a row with a different color for inactive text
            sub_row.label(text="Fonts", icon='RADIOBUT_OFF')
        
        sub_row = split.row()
        if font_duplicates > 0:
            sub_row.prop(context.scene, "show_font_duplicates", 
                         text=f"{font_duplicates} duplicates", 
                         icon='DISCLOSURE_TRI_DOWN' if context.scene.show_font_duplicates else 'DISCLOSURE_TRI_RIGHT',
                         emboss=False)
        elif font_numbered > 0:
            sub_row.label(text=f"{font_numbered} numbered")
        else:
            sub_row.label(text="0 duplicates")
        
        # Show font duplicates if enabled
        if context.scene.show_font_duplicates and font_duplicates > 0 and context.scene.dataremap_fonts:
            box_dup = col.box()
            for base_name, fonts in font_groups.items():
                if len(fonts) > 1:
                    row = box_dup.row()
                    
                    # Add checkbox to include/exclude this group
                    group_key = f"fonts:{base_name}"
                    is_excluded = group_key in context.scene.excluded_remap_groups
                    
                    op = row.operator("scene.toggle_group_exclusion", 
                                      text="", 
                                      icon='CHECKBOX_HLT' if not is_excluded else 'CHECKBOX_DEHLT',
                                      emboss=False)
                    op.group_key = base_name
                    op.data_type = "fonts"
                    
                    row.label(text=f"{base_name}: {len(fonts)} versions")
                    
                    # Only show details if not excluded
                    if not is_excluded:
                        for font in fonts:
                            sub_row = box_dup.row()
                            sub_row.label(text=f"  • {font.name}")
        
        # Add the operator button
        row = box.row()
        row.scale_y = 1.5
        row.operator("scene.bulk_data_remap")
        
        # Show total counts
        total_duplicates = image_duplicates + material_duplicates + font_duplicates
        total_numbered = image_numbered + material_numbered + font_numbered
        
        if total_duplicates > 0 or total_numbered > 0:
            box.separator()
            if total_duplicates > 0:
                box.label(text=f"Found {total_duplicates} duplicate data blocks")
            if total_numbered > 0:
                box.label(text=f"Found {total_numbered} numbered data blocks")
        else:
            box.label(text="No data blocks to process")
        
        # Add a separator and purge button
        box.separator()
        row = box.row()
        row.operator("scene.purge_unused_data", icon='TRASH')

# Add a new operator for toggling data types
class DATAREMAP_OT_ToggleDataType(bpy.types.Operator):
    """Toggle whether this data type should be included in remapping"""
    bl_idname = "scene.toggle_data_type"
    bl_label = "Toggle Data Type"
    bl_options = {'REGISTER', 'UNDO'}
    
    data_type: bpy.props.StringProperty(
        name="Data Type",
        description="Type of data (images, materials, fonts)",
        default=""
    )
    
    def execute(self, context):
        if self.data_type == "images":
            context.scene.dataremap_images = not context.scene.dataremap_images
        elif self.data_type == "materials":
            context.scene.dataremap_materials = not context.scene.dataremap_materials
        elif self.data_type == "fonts":
            context.scene.dataremap_fonts = not context.scene.dataremap_fonts
        
        return {'FINISHED'}

# List of all classes in this module
classes = (
    DATAREMAP_OT_RemapData,
    DATAREMAP_OT_PurgeUnused,
    DATAREMAP_OT_ToggleDataType,
    DATAREMAP_OT_ToggleGroupExclusion,
    VIEW3D_PT_BulkDataRemap,
)

# Registration
def register():
    register_dataremap_properties()
    
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    unregister_dataremap_properties() 