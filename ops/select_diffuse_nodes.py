import bpy

def find_node_distance_to_basecolor(node, visited=None):
    """Find the shortest path distance from a node to any Base Color input"""
    if visited is None:
        visited = set()
    
    if node in visited:
        return float('inf')
    
    visited.add(node)
    
    # If this is a Principled BSDF node, check if it has a Base Color input
    if node.type == 'BSDF_PRINCIPLED':
        for input in node.inputs:
            if input.name == 'Base Color':
                # If this input is connected, return 0 (we found our target)
                if input.links:
                    return 0
                return float('inf')
    
    # Check all outputs of this node
    min_distance = float('inf')
    for output in node.outputs:
        for link in output.links:
            # Recursively check connected nodes
            distance = find_node_distance_to_basecolor(link.to_node, visited.copy())
            if distance is not None and distance < min_distance:
                min_distance = distance + 1
    
    return min_distance if min_distance != float('inf') else None

def find_connected_basecolor_texture(node_tree):
    """Find any image texture directly connected to a Base Color input"""
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            base_color_input = node.inputs.get('Base Color')
            if base_color_input and base_color_input.links:
                # Get the node connected to Base Color
                connected_node = base_color_input.links[0].from_node
                # If it's an image texture, return it
                if connected_node.type == 'TEX_IMAGE' and connected_node.image:
                    return connected_node
    return None

def select_diffuse_nodes():
    # Get all materials in the blend file
    materials = bpy.data.materials
    
    # Counter for found nodes
    found_nodes = 0
    
    # Keywords to look for in image names (case insensitive)
    keywords = ['diffuse', 'basecolor', 'base_color', 'albedo', 'color']
    
    # Iterate through all materials
    for material in materials:
        # Skip materials without node trees
        if not material.use_nodes:
            continue
            
        node_tree = material.node_tree
        
        # First, try to find any image texture connected to Base Color
        base_color_texture = find_connected_basecolor_texture(node_tree)
        if base_color_texture:
            node_tree.nodes.active = base_color_texture
            base_color_texture.select = True
            found_nodes += 1
            print(f"Selected Base Color connected texture '{base_color_texture.image.name}' in material: {material.name}")
            continue
        
        # If no direct connection found, fall back to name-based search
        matching_nodes = []
        for node in node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                # Check if the image name contains any of our keywords
                image_name = node.image.name.lower()
                if any(keyword in image_name for keyword in keywords):
                    # Calculate distance to Base Color input
                    distance = find_node_distance_to_basecolor(node)
                    if distance is not None:
                        matching_nodes.append((node, distance))
        
        # If we found any matching nodes, select the one with the shortest distance
        if matching_nodes:
            # Sort by distance (closest to Base Color first)
            matching_nodes.sort(key=lambda x: x[1])
            selected_node = matching_nodes[0][0]
            
            node_tree.nodes.active = selected_node
            selected_node.select = True
            found_nodes += 1
            print(f"Selected named texture '{selected_node.image.name}' in material: {material.name} (distance to Base Color: {matching_nodes[0][1]})")
    
    print(f"\nTotal texture nodes selected: {found_nodes}")

# Only run if this script is run directly
if __name__ == "__main__":
    select_diffuse_nodes() 