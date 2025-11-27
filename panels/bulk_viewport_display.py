import bpy # type: ignore
import numpy as np
from time import time
import os
from enum import Enum
import colorsys  # Add colorsys for RGB to HSV conversion
from ..ops.select_diffuse_nodes import select_diffuse_nodes  # Import the specific function

# Material processing status enum
class MaterialStatus(Enum):
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3
    PREVIEW_BASED = 4

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
    
    # New properties for thumbnail-based color extraction
    bpy.types.Scene.viewport_colors_use_preview = bpy.props.BoolProperty(  # type: ignore
        name="Use Material Thumbnails",
        description="Use Blender's material thumbnails for color extraction (faster and more reliable)",
        default=True
    )

    bpy.types.Scene.show_material_results = bpy.props.BoolProperty(
        name="",
        description="Show material results in the viewport display panel",
        default=True
    )

def unregister_viewport_properties():
    del bpy.types.Scene.viewport_colors_use_preview
    del bpy.types.Scene.viewport_colors_batch_size
    del bpy.types.Scene.viewport_colors_use_vectorized
    del bpy.types.Scene.viewport_colors_darken_amount
    del bpy.types.Scene.viewport_colors_value_amount
    del bpy.types.Scene.viewport_colors_progress
    del bpy.types.Scene.viewport_colors_selected_only
    del bpy.types.Scene.viewport_colors_show_advanced
    del bpy.types.Scene.show_material_results

class VIEWPORT_OT_SetViewportColors(bpy.types.Operator):
    """Set Viewport Display colors from BSDF base color or texture"""
    bl_idname = "bst.set_viewport_colors"
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
                # Store the color change to apply later in main thread
                material_results[material.name] = (color, status)
                # Mark this material for color application
                if not hasattr(self, 'pending_color_changes'):
                    self.pending_color_changes = []
                self.pending_color_changes.append((material, color))
            else:
                # Store the result without color change
                material_results[material.name] = (None, status)
            
            # Update processed count
            processed_count += 1
            
            # Update progress
            if total_materials > 0:
                bpy.context.scene.viewport_colors_progress = (processed_count / total_materials) * 100
        
        # Update the current index
        current_index = batch_end
        
        # Force a redraw of the UI
        for area in bpy.context.screen.areas:
            area.tag_redraw()
        
        # Check if we're done
        if current_index >= len(material_queue):
            is_processing = False
            # Apply pending color changes in main thread
            if hasattr(self, 'pending_color_changes') and self.pending_color_changes:
                bpy.app.timers.register(self._apply_color_changes)
            self.report_info()
            return None
        
        # Continue processing
        return 0.1  # Check again in 0.1 seconds
    
    def _apply_color_changes(self):
        """Apply pending color changes in the main thread"""
        if not hasattr(self, 'pending_color_changes') or not self.pending_color_changes:
            return None
        
        # Apply a batch of color changes
        batch_size = 10  # Process 10 materials at a time
        batch = self.pending_color_changes[:batch_size]
        
        for material, color in batch:
            try:
                if material and material.name in bpy.data.materials:
                    material.diffuse_color = (*color, 1.0)
            except Exception as e:
                print(f"Could not set diffuse_color for {material.name if material else 'Unknown'}: {e}")
        
        # Remove processed items
        self.pending_color_changes = self.pending_color_changes[batch_size:]
        
        # Continue if there are more to process
        if self.pending_color_changes:
            return 0.01  # Process next batch in 0.01 seconds
        
        # All done
        print(f"Applied viewport colors to {len(batch)} materials")
        return None
    
    def report_info(self):
        global processed_count, start_time
        elapsed_time = time() - start_time
        
        # Count materials by status
        preview_count = 0
        node_count = 0
        failed_count = 0
        
        for _, status in material_results.values():
            if status == MaterialStatus.PREVIEW_BASED:
                preview_count += 1
            elif status == MaterialStatus.COMPLETED:
                node_count += 1
            elif status == MaterialStatus.FAILED:
                failed_count += 1
        
        # Use a popup menu instead of self.report since this might be called from a timer
        def draw_popup(self, context):
            self.layout.label(text=f"Processed {processed_count} materials in {elapsed_time:.2f} seconds")
            self.layout.label(text=f"Thumbnail-based: {preview_count}, Node-based: {node_count}")
            self.layout.label(text=f"Failed: {failed_count}")
        
        bpy.context.window_manager.popup_menu(draw_popup, title="Processing Complete", icon='INFO')


