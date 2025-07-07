import bpy

def safe_wgt_removal():
    """Safely remove only WGT widget objects that are clearly ghosts"""
    
    print("="*80)
    print("CONSERVATIVE WGT GHOST REMOVAL")
    print("="*80)
    
    # Find all WGT objects
    wgt_objects = []
    for obj in bpy.data.objects:
        if obj.name.startswith('WGT-'):
            wgt_objects.append(obj)
    
    print(f"Found {len(wgt_objects)} WGT objects")
    
    # Check which ones are actually being used by armatures
    used_wgts = set()
    for armature in bpy.data.armatures:
        for bone in armature.bones:
            if bone.use_deform and hasattr(bone, 'custom_shape') and bone.custom_shape:
                used_wgts.add(bone.custom_shape.name)
    
    print(f"Found {len(used_wgts)} WGT objects actually used by armatures")
    
    # Remove unused WGT objects
    removed_wgts = 0
    for obj in wgt_objects:
        if obj.name not in used_wgts:
            try:
                # Skip linked objects (they're legitimate library content)
                if hasattr(obj, 'library') and obj.library is not None:
                    print(f"  Skipping linked WGT: {obj.name} (from {obj.library.name})")
                    continue
                
                # Check if it's in the WGTS collection (typical ghost pattern)
                in_wgts_collection = False
                for collection in bpy.data.collections:
                    if 'WGTS' in collection.name and obj in collection.objects.values():
                        in_wgts_collection = True
                        break
                
                if in_wgts_collection:
                    print(f"  Removing unused WGT: {obj.name}")
                    bpy.data.objects.remove(obj, do_unlink=True)
                    removed_wgts += 1
            except Exception as e:
                print(f"  Failed to remove {obj.name}: {e}")
    
    print(f"Removed {removed_wgts} unused WGT objects")
    return removed_wgts

def is_collection_in_scene_hierarchy(collection, scene_collection):
    """Recursively check if a collection exists anywhere in the scene collection hierarchy"""
    if collection == scene_collection:
        return True
    
    for child_collection in scene_collection.children:
        if child_collection == collection:
            return True
        if is_collection_in_scene_hierarchy(collection, child_collection):
            return True
    
    return False

def clean_empty_collections():
    """Remove empty collections that are not linked to scenes"""
    
    print("\n" + "="*80)
    print("CLEANING EMPTY COLLECTIONS")
    print("="*80)
    
    removed_collections = 0
    collections_to_remove = []
    
    for collection in bpy.data.collections:
        # Check if collection is empty
        if len(collection.objects) == 0 and len(collection.children) == 0:
            # Skip linked collections (they're legitimate library content)
            if hasattr(collection, 'library') and collection.library is not None:
                print(f"  Skipping linked empty collection: {collection.name}")
                continue
            
            # Check if it's anywhere in any scene's collection hierarchy
            linked_to_scene = False
            for scene in bpy.data.scenes:
                if is_collection_in_scene_hierarchy(collection, scene.collection):
                    linked_to_scene = True
                    print(f"  Preserving empty collection: {collection.name} (in scene '{scene.name}')")
                    break
            
            if not linked_to_scene:
                collections_to_remove.append(collection)
    
    for collection in collections_to_remove:
        try:
            print(f"  Removing empty collection: {collection.name}")
            bpy.data.collections.remove(collection)
            removed_collections += 1
        except Exception as e:
            print(f"  Failed to remove collection {collection.name}: {e}")
    
    print(f"Removed {removed_collections} empty collections")
    return removed_collections

def is_object_used_by_scene_instance_collections(obj):
    """Check if object is in a collection that's being instanced by objects in scenes"""
    
    # Find all collections that contain this object
    obj_collections = []
    for collection in bpy.data.collections:
        if obj in collection.objects.values():
            obj_collections.append(collection)
    
    if not obj_collections:
        return False
    
    # Check if any of these collections are being instanced by objects in scenes
    for collection in obj_collections:
        # Find objects that instance this collection
        for other_obj in bpy.data.objects:
            if (other_obj.instance_type == 'COLLECTION' and 
                other_obj.instance_collection == collection):
                
                # Check if the instancing object is in any scene
                for scene in bpy.data.scenes:
                    if other_obj in scene.objects.values():
                        return True
    
    return False

