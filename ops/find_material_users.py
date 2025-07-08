import bpy

material_name = "_Black.001"
material = bpy.data.materials.get(material_name)

if not material:
    print(f"Material '{material_name}' not found")
else:
    print(f"Material '{material_name}' users:")
    print(f"  Users: {material.users}")
    print(f"  Fake users: {material.use_fake_user}")
    
    # Check objects
    object_users = []
    for obj in bpy.data.objects:
        if obj.material_slots:
            for slot in obj.material_slots:
                if slot.material == material:
                    object_users.append(obj.name)
                    break
    
    if object_users:
        print(f"  Objects: {object_users}")
    else:
        print("  Objects: None")
    
    # Check node groups more thoroughly
    node_users = []
    for node_tree in bpy.data.node_groups:
        for node in node_tree.nodes:
            # Check material nodes
            if hasattr(node, 'material') and node.material == material:
                node_users.append(f"{node_tree.name}.{node.name}")
            # Check material input sockets
            for input_socket in node.inputs:
                if hasattr(input_socket, 'default_value') and hasattr(input_socket.default_value, 'name'):
                    if input_socket.default_value.name == material_name:
                        node_users.append(f"{node_tree.name}.{node.name}.{input_socket.name}")
    
    if node_users:
        print(f"  Node trees: {node_users}")
    else:
        print("  Node trees: None")
    
    # Check material node trees
    material_node_users = []
    for mat in bpy.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if hasattr(node, 'material') and node.material == material:
                    material_node_users.append(f"{mat.name}.{node.name}")
    
    if material_node_users:
        print(f"  Material node trees: {material_node_users}")
    else:
        print("  Material node trees: None")
    
    # Check if it's linked to any data blocks
    print(f"  ID data users: {material.id_data.users if hasattr(material, 'id_data') else 'N/A'}") 