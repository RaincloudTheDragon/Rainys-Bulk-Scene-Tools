import bpy

class MATERIAL_USERS_OT_summary_dialog(bpy.types.Operator):
    """Show material users analysis in a popup dialog"""
    bl_idname = "bst.material_users_summary_dialog"
    bl_label = "Material Users Summary"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    # Properties to store summary data
    material_name: bpy.props.StringProperty(default="")
    users_count: bpy.props.IntProperty(default=0)
    fake_user: bpy.props.BoolProperty(default=False)
    object_users: bpy.props.StringProperty(default="")
    node_users: bpy.props.StringProperty(default="")
    material_node_users: bpy.props.StringProperty(default="")
    total_user_count: bpy.props.IntProperty(default=0)
    
    def draw(self, context):
        layout = self.layout
        
        # Title
        layout.label(text=f"Material Users - '{self.material_name}'", icon='MATERIAL')
        layout.separator()
        
        # Basic info box
        box = layout.box()
        col = box.column(align=True)
        col.label(text=f"Blender Users Count: {self.users_count}")
        col.label(text=f"Fake User: {'Yes' if self.fake_user else 'No'}")
        col.label(text=f"Total Found Users: {self.total_user_count}")
        
        layout.separator()
        
        # Object users section
        if self.object_users:
            layout.label(text="Object Users:", icon='OBJECT_DATA')
            objects_box = layout.box()
            objects_col = objects_box.column(align=True)
            for obj_name in self.object_users.split('|'):
                if obj_name.strip():
                    objects_col.label(text=f"• {obj_name}", icon='RIGHTARROW_THIN')
        else:
            layout.label(text="Object Users: None", icon='OBJECT_DATA')
        
        # Node tree users section
        if self.node_users:
            layout.separator()
            layout.label(text="Node Tree Users:", icon='NODETREE')
            nodes_box = layout.box()
            nodes_col = nodes_box.column(align=True)
            for node_ref in self.node_users.split('|'):
                if node_ref.strip():
                    nodes_col.label(text=f"• {node_ref}", icon='RIGHTARROW_THIN')
        
        # Material node tree users section
        if self.material_node_users:
            layout.separator()
            layout.label(text="Material Node Tree Users:", icon='MATERIAL')
            mat_nodes_box = layout.box()
            mat_nodes_col = mat_nodes_box.column(align=True)
            for mat_node_ref in self.material_node_users.split('|'):
                if mat_node_ref.strip():
                    mat_nodes_col.label(text=f"• {mat_node_ref}", icon='RIGHTARROW_THIN')
        
        layout.separator()
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=500)

class FindMaterialUsers(bpy.types.Operator):
    """Find all users of a specified material and display detailed information"""
    bl_idname = "bst.find_material_users"
    bl_label = "Find Material Users"
    bl_description = "Find and display all users of a specified material"
    bl_options = {'REGISTER'}

    material_name: bpy.props.StringProperty(
        name="Material",
        description="Name of the material to analyze",
        default="",
    )

    def draw(self, context):
        layout = self.layout
        
        # Set the material if we have a name
        if self.material_name and self.material_name in bpy.data.materials:
            context.scene.bst_temp_material = bpy.data.materials[self.material_name]
        
        # Use template_ID to get the proper material selector (without new button)
        layout.template_ID(context.scene, "bst_temp_material", text="Material")

    def execute(self, context):
        # Get the material from the temp property
        material = getattr(context.scene, 'bst_temp_material', None)
        
        if not material:
            self.report({'ERROR'}, "No material selected")
            return {'CANCELLED'}

        # Update our material_name property
        self.material_name = material.name

        # Check objects
        object_users = []
        for obj in bpy.data.objects:
            if obj.material_slots:
                for slot in obj.material_slots:
                    if slot.material == material:
                        object_users.append(obj.name)
                        break
        
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
                        if input_socket.default_value.name == material.name:
                            node_users.append(f"{node_tree.name}.{node.name}.{input_socket.name}")
        
        # Check material node trees
        material_node_users = []
        for mat in bpy.data.materials:
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if hasattr(node, 'material') and node.material == material:
                        material_node_users.append(f"{mat.name}.{node.name}")
        
        # Show summary dialog
        self.show_summary_dialog(context, material, object_users, node_users, material_node_users)
        return {'FINISHED'}

    def show_summary_dialog(self, context, material, object_users, node_users, material_node_users):
        """Show the material users summary in a popup dialog"""
        total_user_count = len(object_users) + len(node_users) + len(material_node_users)
        
        # Create and configure the summary dialog
        dialog_op = bpy.ops.bst.material_users_summary_dialog
        dialog_op('INVOKE_DEFAULT',
                  material_name=material.name,
                  users_count=material.users,
                  fake_user=material.use_fake_user,
                  object_users='|'.join(object_users),
                  node_users='|'.join(node_users),
                  material_node_users='|'.join(material_node_users),
                  total_user_count=total_user_count)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self) 