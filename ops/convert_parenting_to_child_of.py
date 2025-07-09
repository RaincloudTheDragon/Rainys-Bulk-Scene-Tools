import bpy

def convert_parenting_to_child_of_constraints():
    """Convert regular parenting to Child Of constraints for all selected objects"""
    
    # Get all selected objects
    selected_objects = bpy.context.selected_objects
    
    if not selected_objects:
        print("No objects selected!")
        return
    
    print(f"Converting parenting to Child Of constraints for {len(selected_objects)} objects...")
    
    converted_count = 0
    
    for obj in selected_objects:
        # Check if object has a parent
        if obj.parent is None:
            print(f"Skipping {obj.name}: No parent found")
            continue
        
        print(f"Processing {obj.name} -> {obj.parent.name}")
        
        # Store original parent and current world matrix
        original_parent = obj.parent
        world_matrix = obj.matrix_world.copy()
        
        # Remove the parent relationship
        obj.parent = None
        
        # Add Child Of constraint
        child_of_constraint = obj.constraints.new(type='CHILD_OF')
        child_of_constraint.name = f"Child_Of_{original_parent.name}"
        child_of_constraint.target = original_parent
        
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

# Run the conversion
if __name__ == "__main__":
    convert_parenting_to_child_of_constraints() 