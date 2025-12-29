"""
Interactive Setup Wizard for Video Chapter Automater

A comprehensive TUI-based setup system that guides users through installation,
configuration, and system validation with rich visual feedback.
"""

import subprocess
import sys
import os
import json
import shutil
import platform
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.text import Text
from rich.tree import Tree
from rich.columns import Columns
from rich.status import Status

from .gpu_detection import GPUDetector, ProcessingMode, GPUVendor
from .app_paths import ApplicationPaths


class InstallationType(Enum):
    FULL = "full"
    STANDARD = "standard"
    DOCKER_ONLY = "docker_only"
    CUSTOM = "custom"


class SetupStep(Enum):
    WELCOME = "welcome"
    SYSTEM_CHECK = "system_check"
    GPU_DETECTION = "gpu_detection"
    INSTALLATION_TYPE = "installation_type"
    DEPENDENCY_INSTALL = "dependency_install"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    COMPLETE = "complete"


@dataclass
class UserPreferences:
    installation_type: InstallationType = InstallationType.STANDARD
    gpu_preference: str = "auto"  # auto, nvidia, intel, cpu
    output_format: str = "mp4"
    default_output_dir: Optional[str] = None
    enable_gpu_acceleration: bool = True
    scene_detection_threshold: float = 30.0
    cleanup_intermediate_files: bool = True
    parallel_processing: bool = True
    first_run: bool = True

    def __post_init__(self):
        """Validate configuration parameters."""
        # Validate scene_detection_threshold
        if self.scene_detection_threshold < 0:
            raise ValueError(
                f"scene_detection_threshold must be >= 0, got {self.scene_detection_threshold}"
            )

        # Validate output_format
        valid_formats = ["mp4", "mkv", "avi", "mov", "webm"]
        if self.output_format not in valid_formats:
            raise ValueError(
                f"output_format must be one of {valid_formats}, got '{self.output_format}'"
            )

        # Validate gpu_preference
        valid_gpu_prefs = ["auto", "nvidia", "intel", "cpu"]
        if self.gpu_preference not in valid_gpu_prefs:
            raise ValueError(
                f"gpu_preference must be one of {valid_gpu_prefs}, got '{self.gpu_preference}'"
            )

    def save(self, config_path: Path) -> None:
        """Save preferences to JSON file."""
        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, config_path: Path) -> "UserPreferences":
        """Load preferences from JSON file."""
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()


