import bpy # type: ignore
import re
import os
import sys
import subprocess

# Import ghost buster functionality
from ..ops.ghost_buster import GhostBuster, GhostDetector, ResyncEnforce
from ..utils import compat

# Regular expression to match numbered suffixes like .001, .002, _001, _0001, etc.
NUMBERED_SUFFIX_PATTERN = re.compile(r'(.*?)[._](\d{3,})$')

# Function to check if any datablocks in a collection are linked from a library
def has_linked_datablocks(data_collection):
    """Check if any datablocks in the collection are linked from a library"""
    for data in data_collection:
        if data.users > 0 and hasattr(data, 'library') and data.library is not None:
            return True
    return False

# Register properties for data remap settings
def register_dataremap_properties():
    bpy.types.Scene.dataremap_images = bpy.props.BoolProperty(  # type: ignore
        name="Images",
        description="Find and remap duplicate images",
        default=True
    )
    
    bpy.types.Scene.dataremap_materials = bpy.props.BoolProperty(  # type: ignore
        name="Materials",
        description="Find and remap duplicate materials",
        default=True
    )
    
    bpy.types.Scene.dataremap_fonts = bpy.props.BoolProperty(  # type: ignore
        name="Fonts",
        description="Find and remap duplicate fonts",
        default=True
    )
    
    bpy.types.Scene.dataremap_worlds = bpy.props.BoolProperty(  # type: ignore
        name="Worlds",
        description="Find and remap duplicate worlds",
        default=True
    )
    
    # Add properties for showing duplicate lists
    bpy.types.Scene.show_image_duplicates = bpy.props.BoolProperty(  # type: ignore
        name="Show Image Duplicates",
        description="Show list of duplicate images",
        default=False
    )
    
    bpy.types.Scene.show_material_duplicates = bpy.props.BoolProperty(  # type: ignore
        name="Show Material Duplicates",
        description="Show list of duplicate materials",
        default=False
    )
    
    bpy.types.Scene.show_font_duplicates = bpy.props.BoolProperty(  # type: ignore
        name="Show Font Duplicates",
        description="Show list of duplicate fonts",
        default=False
    )
    
    bpy.types.Scene.show_world_duplicates = bpy.props.BoolProperty(  # type: ignore
        name="Show World Duplicates",
        description="Show list of duplicate worlds",
        default=False
    )
    
    # Sort by selected properties for each data type
    bpy.types.Scene.dataremap_sort_images = bpy.props.BoolProperty(  # type: ignore
        name="Sort Images by Selected",
        description="Show selected image groups at the top of the list",
        default=False
    )
    bpy.types.Scene.dataremap_sort_materials = bpy.props.BoolProperty(  # type: ignore
        name="Sort Materials by Selected",
        description="Show selected material groups at the top of the list",
        default=False
    )
    bpy.types.Scene.dataremap_sort_fonts = bpy.props.BoolProperty(  # type: ignore
        name="Sort Fonts by Selected",
        description="Show selected font groups at the top of the list",
        default=False
    )
    bpy.types.Scene.dataremap_sort_worlds = bpy.props.BoolProperty(  # type: ignore
        name="Sort Worlds by Selected",
        description="Show selected world groups at the top of the list",
        default=False
    )
    
    # Search filter properties for each data type
    bpy.types.Scene.dataremap_search_images = bpy.props.StringProperty(  # type: ignore
        name="Search Images",
        description="Filter images by name (case-insensitive)",
        default=""
    )
    
    bpy.types.Scene.dataremap_search_materials = bpy.props.StringProperty(  # type: ignore
        name="Search Materials",
        description="Filter materials by name (case-insensitive)",
        default=""
    )
    
    bpy.types.Scene.dataremap_search_fonts = bpy.props.StringProperty(  # type: ignore
        name="Search Fonts",
        description="Filter fonts by name (case-insensitive)",
        default=""
    )
    
    bpy.types.Scene.dataremap_search_worlds = bpy.props.StringProperty(  # type: ignore
        name="Search Worlds",
        description="Filter worlds by name (case-insensitive)",
        default=""
    )
    
    # Dictionary to store excluded groups
    if not hasattr(bpy.types.Scene, "excluded_remap_groups"):
        bpy.types.Scene.excluded_remap_groups = {}
        
    # Dictionary to store expanded groups
    if not hasattr(bpy.types.Scene, "expanded_remap_groups"):
        bpy.types.Scene.expanded_remap_groups = {}
        
    # Store the last clicked group for shift-click range selection
    if not hasattr(bpy.types.Scene, "last_clicked_group"):
        bpy.types.Scene.last_clicked_group = {}
    
    # Ghost Buster properties
    bpy.types.Scene.ghost_buster_delete_low_priority = bpy.props.BoolProperty(  # type: ignore
        name="Delete Low Priority Ghosts",
        description="Delete objects not in scenes with no legitimate use and users < 2",
        default=False
    )

def unregister_dataremap_properties():
    del bpy.types.Scene.dataremap_images
    del bpy.types.Scene.dataremap_materials
    del bpy.types.Scene.dataremap_fonts
    del bpy.types.Scene.dataremap_worlds
    del bpy.types.Scene.show_image_duplicates
    del bpy.types.Scene.show_material_duplicates
    del bpy.types.Scene.show_font_duplicates
    del bpy.types.Scene.show_world_duplicates
    if hasattr(bpy.types.Scene, "excluded_remap_groups"):
        del bpy.types.Scene.excluded_remap_groups
    if hasattr(bpy.types.Scene, "expanded_remap_groups"):
        del bpy.types.Scene.expanded_remap_groups
    if hasattr(bpy.types.Scene, "last_clicked_group"):
        del bpy.types.Scene.last_clicked_group
    
    # Delete sort properties
    del bpy.types.Scene.dataremap_sort_images
    del bpy.types.Scene.dataremap_sort_materials
    del bpy.types.Scene.dataremap_sort_fonts
    del bpy.types.Scene.dataremap_sort_worlds
    
    # Delete ghost buster properties
    if hasattr(bpy.types.Scene, "ghost_buster_delete_low_priority"):
        del bpy.types.Scene.ghost_buster_delete_low_priority

