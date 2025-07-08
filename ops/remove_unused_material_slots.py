import bpy

class RemoveUnusedMaterialSlots(bpy.types.Operator):
    """Remove unused material slots from all mesh objects"""
    bl_idname = "bst.remove_unused_material_slots"
    bl_label = "Remove Unused Material Slots"
    bl_description = "Remove unused material slots from all mesh objects in the scene"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        processed_objects = 0
        
        # Store original active object and selection
        original_active = context.view_layer.objects.active
        original_selection = [obj for obj in context.selected_objects]
        
        try:
            # Remove unused material slots from all mesh objects
            for obj in bpy.data.objects:
                if obj.type == 'MESH' and obj.material_slots:
                    # Temporarily ensure object is in view layer by linking to master collection
                    was_linked = False
                    if obj.name not in context.view_layer.objects:
                        context.scene.collection.objects.link(obj)
                        was_linked = True
                    
                    # Store original selection state
                    original_obj_selection = obj.select_get()
                    
                    # Select the object and make it active
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    
                    # Remove unused material slots
                    bpy.ops.object.material_slot_remove_unused()
                    processed_objects += 1
                    
                    # Restore original selection state
                    obj.select_set(original_obj_selection)
                    
                    # Unlink if we linked it
                    if was_linked:
                        context.scene.collection.objects.unlink(obj)
        
        finally:
            # Restore original active object and selection
            context.view_layer.objects.active = original_active
            # Clear all selections first
            for obj in context.selected_objects:
                obj.select_set(False)
            # Restore original selection
            for obj in original_selection:
                if obj.name in context.view_layer.objects:
                    obj.select_set(True)

        self.report({'INFO'}, f"Removed unused material slots from {processed_objects} mesh objects")
        return {'FINISHED'} 