import bpy


class RemoveActionFakeUsers(bpy.types.Operator):
    """Remove fake users from all actions so only used animations are kept on save"""
    bl_idname = "bst.remove_action_fake_users"
    bl_label = "Remove Action FU"
    bl_description = "Remove fake users from all actions so only used animations are kept"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        actions = bpy.data.actions
        cleared_count = 0

        for action in actions:
            if getattr(action, "library", None) is not None:
                continue
            if action.use_fake_user:
                action.use_fake_user = False
                cleared_count += 1
                print(f"Removed fake user from action '{action.name}'")

        self.report({'INFO'}, f"Removed fake users from {cleared_count} actions")
        return {'FINISHED'}
