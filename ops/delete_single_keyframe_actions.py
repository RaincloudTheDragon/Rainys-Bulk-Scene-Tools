import bpy

def delete_unwanted_actions():
    """
    Delete actions that:
    - Have no keyframes
    - Have only one keyframe (total)
    - Have all keyframes on the same frame
    """
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
    print(f"Deleted {deleted_count} unwanted actions.")
    return deleted_count

if __name__ == "__main__":
    delete_unwanted_actions() 