import bpy

class NoSubdiv(bpy.types.Operator):
    """Remove all subdivision surface modifiers from objects"""
    bl_idname = "bst.no_subdiv"
    bl_label = "No Subdiv"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Iterate over all objects in the scene
        for obj in bpy.data.objects:
            # Check if object has modifiers
            if obj.modifiers:
                # Collect all subdivision modifiers to remove
                subdiv_mods = [mod for mod in obj.modifiers if mod.type == 'SUBSURF']
                for mod in subdiv_mods:
                    obj.modifiers.remove(mod)
        
        self.report({'INFO'}, "Subdivision Surface modifiers removed from all objects.")
        return {'FINISHED'}

print("Subdivision Surface modifiers removed from all objects.")
