import bpy

class RBST_FreeGPU(bpy.types.Operator):
    bl_idname = "bst.free_gpu"
    bl_label = "Free VRAM"
    bl_description = "Unallocate all material images from VRAM"

    def execute(self, context):
        for mat in bpy.data.materials:
            if mat.use_nodes:
                for node in mat.node_tree.nodes:
                    if hasattr(node, 'image') and node.image:
                        node.image.gl_free()
        return {"FINISHED"}