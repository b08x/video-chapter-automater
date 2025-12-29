"""
Video Chapter Automater - Automatic video chapter generation using scene detection.

This package provides tools for automatically adding chapter markers to video files
based on detected scene changes using PySceneDetect and FFmpeg with GPU acceleration.
"""

__version__ = "1.0.0"
__author__ = "Video Chapter Automater Team"

from .gpu_detection import GPUDetector, detect_gpu_capabilities, ProcessingMode
from .processor import VideoProcessor, process_video_file
from .chapconv import ChapterConverter, convert_pyscenedetect_csv

# Setup wizard is imported conditionally to avoid dependency issues
try:
    from .setup_wizard import SetupWizard, UserPreferences
    __all__ = [
        "VideoProcessor",
        "process_video_file",
        "ChapterConverter", 
        "convert_pyscenedetect_csv",
        "GPUDetector",
        "detect_gpu_capabilities", 
        "ProcessingMode",
        "SetupWizard",
        "UserPreferences",
    ]
except ImportError:
    __all__ = [
        "VideoProcessor",
        "process_video_file", 
        "ChapterConverter",
        "convert_pyscenedetect_csv",
        "GPUDetector",
        "detect_gpu_capabilities", 
        "ProcessingMode",
    ]