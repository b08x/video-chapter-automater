"""
Unit tests for audio extraction module.

Tests AudioExtractor with mocked FFmpeg calls to avoid
requiring actual video files and FFmpeg installation.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from video_chapter_automater.preprocessing.audio_extractor import (
    AudioExtractor,
    AudioExtractionConfig,
    AudioExtractionResult,
)
from video_chapter_automater.exceptions import (
    AudioExtractionError,
    DependencyError,
)


@pytest.fixture
def audio_extractor():
    """Create AudioExtractor instance for testing."""
    return AudioExtractor(verbose=False)


@pytest.fixture
def test_video_path(tmp_path):
    """Create a temporary test video file."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_text("fake video content")
    return video_file


@pytest.fixture
def default_config():
    """Create default AudioExtractionConfig."""
    return AudioExtractionConfig()


class TestAudioExtractionConfig:
    """Test AudioExtractionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AudioExtractionConfig()
        assert config.sample_rate == 16000
        assert config.channels == 1
        assert config.format == "wav"
        assert config.normalize is False
        assert config.codec == "pcm_s16le"
        assert config.bitrate is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = AudioExtractionConfig(
            sample_rate=44100,
            channels=2,
            format="mp3",
            normalize=True,
            bitrate="320k"
        )
        assert config.sample_rate == 44100
        assert config.channels == 2
        assert config.format == "mp3"
        assert config.normalize is True
        assert config.bitrate == "320k"

    def test_invalid_sample_rate(self):
        """Test validation of invalid sample rate."""
        with pytest.raises(ValueError, match="Invalid sample_rate"):
            AudioExtractionConfig(sample_rate=12345)

    def test_invalid_channels(self):
        """Test validation of invalid channels."""
        with pytest.raises(ValueError, match="Invalid channels"):
            AudioExtractionConfig(channels=5)

    def test_invalid_format(self):
        """Test validation of invalid format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            AudioExtractionConfig(format="ogg")


class TestAudioExtractor:
    """Test AudioExtractor class."""

    def test_validate_input_success(self, audio_extractor, test_video_path):
        """Test successful input validation."""
        assert audio_extractor.validate_input(test_video_path) is True

    def test_validate_input_nonexistent_file(self, audio_extractor, tmp_path):
        """Test validation with nonexistent file."""
        nonexistent = tmp_path / "nonexistent.mp4"
        with pytest.raises(ValueError, match="does not exist"):
            audio_extractor.validate_input(nonexistent)

    def test_validate_input_directory(self, audio_extractor, tmp_path):
        """Test validation with directory instead of file."""
        with pytest.raises(ValueError, match="not a file"):
            audio_extractor.validate_input(tmp_path)

    def test_validate_input_invalid_extension(self, audio_extractor, tmp_path):
        """Test validation with unsupported file extension."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("text file")
        with pytest.raises(ValueError, match="Unsupported video format"):
            audio_extractor.validate_input(invalid_file)

    def test_estimate_duration(self, audio_extractor, test_video_path):
        """Test duration estimation."""
        # Create a file with known size (1MB = ~10 seconds estimate)
        test_video_path.write_bytes(b"x" * (1024 * 1024))
        duration = audio_extractor.estimate_duration(test_video_path)
        assert duration > 0
        assert isinstance(duration, float)

    @patch('subprocess.run')
    def test_execute_success(
        self,
        mock_run,
        audio_extractor,
        test_video_path,
        default_config,
        tmp_path
    ):
        """Test successful audio extraction."""
        # Mock successful FFmpeg execution
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        # Create expected output file
        output_path = test_video_path.parent / f"{test_video_path.stem}.wav"
        output_path.write_bytes(b"x" * 1000)  # Mock audio data

        # Mock ffprobe for duration
        with patch.object(
            audio_extractor,
            '_get_audio_duration',
            return_value=120.5
        ):
            result = audio_extractor.execute(test_video_path, default_config)

        assert result.success is True
        assert result.output_path == output_path
        assert result.sample_rate == 16000
        assert result.channels == 1
        assert result.duration_seconds == 120.5
        assert result.file_size_bytes == 1000

    @patch('subprocess.run')
    def test_execute_ffmpeg_not_found(
        self,
        mock_run,
        audio_extractor,
        test_video_path,
        default_config
    ):
        """Test error when FFmpeg is not installed."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(DependencyError, match="ffmpeg"):
            audio_extractor.execute(test_video_path, default_config)

    @patch('subprocess.run')
    def test_execute_ffmpeg_failure(
        self,
        mock_run,
        audio_extractor,
        test_video_path,
        default_config
    ):
        """Test error when FFmpeg command fails."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["ffmpeg"],
            stderr="FFmpeg error message"
        )

        with pytest.raises(AudioExtractionError, match="FFmpeg failed"):
            audio_extractor.execute(test_video_path, default_config)

    @patch('subprocess.run')
    def test_execute_output_not_created(
        self,
        mock_run,
        audio_extractor,
        test_video_path,
        default_config
    ):
        """Test error when output file is not created."""
        # Mock successful FFmpeg but don't create output file
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with pytest.raises(AudioExtractionError, match="Output file was not created"):
            audio_extractor.execute(test_video_path, default_config)

    def test_build_ffmpeg_command_default(
        self,
        audio_extractor,
        test_video_path,
        default_config
    ):
        """Test FFmpeg command building with default config."""
        cmd = audio_extractor._build_ffmpeg_command(test_video_path, default_config)

        assert "ffmpeg" in cmd
        assert "-y" in cmd  # Overwrite
        assert "-i" in cmd
        assert str(test_video_path) in cmd
        assert "-vn" in cmd  # No video
        assert "-acodec" in cmd
        assert "pcm_s16le" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd

    def test_build_ffmpeg_command_with_normalization(
        self,
        audio_extractor,
        test_video_path
    ):
        """Test FFmpeg command with audio normalization."""
        config = AudioExtractionConfig(normalize=True)
        cmd = audio_extractor._build_ffmpeg_command(test_video_path, config)

        assert "-af" in cmd
        assert "loudnorm" in cmd

    def test_build_ffmpeg_command_with_bitrate(
        self,
        audio_extractor,
        test_video_path
    ):
        """Test FFmpeg command with bitrate for compressed formats."""
        config = AudioExtractionConfig(format="mp3", bitrate="320k")
        cmd = audio_extractor._build_ffmpeg_command(test_video_path, config)

        assert "-b:a" in cmd
        assert "320k" in cmd

    @patch('subprocess.run')
    def test_get_audio_duration_success(self, mock_run, audio_extractor, tmp_path):
        """Test successful audio duration retrieval."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="123.45\n"
        )

        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        duration = audio_extractor._get_audio_duration(audio_file)
        assert duration == 123.45

    @patch('subprocess.run')
    def test_get_audio_duration_failure(self, mock_run, audio_extractor, tmp_path):
        """Test audio duration retrieval failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["ffprobe"])

        audio_file = tmp_path / "test.wav"
        audio_file.write_text("fake audio")

        duration = audio_extractor._get_audio_duration(audio_file)
        assert duration == 0.0

    def test_get_operation_name(self, audio_extractor):
        """Test operation name retrieval."""
        assert audio_extractor.get_operation_name() == "Audio Extraction"
