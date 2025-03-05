bl_info = {
    "name": "Set Viewport Colors from BSDF",
    "author": "RaincloudTheDragon",
    "version": (0, 0, 1),
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

def set_viewport_colors():
    """Set Viewport Display colors based on BSDF base color, PBR diffuse color, or texture."""
    for mat in bpy.data.materials:
        if not mat.use_nodes or not mat.node_tree:
            continue

        base_color = (1.0, 1.0, 1.0)  # Default white
        linked_image = None

        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                # Found a Principled BSDF node
                base_color = node.inputs['Base Color'].default_value[:3]

                # Check for a connected texture
                if node.inputs['Base Color'].links:
                    linked_image = find_image_node(node)
                break  # Stop searching, since we prioritize BSDF
            elif "Diffuse Color" in node.inputs:
                # Found a non-BSDF shader with a "Diffuse Color" input
                base_color = node.inputs["Diffuse Color"].default_value[:3]

                # Check if a texture is connected
                if node.inputs["Diffuse Color"].links:
                    linked_image = find_image_node(node)

        # Use image color if available, otherwise use diffuse/base color
        display_color = get_average_color(linked_image) if linked_image else (*base_color, 1.0)

        mat.diffuse_color = display_color

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
