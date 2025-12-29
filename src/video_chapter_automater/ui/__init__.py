"""
UI components module for VideoChapterAutomater.

Provides Rich-based UI widgets for resource monitoring, progress tracking,
and result visualization. Harvests advanced features from main.py.
"""

from .monitors import ResourceMonitor, SystemResources
from .previews import ChapterPreview

__all__ = [
    "ResourceMonitor",
    "SystemResources",
    "ChapterPreview",
]