class SetupWizard:
    """Interactive setup wizard with Rich TUI components."""

    def __init__(self):
        self.console = Console()
        self.app_paths = ApplicationPaths.for_current_platform()
        self.config_dir = self.app_paths.config_dir
        self.config_file = self.app_paths.config_file
        self.preferences = UserPreferences.load(self.config_file)
        self.gpu_detector = GPUDetector()
        self.current_step = SetupStep.WELCOME

        # Virtual environment detection
        self.project_root = Path.cwd()
        self.venv_path = self.project_root / ".venv"
        self.in_venv = self._detect_virtual_environment()
        self.venv_python = self._get_venv_python()
        self.venv_pip = self._get_venv_pip()

        # System requirements
        self.required_python = (3, 8)
        self.required_tools = ["ffmpeg", "scenedetect"]
        self.optional_tools = ["nvcc", "intel_gpu_top", "clinfo"]

        # Installation status tracking
        self.system_requirements_met = False
        self.gpu_capabilities = None
        self.installation_successful = False

    def _detect_virtual_environment(self) -> bool:
        """Detect if we're running in a virtual environment."""
        # Check if VIRTUAL_ENV is set
        if os.environ.get('VIRTUAL_ENV'):
            return True
        
        # Check if .venv directory exists and has proper structure
        if self.venv_path.exists() and (self.venv_path / "bin" / "python").exists():
            return True
            
        return False

    def _get_venv_python(self) -> Optional[str]:
        """Get the Python executable for the virtual environment."""
        if self.venv_path.exists():
            python_path = self.venv_path / "bin" / "python"
            if python_path.exists():
                return str(python_path)
        return None

    def _get_venv_pip(self) -> Optional[str]:
        """Get the pip executable for the virtual environment."""
        if self.venv_python:
            # Use python -m pip to ensure we use the right pip
            return f"{self.venv_python} -m pip"
        return None

    def _ensure_pip_in_venv(self) -> bool:
        """Ensure pip is installed in the virtual environment.

        Returns:
            bool: True if pip is available, False otherwise
        """
        if not self.venv_python:
            return False

        # Check if pip is already available
        try:
            result = subprocess.run(
                [self.venv_python, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try to install pip using ensurepip (standard library module)
        try:
            subprocess.run(
                [self.venv_python, "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                check=True,
                timeout=60
            )
            # Verify pip is now available
            result = subprocess.run(
                [self.venv_python, "-m", "pip", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # If uv is available, try using it to install pip
        if shutil.which("uv"):
            try:
                subprocess.run(
                    ["uv", "pip", "install", "--python", self.venv_python, "pip"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=60
                )
                # Verify pip is now available
                result = subprocess.run(
                    [self.venv_python, "-m", "pip", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                pass

        return False

    def run(self) -> bool:
        """Run the complete setup wizard."""
        self.console.clear()

        try:
            # Step 1: Welcome Screen
            if not self._show_welcome():
                return False

            # Step 2: System Requirements Check
            self.current_step = SetupStep.SYSTEM_CHECK
            if not self._check_system_requirements():
                return False

            # Step 3: GPU Detection
            self.current_step = SetupStep.GPU_DETECTION
            self._detect_and_display_gpu()

            # Step 4: Installation Type Selection
            self.current_step = SetupStep.INSTALLATION_TYPE
            self._select_installation_type()

            # Step 5: Dependency Installation
            self.current_step = SetupStep.DEPENDENCY_INSTALL
            if not self._install_dependencies():
                return False

            # Step 6: Configuration
            self.current_step = SetupStep.CONFIGURATION
            self._configure_preferences()

            # Step 7: Final Validation
            self.current_step = SetupStep.VALIDATION
            if not self._validate_installation():
                return False

            # Step 8: Completion
            self.current_step = SetupStep.COMPLETE
            self._show_completion()

            return True

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Setup cancelled by user.[/yellow]")
            return False
        except Exception as e:
            self.console.print(
                f"\n[bold red]Setup failed with error:[/bold red] {e}")
            return False

    def _show_welcome(self) -> bool:
        """Display welcome screen with ASCII art and project info."""
        ascii_art = """
        ╔══════════════════════════════════════════════════════════════╗
        ║  🎬 VIDEO CHAPTER AUTOMATER SETUP WIZARD 🎬                 ║
        ║                                                              ║
        ║     █████  ██    ██ ████████  ██████                        ║
        ║    ██   ██ ██    ██    ██    ██    ██                       ║
        ║    ███████ ██    ██    ██    ██    ██                       ║
        ║    ██   ██ ██    ██    ██    ██    ██                       ║
        ║    ██   ██  ██████     ██     ██████                        ║
        ║                                                              ║
        ║         Automatic Chapter Generation for Videos              ║
        ║         Powered by AI Scene Detection & GPU Acceleration    ║
        ╚══════════════════════════════════════════════════════════════╝
        """

        welcome_panel = Panel(
            ascii_art,
            title="[bold blue]Welcome to Video Chapter Automater[/bold blue]",
            border_style="blue",
            padding=(1, 2)
        )

        self.console.print(welcome_panel)
        self.console.print()

        # Project overview
        overview_content = Text()
        overview_content.append("🚀 What this tool does:\n", style="bold green")
        overview_content.append(
            "  • Automatically detects scene changes in videos\n")
        overview_content.append(
            "  • Generates chapter markers for better navigation\n")
        overview_content.append(
            "  • Supports GPU acceleration (NVIDIA & Intel)\n")
        overview_content.append(
            "  • Creates professional chapter-enabled videos\n\n")

        overview_content.append("🔧 System Integration:\n", style="bold yellow")
        overview_content.append(
            "  • Uses PySceneDetect for AI-powered scene analysis\n")
        overview_content.append("  • Leverages FFmpeg for video processing\n")
        overview_content.append(
            "  • Optimizes performance with GPU acceleration\n")
        overview_content.append("  • Modern Python packaging with uv\n\n")

        overview_content.append("📋 This wizard will:\n", style="bold cyan")
        overview_content.append("  ✓ Check your system requirements\n")
        overview_content.append("  ✓ Detect and configure GPU capabilities\n")
        overview_content.append("  ✓ Install required dependencies\n")
        overview_content.append("  ✓ Set up your preferences\n")
        overview_content.append("  ✓ Validate the complete installation\n")

        overview_panel = Panel(
            overview_content,
            title="[bold green]Setup Overview[/bold green]",
            border_style="green"
        )

        self.console.print(overview_panel)

        # Virtual environment status
        if self.venv_path.exists():
            if self.in_venv:
                venv_status = "[bold green]✅ Virtual environment active and detected[/bold green]"
            else:
                venv_status = "[bold yellow]⚠️ Virtual environment found but not active - will be used automatically[/bold yellow]"
        else:
            venv_status = "[bold blue]ℹ️ No virtual environment found - will install to system or create one[/bold blue]"
        
        self.console.print(f"\n{venv_status}")

        # First-run detection
        if self.preferences.first_run:
            self.console.print(
                "\n[bold yellow]👋 Welcome! This appears to be your first time running the setup.[/bold yellow]")
        else:
            self.console.print(
                f"\n[dim]Previous configuration found. This will update your existing setup.[/dim]")

        return Confirm.ask("\n[bold]Ready to begin the setup process?[/bold]", default=True)

    def _check_system_requirements(self) -> bool:
        """Check and display system requirements with detailed feedback."""
        self.console.print(Panel(
            "🔍 Analyzing System Compatibility",
            title="[bold cyan]System Requirements Check[/bold cyan]",
            border_style="cyan"
        ))

        # Create requirements table
        req_table = Table(title="System Requirements Analysis")
        req_table.add_column("Component", style="cyan", width=25)
        req_table.add_column("Required", style="yellow", width=15)
        req_table.add_column("Found", style="green", width=20)
        req_table.add_column("Status", style="bold", width=15)

        all_requirements_met = True

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:

            # Check Python version
            task = progress.add_task("Checking Python version...", total=None)
            python_version = sys.version_info[:2]
            python_ok = python_version >= self.required_python

            req_table.add_row(
                "Python Version",
                f">= {'.'.join(map(str, self.required_python))}",
                f"{'.'.join(map(str, python_version))}",
                "✅ OK" if python_ok else "❌ FAIL"
            )

            if not python_ok:
                all_requirements_met = False
            progress.update(task, completed=True)

            # Check platform
            task = progress.add_task(
                "Checking platform compatibility...", total=None)
            platform_name = platform.system()
            platform_ok = platform_name in ["Linux", "Darwin", "Windows"]

            req_table.add_row(
                "Platform",
                "Linux/macOS/Windows",
                platform_name,
                "✅ OK" if platform_ok else "❌ UNSUPPORTED"
            )

            if not platform_ok:
                all_requirements_met = False
            progress.update(task, completed=True)

            # Check required tools
            for tool in self.required_tools:
                task = progress.add_task(f"Checking {tool}...", total=None)
                tool_path = shutil.which(tool)
                tool_ok = tool_path is not None

                req_table.add_row(
                    tool,
                    "Required",
                    tool_path or "Not found",
                    "✅ OK" if tool_ok else "❌ MISSING"
                )

                if not tool_ok:
                    all_requirements_met = False
                progress.update(task, completed=True)

            # Check optional tools
            for tool in self.optional_tools:
                task = progress.add_task(
                    f"Checking {tool} (optional)...", total=None)
                tool_path = shutil.which(tool)

                req_table.add_row(
                    f"{tool} (optional)",
                    "Optional",
                    tool_path or "Not found",
                    "✅ Available" if tool_path else "➖ Optional"
                )
                progress.update(task, completed=True)

        self.console.print(req_table)

        # Show detailed results
        if all_requirements_met:
            self.console.print(Panel(
                "✅ All system requirements met! Ready to proceed.",
                title="[bold green]Requirements Check Passed[/bold green]",
                border_style="green"
            ))
            self.system_requirements_met = True
            return True
        else:
            # Show installation instructions for missing components
            missing_panel = Panel(
                self._get_installation_instructions(),
                title="[bold red]Missing Requirements[/bold red]",
                border_style="red"
            )
            self.console.print(missing_panel)

            if Confirm.ask("\n[bold yellow]Would you like to continue anyway?[/bold yellow] (Some features may not work)", default=False):
                return True
            else:
                return False

    def _get_installation_instructions(self) -> str:
        """Generate installation instructions for missing components."""
        instructions = "Please install the missing components:\n\n"

        if not shutil.which("ffmpeg"):
            if platform.system() == "Linux":
                instructions += "📦 FFmpeg (Ubuntu/Debian): sudo apt install ffmpeg\n"
                instructions += "📦 FFmpeg (CentOS/RHEL): sudo yum install ffmpeg\n"
                instructions += "📦 FFmpeg (Arch): sudo pacman -S ffmpeg\n"
            elif platform.system() == "Darwin":
                instructions += "📦 FFmpeg (macOS): brew install ffmpeg\n"
            elif platform.system() == "Windows":
                instructions += "📦 FFmpeg (Windows): Download from https://ffmpeg.org/download.html\n"
            instructions += "\n"

        if not shutil.which("scenedetect"):
            instructions += "🐍 PySceneDetect: pip install scenedetect[opencv]\n"
            instructions += "🐍 Or with uv: uv add scenedetect[opencv]\n\n"

        instructions += "🔄 Run this setup wizard again after installing missing components."

        return instructions

    def _detect_and_display_gpu(self) -> None:
        """Detect GPU capabilities and display comprehensive results."""
        self.console.print(Panel(
            "🎮 Analyzing Graphics Processing Capabilities",
            title="[bold magenta]GPU Detection & Analysis[/bold magenta]",
            border_style="magenta"
        ))

        with Status("Scanning for GPU hardware...", console=self.console):
            detected_gpus = self.gpu_detector.detect_all_gpus()

        # Display detailed GPU information
        if detected_gpus:
            gpu_table = Table(title="Detected Graphics Hardware")
            gpu_table.add_column("Vendor", style="cyan")
            gpu_table.add_column("Model", style="green")
            gpu_table.add_column("Memory", style="blue")
            gpu_table.add_column("Driver", style="yellow")
            gpu_table.add_column("Capabilities", style="magenta")
            gpu_table.add_column("Status", style="bold")

            for gpu in detected_gpus:
                memory = f"{gpu.memory_mb} MB" if gpu.memory_mb else "Unknown"
                driver = gpu.driver_version or "Unknown"

                # Determine capabilities
                capabilities = []
                if gpu.vendor == GPUVendor.NVIDIA:
                    capabilities.append("CUDA")
                    if gpu.cuda_version:
                        capabilities.append(f"CUDA {gpu.cuda_version}")
                if gpu.vendor == GPUVendor.INTEL:
                    if gpu.opencl_support:
                        capabilities.append("OpenCL")
                    capabilities.append("VAAPI")

                caps_str = ", ".join(capabilities) if capabilities else "Basic"

                status = "🚀 Selected" if gpu == self.gpu_detector.selected_gpu else "Available"

                gpu_table.add_row(
                    gpu.vendor.value.upper(),
                    gpu.name,
                    memory,
                    driver,
                    caps_str,
                    status
                )

            self.console.print(gpu_table)

            # Show processing mode
            mode_info = {
                ProcessingMode.NVIDIA_GPU: ("🚀 NVIDIA GPU Acceleration", "Optimal performance for video processing", "green"),
                ProcessingMode.INTEL_GPU: ("⚡ Intel GPU Acceleration", "Good performance with hardware acceleration", "yellow"),
                ProcessingMode.CPU_ONLY: (
                    "💻 CPU Processing", "Standard performance, no GPU acceleration", "red")
            }

            mode_text, mode_desc, mode_color = mode_info[self.gpu_detector.processing_mode]

            mode_panel = Panel(
                f"{mode_text}\n{mode_desc}",
                title="[bold]Selected Processing Mode[/bold]",
                border_style=mode_color
            )
            self.console.print(mode_panel)

        else:
            no_gpu_panel = Panel(
                "No dedicated GPUs detected. Processing will use CPU only.\n"
                "This is normal for many systems and will still work well.",
                title="[bold yellow]GPU Detection Results[/bold yellow]",
                border_style="yellow"
            )
            self.console.print(no_gpu_panel)

        self.gpu_capabilities = {
            "detected_gpus": len(detected_gpus),
            "processing_mode": self.gpu_detector.processing_mode.value,
            "selected_gpu": self.gpu_detector.selected_gpu.name if self.gpu_detector.selected_gpu else None
        }

    def _select_installation_type(self) -> None:
        """Interactive installation type selection."""
        self.console.print(Panel(
            "🎯 Choose Installation Type",
            title="[bold blue]Installation Configuration[/bold blue]",
            border_style="blue"
        ))

        # Create installation options table
        install_table = Table(title="Installation Options")
        install_table.add_column("Type", style="cyan", width=15)
        install_table.add_column("Description", style="green", width=40)
        install_table.add_column("Includes", style="yellow", width=30)
        install_table.add_column("Best For", style="magenta", width=25)

        install_table.add_row(
            "Full",
            "Complete installation with all features",
            "GPU support, dev tools, optional deps",
            "Power users, developers"
        )
        install_table.add_row(
            "Standard",
            "Recommended for most users",
            "Core functionality, GPU support",
            "Regular usage"
        )
        install_table.add_row(
            "Docker Only",
            "Container-based deployment",
            "Pre-configured environment",
            "Docker users"
        )
        install_table.add_row(
            "Custom",
            "Select specific components",
            "User-defined selection",
            "Advanced users"
        )

        self.console.print(install_table)

        # Get user selection
        choices = {
            "1": InstallationType.FULL,
            "2": InstallationType.STANDARD,
            "3": InstallationType.DOCKER_ONLY,
            "4": InstallationType.CUSTOM
        }

        choice = Prompt.ask(
            "\n[bold]Select installation type[/bold]",
            choices=list(choices.keys()),
            default="2"
        )

        self.preferences.installation_type = choices[choice]

        # Custom installation additional prompts
        if self.preferences.installation_type == InstallationType.CUSTOM:
            self._configure_custom_installation()

    def _configure_custom_installation(self) -> None:
        """Configure custom installation options."""
        self.console.print(Panel(
            "🔧 Custom Installation Configuration",
            title="[bold yellow]Custom Setup[/bold yellow]",
            border_style="yellow"
        ))

        # GPU support
        self.preferences.enable_gpu_acceleration = Confirm.ask(
            "Enable GPU acceleration support?",
            default=True
        )

        # Development tools
        install_dev_tools = Confirm.ask(
            "Install development tools (testing, linting, etc.)?",
            default=False
        )

        if install_dev_tools:
            self.preferences.installation_type = InstallationType.FULL

    def _install_dependencies(self) -> bool:
        """Install dependencies with progress tracking and error handling."""
        self.console.print(Panel(
            "📦 Installing Dependencies",
            title="[bold green]Package Installation[/bold green]",
            border_style="green"
        ))

        if self.preferences.installation_type == InstallationType.DOCKER_ONLY:
            return self._setup_docker_environment()

        # Determine packages to install
        packages_to_install = self._get_package_list()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:

            main_task = progress.add_task(
                "Installing packages...",
                total=len(packages_to_install)
            )

            for i, (package_name, package_spec) in enumerate(packages_to_install):
                task = progress.add_task(
                    f"Installing {package_name}...", total=None)

                try:
                    install_result = self._install_package(package_spec)
                    if install_result:
                        progress.update(
                            task, description=f"✅ {package_name} installed")
                    else:
                        progress.update(
                            task, description=f"❌ {package_name} failed")

                        # Provide more helpful error information
                        error_msg = f"Failed to install {package_name}"
                        if package_name == "Rich TUI Library" and self._is_package_installed("rich"):
                            progress.update(task, description=f"✅ {package_name} already available")
                            continue

                        # Stop progress display before interactive prompt
                        progress.stop()

                        self.console.print(f"\n[red]{error_msg}[/red]")

                        # Display captured installation errors for debugging
                        if hasattr(self, '_last_install_error') and self._last_install_error:
                            self.console.print("\n[yellow]Installation attempts:[/yellow]")
                            # Show last 3 attempts to avoid overwhelming output
                            for error in self._last_install_error[-3:]:
                                method = error.get('method', 'Unknown method')
                                self.console.print(f"  [dim]→ {method}[/dim]")

                                if 'stderr' in error and error['stderr']:
                                    # Truncate long error messages
                                    stderr_preview = error['stderr'][:300]
                                    if len(error['stderr']) > 300:
                                        stderr_preview += "..."
                                    self.console.print(f"    [dim red]{stderr_preview}[/dim red]")

                                if 'error' in error:
                                    self.console.print(f"    [dim red]{error['error']}[/dim red]")

                                if 'returncode' in error:
                                    self.console.print(f"    [dim]Exit code: {error['returncode']}[/dim]")

                        # Show installation suggestions
                        if not self.in_venv and self.venv_path.exists():
                            self.console.print("[yellow]Suggestion: Try running this setup from within the virtual environment:[/yellow]")
                            self.console.print(f"[dim]source .venv/bin/activate && python -m video_chapter_automater.setup_wizard[/dim]")

                        if not Confirm.ask(f"Continue without {package_name}?", default=True):
                            return False

                        # Resume progress display
                        progress.start()

                except Exception as e:
                    # Stop progress display before interactive prompt
                    progress.stop()

                    self.console.print(
                        f"[red]Unexpected error installing {package_name}: {e}[/red]")

                    if not Confirm.ask(f"Continue without {package_name}?", default=True):
                        return False

                    # Resume progress display
                    progress.start()

                progress.update(main_task, advance=1)

        self.installation_successful = True
        self.console.print(Panel(
            "✅ All dependencies installed successfully!",
            title="[bold green]Installation Complete[/bold green]",
            border_style="green"
        ))

        return True

    def _get_package_list(self) -> List[Tuple[str, str]]:
        """Get list of packages to install based on configuration."""
        packages = [
            ("Rich TUI Library", "rich"),
            ("Scene Detection", "scenedetect[opencv]>=0.6.0")]

        if self.preferences.installation_type in [InstallationType.FULL, InstallationType.STANDARD]:
            if self.preferences.enable_gpu_acceleration:
                packages.extend([
                    ("OpenCV with GPU",
                     "opencv-python-headless[contrib]>=4.6.0"),
                ])

                # NVIDIA-specific packages
                if any(gpu.vendor == GPUVendor.NVIDIA for gpu in self.gpu_detector.detected_gpus):
                    packages.append(
                        ("NVIDIA GPU Tools", "nvidia-ml-py>=11.0.0"))

                # Intel-specific packages
                if any(gpu.vendor == GPUVendor.INTEL for gpu in self.gpu_detector.detected_gpus):
                    packages.append(
                        ("Intel GPU Tools", "intel-extension-for-pytorch"))

        if self.preferences.installation_type == InstallationType.FULL:
            packages.extend([
                ("Testing Framework", "pytest>=7.0.0"),
                ("Code Formatting", "black>=22.0.0"),
                ("Import Sorting", "isort>=5.10.0"),
                ("Type Checking", "mypy>=1.0.0"),
            ])

        return packages

    def _install_package(self, package_spec: str) -> bool:
        """Install a single package using virtual environment-aware methods.

        Returns:
            bool: True if installation succeeded, False otherwise

        Note:
            Stores last error in self._last_install_error for debugging
        """
        # First check if package is already installed
        if self._is_package_installed(package_spec.split(">=")[0].split("==")[0]):
            return True

        # Ensure pip is available in the virtual environment
        if self.venv_python and not self._ensure_pip_in_venv():
            # If we can't get pip installed, fall back to system installation methods
            pass

        # Try different installation methods in order of preference
        installation_methods = []

        # If we have virtual environment, prefer venv-specific methods
        if self.venv_python and self.venv_pip:
            # Method 1: uv pip install (most reliable for uv-managed projects)
            if shutil.which("uv"):
                installation_methods.append([
                    "uv", "pip", "install", package_spec
                ])

            # Method 2: uv pip install with explicit python (if method 1 fails)
            if shutil.which("uv"):
                installation_methods.append([
                    "uv", "pip", "install", "--python", self.venv_python, package_spec
                ])

            # Method 3: Direct venv pip (fallback)
            installation_methods.append(
                self.venv_pip.split() + ["install", package_spec]
            )

        # Method 3: Try uv add (but only if we have pyproject.toml)
        if (self.project_root / "pyproject.toml").exists() and shutil.which("uv"):
            installation_methods.append(["uv", "add", package_spec])

        # Method 4: Fallback to system pip (last resort)
        installation_methods.append([
            sys.executable, "-m", "pip", "install", package_spec
        ])

        # Track errors for debugging
        errors = []

        for method in installation_methods:
            try:
                result = subprocess.run(
                    method,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=self.project_root
                )
                # Verify installation was successful
                package_name = package_spec.split(">=")[0].split("==")[0].split("[")[0]
                if self._is_package_installed(package_name):
                    return True
            except subprocess.CalledProcessError as e:
                errors.append({
                    "method": " ".join(method),
                    "returncode": e.returncode,
                    "stderr": e.stderr.strip() if e.stderr else "",
                    "stdout": e.stdout.strip() if e.stdout else ""
                })
                continue
            except FileNotFoundError as e:
                errors.append({
                    "method": " ".join(method),
                    "error": f"Command not found: {e}"
                })
                continue

        # Store last error for debugging
        self._last_install_error = errors
        return False

    def _is_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed in the virtual environment."""
        try:
            if self.venv_python:
                # Check in virtual environment
                result = subprocess.run(
                    [self.venv_python, "-c", f"import {package_name.replace('-', '_')}"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return True
            else:
                # Check in current environment
                result = subprocess.run(
                    [sys.executable, "-c", f"import {package_name.replace('-', '_')}"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Try alternative import names for common packages
            alt_names = {
                "scenedetect": "scenedetect",
                "opencv-python": "cv2",
                "opencv-python-headless": "cv2",
                "rich": "rich",
                "nvidia-ml-py": "pynvml",
                "intel-extension-for-pytorch": "intel_extension_for_pytorch"
            }
            
            if package_name in alt_names:
                try:
                    python_exe = self.venv_python or sys.executable
                    result = subprocess.run(
                        [python_exe, "-c", f"import {alt_names[package_name]}"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    return True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    pass
            
            return False

    def _setup_docker_environment(self) -> bool:
        """Set up Docker-based environment."""
        self.console.print(Panel(
            "🐳 Setting up Docker Environment",
            title="[bold blue]Docker Setup[/bold blue]",
            border_style="blue"
        ))

        # Check if Docker is available
        if not shutil.which("docker"):
            self.console.print(
                "[red]Docker is not installed or not in PATH.[/red]")
            self.console.print(
                "Please install Docker from: https://docs.docker.com/get-docker/")
            return False

        # Check if Docker daemon is running
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            self.console.print("[red]Docker daemon is not running.[/red]")
            return False

        dockerfile_content = '''
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    ffmpeg \\
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy source code
COPY src/ ./src/

# Set entry point
ENTRYPOINT ["uv", "run", "python", "-m", "video_chapter_automater"]
'''

        # Write Dockerfile if it doesn't exist
        dockerfile_path = Path.cwd() / "Dockerfile"
        if not dockerfile_path.exists():
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)

        self.console.print("✅ Docker environment configured successfully!")
        return True

    def _configure_preferences(self) -> None:
        """Configure user preferences with interactive prompts."""
        self.console.print(Panel(
            "⚙️ Configuring Preferences",
            title="[bold cyan]User Configuration[/bold cyan]",
            border_style="cyan"
        ))

        # GPU preference
        if self.gpu_capabilities and self.gpu_capabilities["detected_gpus"] > 0:
            gpu_options = ["auto", "nvidia", "intel", "cpu"]
            if self.gpu_detector.processing_mode == ProcessingMode.NVIDIA_GPU:
                default_gpu = "nvidia"
            elif self.gpu_detector.processing_mode == ProcessingMode.INTEL_GPU:
                default_gpu = "intel"
            else:
                default_gpu = "auto"

            self.preferences.gpu_preference = Prompt.ask(
                "GPU processing preference",
                choices=gpu_options,
                default=default_gpu
            )

        # Output format
        self.preferences.output_format = Prompt.ask(
            "Default output format",
            choices=["mp4", "mkv", "avi"],
            default="mp4"
        )

        # Default output directory
        current_default = self.preferences.default_output_dir or str(
            Path.cwd())
        new_output_dir = Prompt.ask(
            "Default output directory",
            default=current_default
        )

        if Path(new_output_dir).exists():
            self.preferences.default_output_dir = new_output_dir
        else:
            if Confirm.ask(f"Directory {new_output_dir} does not exist. Create it?"):
                Path(new_output_dir).mkdir(parents=True, exist_ok=True)
                self.preferences.default_output_dir = new_output_dir

        # Scene detection threshold
        self.preferences.scene_detection_threshold = float(Prompt.ask(
            "Scene detection sensitivity (higher = more chapters)",
            default=str(self.preferences.scene_detection_threshold)
        ))

        # Advanced options
        if Confirm.ask("Configure advanced options?", default=False):
            self.preferences.cleanup_intermediate_files = Confirm.ask(
                "Clean up intermediate files after processing?",
                default=self.preferences.cleanup_intermediate_files
            )

            self.preferences.parallel_processing = Confirm.ask(
                "Enable parallel processing when possible?",
                default=self.preferences.parallel_processing
            )

        # Save preferences
        self.app_paths.ensure_config_dir()
        self.preferences.first_run = False
        self.preferences.save(self.config_file)

        self.console.print(Panel(
            f"Configuration saved to: {self.config_file}",
            title="[bold green]Preferences Saved[/bold green]",
            border_style="green"
        ))

    def _validate_installation(self) -> bool:
        """Perform comprehensive installation validation."""
        self.console.print(Panel(
            "🔍 Validating Installation",
            title="[bold yellow]Installation Validation[/bold yellow]",
            border_style="yellow"
        ))

        validation_tasks = [
            ("Import core modules", self._test_imports),
            ("Test GPU detection", self._test_gpu_detection),
            ("Validate FFmpeg integration", self._test_ffmpeg),
            ("Check scene detection", self._test_scene_detection),
        ]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:

            all_tests_passed = True

            for test_name, test_func in validation_tasks:
                task = progress.add_task(
                    f"Testing {test_name.lower()}...", total=None)

                try:
                    if test_func():
                        progress.update(task, description=f"✅ {test_name}")
                    else:
                        progress.update(task, description=f"❌ {test_name}")
                        all_tests_passed = False
                except Exception as e:
                    progress.update(
                        task, description=f"❌ {test_name} - {str(e)}")
                    all_tests_passed = False

        if all_tests_passed:
            self.console.print(Panel(
                "🎉 All validation tests passed! Installation is ready to use.",
                title="[bold green]Validation Successful[/bold green]",
                border_style="green"
            ))
            return True
        else:
            self.console.print(Panel(
                "⚠️ Some validation tests failed. Check the installation and try again.",
                title="[bold red]Validation Issues Found[/bold red]",
                border_style="red"
            ))

            return Confirm.ask("Continue anyway?", default=False)

    def _test_imports(self) -> bool:
        """Test importing core modules."""
        try:
            from . import gpu_detection, main
            import scenedetect
            import rich
            return True
        except ImportError:
            return False

    def _test_gpu_detection(self) -> bool:
        """Test GPU detection functionality."""
        try:
            detector = GPUDetector()
            detector.detect_all_gpus()
            return True
        except Exception:
            return False

    def _test_ffmpeg(self) -> bool:
        """Test FFmpeg availability and basic functionality."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                check=True
            )
            return "ffmpeg version" in result.stdout.lower()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _test_scene_detection(self) -> bool:
        """Test scene detection functionality."""
        try:
            result = subprocess.run(
                ["scenedetect", "--help"],
                capture_output=True,
                text=True,
                check=True
            )
            return "scenedetect" in result.stdout.lower()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _show_completion(self) -> None:
        """Display completion screen with next steps."""
        completion_art = """
        ┌───────────────────────────────────────────────────────────────┐
        │  🎉 SETUP COMPLETED SUCCESSFULLY! 🎉                        │
        │                                                               │
        │     Your Video Chapter Automater is ready to use!            │
        │                                                               │
        │  ██████  ██████  ███    ██ ███████                          │
        │  ██   ██ ██    ██ ████   ██ ██                               │
        │  ██   ██ ██    ██ ██ ██  ██ █████                           │
        │  ██   ██ ██    ██ ██  ██ ██ ██                               │
        │  ██████   ██████  ██   ████ ███████                         │
        └───────────────────────────────────────────────────────────────┘
        """

        completion_panel = Panel(
            completion_art,
            title="[bold green]🎬 Setup Complete[/bold green]",
            border_style="green",
            padding=(1, 2)
        )

        self.console.print(completion_panel)

        # Show configuration summary
        summary_content = Text()
        summary_content.append("📋 Installation Summary:\n", style="bold blue")
        summary_content.append(
            f"  • Installation Type: {self.preferences.installation_type.value.title()}\n")
        summary_content.append(
            f"  • GPU Processing: {self.preferences.gpu_preference.upper()}\n")
        summary_content.append(
            f"  • Output Format: {self.preferences.output_format.upper()}\n")
        summary_content.append(f"  • Configuration: {self.config_file}\n\n")

        summary_content.append("🚀 Next Steps:\n", style="bold green")
        summary_content.append(
            "  1. Run: video-chapter-automater your_video.mp4\n")
        summary_content.append(
            "  2. Or use the short form: vca your_video.mp4\n")
        summary_content.append(
            "  3. Check the output in your video directory\n\n")

        summary_content.append("💡 Helpful Commands:\n", style="bold yellow")
        summary_content.append(
            "  • vca --help              Show all options\n")
        summary_content.append(
            "  • vca --gpu-info          Display GPU status\n")
        summary_content.append(
            "  • vca --config             Show configuration\n")
        summary_content.append(
            "  • python -m video_chapter_automater.setup_wizard  Run setup again\n\n")

        summary_content.append(
            "📖 Documentation: https://github.com/your-org/video-chapter-automater", style="dim")

        summary_panel = Panel(
            summary_content,
            title="[bold cyan]Ready to Process Videos![/bold cyan]",
            border_style="cyan"
        )

        self.console.print(summary_panel)


def main():
    """Main entry point for the setup wizard."""
    wizard = SetupWizard()
    success = wizard.run()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
