bl_info = {
    "name": "Set Viewport Colors from BSDF",
    "author": "RaincloudTheDragon",
    "version": (0, 0, 3),
    "blender": (4, 3, 2),
    "location": "Properties > Material > Viewport Display",
    "description": "Sets the Viewport Display color based on BSDF base color or the average color of the connected texture",
    "category": "Material",
    "maintainer": "RaincloudTheDragon",
    "support": "COMMUNITY",
    "doc_url": "",
    "tracker_url": "",
}

import bpy
import numpy as np

class VIEWPORT_OT_SetViewportColors(bpy.types.Operator):
    """Set Viewport Display colors from BSDF base color or texture"""
    bl_idname = "material.set_viewport_colors"
    bl_label = "Set Viewport Colors"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        set_viewport_colors()
        return {'FINISHED'}

def get_average_color(image):
    """Calculate the average color of an image."""
    if image is None or image.size[0] == 0 or image.size[1] == 0:
        return (1.0, 1.0, 1.0, 1.0)  # Default white if no image
    
    pixels = np.array(image.pixels[:])  # Get all pixel data
    pixels = pixels.reshape(-1, 4)  # Reshape to (N, RGBA)
    
    avg_color = pixels[:, :3].mean(axis=0)  # Average RGB, ignore alpha
    return (avg_color[0], avg_color[1], avg_color[2], 1.0)

def find_image_node(node, visited=None):
    """Recursively search for an image texture node linked to the given node."""
    if visited is None:
        visited = set()
    
    if node in visited:  # Prevent infinite loops
        return None
    
    visited.add(node)
    
    # If this is an image texture node with an image, return it
    if node.type == 'TEX_IMAGE' and node.image:
        return node.image
    
    # Otherwise, recursively search through connected nodes
    for input_socket in node.inputs:
        for link in input_socket.links:
            result = find_image_node(link.from_node, visited)
            if result:
                return result  # Stop as soon as an image is found

    return None

def get_final_color(material):
    """Get the final color from the material's output node."""
    if not material.use_nodes or not material.node_tree:
        return None, (1.0, 1.0, 1.0)  # Default white if no nodes
    
    # Find the output node
    output_node = None
    for node in material.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and node.is_active_output:
            output_node = node
            break
    
    if not output_node or not output_node.inputs['Surface'].links:
        return None, (1.0, 1.0, 1.0)  # Default white if no output
    
    # Get the shader connected to the output
    shader_node = output_node.inputs['Surface'].links[0].from_node
    
    # First try to calculate the final color directly
    final_color = calculate_node_color(shader_node)
    if final_color:
        return None, final_color
    
    # If direct calculation fails, check for textures or color inputs
    image, color = find_color_or_texture(shader_node)
    return image, color if color else (1.0, 1.0, 1.0)