def get_base_name(name):
    """Extract the base name without numbered suffix"""
    match = NUMBERED_SUFFIX_PATTERN.match(name)
    if match:
        return match.group(1)  # Return the base name
    return name

def find_data_groups(data_collection):
    """Group data blocks by their base name, excluding those with no users or linked from libraries"""
    groups = {}
    
    for data in data_collection:
        # Skip datablocks with no users
        if data.users == 0:
            continue
            
        # Skip linked datablocks
        if hasattr(data, 'library') and data.library is not None:
            continue
            
        base_name = get_base_name(data.name)
        
        # Only group local datablocks
        if base_name not in groups:
            groups[base_name] = []
        groups[base_name].append(data)
    
    # Filter out groups with only one item (no duplicates)
    # Also filter out groups where all items are linked
    return {name: items for name, items in groups.items() 
            if len(items) > 1 and any(not (hasattr(item, 'library') and item.library is not None) for item in items)}

def find_target_data(data_group):
    """Find the target data block to remap to"""
    # Filter out linked datablocks
    local_data_group = [data for data in data_group if not (hasattr(data, 'library') and data.library is not None)]
    
    # If all datablocks are linked, return the first one (though this shouldn't happen due to earlier checks)
    if not local_data_group:
        return data_group[0]
    
    # First, try to find a data block without a numbered suffix
    for data in local_data_group:
        if get_base_name(data.name) == data.name:
            return data
    
    # If no unnumbered version exists, find the "youngest" version (highest number)
    youngest = local_data_group[0]
    highest_suffix = 0
    
    for data in local_data_group:
        match = NUMBERED_SUFFIX_PATTERN.match(data.name)
        if match:
            suffix_num = int(match.group(2))
            if suffix_num > highest_suffix:
                highest_suffix = suffix_num
                youngest = data
    
    return youngest

def clean_data_names(data_collection):
    """Remove numbered suffixes from all data blocks with users"""
    cleaned_count = 0
    
    for data in data_collection:
        # Skip datablocks with no users
        if data.users == 0:
            continue
            
        # Skip linked datablocks
        if hasattr(data, 'library') and data.library is not None:
            continue
            
        base_name = get_base_name(data.name)
        if base_name != data.name:
            data.name = base_name
            cleaned_count += 1
    
    return cleaned_count

