"""
Unit tests for codec strategy implementations.

Tests all codec strategies (H264Nvenc, HevcNvenc, VP9, LibX264, LibX265)
for proper FFmpeg argument generation and GPU support checking.
"""

from pathlib import Path

import pytest

from video_chapter_automater.preprocessing.strategies.codec_strategies import (
    VideoEncodingConfig,
    H264NvencStrategy,
    HevcNvencStrategy,
    VP9Strategy,
    LibX264Strategy,
    LibX265Strategy,
)


@pytest.fixture
def test_video_path(tmp_path):
    """Create a temporary test video file."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_text("fake video content")
    return video_file


@pytest.fixture
def default_config():
    """Create default VideoEncodingConfig."""
    return VideoEncodingConfig()


class TestVideoEncodingConfig:
    """Test VideoEncodingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = VideoEncodingConfig()
        assert config.preset == "medium"
        assert config.crf == 23
        assert config.bitrate is None
        assert config.tune is None
        assert config.pixel_format == "yuv420p"
        assert config.resolution is None
        assert config.fps is None
        assert config.two_pass is False

    def test_custom_config(self):
        """Test custom configuration."""
        config = VideoEncodingConfig(
            preset="slow",
            crf=18,
            bitrate="5M",
            tune="film",
            resolution="1920x1080",
            fps=30,
            two_pass=True
        )
        assert config.preset == "slow"
        assert config.crf == 18
        assert config.bitrate == "5M"
        assert config.tune == "film"
        assert config.resolution == "1920x1080"
        assert config.fps == 30
        assert config.two_pass is True

    def test_invalid_preset(self):
        """Test validation of invalid preset."""
        with pytest.raises(ValueError, match="Invalid preset"):
            VideoEncodingConfig(preset="invalid")

    def test_invalid_crf_too_low(self):
        """Test validation of CRF too low."""
        with pytest.raises(ValueError, match="CRF must be between"):
            VideoEncodingConfig(crf=-1)

    def test_invalid_crf_too_high(self):
        """Test validation of CRF too high."""
        with pytest.raises(ValueError, match="CRF must be between"):
            VideoEncodingConfig(crf=52)

    def test_two_pass_requires_bitrate(self):
        """Test that two-pass encoding requires bitrate."""
        with pytest.raises(ValueError, match="Two-pass encoding requires bitrate"):
            VideoEncodingConfig(two_pass=True, bitrate=None)


class TestH264NvencStrategy:
    """Test H264NvencStrategy."""

    def test_get_ffmpeg_args_default(self, test_video_path, default_config):
        """Test FFmpeg argument generation with default config."""
        strategy = H264NvencStrategy()
        args = strategy.get_ffmpeg_args(test_video_path, default_config)

        assert "-c:v" in args
        assert "h264_nvenc" in args
        assert "-preset" in args
        assert "-cq" in args
        assert str(default_config.crf) in args
        assert "-pix_fmt" in args
        assert default_config.pixel_format in args

    def test_get_ffmpeg_args_with_bitrate(self, test_video_path):
        """Test FFmpeg arguments with bitrate instead of CRF."""
        config = VideoEncodingConfig(bitrate="5M")
        strategy = H264NvencStrategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-b:v" in args
        assert "5M" in args
        assert "-cq" not in args

    def test_get_ffmpeg_args_with_resolution(self, test_video_path):
        """Test FFmpeg arguments with resolution scaling."""
        config = VideoEncodingConfig(resolution="1920x1080")
        strategy = H264NvencStrategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-s" in args
        assert "1920x1080" in args

    def test_get_ffmpeg_args_with_fps(self, test_video_path):
        """Test FFmpeg arguments with frame rate."""
        config = VideoEncodingConfig(fps=30)
        strategy = H264NvencStrategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-r" in args
        assert "30" in args

    def test_supports_gpu_nvidia(self):
        """Test GPU support check for NVIDIA."""
        strategy = H264NvencStrategy()
        assert strategy.supports_gpu("nvidia") is True
        assert strategy.supports_gpu("NVIDIA") is True

    def test_supports_gpu_other(self):
        """Test GPU support check for non-NVIDIA."""
        strategy = H264NvencStrategy()
        assert strategy.supports_gpu("intel") is False
        assert strategy.supports_gpu("cpu") is False

    def test_get_fallback_strategy(self):
        """Test fallback strategy retrieval."""
        strategy = H264NvencStrategy()
        fallback = strategy.get_fallback_strategy()
        assert isinstance(fallback, LibX264Strategy)


class TestHevcNvencStrategy:
    """Test HevcNvencStrategy."""

    def test_get_ffmpeg_args_default(self, test_video_path, default_config):
        """Test FFmpeg argument generation with default config."""
        strategy = HevcNvencStrategy()
        args = strategy.get_ffmpeg_args(test_video_path, default_config)

        assert "-c:v" in args
        assert "hevc_nvenc" in args
        assert "-preset" in args
        assert "-cq" in args

    def test_supports_gpu_nvidia(self):
        """Test GPU support check for NVIDIA."""
        strategy = HevcNvencStrategy()
        assert strategy.supports_gpu("nvidia") is True

    def test_get_fallback_strategy(self):
        """Test fallback strategy retrieval."""
        strategy = HevcNvencStrategy()
        fallback = strategy.get_fallback_strategy()
        assert isinstance(fallback, LibX265Strategy)


