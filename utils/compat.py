"""
This module provides API compatibility functions for handling differences
between Blender 4.2, 4.4, 4.5, and 5.0.

"""

import bpy
from bpy.utils import register_class, unregister_class
from . import version


def safe_register_class(cls):
    """
    Safely register a class, handling any version-specific registration issues.
    
    Args:
        cls: The class to register
    
    Returns:
        bool: True if registration succeeded, False otherwise
    """
    try:
        register_class(cls)
        return True
    except Exception as e:
        print(f"Warning: Failed to register {cls.__name__}: {e}")
        return False


def safe_unregister_class(cls):
    """
    Safely unregister a class, handling any version-specific unregistration issues.
    
    Args:
        cls: The class to unregister
    
    Returns:
        bool: True if unregistration succeeded, False otherwise
    """
    try:
        unregister_class(cls)
        return True
    except Exception as e:
        print(f"Warning: Failed to unregister {cls.__name__}: {e}")
        return False

