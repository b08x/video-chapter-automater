"""
Video Chapter Automater - Automatic video chapter generation using scene detection.

This package provides tools for automatically adding chapter markers to video files
based on detected scene changes using PySceneDetect, chapconv, and FFmpeg.
"""

__version__ = "1.0.0"
__author__ = "Video Chapter Automater Team"

from .gpu_detection import GPUDetector, detect_gpu_capabilities, ProcessingMode
from .main import main

# Setup wizard is imported conditionally to avoid dependency issues
try:
    from .setup_wizard import SetupWizard, UserPreferences
    __all__ = [
        "GPUDetector",
        "detect_gpu_capabilities", 
        "ProcessingMode",
        "main",
        "SetupWizard",
        "UserPreferences",
    ]
except ImportError:
    __all__ = [
        "GPUDetector",
        "detect_gpu_capabilities", 
        "ProcessingMode",
        "main",
    ]