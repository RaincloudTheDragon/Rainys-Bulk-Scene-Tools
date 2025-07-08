import bpy

class FindMaterialUsers(bpy.types.Operator):
    """Find all users of a specified material and print detailed information"""
    bl_idname = "bst.find_material_users"
    bl_label = "Find Material Users"
    bl_description = "Find and display all users of a specified material"
    bl_options = {'REGISTER'}

    material_name: bpy.props.StringProperty(
        name="Material Name",
        description="Name of the material to search for",
        default="",
    )

    def execute(self, context):
        if not self.material_name:
            self.report({'ERROR'}, "Material name cannot be empty")
            return {'CANCELLED'}

        material = bpy.data.materials.get(self.material_name)

        if not material:
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}

        print(f"Material '{self.material_name}' users:")
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
                        if input_socket.default_value.name == self.material_name:
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
        
        user_count = len(object_users) + len(node_users) + len(material_node_users)
        self.report({'INFO'}, f"Found {user_count} users for material '{self.material_name}'. Check console for details")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self) 