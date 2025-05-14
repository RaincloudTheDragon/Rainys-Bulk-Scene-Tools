"""
Updater module for Rainy's Bulk Scene Tools
"""

import bpy
import os
import sys
from .. import bl_info

# Import the addon updater
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from addon_updater import Updater as updater

def configure_updater():
    """Configure updater settings for this addon"""
    updater.addon = __package__.split('.')[0]  # Main package name
    updater.user = "RaincloudTheDragon"
    updater.repo = "Rainys-Bulk-Scene-Tools"
    updater.website = "https://github.com/RaincloudTheDragon/Rainys-Bulk-Scene-Tools"
    updater.current_version = bl_info["version"]
    
    # Configure auto-check
    updater.set_check_interval(enabled=True, 
                               months=0, 
                               days=0,
                               hours=24, 
                               minutes=0)
    
    # File handling during updates
    updater.overwrite_patterns = ["*.py", "*.md"]
    updater.remove_pre_update_patterns = ["*.py", "*.md"]
    
    # Use GitHub releases
    updater.include_branches = False
    updater.use_releases = True
    
    # Auto reload after update
    updater.auto_reload_post_update = True

    return updater

def get_user_preferences(context=None):
    """Get addon preferences"""
    if not context:
        context = bpy.context
    addon_prefs = None
    if hasattr(context, "preferences") and __package__.split('.')[0] in context.preferences.addons:
        addon_prefs = context.preferences.addons[__package__.split('.')[0]].preferences
    return addon_prefs 