class VIEWPORT_OT_RefreshMaterialPreviews(bpy.types.Operator):
    """Regenerate material previews to avoid stale thumbnails"""
    bl_idname = "bst.refresh_material_previews"
    bl_label = "Refresh Material Previews"
    bl_options = {'REGISTER'}

    def execute(self, context):
        forced_count = 0
        try:
            bpy.ops.wm.previews_clear()
            bpy.ops.wm.previews_batch_generate()
            bpy.ops.wm.previews_ensure()
        except Exception as exc:
            self.report({'WARNING'}, f"Pre-clearing previews failed: {exc}")
        
        temp_obj = self._create_preview_object(context)
        
        try:
            for material in bpy.data.materials:
                if not material or material.is_grease_pencil:
                    continue
                
                try:
                    self._force_preview(material, temp_obj)
                    forced_count += 1
                except Exception as exc:
                    print(f"BST preview refresh: failed for {material.name}: {exc}")
        finally:
            self._cleanup_preview_object(temp_obj)

        message = f"Material previews refreshed ({forced_count} materials)"
        self.report({'INFO'}, message)
        return {'FINISHED'}

    def _create_preview_object(self, context):
        mesh = bpy.data.meshes.new("BST_PreviewMesh")
        mesh.from_pydata(
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)],
            [],
            [(0, 1, 2), (0, 2, 3), (0, 3, 1), (1, 3, 2)]
        )
        obj = bpy.data.objects.new("BST_PreviewObject", mesh)
        obj.hide_viewport = True
        obj.hide_render = True
        context.scene.collection.objects.link(obj)
        return obj

    def _cleanup_preview_object(self, obj):
        if not obj:
            return
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh:
            bpy.data.meshes.remove(mesh, do_unlink=True)

    def _force_preview(self, material, temp_obj):
        if temp_obj.data.materials:
            temp_obj.data.materials[0] = material
        else:
            temp_obj.data.materials.append(material)
        material.preview_render_type = 'SPHERE'
        preview = material.preview_ensure()
        if preview:
            # Touch icon id to ensure generation
            _ = preview.icon_id


def correct_viewport_color(color):
    """Adjust viewport colors by color intensity and saturation"""
    r, g, b = color
    
    # Get the color adjustment amount (-1 to +1) and scale it to ±10%
    color_adjustment = bpy.context.scene.viewport_colors_darken_amount * 0.1
    
    # Get the saturation adjustment amount (-1 to +1) and scale it to ±10%
    saturation_adjustment = bpy.context.scene.viewport_colors_value_amount * 0.1
    
    # First apply the color adjustment (RGB)
    r = r + color_adjustment
    g = g + color_adjustment
    b = b + color_adjustment
    
    # Clamp RGB values after color adjustment
    r = max(0.0, min(1.0, r))
    g = max(0.0, min(1.0, g))
    b = max(0.0, min(1.0, b))
    
    # Then apply the saturation adjustment using HSV
    if saturation_adjustment != 0:
        # Convert to HSV
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        
        # Adjust saturation while preserving hue and value
        s = s + saturation_adjustment
        s = max(0.0, min(1.0, s))
        
        # Convert back to RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
    
    return (r, g, b)

def process_material(material, use_vectorized=True):
    """Process a material to determine its viewport color"""
    if not material:
        print(f"Material is None, using fallback color")
        return (1, 1, 1), MaterialStatus.PREVIEW_BASED
    
    if material.is_grease_pencil:
        print(f"Material {material.name}: is a grease pencil material, using fallback color")
        return (1, 1, 1), MaterialStatus.PREVIEW_BASED
    
    try:
        # Get color from material thumbnail
        print(f"Material {material.name}: Attempting to extract color from thumbnail")
        
        # Get color from the material thumbnail
        color = get_color_from_preview(material, use_vectorized)
        
        if color:
            print(f"Material {material.name}: Thumbnail color = {color}")
            
            # Correct color for viewport display
            corrected_color = correct_viewport_color(color)
            print(f"Material {material.name}: Corrected thumbnail color = {corrected_color}")
            
            return corrected_color, MaterialStatus.PREVIEW_BASED
        else:
            print(f"Material {material.name}: Could not extract color from thumbnail, using fallback color")
            return (1, 1, 1), MaterialStatus.PREVIEW_BASED
        
    except Exception as e:
        print(f"Error processing material {material.name}: {e}")
        return (1, 1, 1), MaterialStatus.FAILED