def remap_data_blocks(context, remap_images, remap_materials, remap_fonts, remap_worlds):
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
                try:
                    target_image.name = get_base_name(target_image.name)
                except AttributeError:
                    # Skip if the target is linked and can't be renamed
                    print(f"Warning: Cannot rename linked image {target_image.name}")
                    continue
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for image in images:
                    if image != target_image:
                        try:
                            # Use the low-level ID remap functionality
                            image.user_remap(target_image)
                            remapped_count += 1
                        except AttributeError:
                            # Skip if the image is linked and can't be remapped
                            print(f"Warning: Cannot remap linked image {image.name}")
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
                                        try:
                                            node.image = target_image
                                            remapped_count += 1
                                        except AttributeError:
                                            # Skip if the node is in a linked material
                                            print(f"Warning: Cannot modify linked material {mat.name}")
                        
                        # Check for other possible users (like brushes, world textures, etc.)
                        for brush in bpy.data.brushes:
                            if hasattr(brush, 'texture') and brush.texture and brush.texture.type == 'IMAGE':
                                if hasattr(brush.texture, 'image') and brush.texture.image == image:
                                    try:
                                        brush.texture.image = target_image
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the brush is linked
                                        print(f"Warning: Cannot modify linked brush {brush.name}")
                        
                        # Check for world textures
                        for world in bpy.data.worlds:
                            if world.use_nodes:
                                for node in world.node_tree.nodes:
                                    if node.type == 'TEX_IMAGE' and node.image == image:
                                        try:
                                            node.image = target_image
                                            remapped_count += 1
                                        except AttributeError:
                                            # Skip if the world is linked
                                            print(f"Warning: Cannot modify linked world {world.name}")
            
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
                try:
                    target_material.name = get_base_name(target_material.name)
                except AttributeError:
                    # Skip if the target is linked and can't be renamed
                    print(f"Warning: Cannot rename linked material {target_material.name}")
                    continue
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for material in materials:
                    if material != target_material:
                        try:
                            # Use the low-level ID remap functionality
                            material.user_remap(target_material)
                            remapped_count += 1
                        except AttributeError:
                            # Skip if the material is linked and can't be remapped
                            print(f"Warning: Cannot remap linked material {material.name}")
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
                                        try:
                                            obj.material_slots[i].material = target_material
                                            remapped_count += 1
                                        except AttributeError:
                                            # Skip if the object is linked
                                            print(f"Warning: Cannot modify linked object {obj.name}")
                        
                        # Check node groups that might use materials
                        for node_group in bpy.data.node_groups:
                            for node in node_group.nodes:
                                if hasattr(node, 'material') and node.material == material:
                                    try:
                                        node.material = target_material
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the node group is linked
                                        print(f"Warning: Cannot modify linked node group {node_group.name}")
                        
                        # Check other materials' node trees for material references
                        for other_mat in bpy.data.materials:
                            if other_mat.use_nodes:
                                for node in other_mat.node_tree.nodes:
                                    if hasattr(node, 'material') and node.material == material:
                                        try:
                                            node.material = target_material
                                            remapped_count += 1
                                        except AttributeError:
                                            # Skip if the material is linked
                                            print(f"Warning: Cannot modify linked material {other_mat.name}")
                        
                        # Check for material overrides in collections
                        for coll in bpy.data.collections:
                            if hasattr(coll, 'override_library'):
                                if coll.override_library:
                                    for override in coll.override_library.properties:
                                        if override.rna_type.identifier == 'MaterialSlot' and override.value == material:
                                            try:
                                                override.value = target_material
                                                remapped_count += 1
                                            except AttributeError:
                                                # Skip if the collection is linked
                                                print(f"Warning: Cannot modify linked collection {coll.name}")
                        
                        # Check for grease pencil materials - compatible with Blender 4.3.2
                        # In Blender 4.3, grease pencil layers don't have direct material references
                        # Instead, materials are assigned to the grease pencil data object itself or to the object using the grease pencil data
                        for gpencil in bpy.data.grease_pencils:
                            # Check material slots on the grease pencil object
                            if hasattr(gpencil, 'materials'):
                                for i, mat_slot in enumerate(gpencil.materials):
                                    if mat_slot == material:
                                        try:
                                            gpencil.materials[i] = target_material
                                            remapped_count += 1
                                        except AttributeError:
                                            # Skip if the grease pencil is linked
                                            print(f"Warning: Cannot modify linked grease pencil {gpencil.name}")
                            
                            # Check for any objects using this grease pencil data
                            for obj in bpy.data.objects:
                                if obj.type == 'GPENCIL' and hasattr(obj, 'material_slots'):
                                    for i, mat_slot in enumerate(obj.material_slots):
                                        if mat_slot.material == material:
                                            try:
                                                obj.material_slots[i].material = target_material
                                                remapped_count += 1
                                            except AttributeError:
                                                # Skip if the object is linked
                                                print(f"Warning: Cannot modify linked object {obj.name}")
            
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
                try:
                    target_font.name = get_base_name(target_font.name)
                except AttributeError:
                    # Skip if the target is linked and can't be renamed
                    print(f"Warning: Cannot rename linked font {target_font.name}")
                    continue
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for font in fonts:
                    if font != target_font:
                        try:
                            # Use the low-level ID remap functionality
                            font.user_remap(target_font)
                            remapped_count += 1
                        except AttributeError:
                            # Skip if the font is linked and can't be remapped
                            print(f"Warning: Cannot remap linked font {font.name}")
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
                                    try:
                                        text.font = target_font
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the text is linked
                                        print(f"Warning: Cannot modify linked text {text.name}")
                                if hasattr(text, 'font_bold') and text.font_bold == font:
                                    try:
                                        text.font_bold = target_font
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the text is linked
                                        print(f"Warning: Cannot modify linked text {text.name}")
                                if hasattr(text, 'font_italic') and text.font_italic == font:
                                    try:
                                        text.font_italic = target_font
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the text is linked
                                        print(f"Warning: Cannot modify linked text {text.name}")
                                if hasattr(text, 'font_bold_italic') and text.font_bold_italic == font:
                                    try:
                                        text.font_bold_italic = target_font
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the text is linked
                                        print(f"Warning: Cannot modify linked text {text.name}")
            
            # Keep duplicates with 0 users (don't remove them)
            # This matches Blender's Remap Users behavior
        
        # Then clean up any remaining numbered suffixes
        cleaned_count += clean_data_names(bpy.data.fonts)
    
    # Process worlds
    if remap_worlds:
        # First remap duplicates
        world_groups = find_data_groups(bpy.data.worlds)
        for base_name, worlds in world_groups.items():
            # Skip excluded groups
            if f"worlds:{base_name}" in context.scene.excluded_remap_groups:
                continue
                
            target_world = find_target_data(worlds)
            
            # Rename the target if it has a numbered suffix and is the youngest
            if get_base_name(target_world.name) != target_world.name:
                try:
                    target_world.name = get_base_name(target_world.name)
                except AttributeError:
                    # Skip if the target is linked and can't be renamed
                    print(f"Warning: Cannot rename linked world {target_world.name}")
                    continue
            
            # Try to use Blender's built-in functionality for remapping
            try:
                # First try to use the ID remap functionality directly
                for world in worlds:
                    if world != target_world:
                        try:
                            # Use the low-level ID remap functionality
                            world.user_remap(target_world)
                            remapped_count += 1
                        except AttributeError:
                            # Skip if the world is linked and can't be remapped
                            print(f"Warning: Cannot remap linked world {world.name}")
            except Exception as e:
                print(f"Error using built-in remap for worlds: {e}")
                # Fall back to manual remapping
                for world in worlds:
                    if world != target_world:
                        # Find all users of this world and replace with target
                        
                        # Check scenes
                        for scene in bpy.data.scenes:
                            if scene.world == world:
                                try:
                                    scene.world = target_world
                                    remapped_count += 1
                                except AttributeError:
                                    # Skip if the scene is linked
                                    print(f"Warning: Cannot modify linked scene {scene.name}")
                        
                        # Check world node groups
                        for node_group in bpy.data.node_groups:
                            for node in node_group.nodes:
                                if hasattr(node, 'world') and node.world == world:
                                    try:
                                        node.world = target_world
                                        remapped_count += 1
                                    except AttributeError:
                                        # Skip if the node group is linked
                                        print(f"Warning: Cannot modify linked node group {node_group.name}")
            
            # Keep duplicates with 0 users (don't remove them)
            # This matches Blender's Remap Users behavior
        
        # Then clean up any remaining numbered suffixes
        cleaned_count += clean_data_names(bpy.data.worlds)
    
    # Force an update of the dependency graph to ensure all users are properly updated
    if context.view_layer:
        context.view_layer.update()
    
    return remapped_count, cleaned_count

