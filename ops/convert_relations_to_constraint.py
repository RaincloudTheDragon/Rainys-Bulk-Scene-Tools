import bpy

class ConvertRelationsToConstraint(bpy.types.Operator):
    """Convert regular parenting to Child Of constraints for all selected objects"""
    bl_idname = "bst.convert_relations_to_constraint"
    bl_label = "Convert Relations to Constraint"
    bl_description = "Convert regular parenting relationships to Child Of constraints for selected objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        result = convert_relations_to_constraint()
        if result:
            self.report({'INFO'}, f"Converted {result} objects to Child Of constraints")
        else:
            self.report({'WARNING'}, "No objects with parents found in selection")
        return {'FINISHED'}

def convert_relations_to_constraint():
    """Convert regular parenting to Child Of constraints for all selected objects"""
    
    # Get all selected objects
    selected_objects = bpy.context.selected_objects
    
    if not selected_objects:
        print("No objects selected!")
        return 0
    
    print(f"Converting parenting to Child Of constraints for {len(selected_objects)} objects...")
    
    converted_count = 0
    
    for obj in selected_objects:
        # Check if object has a parent
        if obj.parent is None:
            print(f"Skipping {obj.name}: No parent found")
            continue
        
        # Store bone information if parented to a bone
        parent_bone = obj.parent_bone if obj.parent_bone else None
        bone_info = f" (bone: {parent_bone})" if parent_bone else ""
        print(f"Processing {obj.name} -> {obj.parent.name}{bone_info}")
        
        # Store original parent and current world matrix
        original_parent = obj.parent
        world_matrix = obj.matrix_world.copy()
        
        # Remove the parent relationship
        obj.parent = None
        obj.parent_bone = ""  # Clear the bone reference
        
        # Add Child Of constraint
        child_of_constraint = obj.constraints.new(type='CHILD_OF')
        child_of_constraint.name = f"Child_Of_{original_parent.name}"
        child_of_constraint.target = original_parent
        
        # Transfer bone information to constraint subtarget
        if parent_bone:
            child_of_constraint.subtarget = parent_bone
            print(f"  ✓ Transferred bone target: {parent_bone}")
        
        # Set the inverse matrix properly to maintain world position
        # This is equivalent to clicking "Set Inverse" in the UI
        child_of_constraint.inverse_matrix = original_parent.matrix_world.inverted()
        
        # Restore the original world position
        obj.matrix_world = world_matrix
        
        # Set the constraint to be active
        child_of_constraint.influence = 1.0
        
        converted_count += 1
        print(f"  ✓ Converted {obj.name} to Child Of constraint")
    
    print(f"\nConversion complete! Converted {converted_count} objects.")
    
    # Report remaining parented objects
    remaining_parented = [obj for obj in bpy.context.selected_objects if obj.parent is not None]
    if remaining_parented:
        print(f"\nObjects that still have parents (not converted):")
        for obj in remaining_parented:
            print(f"  - {obj.name} -> {obj.parent.name}")
    
    return converted_count

# Run the conversion
if __name__ == "__main__":
    convert_relations_to_constraint() 