def get_average_color(image, use_vectorized=True):
    """Calculate the average color of an image"""
    if not image or not image.has_data:
        return None
    
    # Get image pixels
    pixels = list(image.pixels)
    
    if use_vectorized and np is not None:
        # Use NumPy for faster processing
        pixels_np = np.array(pixels)
        
        # Reshape to RGBA format
        pixels_np = pixels_np.reshape(-1, 4)
        
        # Calculate average color (ignoring alpha)
        avg_color = pixels_np[:, :3].mean(axis=0)
        
        return avg_color.tolist()
    else:
        # Fallback to pure Python
        total_r, total_g, total_b = 0, 0, 0
        pixel_count = len(pixels) // 4
        
        for i in range(0, len(pixels), 4):
            total_r += pixels[i]
            total_g += pixels[i+1]
            total_b += pixels[i+2]
        
        if pixel_count > 0:
            return [total_r / pixel_count, total_g / pixel_count, total_b / pixel_count]
        else:
            return None

def find_image_node(node, visited=None):
    """Find the first image node connected to the given node"""
    if visited is None:
        visited = set()
    
    if node in visited:
        return None
    
    visited.add(node)
    
    # Check if this is an image node
    if node.type == 'TEX_IMAGE' and node.image:
        return node
    
    # Check input connections
    for input_socket in node.inputs:
        for link in input_socket.links:
            from_node = link.from_node
            result = find_image_node(from_node, visited)
            if result:
                return result
    
    return None

