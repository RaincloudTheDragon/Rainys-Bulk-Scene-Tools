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

# Run conservative cleanup
main() 