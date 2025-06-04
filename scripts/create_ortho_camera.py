import bpy
from bpy.types import Operator

class CreateOrthoCamera(Operator):
    """Create an orthographic camera with predefined settings"""
    bl_idname = "bst.create_ortho_camera"
    bl_label = "Create Ortho Camera"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Create a new camera
        bpy.ops.object.camera_add()
        camera = context.active_object
        
        # Set camera to orthographic
        camera.data.type = 'ORTHO'
        camera.data.ortho_scale = 1.8  # Set orthographic scale
        
        # Set camera position
        camera.location = (0, -2, 1)  # x=0, y=-2m, z=1m
        
        # Set camera rotation (90 degrees around X axis)
        camera.rotation_euler = (1.5708, 0, 0)  # 90 degrees in radians
        
        # Get or create camera collection
        camera_collection = bpy.data.collections.get("Camera")
        if not camera_collection:
            camera_collection = bpy.data.collections.new("Camera")
            context.scene.collection.children.link(camera_collection)
        
        # Move camera to camera collection
        # First unlink from current collection
        for collection in camera.users_collection:
            collection.objects.unlink(camera)
        # Then link to camera collection
        camera_collection.objects.link(camera)
        
        return {'FINISHED'}

def register():
    bpy.utils.register_class(CreateOrthoCamera)

def unregister():
    bpy.utils.unregister_class(CreateOrthoCamera)

if __name__ == "__main__":
    register()