"""
Codec strategy implementations for video re-encoding.

Provides concrete implementations of CodecStrategy for various video codecs,
including GPU-accelerated (NVENC, VAAPI) and CPU fallback options.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..base import CodecStrategy


@dataclass
class VideoEncodingConfig:
    """
    Configuration for video encoding operations.

    Attributes:
        preset: Encoding speed preset (ultrafast, fast, medium, slow, veryslow)
        crf: Constant Rate Factor for quality (0-51, lower = better quality)
        bitrate: Target bitrate (e.g., "5M", "10M") - overrides CRF if set
        tune: Encoding optimization preset (film, animation, grain, etc.)
        pixel_format: Pixel format (yuv420p, yuv444p, etc.)
        resolution: Target resolution (e.g., "1920x1080", None = keep original)
        fps: Target frame rate (None = keep original)
        two_pass: Enable two-pass encoding for better quality
    """
    preset: str = "medium"
    crf: int = 23
    bitrate: Optional[str] = None
    tune: Optional[str] = None
    pixel_format: str = "yuv420p"
    resolution: Optional[str] = None
    fps: Optional[int] = None
    two_pass: bool = False

    def __post_init__(self):
        """Validate configuration parameters."""
        valid_presets = {
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow", "placebo"
        }
        if self.preset not in valid_presets:
            raise ValueError(
                f"Invalid preset: {self.preset}. "
                f"Must be one of: {', '.join(sorted(valid_presets))}"
            )

        if not 0 <= self.crf <= 51:
            raise ValueError(f"CRF must be between 0-51, got {self.crf}")

        if self.two_pass and not self.bitrate:
            raise ValueError("Two-pass encoding requires bitrate to be set")


class H264NvencStrategy(CodecStrategy):
    """
    NVIDIA NVENC hardware-accelerated H.264/AVC encoding.

    Uses h264_nvenc codec for fast GPU-based encoding on NVIDIA cards.
    Falls back to libx264 CPU encoding if GPU not available.
    """

    @property
    def name(self) -> str:
        """Human-readable codec name."""
        return "H.264 (NVENC)"

    @property
    def encoder_name(self) -> str:
        """FFmpeg encoder name."""
        return "h264_nvenc"

    def get_ffmpeg_args(
        self,
        input_path: Path,
        config: VideoEncodingConfig
    ) -> List[str]:
        """
        Generate FFmpeg arguments for NVENC H.264 encoding.

        Args:
            input_path: Path to input video file
            config: Encoding configuration

        Returns:
            List of FFmpeg command arguments
        """
        args = ["-c:v", "h264_nvenc"]

        # NVENC preset mapping
        nvenc_presets = {
            "ultrafast": "p1",
            "superfast": "p2",
            "veryfast": "p3",
            "faster": "p4",
            "fast": "p5",
            "medium": "p6",
            "slow": "p7",
            "slower": "p7",
            "veryslow": "p7",
        }
        preset = nvenc_presets.get(config.preset, "p6")
        args.extend(["-preset", preset])

        # Quality control
        if config.bitrate:
            args.extend(["-b:v", config.bitrate])
        else:
            # NVENC uses CQ (Constant Quality) instead of CRF
            cq_value = min(max(config.crf, 0), 51)
            args.extend(["-cq", str(cq_value)])

        # Pixel format
        args.extend(["-pix_fmt", config.pixel_format])

        # Resolution scaling
        if config.resolution:
            args.extend(["-s", config.resolution])

        # Frame rate
        if config.fps:
            args.extend(["-r", str(config.fps)])

        # Tune (limited support in NVENC)
        if config.tune == "film":
            args.extend(["-tune", "hq"])  # High quality
        elif config.tune == "animation":
            args.extend(["-tune", "ll"])  # Low latency

        return args

    def supports_gpu(self, gpu_type: str) -> bool:
        """
        Check if this strategy supports the given GPU type.

        Args:
            gpu_type: GPU vendor identifier ("nvidia", "intel", "cpu")

        Returns:
            True if GPU is NVIDIA, False otherwise
        """
        return gpu_type.lower() == "nvidia"

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        """
        Get CPU fallback strategy.

        Returns:
            LibX264Strategy instance for CPU encoding
        """
        return LibX264Strategy()


class HevcNvencStrategy(CodecStrategy):
    """
    NVIDIA NVENC hardware-accelerated H.265/HEVC encoding.

    Uses hevc_nvenc codec for efficient GPU-based HEVC encoding.
    Falls back to libx265 CPU encoding if GPU not available.
    """

    @property
    def name(self) -> str:
        """Human-readable codec name."""
        return "H.265/HEVC (NVENC)"

    @property
    def encoder_name(self) -> str:
        """FFmpeg encoder name."""
        return "hevc_nvenc"

    def get_ffmpeg_args(
        self,
        input_path: Path,
        config: VideoEncodingConfig
    ) -> List[str]:
        """
        Generate FFmpeg arguments for NVENC HEVC encoding.

        Args:
            input_path: Path to input video file
            config: Encoding configuration

        Returns:
            List of FFmpeg command arguments
        """
        args = ["-c:v", "hevc_nvenc"]

        # NVENC preset mapping
        nvenc_presets = {
            "ultrafast": "p1",
            "superfast": "p2",
            "veryfast": "p3",
            "faster": "p4",
            "fast": "p5",
            "medium": "p6",
            "slow": "p7",
            "slower": "p7",
            "veryslow": "p7",
        }
        preset = nvenc_presets.get(config.preset, "p6")
        args.extend(["-preset", preset])

        # Quality control
        if config.bitrate:
            args.extend(["-b:v", config.bitrate])
        else:
            # NVENC HEVC uses CQ
            cq_value = min(max(config.crf, 0), 51)
            args.extend(["-cq", str(cq_value)])

        # Pixel format
        args.extend(["-pix_fmt", config.pixel_format])

        # Resolution scaling
        if config.resolution:
            args.extend(["-s", config.resolution])

        # Frame rate
        if config.fps:
            args.extend(["-r", str(config.fps)])

        # Tune
        if config.tune == "film":
            args.extend(["-tune", "hq"])
        elif config.tune == "animation":
            args.extend(["-tune", "ll"])

        return args

    def supports_gpu(self, gpu_type: str) -> bool:
        """Check if this strategy supports the given GPU type."""
        return gpu_type.lower() == "nvidia"

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        """Get CPU fallback strategy."""
        return LibX265Strategy()


class VP9Strategy(CodecStrategy):
    """
    VP9 encoding with optional GPU acceleration.

    Uses libvpx-vp9 codec. GPU acceleration support varies by hardware.
    Primarily CPU-based encoding with some GPU optimizations if available.
    """

    @property
    def name(self) -> str:
        """Human-readable codec name."""
        return "VP9"

    @property
    def encoder_name(self) -> str:
        """FFmpeg encoder name."""
        return "libvpx-vp9"

    def get_ffmpeg_args(
        self,
        input_path: Path,
        config: VideoEncodingConfig
    ) -> List[str]:
        """
        Generate FFmpeg arguments for VP9 encoding.

        Args:
            input_path: Path to input video file
            config: Encoding configuration

        Returns:
            List of FFmpeg command arguments
        """
        args = ["-c:v", "libvpx-vp9"]

        # VP9 has different speed presets (0-5, lower = slower/better)
        speed_map = {
            "ultrafast": "5",
            "superfast": "5",
            "veryfast": "4",
            "faster": "4",
            "fast": "3",
            "medium": "2",
            "slow": "1",
            "slower": "0",
            "veryslow": "0",
        }
        speed = speed_map.get(config.preset, "2")
        args.extend(["-speed", speed])

        # Quality control
        if config.bitrate:
            args.extend(["-b:v", config.bitrate])
            if config.two_pass:
                # Two-pass encoding setup
                args.extend(["-pass", "1", "-passlogfile", str(input_path.stem)])
        else:
            # CRF for VP9 (0-63, recommended 15-35)
            crf_value = min(max(config.crf, 0), 63)
            args.extend(["-crf", str(crf_value)])

        # VP9 specific quality settings
        args.extend(["-quality", "good"])  # or "best" for slower encoding

        # Pixel format
        args.extend(["-pix_fmt", config.pixel_format])

        # Resolution scaling
        if config.resolution:
            args.extend(["-s", config.resolution])

        # Frame rate
        if config.fps:
            args.extend(["-r", str(config.fps)])

        # Row-based multithreading for better CPU utilization
        args.extend(["-row-mt", "1"])

        return args

    def supports_gpu(self, gpu_type: str) -> bool:
        """
        Check if this strategy supports the given GPU type.

        VP9 has limited GPU support, primarily CPU-based.
        """
        # VP9 can use some GPU acceleration but is primarily CPU
        # Return True for any GPU type to allow usage
        return True

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        """
        Get fallback strategy.

        VP9 doesn't have a simpler fallback, returns None.
        """
        return None


class LibX264Strategy(CodecStrategy):
    """
    CPU-based H.264/AVC encoding using libx264.

    Software encoder with excellent quality and wide compatibility.
    Used as fallback when NVENC is not available.
    """

    @property
    def name(self) -> str:
        """Human-readable codec name."""
        return "H.264 (libx264)"

    @property
    def encoder_name(self) -> str:
        """FFmpeg encoder name."""
        return "libx264"

    def get_ffmpeg_args(
        self,
        input_path: Path,
        config: VideoEncodingConfig
    ) -> List[str]:
        """
        Generate FFmpeg arguments for libx264 encoding.

        Args:
            input_path: Path to input video file
            config: Encoding configuration

        Returns:
            List of FFmpeg command arguments
        """
        args = ["-c:v", "libx264"]

        # Preset
        args.extend(["-preset", config.preset])

        # Quality control
        if config.bitrate:
            args.extend(["-b:v", config.bitrate])
            if config.two_pass:
                args.extend(["-pass", "1", "-passlogfile", str(input_path.stem)])
        else:
            # CRF (0-51, recommended 18-28)
            args.extend(["-crf", str(config.crf)])

        # Tune
        if config.tune:
            args.extend(["-tune", config.tune])

        # Pixel format
        args.extend(["-pix_fmt", config.pixel_format])

        # Resolution scaling
        if config.resolution:
            args.extend(["-s", config.resolution])

        # Frame rate
        if config.fps:
            args.extend(["-r", str(config.fps)])

        # Profile for compatibility
        args.extend(["-profile:v", "high", "-level", "4.1"])

        return args

    def supports_gpu(self, gpu_type: str) -> bool:
        """
        Check if this strategy supports the given GPU type.

        libx264 is CPU-only, always returns True for compatibility.
        """
        return True  # CPU fallback, always available

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        """
        Get fallback strategy.

        libx264 is already the fallback, returns None.
        """
        return None


class LibX265Strategy(CodecStrategy):
    """
    CPU-based H.265/HEVC encoding using libx265.

    Software encoder with excellent compression efficiency.
    Used as fallback when HEVC NVENC is not available.
    """

    @property
    def name(self) -> str:
        """Human-readable codec name."""
        return "H.265/HEVC (libx265)"

    @property
    def encoder_name(self) -> str:
        """FFmpeg encoder name."""
        return "libx265"

    def get_ffmpeg_args(
        self,
        input_path: Path,
        config: VideoEncodingConfig
    ) -> List[str]:
        """
        Generate FFmpeg arguments for libx265 encoding.

        Args:
            input_path: Path to input video file
            config: Encoding configuration

        Returns:
            List of FFmpeg command arguments
        """
        args = ["-c:v", "libx265"]

        # Preset
        args.extend(["-preset", config.preset])

        # Quality control
        if config.bitrate:
            args.extend(["-b:v", config.bitrate])
            if config.two_pass:
                args.extend(["-pass", "1", "-passlogfile", str(input_path.stem)])
        else:
            # CRF (0-51, recommended 20-28)
            args.extend(["-crf", str(config.crf)])

        # Tune
        if config.tune:
            args.extend(["-tune", config.tune])

        # Pixel format
        args.extend(["-pix_fmt", config.pixel_format])

        # Resolution scaling
        if config.resolution:
            args.extend(["-s", config.resolution])

        # Frame rate
        if config.fps:
            args.extend(["-r", str(config.fps)])

        # x265 specific parameters for quality
        x265_params = "log-level=error"
        args.extend(["-x265-params", x265_params])

        return args

    def supports_gpu(self, gpu_type: str) -> bool:
        """
        Check if this strategy supports the given GPU type.

        libx265 is CPU-only, always returns True for compatibility.
        """
        return True  # CPU fallback, always available

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        """
        Get fallback strategy.

        libx265 is already the fallback, returns None.
        """
        return None
