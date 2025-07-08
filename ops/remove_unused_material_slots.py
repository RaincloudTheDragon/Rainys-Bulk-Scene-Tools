import bpy

# Remove unused material slots from all objects
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.material_slots:
        # Temporarily ensure object is in view layer by linking to master collection
        if obj.name not in bpy.context.view_layer.objects:
            bpy.context.scene.collection.objects.link(obj)
            was_linked = True
        else:
            was_linked = False
            
        # Store original selection state
        original_selection = obj.select_get()
        original_active = bpy.context.view_layer.objects.active
        
        # Select the object and make it active
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        
        # Remove unused material slots
        bpy.ops.object.material_slot_remove_unused()
        
        # Restore original selection state
        obj.select_set(original_selection)
        bpy.context.view_layer.objects.active = original_active
        
        # Unlink if we linked it
        if was_linked:
            bpy.context.scene.collection.objects.unlink(obj)

print("Removed unused material slots from all objects") 