def is_object_legitimate_outside_scene(obj):
    """Check if an object has legitimate reasons to exist outside scenes"""
    
    # WGT objects (rig widgets) are legitimate outside scenes
    if obj.name.startswith('WGT-'):
        return True
    
    # Collection instance objects (linked collection references) are legitimate
    if obj.instance_type == 'COLLECTION' and obj.instance_collection is not None:
        return True
    
    # Objects that are being used by instance collections in scenes are legitimate
    if is_object_used_by_scene_instance_collections(obj):
        return True
    
    # Objects used as curve modifiers, constraints targets, etc.
    # Check if object is used by modifiers on other objects that are in scenes
    for other_obj in bpy.data.objects:
        # Check if the other object is in any scene
        in_scene = False
        for scene in bpy.data.scenes:
            if other_obj in scene.objects.values():
                in_scene = True
                break
        
        if in_scene:
            for modifier in other_obj.modifiers:
                if hasattr(modifier, 'object') and modifier.object == obj:
                    return True
                if hasattr(modifier, 'target') and modifier.target == obj:
                    return True
    
    # Check if object is used by constraints on other objects that are in scenes
    for other_obj in bpy.data.objects:
        # Check if the other object is in any scene
        in_scene = False
        for scene in bpy.data.scenes:
            if other_obj in scene.objects.values():
                in_scene = True
                break
        
        if in_scene:
            for constraint in other_obj.constraints:
                if hasattr(constraint, 'target') and constraint.target == obj:
                    return True
                if hasattr(constraint, 'subtarget') and constraint.subtarget == obj.name:
                    return True
    
    # Check if object is used in particle systems on objects that are in scenes
    for other_obj in bpy.data.objects:
        # Check if the other object is in any scene
        in_scene = False
        for scene in bpy.data.scenes:
            if other_obj in scene.objects.values():
                in_scene = True
                break
        
        if in_scene:
            for modifier in other_obj.modifiers:
                if modifier.type == 'PARTICLE_SYSTEM':
                    settings = modifier.particle_system.settings
                    if hasattr(settings, 'object') and settings.object == obj:
                        return True
                    if hasattr(settings, 'instance_object') and settings.instance_object == obj:
                        return True
    
    return False

def clean_object_ghosts(delete_low_priority=False):
    """Remove objects that are not in any scene and have no legitimate purpose (potential ghosts)"""
    
    print("\n" + "="*80)
    print("OBJECT GHOST CLEANUP")
    print("="*80)
    
    # Get all objects, excluding cameras and lights by default (they're often not in scenes for good reasons)
    candidate_objects = [obj for obj in bpy.data.objects if obj.type not in ['CAMERA', 'LIGHT']]
    
    if not candidate_objects:
        print("No candidate objects found")
        return 0
    
    print(f"Found {len(candidate_objects)} candidate objects")
    
    removed_objects = 0
    ghosts_to_remove = []
    
    for obj in candidate_objects:
        # Skip linked objects (they're legitimate library content)
        if hasattr(obj, 'library') and obj.library is not None:
            continue
        
        # Check which scenes contain it
        in_scenes = []
        for scene in bpy.data.scenes:
            if obj in scene.objects.values():
                in_scenes.append(scene.name)
        
        # If not in any scene, check if it has legitimate reasons to exist
        if len(in_scenes) == 0:
            if is_object_legitimate_outside_scene(obj):
                print(f"  Preserving object: {obj.name} (legitimate use outside scene)")
                continue
            
            # If not legitimate, it's a ghost - but be conservative with low user count objects
            should_remove = False
            removal_reason = ""
            
            if obj.users >= 2:
                # Higher user count ghosts are definitely safe to remove
                should_remove = True
                removal_reason = "ghost (users >= 2, no legitimate use found)"
            elif obj.users < 2 and delete_low_priority:
                # Low user count ghosts only if user enables the option
                should_remove = True
                removal_reason = "low priority ghost (users < 2, no legitimate use found)"
            elif obj.users < 2:
                print(f"  Skipping low priority object: {obj.name} (users < 2, enable 'Delete Low Priority' to remove)")
            
            if should_remove:
                ghosts_to_remove.append(obj)
                print(f"  Marking ghost for removal: {obj.name} (type: {obj.type}) - {removal_reason}")
    
    # Remove the ghost objects
    for obj in ghosts_to_remove:
        try:
            print(f"  Removing object ghost: {obj.name}")
            bpy.data.objects.remove(obj, do_unlink=True)
            removed_objects += 1
        except Exception as e:
            print(f"  Failed to remove object {obj.name}: {e}")
    
    print(f"Removed {removed_objects} ghost objects")
    return removed_objects

