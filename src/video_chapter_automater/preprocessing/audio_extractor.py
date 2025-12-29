"""
Audio extraction module for VideoChapterAutomater.

Extracts audio tracks from video files and converts them to WAV format
optimized for speech transcription (16kHz, mono).
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..exceptions import AudioExtractionError, DependencyError
from .base import PreprocessingOperation, PreprocessingResult


@dataclass
class AudioExtractionConfig:
    """
    Configuration for audio extraction.

    Attributes:
        sample_rate: Target sample rate in Hz (default: 16000 for speech)
        channels: Number of audio channels (1=mono, 2=stereo)
        format: Output audio format (wav, mp3, flac)
        normalize: Apply audio normalization (loudnorm filter)
        codec: Audio codec to use (pcm_s16le for WAV)
        bitrate: Bitrate for compressed formats (e.g., "320k" for MP3)
    """
    sample_rate: int = 16000
    channels: int = 1  # mono
    format: str = "wav"
    normalize: bool = False
    codec: str = "pcm_s16le"  # 16-bit PCM for WAV
    bitrate: Optional[str] = None  # Only for compressed formats

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            raise ValueError(
                f"Invalid sample_rate: {self.sample_rate}. "
                f"Must be one of: 8000, 16000, 22050, 44100, 48000"
            )

        if self.channels not in [1, 2]:
            raise ValueError(f"Invalid channels: {self.channels}. Must be 1 (mono) or 2 (stereo)")

        if self.format not in ["wav", "mp3", "flac", "aac"]:
            raise ValueError(f"Unsupported format: {self.format}")


@dataclass
class AudioExtractionResult(PreprocessingResult):
    """Result from audio extraction operation."""
    sample_rate: int = 0
    channels: int = 0
    duration_seconds: float = 0.0
    file_size_bytes: int = 0


class AudioExtractor(PreprocessingOperation):
    """
    Extracts and converts audio from video files.

    Handles audio track extraction using FFmpeg, with support for
    format conversion, sample rate conversion, and normalization.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize audio extractor.

        Args:
            verbose: Enable verbose FFmpeg output for debugging
        """
        self.verbose = verbose

    def execute(
        self,
        input_path: Path,
        config: AudioExtractionConfig
    ) -> AudioExtractionResult:
        """
        Extract audio from video file.

        Args:
            input_path: Path to input video file
            config: Audio extraction configuration

        Returns:
            AudioExtractionResult with extraction details

        Raises:
            AudioExtractionError: If extraction fails
            DependencyError: If FFmpeg is not available
        """
        start_time = time.time()

        # Validate input
        self.validate_input(input_path)

        # Build FFmpeg command
        ffmpeg_cmd = self._build_ffmpeg_command(input_path, config)

        # Execute extraction
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
                raise AudioExtractionError(
                    str(input_path),
                    "Output file was not created"
                )

            # Get audio metadata
            duration = self._get_audio_duration(output_path)
            file_size = output_path.stat().st_size

            return AudioExtractionResult(
                success=True,
                output_path=output_path,
                duration=time.time() - start_time,
                sample_rate=config.sample_rate,
                channels=config.channels,
                duration_seconds=duration,
                file_size_bytes=file_size,
                metadata={
                    "format": config.format,
                    "normalized": config.normalize,
                    "codec": config.codec,
                }
            )

        except FileNotFoundError as e:
            raise DependencyError(
                "ffmpeg",
                "Please install FFmpeg: https://ffmpeg.org/download.html"
            ) from e

        except subprocess.CalledProcessError as e:
            stderr = e.stderr if e.stderr else "Unknown error"
            raise AudioExtractionError(
                str(input_path),
                f"FFmpeg failed: {stderr[:500]}"
            ) from e

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
        Estimate extraction duration based on video file size.

        Audio extraction is typically very fast (~1-5% of video duration).

        Args:
            input_path: Path to video file

        Returns:
            Estimated duration in seconds
        """
        # Rough estimate: 10MB/sec processing speed
        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        estimated_seconds = max(file_size_mb / 10, 1.0)
        return estimated_seconds

    def _build_ffmpeg_command(
        self,
        input_path: Path,
        config: AudioExtractionConfig
    ) -> list[str]:
        """
        Build FFmpeg command for audio extraction.

        Args:
            input_path: Input video file
            config: Extraction configuration

        Returns:
            FFmpeg command as list of arguments
        """
        # Generate output filename
        output_filename = f"{input_path.stem}.{config.format}"
        output_path = input_path.parent / output_filename

        cmd = ["ffmpeg", "-y"]  # -y = overwrite output file

        # Input file
        cmd.extend(["-i", str(input_path)])

        # No video stream
        cmd.append("-vn")

        # Audio codec
        cmd.extend(["-acodec", config.codec])

        # Sample rate
        cmd.extend(["-ar", str(config.sample_rate)])

        # Channels (mono/stereo)
        cmd.extend(["-ac", str(config.channels)])

        # Bitrate (for compressed formats)
        if config.bitrate and config.format in ["mp3", "aac"]:
            cmd.extend(["-b:a", config.bitrate])

        # Normalization filter
        if config.normalize:
            cmd.extend(["-af", "loudnorm"])

        # Verbosity
        if not self.verbose:
            cmd.extend(["-loglevel", "error"])

        # Output file
        cmd.append(str(output_path))

        return cmd

    def _get_audio_duration(self, audio_path: Path) -> float:
        """
        Get duration of audio file using ffprobe.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path)
            ]

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            return float(result.stdout.strip())

        except (subprocess.CalledProcessError, ValueError):
            return 0.0

    def get_operation_name(self) -> str:
        """Get human-readable operation name."""
        return "Audio Extraction"
