import bpy


class WhiteWorld(bpy.types.Operator):
    """Create a pure-white world and set it active; remove 'Dual Node Background' if present, enable transparent film"""
    bl_idname = "bst.white_world"
    bl_label = "White World"
    bl_description = "Create white background world, set film transparent, purge orphans"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if "Dual Node Background" in bpy.data.worlds:
            w = bpy.data.worlds["Dual Node Background"]
            bpy.data.worlds.remove(w, do_unlink=True)
        new_world = bpy.data.worlds.new(name="World")
        new_world.use_nodes = True
        nodes = new_world.node_tree.nodes
        links = new_world.node_tree.links
        nodes.clear()
        bg = nodes.new(type="ShaderNodeBackground")
        bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        out = nodes.new(type="ShaderNodeOutputWorld")
        links.new(bg.outputs[0], out.inputs[0])
        context.scene.world = new_world
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        context.scene.render.film_transparent = True
        self.report({'INFO'}, "White world set, film transparent, orphans purged")
        return {'FINISHED'}
