"""
Unified Video Chapter Processor

Combines the simple reliability of core.py with the rich UI features of main.py.
Provides both basic and enhanced processing modes with GPU acceleration support.
"""

from __future__ import annotations

import csv
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Rich UI components (optional)
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn, 
        TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
    )
    from rich.status import Status
    from rich.table import Table
    from rich.text import Text
    from rich.traceback import install as install_traceback
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from .chapconv import convert_pyscenedetect_csv, ChapterConverter
from .exceptions import (
    CommandExecutionError,
    DependencyError, 
    FileNotFoundError as VCAFileNotFoundError
)
from .gpu_detection import detect_gpu_capabilities, ProcessingMode


class VideoProcessor:
    """
    Unified video chapter processor with both simple and enhanced modes.
    
    Features:
    - Progressive enhancement (Rich UI when available)
    - GPU acceleration with automatic fallback
    - Comprehensive error handling and recovery
    """
    
    def __init__(
        self, 
        mode: str = 'auto',
        silent: bool = False,
        enable_rich_ui: Optional[bool] = None,
        enable_logging: bool = True
    ) -> None:
        """
        Initialize the video processor.
        
        Args:
            mode: Processing mode ('simple', 'enhanced', 'auto')
            silent: Suppress non-error output
            enable_rich_ui: Force Rich UI on/off (None = auto-detect)
            enable_logging: Configure logging
        """
        self.mode = mode
        self.silent = silent
        
        # Determine UI mode
        if enable_rich_ui is None:
            self.rich_ui = RICH_AVAILABLE and not silent and (mode in ['enhanced', 'auto'])
        else:
            self.rich_ui = enable_rich_ui and RICH_AVAILABLE
        
        # Setup console and logging
        if self.rich_ui:
            self.console = Console()
            install_traceback(show_locals=True)
        else:
            self.console = None
        
        if enable_logging:
            self._setup_logging()
        
        # Processing state
        self.stats = {
            'start_time': None,
            'scene_detection_time': None,
            'conversion_time': None,
            'embedding_time': None,
            'total_time': None,
            'chapters_detected': 0,
            'gpu_acceleration': False,
            'processing_mode': 'cpu'
        }
        
        # GPU detection
        self.processing_mode, self.selected_gpu, self.gpu_ffmpeg_args = detect_gpu_capabilities()
        self.stats['processing_mode'] = self.processing_mode.value
        self.stats['gpu_acceleration'] = self.processing_mode != ProcessingMode.CPU_ONLY
    
    def _setup_logging(self) -> None:
        """Configure logging with appropriate handler."""
        if self.rich_ui:
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
        else:
            logging.basicConfig(
                level="INFO",
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        
        self.log = logging.getLogger("video_processor")
    
    def _print(self, message: str, style: Optional[str] = None) -> None:
        """Print message using appropriate method (Rich or standard)."""
        if self.silent:
            return
        
        if self.rich_ui and self.console:
            if style:
                self.console.print(f"[{style}]{message}[/{style}]")
            else:
                self.console.print(message)
        else:
            print(message)
    
    def _show_header(self, video_path: Path) -> None:
        """Display processing header."""
        if self.rich_ui and self.console:
            header_panel = Panel(
                f"🎬 Processing: [cyan]{video_path.name}[/cyan]\n"
                f"Started: {datetime.now().strftime('%H:%M:%S')} • "
                f"Mode: [bold]{self.processing_mode.value.upper()}[/bold]",
                title="[bold blue]Video Chapter Automater[/bold blue]",
                border_style="blue"
            )
            self.console.print(header_panel)
        else:
            self._print(f"🎬 Processing: {video_path.name}")
            self._print(f"Mode: {self.processing_mode.value.upper()}")
    
    def run_command(
        self, 
        command: List[str], 
        message: str,
        progress_task: Optional[Any] = None,
        expected_duration: Optional[float] = None
    ) -> subprocess.CompletedProcess[str]:
        """Execute a command with appropriate progress display."""
        
        if self.rich_ui and progress_task:
            return self._run_command_with_rich_progress(
                command, message, progress_task, expected_duration
            )
        else:
            return self._run_command_simple(command, message)
    
    def _run_command_simple(self, command: List[str], message: str) -> subprocess.CompletedProcess[str]:
        """Execute command with simple progress indication."""
        if not self.silent:
            self._print(f"{message}...")
        
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if not self.silent and hasattr(self, 'log'):
                self.log.info(f"{message}... Done!")
            
            return result
            
        except FileNotFoundError as e:
            raise DependencyError(
                dependency=str(e.filename),
                suggestion="Please ensure it is installed and in your PATH"
            ) from e
            
        except subprocess.CalledProcessError as e:
            if not self.silent:
                self._print(f"❌ Error during: '{message}'", "red")
                if e.stderr:
                    self._print(f"Error: {e.stderr.strip()}", "red")
            
            raise CommandExecutionError(
                command=' '.join(command),
                exit_code=e.returncode,
                stderr=e.stderr or ""
            ) from e
    
    def _run_command_with_rich_progress(
        self,
        command: List[str], 
        message: str,
        progress_task: Any,
        expected_duration: Optional[float] = None
    ) -> subprocess.CompletedProcess[str]:
        """Execute command with Rich progress tracking."""
        start_time = time.time()
        
        # Get the progress object from self if available
        progress_obj = getattr(self, '_current_progress', None)
        
        try:
            # Update progress to show command is running
            if progress_obj and hasattr(progress_obj, 'update'):
                progress_obj.update(progress_task, description=f"[bold green]{message}...[/bold green]")
            
            # Start process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8'
            )
            
            # Monitor process with progress updates
            while process.poll() is None:
                elapsed = time.time() - start_time
                
                if progress_obj and hasattr(progress_obj, 'update'):
                    if expected_duration:
                        estimated_progress = min((elapsed / expected_duration) * 100, 95)
                        progress_obj.update(progress_task, completed=estimated_progress)
                    else:
                        progress_obj.update(progress_task, completed=min(elapsed * 10, 95))
                
                time.sleep(0.1)
            
            # Get final result
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
            
            # Mark as complete
            if progress_obj and hasattr(progress_obj, 'update'):
                progress_obj.update(progress_task, completed=100, description=f"[bold green]{message} ✓[/bold green]")
            
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            
        except Exception as e:
            if progress_obj and hasattr(progress_obj, 'update'):
                progress_obj.update(progress_task, description=f"[bold red]{message} ✗[/bold red]")
            raise
    
    def process_video(self, video_path: str | Path, **options) -> Path:
        """
        Main video processing function.
        
        Args:
            video_path: Path to input video
            **options: Processing options (threshold, cleanup, etc.)
            
        Returns:
            Path to output video with chapters
        """
        self.stats['start_time'] = datetime.now()
        
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
        
        # Show header
        self._show_header(video_file)
        
        try:
            if self.rich_ui:
                return self._process_with_rich_ui(
                    video_file, scenes_csv_file, chapters_txt_file, 
                    output_video_file, **options
                )
            else:
                return self._process_simple(
                    video_file, scenes_csv_file, chapters_txt_file,
                    output_video_file, **options
                )
        
        except Exception:
            # Cleanup on error
            for temp_file in [scenes_csv_file, chapters_txt_file]:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass
            raise
    
    def _process_simple(
        self, 
        video_file: Path,
        scenes_csv_file: Path,
        chapters_txt_file: Path, 
        output_video_file: Path,
        **options
    ) -> Path:
        """Process video with simple progress indication."""
        
        # Step 1: Scene Detection
        threshold = options.get('threshold', 30.0)
        scene_start = time.time()
        
        scenedetect_cmd = [
            "scenedetect",
            "-i", str(video_file),
            "detect-content",
            "-t", str(threshold),
            "list-scenes"
        ]
        
        self.run_command(scenedetect_cmd, "Detecting scenes")
        self.stats['scene_detection_time'] = time.time() - scene_start
        
        if not scenes_csv_file.exists():
            raise VCAFileNotFoundError(
                str(scenes_csv_file),
                "PySceneDetect did not create the expected CSV file"
            )
        
        # Step 2: Chapter Conversion (Python-native)
        convert_start = time.time()
        self._print("Converting scenes to chapters...")
        
        try:
            chapters_content = convert_pyscenedetect_csv(scenes_csv_file)
            
            # Count chapters
            self.stats['chapters_detected'] = chapters_content.count('[CHAPTER]')
            
            # Write chapters file
            with open(chapters_txt_file, 'w', encoding='utf-8') as f:
                f.write(chapters_content)
            
            self.stats['conversion_time'] = time.time() - convert_start
            self._print(f"Generated {self.stats['chapters_detected']} chapters")
            
        except Exception as e:
            raise CommandExecutionError(
                command="python chapter conversion",
                exit_code=1,
                stderr=str(e)
            ) from e
        
        # Step 3: Chapter Embedding
        embed_start = time.time()
        
        ffmpeg_cmd = ["ffmpeg", "-y"]
        if self.gpu_ffmpeg_args:
            ffmpeg_cmd.extend(self.gpu_ffmpeg_args)
        
        ffmpeg_cmd.extend([
            "-i", str(video_file),
            "-i", str(chapters_txt_file),
            "-map_metadata", "1",
            "-codec", "copy",
            str(output_video_file)
        ])
        
        self.run_command(ffmpeg_cmd, "Embedding chapters")
        self.stats['embedding_time'] = time.time() - embed_start
        
        # Step 4: Cleanup
        if options.get('cleanup', True):
            try:
                scenes_csv_file.unlink(missing_ok=True)
                chapters_txt_file.unlink(missing_ok=True)
                if not self.silent:
                    self._print("Cleaned up intermediate files")
            except OSError as e:
                if hasattr(self, 'log'):
                    self.log.warning(f"Could not remove intermediate files: {e}")
        
        # Final stats
        self.stats['total_time'] = time.time() - self.stats['start_time'].timestamp()
        
        if not self.silent:
            self._print(f"✅ Successfully created: {output_video_file.name}", "green")
            self._print(f"Processing time: {self.stats['total_time']:.1f}s")
        
        return output_video_file
    
    def _process_with_rich_ui(
        self,
        video_file: Path,
        scenes_csv_file: Path,
        chapters_txt_file: Path,
        output_video_file: Path,
        **options
    ) -> Path:
        """Process video with Rich UI progress tracking."""
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="green", finished_style="bold green"),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True
        ) as progress:
            
            # Store progress object for use in command execution
            self._current_progress = progress
            
            # Create progress tasks
            overall_task = progress.add_task("🎬 Overall Progress", total=100)
            scene_task = progress.add_task("🔍 Scene Detection", total=100)
            convert_task = progress.add_task("🔄 Chapter Conversion", total=100)
            embed_task = progress.add_task("📁 Chapter Embedding", total=100)
            
            try:
                # Step 1: Scene Detection
                progress.update(overall_task, advance=25, description="🔍 Detecting scenes...")
                threshold = options.get('threshold', 30.0)
                scene_start = time.time()
                
                scenedetect_cmd = [
                    "scenedetect",
                    "-i", str(video_file),
                    "detect-content", 
                    "-t", str(threshold),
                    "list-scenes"
                ]
                
                file_size_mb = video_file.stat().st_size / (1024*1024)
                estimated_duration = max(file_size_mb / 100, 2.0)  # Rough estimate
                
                self.run_command(
                    scenedetect_cmd,
                    "Analyzing video scenes", 
                    scene_task,
                    estimated_duration
                )
                
                self.stats['scene_detection_time'] = time.time() - scene_start
                
                if not scenes_csv_file.exists():
                    raise VCAFileNotFoundError(
                        str(scenes_csv_file),
                        "PySceneDetect did not create the expected CSV file"
                    )
                
                # Step 2: Chapter Conversion
                progress.update(overall_task, advance=25, description="🔄 Converting to chapters...")
                convert_start = time.time()
                
                progress.update(convert_task, description="[bold green]Converting scene data to chapters...[/bold green]")
                
                try:
                    chapters_content = convert_pyscenedetect_csv(scenes_csv_file)
                    self.stats['chapters_detected'] = chapters_content.count('[CHAPTER]')
                    
                    with open(chapters_txt_file, 'w', encoding='utf-8') as f:
                        f.write(chapters_content)
                    
                    progress.update(convert_task, completed=100, 
                                  description=f"[bold green]Generated {self.stats['chapters_detected']} chapters ✓[/bold green]")
                    
                    self.stats['conversion_time'] = time.time() - convert_start
                    
                except Exception as e:
                    progress.update(convert_task, description=f"[bold red]Chapter conversion failed ✗[/bold red]")
                    raise CommandExecutionError(
                        command="python chapter conversion",
                        exit_code=1,
                        stderr=str(e)
                    ) from e
                
                # Step 3: Chapter Embedding
                progress.update(overall_task, advance=40, description="📁 Embedding chapters...")
                embed_start = time.time()
                
                ffmpeg_cmd = ["ffmpeg", "-y"]
                if self.gpu_ffmpeg_args:
                    ffmpeg_cmd.extend(self.gpu_ffmpeg_args)
                
                ffmpeg_cmd.extend([
                    "-i", str(video_file),
                    "-i", str(chapters_txt_file),
                    "-map_metadata", "1",
                    "-codec", "copy",
                    str(output_video_file)
                ])
                
                estimated_embed_duration = max(file_size_mb / 200, 1.0)
                
                self.run_command(
                    ffmpeg_cmd,
                    "Embedding chapters into video",
                    embed_task,
                    estimated_embed_duration
                )
                
                self.stats['embedding_time'] = time.time() - embed_start
                
                # Step 4: Cleanup
                progress.update(overall_task, advance=10, description="🧹 Cleaning up...")
                
                if options.get('cleanup', True):
                    try:
                        scenes_csv_file.unlink(missing_ok=True)
                        chapters_txt_file.unlink(missing_ok=True)
                    except OSError as e:
                        self.log.warning(f"Could not remove intermediate files: {e}")
                
                # Complete
                progress.update(overall_task, completed=100, description="✅ Processing Complete!")
                self.stats['total_time'] = time.time() - self.stats['start_time'].timestamp()
                
                # Show completion
                self._show_completion(output_video_file)
                
            except Exception:
                # Update progress to show error
                progress.update(overall_task, description="❌ Processing Failed")
                raise
            finally:
                # Clean up progress object reference
                if hasattr(self, '_current_progress'):
                    delattr(self, '_current_progress')
        
        return output_video_file
    
    def _show_completion(self, output_video_file: Path) -> None:
        """Show completion message with stats."""
        if not self.rich_ui or self.silent:
            return
        
        # Create stats table
        stats_table = Table(title="📊 Processing Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        
        if self.stats['scene_detection_time']:
            stats_table.add_row("Scene Detection", f"{self.stats['scene_detection_time']:.1f}s")
        if self.stats['conversion_time']:
            stats_table.add_row("Chapter Conversion", f"{self.stats['conversion_time']:.1f}s")
        if self.stats['embedding_time']:
            stats_table.add_row("Chapter Embedding", f"{self.stats['embedding_time']:.1f}s")
        if self.stats['total_time']:
            stats_table.add_row("Total Time", f"{self.stats['total_time']:.1f}s")
        
        stats_table.add_row("Chapters Created", str(self.stats['chapters_detected']))
        stats_table.add_row("Processing Mode", self.stats['processing_mode'].upper())
        
        success_panel = Panel(
            f"🎉 [bold green]Processing Complete![/bold green] 🎉\n\n"
            f"📁 Output: [cyan]{output_video_file.name}[/cyan]\n"
            f"📍 Location: {output_video_file.parent}\n\n"
            f"🚀 Your video now has {self.stats['chapters_detected']} chapters!",
            title="[bold green]Success[/bold green]",
            border_style="green"
        )
        
        self.console.print(success_panel)
        self.console.print(stats_table)


def process_video_file(video_path: str | Path, **kwargs) -> Path:
    """Convenience function to process a single video file."""
    processor = VideoProcessor(**kwargs)
    return processor.process_video(video_path)
