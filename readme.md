# Set Viewport Colors from BSDF

A Blender addon that automatically sets viewport display colors based on material and material node settings.

## Description

Simply sets viewport material colors with the actual material settings in your node setup. It works by:

1. Calculating the final color by analyzing the node tree from the output node
2. Properly handling color mixing operations (like Mix RGB and Multiply nodes)
3. If a texture is used, calculating the average color of that texture as a fallback

This ensures your viewport shading better represents the final render appearance.

## Features

- ""Intelligently"" calculates final colors by analyzing the entire node tree
- Handles Mix RGB nodes with proper color mixing calculations
- Supports Principled BSDF and other shader types
- Works with all materials in your scene with a single click
- Integrates seamlessly into the Material Properties panel

## Requirements

Blender 4.3.2

## Installation

1. Download the addon (zip file)
2. In Blender, go to Edit > Preferences > Add-ons
3. Click "Install..." and select the downloaded zip file
4. Enable the addon by checking the box next to "Material: Set Viewport Colors from BSDF"

## Usage

1. Select any object with materials
2. Go to Properties > Material > Set Viewport Colors
3. Click the "Set Viewport Colors" button
4. All materials in your scene will have their viewport colors updated to match their node setups

## Author

- **RaincloudTheDragon**