def find_color_source(node, socket_name=None, visited=None):
    """
    Recursively trace color data through nodes to find the source
    This is an enhanced version that handles mix nodes and node groups
    """
    if visited is None:
        visited = set()
    
    # Avoid infinite recursion
    node_id = (node, socket_name)
    if node_id in visited:
        return None, None
    
    visited.add(node_id)
    
    # Handle different node types
    if node.type == 'TEX_IMAGE' and node.image:
        # Direct image texture
        return node, 'Color'
    
    elif node.type == 'RGB':
        # Direct RGB color
        return node, 'Color'
    
    elif node.type == 'VALTORGB':  # Color Ramp
        return node, 'Color'
    
    elif node.type == 'MIX_RGB' or node.type == 'MIX':
        # For mix nodes, check the factor to determine which input to prioritize
        factor = 0.5  # Default to equal mix
        
        # Try to get the factor value
        if len(node.inputs) >= 1:
            if hasattr(node.inputs[0], 'default_value'):
                factor = node.inputs[0].default_value
        
        # If factor is close to 0, prioritize the first color input
        # If factor is close to 1, prioritize the second color input
        # Otherwise, check both with second having slightly higher priority
        
        if factor < 0.1:  # Strongly favor first input
            if len(node.inputs) >= 2 and node.inputs[1].links:
                color1_node = node.inputs[1].links[0].from_node
                result_node, result_socket = find_color_source(color1_node, None, visited)
                if result_node:
                    return result_node, result_socket
                    
            # Fallback to second input
            if len(node.inputs) >= 3 and node.inputs[2].links:
                color2_node = node.inputs[2].links[0].from_node
                result_node, result_socket = find_color_source(color2_node, None, visited)
                if result_node:
                    return result_node, result_socket
                    
        elif factor > 0.9:  # Strongly favor second input
            if len(node.inputs) >= 3 and node.inputs[2].links:
                color2_node = node.inputs[2].links[0].from_node
                result_node, result_socket = find_color_source(color2_node, None, visited)
                if result_node:
                    return result_node, result_socket
                    
            # Fallback to first input
            if len(node.inputs) >= 2 and node.inputs[1].links:
                color1_node = node.inputs[1].links[0].from_node
                result_node, result_socket = find_color_source(color1_node, None, visited)
                if result_node:
                    return result_node, result_socket
        else:
            # Check both inputs with slight preference for the second input (usually the main color)
            # First try Color2 (second input)
            if len(node.inputs) >= 3 and node.inputs[2].links:
                color2_node = node.inputs[2].links[0].from_node
                result_node, result_socket = find_color_source(color2_node, None, visited)
                if result_node:
                    return result_node, result_socket
            
            # Then try Color1 (first input)
            if len(node.inputs) >= 2 and node.inputs[1].links:
                color1_node = node.inputs[1].links[0].from_node
                result_node, result_socket = find_color_source(color1_node, None, visited)
                if result_node:
                    return result_node, result_socket
    
    elif node.type == 'GROUP':
        # Handle node groups by finding the group output node and tracing back
        if node.node_tree:
            # Find output node in the group
            for group_node in node.node_tree.nodes:
                if group_node.type == 'GROUP_OUTPUT':
                    # Find which input socket corresponds to the color output
                    for i, output in enumerate(node.outputs):
                        if output.links and (socket_name is None or output.name == socket_name):
                            # Find the corresponding input in the group output node
                            if i < len(group_node.inputs) and group_node.inputs[i].links:
                                input_link = group_node.inputs[i].links[0]
                                source_node = input_link.from_node
                                source_socket = input_link.from_socket.name
                                return find_color_source(source_node, source_socket, visited)
    
    elif node.type == 'BSDF_PRINCIPLED':
        # If we somehow got to a principled BSDF node, check its base color input
        base_color_input = node.inputs.get('Base Color')
        if base_color_input and base_color_input.links:
            connected_node = base_color_input.links[0].from_node
            return find_color_source(connected_node, None, visited)
    
    # For shader nodes, try to find color inputs
    elif 'BSDF' in node.type or 'SHADER' in node.type:
        # Look for color inputs in shader nodes
        color_input_names = ['Color', 'Base Color', 'Diffuse Color', 'Tint']
        for name in color_input_names:
            input_socket = node.inputs.get(name)
            if input_socket and input_socket.links:
                connected_node = input_socket.links[0].from_node
                result_node, result_socket = find_color_source(connected_node, None, visited)
                if result_node:
                    return result_node, result_socket
    
    # For other node types, check all inputs
    for input_socket in node.inputs:
        if input_socket.links:
            from_node = input_socket.links[0].from_node
            result_node, result_socket = find_color_source(from_node, None, visited)
            if result_node:
                return result_node, result_socket
    
    # If we get here, no color source was found
    return None, None

