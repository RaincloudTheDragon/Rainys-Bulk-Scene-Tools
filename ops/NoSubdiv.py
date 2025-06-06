import bpy

class NoSubdiv(bpy.types.Operator):
    """Remove all subdivision surface modifiers from objects"""
    bl_idname = "bst.no_subdiv"
    bl_label = "No Subdiv"
    bl_options = {'REGISTER', 'UNDO'}

    only_selected: bpy.props.BoolProperty(
        name="Only Selected Objects",
        description="Apply only to selected objects",
        default=True
    )
    
    def execute(self, context):
        # Choose objects based on the property
        if self.only_selected:
            objects = context.selected_objects
        else:
            objects = bpy.data.objects
        removed_count = 0
        for obj in objects:
            if obj.modifiers:
                subdiv_mods = [mod for mod in obj.modifiers if mod.type == 'SUBSURF']
                for mod in subdiv_mods:
                    obj.modifiers.remove(mod)
                    removed_count += 1
        self.report({'INFO'}, f"Subdivision Surface modifiers removed from {'selected' if self.only_selected else 'all'} objects. ({removed_count} removed)")
        return {'FINISHED'}

print("Subdivision Surface modifiers removed from all objects.")
