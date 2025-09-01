"""
Enhanced Video Chapter Automater with Advanced Rich TUI
A modern, interactive CLI application for automatic video chapter generation.
"""

import subprocess
import os
import argparse
import sys
import json
import time
import psutil
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

# Rich Components
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn,
    MofNCompleteColumn, FileSizeColumn, TransferSpeedColumn
)
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich.status import Status
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.logging import RichHandler
from rich.traceback import install as install_traceback
from rich.filesize import decimal
from rich.markup import escape
import logging

# Local imports
from .gpu_detection import detect_gpu_capabilities, ProcessingMode
from .setup_wizard import UserPreferences

# --- Advanced Configuration and State Management ---

@dataclass
class ProcessingStats:
    """Statistics tracking for processing operations."""
    start_time: Optional[datetime] = None
    scene_detection_time: Optional[float] = None
    conversion_time: Optional[float] = None
    embedding_time: Optional[float] = None
    total_time: Optional[float] = None
    input_file_size: int = 0
    output_file_size: int = 0
    chapters_detected: int = 0
    gpu_acceleration: bool = False
    processing_mode: str = "cpu"

@dataclass
class SystemResources:
    """Real-time system resource monitoring."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_usage: float = 0.0
    available_disk_gb: float = 0.0
    gpu_utilization: float = 0.0
    temperature: float = 0.0

class EnhancedVideoProcessor:
    """Enhanced video processor with advanced Rich TUI components."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.stats = ProcessingStats()
        self.resources = SystemResources()
        self.config_dir = Path.home() / ".video_chapter_automater"
        self.config_file = self.config_dir / "config.json"
        
        # Load user preferences
        self.preferences = UserPreferences.load(self.config_file)
        
        # Setup logging
        self._setup_logging()
        
        # Progress tracking
        self.current_step = 0
        self.total_steps = 4
        self.step_progress = {}
        
        # Resource monitoring
        self.resource_monitor_active = False
        self.resource_thread: Optional[threading.Thread] = None
        
    def _setup_logging(self):
        """Configure logging with Rich handler."""
        install_traceback(show_locals=True)
        
        logging.basicConfig(
            level="INFO",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(
                console=self.console, 
                rich_tracebacks=True, 
                show_path=False,
                markup=True
            )]
        )
        self.log = logging.getLogger("video_processor")

    def _start_resource_monitoring(self):
        """Start background resource monitoring."""
        self.resource_monitor_active = True
        self.resource_thread = threading.Thread(
            target=self._monitor_resources, 
            daemon=True
        )
        self.resource_thread.start()

    def _stop_resource_monitoring(self):
        """Stop background resource monitoring."""
        self.resource_monitor_active = False
        if self.resource_thread:
            self.resource_thread.join(timeout=1.0)

    def _monitor_resources(self):
        """Monitor system resources in background thread."""
        while self.resource_monitor_active:
            try:
                # CPU and Memory
                self.resources.cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                self.resources.memory_percent = memory.percent
                
                # Disk usage for current directory
                disk = psutil.disk_usage('.')
                self.resources.disk_usage = (disk.used / disk.total) * 100
                self.resources.available_disk_gb = disk.free / (1024**3)
                
                # GPU monitoring (if available)
                try:
                    import GPUtil
                    gpus = GPUtil.getGPUs()
                    if gpus:
                        self.resources.gpu_utilization = gpus[0].load * 100
                        self.resources.temperature = gpus[0].temperature
                except ImportError:
                    pass
                    
                time.sleep(1.0)
                
            except Exception:
                # Silently handle monitoring errors
                time.sleep(2.0)

    def create_main_layout(self) -> Layout:
        """Create the main application layout."""
        layout = Layout()
        
        # Define layout structure
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=8)
        )
        
        # Split main area
        layout["main"].split_row(
            Layout(name="left", ratio=2),
            Layout(name="right", ratio=1)
        )
        
        # Split footer for progress and resources
        layout["footer"].split_row(
            Layout(name="progress", ratio=2),
            Layout(name="resources", ratio=1)
        )
        
        return layout

    def create_header_panel(self, video_file: Path) -> Panel:
        """Create animated header panel."""
        header_content = Text()
        header_content.append("🎬 ", style="bold blue")
        header_content.append("VIDEO CHAPTER AUTOMATER", style="bold blue")
        header_content.append(" 🎬", style="bold blue")
        header_content.append(f"\nProcessing: {video_file.name}", style="cyan")
        header_content.append(f" • Started: {datetime.now().strftime('%H:%M:%S')}", style="dim")
        
        return Panel(
            Align.center(header_content),
            style="bold blue",
            border_style="blue",
            title="🚀 Enhanced Processing Engine",
            subtitle=f"v2.0 • GPU: {self.stats.processing_mode.upper()}"
        )

    def create_progress_panel(self, progress: Progress) -> Panel:
        """Create enhanced progress panel with multiple progress bars."""
        return Panel(
            progress,
            title="[bold green]Processing Progress[/bold green]",
            border_style="green",
            padding=(1, 2)
        )

    def create_resources_panel(self) -> Panel:
        """Create system resources monitoring panel."""
        resources_table = Table.grid(padding=1)
        resources_table.add_column(style="cyan", no_wrap=True)
        resources_table.add_column(style="white")
        
        # CPU
        cpu_bar = self._create_resource_bar(self.resources.cpu_percent)
        resources_table.add_row("CPU:", f"{self.resources.cpu_percent:5.1f}% {cpu_bar}")
        
        # Memory
        mem_bar = self._create_resource_bar(self.resources.memory_percent)
        resources_table.add_row("RAM:", f"{self.resources.memory_percent:5.1f}% {mem_bar}")
        
        # Disk
        disk_bar = self._create_resource_bar(self.resources.disk_usage)
        resources_table.add_row("Disk:", f"{self.resources.available_disk_gb:5.1f}GB {disk_bar}")
        
        # GPU (if available)
        if self.resources.gpu_utilization > 0:
            gpu_bar = self._create_resource_bar(self.resources.gpu_utilization)
            resources_table.add_row("GPU:", f"{self.resources.gpu_utilization:5.1f}% {gpu_bar}")
            resources_table.add_row("Temp:", f"{self.resources.temperature:5.1f}°C")
        
        return Panel(
            resources_table,
            title="[bold yellow]System Resources[/bold yellow]",
            border_style="yellow"
        )

    def _create_resource_bar(self, percent: float) -> str:
        """Create a simple text-based resource bar."""
        bar_length = 10
        filled = int((percent / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        if percent > 80:
            return f"[red]{bar}[/red]"
        elif percent > 60:
            return f"[yellow]{bar}[/yellow]"
        else:
            return f"[green]{bar}[/green]"

    def create_video_info_table(self, video_file: Path) -> Table:
        """Create detailed video information table."""
        table = Table(title="📹 Video Information")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        
        try:
            # Get file stats
            file_stats = video_file.stat()
            file_size = decimal(file_stats.st_size)
            modified_time = datetime.fromtimestamp(file_stats.st_mtime)
            
            table.add_row("File Name", video_file.name)
            table.add_row("File Size", str(file_size))
            table.add_row("Location", str(video_file.parent))
            table.add_row("Modified", modified_time.strftime("%Y-%m-%d %H:%M:%S"))
            
            # Try to get video metadata using ffprobe
            try:
                result = subprocess.run([
                    "ffprobe", "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", str(video_file)
                ], capture_output=True, text=True, check=True)
                
                metadata = json.loads(result.stdout)
                format_info = metadata.get("format", {})
                video_streams = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
                
                if format_info:
                    duration = float(format_info.get("duration", 0))
                    table.add_row("Duration", self._format_duration(duration))
                    table.add_row("Bitrate", f"{int(float(format_info.get('bit_rate', 0)) / 1000)} kbps")
                
                if video_streams:
                    stream = video_streams[0]
                    table.add_row("Resolution", f"{stream.get('width', 'Unknown')}x{stream.get('height', 'Unknown')}")
                    table.add_row("Codec", stream.get("codec_name", "Unknown"))
                    table.add_row("FPS", f"{eval(stream.get('r_frame_rate', '0/1')):.2f}")
                    
            except (subprocess.CalledProcessError, json.JSONDecodeError, Exception):
                table.add_row("Metadata", "[dim]Could not read video metadata[/dim]")
                
        except Exception as e:
            table.add_row("Error", f"[red]Could not read file information: {e}[/red]")
            
        return table

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human readable format."""
        duration = timedelta(seconds=seconds)
        hours, remainder = divmod(duration.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

    def run_command_with_progress(
        self, 
        command: List[str], 
        message: str,
        progress: Progress,
        task_id: int,
        expected_duration: Optional[float] = None
    ) -> subprocess.CompletedProcess[str]:
        """Execute command with enhanced progress tracking."""
        
        start_time = time.time()
        
        try:
            # Update progress to show command is running
            progress.update(task_id, description=f"[bold green]{message}...[/bold green]")
            
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
                
                if expected_duration:
                    # Calculate progress based on expected duration
                    estimated_progress = min((elapsed / expected_duration) * 100, 95)
                    progress.update(task_id, completed=estimated_progress)
                else:
                    # Use indeterminate progress
                    progress.update(task_id, completed=min(elapsed * 10, 95))
                
                time.sleep(0.1)
            
            # Get final result
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
            
            # Mark as complete
            progress.update(task_id, completed=100, description=f"[bold green]{message} ✓[/bold green]")
            
            # Create completed process object
            result = subprocess.CompletedProcess(
                command, process.returncode, stdout, stderr
            )
            
            return result
            
        except FileNotFoundError as e:
            progress.update(task_id, description=f"[bold red]{message} ✗ Command not found[/bold red]")
            self.console.print(
                Panel(
                    f"Command not found: [bold red]{e.filename}[/bold red]\n"
                    f"Please ensure it is installed and in your PATH.\n\n"
                    f"💡 [bold yellow]Installation Help:[/bold yellow]\n"
                    f"• For FFmpeg: https://ffmpeg.org/download.html\n"
                    f"• For PySceneDetect: pip install scenedetect[opencv]\n"
                    f"• For chapconv: pip install chapconv",
                    title="[bold red]❌ Dependency Missing[/bold red]",
                    border_style="red"
                )
            )
            sys.exit(1)
            
        except subprocess.CalledProcessError as e:
            progress.update(task_id, description=f"[bold red]{message} ✗ Failed[/bold red]")
            
            error_panel = Panel(
                f"[bold red]Command Failed:[/bold red] {' '.join(command)}\n\n"
                f"[bold yellow]Exit Code:[/bold yellow] {e.returncode}\n\n"
                f"[bold yellow]Error Output:[/bold yellow]\n"
                f"{escape(e.stderr.strip()) if e.stderr else 'No error output'}\n\n"
                f"💡 [bold cyan]Troubleshooting Tips:[/bold cyan]\n"
                f"• Check if input file is corrupted\n"
                f"• Ensure sufficient disk space\n"
                f"• Verify file permissions\n"
                f"• Try with a different video file",
                title="[bold red]❌ Processing Error[/bold red]",
                border_style="red",
                expand=False
            )
            self.console.print(error_panel)
            
            # Ask user if they want to continue or abort
            if not Confirm.ask("\n[bold yellow]Would you like to try to continue anyway?[/bold yellow]", default=False):
                sys.exit(1)
            
            raise

    def detect_gpu_with_display(self) -> Tuple[ProcessingMode, Any, List[str]]:
        """Detect GPU capabilities with enhanced display."""
        
        with Status("🔍 Analyzing system capabilities...", console=self.console):
            processing_mode, selected_gpu, gpu_ffmpeg_args = detect_gpu_capabilities()
        
        # Create enhanced GPU info display
        gpu_table = Table(title="🎮 System Analysis Results")
        gpu_table.add_column("Component", style="cyan")
        gpu_table.add_column("Status", style="green")
        gpu_table.add_column("Details", style="yellow")
        
        # Processing mode
        mode_icons = {
            ProcessingMode.NVIDIA_GPU: "🚀",
            ProcessingMode.INTEL_GPU: "⚡", 
            ProcessingMode.CPU_ONLY: "💻"
        }
        
        mode_descriptions = {
            ProcessingMode.NVIDIA_GPU: "CUDA Hardware Acceleration",
            ProcessingMode.INTEL_GPU: "Intel Quick Sync Acceleration",
            ProcessingMode.CPU_ONLY: "Software Processing"
        }
        
        gpu_table.add_row(
            "Processing Mode",
            f"{mode_icons.get(processing_mode, '❓')} {processing_mode.value.upper()}",
            mode_descriptions.get(processing_mode, "Unknown")
        )
        
        # GPU details
        if selected_gpu:
            gpu_table.add_row(
                "Selected GPU",
                "✅ Available",
                f"{selected_gpu.name}"
            )
            if hasattr(selected_gpu, 'memory_mb') and selected_gpu.memory_mb:
                gpu_table.add_row(
                    "GPU Memory",
                    f"{selected_gpu.memory_mb} MB",
                    "Sufficient for processing"
                )
        else:
            gpu_table.add_row(
                "GPU Acceleration", 
                "❌ Not Available", 
                "Using CPU processing"
            )
        
        # System resources
        try:
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            gpu_table.add_row(
                "CPU Cores",
                f"✅ {cpu_count} cores",
                f"{psutil.cpu_freq().current:.0f} MHz" if psutil.cpu_freq() else "Unknown frequency"
            )
            
            gpu_table.add_row(
                "System Memory", 
                f"✅ {memory.total // (1024**3)} GB",
                f"{memory.available // (1024**3)} GB available"
            )
            
            gpu_table.add_row(
                "Disk Space",
                f"✅ {disk.free // (1024**3)} GB free",
                "Sufficient for processing"
            )
            
        except Exception:
            gpu_table.add_row("System Info", "❓ Could not detect", "")
        
        gpu_panel = Panel(
            gpu_table,
            title="[bold blue]🔧 System Configuration[/bold blue]",
            border_style="blue"
        )
        
        self.console.print(gpu_panel)
        
        return processing_mode, selected_gpu, gpu_ffmpeg_args

    def show_interactive_file_dialog(self) -> Optional[Path]:
        """Show interactive file selection dialog."""
        self.console.print(Panel(
            "📂 No video file specified. Please select a file to process.",
            title="[bold cyan]File Selection[/bold cyan]",
            border_style="cyan"
        ))
        
        current_dir = Path.cwd()
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        
        while True:
            # List video files in current directory
            video_files = [
                f for f in current_dir.iterdir() 
                if f.is_file() and f.suffix.lower() in video_extensions
            ]
            
            if not video_files:
                self.console.print(f"[yellow]No video files found in {current_dir}[/yellow]")
                
                if Confirm.ask("Enter file path manually?", default=True):
                    file_path = Prompt.ask("Enter video file path")
                    path_obj = Path(file_path).expanduser().resolve()
                    
                    if path_obj.exists() and path_obj.is_file():
                        return path_obj
                    else:
                        self.console.print(f"[red]File not found: {file_path}[/red]")
                        continue
                else:
                    return None
            
            # Create file selection table
            file_table = Table(title=f"📁 Video Files in {current_dir}")
            file_table.add_column("#", style="cyan", width=3)
            file_table.add_column("File Name", style="white")
            file_table.add_column("Size", style="yellow", justify="right")
            file_table.add_column("Modified", style="dim")
            
            for i, video_file in enumerate(video_files, 1):
                try:
                    stats = video_file.stat()
                    size_str = decimal(stats.st_size)
                    modified = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d")
                    file_table.add_row(str(i), video_file.name, str(size_str), modified)
                except Exception:
                    file_table.add_row(str(i), video_file.name, "Unknown", "Unknown")
            
            self.console.print(file_table)
            
            # Get user selection
            choice = Prompt.ask(
                f"\nSelect file (1-{len(video_files)}) or 'q' to quit",
                default="1"
            )
            
            if choice.lower() == 'q':
                return None
            
            try:
                file_index = int(choice) - 1
                if 0 <= file_index < len(video_files):
                    return video_files[file_index]
                else:
                    self.console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                self.console.print("[red]Invalid input. Please enter a number or 'q'.[/red]")

    def show_processing_options(self) -> Dict[str, Any]:
        """Show interactive processing options dialog."""
        self.console.print(Panel(
            "⚙️ Configure processing options for optimal results",
            title="[bold magenta]Processing Configuration[/bold magenta]",
            border_style="magenta"
        ))
        
        options = {}
        
        # Processing quality
        quality_table = Table(title="Quality Profiles")
        quality_table.add_column("Profile", style="cyan")
        quality_table.add_column("Description", style="white")
        quality_table.add_column("Speed", style="yellow")
        quality_table.add_column("Best For", style="green")
        
        quality_table.add_row("Fast", "Quick processing, basic detection", "🚀 Fastest", "Quick previews")
        quality_table.add_row("Balanced", "Good quality/speed balance", "⚡ Fast", "Most use cases")
        quality_table.add_row("Quality", "Best scene detection accuracy", "🐌 Slower", "Final production")
        
        self.console.print(quality_table)
        
        quality_choice = Prompt.ask(
            "\nSelect quality profile",
            choices=["fast", "balanced", "quality"],
            default="balanced"
        )
        options['quality'] = quality_choice
        
        # Scene detection sensitivity
        if quality_choice == "quality":
            sensitivity = float(Prompt.ask(
                "Scene detection threshold (lower = more chapters)",
                default="27.0"
            ))
            options['threshold'] = sensitivity
        else:
            options['threshold'] = 30.0 if quality_choice == "balanced" else 35.0
        
        # Advanced options
        if Confirm.ask("\nConfigure advanced options?", default=False):
            options['cleanup'] = Confirm.ask(
                "Clean up intermediate files?", 
                default=self.preferences.cleanup_intermediate_files
            )
            
            options['parallel'] = Confirm.ask(
                "Enable parallel processing?",
                default=self.preferences.parallel_processing
            )
        else:
            options['cleanup'] = self.preferences.cleanup_intermediate_files
            options['parallel'] = self.preferences.parallel_processing
        
        return options

    def create_chapters_table(self, chapters_file: Path) -> Optional[Table]:
        """Create a table showing detected chapters."""
        if not chapters_file.exists():
            return None
            
        try:
            with open(chapters_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse chapter information (basic FFmpeg format parsing)
            chapters = []
            current_chapter = {}
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('[CHAPTER'):
                    if current_chapter:
                        chapters.append(current_chapter)
                    current_chapter = {}
                elif line.startswith('TIMEBASE='):
                    current_chapter['timebase'] = line.split('=')[1]
                elif line.startswith('START='):
                    current_chapter['start'] = int(line.split('=')[1])
                elif line.startswith('END='):
                    current_chapter['end'] = int(line.split('=')[1])
                elif line.startswith('title='):
                    current_chapter['title'] = line.split('=')[1]
            
            if current_chapter:
                chapters.append(current_chapter)
            
            if not chapters:
                return None
            
            # Create chapters table
            chapters_table = Table(title=f"📚 Detected Chapters ({len(chapters)} found)")
            chapters_table.add_column("Chapter", style="cyan", width=8)
            chapters_table.add_column("Start Time", style="green")
            chapters_table.add_column("Duration", style="yellow")
            chapters_table.add_column("Title", style="white")
            
            self.stats.chapters_detected = len(chapters)
            
            for i, chapter in enumerate(chapters, 1):
                try:
                    start_seconds = chapter.get('start', 0) / 1000  # Convert from milliseconds
                    end_seconds = chapter.get('end', 0) / 1000
                    duration = end_seconds - start_seconds
                    
                    start_time = self._format_duration(start_seconds)
                    duration_str = self._format_duration(duration)
                    title = chapter.get('title', f'Chapter {i}')
                    
                    chapters_table.add_row(
                        f"Ch {i:02d}",
                        start_time,
                        duration_str,
                        title
                    )
                except Exception:
                    chapters_table.add_row(
                        f"Ch {i:02d}",
                        "Unknown",
                        "Unknown", 
                        f"Chapter {i}"
                    )
            
            return chapters_table
            
        except Exception as e:
            self.log.warning(f"Could not parse chapters file: {e}")
            return None

    def process_video_enhanced(self, video_path: Path, options: Dict[str, Any]) -> Path:
        """Enhanced video processing with advanced progress tracking."""
        
        # Initialize stats
        self.stats.start_time = datetime.now()
        self.stats.input_file_size = video_path.stat().st_size
        
        # Setup paths
        base_name = video_path.stem
        output_dir = video_path.parent
        scenes_csv_file = output_dir / f"{base_name}-Scenes.csv"
        chapters_txt_file = output_dir / "chapters.txt"
        output_video_file = output_dir / f"{base_name}_with_chapters.mp4"
        
        # Start resource monitoring
        self._start_resource_monitoring()
        
        # Create main layout
        layout = self.create_main_layout()
        
        # Create progress bars with enhanced tracking
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
            
            # Create individual task progress bars
            overall_task = progress.add_task("🎬 Overall Progress", total=100)
            scene_task = progress.add_task("🔍 Scene Detection", total=100)
            convert_task = progress.add_task("🔄 Chapter Conversion", total=100)
            embed_task = progress.add_task("📁 Chapter Embedding", total=100)
            
            with Live(layout, console=self.console, refresh_per_second=4) as live:
                try:
                    # Update layout components
                    layout["header"].update(self.create_header_panel(video_path))
                    layout["progress"].update(self.create_progress_panel(progress))
                    layout["left"].update(self.create_video_info_table(video_path))
                    layout["resources"].update(self.create_resources_panel())
                    
                    # Step 1: Scene Detection
                    progress.update(overall_task, advance=25, description="🔍 Detecting scenes...")
                    scene_start = time.time()
                    
                    scenedetect_cmd = [
                        "scenedetect",
                        "-i", str(video_path),
                        "detect-content",
                        "-t", str(options.get('threshold', 30.0)),
                        "list-scenes"
                    ]
                    
                    self.run_command_with_progress(
                        scenedetect_cmd, 
                        "Analyzing video scenes",
                        progress, 
                        scene_task,
                        expected_duration=self.stats.input_file_size / (1024*1024*10)  # Rough estimate
                    )
                    
                    self.stats.scene_detection_time = time.time() - scene_start
                    
                    if not scenes_csv_file.exists():
                        raise FileNotFoundError("PySceneDetect did not create the expected CSV file")
                    
                    # Step 2: Chapter Conversion
                    progress.update(overall_task, advance=25, description="🔄 Converting to chapters...")
                    convert_start = time.time()
                    
                    chapconv_cmd = [
                        "chapconv",
                        "--input-format", "pyscenedetect",
                        str(scenes_csv_file),
                        "--output-format", "ffmpeg"
                    ]
                    
                    result = self.run_command_with_progress(
                        chapconv_cmd,
                        "Converting scene data to chapters",
                        progress,
                        convert_task,
                        expected_duration=2.0
                    )
                    
                    # Write chapters file
                    with open(chapters_txt_file, 'w', encoding='utf-8') as f:
                        f.write(result.stdout)
                    
                    self.stats.conversion_time = time.time() - convert_start
                    
                    # Update display with chapter information
                    chapters_table = self.create_chapters_table(chapters_txt_file)
                    if chapters_table:
                        layout["right"].update(Panel(
                            chapters_table,
                            title="[bold green]📚 Chapter Preview[/bold green]",
                            border_style="green"
                        ))
                    
                    # Step 3: Chapter Embedding
                    progress.update(overall_task, advance=40, description="📁 Embedding chapters...")
                    embed_start = time.time()
                    
                    # Get GPU acceleration arguments
                    _, _, gpu_ffmpeg_args = self.detect_gpu_with_display()
                    
                    ffmpeg_cmd = ["ffmpeg", "-y"]
                    if gpu_ffmpeg_args and options.get('quality') != 'fast':
                        ffmpeg_cmd.extend(gpu_ffmpeg_args)
                        self.stats.gpu_acceleration = True
                    
                    ffmpeg_cmd.extend([
                        "-i", str(video_path),
                        "-i", str(chapters_txt_file),
                        "-map_metadata", "1",
                        "-codec", "copy",
                        str(output_video_file)
                    ])
                    
                    self.run_command_with_progress(
                        ffmpeg_cmd,
                        "Embedding chapters into video",
                        progress,
                        embed_task,
                        expected_duration=self.stats.input_file_size / (1024*1024*20)  # Rough estimate
                    )
                    
                    self.stats.embedding_time = time.time() - embed_start
                    self.stats.output_file_size = output_video_file.stat().st_size
                    
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
                    self.stats.total_time = time.time() - self.stats.start_time.timestamp()
                    
                    # Final success display
                    self._show_completion_celebration(output_video_file)
                    
                except Exception as e:
                    # Error handling with cleanup
                    self._stop_resource_monitoring()
                    
                    for temp_file in [scenes_csv_file, chapters_txt_file]:
                        if temp_file.exists():
                            try:
                                temp_file.unlink()
                            except OSError:
                                pass
                    
                    raise
        
        self._stop_resource_monitoring()
        return output_video_file

    def _show_completion_celebration(self, output_video_file: Path):
        """Show animated completion celebration."""
        
        # Create stats summary
        stats_table = Table(title="📊 Processing Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Value", style="green")
        stats_table.add_column("Details", style="yellow")
        
        # File sizes
        input_size = decimal(self.stats.input_file_size)
        output_size = decimal(self.stats.output_file_size)
        size_diff = self.stats.output_file_size - self.stats.input_file_size
        
        stats_table.add_row("Input Size", str(input_size), "Original file")
        stats_table.add_row("Output Size", str(output_size), f"{'+' if size_diff > 0 else ''}{decimal(abs(size_diff))} difference")
        
        # Processing times
        if self.stats.scene_detection_time:
            stats_table.add_row("Scene Detection", f"{self.stats.scene_detection_time:.1f}s", "AI analysis time")
        if self.stats.conversion_time:
            stats_table.add_row("Chapter Conversion", f"{self.stats.conversion_time:.1f}s", "Format conversion")
        if self.stats.embedding_time:
            stats_table.add_row("Chapter Embedding", f"{self.stats.embedding_time:.1f}s", "Video processing")
        if self.stats.total_time:
            stats_table.add_row("Total Time", f"{self.stats.total_time:.1f}s", "End-to-end processing")
        
        # Processing details
        stats_table.add_row("Chapters Created", str(self.stats.chapters_detected), "Scene-based chapters")
        stats_table.add_row("Acceleration", "GPU" if self.stats.gpu_acceleration else "CPU", "Processing method")
        
        # Create final success panel
        success_content = Text()
        success_content.append("🎉 ", style="bold green")
        success_content.append("VIDEO PROCESSING COMPLETED SUCCESSFULLY!", style="bold green")
        success_content.append(" 🎉\n\n", style="bold green")
        
        success_content.append("📁 Output File:\n", style="bold cyan")
        success_content.append(f"   {output_video_file.name}\n", style="white")
        success_content.append(f"   {output_video_file.parent}\n\n", style="dim")
        
        success_content.append("🚀 Ready to enjoy your chapter-enhanced video!\n", style="bold yellow")
        success_content.append("   • Open in any video player\n", style="dim")
        success_content.append("   • Navigate between chapters easily\n", style="dim")
        success_content.append("   • Perfect for long-form content", style="dim")
        
        success_panel = Panel(
            Columns([
                Panel(success_content, border_style="green", title="🎬 Success"),
                Panel(stats_table, border_style="blue", title="📊 Statistics")
            ]),
            title="[bold green]🎉 PROCESSING COMPLETE 🎉[/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(success_panel)
        
        # Optional: Ask if user wants to open the file
        if Confirm.ask(f"\n[bold cyan]Open output directory?[/bold cyan]", default=False):
            try:
                import subprocess
                import platform
                
                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", str(output_video_file.parent)])
                elif platform.system() == "Windows":  # Windows
                    subprocess.run(["explorer", str(output_video_file.parent)])
                else:  # Linux and others
                    subprocess.run(["xdg-open", str(output_video_file.parent)])
            except Exception:
                self.console.print(f"[yellow]Could not open directory automatically. Location: {output_video_file.parent}[/yellow]")


# --- Main Application Entry Point ---

def main(video_path: Optional[str] = None):
    """
    Main function with enhanced TUI and interactive features.
    """
    console = Console()
    processor = EnhancedVideoProcessor(console)
    
    # Show enhanced startup banner
    startup_banner = Panel(
        Text.assemble(
            ("🎬 ", "bold blue"),
            ("VIDEO CHAPTER AUTOMATER", "bold blue"),
            (" v2.0 🎬\n", "bold blue"),
            ("Enhanced with Advanced Rich Components\n\n", "cyan"),
            ("✨ Features:\n", "bold yellow"),
            ("  • Real-time progress visualization\n", "white"),
            ("  • Interactive file selection\n", "white"),
            ("  • GPU acceleration detection\n", "white"),
            ("  • System resource monitoring\n", "white"),
            ("  • Advanced error handling\n", "white"),
            ("  • Chapter preview and statistics\n", "white"),
        ),
        title="[bold green]🚀 Enhanced Processing Engine[/bold green]",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(startup_banner)
    
    try:
        # Step 1: Get video file
        if video_path:
            video_file = Path(video_path)
            if not video_file.exists():
                console.print(f"[bold red]Error: Video file not found:[/bold red] {video_path}")
                return 1
        else:
            # Interactive file selection
            video_file = processor.show_interactive_file_dialog()
            if not video_file:
                console.print("[yellow]No file selected. Exiting.[/yellow]")
                return 0
        
        # Step 2: Show processing options
        options = processor.show_processing_options()
        
        # Step 3: Process video with enhanced tracking
        console.print(f"\n[bold green]🚀 Starting enhanced processing of:[/bold green] {video_file.name}")
        
        output_file = processor.process_video_enhanced(video_file, options)
        
        console.print(f"\n[bold green]✅ Successfully created:[/bold green] {output_file.name}")
        return 0
        
    except KeyboardInterrupt:
        console.print("\n[yellow]❌ Processing cancelled by user.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]❌ Processing failed:[/bold red] {e}")
        console.print_exception()
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enhanced Video Chapter Automater with Advanced Rich TUI",
        epilog="Example: python main.py my_video.mp4"
    )
    parser.add_argument(
        "video_file",
        nargs='?',
        help="Path to the input video file (optional - will prompt if not provided)"
    )
    parser.add_argument(
        "--gpu-info",
        action="store_true",
        help="Show GPU capabilities and exit"
    )
    parser.add_argument(
        "--config",
        action="store_true", 
        help="Show current configuration and exit"
    )
    
    args = parser.parse_args()
    
    if args.gpu_info:
        # Just show GPU info and exit
        console = Console()
        console.print(Panel("🎮 GPU Capabilities Detection", style="bold blue"))
        detect_gpu_capabilities()
        sys.exit(0)
    
    if args.config:
        # Show configuration and exit
        console = Console()
        processor = EnhancedVideoProcessor(console)
        
        config_table = Table(title="⚙️ Current Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")
        
        config_table.add_row("Config File", str(processor.config_file))
        config_table.add_row("GPU Preference", processor.preferences.gpu_preference)
        config_table.add_row("Output Format", processor.preferences.output_format)
        config_table.add_row("Cleanup Files", str(processor.preferences.cleanup_intermediate_files))
        config_table.add_row("Parallel Processing", str(processor.preferences.parallel_processing))
        config_table.add_row("Detection Threshold", str(processor.preferences.scene_detection_threshold))
        
        console.print(Panel(config_table, border_style="green"))
        sys.exit(0)
    
    # Run main application
    sys.exit(main(args.video_file))