def get_final_color(material):
    """Get the final color for a material"""
    if not material or not material.use_nodes:
        print(f"Material {material.name if material else 'None'} has no nodes")
        return None
    
    # Find the Principled BSDF node
    principled_node = None
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_node = node
            break
    
    if not principled_node:
        print(f"Material {material.name}: No Principled BSDF node found")
        return None
    
    # Get the Base Color input
    base_color_input = principled_node.inputs.get('Base Color')
    if not base_color_input:
        print(f"Material {material.name}: No Base Color input found")
        return None
    
    # Check if there's a texture connected to the Base Color input
    if base_color_input.links:
        connected_node = base_color_input.links[0].from_node
        print(f"Material {material.name}: Base Color connected to {connected_node.name} of type {connected_node.type}")
        
        # Use the enhanced color source finding function
        source_node, source_socket = find_color_source(connected_node)
        
        if source_node:
            print(f"Material {material.name}: Found color source node {source_node.name} of type {source_node.type}")
            
            # Handle different source node types
            if source_node.type == 'TEX_IMAGE' and source_node.image:
                print(f"Material {material.name}: Using image texture {source_node.image.name}")
                color = get_average_color(source_node.image)
                if color:
                    print(f"Material {material.name}: Image average color = {color}")
                    return color
                else:
                    print(f"Material {material.name}: Could not calculate image average color")
            
            # If it's a color ramp, get the average color from the ramp
            elif source_node.type == 'VALTORGB':  # Color Ramp node
                print(f"Material {material.name}: Using color ramp")
                # Get the average of the color stops
                elements = source_node.color_ramp.elements
                if elements:
                    avg_color = [0, 0, 0]
                    for element in elements:
                        color = element.color[:3]  # Ignore alpha
                        avg_color[0] += color[0]
                        avg_color[1] += color[1]
                        avg_color[2] += color[2]
                    
                    avg_color[0] /= len(elements)
                    avg_color[1] /= len(elements)
                    avg_color[2] /= len(elements)
                    
                    print(f"Material {material.name}: Color ramp average = {avg_color}")
                    return avg_color
            
            # If it's an RGB node, use its color
            elif source_node.type == 'RGB':
                color = list(source_node.outputs[0].default_value)[:3]
                print(f"Material {material.name}: RGB node color = {color}")
                return color
            
            # For other node types, try to get color from the output socket
            elif source_socket and hasattr(source_node.outputs, '__getitem__'):
                for output in source_node.outputs:
                    if output.name == source_socket:
                        if hasattr(output, 'default_value') and len(output.default_value) >= 3:
                            color = list(output.default_value)[:3]
                            print(f"Material {material.name}: Node output socket color = {color}")
                            return color
            
            print(f"Material {material.name}: Could not extract color from source node {source_node.name} of type {source_node.type}")
        else:
            print(f"Material {material.name}: Could not find color source node in the node tree")
            
            # Debug: Print the node tree structure to help diagnose the issue
            print(f"Material {material.name}: Node tree structure:")
            for node in material.node_tree.nodes:
                print(f"  - Node: {node.name}, Type: {node.type}")
                for input_socket in node.inputs:
                    if input_socket.links:
                        print(f"    - Input: {input_socket.name} connected to {input_socket.links[0].from_node.name}")
    
    # If no texture or couldn't get texture color, use the base color value
    color = list(base_color_input.default_value)[:3]
    print(f"Material {material.name}: Using base color value = {color}")
    return color

def find_diffuse_texture(material):
    """Find the diffuse texture in a material"""
    if not material or not material.use_nodes:
        return None
    
    # Find the principled BSDF node
    principled_node = None
    for node in material.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_node = node
            break
    
    if not principled_node:
        return None
    
    # Find the base color input
    base_color_input = principled_node.inputs.get('Base Color')
    if not base_color_input or not base_color_input.links:
        return None
    
    # Get the connected node
    connected_node = base_color_input.links[0].from_node
    
    # Use the enhanced color source finding function
    source_node, _ = find_color_source(connected_node)
    
    # Check if we found an image texture
    if source_node and source_node.type == 'TEX_IMAGE' and source_node.image:
        return source_node.image
    
    return None

def get_status_icon(status):
    """Get the icon for a material status"""
    if status == MaterialStatus.PENDING:
        return 'TRIA_RIGHT'
    elif status == MaterialStatus.PROCESSING:
        return 'SORTTIME'
    elif status == MaterialStatus.COMPLETED:
        return 'CHECKMARK'
    elif status == MaterialStatus.PREVIEW_BASED:
        return 'IMAGE_DATA'
    elif status == MaterialStatus.FAILED:
        return 'ERROR'
    else:
        return 'QUESTION'

def get_status_text(status):
    """Get the text for a material status"""
    if status == MaterialStatus.PENDING:
        return "Pending"
    elif status == MaterialStatus.PROCESSING:
        return "Processing"
    elif status == MaterialStatus.COMPLETED:
        return "Node-based"
    elif status == MaterialStatus.PREVIEW_BASED:
        return "Thumbnail-based"
    elif status == MaterialStatus.FAILED:
        return "Failed"
    else:
        return "Unknown"

