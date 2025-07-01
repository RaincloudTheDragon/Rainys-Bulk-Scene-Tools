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
            # Check if it's linked to any scene
            linked_to_scene = False
            for scene in bpy.data.scenes:
                if collection in scene.collection.children.values():
                    linked_to_scene = True
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

def manual_cc_object_check():
    """Manual check of CC objects - show info but don't auto-remove"""
    
    print("\n" + "="*80)
    print("CC OBJECT ANALYSIS (MANUAL REVIEW)")
    print("="*80)
    
    cc_objects = [obj for obj in bpy.data.objects if obj.name.startswith('CC_')]
    
    if not cc_objects:
        print("No CC objects found")
        return
    
    print(f"Found {len(cc_objects)} CC objects:")
    
    for obj in cc_objects:
        print(f"\n  Object: {obj.name}")
        print(f"    Users: {obj.users}")
        print(f"    Parent: {obj.parent.name if obj.parent else 'None'}")
        
        # Check which scenes contain it
        in_scenes = []
        for scene in bpy.data.scenes:
            if obj in scene.objects.values():
                in_scenes.append(scene.name)
        print(f"    In scenes: {in_scenes}")
        
        # Check collections
        in_collections = []
        for collection in bpy.data.collections:
            if obj in collection.objects.values():
                in_collections.append(collection.name)
        print(f"    In collections: {in_collections}")
        
        # Show recommendation
        if len(in_scenes) == 0:
            print(f"    -> POTENTIAL GHOST: Not in any scene")
        elif obj.parent and 'Rigify' in obj.parent.name:
            print(f"    -> LEGITIMATE: Parented to rig")
        else:
            print(f"    -> UNCLEAR: Manual review needed")

def main():
    """Main conservative cleanup function"""
    
    print("CONSERVATIVE GHOST DATA CLEANUP")
    print("="*80)
    print("This script only removes:")
    print("1. Unused WGT widget objects")
    print("2. Empty unlinked collections") 
    print("3. Shows CC object analysis for manual review")
    print("="*80)
    
    initial_objects = len(list(bpy.data.objects))
    initial_collections = len(list(bpy.data.collections))
    
    # Safe operations only
    wgts_removed = safe_wgt_removal()
    collections_removed = clean_empty_collections()
    
    # Manual review
    manual_cc_object_check()
    
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
    print("="*80)

class GhostBuster(bpy.types.Operator):
    """Conservative cleanup of ghost data (unused WGT objects, empty collections)"""
    bl_idname = "bst.ghost_buster"
    bl_label = "Ghost Buster"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        try:
            # Call the main ghost buster function
            main()
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
    cc_objects: bpy.props.IntProperty(default=0)
    cc_potential_ghosts: bpy.props.IntProperty(default=0)
    cc_legitimate: bpy.props.IntProperty(default=0)
    cc_unclear: bpy.props.IntProperty(default=0)
    wgt_details: bpy.props.StringProperty(default="")
    collection_details: bpy.props.StringProperty(default="")
    cc_details: bpy.props.StringProperty(default="")
    
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
                # Check if it's linked to any scene
                linked_to_scene = False
                for scene in bpy.data.scenes:
                    if collection in scene.collection.children.values():
                        linked_to_scene = True
                        break
                
                if not linked_to_scene:
                    empty_collections.append(collection)
                    collection_details_list.append(f"• {collection.name}")
        
        self.empty_collections = len(empty_collections)
        self.collection_details = "\n".join(collection_details_list[:10])  # Limit to first 10
        if len(empty_collections) > 10:
            self.collection_details += f"\n... and {len(empty_collections) - 10} more"
        
        # Analyze CC objects
        cc_objects = [obj for obj in bpy.data.objects if obj.name.startswith('CC_')]
        self.cc_objects = len(cc_objects)
        
        potential_ghosts = 0
        legitimate = 0
        unclear = 0
        cc_details_list = []
        
        for obj in cc_objects:
            # Check which scenes contain it
            in_scenes = []
            for scene in bpy.data.scenes:
                if obj in scene.objects.values():
                    in_scenes.append(scene.name)
            
            # Classify CC object
            status = ""
            if len(in_scenes) == 0:
                potential_ghosts += 1
                status = "POTENTIAL GHOST (not in any scene)"
            elif obj.parent and 'Rigify' in obj.parent.name:
                legitimate += 1
                status = "LEGITIMATE (parented to rig)"
            else:
                unclear += 1
                status = "UNCLEAR (manual review needed)"
            
            cc_details_list.append(f"• {obj.name}: {status}")
        
        self.cc_potential_ghosts = potential_ghosts
        self.cc_legitimate = legitimate
        self.cc_unclear = unclear
        self.cc_details = "\n".join(cc_details_list[:8])  # Limit to first 8
        if len(cc_objects) > 8:
            self.cc_details += f"\n... and {len(cc_objects) - 8} more"
    
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
        
        # CC Objects section
        box = layout.box()
        box.label(text="CC Objects Analysis", icon='OBJECT_DATA')
        col = box.column(align=True)
        col.label(text=f"Total CC objects: {self.cc_objects}")
        if self.cc_objects > 0:
            if self.cc_potential_ghosts > 0:
                col.label(text=f"Potential ghosts: {self.cc_potential_ghosts}", icon='ERROR')
            if self.cc_legitimate > 0:
                col.label(text=f"Legitimate objects: {self.cc_legitimate}", icon='CHECKMARK')
            if self.cc_unclear > 0:
                col.label(text=f"Need manual review: {self.cc_unclear}", icon='QUESTION')
            
            if self.cc_details:
                box.separator()
                details_col = box.column(align=True)
                for line in self.cc_details.split('\n'):
                    if line.strip():
                        details_col.label(text=line)
        else:
            col.label(text="No CC objects found", icon='CHECKMARK')
        
        # Summary
        layout.separator()
        summary_box = layout.box()
        summary_box.label(text="Summary", icon='INFO')
        total_issues = self.unused_wgt_objects + self.empty_collections + self.cc_potential_ghosts
        if total_issues > 0:
            summary_box.label(text=f"Found {total_issues} potential ghost data issues", icon='ERROR')
            summary_box.label(text="Use Ghost Buster to clean up safely")
        else:
            summary_box.label(text="No ghost data issues detected!", icon='CHECKMARK')
    
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        # Analyze the ghost data before showing the dialog
        self.analyze_ghost_data()
        return context.window_manager.invoke_popup(self, width=500)

# Note: main() is called by the operator, not automatically

# List of classes to register
classes = (
    GhostBuster,
    GhostDetector,
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