class TestVP9Strategy:
    """Test VP9Strategy."""

    def test_get_ffmpeg_args_default(self, test_video_path, default_config):
        """Test FFmpeg argument generation with default config."""
        strategy = VP9Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, default_config)

        assert "-c:v" in args
        assert "libvpx-vp9" in args
        assert "-speed" in args
        assert "-crf" in args
        assert str(default_config.crf) in args
        assert "-quality" in args
        assert "good" in args
        assert "-row-mt" in args

    def test_get_ffmpeg_args_with_bitrate(self, test_video_path):
        """Test FFmpeg arguments with bitrate."""
        config = VideoEncodingConfig(bitrate="5M")
        strategy = VP9Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-b:v" in args
        assert "5M" in args

    def test_get_ffmpeg_args_two_pass(self, test_video_path):
        """Test FFmpeg arguments for two-pass encoding."""
        config = VideoEncodingConfig(bitrate="5M", two_pass=True)
        strategy = VP9Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-pass" in args
        assert "1" in args
        assert "-passlogfile" in args

    def test_supports_gpu_any(self):
        """Test GPU support check (VP9 supports any)."""
        strategy = VP9Strategy()
        assert strategy.supports_gpu("nvidia") is True
        assert strategy.supports_gpu("intel") is True
        assert strategy.supports_gpu("cpu") is True

    def test_get_fallback_strategy(self):
        """Test fallback strategy retrieval (VP9 has no fallback)."""
        strategy = VP9Strategy()
        fallback = strategy.get_fallback_strategy()
        assert fallback is None


class TestLibX264Strategy:
    """Test LibX264Strategy."""

    def test_get_ffmpeg_args_default(self, test_video_path, default_config):
        """Test FFmpeg argument generation with default config."""
        strategy = LibX264Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, default_config)

        assert "-c:v" in args
        assert "libx264" in args
        assert "-preset" in args
        assert default_config.preset in args
        assert "-crf" in args
        assert str(default_config.crf) in args
        assert "-profile:v" in args
        assert "high" in args
        assert "-level" in args

    def test_get_ffmpeg_args_with_tune(self, test_video_path):
        """Test FFmpeg arguments with tune parameter."""
        config = VideoEncodingConfig(tune="film")
        strategy = LibX264Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-tune" in args
        assert "film" in args

    def test_get_ffmpeg_args_two_pass(self, test_video_path):
        """Test FFmpeg arguments for two-pass encoding."""
        config = VideoEncodingConfig(bitrate="5M", two_pass=True)
        strategy = LibX264Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, config)

        assert "-b:v" in args
        assert "5M" in args
        assert "-pass" in args
        assert "1" in args

    def test_supports_gpu_always_true(self):
        """Test GPU support check (CPU fallback always available)."""
        strategy = LibX264Strategy()
        assert strategy.supports_gpu("nvidia") is True
        assert strategy.supports_gpu("intel") is True
        assert strategy.supports_gpu("cpu") is True

    def test_get_fallback_strategy(self):
        """Test fallback strategy retrieval (already fallback)."""
        strategy = LibX264Strategy()
        fallback = strategy.get_fallback_strategy()
        assert fallback is None


class TestLibX265Strategy:
    """Test LibX265Strategy."""

    def test_get_ffmpeg_args_default(self, test_video_path, default_config):
        """Test FFmpeg argument generation with default config."""
        strategy = LibX265Strategy()
        args = strategy.get_ffmpeg_args(test_video_path, default_config)

        assert "-c:v" in args
        assert "libx265" in args
        assert "-preset" in args
        assert "-crf" in args
        assert "-x265-params" in args

    def test_supports_gpu_always_true(self):
        """Test GPU support check (CPU fallback always available)."""
        strategy = LibX265Strategy()
        assert strategy.supports_gpu("nvidia") is True
        assert strategy.supports_gpu("cpu") is True

    def test_get_fallback_strategy(self):
        """Test fallback strategy retrieval (already fallback)."""
        strategy = LibX265Strategy()
        fallback = strategy.get_fallback_strategy()
        assert fallback is None


class TestCodecStrategyInteraction:
    """Test interactions between codec strategies."""

    def test_nvenc_to_cpu_fallback_h264(self):
        """Test H264 NVENC to CPU fallback chain."""
        gpu_strategy = H264NvencStrategy()
        cpu_strategy = gpu_strategy.get_fallback_strategy()

        assert isinstance(cpu_strategy, LibX264Strategy)
        assert cpu_strategy.get_fallback_strategy() is None

    def test_nvenc_to_cpu_fallback_hevc(self):
        """Test HEVC NVENC to CPU fallback chain."""
        gpu_strategy = HevcNvencStrategy()
        cpu_strategy = gpu_strategy.get_fallback_strategy()

        assert isinstance(cpu_strategy, LibX265Strategy)
        assert cpu_strategy.get_fallback_strategy() is None

    def test_preset_mapping_consistency(self, test_video_path):
        """Test that all strategies handle presets consistently."""
        config_fast = VideoEncodingConfig(preset="fast")
        config_slow = VideoEncodingConfig(preset="slow")

        strategies = [
            H264NvencStrategy(),
            HevcNvencStrategy(),
            VP9Strategy(),
            LibX264Strategy(),
            LibX265Strategy(),
        ]

        for strategy in strategies:
            args_fast = strategy.get_ffmpeg_args(test_video_path, config_fast)
            args_slow = strategy.get_ffmpeg_args(test_video_path, config_slow)

            # All should include preset/speed arguments
            assert "-preset" in args_fast or "-speed" in args_fast
            assert "-preset" in args_slow or "-speed" in args_slow
