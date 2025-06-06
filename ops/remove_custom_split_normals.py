import bpy

class RemoveCustomSplitNormals(bpy.types.Operator):
    """Remove custom split normals and apply smooth shading to all accessible mesh objects"""
    bl_idname = "bst.remove_custom_split_normals"
    bl_label = "Remove Custom Split Normals"
    bl_options = {'REGISTER', 'UNDO'}

    only_selected: bpy.props.BoolProperty(
        name="Only Selected Objects",
        description="Apply only to selected objects",
        default=True
    )

    def execute(self, context):
        # Store the current context
        original_active = context.active_object
        original_selected = context.selected_objects.copy()
        original_mode = context.mode

        # Get object names that are in the current view layer
        view_layer_object_names = set(context.view_layer.objects.keys())

        # Choose objects based on the property
        if self.only_selected:
            objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.name in view_layer_object_names]
        else:
            objects = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.name in view_layer_object_names]

        processed_count = 0
        for obj in objects:
            mesh = obj.data
            if mesh.has_custom_normals:
                # Select and make active
                obj.select_set(True)
                context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.customdata_custom_splitnormals_clear()
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.shade_smooth()
                obj.select_set(False)
                processed_count += 1
                self.report({'INFO'}, f"Removed custom split normals and applied smooth shading to: {obj.name}")

        # Restore original selection and active object
        context.view_layer.objects.active = original_active
        for obj in original_selected:
            if obj.name in view_layer_object_names:
                obj.select_set(True)

        self.report({'INFO'}, f"Done: custom split normals removed and smooth shading applied to {'selected' if self.only_selected else 'all'} mesh objects. ({processed_count} processed)")
        return {'FINISHED'}

# Registration
def register():
    bpy.utils.register_class(MESH_OT_RemoveCustomSplitNormals)

def unregister():
    bpy.utils.unregister_class(MESH_OT_RemoveCustomSplitNormals)

# Only run if this script is run directly
if __name__ == "__main__":
    register()
