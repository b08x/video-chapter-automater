"""Core video chapter processing functionality."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.traceback import install as install_traceback

from video_chapter_automater.exceptions import (
    CommandExecutionError,
    DependencyError,
    FileNotFoundError as VCAFileNotFoundError,
)

# Setup Rich Console and Logging
console = Console()
install_traceback(show_locals=True)


class VideoChapterProcessor:
    """Processes video files to automatically add chapter markers."""

    def __init__(self, enable_logging: bool = True, silent: bool = False) -> None:
        """Initialize the processor with optional logging configuration.
        
        Args:
            enable_logging: Whether to configure rich logging
            silent: Whether to suppress non-error output
        """
        self.console = Console()
        self.silent = silent
        
        if enable_logging:
            self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging to use RichHandler for pretty output."""
        import logging
        
        logging.basicConfig(
            level="INFO",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[
                RichHandler(
                    console=self.console,
                    rich_tracebacks=True,
                    show_path=False
                )
            ]
        )
        self.log = logging.getLogger("rich")

    def run_command(
        self, 
        command: list[str], 
        message: str, 
        silent: bool | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Execute a shell command with error handling and status display.
        
        Args:
            command: List of command arguments
            message: Description of the operation for user feedback
            silent: Override instance silent setting
            
        Returns:
            CompletedProcess result
            
        Raises:
            DependencyError: If the command is not found
            CommandExecutionError: If the command fails
        """
        if silent is None:
            silent = self.silent
            
        with self.console.status(f"[bold green]{message}...") as status:
            try:
                result = subprocess.run(
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                if not silent and hasattr(self, 'log'):
                    self.log.info(f"{message}... [bold green]Done![/bold green]")
                return result
                
            except FileNotFoundError as e:
                raise DependencyError(
                    dependency=str(e.filename),
                    suggestion="Please ensure it is installed and in your PATH"
                ) from e
                
            except subprocess.CalledProcessError as e:
                if not silent:
                    self.console.print(f"[bold red]Error during: '{message}'[/bold red]")
                    error_panel = Panel(
                        e.stderr.strip() if e.stderr else "No error output",
                        title="[bold yellow]Error Output[/bold yellow]",
                        border_style="red",
                        expand=False
                    )
                    self.console.print(error_panel)
                
                raise CommandExecutionError(
                    command=' '.join(command),
                    exit_code=e.returncode,
                    stderr=e.stderr or ""
                ) from e

    def process_video(self, video_path: str | Path) -> Path:
        """Process a video file to add chapter markers.
        
        Args:
            video_path: Path to the input video file
            
        Returns:
            Path to the output video file with chapters
            
        Raises:
            VCAFileNotFoundError: If the input video file doesn't exist
            CommandExecutionError: If any processing step fails
            DependencyError: If required tools are not available
        """
        if not self.silent:
            self.console.print(
                Panel(
                    "🎬 Automatic Video Chapter Generator 🎬",
                    style="bold blue", 
                    title="[bold green]Status[/bold green]", 
                    expand=False
                )
            )

        # Setup paths
        video_file = Path(video_path)
        if not video_file.exists():
            raise VCAFileNotFoundError(
                str(video_file), 
                "Input video file does not exist"
            )

        base_name = video_file.stem
        output_dir = video_file.parent

        scenes_csv_file = output_dir / f"{base_name}-Scenes.csv"
        chapters_txt_file = output_dir / "chapters.txt"
        output_video_file = output_dir / f"{base_name}_with_chapters.mp4"

        if not self.silent and hasattr(self, 'log'):
            self.log.info(f"Input video: [cyan]{video_file.name}[/cyan]")
            self.log.info(f"Output video: [cyan]{output_video_file.name}[/cyan]")

        try:
            # Step 1: Detect scenes with PySceneDetect
            self._detect_scenes(video_file)
            
            if not scenes_csv_file.exists():
                raise VCAFileNotFoundError(
                    str(scenes_csv_file),
                    "PySceneDetect did not create the expected CSV file"
                )

            # Step 2: Convert CSV to FFmpeg chapters
            chapters_content = self._convert_scenes_to_chapters(scenes_csv_file)
            
            # Write chapters to file
            with open(chapters_txt_file, 'w', encoding='utf-8') as f:
                f.write(chapters_content)

            # Step 3: Embed chapters with FFmpeg
            self._embed_chapters(video_file, chapters_txt_file, output_video_file)

            # Step 4: Cleanup intermediate files
            self._cleanup_intermediate_files(scenes_csv_file, chapters_txt_file)

            # Final success message
            if not self.silent:
                success_panel = Panel(
                    f"Successfully created new video with chapters:\n"
                    f"[bold cyan][link=file://{output_video_file.resolve()}]"
                    f"{output_video_file.name}[/link]",
                    title="[bold green]🎉 Process Complete 🎉[/bold green]",
                    border_style="green",
                    expand=False
                )
                self.console.print(success_panel)

            return output_video_file

        except Exception:
            # Cleanup on error
            for temp_file in [scenes_csv_file, chapters_txt_file]:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass  # Ignore cleanup errors
            raise

    def _detect_scenes(self, video_file: Path) -> None:
        """Detect scenes using PySceneDetect."""
        scenedetect_cmd = [
            "scenedetect",
            "-i", str(video_file),
            "detect-content",
            "list-scenes"
        ]
        self.run_command(scenedetect_cmd, "Step 1: Detecting scenes")

    def _convert_scenes_to_chapters(self, scenes_csv_file: Path) -> str:
        """Convert scene CSV to FFmpeg chapter format using chapconv."""
        chapconv_cmd = [
            "chapconv",
            "--input-format", "pyscenedetect",
            str(scenes_csv_file),
            "--output-format", "ffmpeg"
        ]
        result = self.run_command(chapconv_cmd, "Step 2: Converting scene data")
        return result.stdout

    def _embed_chapters(
        self, 
        video_file: Path, 
        chapters_file: Path, 
        output_file: Path
    ) -> None:
        """Embed chapters into video using FFmpeg."""
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if it exists
            "-i", str(video_file),
            "-i", str(chapters_file),
            "-map_metadata", "1",
            "-codec", "copy",
            str(output_file)
        ]
        self.run_command(ffmpeg_cmd, "Step 3: Embedding chapters")

    def _cleanup_intermediate_files(
        self, 
        scenes_csv_file: Path, 
        chapters_txt_file: Path
    ) -> None:
        """Clean up intermediate files."""
        try:
            scenes_csv_file.unlink(missing_ok=True)
            chapters_txt_file.unlink(missing_ok=True)
            if not self.silent and hasattr(self, 'log'):
                self.log.info(
                    "Step 4: Cleaning up intermediate files... "
                    "[bold green]Done![/bold green]"
                )
        except OSError as e:
            if not self.silent and hasattr(self, 'log'):
                self.log.warning(f"Could not remove intermediate files: {e}")


def process_video_file(video_path: str | Path, silent: bool = False) -> Path:
    """Convenience function to process a single video file.
    
    Args:
        video_path: Path to the input video file
        silent: Whether to suppress output
        
    Returns:
        Path to the output video file with chapters
    """
    processor = VideoChapterProcessor(silent=silent)
    return processor.process_video(video_path)