def manual_object_analysis():
    """Manual analysis of objects - show info but don't auto-remove"""
    
    print("\n" + "="*80)
    print("OBJECT GHOST ANALYSIS (MANUAL REVIEW)")
    print("="*80)
    
    # Get all objects, excluding cameras and lights (they're often legitimately not in scenes)
    candidate_objects = [obj for obj in bpy.data.objects if obj.type not in ['CAMERA', 'LIGHT']]
    
    # Filter to only objects not in scenes for analysis
    objects_not_in_scenes = []
    for obj in candidate_objects:
        # Skip linked objects for analysis
        if hasattr(obj, 'library') and obj.library is not None:
            continue
        
        # Check which scenes contain it
        in_scenes = []
        for scene in bpy.data.scenes:
            if obj in scene.objects.values():
                in_scenes.append(scene.name)
        
        if len(in_scenes) == 0:
            objects_not_in_scenes.append(obj)
    
    if not objects_not_in_scenes:
        print("No local objects found outside scenes")
        return
    
    print(f"Found {len(objects_not_in_scenes)} local objects not in any scene:")
    
    for obj in objects_not_in_scenes:
        print(f"\n  Object: {obj.name} (type: {obj.type})")
        print(f"    Users: {obj.users}")
        print(f"    Parent: {obj.parent.name if obj.parent else 'None'}")
        
        # Check collections
        in_collections = []
        for collection in bpy.data.collections:
            if obj in collection.objects.values():
                in_collections.append(collection.name)
        print(f"    In collections: {in_collections}")
        
        # Show recommendation
        if is_object_legitimate_outside_scene(obj):
            print(f"    -> LEGITIMATE: Has valid use outside scenes")
        elif obj.users >= 2:
            print(f"    -> GHOST: No legitimate use found, users >= 2 (will be removed)")
        elif obj.users < 2:
            print(f"    -> LOW PRIORITY: No legitimate use found, users < 2 (needs option enabled)")
        else:
            print(f"    -> UNCLEAR: Manual review needed")

def main(delete_low_priority=False):
    """Main conservative cleanup function"""
    
    print("CONSERVATIVE GHOST DATA CLEANUP")
    print("="*80)
    print("This script removes:")
    print("1. Unused local WGT widget objects")
    print("2. Empty unlinked collections") 
    print("3. Objects not in any scene with no legitimate use")
    if delete_low_priority:
        print("   - Including low priority ghosts (no legitimate use, users < 2)")
    else:
        print("   - Excluding low priority ghosts (no legitimate use, users < 2)")
    print("="*80)
    
    initial_objects = len(list(bpy.data.objects))
    initial_collections = len(list(bpy.data.collections))
    
    # Safe operations only
    wgts_removed = safe_wgt_removal()
    collections_removed = clean_empty_collections()
    object_ghosts_removed = clean_object_ghosts(delete_low_priority)
    
    # Show remaining object analysis
    manual_object_analysis()
    
    # Final purge
    print("\n" + "="*80)
    print("FINAL SAFE PURGE")
    print("="*80)
    
    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        print("Safe purge completed")
    except:
        print("Purge had issues")
    
    final_objects = len(list(bpy.data.objects))
    final_collections = len(list(bpy.data.collections))
    
    print(f"\n" + "="*80)
    print("CONSERVATIVE CLEANUP SUMMARY")
    print("="*80)
    print(f"Objects: {initial_objects} -> {final_objects} (removed {initial_objects - final_objects})")
    print(f"Collections: {initial_collections} -> {final_collections} (removed {collections_removed})")
    print(f"WGT objects removed: {wgts_removed}")
    print(f"Object ghosts removed: {object_ghosts_removed}")
    print("="*80)