class DATAREMAP_OT_RemapData(bpy.types.Operator):
    """Remap redundant data blocks to reduce duplicates"""
    bl_idname = "bst.bulk_data_remap"
    bl_label = "Remap Data"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Get settings from scene properties
        remap_images = context.scene.dataremap_images
        remap_materials = context.scene.dataremap_materials
        remap_fonts = context.scene.dataremap_fonts
        remap_worlds = context.scene.dataremap_worlds
        
        # Count duplicates before remapping (only for local datablocks)
        image_groups = find_data_groups(bpy.data.images) if remap_images else {}
        material_groups = find_data_groups(bpy.data.materials) if remap_materials else {}
        font_groups = find_data_groups(bpy.data.fonts) if remap_fonts else {}
        world_groups = find_data_groups(bpy.data.worlds) if remap_worlds else {}
        
        total_duplicates = sum(len(group) - 1 for groups in [image_groups, material_groups, font_groups, world_groups] for group in groups.values())
        
        # Count data blocks with numbered suffixes (only for local datablocks)
        total_numbered = 0
        if remap_images:
            total_numbered += sum(1 for img in bpy.data.images 
                                if img.users > 0 
                                and not (hasattr(img, 'library') and img.library is not None)
                                and get_base_name(img.name) != img.name)
        if remap_materials:
            total_numbered += sum(1 for mat in bpy.data.materials 
                                if mat.users > 0 
                                and not (hasattr(mat, 'library') and mat.library is not None)
                                and get_base_name(mat.name) != mat.name)
        if remap_fonts:
            total_numbered += sum(1 for font in bpy.data.fonts 
                                if font.users > 0 
                                and not (hasattr(font, 'library') and font.library is not None)
                                and get_base_name(font.name) != font.name)
        if remap_worlds:
            total_numbered += sum(1 for world in bpy.data.worlds 
                                if world.users > 0 
                                and not (hasattr(world, 'library') and world.library is not None)
                                and get_base_name(world.name) != world.name)
        
        if total_duplicates == 0 and total_numbered == 0:
            self.report({'INFO'}, "No local data blocks to process")
            return {'CANCELLED'}
        
        # Perform the remapping and cleaning
        remapped_count, cleaned_count = remap_data_blocks(
            context,
            remap_images,
            remap_materials,
            remap_fonts,
            remap_worlds
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

# Add a new operator for merging duplicates using data-block utilities
class BST_OT_MergeDuplicatesWithDBU(bpy.types.Operator):
    """Merge duplicates using data-block utilities addon for all supported data types"""
    bl_idname = "bst.merge_duplicates_dbu"
    bl_label = "Merge Duplicates (DBU)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Check if data-block utilities addon is installed
        if not hasattr(context.scene, 'dbu_similar_settings'):
            self.report({'ERROR'}, "Data-block utilities addon is not installed or enabled")
            return {'CANCELLED'}
        
        # Data types to process in order
        data_types = ['NODETREE', 'MATERIAL', 'LIGHT', 'IMAGE', 'MESH']
        type_labels = {
            'NODETREE': 'Node Groups',
            'MATERIAL': 'Materials',
            'LIGHT': 'Lights',
            'IMAGE': 'Images',
            'MESH': 'Meshes'
        }
        
        total_merged = 0
        processed_types = []
        
        try:
            settings = context.scene.dbu_similar_settings
            
            for id_type in data_types:
                # Set the id_type
                settings.id_type = id_type
                
                # Find similar and duplicates
                try:
                    bpy.ops.scene.dbu_find_similar_and_duplicates()
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to find duplicates for {type_labels[id_type]}: {str(e)}")
                    continue
                
                # Check if any duplicates were found
                if not settings.duplicates:
                    continue
                
                # Count items to be merged (each group has duplicates, so count items - groups)
                # Each group keeps one item, so we count (total items - number of groups)
                total_items = sum(len(group.group) for group in settings.duplicates)
                num_groups = len(settings.duplicates)
                items_to_remove = total_items - num_groups  # One item per group is kept
                
                # Merge duplicates
                try:
                    bpy.ops.scene.dbu_merge_duplicates()
                    total_merged += items_to_remove
                    processed_types.append(f"{type_labels[id_type]} ({items_to_remove})")
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to merge duplicates for {type_labels[id_type]}: {str(e)}")
                    continue
            
            # Report results
            if total_merged > 0:
                types_str = ", ".join(processed_types)
                self.report({'INFO'}, f"Merged {total_merged} duplicate(s) across: {types_str}")
            else:
                self.report({'INFO'}, "No duplicates found to merge")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error during merge operation: {str(e)}")
            return {'CANCELLED'}

# Add a new operator for purging unused data
class DATAREMAP_OT_PurgeUnused(bpy.types.Operator):
    """Purge all unused data-blocks from the file (equivalent to File > Clean Up > Purge Unused Data)"""
    bl_idname = "bst.purge_unused_data"
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
    bl_idname = "bst.toggle_group_exclusion"
    bl_label = "Toggle Group"
    bl_options = {'REGISTER', 'UNDO'}
    
    group_key: bpy.props.StringProperty(  # type: ignore
        name="Group Key",
        description="Unique identifier for the group",
        default=""
    )
    
    data_type: bpy.props.StringProperty(  # type: ignore
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

class DATAREMAP_OT_SelectAllGroups(bpy.types.Operator):
    """Select or deselect all groups of a specific data type"""
    bl_idname = "bst.select_all_data_groups"
    bl_label = "Select All Groups"
    bl_options = {'REGISTER', 'UNDO'}
    
    data_type: bpy.props.StringProperty(  # type: ignore
        name="Data Type",
        description="Type of data (images, materials, fonts, worlds)",
        default=""
    )
    
    select_all: bpy.props.BoolProperty(  # type: ignore
        name="Select All",
        description="True to select all, False to deselect all",
        default=True
    )
    
    def execute(self, context):
        # Initialize the dictionary if it doesn't exist
        if not hasattr(context.scene, "excluded_remap_groups"):
            context.scene.excluded_remap_groups = {}
        
        # Get the appropriate data groups based on data_type
        data_groups = {}
        if self.data_type == "images":
            data_groups = find_data_groups(bpy.data.images)
        elif self.data_type == "materials":
            data_groups = find_data_groups(bpy.data.materials)
        elif self.data_type == "fonts":
            data_groups = find_data_groups(bpy.data.fonts)
        elif self.data_type == "worlds":
            data_groups = find_data_groups(bpy.data.worlds)
        
        # Process only groups with more than one item
        for base_name, items in data_groups.items():
            if len(items) > 1:
                key = f"{self.data_type}:{base_name}"
                
                if self.select_all:
                    # Remove from excluded list to select
                    if key in context.scene.excluded_remap_groups:
                        del context.scene.excluded_remap_groups[key]
                else:
                    # Add to excluded list to deselect
                    context.scene.excluded_remap_groups[key] = True
        
        return {'FINISHED'}

# Update the toggle group selection operator to handle shift-click range selection
class DATAREMAP_OT_ToggleGroupSelection(bpy.types.Operator):
    """Toggle whether this group should be included in remapping"""
    bl_idname = "bst.toggle_group_selection"
    bl_label = "Toggle Group Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    group_key: bpy.props.StringProperty(  # type: ignore
        name="Group Key",
        description="Unique identifier for the group",
        default=""
    )
    
    data_type: bpy.props.StringProperty(  # type: ignore
        name="Data Type",
        description="Type of data (images, materials, fonts, worlds)",
        default=""
    )
    
    def invoke(self, context, event):
        # Initialize the dictionary if it doesn't exist
        if not hasattr(context.scene, "excluded_remap_groups"):
            context.scene.excluded_remap_groups = {}
        
        # Create a unique key for this group
        key = f"{self.data_type}:{self.group_key}"
        
        # Get the current state
        is_excluded = key in context.scene.excluded_remap_groups
        
        # Initialize the last clicked group dictionary if it doesn't exist
        if not hasattr(context.scene, "last_clicked_group"):
            context.scene.last_clicked_group = {}
        
        # Check if shift is held down for range selection
        if event.shift and self.data_type in context.scene.last_clicked_group:
            # Get the last clicked group
            last_group = context.scene.last_clicked_group[self.data_type]
            
            # Get all data groups for this data type
            data_groups = []
            if self.data_type == "images":
                data_groups = list(find_data_groups(bpy.data.images).keys())
            elif self.data_type == "materials":
                data_groups = list(find_data_groups(bpy.data.materials).keys())
            elif self.data_type == "fonts":
                data_groups = list(find_data_groups(bpy.data.fonts).keys())
            elif self.data_type == "worlds":
                data_groups = list(find_data_groups(bpy.data.worlds).keys())
            
            # Find the indices of the last clicked group and the current group
            try:
                last_index = data_groups.index(last_group)
                current_index = data_groups.index(self.group_key)
                
                # Determine the range of groups to toggle
                start_index = min(last_index, current_index)
                end_index = max(last_index, current_index)
                
                # Toggle all groups in the range
                for i in range(start_index, end_index + 1):
                    group_name = data_groups[i]
                    group_key = f"{self.data_type}:{group_name}"
                    
                    # Apply the same toggle state as the first clicked item
                    if is_excluded:
                        # Select this group (remove from excluded list)
                        if group_key in context.scene.excluded_remap_groups:
                            del context.scene.excluded_remap_groups[group_key]
                    else:
                        # Deselect this group (add to excluded list)
                        context.scene.excluded_remap_groups[group_key] = True
            except ValueError:
                # If one of the groups is not found, just toggle the current group
                if is_excluded:
                    del context.scene.excluded_remap_groups[key]
                else:
                    context.scene.excluded_remap_groups[key] = True
        else:
            # Regular toggle for a single group
            if is_excluded:
                del context.scene.excluded_remap_groups[key]
            else:
                context.scene.excluded_remap_groups[key] = True
        
        # Store this group as the last clicked group for this data type
        context.scene.last_clicked_group[self.data_type] = self.group_key
        
        return {'FINISHED'}
    
    def execute(self, context):
        # This is only used when the operator is called programmatically
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

# Add a custom draw function for checkboxes that supports drag selection
def draw_drag_selectable_checkbox(layout, context, data_type, group_key):
    """Draw a checkbox that supports drag selection"""
    # Create a unique key for this group
    key = f"{data_type}:{group_key}"
    
    # Check if this group is excluded
    is_excluded = key in context.scene.excluded_remap_groups
    
    # Draw the checkbox
    op = layout.operator("bst.toggle_group_selection", 
                         text="", 
                         icon='CHECKBOX_HLT' if not is_excluded else 'CHECKBOX_DEHLT',
                         emboss=False)
    op.group_key = group_key
    op.data_type = data_type

def search_matches_group(group, search_string):
    """Check if search string matches group base name or any item in group"""
    if not search_string:
        return True
    search_lower = search_string.lower()
    base_name, items = group
    # Check base name
    if search_lower in base_name.lower():
        return True
    # Check all item names in group
    for item in items:
        if search_lower in item.name.lower():
            return True
    return False

# Update the UI code to use the custom draw function
def draw_data_duplicates(layout, context, data_type, data_groups):
    """Draw the list of duplicate data items with drag-selectable checkboxes and click to rename"""
    box_dup = layout.box()
    
    # Add Select All / Deselect All buttons
    select_row = box_dup.row(align=True)
    select_row.scale_y = 0.8
    
    select_op = select_row.operator("bst.select_all_data_groups", text="Select All")
    select_op.data_type = data_type
    select_op.select_all = True
    
    deselect_op = select_row.operator("bst.select_all_data_groups", text="Deselect All")
    deselect_op.data_type = data_type
    deselect_op.select_all = False
    
    # Add sort by selected toggle
    sort_prop_name = f"dataremap_sort_{data_type}"
    if hasattr(context.scene, sort_prop_name):
        select_row.prop(context.scene, sort_prop_name, text="Sort by Selected")
    
    # Add search filter
    search_row = box_dup.row()
    search_row.label(text="", icon='VIEWZOOM')
    search_prop_name = f"dataremap_search_{data_type}"
    if hasattr(context.scene, search_prop_name):
        search_row.prop(context.scene, search_prop_name, text="")
    
    box_dup.separator(factor=0.5)
    
    # Initialize the expanded groups dictionary if it doesn't exist
    if not hasattr(context.scene, "expanded_remap_groups"):
        context.scene.expanded_remap_groups = {}
    
    # Get the groups and possibly sort them
    group_items = list(data_groups.items())
    
    # Filter by search string if provided
    search_prop_name = f"dataremap_search_{data_type}"
    search_string = ""
    if hasattr(context.scene, search_prop_name):
        search_string = getattr(context.scene, search_prop_name)
    
    if search_string:
        group_items = [group for group in group_items if search_matches_group(group, search_string)]
    
    # Sort by selection if enabled
    sort_prop_name = f"dataremap_sort_{data_type}"
    if hasattr(context.scene, sort_prop_name) and getattr(context.scene, sort_prop_name):
        # Check if groups are excluded
        def is_group_selected(group_key):
            base_name, items = group_key
            group_id = f"{data_type}:{base_name}"
            # A group is "selected" if it's not excluded
            return group_id not in context.scene.excluded_remap_groups
        
        # Sort groups so that selected groups appear first
        group_items.sort(key=lambda x: not is_group_selected(x))
    
    for base_name, items in group_items:
        if len(items) > 1:
            row = box_dup.row()
            
            # Add checkbox to include/exclude this group using the custom draw function
            draw_drag_selectable_checkbox(row, context, data_type, base_name)
            
            # Add dropdown toggle
            group_key = f"{data_type}:{base_name}"
            is_expanded = group_key in context.scene.expanded_remap_groups
            
            exp_op = row.operator("bst.toggle_group_expansion",
                                 text="",
                                 icon='DISCLOSURE_TRI_DOWN' if is_expanded else 'DISCLOSURE_TRI_RIGHT',
                                 emboss=False)
            exp_op.group_key = base_name
            exp_op.data_type = data_type
            
            # Find the original data item (target)
            target_item = find_target_data(items)
            
            # Add icon based on data type
            if data_type == "images":
                if target_item and hasattr(target_item, 'preview'):
                    # Use the actual image thumbnail
                    row.template_icon(icon_value=target_item.preview_ensure().icon_id, scale=1.0)
                else:
                    row.label(text="", icon='IMAGE_DATA')
            elif data_type == "materials":
                if target_item and hasattr(target_item, 'preview'):
                    # Use UI_previews_ensure_material which is what Blender uses internally
                    # This accesses the cached thumbnail without triggering a render
                    icon_id = bpy.types.UILayout.icon(target_item)
                    row.label(text="", icon_value=icon_id)
                else:
                    row.label(text="", icon='MATERIAL')
            elif data_type == "fonts":
                row.label(text="", icon='FONT_DATA')
            elif data_type == "worlds":
                if target_item and hasattr(target_item, 'preview') and target_item.preview:
                    row.template_icon(icon_value=target_item.preview.icon_id, scale=1.0)
                else:
                    row.label(text="", icon='WORLD')
            
            # Add rename operator for the group name
            rename_op = row.operator("bst.rename_datablock_remap", text=f"{base_name}: {len(items)} versions", emboss=False)
            rename_op.data_type = data_type
            rename_op.old_name = target_item.name
            
            # Only show details if expanded
            if is_expanded:
                # Sort subgroup items if sort by selected is enabled
                if hasattr(context.scene, sort_prop_name) and getattr(context.scene, sort_prop_name):
                    items = sorted(items, key=lambda item: item != target_item)  # Keep target at top
                
                for item in items:
                    sub_row = box_dup.row()
                    sub_row.label(text="", icon='BLANK1')  # Indent
                    # Add icon based on data type
                    if data_type == "images":
                        if item and hasattr(item, 'preview'):
                            # Use the actual image thumbnail
                            sub_row.template_icon(icon_value=item.preview_ensure().icon_id, scale=1.0)
                        else:
                            sub_row.label(text="", icon='IMAGE_DATA')
                    elif data_type == "materials":
                        if item and hasattr(item, 'preview'):
                            # Use UI_previews_ensure_material which is what Blender uses internally
                            # This accesses the cached thumbnail without triggering a render
                            icon_id = bpy.types.UILayout.icon(item)
                            sub_row.label(text="", icon_value=icon_id)
                        else:
                            sub_row.label(text="", icon='MATERIAL')
                    elif data_type == "fonts":
                        sub_row.label(text="", icon='FONT_DATA')
                    elif data_type == "worlds":
                        if item and hasattr(item, 'preview') and item.preview:
                            sub_row.template_icon(icon_value=item.preview.icon_id, scale=1.0)
                        else:
                            sub_row.label(text="", icon='WORLD')
                    
                    # Add rename operator for each item
                    rename_op = sub_row.operator("bst.rename_datablock_remap", text=f"{item.name}", emboss=False)
                    rename_op.data_type = data_type
                    rename_op.old_name = item.name

class VIEW3D_PT_BulkDataRemap(bpy.types.Panel):
    """Bulk Data Remap Panel"""
    bl_label = "Bulk Data Remap"
    bl_idname = "VIEW3D_PT_bulk_data_remap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 2
    
    def draw(self, context):
        layout = self.layout
        
        # Data Remapper section
        box = layout.box()
        box.label(text="Data Remapper")
        
        # Check for linked datablocks and create a separate warning section if found
        linked_datablocks_found = False
        linked_types = []
        linked_paths = set()
        
        if context.scene.dataremap_images and has_linked_datablocks(bpy.data.images):
            linked_datablocks_found = True
            linked_types.append("images")
            linked_paths.update(get_linked_file_paths(bpy.data.images))
            
        if context.scene.dataremap_materials and has_linked_datablocks(bpy.data.materials):
            linked_datablocks_found = True
            linked_types.append("materials")
            linked_paths.update(get_linked_file_paths(bpy.data.materials))
            
        if context.scene.dataremap_fonts and has_linked_datablocks(bpy.data.fonts):
            linked_datablocks_found = True
            linked_types.append("fonts")
            linked_paths.update(get_linked_file_paths(bpy.data.fonts))
            
        if context.scene.dataremap_worlds and has_linked_datablocks(bpy.data.worlds):
            linked_datablocks_found = True
            linked_types.append("worlds")
            linked_paths.update(get_linked_file_paths(bpy.data.worlds))
        
        # Display warning about linked datablocks in a separate section if found
        if linked_datablocks_found:
            warning_box = layout.box()
            warning_box.alert = True
            warning_box.label(text="Warning: Linked datablocks detected", icon='ERROR')
            warning_box.label(text=f"Types: {', '.join(linked_types)}")
            warning_box.label(text="Cannot remap linked datablocks.")
            warning_box.label(text="Edit the source file directly.")
            
            # Add buttons to open linked files
            if linked_paths:
                warning_box.separator()
                warning_box.label(text="Linked files:")
                for path in linked_paths:
                    row = warning_box.row()
                    row.label(text=os.path.basename(path))
                    op = row.operator("bst.open_linked_file", text="Open", icon='FILE_BLEND')
                    op.filepath = path
        
        # Add description
        col = box.column()
        col.label(text="Find and remap redundant datablocks,")
        col.label(text="e.g. .001, .002 duplicates")
        col.label(text="SAVE OFTEN! Bulk Data Processing can cause instability.", icon='ERROR')
        # Add data type options with checkboxes
        col = box.column(align=True)
        
        # Count duplicates and numbered suffixes for each type
        image_groups = find_data_groups(bpy.data.images)
        material_groups = find_data_groups(bpy.data.materials)
        font_groups = find_data_groups(bpy.data.fonts)
        world_groups = find_data_groups(bpy.data.worlds)
        
        image_duplicates = sum(len(group) - 1 for group in image_groups.values())
        material_duplicates = sum(len(group) - 1 for group in material_groups.values())
        font_duplicates = sum(len(group) - 1 for group in font_groups.values())
        world_duplicates = sum(len(group) - 1 for group in world_groups.values())
        
        image_numbered = sum(1 for img in bpy.data.images if img.users > 0 and get_base_name(img.name) != img.name)
        material_numbered = sum(1 for mat in bpy.data.materials if mat.users > 0 and get_base_name(mat.name) != mat.name)
        font_numbered = sum(1 for font in bpy.data.fonts if font.users > 0 and get_base_name(font.name) != font.name)
        world_numbered = sum(1 for world in bpy.data.worlds if world.users > 0 and get_base_name(world.name) != world.name)
        
        # Initialize excluded_remap_groups if it doesn't exist
        if not hasattr(context.scene, "excluded_remap_groups"):
            context.scene.excluded_remap_groups = {}
        
        # Add checkboxes with counts and dropdown toggles
        # Images
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("bst.toggle_data_type", text="", icon='IMAGE_DATA', depress=context.scene.dataremap_images)
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
            draw_data_duplicates(col, context, "images", image_groups)
        
        # Materials
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("bst.toggle_data_type", text="", icon='MATERIAL', depress=context.scene.dataremap_materials)
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
            draw_data_duplicates(col, context, "materials", material_groups)
        
        # Fonts
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("bst.toggle_data_type", text="", icon='FONT_DATA', depress=context.scene.dataremap_fonts)
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
            draw_data_duplicates(col, context, "fonts", font_groups)
        
        # World
        row = col.row()
        split = row.split(factor=0.6)
        sub_row = split.row()
        
        # Use depress parameter to show button as pressed when active
        op = sub_row.operator("bst.toggle_data_type", text="", icon='WORLD', depress=context.scene.dataremap_worlds)
        op.data_type = "worlds"
        
        # Use different text color based on activation
        if context.scene.dataremap_worlds:
            sub_row.label(text="Worlds")
        else:
            # Create a row with a different color for inactive text
            sub_row.label(text="Worlds", icon='RADIOBUT_OFF')
        
        sub_row = split.row()
        if world_duplicates > 0:
            sub_row.prop(context.scene, "show_world_duplicates", 
                         text=f"{world_duplicates} duplicates", 
                         icon='DISCLOSURE_TRI_DOWN' if context.scene.show_world_duplicates else 'DISCLOSURE_TRI_RIGHT',
                         emboss=False)
        elif world_numbered > 0:
            sub_row.label(text=f"{world_numbered} numbered")
        else:
            sub_row.label(text="0 duplicates")
        
        # Show world duplicates if enabled
        if context.scene.show_world_duplicates and world_duplicates > 0 and context.scene.dataremap_worlds:
            draw_data_duplicates(col, context, "worlds", world_groups)
        
        # Add the operator button
        row = box.row()
        row.scale_y = 1.5
        row.operator("bst.bulk_data_remap")
        
        # Add Data-Block Utils Integration section
        box.separator()
        dbu_box = box.box()
        dbu_box.label(text="Data-Block Utils Integration")
        dbu_col = dbu_box.column()
        dbu_col.label(text="Merge duplicates using data-block utilities addon")
        dbu_col.label(text="Processes: Node Groups, Materials, Lights, Images, Meshes")
        
        # Check if data-block utilities addon is available
        if hasattr(context.scene, 'dbu_similar_settings'):
            dbu_row = dbu_box.row()
            dbu_row.scale_y = 1.5
            dbu_row.operator("bst.merge_duplicates_dbu", text="Merge Duplicates (DBU)", icon='FILE_PARENT')
        else:
            dbu_box.alert = True
            dbu_box.label(text="Data-block utilities addon not installed", icon='ERROR')
        
        # Show total counts
        total_duplicates = image_duplicates + material_duplicates + font_duplicates + world_duplicates
        total_numbered = image_numbered + material_numbered + font_numbered + world_numbered
        
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
        row.operator("bst.purge_unused_data", icon='TRASH')
        
        # Ghost Buster section
        layout.separator()
        ghost_box = layout.box()
        ghost_box.label(text="Ghost Buster - Experimental")
        
        col = ghost_box.column()
        col.label(text="Ghost data cleanup & library override fixes:")
        col.label(text="• Unused local WGT widget objects")
        col.label(text="• Empty unlinked collections")
        col.label(text="• Objects not in scenes with no legitimate use")
        col.label(text="• Fix broken library override hierarchies")
        
        # Two button layout
        row = ghost_box.row(align=True)
        row.scale_y = 1.5
        row.operator("bst.ghost_detector", text="Ghost Detector", icon='ZOOM_IN')
        row.operator("bst.ghost_buster", text="Ghost Buster", icon='GHOST_ENABLED')
        
        # Ghost Buster option
        ghost_box.prop(context.scene, "ghost_buster_delete_low_priority", text="Delete Low Priority Ghosts")
        
        # Resync Enforce button
        ghost_box.separator()
        row = ghost_box.row()
        row.scale_y = 1.2
        row.operator("bst.resync_enforce", text="Resync Enforce", icon='FILE_REFRESH')

# Add a new operator for toggling data types
class DATAREMAP_OT_ToggleDataType(bpy.types.Operator):
    """Toggle whether this data type should be included in remapping"""
    bl_idname = "bst.toggle_data_type"
    bl_label = "Toggle Data Type"
    bl_options = {'REGISTER', 'UNDO'}
    
    data_type: bpy.props.StringProperty(  # type: ignore
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
        elif self.data_type == "worlds":
            context.scene.dataremap_worlds = not context.scene.dataremap_worlds
        
        return {'FINISHED'}

# Add a new operator for toggling group expansion
class DATAREMAP_OT_ToggleGroupExpansion(bpy.types.Operator):
    """Toggle whether this group should be expanded to show details"""
    bl_idname = "bst.toggle_group_expansion"
    bl_label = "Toggle Group Expansion"
    bl_options = {'REGISTER', 'UNDO'}
    
    group_key: bpy.props.StringProperty(  # type: ignore
        name="Group Key",
        description="Unique identifier for the group",
        default=""
    )
    
    data_type: bpy.props.StringProperty(  # type: ignore
        name="Data Type",
        description="Type of data (images, materials, fonts)",
        default=""
    )
    
    def execute(self, context):
        # Initialize the dictionary if it doesn't exist
        if not hasattr(context.scene, "expanded_remap_groups"):
            context.scene.expanded_remap_groups = {}
        
        # Create a unique key for this group
        key = f"{self.data_type}:{self.group_key}"
        
        # Toggle the expansion state
        if key in context.scene.expanded_remap_groups:
            del context.scene.expanded_remap_groups[key]
        else:
            context.scene.expanded_remap_groups[key] = True
        
        return {'FINISHED'}

# Function to get unique linked file paths from datablocks
def get_linked_file_paths(data_collection):
    """Get unique file paths of linked libraries from datablocks"""
    linked_paths = set()
    
    for data in data_collection:
        if data.users > 0 and hasattr(data, 'library') and data.library is not None:
            if hasattr(data.library, 'filepath') and data.library.filepath:
                linked_paths.add(data.library.filepath)
    
    return linked_paths

class DATAREMAP_OT_OpenLinkedFile(bpy.types.Operator):
    """Open the linked file in a new Blender instance"""
    bl_idname = "bst.open_linked_file"
    bl_label = "Open Linked File"
    bl_options = {'REGISTER'}
    
    filepath: bpy.props.StringProperty(  # type: ignore
        name="File Path",
        description="Path to the linked file",
        default=""
    )
    
    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No file path specified")
            return {'CANCELLED'}
        
        # Try to open the linked file in a new Blender instance
        try:
            # Use Blender's built-in file browser to open the file
            bpy.ops.wm.path_open(filepath=self.filepath)
            self.report({'INFO'}, f"Opening linked file: {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to open linked file: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}

# Add a new operator for renaming datablocks
class DATAREMAP_OT_RenameDatablock(bpy.types.Operator):
    """Click to rename datablock"""
    bl_idname = "bst.rename_datablock_remap"
    bl_label = "Rename Datablock"
    bl_options = {'REGISTER', 'UNDO'}
    
    data_type: bpy.props.StringProperty(  # type: ignore
        name="Data Type",
        description="Type of data (images, materials, fonts, worlds)",
        default=""
    )
    
    old_name: bpy.props.StringProperty(  # type: ignore
        name="Old Name",
        description="Current name of the datablock",
        default=""
    )
    
    new_name: bpy.props.StringProperty(  # type: ignore
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
        # Get the appropriate data collection
        data_collection = None
        if self.data_type == "images":
            data_collection = bpy.data.images
        elif self.data_type == "materials":
            data_collection = bpy.data.materials
        elif self.data_type == "fonts":
            data_collection = bpy.data.fonts
        elif self.data_type == "worlds":
            data_collection = bpy.data.worlds
        
        if not data_collection:
            self.report({'ERROR'}, "Invalid data type")
            return {'CANCELLED'}
        
        # Find the datablock
        datablock = data_collection.get(self.old_name)
        if not datablock:
            self.report({'ERROR'}, f"Could not find {self.data_type} with name {self.old_name}")
            return {'CANCELLED'}
        
        # Check if the datablock is linked
        if hasattr(datablock, 'library') and datablock.library is not None:
            self.report({'ERROR'}, f"Cannot rename linked {self.data_type}")
            return {'CANCELLED'}
        
        # Rename the datablock
        try:
            datablock.name = self.new_name
            self.report({'INFO'}, f"Renamed {self.data_type} to {self.new_name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to rename {self.data_type}: {str(e)}")
            return {'CANCELLED'}



# List of all classes in this module
classes = (
    DATAREMAP_OT_RemapData,
    BST_OT_MergeDuplicatesWithDBU,
    DATAREMAP_OT_PurgeUnused,
    DATAREMAP_OT_ToggleDataType,
    DATAREMAP_OT_ToggleGroupExclusion,
    DATAREMAP_OT_SelectAllGroups,
    VIEW3D_PT_BulkDataRemap,
    DATAREMAP_OT_ToggleGroupExpansion,
    DATAREMAP_OT_ToggleGroupSelection,
    DATAREMAP_OT_OpenLinkedFile,
    DATAREMAP_OT_RenameDatablock,
)

# Registration
def register():
    register_dataremap_properties()
    
    for cls in classes:
        compat.safe_register_class(cls)

def unregister():
    for cls in reversed(classes):
        compat.safe_unregister_class(cls)
    # Unregister properties
    try:
        unregister_dataremap_properties()
    except Exception:
        pass 