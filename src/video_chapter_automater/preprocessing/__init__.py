"""
Video preprocessing module for VideoChapterAutomater.

This module provides GPU-accelerated video re-encoding, audio extraction,
and scene image extraction with perceptual hash deduplication.
"""

from .base import PreprocessingOperation, CodecStrategy, HashStrategy
from .video_encoder import VideoEncoder, VideoEncodingConfig
from .audio_extractor import AudioExtractor, AudioExtractionConfig
from .scene_extractor import SceneExtractor, SceneExtractionConfig

__all__ = [
    "PreprocessingOperation",
    "CodecStrategy",
    "HashStrategy",
    "VideoEncoder",
    "VideoEncodingConfig",
    "AudioExtractor",
    "AudioExtractionConfig",
    "SceneExtractor",
    "SceneExtractionConfig",
]
