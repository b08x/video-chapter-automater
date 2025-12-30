"""
Video encoding module for VideoChapterAutomater.

Re-encodes video files with GPU acceleration and intelligent CPU fallback.
Supports multiple codecs (H.264, H.265, VP9) with interactive error handling.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from ..exceptions import GPUEncodingError, DependencyError, InvalidConfigurationError
from ..gpu_detection import GPUDetector, GPUVendor, ProcessingMode
from .base import PreprocessingOperation, PreprocessingResult, CodecStrategy
from .strategies.codec_strategies import (
    VideoEncodingConfig,
    H264NvencStrategy,
    HevcNvencStrategy,
    VP9Strategy,
    LibX264Strategy,
    LibX265Strategy,
)

console = Console()


@dataclass
class VideoEncodingResult(PreprocessingResult):
    """Result from video encoding operation."""
    codec_used: str = ""
    gpu_accelerated: bool = False
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    resolution: str = ""
    fps: float = 0.0
    bitrate_kbps: int = 0


class VideoEncoder(PreprocessingOperation):
    """
    Re-encodes video files with GPU acceleration and CPU fallback.

    Handles codec selection, GPU detection, encoding execution, and
    interactive fallback prompts when GPU encoding fails.
    """

    # Codec strategy mapping
    CODEC_STRATEGIES = {
        "h264_nvenc": H264NvencStrategy,
        "hevc_nvenc": HevcNvencStrategy,
        "vp9": VP9Strategy,
        "libx264": LibX264Strategy,
        "libx265": LibX265Strategy,
    }

    def __init__(self, verbose: bool = False, interactive: bool = True):
        """
        Initialize video encoder.

        Args:
            verbose: Enable verbose FFmpeg output for debugging
            interactive: Enable interactive prompts for GPU fallback
        """
        self.verbose = verbose
        self.interactive = interactive
        self.gpu_detector = GPUDetector()

    def execute(
        self,
        input_path: Path,
        config: VideoEncodingConfig,
        codec_name: str = "h264_nvenc",
        output_dir: Optional[Path] = None
    ) -> VideoEncodingResult:
        """
        Re-encode video file with specified codec.

        Args:
            input_path: Path to input video file
            config: Video encoding configuration
            codec_name: Codec identifier (h264_nvenc, hevc_nvenc, vp9, libx264, libx265)

        Returns:
            VideoEncodingResult with encoding details

        Raises:
            GPUEncodingError: If GPU encoding fails and user chooses to abort
            DependencyError: If FFmpeg is not available
            InvalidConfigurationError: If codec is not supported
        """
        start_time = time.time()

        # Validate input
        self.validate_input(input_path)

        # Validate codec
        if codec_name not in self.CODEC_STRATEGIES:
            raise InvalidConfigurationError(
                f"Unsupported codec: {codec_name}. "
                f"Supported: {', '.join(self.CODEC_STRATEGIES.keys())}"
            )

        # Detect GPUs
        self.gpu_detector.detect_all_gpus()

        # Get codec strategy
        strategy_class = self.CODEC_STRATEGIES[codec_name]
        strategy = strategy_class()

        # Determine GPU type for strategy
        gpu_type = self._get_gpu_type()

        # Try GPU encoding first, then CPU fallback if needed
        result = self._encode_with_fallback(
            input_path,
            config,
            strategy,
            gpu_type,
            codec_name
        )

        # Add timing
        result.duration = time.time() - start_time

        return result

    def validate_input(self, input_path: Path) -> bool:
        """
        Validate input video file.

        Args:
            input_path: Path to video file

        Returns:
            True if valid

        Raises:
            ValueError: If input is invalid
        """
        if not input_path.exists():
            raise ValueError(f"Input file does not exist: {input_path}")

        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")

        # Check file extension
        valid_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
            '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'
        }

        if input_path.suffix.lower() not in valid_extensions:
            raise ValueError(
                f"Unsupported video format: {input_path.suffix}. "
                f"Supported: {', '.join(sorted(valid_extensions))}"
            )

        return True

    def estimate_duration(self, input_path: Path) -> float:
        """
        Estimate encoding duration based on video file size and codec.

        GPU encoding is significantly faster than CPU encoding.

        Args:
            input_path: Path to video file

        Returns:
            Estimated duration in seconds
        """
        file_size_mb = input_path.stat().st_size / (1024 * 1024)

        # GPU encoding: ~2-5x realtime speed
        # CPU encoding: ~0.5-2x realtime speed
        has_gpu = len(self.gpu_detector.detected_gpus) > 0

        if has_gpu:
            # GPU: process ~50MB/sec
            estimated_seconds = max(file_size_mb / 50, 5.0)
        else:
            # CPU: process ~5MB/sec
            estimated_seconds = max(file_size_mb / 5, 10.0)

        return estimated_seconds

    def _get_gpu_type(self) -> str:
        """
        Get GPU type string for codec strategy.

        Returns:
            GPU type: "nvidia", "intel", or "cpu"
        """
        if self.gpu_detector.processing_mode == ProcessingMode.NVIDIA_GPU:
            return "nvidia"
        elif self.gpu_detector.processing_mode == ProcessingMode.INTEL_GPU:
            return "intel"
        else:
            return "cpu"

    def _encode_with_fallback(
        self,
        input_path: Path,
        config: VideoEncodingConfig,
        strategy: CodecStrategy,
        gpu_type: str,
        codec_name: str,
        output_dir: Optional[Path] = None
    ) -> VideoEncodingResult:
        """
        Attempt encoding with GPU, fall back to CPU if it fails.

        Args:
            input_path: Input video file
            config: Encoding configuration
            strategy: Codec strategy to use
            gpu_type: GPU type detected
            codec_name: Original codec name

        Returns:
            VideoEncodingResult with encoding details

        Raises:
            GPUEncodingError: If GPU fails and user chooses to abort
        """
        # Check if strategy supports this GPU
        if not strategy.supports_gpu(gpu_type):
            # Use fallback strategy immediately
            fallback_strategy = strategy.get_fallback_strategy()
            if fallback_strategy:
                console.print(
                    f"[yellow]GPU type '{gpu_type}' not supported by {codec_name}, "
                    f"using CPU fallback[/yellow]"
                )
                strategy = fallback_strategy
                gpu_type = "cpu"

        # Try encoding
        try:
            return self._execute_encoding(
                input_path,
                config,
                strategy,
                gpu_type,
                codec_name,
                output_dir=output_dir
            )

        except subprocess.CalledProcessError as e:
            # GPU encoding failed
            stderr = e.stderr if e.stderr else "Unknown error"

            if gpu_type != "cpu":
                # Offer CPU fallback
                return self._handle_gpu_failure(
                    input_path,
                    config,
                    strategy,
                    codec_name,
                    gpu_type,
                    stderr,
                    output_dir=output_dir
                )
            else:
                # CPU encoding also failed, re-raise
                raise GPUEncodingError(
                    codec_name,
                    gpu_type,
                    f"Encoding failed: {stderr[:500]}"
                ) from e

    def _execute_encoding(
        self,
        input_path: Path,
        config: VideoEncodingConfig,
        strategy: CodecStrategy,
        gpu_type: str,
        codec_name: str,
        output_dir: Optional[Path] = None
    ) -> VideoEncodingResult:
        """
        Execute FFmpeg encoding command.

        Args:
            input_path: Input video file
            config: Encoding configuration
            strategy: Codec strategy
            gpu_type: GPU type
            codec_name: Codec identifier

        Returns:
            VideoEncodingResult

        Raises:
            subprocess.CalledProcessError: If FFmpeg fails
            DependencyError: If FFmpeg not found
        """
        # Build FFmpeg command
        ffmpeg_cmd = self._build_ffmpeg_command(
            input_path,
            config,
            strategy,
            output_dir=output_dir
        )

        # Execute encoding
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )

            # Get output path from command
            output_path = Path(ffmpeg_cmd[-1])

            # Validate output
            if not output_path.exists():
                raise GPUEncodingError(
                    codec_name,
                    gpu_type,
                    "Output file was not created"
                )

            # Get video metadata
            metadata = self._get_video_metadata(output_path)

            return VideoEncodingResult(
                success=True,
                output_path=output_path,
                codec_used=codec_name,
                gpu_accelerated=(gpu_type != "cpu"),
                file_size_bytes=output_path.stat().st_size,
                duration_seconds=metadata.get("duration", 0.0),
                resolution=metadata.get("resolution", ""),
                fps=metadata.get("fps", 0.0),
                bitrate_kbps=metadata.get("bitrate_kbps", 0),
                metadata={
                    "gpu_type": gpu_type,
                    "preset": config.preset,
                    "crf": config.crf,
                    "pixel_format": config.pixel_format,
                }
            )

        except FileNotFoundError as e:
            raise DependencyError(
                "ffmpeg",
                "Please install FFmpeg: https://ffmpeg.org/download.html"
            ) from e

    def _handle_gpu_failure(
        self,
        input_path: Path,
        config: VideoEncodingConfig,
        strategy: CodecStrategy,
        codec_name: str,
        gpu_type: str,
        error_message: str,
        output_dir: Optional[Path] = None
    ) -> VideoEncodingResult:
        """
        Handle GPU encoding failure with interactive fallback.

        Args:
            input_path: Input video file
            config: Encoding configuration
            strategy: Failed codec strategy
            codec_name: Codec identifier
            gpu_type: GPU type that failed
            error_message: Error details from FFmpeg

        Returns:
            VideoEncodingResult from CPU fallback

        Raises:
            GPUEncodingError: If user chooses to abort
        """
        # Get fallback strategy
        fallback_strategy = strategy.get_fallback_strategy()

        if not fallback_strategy:
            # No fallback available
            raise GPUEncodingError(
                codec_name,
                gpu_type,
                f"GPU encoding failed and no CPU fallback available: {error_message[:500]}"
            )

        # Show error panel
        console.print()
        console.print(Panel(
            f"[bold red]GPU Encoding Failed[/bold red]\n\n"
            f"Codec: {codec_name}\n"
            f"GPU Type: {gpu_type}\n\n"
            f"Error: {error_message[:200]}...",
            title="Encoding Error",
            border_style="red"
        ))

        # Interactive prompt
        if self.interactive:
            retry_cpu = Confirm.ask(
                "\n[yellow]Retry with CPU fallback?[/yellow]",
                default=True
            )

            if not retry_cpu:
                raise GPUEncodingError(
                    codec_name,
                    gpu_type,
                    "User chose to abort after GPU encoding failure"
                )

            console.print("[green]Retrying with CPU encoding...[/green]\n")
        else:
            # Non-interactive: automatically fall back
            console.print("[yellow]Automatically falling back to CPU encoding...[/yellow]\n")

        # Retry with CPU fallback
        try:
            return self._execute_encoding(
                input_path,
                config,
                fallback_strategy,
                "cpu",
                self._get_fallback_codec_name(codec_name),
                output_dir=output_dir
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else "Unknown error"
            raise GPUEncodingError(
                codec_name,
                "cpu",
                f"CPU fallback also failed: {stderr[:500]}"
            ) from e

    def _build_ffmpeg_command(
        self,
        input_path: Path,
        config: VideoEncodingConfig,
        strategy: CodecStrategy,
        output_dir: Optional[Path] = None
    ) -> list[str]:
        """
        Build FFmpeg command for video encoding.

        Args:
            input_path: Input video file
            config: Encoding configuration
            strategy: Codec strategy

        Returns:
            FFmpeg command as list of arguments
        """
        # Generate output filename
        output_filename = f"{input_path.stem}_reencoded{input_path.suffix}"
        
        if output_dir:
            output_path = output_dir / output_filename
        else:
            output_path = input_path.parent / output_filename

        cmd = ["ffmpeg", "-y"]  # -y = overwrite output file

        # Input file
        cmd.extend(["-i", str(input_path)])

        # Get codec-specific video arguments from strategy
        codec_args = strategy.get_ffmpeg_args(input_path, config)
        cmd.extend(codec_args)

        # Copy audio stream (no re-encoding)
        cmd.extend(["-c:a", "copy"])

        # Copy subtitles if present
        cmd.extend(["-c:s", "copy"])

        # Metadata
        cmd.extend(["-movflags", "+faststart"])  # Enable streaming

        # Verbosity
        if not self.verbose:
            cmd.extend(["-loglevel", "error"])
        else:
            cmd.extend(["-loglevel", "info", "-stats"])

        # Output file
        cmd.append(str(output_path))

        return cmd

    def _get_video_metadata(self, video_path: Path) -> dict:
        """
        Get metadata from video file using ffprobe.

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with duration, resolution, fps, bitrate
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,bit_rate:format=duration",
                "-of", "json",
                str(video_path)
            ]

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            import json
            data = json.loads(result.stdout)

            metadata = {}

            # Duration
            if "format" in data and "duration" in data["format"]:
                metadata["duration"] = float(data["format"]["duration"])

            # Resolution, FPS, bitrate from first video stream
            if "streams" in data and len(data["streams"]) > 0:
                stream = data["streams"][0]

                width = stream.get("width", 0)
                height = stream.get("height", 0)
                if width and height:
                    metadata["resolution"] = f"{width}x{height}"

                # Parse frame rate (e.g., "30/1" -> 30.0)
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    if int(den) > 0:
                        metadata["fps"] = float(num) / float(den)

                # Bitrate
                bitrate = stream.get("bit_rate")
                if bitrate:
                    metadata["bitrate_kbps"] = int(bitrate) // 1000

            return metadata

        except (subprocess.CalledProcessError, ValueError, KeyError, json.JSONDecodeError):
            return {}

    def _get_fallback_codec_name(self, codec_name: str) -> str:
        """
        Get fallback codec name for display purposes.

        Args:
            codec_name: Original codec name

        Returns:
            Fallback codec name
        """
        fallback_map = {
            "h264_nvenc": "libx264",
            "hevc_nvenc": "libx265",
            "vp9": "vp9",  # VP9 falls back to itself (CPU)
        }
        return fallback_map.get(codec_name, "libx264")

    def get_operation_name(self) -> str:
        """Get human-readable operation name."""
        return "Video Re-encoding"
