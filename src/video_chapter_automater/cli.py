"""Command-line interface for Video Chapter Automater."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.traceback import install as install_traceback
    from rich.panel import Panel
    # Install Rich traceback handler for beautiful exceptions
    install_traceback(show_locals=True)
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    console = None
    RICH_AVAILABLE = False

from video_chapter_automater.processor import VideoProcessor
from video_chapter_automater.exceptions import VideoChapterAutomaterError
from video_chapter_automater.gpu_detection import detect_gpu_capabilities


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="video-chapter-automater",
        description="Automate video chapter creation using PySceneDetect and FFmpeg with GPU acceleration.",
        epilog=(
            "This tool requires the following external dependencies:\n"
            "  - scenedetect: Python package for scene detection\n" 
            "  - ffmpeg: Video processing tool\n\n"
            "Processing modes:\n"
            "  - auto: Automatically choose best interface (default)\n"
            "  - simple: Basic processing with minimal output\n" 
            "  - enhanced: Rich interactive interface with progress bars\n\n"
            "Example usage:\n"
            "  vca my_video.mp4                    # Auto mode\n"
            "  vca /path/to/video.mkv --simple     # Simple mode\n"
            "  vca video.mp4 --enhanced            # Rich UI mode\n"
            "  vca --setup                         # Run setup wizard\n"
            "  vca --gpu-info                      # Show GPU info"
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
        "-m", "--mode",
        choices=["auto", "simple", "enhanced"],
        default="auto",
        help="Processing mode: auto (default), simple, or enhanced"
    )
    
    parser.add_argument(
        "--simple",
        action="store_const",
        dest="mode",
        const="simple",
        help="Use simple processing mode (equivalent to --mode simple)"
    )
    
    parser.add_argument(
        "--enhanced", 
        action="store_const",
        dest="mode",
        const="enhanced",
        help="Use enhanced Rich UI mode (equivalent to --mode enhanced)"
    )
    
    parser.add_argument(
        "-t", "--threshold",
        type=float,
        default=30.0,
        help="Scene detection threshold (default: 30.0, lower = more chapters)"
    )
    
    parser.add_argument(
        "--no-cleanup",
        action="store_false", 
        dest="cleanup",
        default=True,
        help="Keep intermediate files (CSV, chapters.txt)"
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
    if console:
        console.print(Panel(
            "🎮 GPU Detection & System Capabilities",
            title="[bold blue]System Information[/bold blue]",
            border_style="blue"
        ))
    else:
        print("🎮 GPU Detection & System Capabilities")
        print("=" * 40)
    
    processing_mode, selected_gpu, ffmpeg_args = detect_gpu_capabilities()
    
    # Additional system info
    import platform
    platform_info = f"Platform: {platform.system()} {platform.release()}"
    python_info = f"Python: {sys.version.split()[0]}"
    
    if console:
        console.print(f"[dim]{platform_info}[/dim]")
        console.print(f"[dim]{python_info}[/dim]")
    else:
        print(platform_info)
        print(python_info)


def show_config() -> None:
    """Display current configuration."""
    try:
        from video_chapter_automater.setup_wizard import UserPreferences
        from video_chapter_automater.app_paths import ApplicationPaths

        app_paths = ApplicationPaths.for_current_platform()
        config_file = app_paths.config_file
        preferences = UserPreferences.load(config_file)

        config_text = (
            f"Configuration file: {config_file}\n\n"
            f"Installation Type: {preferences.installation_type.value}\n"
            f"GPU Preference: {preferences.gpu_preference}\n"
            f"Output Format: {preferences.output_format}\n"
            f"Default Output Dir: {preferences.default_output_dir or 'Current directory'}\n"
            f"Scene Detection Threshold: {preferences.scene_detection_threshold}\n"
            f"Cleanup Intermediate Files: {preferences.cleanup_intermediate_files}\n"
            f"Parallel Processing: {preferences.parallel_processing}"
        )
        
        if console:
            console.print(Panel(
                config_text,
                title="[bold green]Current Configuration[/bold green]",
                border_style="green"
            ))
        else:
            print("Current Configuration")
            print("=" * 21)
            print(config_text)
        
    except ImportError:
        msg = "Configuration not available - run setup first"
        if console:
            console.print(f"[yellow]{msg}[/yellow]")
        else:
            print(msg)
    except Exception as e:
        error_msg = f"Error reading configuration: {e}"
        if console:
            console.print(f"[red]{error_msg}[/red]")
        else:
            print(error_msg)


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
        # Create processor with appropriate mode
        processor = VideoProcessor(
            mode=parsed_args.mode,
            silent=parsed_args.silent,
            enable_rich_ui=None,  # Auto-detect based on mode
            enable_logging=True
        )
        
        # Process the video with options
        output_file = processor.process_video(
            parsed_args.video_file,
            threshold=parsed_args.threshold,
            cleanup=parsed_args.cleanup
        )
        
        if parsed_args.silent:
            # In silent mode, just print the output file path
            if console:
                console.print(str(output_file))
            else:
                print(str(output_file))
        
        return 0
        
    except VideoChapterAutomaterError as e:
        error_msg = f"Error: {e.message}"
        if console:
            # Use console.err for stderr output 
            console = Console(stderr=True)
            console.print(f"[bold red]{error_msg}[/bold red]")
        else:
            print(error_msg, file=sys.stderr)
        return 1
        
    except KeyboardInterrupt:
        msg = "Operation cancelled by user."
        if console:
            err_console = Console(stderr=True)
            err_console.print(f"\n[bold yellow]{msg}[/bold yellow]")
        else:
            print(f"\n{msg}", file=sys.stderr)
        return 130  # Standard exit code for SIGINT
        
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        if console:
            err_console = Console(stderr=True)
            err_console.print(f"[bold red]{error_msg}[/bold red]")
            if not parsed_args.silent:
                err_console.print_exception()
        else:
            print(error_msg, file=sys.stderr)
            if not parsed_args.silent:
                import traceback
                traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())