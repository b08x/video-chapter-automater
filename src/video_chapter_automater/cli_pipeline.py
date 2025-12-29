"""
Advanced pipeline CLI for Video Chapter Automater.

Provides vca-pipeline command for comprehensive preprocessing workflows
with GPU acceleration, scene extraction, and audio processing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.traceback import install as install_traceback
from rich.panel import Panel
from rich.table import Table

from .pipeline.config import PipelineConfig, PipelineStage, ExecutionMode
from .pipeline.orchestrator import PipelineOrchestrator
from .preprocessing.audio_extractor import AudioExtractionConfig
from .preprocessing.scene_extractor import SceneExtractionConfig
from .preprocessing.strategies.codec_strategies import VideoEncodingConfig
from .output.manager import OutputManager
from .exceptions import VideoChapterAutomaterError

# Install Rich traceback handler
install_traceback(show_locals=True)
console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the vca-pipeline argument parser."""
    parser = argparse.ArgumentParser(
        prog="vca-pipeline",
        description="Advanced video preprocessing pipeline with GPU acceleration and scene extraction.",
        epilog=(
            "Pipeline Stages:\n"
            "  1. Video Re-encoding (GPU-accelerated H.264/H.265/VP9)\n"
            "  2. Audio Extraction (WAV 16kHz mono for transcription)\n"
            "  3. Scene Extraction (with perceptual hash deduplication)\n\n"
            "Example usage:\n"
            "  vca-pipeline video.mp4                           # Full pipeline\n"
            "  vca-pipeline video.mp4 --no-video                # Skip re-encoding\n"
            "  vca-pipeline video.mp4 --codec hevc_nvenc        # Use H.265\n"
            "  vca-pipeline video.mp4 --scenes-per-scene 5      # 5 images per scene\n"
            "  vca-pipeline video.mp4 --dedup-threshold 3       # Strict deduplication\n"
            "  vca-pipeline video.mp4 --minimal                 # Audio + scenes only\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Required arguments
    parser.add_argument(
        "video_file",
        type=Path,
        help="Path to the input video file"
    )

    # Pipeline configuration
    pipeline_group = parser.add_argument_group("Pipeline Configuration")
    pipeline_group.add_argument(
        "--mode",
        choices=["sequential", "resilient"],
        default="sequential",
        help="Execution mode: sequential (stop on error) or resilient (continue on errors)"
    )
    pipeline_group.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./vca_output"),
        help="Base output directory (default: ./vca_output)"
    )
    pipeline_group.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bars and visual feedback"
    )
    pipeline_group.add_argument(
        "--no-monitoring",
        action="store_true",
        help="Disable system resource monitoring"
    )

    # Stage selection (preset configurations)
    preset_group = parser.add_argument_group("Pipeline Presets")
    presets = preset_group.add_mutually_exclusive_group()
    presets.add_argument(
        "--minimal",
        action="store_true",
        help="Minimal pipeline: audio + scenes only (no re-encoding)"
    )
    presets.add_argument(
        "--encoding-only",
        action="store_true",
        help="Video re-encoding only (no audio/scenes)"
    )

    # Individual stage toggles
    stage_group = parser.add_argument_group("Stage Selection")
    stage_group.add_argument(
        "--no-video",
        action="store_true",
        help="Skip video re-encoding stage"
    )
    stage_group.add_argument(
        "--no-audio",
        action="store_true",
        help="Skip audio extraction stage"
    )
    stage_group.add_argument(
        "--no-scenes",
        action="store_true",
        help="Skip scene extraction stage"
    )

    # Video encoding options
    video_group = parser.add_argument_group("Video Encoding Options")
    video_group.add_argument(
        "--codec",
        choices=["h264_nvenc", "hevc_nvenc", "vp9", "libx264", "libx265"],
        default="h264_nvenc",
        help="Video codec (default: h264_nvenc)"
    )
    video_group.add_argument(
        "--preset",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast",
                 "medium", "slow", "slower", "veryslow"],
        default="medium",
        help="Encoding preset (default: medium)"
    )
    video_group.add_argument(
        "--crf",
        type=int,
        default=23,
        help="Constant Rate Factor for quality, 0-51 (default: 23, lower = better)"
    )
    video_group.add_argument(
        "--bitrate",
        type=str,
        help="Target bitrate (e.g., '5M', '10M'), overrides CRF if set"
    )

    # Audio extraction options
    audio_group = parser.add_argument_group("Audio Extraction Options")
    audio_group.add_argument(
        "--sample-rate",
        type=int,
        choices=[8000, 16000, 22050, 44100, 48000],
        default=16000,
        help="Audio sample rate in Hz (default: 16000 for speech)"
    )
    audio_group.add_argument(
        "--audio-format",
        choices=["wav", "mp3", "flac", "aac"],
        default="wav",
        help="Audio output format (default: wav)"
    )
    audio_group.add_argument(
        "--normalize-audio",
        action="store_true",
        help="Apply audio normalization (loudnorm filter)"
    )

    # Scene extraction options
    scene_group = parser.add_argument_group("Scene Extraction Options")
    scene_group.add_argument(
        "--scenes-per-scene",
        type=int,
        default=3,
        choices=range(1, 10),
        metavar="N",
        help="Number of images to extract per scene, 1-9 (default: 3)"
    )
    scene_group.add_argument(
        "--scene-threshold",
        type=float,
        default=27.0,
        help="Content detection threshold (default: 27.0, higher = fewer scenes)"
    )
    scene_group.add_argument(
        "--dedup-threshold",
        type=int,
        default=5,
        help="Image similarity threshold for deduplication, 0-20 (default: 5)"
    )
    scene_group.add_argument(
        "--hash-algorithm",
        choices=["phash", "dhash", "whash"],
        default="phash",
        help="Perceptual hash algorithm (default: phash)"
    )
    scene_group.add_argument(
        "--scene-format",
        choices=["png", "jpg", "jpeg"],
        default="png",
        help="Scene image format (default: png)"
    )

    # General options
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output for debugging"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0"
    )

    return parser


