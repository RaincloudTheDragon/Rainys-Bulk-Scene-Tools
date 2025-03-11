# Raincloud's Bulk Scene Tools

A couple Blender tools to help me automate some tedious tasks in scene optimization.

## Features

- Bulk Data Remap
- Bulk Viewport Display

## Requirements

Blender 4.3.2

## Installation

1. Download the addon (zip file)
2. In Blender, go to Edit > Preferences > Add-ons
3. Click "Install..." and select the downloaded zip file, or click and drag if it allows.
4. Ensure addon is enabled.

## Usage

1. Open blender file/scene to optimize
2. Open side panel > Edit tab > Bulk Scene Tools
3. Data remapper: Select data types to remap. Currently supports Images, Materials, and Fonts. Select to exclude data type from remapping.
4. View amount of duplicates and use the dropdown menus to select which duplicate groups to exclude from remapping.
5. Remap. This action is undo-able!
6. If remapping has successfully remapped to your liking, Purge Unused Data so that the Viewport Display function has less materials to calculate, unless you are applying it only to selected objects.
7. Recommend activating Solid viewport shading mode so you can see what the Material Viewport function is doing. Change color from Material to Texture if you prefer; the function should find the diffuse texture if one exists.
8. Apply material calculation to selected objects if preferred.
9. Manually set display color for objects that couldn't be calculated, or weren't calculated to your preference.

## Author

- **RaincloudTheDragon**