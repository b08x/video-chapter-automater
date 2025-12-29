"""
Shared pytest fixtures and configuration for VideoChapterAutomater tests.

Provides common fixtures and test utilities across all test modules.
"""

import sys
from pathlib import Path

import pytest

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def temp_video_file(tmp_path):
    """
    Create a temporary video file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary .mp4 file
    """
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content")
    return video_file


@pytest.fixture
def temp_audio_file(tmp_path):
    """
    Create a temporary audio file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary .wav file
    """
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"fake audio content")
    return audio_file


@pytest.fixture
def sample_video_metadata():
    """
    Provide sample video metadata dictionary.

    Returns:
        Dictionary with typical video metadata fields
    """
    return {
        "duration": 120.5,
        "resolution": "1920x1080",
        "fps": 30.0,
        "bitrate_kbps": 5000,
        "codec": "h264",
    }


@pytest.fixture
def mock_gpu_info():
    """
    Provide mock GPU information.

    Returns:
        Dictionary with GPU detection results
    """
    return {
        "has_nvidia": True,
        "has_intel": False,
        "gpu_name": "NVIDIA GeForce GTX 1080",
        "cuda_version": "12.0",
    }