class GhostBuster(bpy.types.Operator):
    """Conservative cleanup of ghost data (unused WGT objects, empty collections)"""
    bl_idname = "bst.ghost_buster"
    bl_label = "Ghost Buster"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            # Get the delete low priority setting from scene properties
            delete_low_priority = getattr(context.scene, "ghost_buster_delete_low_priority", False)
            
            # Call the main ghost buster function
            main(delete_low_priority)
            self.report({'INFO'}, "Ghost data cleanup completed")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Ghost buster failed: {str(e)}")
            return {'CANCELLED'}

class GhostDetector(bpy.types.Operator):
    """Detect and analyze ghost data without removing it"""
    bl_idname = "bst.ghost_detector"
    bl_label = "Ghost Detector"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    # Properties to store analysis data
    total_wgt_objects: bpy.props.IntProperty(default=0)
    unused_wgt_objects: bpy.props.IntProperty(default=0)
    used_wgt_objects: bpy.props.IntProperty(default=0)
    empty_collections: bpy.props.IntProperty(default=0)
    ghost_objects: bpy.props.IntProperty(default=0)
    ghost_potential: bpy.props.IntProperty(default=0)
    ghost_legitimate: bpy.props.IntProperty(default=0)
    ghost_low_priority: bpy.props.IntProperty(default=0)
    wgt_details: bpy.props.StringProperty(default="")
    collection_details: bpy.props.StringProperty(default="")
    ghost_details: bpy.props.StringProperty(default="")
    
    def analyze_ghost_data(self):
        """Analyze ghost data similar to ghost_buster functions"""
        
        # Analyze WGT objects
        wgt_objects = []
        for obj in bpy.data.objects:
            if obj.name.startswith('WGT-'):
                wgt_objects.append(obj)
        
        self.total_wgt_objects = len(wgt_objects)
        
        # Check which WGT objects are used by armatures
        used_wgts = set()
        for armature in bpy.data.armatures:
            for bone in armature.bones:
                if bone.use_deform and hasattr(bone, 'custom_shape') and bone.custom_shape:
                    used_wgts.add(bone.custom_shape.name)
        
        self.used_wgt_objects = len(used_wgts)
        
        # Count unused WGT objects
        unused_wgts = []
        wgt_details_list = []
        for obj in wgt_objects:
            if obj.name not in used_wgts:
                # Skip linked objects (they're legitimate library content)
                if hasattr(obj, 'library') and obj.library is not None:
                    continue
                
                # Check if it's in the WGTS collection (typical ghost pattern)
                in_wgts_collection = False
                for collection in bpy.data.collections:
                    if 'WGTS' in collection.name and obj in collection.objects.values():
                        in_wgts_collection = True
                        break
                
                if in_wgts_collection:
                    unused_wgts.append(obj)
                    wgt_details_list.append(f"• {obj.name} (in WGTS collection)")
        
        self.unused_wgt_objects = len(unused_wgts)
        self.wgt_details = "\n".join(wgt_details_list[:10])  # Limit to first 10
        if len(unused_wgts) > 10:
            self.wgt_details += f"\n... and {len(unused_wgts) - 10} more"
        
        # Analyze empty collections
        empty_collections = []
        collection_details_list = []
        for collection in bpy.data.collections:
            if len(collection.objects) == 0 and len(collection.children) == 0:
                # Skip linked collections (they're legitimate library content)
                if hasattr(collection, 'library') and collection.library is not None:
                    continue
                
                # Check if it's anywhere in any scene's collection hierarchy
                linked_to_scene = False
                for scene in bpy.data.scenes:
                    if is_collection_in_scene_hierarchy(collection, scene.collection):
                        linked_to_scene = True
                        break
                
                if not linked_to_scene:
                    empty_collections.append(collection)
                    collection_details_list.append(f"• {collection.name}")
        
        self.empty_collections = len(empty_collections)
        self.collection_details = "\n".join(collection_details_list[:10])  # Limit to first 10
        if len(empty_collections) > 10:
            self.collection_details += f"\n... and {len(empty_collections) - 10} more"
        
        # Analyze ghost objects (objects not in scenes)
        candidate_objects = [obj for obj in bpy.data.objects if obj.type not in ['CAMERA', 'LIGHT']]
        
        potential_ghosts = 0
        legitimate = 0
        low_priority = 0
        ghost_details_list = []
        
        for obj in candidate_objects:
            # Skip linked objects (they're legitimate library content)
            if hasattr(obj, 'library') and obj.library is not None:
                continue
            
            # Check which scenes contain it
            in_scenes = []
            for scene in bpy.data.scenes:
                if obj in scene.objects.values():
                    in_scenes.append(scene.name)
            
            # Only analyze objects not in scenes
            if len(in_scenes) == 0:
                # Classify object
                status = ""
                if is_object_legitimate_outside_scene(obj):
                    legitimate += 1
                    status = "LEGITIMATE (has valid use outside scenes)"
                elif obj.users >= 2:
                    potential_ghosts += 1
                    status = "GHOST (no legitimate use found, users >= 2)"
                elif obj.users < 2:
                    low_priority += 1
                    status = "LOW PRIORITY (no legitimate use found, users < 2)"
                else:
                    status = "UNCLEAR"
                
                ghost_details_list.append(f"• {obj.name} ({obj.type}): {status}")
        
        self.ghost_objects = len([obj for obj in candidate_objects if len([s for s in bpy.data.scenes if obj in s.objects.values()]) == 0 and not (hasattr(obj, 'library') and obj.library is not None)])
        self.ghost_potential = potential_ghosts
        self.ghost_legitimate = legitimate
        self.ghost_low_priority = low_priority
        self.ghost_details = "\n".join(ghost_details_list[:10])  # Limit to first 10
        if len(ghost_details_list) > 10:
            self.ghost_details += f"\n... and {len(ghost_details_list) - 10} more"
    
    def draw(self, context):
        layout = self.layout
        
        # Title
        layout.label(text="Ghost Data Analysis", icon='GHOST_ENABLED')
        layout.separator()
        
        # WGT Objects section
        box = layout.box()
        box.label(text="WGT Widget Objects", icon='ARMATURE_DATA')
        col = box.column(align=True)
        col.label(text=f"Total WGT objects: {self.total_wgt_objects}")
        col.label(text=f"Used by armatures: {self.used_wgt_objects}", icon='CHECKMARK')
        if self.unused_wgt_objects > 0:
            col.label(text=f"Unused (potential ghosts): {self.unused_wgt_objects}", icon='ERROR')
            if self.wgt_details:
                box.separator()
                details_col = box.column(align=True)
                for line in self.wgt_details.split('\n'):
                    if line.strip():
                        details_col.label(text=line)
        else:
            col.label(text="No unused WGT objects found", icon='CHECKMARK')
        
        # Empty Collections section
        box = layout.box()
        box.label(text="Empty Collections", icon='OUTLINER_COLLECTION')
        col = box.column(align=True)
        if self.empty_collections > 0:
            col.label(text=f"Empty unlinked collections: {self.empty_collections}", icon='ERROR')
            if self.collection_details:
                box.separator()
                details_col = box.column(align=True)
                for line in self.collection_details.split('\n'):
                    if line.strip():
                        details_col.label(text=line)
        else:
            col.label(text="No empty unlinked collections found", icon='CHECKMARK')
        
        # Ghost Objects section
        box = layout.box()
        box.label(text="Ghost Objects Analysis", icon='OBJECT_DATA')
        col = box.column(align=True)
        col.label(text=f"Objects not in scenes: {self.ghost_objects}")
        if self.ghost_objects > 0:
            if self.ghost_potential > 0:
                col.label(text=f"Ghosts (users >= 2): {self.ghost_potential}", icon='ERROR')
            if self.ghost_legitimate > 0:
                col.label(text=f"Legitimate objects: {self.ghost_legitimate}", icon='CHECKMARK')
            if self.ghost_low_priority > 0:
                col.label(text=f"Low priority (users < 2): {self.ghost_low_priority}", icon='QUESTION')
            
            if self.ghost_details:
                box.separator()
                details_col = box.column(align=True)
                for line in self.ghost_details.split('\n'):
                    if line.strip():
                        details_col.label(text=line)
        else:
            col.label(text="No ghost objects found", icon='CHECKMARK')
        
        # Summary
        layout.separator()
        summary_box = layout.box()
        summary_box.label(text="Summary", icon='INFO')
        total_issues = self.unused_wgt_objects + self.empty_collections + self.ghost_potential
        if total_issues > 0:
            summary_box.label(text=f"Found {total_issues} ghost data issues that will be removed", icon='ERROR')
            if self.ghost_low_priority > 0:
                summary_box.label(text=f"+ {self.ghost_low_priority} low priority issues (optional)", icon='QUESTION')
            summary_box.label(text="Use Ghost Buster to clean up safely")
        else:
            summary_box.label(text="No ghost data issues detected!", icon='CHECKMARK')
            if self.ghost_low_priority > 0:
                summary_box.label(text=f"({self.ghost_low_priority} low priority issues available)", icon='INFO')
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Analyze the ghost data before showing the dialog
        self.analyze_ghost_data()
        return context.window_manager.invoke_popup(self, width=500)

