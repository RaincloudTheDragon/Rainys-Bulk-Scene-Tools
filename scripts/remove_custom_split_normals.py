import bpy

# Store the current context
original_active = bpy.context.active_object
original_selected = bpy.context.selected_objects.copy()
original_mode = bpy.context.mode

# Clear selection
bpy.ops.object.select_all(action='DESELECT')

# Get object names that are in the current view layer
view_layer_object_names = set(bpy.context.view_layer.objects.keys())

for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.name in view_layer_object_names:
        mesh = obj.data

        # Only proceed if mesh has custom normals
        if mesh.has_custom_normals:
            # Select and make active
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            
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
            
            print(f"Removed custom split normals and applied smooth shading to: {obj.name}")

# Restore original selection and active object
bpy.context.view_layer.objects.active = original_active
for obj in original_selected:
    if obj.name in view_layer_object_names:
        obj.select_set(True)

print("Done: custom split normals removed and smooth shading applied to all accessible mesh objects.")
