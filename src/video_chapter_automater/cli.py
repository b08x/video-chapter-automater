"""Command-line interface for Video Chapter Automater."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.traceback import install as install_traceback
from rich.panel import Panel

from video_chapter_automater.core import VideoChapterProcessor
from video_chapter_automater.exceptions import VideoChapterAutomaterError
from video_chapter_automater.gpu_detection import detect_gpu_capabilities

# Install Rich traceback handler for beautiful exceptions
install_traceback(show_locals=True)
console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-chapter-automater",
        description="Automate video chapter creation using PySceneDetect, chapconv, and FFmpeg.",
        epilog=(
            "This tool requires the following external dependencies:\n"
            "  - scenedetect: Python package for scene detection\n"
            "  - chapconv: Tool for chapter format conversion\n"
            "  - ffmpeg: Video processing tool\n\n"
            "Example usage:\n"
            "  video-chapter-automater my_video.mp4\n"
            "  vca /path/to/video.mkv\n"
            "  vca --setup    # Run interactive setup wizard"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "video_file",
        type=Path,
        nargs='?',
        help="Path to the input video file"
    )
    
    parser.add_argument(
        "-s", "--silent",
        action="store_true",
        help="Suppress non-error output"
    )
    
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the interactive setup wizard"
    )
    
    parser.add_argument(
        "--gpu-info",
        action="store_true",
        help="Display GPU detection information and exit"
    )
    
    parser.add_argument(
        "--config",
        action="store_true", 
        help="Show current configuration and exit"
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s 1.0.0"
    )
    
    return parser


def validate_input_file(video_file: Path) -> None:
    """Validate the input video file exists and has a reasonable extension.
    
    Args:
        video_file: Path to the video file
        
    Raises:
        SystemExit: If validation fails
    """
    if not video_file.exists():
        console.print(
            f"[bold red]Error:[/bold red] Video file not found: {video_file}",
            file=sys.stderr
        )
        sys.exit(1)
    
    if not video_file.is_file():
        console.print(
            f"[bold red]Error:[/bold red] Path is not a file: {video_file}",
            file=sys.stderr
        )
        sys.exit(1)
    
    # Check for common video file extensions
    video_extensions = {
        '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v',
        '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.mts', '.m2ts'
    }
    
    if video_file.suffix.lower() not in video_extensions:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] "
            f"'{video_file.suffix}' is not a recognized video file extension. "
            f"Proceeding anyway...",
            file=sys.stderr
        )


def show_gpu_info() -> None:
    """Display GPU detection information."""
    console.print(Panel(
        "🎮 GPU Detection & System Capabilities",
        title="[bold blue]System Information[/bold blue]",
        border_style="blue"
    ))
    
    processing_mode, selected_gpu, ffmpeg_args = detect_gpu_capabilities()
    
    # Additional system info
    import platform
    console.print(f"[dim]Platform:[/dim] {platform.system()} {platform.release()}")
    console.print(f"[dim]Python:[/dim] {sys.version.split()[0]}")


def show_config() -> None:
    """Display current configuration."""
    try:
        from video_chapter_automater.setup_wizard import UserPreferences
        config_file = Path.home() / ".video_chapter_automater" / "config.json"
        preferences = UserPreferences.load(config_file)
        
        console.print(Panel(
            f"Configuration file: {config_file}\n\n"
            f"Installation Type: {preferences.installation_type.value}\n"
            f"GPU Preference: {preferences.gpu_preference}\n"
            f"Output Format: {preferences.output_format}\n"
            f"Default Output Dir: {preferences.default_output_dir or 'Current directory'}\n"
            f"Scene Detection Threshold: {preferences.scene_detection_threshold}\n"
            f"Cleanup Intermediate Files: {preferences.cleanup_intermediate_files}\n"
            f"Parallel Processing: {preferences.parallel_processing}",
            title="[bold green]Current Configuration[/bold green]",
            border_style="green"
        ))
        
    except ImportError:
        console.print("[yellow]Configuration not available - run setup first[/yellow]")
    except Exception as e:
        console.print(f"[red]Error reading configuration: {e}[/red]")


def run_setup_wizard() -> int:
    """Run the interactive setup wizard."""
    try:
        from video_chapter_automater.setup_wizard import SetupWizard
        wizard = SetupWizard()
        success = wizard.run()
        return 0 if success else 1
        
    except ImportError as e:
        console.print(f"[bold red]Setup wizard not available:[/bold red] {e}", file=sys.stderr)
        console.print("Please ensure all dependencies are installed.", file=sys.stderr)
        return 1


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI application.
    
    Args:
        args: Optional list of command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    # Handle special commands first
    if parsed_args.setup:
        return run_setup_wizard()
        
    if parsed_args.gpu_info:
        show_gpu_info()
        return 0
        
    if parsed_args.config:
        show_config()
        return 0
    
    # Require video file for normal processing
    if not parsed_args.video_file:
        console.print("[bold red]Error:[/bold red] Video file path is required", file=sys.stderr)
        console.print("Use --help for usage information or --setup to run the setup wizard", file=sys.stderr)
        return 1
    
    # Validate input
    validate_input_file(parsed_args.video_file)
    
    try:
        # Process the video
        processor = VideoChapterProcessor(silent=parsed_args.silent)
        output_file = processor.process_video(parsed_args.video_file)
        
        if parsed_args.silent:
            # In silent mode, just print the output file path
            console.print(str(output_file))
        
        return 0
        
    except VideoChapterAutomaterError as e:
        console.print(
            f"[bold red]Error:[/bold red] {e.message}",
            file=sys.stderr
        )
        return 1
        
    except KeyboardInterrupt:
        console.print(
            "\n[bold yellow]Operation cancelled by user.[/bold yellow]",
            file=sys.stderr
        )
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        console.print(
            f"[bold red]Unexpected error:[/bold red] {e}",
            file=sys.stderr
        )
        if not parsed_args.silent:
            console.print_exception()
        return 1


if __name__ == "__main__":
    sys.exit(main())