def build_pipeline_config(args: argparse.Namespace) -> PipelineConfig:
    """
    Build pipeline configuration from command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Configured PipelineConfig instance
    """
    # Determine execution mode
    if args.mode == "resilient":
        execution_mode = ExecutionMode.RESILIENT
    else:
        execution_mode = ExecutionMode.SEQUENTIAL

    # Create base config
    config = PipelineConfig(
        execution_mode=execution_mode,
        output_base_dir=args.output_dir,
        enable_monitoring=not args.no_monitoring,
        enable_progress_bars=not args.no_progress,
        stop_on_error=(args.mode != "resilient")
    )

    # Apply presets
    if args.minimal:
        # Minimal: audio + scenes only
        _add_audio_stage(config, args)
        _add_scene_stage(config, args)
    elif args.encoding_only:
        # Encoding only
        _add_video_stage(config, args)
    else:
        # Default: add stages based on flags
        if not args.no_video:
            _add_video_stage(config, args)
        if not args.no_audio:
            _add_audio_stage(config, args)
        if not args.no_scenes:
            _add_scene_stage(config, args)

    return config


def _add_video_stage(config: PipelineConfig, args: argparse.Namespace) -> None:
    """Add video encoding stage to pipeline."""
    video_config = VideoEncodingConfig(
        preset=args.preset,
        crf=args.crf,
        bitrate=args.bitrate
    )
    config.add_stage(PipelineStage.VIDEO_ENCODING, config=video_config)
    config.metadata["video_codec"] = args.codec


def _add_audio_stage(config: PipelineConfig, args: argparse.Namespace) -> None:
    """Add audio extraction stage to pipeline."""
    audio_config = AudioExtractionConfig(
        sample_rate=args.sample_rate,
        format=args.audio_format,
        normalize=args.normalize_audio
    )
    config.add_stage(PipelineStage.AUDIO_EXTRACTION, config=audio_config)


def _add_scene_stage(config: PipelineConfig, args: argparse.Namespace) -> None:
    """Add scene extraction stage to pipeline."""
    scene_config = SceneExtractionConfig(
        num_images=args.scenes_per_scene,
        threshold=args.scene_threshold,
        dedup_threshold=args.dedup_threshold,
        hash_algorithm=args.hash_algorithm,
        image_format=args.scene_format
    )
    config.add_stage(PipelineStage.SCENE_EXTRACTION, config=scene_config)


def display_welcome_banner() -> None:
    """Display welcome banner."""
    banner_text = """
[bold blue]🎬 VIDEO PREPROCESSING PIPELINE 🎬[/bold blue]

[cyan]Advanced multi-stage preprocessing with GPU acceleration[/cyan]
    """
    console.print(Panel(banner_text, border_style="blue"))
    console.print()


def display_config_summary(config: PipelineConfig, video_file: Path, codec: str) -> None:
    """
    Display pipeline configuration summary.

    Args:
        config: Pipeline configuration
        video_file: Input video file path
        codec: Video codec name
    """
    table = Table(title="Pipeline Configuration", show_header=True)
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Input File", str(video_file.name))
    table.add_row("Output Directory", str(config.output_base_dir))
    table.add_row("Execution Mode", config.execution_mode.value)

    # List enabled stages
    stages = config.get_enabled_stages()
    stage_names = [s.stage.value for s in stages]
    table.add_row("Enabled Stages", ", ".join(stage_names))

    # Add codec if video encoding enabled
    if config.has_stage(PipelineStage.VIDEO_ENCODING):
        table.add_row("Video Codec", codec)

    console.print(table)
    console.print()


def main() -> int:
    """
    Main entry point for vca-pipeline command.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Validate input file
    if not args.video_file.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {args.video_file}", style="red")
        return 1

    if not args.video_file.is_file():
        console.print(f"[bold red]Error:[/bold red] Not a file: {args.video_file}", style="red")
        return 1

    try:
        # Display welcome banner
        if not args.no_progress:
            display_welcome_banner()

        # Build pipeline configuration
        config = build_pipeline_config(args)

        # Validate configuration
        try:
            config.validate()
        except ValueError as e:
            console.print(f"[bold red]Configuration Error:[/bold red] {e}", style="red")
            return 1

        # Display configuration summary
        if not args.no_progress:
            display_config_summary(config, args.video_file, args.codec)

        # Create output manager
        output_manager = OutputManager(
            base_dir=config.output_base_dir,
            auto_create=True
        )

        # Create and execute pipeline
        orchestrator = PipelineOrchestrator(
            config=config,
            output_manager=output_manager,
            verbose=args.verbose
        )

        result = orchestrator.execute(
            args.video_file,
            codec=args.codec  # Pass codec to video encoding stage
        )

        # Display results
        if result.success:
            console.print()
            console.print(Panel(
                f"[bold green]✓ Pipeline completed successfully![/bold green]\n"
                f"Total Duration: {result.total_duration:.2f}s\n"
                f"Output Directory: {config.output_base_dir}",
                title="Success",
                border_style="green"
            ))
            return 0
        else:
            console.print()
            console.print(Panel(
                f"[bold red]✗ Pipeline failed[/bold red]\n\n"
                f"{result.error_summary}",
                title="Error",
                border_style="red"
            ))
            return 1

    except VideoChapterAutomaterError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}", style="red")
        if args.verbose:
            console.print_exception()
        return 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}", style="red")
        console.print_exception()
        return 1


if __name__ == "__main__":
    sys.exit(main())
