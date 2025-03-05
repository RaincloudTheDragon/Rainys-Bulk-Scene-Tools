# Set Viewport Colors from BSDF

A basic Blender addon that automatically sets viewport display colors based on material node settings.

## Description

Simply sets viewport material colors with the actual material settings in your node setup. It works by:

1. Reading the base color from Principled BSDF nodes
2. If a texture is connected to the Base Color input, it calculates the average color of that texture
3. Sets the viewport display color to match, making your viewport representation more accurate

Useful for setting material viewport colors in bulk.

## Features

- Automatically detects Principled BSDF nodes and extracts base colors
- Calculates average colors from connected texture nodes
- Works with all materials in your scene with a single click
- Supports both solid color inputs and texture-based materials
- Integrates seamlessly into the Material Properties panel

## Version support

Blender 4.3.2

## Installation

1. Download the addon (zip file)
2. In Blender, go to Edit > Preferences > Add-ons
3. Click "Install..." and select the downloaded zip file
4. Enable the addon by checking the box next to "Material: Set Viewport Colors from BSDF"

## Usage

1. Open scene
2. Go to Properties > Material > Set Viewport Colors
3. Click the "Set Viewport Colors" button
4. All materials in your scene will have their viewport colors updated to match their node setups

## How It Works

The addon traverses the node tree of each material looking for Principled BSDF nodes. If found, it extracts the Base Color value. If a texture is connected to the Base Color input, it calculates the average color of that texture and uses it instead.

For non-Principled BSDF materials, it looks for inputs named "Diffuse Color" as a fallback.

## Author

- **RaincloudTheDragon**

## Version

0.0.1
