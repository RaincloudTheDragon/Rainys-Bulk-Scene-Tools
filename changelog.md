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