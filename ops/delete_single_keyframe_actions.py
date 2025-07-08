import bpy

class DeleteSingleKeyframeActions(bpy.types.Operator):
    """Delete actions that have no keyframes, only one keyframe, or all keyframes on the same frame"""
    bl_idname = "bst.delete_single_keyframe_actions"
    bl_label = "Delete Single Keyframe Actions"
    bl_description = "Delete actions with unwanted keyframe patterns (no keyframes, single keyframe, or all keyframes on same frame)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        actions = bpy.data.actions
        actions_to_delete = []

        for action in actions:
            keyframe_frames = set()
            total_keyframes = 0
            for fcurve in action.fcurves:
                for kf in fcurve.keyframe_points:
                    keyframe_frames.add(kf.co[0])
                    total_keyframes += 1
            
            # No keyframes
            if total_keyframes == 0:
                actions_to_delete.append(action)
            # Only one keyframe
            elif total_keyframes == 1:
                actions_to_delete.append(action)
            # All keyframes on the same frame
            elif len(keyframe_frames) == 1:
                actions_to_delete.append(action)

        deleted_count = 0
        for action in actions_to_delete:
            print(f"Deleting action '{action.name}' (unwanted keyframe pattern)")
            bpy.data.actions.remove(action)
            deleted_count += 1
        
        self.report({'INFO'}, f"Deleted {deleted_count} unwanted actions")
        return {'FINISHED'} 