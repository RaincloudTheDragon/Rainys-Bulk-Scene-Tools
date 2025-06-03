import bpy

class RemoveCustomSplitNormals(bpy.types.Operator):
    """Remove custom split normals and apply smooth shading to all accessible mesh objects"""
    bl_idname = "bst.remove_custom_split_normals"
    bl_label = "Remove Custom Split Normals"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Store the current context
        original_active = context.active_object
        original_selected = context.selected_objects.copy()
        original_mode = context.mode

        # Clear selection
        bpy.ops.object.select_all(action='DESELECT')

        # Get object names that are in the current view layer
        view_layer_object_names = set(context.view_layer.objects.keys())

        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.name in view_layer_object_names:
                mesh = obj.data

                # Only proceed if mesh has custom normals
                if mesh.has_custom_normals:
                    # Select and make active
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    
                    # Enter Edit mode
                    bpy.ops.object.mode_set(mode='EDIT')
                    
                    # Clear custom split normals
                    bpy.ops.mesh.customdata_custom_splitnormals_clear()
                    
                    # Return to Object mode
                    bpy.ops.object.mode_set(mode='OBJECT')

                    # Set to smooth shading
                    bpy.ops.object.shade_smooth()
                    
                    # Deselect
                    obj.select_set(False)
                    
                    self.report({'INFO'}, f"Removed custom split normals and applied smooth shading to: {obj.name}")

        # Restore original selection and active object
        context.view_layer.objects.active = original_active
        for obj in original_selected:
            if obj.name in view_layer_object_names:
                obj.select_set(True)

        self.report({'INFO'}, "Done: custom split normals removed and smooth shading applied to all accessible mesh objects.")
        return {'FINISHED'}

# Registration
def register():
    bpy.utils.register_class(MESH_OT_RemoveCustomSplitNormals)

def unregister():
    bpy.utils.unregister_class(MESH_OT_RemoveCustomSplitNormals)

# Only run if this script is run directly
if __name__ == "__main__":
    register()