class VIEW3D_PT_BulkViewportDisplay(bpy.types.Panel):
    """Bulk Viewport Display Panel"""
    bl_label = "Bulk Viewport Display"
    bl_idname = "VIEW3D_PT_bulk_viewport_display"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 3
    
    def draw(self, context):
        layout = self.layout
        
        # Viewport Colors section
        box = layout.box()
        box.label(text="Viewport Colors")
        
        # Add description
        col = box.column()
        col.label(text="Set viewport colors from material thumbnails")
        
        # Add primary settings
        col = box.column(align=True)
        col.prop(context.scene, "viewport_colors_selected_only")
        col.operator("bst.refresh_material_previews", icon='FILE_REFRESH')
        
        # Add advanced options in a collapsible section
        row = box.row()
        row.prop(context.scene, "viewport_colors_show_advanced", 
                 icon='DISCLOSURE_TRI_DOWN' if context.scene.viewport_colors_show_advanced else 'DISCLOSURE_TRI_RIGHT',
                 emboss=False)
        row.label(text="Advanced Options")
        
        if context.scene.viewport_colors_show_advanced:
            adv_col = box.column(align=True)
            adv_col.prop(context.scene, "viewport_colors_batch_size")
            adv_col.prop(context.scene, "viewport_colors_use_vectorized")
            adv_col.prop(context.scene, "viewport_colors_darken_amount")
            adv_col.prop(context.scene, "viewport_colors_value_amount")
        
        # Add the operator button
        row = box.row()
        row.scale_y = 1.5
        row.operator("bst.set_viewport_colors")
        
        # Show progress if processing
        if is_processing:
            row = box.row()
            row.label(text=f"Processing: {processed_count}/{total_materials}")
            
            # Add a progress bar
            row = box.row()
            row.prop(context.scene, "viewport_colors_progress", text="")
        
        # Show material results if available
        if material_results:
            box.separator()
            row = box.row()
            row.prop(context.scene, "show_material_results", 
                     icon='DISCLOSURE_TRI_DOWN' if context.scene.show_material_results else 'DISCLOSURE_TRI_RIGHT',
                     emboss=False)
            row.label(text="Material Results:")
            if context.scene.show_material_results:
                # Create a scrollable list
                material_box = box.box()
                row = material_box.row()
                col = row.column()
                
                # Collect materials to remove
                materials_to_remove = []
                
                # Count materials by status
                preview_count = 0
                failed_count = 0
                
                # Display material results - use a copy of the keys to avoid modification during iteration
                for material_name in list(material_results.keys()):
                    color, status = material_results[material_name]
                    
                    # Update counts
                    if status == MaterialStatus.PREVIEW_BASED:
                        preview_count += 1
                    elif status == MaterialStatus.FAILED:
                        failed_count += 1
                    
                    row = col.row(align=True)
                    
                    # Add status icon
                    row.label(text="", icon=get_status_icon(status))
                    
                    # Add material name with operator to select it
                    op = row.operator("bst.select_in_editor", text=material_name)
                    op.material_name = material_name
                    
                    # Add color preview
                    if color:
                        material = bpy.data.materials.get(material_name)
                        if material:  # Check if material still exists
                            row.prop(material, "diffuse_color", text="")
                        else:
                            # Material no longer exists, show a placeholder color
                            row.label(text="", icon='ERROR')
                            # Mark for removal
                            materials_to_remove.append(material_name)
                
                # Remove materials that no longer exist
                for material_name in materials_to_remove:
                    material_results.pop(material_name, None)
                
                # Show statistics
                if len(material_results) > 0:
                    material_box.separator()
                    stats_col = material_box.column(align=True)
                    stats_col.label(text=f"Total: {len(material_results)} materials")
                    stats_col.label(text=f"Thumbnail-based: {preview_count}")
                    stats_col.label(text=f"Failed: {failed_count}")

        # Add the select diffuse nodes button at the bottom
        layout.separator()
        layout.operator("bst.select_diffuse_nodes", icon='NODE_TEXTURE')

