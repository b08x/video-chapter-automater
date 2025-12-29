"""
System resource monitoring module for VideoChapterAutomater.

Provides real-time monitoring of CPU, memory, disk, and GPU resources
with Rich-based visualization. Harvested from main.py's advanced monitoring.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Optional

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class SystemResources:
    """
    Real-time system resource metrics.

    Attributes:
        cpu_percent: CPU utilization percentage (0-100)
        memory_percent: Memory utilization percentage (0-100)
        disk_usage: Disk utilization percentage (0-100)
        available_disk_gb: Available disk space in GB
        gpu_utilization: GPU utilization percentage (0-100, 0 if unavailable)
        temperature: GPU temperature in Celsius (0 if unavailable)
    """
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_usage: float = 0.0
    available_disk_gb: float = 0.0
    gpu_utilization: float = 0.0
    temperature: float = 0.0


class ResourceMonitor:
    """
    Background system resource monitor with Rich visualization.

    Monitors CPU, memory, disk, and GPU metrics in a background thread,
    providing real-time updates for display in Rich TUI applications.
    """

    def __init__(self, update_interval: float = 1.0):
        """
        Initialize resource monitor.

        Args:
            update_interval: Seconds between resource updates (default: 1.0)
        """
        self.update_interval = update_interval
        self.resources = SystemResources()
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self._gpu_available = self._check_gpu_availability()

    def _check_gpu_availability(self) -> bool:
        """
        Check if GPU monitoring is available.

        Returns:
            True if GPUtil can be imported, False otherwise
        """
        try:
            import GPUtil
            return True
        except ImportError:
            return False

    def start(self) -> None:
        """Start background resource monitoring."""
        if self._active:
            return  # Already running

        self._active = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ResourceMonitor"
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """
        Stop background resource monitoring.

        Args:
            timeout: Maximum seconds to wait for thread to stop
        """
        if not self._active:
            return  # Not running

        self._active = False
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while self._active:
            try:
                self._update_resources()
                time.sleep(self.update_interval)
            except Exception:
                # Silently handle monitoring errors, continue loop
                time.sleep(self.update_interval * 2)

    def _update_resources(self) -> None:
        """Update all resource metrics."""
        # CPU utilization
        self.resources.cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory utilization
        memory = psutil.virtual_memory()
        self.resources.memory_percent = memory.percent

        # Disk usage for current directory
        disk = psutil.disk_usage('.')
        self.resources.disk_usage = (disk.used / disk.total) * 100
        self.resources.available_disk_gb = disk.free / (1024**3)

        # GPU monitoring (if available)
        if self._gpu_available:
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    self.resources.gpu_utilization = gpus[0].load * 100
                    self.resources.temperature = gpus[0].temperature
                else:
                    self.resources.gpu_utilization = 0.0
                    self.resources.temperature = 0.0
            except Exception:
                # GPU monitoring failed, disable for this session
                self._gpu_available = False
                self.resources.gpu_utilization = 0.0
                self.resources.temperature = 0.0

    def get_resources(self) -> SystemResources:
        """
        Get current resource metrics.

        Returns:
            SystemResources dataclass with current metrics
        """
        return self.resources

    def create_panel(self) -> Panel:
        """
        Create Rich Panel with resource visualization.

        Returns:
            Panel containing resource metrics table
        """
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
        """
        Create colored text-based resource bar.

        Args:
            percent: Resource utilization percentage (0-100)

        Returns:
            Formatted Rich string with color-coded bar
        """
        bar_length = 10
        filled = int((percent / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        # Color based on utilization level
        if percent > 80:
            return f"[red]{bar}[/red]"
        elif percent > 60:
            return f"[yellow]{bar}[/yellow]"
        else:
            return f"[green]{bar}[/green]"

    def is_monitoring(self) -> bool:
        """
        Check if monitoring is active.

        Returns:
            True if monitoring thread is running
        """
        return self._active

    def __enter__(self):
        """Context manager entry - start monitoring."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop monitoring."""
        self.stop()
        return False

    def __repr__(self) -> str:
        """String representation of monitor."""
        status = "active" if self._active else "inactive"
        return f"ResourceMonitor(status={status}, interval={self.update_interval}s)"
