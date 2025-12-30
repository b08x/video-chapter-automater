"""
Tests for output organization functionality in VideoEncoder and AudioExtractor.
Verifies that the optional output_dir parameter is correctly handled.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from video_chapter_automater.preprocessing.video_encoder import VideoEncoder, VideoEncodingConfig
from video_chapter_automater.preprocessing.audio_extractor import AudioExtractor, AudioExtractionConfig

@pytest.fixture
def test_video_path(tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_text("fake video content")
    return video_file

@pytest.fixture
def output_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    return d

class TestVideoEncoderOutput:
    def test_build_ffmpeg_command_with_output_dir(self, test_video_path, output_dir):
        encoder = VideoEncoder()
        config = VideoEncodingConfig()
        # Mock strategy to avoid complex setup
        strategy = Mock()
        strategy.get_ffmpeg_args.return_value = ["-c:v", "libx264"]
        
        cmd = encoder._build_ffmpeg_command(test_video_path, config, strategy, output_dir=output_dir)
        
        expected_output = str(output_dir / "test_video_reencoded.mp4")
        assert cmd[-1] == expected_output

    def test_build_ffmpeg_command_without_output_dir(self, test_video_path):
        encoder = VideoEncoder()
        config = VideoEncodingConfig()
        strategy = Mock()
        strategy.get_ffmpeg_args.return_value = ["-c:v", "libx264"]
        
        cmd = encoder._build_ffmpeg_command(test_video_path, config, strategy)
        
        expected_output = str(test_video_path.parent / "test_video_reencoded.mp4")
        assert cmd[-1] == expected_output

class TestAudioExtractorOutput:
    def test_build_ffmpeg_command_with_output_dir(self, test_video_path, output_dir):
        extractor = AudioExtractor()
        config = AudioExtractionConfig()
        
        cmd = extractor._build_ffmpeg_command(test_video_path, config, output_dir=output_dir)
        
        expected_output = str(output_dir / "test_video.wav")
        assert cmd[-1] == expected_output

    def test_build_ffmpeg_command_without_output_dir(self, test_video_path):
        extractor = AudioExtractor()
        config = AudioExtractionConfig()
        
        cmd = extractor._build_ffmpeg_command(test_video_path, config)
        
        expected_output = str(test_video_path.parent / "test_video.wav")
        assert cmd[-1] == expected_output
