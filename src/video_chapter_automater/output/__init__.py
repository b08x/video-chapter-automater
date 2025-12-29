"""
Output directory management for VideoChapterAutomater.

Handles creation and organization of the ./vca_output/ directory structure
with subdirectories for different output types (video, audio, scenes, metadata).
"""

from .manager import OutputManager, OutputType

__all__ = ["OutputManager", "OutputType"]
