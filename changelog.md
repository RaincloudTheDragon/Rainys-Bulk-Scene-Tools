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