"""
Application-specific path management for VideoChapterAutomater.

Provides a single source of truth for all application paths (config, data, cache)
built on top of platform-aware directory resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .platform_dirs import PlatformDirectories, PlatformType


APP_NAME = "video-chapter-automater"


@dataclass
class ApplicationPaths:
    """
    Application-specific path management.

    Provides a single source of truth for all VideoChapterAutomater paths:
    - Configuration files (config.json, preferences)
    - Data files (models, templates - future use)
    - Cache files (temp processing, thumbnails - future use)

    All paths are lazy-created on first access to avoid unnecessary I/O.

    Attributes:
        platform_dirs: Platform-specific base directories
        app_name: Application name for path construction

    Examples:
        >>> app_paths = ApplicationPaths.for_current_platform()
        >>> config_file = app_paths.config_file
        >>> print(config_file)
        PosixPath('/home/user/.config/video-chapter-automater/config.json')
    """

    platform_dirs: PlatformDirectories
    app_name: str = APP_NAME

    # Config paths
    @property
    def config_dir(self) -> Path:
        """
        Application configuration directory.

        Returns:
            Path to config directory (not guaranteed to exist)

        Examples:
            Linux: ~/.config/video-chapter-automater
            macOS: ~/Library/Application Support/video-chapter-automater
            Windows: %APPDATA%/video-chapter-automater
        """
        return self.platform_dirs.config_home / self.app_name

    @property
    def config_file(self) -> Path:
        """
        Main configuration file path.

        Returns:
            Path to config.json (not guaranteed to exist)
        """
        return self.config_dir / "config.json"

    # Data paths (for future use)
    @property
    def data_dir(self) -> Path:
        """
        Application data directory.

        For persistent application data like models, templates, etc.

        Returns:
            Path to data directory (not guaranteed to exist)

        Examples:
            Linux: ~/.local/share/video-chapter-automater
            macOS: ~/Library/Application Support/video-chapter-automater
            Windows: %APPDATA%/video-chapter-automater
        """
        return self.platform_dirs.data_home / self.app_name

    # Cache paths (for future use)
    @property
    def cache_dir(self) -> Path:
        """
        Application cache directory.

        For temporary files, processing artifacts, thumbnails, etc.

        Returns:
            Path to cache directory (not guaranteed to exist)

        Examples:
            Linux: ~/.cache/video-chapter-automater
            macOS: ~/Library/Caches/video-chapter-automater
            Windows: %LOCALAPPDATA%/video-chapter-automater
        """
        return self.platform_dirs.cache_home / self.app_name

    def ensure_config_dir(self) -> Path:
        """
        Ensure configuration directory exists.

        Creates directory with parents if it doesn't exist.
        Uses mode 0o755 (rwxr-xr-x) on Unix-like systems.

        Returns:
            Absolute path to config directory

        Examples:
            >>> app_paths = ApplicationPaths.for_current_platform()
            >>> config_dir = app_paths.ensure_config_dir()
            >>> assert config_dir.exists()
        """
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        return self.config_dir

    def ensure_data_dir(self) -> Path:
        """
        Ensure data directory exists (for future use).

        Creates directory with parents if it doesn't exist.

        Returns:
            Absolute path to data directory
        """
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        return self.data_dir

    def ensure_cache_dir(self) -> Path:
        """
        Ensure cache directory exists (for future use).

        Creates directory with parents if it doesn't exist.

        Returns:
            Absolute path to cache directory
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
        return self.cache_dir

    @classmethod
    def for_current_platform(cls) -> ApplicationPaths:
        """
        Create ApplicationPaths for the current platform.

        This is the primary factory method for normal usage.
        Automatically detects the platform and uses appropriate defaults.

        Returns:
            ApplicationPaths configured for current platform

        Examples:
            >>> app_paths = ApplicationPaths.for_current_platform()
            >>> config = app_paths.config_file
        """
        return cls(platform_dirs=PlatformDirectories.detect())

    @classmethod
    def for_testing(
        cls,
        tmp_path: Path,
        platform_type: Optional[str] = None
    ) -> ApplicationPaths:
        """
        Create ApplicationPaths for testing with custom base directory.

        Useful for pytest fixtures and unit tests. All paths will be
        rooted under tmp_path instead of system directories.

        Args:
            tmp_path: Base directory for all app paths (e.g., pytest tmp_path)
            platform_type: Override platform detection (for cross-platform tests)

        Returns:
            ApplicationPaths using tmp_path as base

        Examples:
            >>> def test_config(tmp_path):
            ...     app_paths = ApplicationPaths.for_testing(tmp_path)
            ...     config_dir = app_paths.ensure_config_dir()
            ...     assert config_dir.exists()
            ...     assert tmp_path in config_dir.parents
        """
        # Create custom PlatformDirectories using tmp_path
        custom_dirs = PlatformDirectories(
            platform_type=PlatformType(platform_type) if platform_type else PlatformType.LINUX,
            config_home=tmp_path / "config",
            data_home=tmp_path / "data",
            cache_home=tmp_path / "cache"
        )

        return cls(platform_dirs=custom_dirs)