class MATERIAL_OT_SelectInEditor(bpy.types.Operator):
    """Select this material in the editor"""
    bl_idname = "bst.select_in_editor"
    bl_label = "Select Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    material_name: bpy.props.StringProperty(  # type: ignore
        name="Material Name",
        description="Name of the material to select",
        default=""
    )
    
    def execute(self, context):
        # Find the material
        material = bpy.data.materials.get(self.material_name)
        if not material:
            # Remove this entry from material_results to avoid future errors
            if self.material_name in material_results:
                material_results.pop(self.material_name, None)
                # Force a redraw of the UI
                for area in context.screen.areas:
                    area.tag_redraw()
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}
        
        # Find an object using this material
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.data.materials:
                for i, mat in enumerate(obj.data.materials):
                    if mat == material:
                        # Select the object
                        bpy.ops.object.select_all(action='DESELECT')
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        
                        # Set the active material index
                        obj.active_material_index = i
                        
                        # Switch to material properties
                        for area in context.screen.areas:
                            if area.type == 'PROPERTIES':
                                for space in area.spaces:
                                    if space.type == 'PROPERTIES':
                                        space.context = 'MATERIAL'
                        
                        return {'FINISHED'}
        
        self.report({'WARNING'}, f"No object using material '{self.material_name}' found")
        return {'CANCELLED'}

def get_color_from_preview(material, use_vectorized=True):
    """Extract the average color from a material thumbnail"""
    if not material:
        return None
    
    # Force Blender to generate the material preview if it doesn't exist
    # This uses Blender's internal preview generation system
    preview = material.preview
    if not preview:
        return None
    
    # Ensure the preview is generated (this should be very fast as Blender maintains these)
    if preview.icon_id == 0:
        # Use Blender's standard preview size
        preview.icon_size = (128, 128)
        # This triggers Blender's internal preview generation
        icon_id = preview.icon_id  # Store in variable instead of just accessing
    
    # Access the preview image data - these are the same thumbnails shown in the material panel
    preview_image = preview.icon_pixels_float
    
    if not preview_image or len(preview_image) == 0:
        return None
    
    if use_vectorized and np is not None:
        # Use NumPy for faster processing
        pixels_np = np.array(preview_image)
        
        # Reshape to RGBA format (preview is stored as a flat RGBA array)
        pixels_np = pixels_np.reshape(-1, 4)
        
        # Calculate average color (ignoring alpha and any pure black pixels which are often the background)
        # Filter out black pixels (background) by checking if R+G+B is very small
        non_black_mask = np.sum(pixels_np[:, :3], axis=1) > 0.05
        
        if np.any(non_black_mask):
            # Only use non-black pixels for the average
            avg_color = pixels_np[non_black_mask][:, :3].mean(axis=0)
            return avg_color.tolist()
        else:
            # If all pixels are black, return the average of all pixels
            avg_color = pixels_np[:, :3].mean(axis=0)
            return avg_color.tolist()
    else:
        # Fallback to pure Python
        total_r, total_g, total_b = 0, 0, 0
        pixel_count = 0
        non_black_count = 0
        
        # Process pixels in groups of 4 (RGBA)
        for i in range(0, len(preview_image), 4):
            r, g, b, a = preview_image[i:i+4]
            
            # Skip black pixels (background)
            if r + g + b > 0.05:
                total_r += r
                total_g += g
                total_b += b
                non_black_count += 1
            
            pixel_count += 1
        
        # If we found non-black pixels, use their average
        if non_black_count > 0:
            return [total_r / non_black_count, total_g / non_black_count, total_b / non_black_count]
        # Otherwise, use the average of all pixels
        elif pixel_count > 0:
            return [total_r / pixel_count, total_g / pixel_count, total_b / pixel_count]
        else:
            return None

class VIEWPORT_OT_SelectDiffuseNodes(bpy.types.Operator):
    bl_idname = "bst.select_diffuse_nodes"
    bl_label = "Set Texture Display"
    bl_description = "Select the most relevant diffuse/base color image texture node in each material"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if select_diffuse_nodes:
            select_diffuse_nodes()
            self.report({'INFO'}, "Diffuse/BaseColor image nodes selected.")
        else:
            self.report({'ERROR'}, "select_diffuse_nodes function not found.")
        return {'FINISHED'}

# List of all classes in this module
classes = (
    VIEWPORT_OT_SetViewportColors,
    VIEWPORT_OT_RefreshMaterialPreviews,
    VIEW3D_PT_BulkViewportDisplay,
    MATERIAL_OT_SelectInEditor,
    VIEWPORT_OT_SelectDiffuseNodes,
)

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties
    register_viewport_properties()

def unregister():
    # Unregister properties
    try:
        unregister_viewport_properties()
    except Exception:
        pass
    # Unregister classes
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass 