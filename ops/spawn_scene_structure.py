import bpy

class SpawnSceneStructure(bpy.types.Operator):
    """Create a standard scene collection structure: Env, Animation, Lgt with subcollections"""
    bl_idname = "bst.spawn_scene_structure"
    bl_label = "Spawn Scene Structure"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        scene_collection = scene.collection
        
        # Define the structure to create
        structure = {
            "Env": ["ROOTS", "Dressing"],
            "Animation": ["Cam", "Char"],
            "Lgt": []
        }
        
        created_collections = []
        skipped_collections = []
        
        try:
            for main_collection_name, subcollections in structure.items():
                # Check if main collection already exists
                main_collection = None
                for existing_collection in scene_collection.children:
                    if existing_collection.name == main_collection_name:
                        main_collection = existing_collection
                        skipped_collections.append(main_collection_name)
                        break
                
                # Create main collection if it doesn't exist
                if main_collection is None:
                    main_collection = bpy.data.collections.new(main_collection_name)
                    scene_collection.children.link(main_collection)
                    created_collections.append(main_collection_name)
                
                # Create subcollections
                for subcollection_name in subcollections:
                    # Check if subcollection already exists
                    subcollection_exists = False
                    for existing_subcollection in main_collection.children:
                        if existing_subcollection.name == subcollection_name:
                            subcollection_exists = True
                            skipped_collections.append(f"{main_collection_name}/{subcollection_name}")
                            break
                    
                    # Create subcollection if it doesn't exist
                    if not subcollection_exists:
                        subcollection = bpy.data.collections.new(subcollection_name)
                        main_collection.children.link(subcollection)
                        created_collections.append(f"{main_collection_name}/{subcollection_name}")
            
            # Report results
            if created_collections:
                created_list = ", ".join(created_collections)
                if skipped_collections:
                    skipped_list = ", ".join(skipped_collections)
                    self.report({'INFO'}, f"Created: {created_list}. Skipped existing: {skipped_list}")
                else:
                    self.report({'INFO'}, f"Created scene structure: {created_list}")
            else:
                self.report({'INFO'}, "Scene structure already exists - no collections created")
            
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create scene structure: {str(e)}")
            return {'CANCELLED'} 