class ResyncEnforce(bpy.types.Operator):
    """Resync Enforce: Fix broken library override hierarchies by rebuilding from linked references"""
    bl_idname = "bst.resync_enforce"
    bl_label = "Resync Enforce"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        # Only available if there are selected objects
        return context.selected_objects
    
    def execute(self, context):
        # Get selected objects
        selected_objects = context.selected_objects.copy()
        
        if not selected_objects:
            self.report({'WARNING'}, "No objects selected for resync enforce")
            return {'CANCELLED'}
        
        # Count library override objects
        override_objects = []
        for obj in selected_objects:
            if obj.override_library:
                override_objects.append(obj)
        
        if not override_objects:
            self.report({'WARNING'}, "No library override objects found in selection")
            return {'CANCELLED'}
        
        try:
            # Store the current selection
            original_selection = set(context.selected_objects)
            
            # Select only the override objects
            bpy.ops.object.select_all(action='DESELECT')
            for obj in override_objects:
                obj.select_set(True)
            
            # Call Blender's resync enforce operation
            result = bpy.ops.object.library_override_operation(
                'INVOKE_DEFAULT',
                type='OVERRIDE_LIBRARY_RESYNC_HIERARCHY_ENFORCE',
                selection_set='SELECTED'
            )
            
            if result == {'FINISHED'}:
                self.report({'INFO'}, f"Resync enforce completed on {len(override_objects)} override objects")
                return_code = {'FINISHED'}
            else:
                self.report({'WARNING'}, "Resync enforce operation was cancelled or failed")
                return_code = {'CANCELLED'}
            
            # Restore original selection
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selection:
                if obj.name in bpy.data.objects:  # Check if object still exists
                    obj.select_set(True)
            
            return return_code
            
        except Exception as e:
            self.report({'ERROR'}, f"Resync enforce failed: {str(e)}")
            return {'CANCELLED'}

# Note: main() is called by the operator, not automatically

# List of classes to register
classes = (
    GhostBuster,
    GhostDetector,
    ResyncEnforce,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass