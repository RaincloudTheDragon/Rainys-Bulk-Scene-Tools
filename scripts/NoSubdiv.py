import bpy

# Iterate over all objects in the scene
for obj in bpy.data.objects:
    # Check if object has modifiers
    if obj.modifiers:
        # Collect all subdivision modifiers to remove
        subdiv_mods = [mod for mod in obj.modifiers if mod.type == 'SUBSURF']
        for mod in subdiv_mods:
            obj.modifiers.remove(mod)

print("Subdivision Surface modifiers removed from all objects.")