def calculate_node_color(node, visited=None):
    """Try to calculate the final color output of a node."""
    if visited is None:
        visited = set()
    
    if node in visited:
        return None
    
    visited.add(node)
    
    # Handle different node types
    if node.type == 'BSDF_PRINCIPLED':
        # For Principled BSDF, use base color if not connected to anything
        if not node.inputs['Base Color'].links:
            return node.inputs['Base Color'].default_value[:3]
        else:
            # Try to calculate the color of the connected node
            from_node = node.inputs['Base Color'].links[0].from_node
            return calculate_node_color(from_node, visited)
    
    elif node.type == 'MIX_RGB':
        # For Mix RGB nodes, calculate based on blend type
        if node.blend_type == 'MIX':
            # Get factor
            factor = node.inputs['Fac'].default_value if not node.inputs['Fac'].links else 0.5
            
            # Get colors
            color1 = (1.0, 1.0, 1.0)
            color2 = (1.0, 1.0, 1.0)
            
            if not node.inputs['Color1'].links:
                color1 = node.inputs['Color1'].default_value[:3]
            else:
                from_color = calculate_node_color(node.inputs['Color1'].links[0].from_node, visited)
                if from_color:
                    color1 = from_color
            
            if not node.inputs['Color2'].links:
                color2 = node.inputs['Color2'].default_value[:3]
            else:
                from_color = calculate_node_color(node.inputs['Color2'].links[0].from_node, visited)
                if from_color:
                    color2 = from_color
            
            # Mix colors
            return (
                color1[0] * (1 - factor) + color2[0] * factor,
                color1[1] * (1 - factor) + color2[1] * factor,
                color1[2] * (1 - factor) + color2[2] * factor
            )
        
        elif node.blend_type == 'MULTIPLY':
            # Get colors
            color1 = (1.0, 1.0, 1.0)
            color2 = (1.0, 1.0, 1.0)
            
            if not node.inputs['Color1'].links:
                color1 = node.inputs['Color1'].default_value[:3]
            else:
                from_color = calculate_node_color(node.inputs['Color1'].links[0].from_node, visited)
                if from_color:
                    color1 = from_color
            
            if not node.inputs['Color2'].links:
                color2 = node.inputs['Color2'].default_value[:3]
            else:
                from_color = calculate_node_color(node.inputs['Color2'].links[0].from_node, visited)
                if from_color:
                    color2 = from_color
            
            # Multiply colors
            return (
                color1[0] * color2[0],
                color1[1] * color2[1],
                color1[2] * color2[2]
            )
    
    elif node.type == 'TEX_IMAGE' and node.image:
        # For image textures, calculate average color
        return get_average_color(node.image)[:3]
    
    # For other node types with color inputs
    for input_name in ['Color', 'Color1', 'Color2', 'Diffuse Color']:
        if input_name in node.inputs and not node.inputs[input_name].links:
            return node.inputs[input_name].default_value[:3]
    
    # If we can't calculate, return None
    return None

def find_color_or_texture(node, visited=None):
    """Find a color or texture in the node tree."""
    if visited is None:
        visited = set()
    
    if node in visited:
        return None, None
    
    visited.add(node)
    
    # Check for image textures
    if node.type == 'TEX_IMAGE' and node.image:
        return node.image, None
    
    # Check for color inputs
    for input_name in ['Color', 'Color1', 'Color2', 'Base Color', 'Diffuse Color']:
        if input_name in node.inputs:
            if not node.inputs[input_name].links:
                return None, node.inputs[input_name].default_value[:3]
            else:
                # Check connected node
                from_node = node.inputs[input_name].links[0].from_node
                image, color = find_color_or_texture(from_node, visited)
                if image or color:
                    return image, color
    
    # Recursively check all connected nodes
    for input_socket in node.inputs:
        for link in input_socket.links:
            image, color = find_color_or_texture(link.from_node, visited)
            if image or color:
                return image, color
    
    return None, None

def set_viewport_colors():
    """Set Viewport Display colors based on the final shader output."""
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue
        
        # Get the final color or texture from the material
        image, color = get_final_color(mat)
        
        # Set the viewport color
        if image and not any(color):  # Only use image if we couldn't calculate a color
            mat.diffuse_color = get_average_color(image)
        else:
            mat.diffuse_color = (*color, 1.0)

class VIEWPORT_PT_SetViewportColorsPanel(bpy.types.Panel):
    """Add button to Material Properties"""
    bl_label = "Set Viewport Colors"
    bl_idname = "VIEWPORT_PT_set_viewport_colors"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    def draw(self, context):
        layout = self.layout
        layout.operator("material.set_viewport_colors")

def register():
    bpy.utils.register_class(VIEWPORT_OT_SetViewportColors)
    bpy.utils.register_class(VIEWPORT_PT_SetViewportColorsPanel)

def unregister():
    bpy.utils.unregister_class(VIEWPORT_OT_SetViewportColors)
    bpy.utils.unregister_class(VIEWPORT_PT_SetViewportColorsPanel)

if __name__ == "__main__":
    register()
