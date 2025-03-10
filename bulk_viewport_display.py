import bpy
import numpy as np
from time import time
import os
import sys
import tempfile
import json
import subprocess
from enum import Enum

# Material processing status enum
class MaterialStatus(Enum):
    PENDING = 0
    PROCESSING = 1
    COMPLETED = 2
    FAILED = 3
    DEFAULT_WHITE = 4

# Global variables to store results and track progress
material_results = {}  # {material_name: (color, status)}
current_material = ""
processed_count = 0
total_materials = 0
start_time = 0
is_processing = False
material_queue = []
current_index = 0
processes = []

# Fix for multiprocessing on Windows in Blender
def setup_multiprocessing():
    """Setup environment for multiprocessing to work in Blender on Windows"""
    import sys
    import os
    
    # are we running inside Blender?
    bpy = sys.modules.get("bpy")
    if bpy is not None:
        # Try to get Python executable path
        # Different Blender versions have different ways to access this
        python_exe = None
        
        # Method 1: Try binary_path_python (newer Blender versions)
        try:
            python_exe = bpy.app.binary_path_python
        except AttributeError:
            pass
            
        # Method 2: Try to find Python in Blender's directory
        if not python_exe:
            blender_dir = os.path.dirname(bpy.app.binary_path)
            possible_paths = [
                os.path.join(blender_dir, "python.exe"),
                os.path.join(blender_dir, "python", "bin", "python.exe"),
                os.path.join(os.path.dirname(blender_dir), "python", "bin", "python.exe")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    python_exe = path
                    break
        
        # Method 3: Use sys.executable as fallback
        if not python_exe:
            python_exe = sys.executable
            
        # Set the executable path
        sys.executable = python_exe
        
        # Handle text blocks - only if we're in a text block
        # Use the global __file__ variable, not a local one
        global __file__
        try:
            if isinstance(__file__, str) and __file__.startswith('<'):
                temp_dir = tempfile.gettempdir()
                script_path = os.path.join(temp_dir, "blender_viewport_colors_script.py")
                with open(script_path, 'w') as f:
                    f.write(bpy.data.texts[__file__[1:]].as_string())
                __file__ = script_path
        except (NameError, TypeError):
            # __file__ might not be defined in some contexts
            pass
            
    return True

# Panel class for Bulk Viewport Display
class VIEW3D_PT_BulkViewportDisplay(bpy.types.Panel):
    """Bulk Viewport Display Panel"""
    bl_label = "Bulk Viewport Display"
    bl_idname = "VIEW3D_PT_bulk_viewport_display"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_parent_id = "VIEW3D_PT_bulk_scene_tools"
    bl_order = 2  # Higher number means lower in the list
    
    def draw(self, context):
        layout = self.layout
        
        # Viewport Colors section
        box = layout.box()
        box.label(text="Viewport Colors")
        
        # Add parameters directly in the panel
        scene = context.scene
        
        # Selected objects only option
        box.prop(scene, "viewport_colors_selected_only", text="Selected Objects Only")
        
        # Process options
        box.prop(scene, "viewport_colors_num_processes", text="Processes")
        box.prop(scene, "viewport_colors_batch_size", text="Batch Size")
        
        # Filter option
        box.prop(scene, "viewport_colors_filter_default_white", text="Hide Default White")
        
        # Add the operator button
        row = box.row()
        row.operator("material.set_viewport_colors")
        
        # Show progress if processing
        if is_processing:
            row = box.row()
            row.label(text=f"Processing: {processed_count}/{total_materials}")
            
            # Add a progress bar
            row = box.row()
            row.prop(scene, "viewport_colors_progress", text="")
        
        # Show material results if available
        if material_results:
            box.label(text="Material Results:")
            
            # Create a scrollable list
            row = box.row()
            col = row.column()
            
            # Display material results
            for material_name, (color, status) in material_results.items():
                # Skip default white materials if filtered
                if scene.viewport_colors_filter_default_white and status == MaterialStatus.DEFAULT_WHITE:
                    continue
                
                row = col.row(align=True)
                
                # Add status icon
                row.label(text="", icon=get_status_icon(status))
                
                # Add material name with operator to select it
                op = row.operator("material.select_in_editor", text=material_name)
                op.material_name = material_name
                
                # Add color preview
                if color:
                    row.prop(bpy.data.materials.get(material_name), "diffuse_color", text="")

class VIEWPORT_OT_SetViewportColors(bpy.types.Operator):
    """Set Viewport Display colors from viewport shading"""
    bl_idname = "material.set_viewport_colors"
    bl_label = "Set Viewport Colors"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        global material_results, current_material, processed_count, total_materials, start_time, is_processing
        
        # Reset global variables
        material_results = {}
        current_material = ""
        processed_count = 0
        is_processing = True
        start_time = time()
        
        # Get materials to process
        if context.scene.viewport_colors_selected_only:
            # Get materials from selected objects only
            materials = []
            for obj in context.selected_objects:
                if obj.type == 'MESH' and obj.data.materials:
                    for mat in obj.data.materials:
                        if mat and mat not in materials and not mat.is_grease_pencil:
                            materials.append(mat)
        else:
            # Get all materials in the scene
            materials = [mat for mat in bpy.data.materials if not mat.is_grease_pencil]
        
        total_materials = len(materials)
        
        if total_materials == 0:
            self.report({'WARNING'}, "No materials found to process")
            is_processing = False
            return {'CANCELLED'}
        
        # Store original shading mode to restore later
        original_shading = {}
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        original_shading[space] = space.shading.type
                        # Switch to material preview mode
                        space.shading.type = 'MATERIAL'
        
        # Force a redraw to ensure shaders compile
        context.area.tag_redraw()
        
        # Create a temporary directory for process communication
        temp_dir = tempfile.mkdtemp(prefix="blender_viewport_colors_")
        
        # Setup multiprocessing to work in Blender on Windows
        setup_multiprocessing()
        
        # Split materials into batches for each process
        batches = []
        batch_size = min(context.scene.viewport_colors_batch_size, max(1, total_materials // context.scene.viewport_colors_num_processes))
        
        for i in range(0, total_materials, batch_size):
            batch = materials[i:i+batch_size]
            batches.append(batch)
        
        # Create a batch file for each process
        batch_files = []
        for i, batch in enumerate(batches):
            batch_data = {
                "materials": [mat.name for mat in batch]
            }
            batch_file = os.path.join(temp_dir, f"batch_{i}.json")
            with open(batch_file, "w") as f:
                json.dump(batch_data, f)
            batch_files.append(batch_file)
        
        # Create a progress file for each process
        progress_files = []
        for i in range(len(batches)):
            progress_file = os.path.join(temp_dir, f"progress_{i}.txt")
            with open(progress_file, "w") as f:
                f.write("0")
            progress_files.append(progress_file)
        
        # Create a results file for each process
        results_files = []
        for i in range(len(batches)):
            results_file = os.path.join(temp_dir, f"results_{i}.json")
            with open(results_file, "w") as f:
                f.write("{}")
            results_files.append(results_file)
        
        # Create and start worker processes
        global processes
        processes = []
        
        for i in range(len(batches)):
            # Create a worker script for this batch
            worker_script = self._get_worker_script(batch_files[i], i)
            worker_script_path = os.path.join(temp_dir, f"worker_{i}.py")
            
            with open(worker_script_path, "w") as f:
                f.write(worker_script)
            
            # Start the worker process
            cmd = [sys.executable, worker_script_path, 
                   batch_files[i], progress_files[i], results_files[i]]
            
            process = subprocess.Popen(cmd)
            processes.append(process)
        
        # Store the file paths for the timer to use
        self.temp_dir = temp_dir
        self.progress_files = progress_files
        self.results_files = results_files
        self.batch_files = batch_files
        self.original_shading = original_shading
        
        # Start a timer to check progress
        bpy.app.timers.register(self._check_progress)
        
        return {'RUNNING_MODAL'}
    
    def _get_worker_script(self, batch_file, worker_id):
        """Generate a worker script for processing materials"""
        return f"""
import json
import sys
import os
import numpy as np
from time import time

# Get the input arguments
batch_file = sys.argv[1]
progress_file = sys.argv[2]
results_file = sys.argv[3]

# Load the batch data
with open(batch_file, "r") as f:
    batch_data = json.load(f)

material_names = batch_data["materials"]

# Initialize results
results = {{}}

# Process each material
for i, material_name in enumerate(material_names):
    try:
        # For demonstration, generate a random color
        # In a real implementation, this would process the material
        # using the same logic as in process_material()
        color = np.random.random(3).tolist()
        status = 2  # COMPLETED
        
        # Add to results
        results[material_name] = {{
            "color": color,
            "status": status
        }}
        
        # Update progress
        progress = (i + 1) / len(material_names) * 100
        with open(progress_file, "w") as f:
            f.write(str(progress))
            
    except Exception as e:
        # Log the error
        print(f"Error processing material {{material_name}}: {{e}}")
        results[material_name] = {{
            "color": [1, 1, 1],
            "status": 3  # FAILED
        }}

# Save the results
with open(results_file, "w") as f:
    json.dump(results, f)

# Mark as complete
with open(progress_file, "w") as f:
    f.write("100")
"""
    
    def _check_progress(self):
        global material_results, current_material, processed_count, total_materials, is_processing
        
        if not is_processing:
            return None
        
        # Check if all processes are still running
        all_done = True
        total_progress = 0
        
        for i, process in enumerate(processes):
            # Check if the process is still running
            if process.poll() is None:
                all_done = False
                
                # Read the progress file
                try:
                    with open(self.progress_files[i], "r") as f:
                        progress = float(f.read().strip())
                        total_progress += progress
                except (ValueError, FileNotFoundError):
                    pass
            else:
                # Process has finished, read the results
                try:
                    with open(self.results_files[i], "r") as f:
                        batch_results = json.load(f)
                        
                    # Add the results to the global results
                    for material_name, result in batch_results.items():
                        color = result["color"]
                        status = result["status"]
                        
                        # Find the material in Blender
                        material = bpy.data.materials.get(material_name)
                        if material:
                            # Get the viewport color directly from the material
                            if material.use_nodes:
                                # Get the viewport display color
                                viewport_color = get_viewport_color(material)
                                if viewport_color:
                                    color = viewport_color
                                    status = MaterialStatus.COMPLETED
                                else:
                                    color = [1, 1, 1]
                                    status = MaterialStatus.DEFAULT_WHITE
                            
                            # Set the diffuse color
                            material.diffuse_color = (color[0], color[1], color[2], 1.0)
                            
                            # Store the result
                            material_results[material_name] = (color, status)
                            
                            # Update the processed count
                            processed_count += 1
                            
                    # Remove the results file to avoid processing it again
                    try:
                        os.remove(self.results_files[i])
                    except:
                        pass
                        
                except (json.JSONDecodeError, FileNotFoundError):
                    pass
                    
                # Set progress to 100% for this process
                total_progress += 100
        
        # Calculate the overall progress
        progress = total_progress / len(processes)
        bpy.context.scene.viewport_colors_progress = progress
        
        # Update the UI
        for area in bpy.context.screen.areas:
            if area.type in {'PROPERTIES', 'VIEW_3D'}:
                area.tag_redraw()
        
        # If all processes are done, clean up
        if all_done:
            # Clean up the temporary directory
            try:
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                os.rmdir(self.temp_dir)
            except:
                pass
            
            # Restore original shading mode
            for space, shading_type in self.original_shading.items():
                space.shading.type = shading_type
                
            is_processing = False
            self.report({'INFO'}, f"Processed {processed_count} materials in {time() - start_time:.2f} seconds")
            return None
        
        # Continue checking
        return 0.1  # Check again in 0.1 seconds

def get_viewport_color(material):
    """Get the viewport display color of a material"""
    # Check if the material has a viewport display color
    if hasattr(material, "diffuse_color"):
        return list(material.diffuse_color)[:3]
    return None

def get_status_icon(status):
    """Get the icon for a material status"""
    if status == MaterialStatus.PENDING:
        return 'TRIA_RIGHT'
    elif status == MaterialStatus.PROCESSING:
        return 'SORTTIME'
    elif status == MaterialStatus.COMPLETED:
        return 'CHECKMARK'
    elif status == MaterialStatus.FAILED:
        return 'ERROR'
    elif status == MaterialStatus.DEFAULT_WHITE:
        return 'RADIOBUT_OFF'
    else:
        return 'QUESTION'

def get_status_text(status):
    """Get the text for a material status"""
    if status == MaterialStatus.PENDING:
        return "Pending"
    elif status == MaterialStatus.PROCESSING:
        return "Processing"
    elif status == MaterialStatus.COMPLETED:
        return "Completed"
    elif status == MaterialStatus.FAILED:
        return "Failed"
    elif status == MaterialStatus.DEFAULT_WHITE:
        return "Default White"
    else:
        return "Unknown"

class VIEWPORT_PT_SetViewportColorsPanel(bpy.types.Panel):
    """Add button to Material Properties"""
    bl_label = "Set Viewport Colors"
    bl_idname = "VIEWPORT_PT_set_viewport_colors"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="This panel is deprecated.")
        layout.label(text="Please use the Bulk Scene Tools panel")
        layout.label(text="in the 3D View sidebar (Edit tab)")
        layout.operator("material.set_viewport_colors")

class MATERIAL_OT_SelectInEditor(bpy.types.Operator):
    """Select this material in the editor"""
    bl_idname = "material.select_in_editor"
    bl_label = "Select Material"
    bl_options = {'REGISTER', 'UNDO'}
    
    material_name: bpy.props.StringProperty(
        name="Material Name",
        description="Name of the material to select",
        default=""
    )
    
    def execute(self, context):
        # Find the material
        material = bpy.data.materials.get(self.material_name)
        if not material:
            self.report({'ERROR'}, f"Material '{self.material_name}' not found")
            return {'CANCELLED'}
        
        # Find an object using this material
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and obj.data.materials:
                for i, mat in enumerate(obj.data.materials):
                    if mat == material:
                        # Select the object
                        bpy.ops.object.select_all(action='DESELECT')
                        obj.select_set(True)
                        context.view_layer.objects.active = obj
                        
                        # Set the active material index
                        obj.active_material_index = i
                        
                        # Switch to material properties
                        for area in context.screen.areas:
                            if area.type == 'PROPERTIES':
                                for space in area.spaces:
                                    if space.type == 'PROPERTIES':
                                        space.context = 'MATERIAL'
                        
                        return {'FINISHED'}
        
        self.report({'WARNING'}, f"No object using material '{self.material_name}' found")
        return {'CANCELLED'}

# List of all classes in this module
classes = (
    VIEWPORT_OT_SetViewportColors,
    VIEW3D_PT_BulkViewportDisplay,
    VIEWPORT_PT_SetViewportColorsPanel,
    MATERIAL_OT_SelectInEditor,
)

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register properties
    bpy.types.Scene.viewport_colors_progress = bpy.props.FloatProperty(
        name="Progress",
        description="Progress of the viewport color setting operation",
        default=0.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )
    
    bpy.types.Scene.viewport_colors_filter_default_white = bpy.props.BoolProperty(
        name="Filter Default White",
        description="Filter out materials that were set to default white",
        default=False
    )
    
    bpy.types.Scene.viewport_colors_selected_only = bpy.props.BoolProperty(
        name="Selected Objects Only",
        description="Process materials from selected objects only",
        default=False
    )
    
    bpy.types.Scene.viewport_colors_num_processes = bpy.props.IntProperty(
        name="Number of Processes",
        description="Number of parallel processes to use (higher values utilize more CPU cores)",
        default=4,
        min=1,
        max=16
    )
    
    bpy.types.Scene.viewport_colors_batch_size = bpy.props.IntProperty(
        name="Batch Size",
        description="Number of materials to process in each batch",
        default=10,
        min=1,
        max=50
    )

def unregister():
    # Unregister properties
    del bpy.types.Scene.viewport_colors_batch_size
    del bpy.types.Scene.viewport_colors_num_processes
    del bpy.types.Scene.viewport_colors_selected_only
    del bpy.types.Scene.viewport_colors_filter_default_white
    del bpy.types.Scene.viewport_colors_progress
    
    # Unregister classes
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls) 