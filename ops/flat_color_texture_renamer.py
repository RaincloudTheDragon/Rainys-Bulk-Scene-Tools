import bpy
import bmesh
from mathutils import Color

def rgb_to_hex(r, g, b, a=1.0):
    """Convert RGBA values (0-1 range) to hex color code."""
    # Convert to 0-255 range and format as hex
    r_int = int(round(r * 255))
    g_int = int(round(g * 255))
    b_int = int(round(b * 255))
    a_int = int(round(a * 255))
    
    # If alpha is full (255), use RGB format, otherwise use RGBA
    if a_int == 255:
        return f"#{r_int:02X}{g_int:02X}{b_int:02X}"
    else:
        return f"#{r_int:02X}{g_int:02X}{b_int:02X}{a_int:02X}"

def is_flat_color_image(image):
    """Check if an image has all pixels of the same color."""
    if not image or not image.pixels:
        return False, None
    
    # Get pixel data
    pixels = image.pixels[:]
    
    if len(pixels) == 0:
        return False, None
    
    # Images in Blender are typically RGBA, so 4 values per pixel
    channels = image.channels
    if channels not in [3, 4]:  # RGB or RGBA
        return False, None
    
    # Get the first pixel color
    first_pixel = pixels[:channels]
    
    # Check if all pixels have the same color
    for i in range(0, len(pixels), channels):
        current_pixel = pixels[i:i+channels]
        
        # Compare with first pixel (with small tolerance for floating point precision)
        tolerance = 1e-6
        for j in range(channels):
            if abs(current_pixel[j] - first_pixel[j]) > tolerance:
                return False, None
    
    # If we get here, all pixels are the same color
    if channels == 3:
        return True, (first_pixel[0], first_pixel[1], first_pixel[2], 1.0)
    else:
        return True, tuple(first_pixel)

def safe_rename_image(image, new_name):
    """Safely rename an image datablock using context override."""
    try:
        # Method 1: Try direct assignment first (works in some contexts)
        image.name = new_name
        return True
    except:
        try:
            # Method 2: Use context override with outliner
            for area in bpy.context.screen.areas:
                if area.type == 'OUTLINER':
                    with bpy.context.temp_override(area=area):
                        image.name = new_name
                    return True
        except:
            try:
                # Method 3: Use bpy.ops with context override
                # Set the image as active and use the rename operator
                bpy.context.view_layer.objects.active = None
                
                # Create a temporary override context
                override_context = bpy.context.copy()
                override_context['edit_image'] = image
                
                with bpy.context.temp_override(**override_context):
                    image.name = new_name
                return True
            except:
                # Method 4: Try using the data API directly with update
                try:
                    old_name = image.name
                    # Force an update cycle
                    bpy.context.view_layer.update()
                    image.name = new_name
                    bpy.context.view_layer.update()
                    return True
                except:
                    return False

def rename_flat_color_textures():
    """Main function to find and rename flat color textures."""
    renamed_count = 0
    failed_count = 0
    processed_count = 0
    
    print("Scanning for flat color textures...")
    
    # Store rename operations to perform them in batch
    rename_operations = []
    
    for image in bpy.data.images:
        processed_count += 1
        
        # Skip if image has no pixel data
        if not hasattr(image, 'pixels') or len(image.pixels) == 0:
            print(f"Skipping '{image.name}': No pixel data available")
            continue
        
        # Check if image has flat color
        is_flat, color = is_flat_color_image(image)
        
        if is_flat and color:
            # Convert color to hex
            hex_color = rgb_to_hex(*color)
            
            # Store original name for logging
            original_name = image.name
            
            # Check if name is already a hex color (to avoid renaming again)
            if not original_name.startswith('#'):
                rename_operations.append((image, original_name, hex_color, color))
            else:
                print(f"Skipping '{original_name}': Already appears to be hex-named")
        else:
            print(f"'{image.name}': Not a flat color texture")
    
    # Perform rename operations
    print(f"\nPerforming {len(rename_operations)} rename operation(s)...")
    
    for image, original_name, hex_color, color in rename_operations:
        success = safe_rename_image(image, hex_color)
        if success:
            print(f"Renamed '{original_name}' to '{hex_color}' (Color: RGBA{color})")
            renamed_count += 1
        else:
            print(f"Failed to rename '{original_name}' to '{hex_color}' - Context restriction")
            failed_count += 1
    
    print(f"\nSummary:")
    print(f"Processed: {processed_count} images")
    print(f"Successfully renamed: {renamed_count} flat color textures")
    if failed_count > 0:
        print(f"Failed to rename: {failed_count} textures (try running from Python Console instead)")
    
    return renamed_count

def reload_image_pixels():
    """Reload pixel data for all images (useful if images aren't loaded)."""
    print("Reloading pixel data for all images...")
    
    for image in bpy.data.images:
        if image.source == 'FILE' and image.filepath:
            try:
                image.reload()
                print(f"Reloaded: {image.name}")
            except:
                print(f"Failed to reload: {image.name}")

# Alternative function for running in restricted contexts
def print_rename_suggestions():
    """Print suggested renames without actually renaming (for restricted contexts)."""
    suggestions = []
    
    print("Scanning for flat color textures (suggestion mode)...")
    
    for image in bpy.data.images:
        if not hasattr(image, 'pixels') or len(image.pixels) == 0:
            continue
        
        is_flat, color = is_flat_color_image(image)
        
        if is_flat and color and not image.name.startswith('#'):
            hex_color = rgb_to_hex(*color)
            suggestions.append((image.name, hex_color, color))
    
    if suggestions:
        print(f"\nFound {len(suggestions)} flat color texture(s) that could be renamed:")
        print("-" * 60)
        for original_name, hex_color, color in suggestions:
            print(f"'{original_name}' -> '{hex_color}' (RGBA{color})")
        
        print("\nTo actually rename them, run this script from:")
        print("1. Blender's Python Console, or")
        print("2. Command line with: blender file.blend --python script.py")
    else:
        print("\nNo flat color textures found that need renaming.")

# Main execution
if __name__ == "__main__":
    print("=" * 50)
    print("Flat Color Texture Renamer")
    print("=" * 50)
    
    # Optional: Reload images to ensure pixel data is available
    # Uncomment the line below if you want to force reload all images
    # reload_image_pixels()
    
    # Try to run the renaming process
    try:
        renamed_count = rename_flat_color_textures()
        
        if renamed_count > 0:
            print(f"\nSuccessfully renamed {renamed_count} flat color texture(s)!")
        else:
            print("\nNo flat color textures found to rename.")
    except Exception as e:
        print(f"\nContext restriction detected. Running in suggestion mode...")
        print_rename_suggestions()
    
    print("Script completed.") 