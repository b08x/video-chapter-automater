"""
Platform-aware directory resolution following XDG Base Directory Specification.

Provides cross-platform directory paths for configuration, data, and cache files
following platform conventions:
- Linux: XDG Base Directory Specification
- macOS: Apple File System Programming Guide
- Windows: Microsoft Known Folders
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PlatformType(Enum):
    """Supported platform types."""
    LINUX = "linux"
    MACOS = "darwin"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PlatformDirectories:
    """
    Platform-aware directory resolution following XDG Base Directory Specification.

    On Linux:
        - Respects XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_CACHE_HOME
        - Defaults: ~/.config, ~/.local/share, ~/.cache

    On macOS:
        - Follows Apple conventions with XDG override support
        - Defaults: ~/Library/Application Support, ~/Library/Caches

    On Windows:
        - Uses APPDATA, LOCALAPPDATA with XDG override support
        - Defaults: %APPDATA%, %LOCALAPPDATA%

    All paths are resolved to absolute pathlib.Path objects.

    Attributes:
        platform_type: Detected platform type
        config_home: Base directory for configuration files
        data_home: Base directory for data files
        cache_home: Base directory for cache files
    """

    platform_type: PlatformType
    config_home: Path
    data_home: Path
    cache_home: Path

    @classmethod
    def detect(cls) -> PlatformDirectories:
        """
        Detect current platform and resolve standard directories.

        Returns:
            PlatformDirectories with resolved paths for current platform

        Examples:
            >>> dirs = PlatformDirectories.detect()
            >>> print(dirs.config_home)
            PosixPath('/home/user/.config')
        """
        system = platform.system()

        if system == "Linux":
            return cls._linux_directories()
        elif system == "Darwin":
            return cls._macos_directories()
        elif system == "Windows":
            return cls._windows_directories()
        else:
            # Fallback to XDG-like structure for unknown platforms
            return cls._fallback_directories()

    @staticmethod
    def _resolve_xdg_path(env_var: str, default_path: Path) -> Path:
        """
        Resolve XDG path from environment variable with spec-compliant validation.

        Per XDG Base Directory Specification, relative paths in environment
        variables must be rejected and the default used instead.

        Args:
            env_var: Environment variable name (e.g., 'XDG_CONFIG_HOME')
            default_path: Default path to use if env var is unset or invalid

        Returns:
            Resolved absolute path

        Examples:
            >>> # Valid absolute path
            >>> os.environ['XDG_CONFIG_HOME'] = '/custom/config'
            >>> path = PlatformDirectories._resolve_xdg_path('XDG_CONFIG_HOME', Path.home() / '.config')
            >>> print(path)
            PosixPath('/custom/config')

            >>> # Relative path rejected per XDG spec
            >>> os.environ['XDG_CONFIG_HOME'] = '.config'
            >>> path = PlatformDirectories._resolve_xdg_path('XDG_CONFIG_HOME', Path.home() / '.config')
            >>> print(path)
            PosixPath('/home/user/.config')
        """
        env_value = os.environ.get(env_var)

        if env_value:
            path = Path(env_value)
            # XDG spec requirement: reject relative paths
            if path.is_absolute():
                return path.resolve()

        # Use default if env var not set or contains relative path
        return default_path.resolve()

    @classmethod
    def _linux_directories(cls) -> PlatformDirectories:
        """
        Linux XDG Base Directory implementation.

        Follows https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html
        """
        home = Path.home()

        config_home = cls._resolve_xdg_path("XDG_CONFIG_HOME", home / ".config")
        data_home = cls._resolve_xdg_path("XDG_DATA_HOME", home / ".local" / "share")
        cache_home = cls._resolve_xdg_path("XDG_CACHE_HOME", home / ".cache")

        return cls(
            platform_type=PlatformType.LINUX,
            config_home=config_home,
            data_home=data_home,
            cache_home=cache_home
        )

    @classmethod
    def _macos_directories(cls) -> PlatformDirectories:
        """
        macOS directory conventions.

        Follows Apple File System Programming Guide with XDG override support.
        """
        home = Path.home()
        library = home / "Library"

        # macOS respects XDG vars if set, else uses Apple conventions
        config_home = cls._resolve_xdg_path("XDG_CONFIG_HOME", library / "Application Support")
        data_home = cls._resolve_xdg_path("XDG_DATA_HOME", library / "Application Support")
        cache_home = cls._resolve_xdg_path("XDG_CACHE_HOME", library / "Caches")

        return cls(
            platform_type=PlatformType.MACOS,
            config_home=config_home,
            data_home=data_home,
            cache_home=cache_home
        )

    @classmethod
    def _windows_directories(cls) -> PlatformDirectories:
        """
        Windows directory conventions.

        Uses Windows environment variables with XDG override support.
        """
        # Windows can still respect XDG vars (e.g., in WSL/msys2)
        appdata = os.environ.get("APPDATA")
        localappdata = os.environ.get("LOCALAPPDATA")

        if appdata:
            config_default = Path(appdata)
            data_default = Path(appdata)
        else:
            # Fallback if APPDATA not set (unlikely but defensive)
            home = Path.home()
            config_default = home / "AppData" / "Roaming"
            data_default = home / "AppData" / "Roaming"

        if localappdata:
            cache_default = Path(localappdata)
        else:
            cache_default = Path.home() / "AppData" / "Local"

        config_home = cls._resolve_xdg_path("XDG_CONFIG_HOME", config_default)
        data_home = cls._resolve_xdg_path("XDG_DATA_HOME", data_default)
        cache_home = cls._resolve_xdg_path("XDG_CACHE_HOME", cache_default)

        return cls(
            platform_type=PlatformType.WINDOWS,
            config_home=config_home,
            data_home=data_home,
            cache_home=cache_home
        )

    @classmethod
    def _fallback_directories(cls) -> PlatformDirectories:
        """
        Fallback for unknown platforms.

        Uses XDG-like structure as a sensible default.
        """
        home = Path.home()

        config_home = cls._resolve_xdg_path("XDG_CONFIG_HOME", home / ".config")
        data_home = cls._resolve_xdg_path("XDG_DATA_HOME", home / ".local" / "share")
        cache_home = cls._resolve_xdg_path("XDG_CACHE_HOME", home / ".cache")

        return cls(
            platform_type=PlatformType.UNKNOWN,
            config_home=config_home,
            data_home=data_home,
            cache_home=cache_home
        )
