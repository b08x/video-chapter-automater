"""
GPU Detection Module for Video Chapter Automater
Detects available GPUs (NVIDIA and Intel) and adapts processing accordingly.
"""

import subprocess
import sys
import platform
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

class GPUVendor(Enum):
    NVIDIA = "nvidia"
    INTEL = "intel"
    UNKNOWN = "unknown"

class ProcessingMode(Enum):
    NVIDIA_GPU = "nvidia_gpu"
    INTEL_GPU = "intel_gpu" 
    CPU_ONLY = "cpu_only"

@dataclass
class GPUInfo:
    vendor: GPUVendor
    name: str
    memory_mb: Optional[int] = None
    driver_version: Optional[str] = None
    cuda_version: Optional[str] = None
    opencl_support: bool = False

class GPUDetector:
    """Detects and manages GPU capabilities for video processing."""
    
    def __init__(self):
        self.detected_gpus: List[GPUInfo] = []
        self.processing_mode = ProcessingMode.CPU_ONLY
        self.selected_gpu: Optional[GPUInfo] = None
        
    def detect_all_gpus(self) -> List[GPUInfo]:
        """Detect all available GPUs on the system."""
        self.detected_gpus = []
        
        # Check for NVIDIA GPUs
        nvidia_gpus = self._detect_nvidia_gpus()
        self.detected_gpus.extend(nvidia_gpus)
        
        # Check for Intel GPUs
        intel_gpus = self._detect_intel_gpus()
        self.detected_gpus.extend(intel_gpus)
        
        # Determine best processing mode
        self._determine_processing_mode()
        
        return self.detected_gpus
    
    def _detect_nvidia_gpus(self) -> List[GPUInfo]:
        """Detect NVIDIA GPUs using nvidia-smi."""
        nvidia_gpus = []
        
        try:
            # Check if nvidia-smi is available
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse nvidia-smi output
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split(', ')
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        try:
                            memory_mb = int(parts[1].strip())
                        except (ValueError, IndexError):
                            memory_mb = None
                        try:
                            driver_version = parts[2].strip() if len(parts) > 2 else None
                        except IndexError:
                            driver_version = None
                        
                        # Get CUDA version if available
                        cuda_version = self._get_cuda_version()
                        
                        gpu_info = GPUInfo(
                            vendor=GPUVendor.NVIDIA,
                            name=name,
                            memory_mb=memory_mb,
                            driver_version=driver_version,
                            cuda_version=cuda_version
                        )
                        nvidia_gpus.append(gpu_info)
                        
        except (subprocess.CalledProcessError, FileNotFoundError):
            # nvidia-smi not found or failed
            pass
            
        return nvidia_gpus
    
    def _detect_intel_gpus(self) -> List[GPUInfo]:
        """Detect Intel GPUs using various methods."""
        intel_gpus = []
        
        # Try Intel GPU Top (intel_gpu_top) if available
        try:
            result = subprocess.run(
                ["intel_gpu_top", "-l"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True
            )
            
            # Intel GPU found if command succeeds
            gpu_info = GPUInfo(
                vendor=GPUVendor.INTEL,
                name="Intel GPU (detected)",
                opencl_support=self._check_opencl_support()
            )
            intel_gpus.append(gpu_info)
            
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Alternative: Check lspci for Intel graphics
        if not intel_gpus:
            try:
                result = subprocess.run(
                    ["lspci", "-nn"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                for line in result.stdout.split('\n'):
                    if 'VGA compatible controller' in line and 'Intel' in line:
                        # Extract GPU name from lspci output
                        parts = line.split(': ')
                        if len(parts) > 1:
                            name = parts[1].split('[')[0].strip()
                        else:
                            name = "Intel GPU"
                            
                        gpu_info = GPUInfo(
                            vendor=GPUVendor.INTEL,
                            name=name,
                            opencl_support=self._check_opencl_support()
                        )
                        intel_gpus.append(gpu_info)
                        break
                        
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        return intel_gpus
    
    def _get_cuda_version(self) -> Optional[str]:
        """Get CUDA version if available."""
        try:
            result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse CUDA version from nvcc output
            for line in result.stdout.split('\n'):
                if 'release' in line.lower():
                    import re
                    match = re.search(r'release (\d+\.\d+)', line)
                    if match:
                        return match.group(1)
                        
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        return None
    
    def _check_opencl_support(self) -> bool:
        """Check if OpenCL is available."""
        try:
            result = subprocess.run(
                ["clinfo"],
                capture_output=True,
                text=True,
                check=True
            )
            return "Platform" in result.stdout
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _determine_processing_mode(self) -> None:
        """Determine the best processing mode based on detected GPUs."""
        # Prioritize NVIDIA GPUs for video processing
        nvidia_gpus = [gpu for gpu in self.detected_gpus if gpu.vendor == GPUVendor.NVIDIA]
        if nvidia_gpus:
            self.processing_mode = ProcessingMode.NVIDIA_GPU
            self.selected_gpu = nvidia_gpus[0]  # Use first NVIDIA GPU
            return
            
        # Fall back to Intel GPU if available
        intel_gpus = [gpu for gpu in self.detected_gpus if gpu.vendor == GPUVendor.INTEL]
        if intel_gpus and intel_gpus[0].opencl_support:
            self.processing_mode = ProcessingMode.INTEL_GPU
            self.selected_gpu = intel_gpus[0]
            return
            
        # Default to CPU processing
        self.processing_mode = ProcessingMode.CPU_ONLY
        self.selected_gpu = None
    
    def get_ffmpeg_gpu_args(self) -> List[str]:
        """Get FFmpeg arguments for GPU acceleration based on detected hardware."""
        if self.processing_mode == ProcessingMode.NVIDIA_GPU:
            return [
                "-hwaccel", "cuda",
                "-hwaccel_output_format", "cuda"
            ]
        elif self.processing_mode == ProcessingMode.INTEL_GPU:
            return [
                "-hwaccel", "vaapi",
                "-hwaccel_device", "/dev/dri/renderD128"
            ]
        else:
            return []  # CPU-only processing
    
    def get_scenedetect_backend(self) -> str:
        """Get the appropriate backend for PySceneDetect."""
        if self.processing_mode == ProcessingMode.NVIDIA_GPU:
            return "opencv"  # OpenCV with CUDA support
        elif self.processing_mode == ProcessingMode.INTEL_GPU:
            return "opencv"  # OpenCV (may use OpenCL)
        else:
            return "opencv"  # Default OpenCV backend
    
    def display_gpu_info(self) -> None:
        """Display detected GPU information in a nice format."""
        if not self.detected_gpus:
            console.print(Panel(
                "❌ No GPUs detected - using CPU-only processing",
                title="[bold yellow]GPU Detection Results[/bold yellow]",
                border_style="yellow"
            ))
            return
        
        # Create table for GPU information
        table = Table(title="Detected GPUs")
        table.add_column("Vendor", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Memory", style="blue")
        table.add_column("Driver", style="magenta")
        table.add_column("Status", style="yellow")
        
        for gpu in self.detected_gpus:
            memory_str = f"{gpu.memory_mb} MB" if gpu.memory_mb else "Unknown"
            driver_str = gpu.driver_version or "Unknown"
            
            if gpu == self.selected_gpu:
                status = "✅ Selected"
            else:
                status = "🔍 Available"
                
            table.add_row(
                gpu.vendor.value.upper(),
                gpu.name,
                memory_str,
                driver_str,
                status
            )
        
        console.print(table)
        
        # Display processing mode
        mode_messages = {
            ProcessingMode.NVIDIA_GPU: "🚀 Using NVIDIA GPU acceleration",
            ProcessingMode.INTEL_GPU: "⚡ Using Intel GPU acceleration", 
            ProcessingMode.CPU_ONLY: "💻 Using CPU-only processing"
        }
        
        console.print(Panel(
            mode_messages[self.processing_mode],
            title="[bold green]Processing Mode[/bold green]",
            border_style="green"
        ))

def detect_gpu_capabilities() -> Tuple[ProcessingMode, Optional[GPUInfo], List[str]]:
    """
    Convenience function to detect GPU capabilities and return processing configuration.
    
    Returns:
        Tuple of (processing_mode, selected_gpu, ffmpeg_args)
    """
    detector = GPUDetector()
    detector.detect_all_gpus()
    detector.display_gpu_info()
    
    return (
        detector.processing_mode,
        detector.selected_gpu,
        detector.get_ffmpeg_gpu_args()
    )

if __name__ == "__main__":
    # Demo the GPU detection
    console.print(Panel(
        "🎬 GPU Detection Demo for Video Chapter Automater",
        title="[bold blue]System Analysis[/bold blue]",
        border_style="blue"
    ))
    
    detect_gpu_capabilities()