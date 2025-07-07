# v 0.7.1

## Ghost Buster Enhancements

### Added
- **Low Priority Ghost Detection**: New option to delete objects not in scenes with no legitimate use and users < 2
- **Smart Instance Collection Detection**: Ghost Buster now properly detects when objects are used by instance collections in scenes
- **Enhanced Legitimacy Checks**: Improved detection of objects with valid uses outside scenes (constraints, modifiers, particle systems only count if the using object is in a scene)

### Improved
- **More Accurate Ghost Detection**: Eliminated false positives by checking if instance collection targets are actually being used by scene objects
- **Better Classification**: Objects are now classified as "Legitimate", "Ghosts (users >= 2)", or "Low Priority (users < 2)" with clearer reasoning
- Cleaned UI

### Technical Changes
- Added `is_object_used_by_scene_instance_collections()` function for precise instance collection detection
- Enhanced `is_object_legitimate_outside_scene()` with scene-aware checks for modifiers, constraints, and particle systems
- Updated ghost analysis and removal logic to use more precise categorization
- Added scene property `ghost_buster_delete_low_priority` for user preference storage

# v 0.7.0

## New: Ghost Detection System
- **Universal Object Analysis**: Expanded ghost detection from CC-objects only to all object types (meshes, empties, curves, etc.)
- **Enhanced Safety Framework**: Added comprehensive protection for legitimate objects outside scenes:
  - WGT rig widgets (`WGT-*` objects)
  - Modifier targets (curve modifiers, constraints)
  - Constraint targets and references
  - Particle system objects
  - Collection instance objects (linked collection references)
- **Smart Classification**: Objects not in scenes now categorized as:
  - `LEGITIMATE`: Has valid use outside scenes (protected)
  - `LOW PRIORITY`: Only collection reference (preserved)
  - `GHOST`: Multiple users but not in scenes (removed)
- **Conservative Cleanup Logic**: Only removes objects with 2+ users that have no legitimate purpose
- **Updated UI**: Ghost Detector popup now shows "Ghost Objects Analysis" with enhanced categorization and object type details
- **Improved Safety**: All linked/library content automatically protected from ghost detection

# v 0.6.1

## Bug Fixes
- **Fixed flat color detection**: Redesigned algorithm with exact pixel matching and smart sampling
- **Fixed AutoMat Extractor**: Now properly organizes images by material instead of dumping everything to common folder
- **Fixed viewport color setting**: Resolved context restriction errors with deferred color application
- **Fixed timer performance**: Reduced timer frequency and improved cancellation reliability
- **Enhanced debugging**: Added comprehensive console reporting for all bulk operations

## Improvements
- Better performance with optimized sampling
- More reliable cancellation system
- Context-safe operations that don't interfere with Blender's drawing state

# v 0.6.0

- **Enhancement: Progress Reporting & Cancellation**
  - Some of the PathMan's operators are pretty resource-intense. Due to Python's GIL, I haven't been able to figure out how to run some of these more efficiently. Without the console window, you're flying blind, so I've integrated a loading bar with progress reporting for the following operators:
    - Flat Color Texture Renamer
    - Remove Extensions
    - Save All to image Paths
    - Remap Selected
    - Rename by Material
    - AutoMat Extractor

# v 0.5.1

- **Enhanced AutoMat Extractor:**
  - Added a crucial safety check to prevent textures from overwriting each other if they resolve to the same filename (e.g., `Image.001.png` and `Image.002.png` both becoming `Image.png`).
  - The operator now correctly sanitizes names with numerical suffixes before saving.
  - A new summary dialog now appears after the operation, reporting how many files were extracted successfully and listing any files that were skipped due to naming conflicts.
  - Added a user preference to control the location of the `common` folder, allowing it to be placed either inside or outside the blend file's specific texture folder. A checkbox for this setting was added to the UI.
- **Improved Suffix Handling:**
  - The "Rename by Material" tool now correctly preserves spaces in packed texture names (e.g., `Flow Pack` instead of `FlowPack`).
  - Added support for underscore-separated packed texture names (e.g., `flow_pack`).
- **Bug Fixes:**
  - Resolved multiple `AttributeError` and `TypeError` exceptions that occurred due to incorrect addon name lookups and invalid icon names, making the UI and addon registration more robust.

# v 0.5.0

- **Integrated Scene General: Free GPU VRAM**
- **Integrated PathMan: Automatic Material Extractor**
- **Integrated PathMan: Rename Image Textures by Material**: Added comprehensive texture suffix recognition
  - Recognizes many Character Creator suffixes
  - Recognizes most standard material suffixes
  - Images with unrecognized suffixes are skipped instead of renamed, preventing unintended modifications
  - Enhanced logging: Unrecognized suffix images are listed separately for easy identification
- **UI Improvements**:
  - Rearranged workflow layout: Make Paths Relative/Absolute moved to main workflow section
  - Remap Selected moved under path preview for better workflow progression
  - Rename by Material and AutoMat Extractor repositioned after Remap Selected
  - Added Autopack toggle at beginning of workflow sections (both Node Editor and 3D Viewport)
  - Consolidated draw functions: Node Editor panel now serves as master template for both panels

# v 0.4.1

- Fixed traceback error causing remap to fail to draw buttons

# v 0.4.0

Overhaul! Added new Scene General panel, major enhancements to all panels and functions.

# v0.3.0

- Added image path remapping for unpacked images, keeping them organized.