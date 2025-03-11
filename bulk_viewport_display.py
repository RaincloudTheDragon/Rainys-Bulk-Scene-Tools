import bpy
import numpy as np
from time import time
import os
from enum import Enum

# Material processing status enum
class MaterialStatus(Enum):
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3
    DEFAULT_WHITE = 4

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
    bpy.types.Scene.viewport_colors_selected_only = bpy.props.BoolProperty(
        name="Selected Objects Only",
        description="Apply viewport colors only to materials in selected objects",
        default=False
    )
    
    bpy.types.Scene.viewport_colors_batch_size = bpy.props.IntProperty(
        name="Batch Size",
        description="Number of materials to process in each batch",
        default=50,
        min=1,
        max=50
    )
    
    bpy.types.Scene.viewport_colors_use_vectorized = bpy.props.BoolProperty(
        name="Use Vectorized Processing",
        description="Use vectorized operations for image processing (faster but uses more memory)",
        default=True
    )
    
    bpy.types.Scene.viewport_colors_progress = bpy.props.FloatProperty(
        name="Progress",
        description="Progress of the viewport color setting operation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )
    
    bpy.types.Scene.viewport_colors_default_white_only = bpy.props.BoolProperty(
        name="Default White Only",
        description="Show only materials that weren't able to be processed",
        default=False
    )

def unregister_viewport_properties():
    del bpy.types.Scene.viewport_colors_filter_default_white
    del bpy.types.Scene.viewport_colors_progress
    del bpy.types.Scene.viewport_colors_use_vectorized
    del bpy.types.Scene.viewport_colors_batch_size
    del bpy.types.Scene.viewport_colors_selected_only

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
            current_material = material.name
            
            # Process the material
            color, status = process_material(material, use_vectorized)
            
            # Apply the color to the material
            if color:
                material.diffuse_color = (*color, 1.0)
            
            # Store the result
            material_results[material.name] = (color, status)
            
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
            self.report_info()
            return None
        
        # Continue processing
        return 0.1  # Check again in 0.1 seconds
    
    def report_info(self):
        elapsed_time = time() - start_time
        bpy.context.window_manager.popup_menu(
            lambda self, context: self.layout.label(text=f"Processed {processed_count} materials in {elapsed_time:.2f} seconds"),
            title="Processing Complete",
            icon='INFO'
        )

def process_material(material, use_vectorized=True):
    """Process a material to determine its viewport color"""
    if not material or not material.use_nodes:
        return (1, 1, 1), MaterialStatus.DEFAULT_WHITE
    
    try:
        # Get the final color from the material
        color = get_final_color(material)
        
        if color is None:
            return (1, 1, 1), MaterialStatus.DEFAULT_WHITE
        
        return color, MaterialStatus.COMPLETED
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

def get_final_color(material):
    """Get the final color for a material"""
    if not material or not material.use_nodes:
        return None
    
    # Get the output node
    output_node = None
    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            output_node = node
            break
    
    if not output_node:
        return None
    
    # Find the surface input
    surface_input = output_node.inputs.get('Surface')
    if not surface_input or not surface_input.links:
        return None
    
    # Get the connected node
    connected_node = surface_input.links[0].from_node
    
    # Calculate the color of the connected node
    return calculate_node_color(connected_node)

def calculate_node_color(node, visited=None):
    """Calculate the color of a node"""
    if visited is None:
        visited = set()
    
    if node in visited:
        return None
    
    visited.add(node)
    
    # Handle different node types
    if node.type == 'BSDF_PRINCIPLED':
        # Check if there's a texture connected to the Base Color input
        base_color_input = node.inputs.get('Base Color')
        if base_color_input and base_color_input.links:
            connected_node = base_color_input.links[0].from_node
            color = calculate_node_color(connected_node, visited)
            if color:
                return color
        
        # If no texture, use the base color value
        if base_color_input:
            return list(base_color_input.default_value)[:3]
    
    elif node.type == 'TEX_IMAGE':
        # Use the image texture
        if node.image:
            color = get_average_color(node.image)
            if color:
                return color
    
    elif node.type == 'MIX_RGB':
        # Mix the colors based on the factor
        factor = node.inputs[0].default_value
        
        color1 = None
        if node.inputs[1].links:
            connected_node = node.inputs[1].links[0].from_node
            color1 = calculate_node_color(connected_node, visited)
        else:
            color1 = list(node.inputs[1].default_value)[:3]
        
        color2 = None
        if node.inputs[2].links:
            connected_node = node.inputs[2].links[0].from_node
            color2 = calculate_node_color(connected_node, visited)
        else:
            color2 = list(node.inputs[2].default_value)[:3]
        
        if color1 and color2:
            # Mix the colors
            blend_type = node.blend_type
            if blend_type == 'MIX':
                return [
                    color1[0] * (1 - factor) + color2[0] * factor,
                    color1[1] * (1 - factor) + color2[1] * factor,
                    color1[2] * (1 - factor) + color2[2] * factor
                ]
            # Add more blend types as needed
    
    elif node.type == 'RGB':
        # Use the RGB node color
        return list(node.outputs[0].default_value)[:3]
    
    # For other node types, try to find a connected image texture
    result = find_color_or_texture(node, visited)
    if result:
        return result
    
    return None

def find_color_or_texture(node, visited=None):
    """Find a color or texture in the node's inputs"""
    if visited is None:
        visited = set()
    
    if node in visited:
        return None
    
    visited.add(node)
    
    # Check all inputs for a color or texture
    for input_socket in node.inputs:
        if input_socket.links:
            for link in input_socket.links:
                from_node = link.from_node
                
                # Check if this is a color or texture node
                if from_node.type in {'TEX_IMAGE', 'RGB'}:
                    result = calculate_node_color(from_node, visited)
                    if result:
                        return result
                
                # Recursively check connected nodes
                result = find_color_or_texture(from_node, visited)
                if result:
                    return result
    
    return None

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
    
    # Find the connected image texture
    connected_node = base_color_input.links[0].from_node
    image_node = find_image_node(connected_node)
    
    return image_node.image if image_node else None

def get_status_icon(status):
    """Get the icon for a material status"""
    if status == MaterialStatus.PENDING:
        return 'TRIA_RIGHT'
    elif status == MaterialStatus.PROCESSING:
        return 'SORTTIME'
    elif status == MaterialStatus.COMPLETED:
        return 'CHECKMARK'
    elif status == MaterialStatus.FAILED:
        return 'ERROR'
    elif status == MaterialStatus.DEFAULT_WHITE:
        return 'RADIOBUT_OFF'
    else:
        return 'QUESTION'

def get_status_text(status):
    """Get the text for a material status"""
    if status == MaterialStatus.PENDING:
        return "Pending"
    elif status == MaterialStatus.PROCESSING:
        return "Processing"
    elif status == MaterialStatus.COMPLETED:
        return "Completed"
    elif status == MaterialStatus.FAILED:
        return "Failed"
    elif status == MaterialStatus.DEFAULT_WHITE:
        return "Default White"
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
    bl_order = 2  # Higher number means lower in the list
    
    def draw(self, context):
        layout = self.layout
        
        # Viewport Colors section
        box = layout.box()
        box.label(text="Viewport Colors")
        
        # Add settings before the button
        col = box.column(align=True)
        col.prop(context.scene, "viewport_colors_selected_only")
        col.prop(context.scene, "viewport_colors_batch_size")
        col.prop(context.scene, "viewport_colors_use_vectorized")
        
        # Add the operator button
        row = box.row()
        row.scale_y = 1.5
        row.operator("material.set_viewport_colors")
        
        # Show progress if processing
        if is_processing:
            row = box.row()
            row.label(text=f"Processing: {processed_count}/{total_materials}")
            
            # Add a progress bar
            row = box.row()
            row.prop(context.scene, "viewport_colors_progress", text="")
        
        # Show material results if available
        if material_results:
            box.label(text="Material Results:")
            
            # Add a filter option
            row = box.row()
            row.prop(context.scene, "viewport_colors_default_white_only", text="Default White Only")
            
            # Create a scrollable list
            row = box.row()
            col = row.column()
            
            # Display material results
            for material_name, (color, status) in material_results.items():
                # Skip default white materials if filtered
                if context.scene.viewport_colors_default_white_only and status != MaterialStatus.DEFAULT_WHITE:
                    continue
                
                row = col.row(align=True)
                
                # Add status icon
                row.label(text="", icon=get_status_icon(status))
                
                # Add material name with operator to select it
                op = row.operator("material.select_in_editor", text=material_name)
                op.material_name = material_name
                
                # Add color preview
                if color:
                    row.prop(bpy.data.materials.get(material_name), "diffuse_color", text="")

class VIEWPORT_PT_SetViewportColorsPanel(bpy.types.Panel):
    """Add button to Material Properties"""
    bl_label = "Set Viewport Colors"
    bl_idname = "VIEWPORT_PT_set_viewport_colors"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="This panel is deprecated.")
        layout.label(text="Please use the Bulk Scene Tools panel")
        layout.label(text="in the 3D View sidebar (Edit tab)")
        layout.operator("material.set_viewport_colors")

class MATERIAL_OT_SelectInEditor(bpy.types.Operator):
    """Select this material in the editor"""
    bl_idname = "material.select_in_editor"
    bl_label = "Select Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    material_name: bpy.props.StringProperty(
        name="Material Name",
        description="Name of the material to select",
        default=""
    )
    
    def execute(self, context):
        # Find the material
        material = bpy.data.materials.get(self.material_name)
        if not material:
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

# List of all classes in this module
classes = (
    VIEWPORT_OT_SetViewportColors,
    VIEW3D_PT_BulkViewportDisplay,
    VIEWPORT_PT_SetViewportColorsPanel,
    MATERIAL_OT_SelectInEditor,
)

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties
    register_viewport_properties()

def unregister():
    # Unregister properties
    unregister_viewport_properties()
    
    # Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 