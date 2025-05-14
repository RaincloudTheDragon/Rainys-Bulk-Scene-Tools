import bpy # type: ignore
import numpy as np
from time import time
import os
from enum import Enum
import colorsys  # Add colorsys for RGB to HSV conversion

# Material processing status enum
class MaterialStatus(Enum):
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3
    DEFAULT_WHITE = 4
    PREVIEW_BASED = 5

# Global variables to store results and track progress
material_results = {}  # {material_name: (color, status)}
current_material = ""
processed_count = 0
total_materials = 0
start_time = 0
is_processing = False
material_queue = []
current_index = 0

# Scene properties for viewport display settings
def register_viewport_properties():
    bpy.types.Scene.viewport_colors_selected_only = bpy.props.BoolProperty(  # type: ignore
        name="Selected Objects Only",
        description="Apply viewport colors only to materials in selected objects",
        default=False
    )
    
    bpy.types.Scene.viewport_colors_batch_size = bpy.props.IntProperty(  # type: ignore
        name="Batch Size",
        description="Number of materials to process in each batch",
        default=50,
        min=1,
        max=50
    )
    
    bpy.types.Scene.viewport_colors_use_vectorized = bpy.props.BoolProperty(  # type: ignore
        name="Use Vectorized Processing",
        description="Use vectorized operations for image processing (faster but uses more memory)",
        default=True
    )
    
    bpy.types.Scene.viewport_colors_darken_amount = bpy.props.FloatProperty(  # type: ignore
        name="Color Adjustment",
        description="Adjust viewport colors by ±10% (+1 = +10% lighter, 0 = no change, -1 = -10% darker)",
        default=0.0,
        min=-1.0,
        max=1.0,
        subtype='FACTOR'
    )
    
    bpy.types.Scene.viewport_colors_value_amount = bpy.props.FloatProperty(  # type: ignore
        name="Saturation Adjustment",
        description="Adjust color saturation by ±10% (+1 = +10% more saturated, 0 = no change, -1 = -10% less saturated)",
        default=1.0,
        min=-1.0,
        max=1.0,
        subtype='FACTOR'
    )
    
    bpy.types.Scene.viewport_colors_progress = bpy.props.FloatProperty(  # type: ignore
        name="Progress",
        description="Progress of the viewport color setting operation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )
    
    bpy.types.Scene.viewport_colors_show_advanced = bpy.props.BoolProperty(  # type: ignore
        name="Show Advanced Options",
        description="Show advanced options for viewport color extraction",
        default=False
    )
    
    bpy.types.Scene.viewport_colors_default_white_only = bpy.props.BoolProperty(  # type: ignore
        name="Default White Only",
        description="Show only materials that weren't able to be processed",
        default=False
    )
    
    # New properties for thumbnail-based color extraction
    bpy.types.Scene.viewport_colors_use_preview = bpy.props.BoolProperty(  # type: ignore
        name="Use Material Thumbnails",
        description="Use Blender's material thumbnails for color extraction (faster and more reliable)",
        default=True
    )

def unregister_viewport_properties():
    del bpy.types.Scene.viewport_colors_use_preview
    del bpy.types.Scene.viewport_colors_default_white_only
    del bpy.types.Scene.viewport_colors_progress
    del bpy.types.Scene.viewport_colors_value_amount
    del bpy.types.Scene.viewport_colors_darken_amount
    del bpy.types.Scene.viewport_colors_use_vectorized
    del bpy.types.Scene.viewport_colors_batch_size
    del bpy.types.Scene.viewport_colors_selected_only
    del bpy.types.Scene.viewport_colors_show_advanced

class VIEWPORT_OT_SetViewportColors(bpy.types.Operator):
    """Set Viewport Display colors from BSDF base color or texture"""
    bl_idname = "material.set_viewport_colors"
    bl_label = "Set Viewport Colors"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        global material_results, current_material, processed_count, total_materials, start_time, is_processing, material_queue, current_index
        
        # Reset global variables
        material_results = {}
        current_material = ""
        processed_count = 0
        is_processing = True
        start_time = time()
        current_index = 0
        
        # Get materials based on selection mode
        if context.scene.viewport_colors_selected_only:
            # Get materials from selected objects only
            materials = []
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.data.materials:
                    for mat in obj.data.materials:
                        if mat and not mat.is_grease_pencil and mat not in materials:
                            materials.append(mat)
        else:
            # Get all materials in the scene
            materials = [mat for mat in bpy.data.materials if not mat.is_grease_pencil]
        
        total_materials = len(materials)
        material_queue = materials.copy()
        
        if total_materials == 0:
            self.report({'WARNING'}, "No materials found to process")
            is_processing = False
            return {'CANCELLED'}
        
        # Reset progress
        context.scene.viewport_colors_progress = 0.0
        
        # Start a timer to process materials in batches
        bpy.app.timers.register(self._process_batch)
        
        return {'FINISHED'}
    
    def _process_batch(self):
        global material_results, current_material, processed_count, total_materials, is_processing, material_queue, current_index
        
        if not is_processing or len(material_queue) == 0:
            is_processing = False
            self.report_info()
            return None
        
        # Get the batch size from scene properties
        batch_size = bpy.context.scene.viewport_colors_batch_size
        use_vectorized = bpy.context.scene.viewport_colors_use_vectorized
        
        # Process a batch of materials
        batch_end = min(current_index + batch_size, len(material_queue))
        batch = material_queue[current_index:batch_end]
        
        for material in batch:
            # Skip if material is invalid or has been deleted
            if material is None or material.name not in bpy.data.materials:
                processed_count += 1
                continue
                
            current_material = material.name
            
            # Process the material
            color, status = process_material(material, use_vectorized)
            
            # Apply the color to the material
            if color:
                # Check if material is still valid
                try:
                    material.diffuse_color = (*color, 1.0)
                except ReferenceError:
                    # Material was deleted or remapped during processing
                    continue
            
            # Store the result
            material_results[material.name] = (color, status)
            
            # Update processed count
            processed_count += 1
            
            # Update progress
            if total_materials > 0:
                bpy.context.scene.viewport_colors_progress = (processed_count / total_materials) * 100
        
        # Update the current index
        current_index = batch_end
        
        # Continue if there are more materials to process
        if current_index < len(material_queue):
            return 0.01  # Schedule the next batch in 0.01 seconds
        else:
            is_processing = False
            self.report_info()
            return None
    
    def report_info(self):
        elapsed_time = time() - start_time
        mins = int(elapsed_time // 60)
        secs = int(elapsed_time % 60)
        
        default_white_count = sum(1 for _, status in material_results.values() if status == MaterialStatus.DEFAULT_WHITE)
        success_count = sum(1 for _, status in material_results.values() if status == MaterialStatus.COMPLETED or status == MaterialStatus.PREVIEW_BASED)
        
        message = f"Processed {processed_count} materials in {mins}m {secs}s. Successfully colored: {success_count}, Default white: {default_white_count}"
        self.report({'INFO'}, message)
        
        # Show a popup with the results
        bpy.context.window_manager.popup_menu(self.draw_popup, title="Viewport Color Results", icon='INFO')
        
    def draw_popup(self, menu, context):
        layout = menu.layout
        layout.label(text=f"Processed {processed_count} materials")
        
        default_white_count = sum(1 for _, status in material_results.values() if status == MaterialStatus.DEFAULT_WHITE)
        if default_white_count > 0:
            layout.label(text=f"{default_white_count} materials could not be processed and are set to default white")
            layout.label(text="Use the list below to view and select these materials")

def correct_viewport_color(color):
    """Apply color adjustment settings to the viewport color"""
    if not color:
        return None
        
    # Get the adjustment values
    darken_factor = bpy.context.scene.viewport_colors_darken_amount
    saturation_factor = bpy.context.scene.viewport_colors_value_amount
    
    if darken_factor == 0.0 and saturation_factor == 0.0:
        return color
    
    # Convert RGB to HSV
    h, s, v = colorsys.rgb_to_hsv(*color)
    
    # Apply saturation adjustment (±10% per unit)
    if saturation_factor > 0:
        s = min(1.0, s * (1.0 + (saturation_factor * 0.5)))
    elif saturation_factor < 0:
        s = max(0.0, s * (1.0 + (saturation_factor * 0.5)))
    
    # Apply value adjustment (±10% per unit)
    if darken_factor > 0:
        v = min(1.0, v * (1.0 + (darken_factor * 0.1)))
    elif darken_factor < 0:
        v = max(0.0, v * (1.0 + (darken_factor * 0.1)))
    
    # Convert back to RGB
    return colorsys.hsv_to_rgb(h, s, v)

def process_material(material, use_vectorized=True):
    """Process a material to get its viewport color"""
    # Use material preview image if enabled
    if bpy.context.scene.viewport_colors_use_preview:
        color = get_color_from_preview(material, use_vectorized)
        if color:
            return correct_viewport_color(color), MaterialStatus.PREVIEW_BASED
    
    # Fallback to node-based detection
    try:
        # Try to get the color from BSDF nodes
        color = get_final_color(material)
        if color:
            return correct_viewport_color(color), MaterialStatus.COMPLETED
    except Exception as e:
        print(f"Error processing material {material.name}: {e}")
        return (1, 1, 1), MaterialStatus.FAILED
    
    # Default to white if no color found
    return (1, 1, 1), MaterialStatus.DEFAULT_WHITE

def get_average_color(image, use_vectorized=True):
    """Get the average color of an image, with optional vectorized processing"""
    if not image or not image.pixels:
        return None
    
    width, height = image.size
    pixel_count = width * height
    
    if pixel_count == 0:
        return None
    
    if use_vectorized:
        try:
            # Vectorized approach for speed
            pixels = np.array(image.pixels).reshape(pixel_count, 4)
            mask = pixels[:, 3] > 0.1  # Only consider pixels with alpha > 0.1
            if not np.any(mask):
                return None
            
            # Get RGB values of non-transparent pixels and average them
            rgb = pixels[mask, :3]
            avg_color = np.mean(rgb, axis=0)
            return tuple(avg_color)
        except:
            # Fallback to non-vectorized approach if numpy fails
            pass
    
    # Non-vectorized approach
    r_total, g_total, b_total = 0, 0, 0
    valid_pixels = 0
    
    for i in range(0, len(image.pixels), 4):
        alpha = image.pixels[i+3]
        if alpha > 0.1:
            r_total += image.pixels[i]
            g_total += image.pixels[i+1]
            b_total += image.pixels[i+2]
            valid_pixels += 1
    
    if valid_pixels == 0:
        return None
        
    return (r_total / valid_pixels, g_total / valid_pixels, b_total / valid_pixels)

def find_image_node(node, visited=None):
    """Find the first image texture node in a node tree starting from the given node"""
    if visited is None:
        visited = set()
    
    if node is None or node in visited:
        return None
    
    visited.add(node)
    
    # Check if this is an image node
    if node.type == 'TEX_IMAGE' and node.image is not None:
        return node
    
    # Check input nodes recursively
    for input_socket in node.inputs:
        for link in input_socket.links:
            result = find_image_node(link.from_node, visited)
            if result:
                return result
    
    return None

def find_color_source(node, socket_name=None, visited=None):
    """Find the color source (either a value or image texture) for a given node"""
    if visited is None:
        visited = set()
    
    if node is None or node in visited:
        return None, None
    
    visited.add(node)
    
    # Check if the input is connected
    if socket_name and socket_name in node.inputs:
        socket = node.inputs[socket_name]
        
        # If socket is not connected, check for a default value
        if not socket.links:
            # Return default value if the socket has it
            if hasattr(socket, "default_value"):
                if len(socket.default_value) >= 3:  # Color socket
                    return socket.default_value[:3], None
                else:  # Value socket
                    val = socket.default_value
                    return (val, val, val), None
            return None, None
        
        # Follow the connection
        from_node = socket.links[0].from_node
        
        # Check node type to determine how to process
        if from_node.type == 'TEX_IMAGE' and from_node.image:
            return None, from_node
        elif from_node.type == 'MIX_RGB':
            # Get the factor 
            factor = 0.5  # Default factor
            if not from_node.inputs['Fac'].links and hasattr(from_node.inputs['Fac'], "default_value"):
                factor = from_node.inputs['Fac'].default_value
            
            # Get colors from both inputs
            color1, image1 = find_color_source(from_node, 'Color1', visited)
            color2, image2 = find_color_source(from_node, 'Color2', visited)
            
            # Choose based on factor and mix mode
            if from_node.blend_type == 'MIX':
                if factor < 0.5 and (color1 or image1):
                    return color1, image1
                else:
                    return color2, image2
            else:
                # For other blend modes, prefer an image source if available
                if image1:
                    return None, image1
                elif image2:
                    return None, image2
                elif color1 and color2:
                    # Approximate mix for simple blend modes
                    if from_node.blend_type == 'ADD':
                        r = min(1.0, color1[0] + color2[0] * factor)
                        g = min(1.0, color1[1] + color2[1] * factor)
                        b = min(1.0, color1[2] + color2[2] * factor)
                        return (r, g, b), None
                    else:
                        # Default to color with higher magnitude
                        mag1 = sum(color1)
                        mag2 = sum(color2)
                        return color1 if mag1 > mag2 else color2, None
                else:
                    return color1 or color2, None
        elif from_node.type == 'MAPPING':
            # Pass through mapping node
            return find_color_source(from_node, 'Vector', visited)
        elif from_node.type == 'TEX_COORD':
            # Texture coordinate node doesn't provide color info
            return None, None
        elif from_node.type == 'RGB':
            # Get color from RGB node
            if hasattr(from_node.outputs[0], "default_value"):
                return from_node.outputs[0].default_value[:3], None
        elif from_node.type == 'NORMAL_MAP':
            # Pass through normal map node
            return find_color_source(from_node, 'Color', visited)
        elif from_node.type == 'SEPARATE_RGB' or from_node.type == 'COMBINE_RGB':
            # These nodes manipulate individual channels, too complex for this function
            return None, None
        else:
            # For other node types, try to find an output that might connect to our input
            for output in from_node.outputs:
                for link in output.links:
                    if link.to_node == node and link.to_socket == socket:
                        # Found the right output, check if it has a default value
                        if hasattr(output, "default_value"):
                            if len(output.default_value) >= 3:  # Color socket
                                return output.default_value[:3], None
                            else:  # Value socket
                                val = output.default_value
                                return (val, val, val), None
            
            # If we didn't find a direct connection, check inputs to the from_node
            for input_name in ['Color', 'Base Color', 'Diffuse Color', 'Emission Color', 'Color1', 'Color2']:
                if input_name in from_node.inputs:
                    result_color, result_image = find_color_source(from_node, input_name, visited)
                    if result_color or result_image:
                        return result_color, result_image
                        
    # If no socket name specified, check common color inputs
    else:
        for input_name in ['Color', 'Base Color', 'Diffuse Color', 'Emission Color']:
            if input_name in node.inputs:
                result_color, result_image = find_color_source(node, input_name, visited)
                if result_color or result_image:
                    return result_color, result_image
    
    # No color source found
    return None, None

def get_final_color(material):
    """Get the viewport color for a material by analyzing its node tree"""
    # Check if material has nodes
    if not material or not material.use_nodes or not material.node_tree:
        # For non-node materials, return the diffuse color
        if hasattr(material, "diffuse_color"):
            return material.diffuse_color[:3]
        return None
    
    # Get the output node
    output_node = None
    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            output_node = node
            break
    
    if not output_node:
        for node in material.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                break
    
    if not output_node:
        return None
    
    # Get the Surface input
    if 'Surface' not in output_node.inputs or not output_node.inputs['Surface'].links:
        return None
    
    # Get the shader node connected to Surface
    shader_node = output_node.inputs['Surface'].links[0].from_node
    
    # Check shader node type
    if shader_node.type == 'BSDF_PRINCIPLED':
        # Try to get base color from Principled BSDF
        base_color, image_node = find_color_source(shader_node, 'Base Color')
        
        if base_color:
            return base_color
            
        if image_node:
            # Extract average color from image
            if image_node.image:
                avg_color = get_average_color(image_node.image)
                if avg_color:
                    return avg_color
    
    elif shader_node.type in ['BSDF_DIFFUSE', 'BSDF_GLOSSY', 'EMISSION']:
        # Get color from other shader types
        color_input = 'Color'
        if shader_node.type == 'EMISSION':
            color_input = 'Color'
        
        base_color, image_node = find_color_source(shader_node, color_input)
        
        if base_color:
            return base_color
            
        if image_node:
            # Extract average color from image
            if image_node.image:
                avg_color = get_average_color(image_node.image)
                if avg_color:
                    return avg_color
    
    elif shader_node.type == 'MIX_SHADER':
        # Try both shader inputs
        shader1 = shader_node.inputs[1].links[0].from_node if shader_node.inputs[1].links else None
        shader2 = shader_node.inputs[2].links[0].from_node if shader_node.inputs[2].links else None
        
        factor = 0.5  # Default mix factor
        if not shader_node.inputs[0].links:
            factor = shader_node.inputs[0].default_value
        
        # Try the dominant shader based on factor
        dominant_shader = shader2 if factor > 0.5 else shader1
        secondary_shader = shader1 if factor > 0.5 else shader2
        
        if dominant_shader:
            result = get_final_color({"use_nodes": True, "node_tree": {"nodes": [dominant_shader]}})
            if result:
                return result
                
        if secondary_shader:
            result = get_final_color({"use_nodes": True, "node_tree": {"nodes": [secondary_shader]}})
            if result:
                return result
    
    # Fallback: search for any image texture node in the material
    image_texture = find_diffuse_texture(material)
    if image_texture and image_texture.image:
        avg_color = get_average_color(image_texture.image)
        if avg_color:
            return avg_color
    
    return None

def find_diffuse_texture(material):
    """Find a diffuse texture in a material by searching all nodes"""
    if not material or not material.use_nodes or not material.node_tree:
        return None
    
    # First look for Principled BSDF nodes
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            # Check if Base Color is connected to an image
            if node.inputs['Base Color'].links:
                from_node = node.inputs['Base Color'].links[0].from_node
                if from_node.type == 'TEX_IMAGE' and from_node.image:
                    return from_node
                
                # Search deeper for an image node connected to this input
                image_node = find_image_node(from_node)
                if image_node:
                    return image_node
    
    # Look for other shader nodes
    for node in material.node_tree.nodes:
        if node.type in ['BSDF_DIFFUSE', 'BSDF_GLOSSY', 'EMISSION']:
            if node.inputs['Color'].links:
                from_node = node.inputs['Color'].links[0].from_node
                if from_node.type == 'TEX_IMAGE' and from_node.image:
                    return from_node
                
                # Search deeper for an image node connected to this input
                image_node = find_image_node(from_node)
                if image_node:
                    return image_node
    
    # Last resort: look for any image texture node
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image:
            return node
    
    return None

def get_status_icon(status):
    """Get an icon for a material status"""
    if status == MaterialStatus.COMPLETED:
        return 'CHECKMARK'
    elif status == MaterialStatus.FAILED:
        return 'ERROR'
    elif status == MaterialStatus.DEFAULT_WHITE:
        return 'QUESTION'
    elif status == MaterialStatus.PREVIEW_BASED:
        return 'IMAGE_PLANE'
    else:
        return 'NONE'

def get_status_text(status):
    """Get text representation of material status"""
    if status == MaterialStatus.COMPLETED:
        return "Processed from nodes"
    elif status == MaterialStatus.FAILED:
        return "Failed to process"
    elif status == MaterialStatus.DEFAULT_WHITE:
        return "Default white (no color found)"
    elif status == MaterialStatus.PREVIEW_BASED:
        return "From preview image"
    else:
        return "Unknown status"

class VIEW3D_PT_BulkViewportDisplay(bpy.types.Panel):
    """Bulk Viewport Display Panel"""
    bl_label = "Bulk Viewport Display"
    bl_idname = "VIEW3D_PT_bulk_viewport_display"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 2  # Higher number means lower in the list
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Main operator
        box = layout.box()
        col = box.column(align=True)
        col.operator("material.set_viewport_colors", icon='MATERIAL')
        
        # Selection settings
        col.prop(scene, "viewport_colors_selected_only")
        
        # Advanced settings toggle
        box.prop(scene, "viewport_colors_show_advanced", toggle=True)
        
        if scene.viewport_colors_show_advanced:
            # Advanced settings
            adv_box = box.box()
            col = adv_box.column(align=True)
            col.label(text="Processing Settings:")
            col.prop(scene, "viewport_colors_use_preview")
            col.prop(scene, "viewport_colors_batch_size")
            col.prop(scene, "viewport_colors_use_vectorized")
            
            adv_box.separator()
            
            # Color adjustments
            col = adv_box.column(align=True)
            col.label(text="Color Adjustments:")
            col.prop(scene, "viewport_colors_darken_amount")
            col.prop(scene, "viewport_colors_value_amount")
        
        # Show progress bar if processing
        if is_processing:
            box = layout.box()
            box.label(text=f"Processing: {current_material}")
            box.prop(scene, "viewport_colors_progress")
        
        # Results section
        if material_results:
            box = layout.box()
            box.label(text="Material Colors:", icon='MATERIAL')
            
            # Toggle to show only white/default materials
            box.prop(scene, "viewport_colors_default_white_only")
            
            # Add scrollable region for materials
            rows = min(len(material_results), 10)  # Show up to 10 rows, scrollable after that
            
            box = box.box()
            col = box.column_flow(columns=1)
            
            # Add material entries
            count = 0
            for mat_name, (color, status) in material_results.items():
                # Skip if not showing all and this isn't a default white
                if scene.viewport_colors_default_white_only and status != MaterialStatus.DEFAULT_WHITE:
                    continue
                
                # Create row for this material
                row = col.row(align=True)
                
                # Material color preview
                if color:
                    row.prop(bpy.data.materials.get(mat_name) if mat_name in bpy.data.materials else None, 
                             "diffuse_color", text="")
                else:
                    row.label(text="", icon='MATERIAL')
                
                # Material name as button to select it
                op = row.operator("material.select_in_editor", text=mat_name)
                op.material_name = mat_name
                
                # Status icon
                row.label(text="", icon=get_status_icon(status))
                
                count += 1
                
            if count == 0:
                col.label(text="No matching materials")

class MATERIAL_OT_SelectInEditor(bpy.types.Operator):
    """Select this material in the editor"""
    bl_idname = "material.select_in_editor"
    bl_label = "Select Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    material_name: bpy.props.StringProperty(  # type: ignore
        name="Material Name",
        description="Name of the material to select"
    )
    
    def execute(self, context):
        # Find the material
        material = bpy.data.materials.get(self.material_name)
        if not material:
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}
        
        # Try to find an object using this material
        found_obj = None
        found_slot = -1
        
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
                
            for i, slot in enumerate(obj.material_slots):
                if slot.material == material:
                    found_obj = obj
                    found_slot = i
                    break
                    
            if found_obj:
                break
        
        if found_obj:
            # Select the object and make it active
            bpy.ops.object.select_all(action='DESELECT')
            found_obj.select_set(True)
            context.view_layer.objects.active = found_obj
            
            # Set the active material slot
            if found_slot >= 0:
                found_obj.active_material_index = found_slot
                
            # Try to set up a reasonable material editor view
            # Find or create a shader editor area
            for area in context.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR':
                            space.tree_type = 'ShaderNodeTree'
                            space.shader_type = 'OBJECT'
                            space.node_tree = material.node_tree
                            break
                    break
            
            self.report({'INFO'}, f"Selected material '{self.material_name}'")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"No objects using material '{self.material_name}' found")
            return {'CANCELLED'}

def get_color_from_preview(material, use_vectorized=True):
    """Extract the dominant color from a material's preview image"""
    if not material:
        return None
        
    # Get preview image
    try:
        preview = material.preview
        if not preview:
            return None
            
        image = preview.icon_id
        if not image:
            return None
            
        # Get pixels from preview
        preview_image = preview.image_pixels_float
        if not preview_image or len(preview_image) == 0:
            return None
            
        # Convert to numpy array for processing if vectorized
        if use_vectorized:
            try:
                # The image is 256x256 in RGBA format
                pixels = np.array(preview_image).reshape(256*256, 4)
                
                # Filter out transparent pixels and background (which is usually dark)
                mask = (pixels[:, 3] > 0.5) & (pixels[:, 0] + pixels[:, 1] + pixels[:, 2] > 0.2)
                if not np.any(mask):
                    return None
                
                # Get RGB values of valid pixels
                rgb = pixels[mask, :3]
                
                # Sort by brightness and take the top 20% of pixels
                brightness = np.sum(rgb, axis=1)
                sorted_indices = np.argsort(brightness)
                top_indices = sorted_indices[-int(len(sorted_indices)*0.2):]
                
                # Take the average of these bright pixels
                avg_color = np.mean(rgb[top_indices], axis=0)
                return tuple(avg_color)
            except:
                # Fallback if numpy approach fails
                pass
        
        # Non-vectorized approach
        valid_pixels = []
        for i in range(0, len(preview_image), 4):
            r, g, b, a = preview_image[i:i+4]
            if a > 0.5 and r + g + b > 0.2:  # Non-transparent and not too dark
                valid_pixels.append((r, g, b))
        
        if not valid_pixels:
            return None
            
        # Sort by brightness and take the top 20%
        valid_pixels.sort(key=lambda p: sum(p))
        top_pixels = valid_pixels[-int(len(valid_pixels)*0.2):]
        
        # Calculate average
        avg_r = sum(p[0] for p in top_pixels) / len(top_pixels)
        avg_g = sum(p[1] for p in top_pixels) / len(top_pixels)
        avg_b = sum(p[2] for p in top_pixels) / len(top_pixels)
        
        return (avg_r, avg_g, avg_b)
    except:
        # If anything goes wrong, just return None
        return None

# The list of all classes in this module
classes = (
    VIEWPORT_OT_SetViewportColors,
    VIEW3D_PT_BulkViewportDisplay,
    MATERIAL_OT_SelectInEditor
)

def register():
    register_viewport_properties()
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    # Unregister properties
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    unregister_viewport_properties() 