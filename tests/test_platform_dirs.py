"""Tests for platform directory resolution."""

import os
import platform
from pathlib import Path
from unittest import mock

import pytest

from video_chapter_automater.platform_dirs import (
    PlatformDirectories,
    PlatformType
)


class TestPlatformDirectories:
    """Test platform-aware directory resolution."""

    def test_detect_returns_platform_directories(self):
        """Test that detect() returns a PlatformDirectories instance."""
        dirs = PlatformDirectories.detect()
        assert isinstance(dirs, PlatformDirectories)
        assert isinstance(dirs.config_home, Path)
        assert isinstance(dirs.data_home, Path)
        assert isinstance(dirs.cache_home, Path)

    def test_all_paths_are_absolute(self):
        """Test that all returned paths are absolute."""
        dirs = PlatformDirectories.detect()
        assert dirs.config_home.is_absolute()
        assert dirs.data_home.is_absolute()
        assert dirs.cache_home.is_absolute()

    def test_linux_directories_default(self):
        """Test Linux XDG defaults without environment variables."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="Linux"):
                dirs = PlatformDirectories.detect()

                assert dirs.platform_type == PlatformType.LINUX
                assert dirs.config_home == Path.home() / ".config"
                assert dirs.data_home == Path.home() / ".local" / "share"
                assert dirs.cache_home == Path.home() / ".cache"

    def test_linux_directories_with_xdg_config_home(self):
        """Test Linux respects XDG_CONFIG_HOME."""
        custom_config = "/custom/config"
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_config}):
            with mock.patch("platform.system", return_value="Linux"):
                dirs = PlatformDirectories.detect()
                assert dirs.config_home == Path(custom_config).resolve()

    def test_linux_directories_with_all_xdg_vars(self):
        """Test Linux respects all XDG environment variables."""
        env_vars = {
            "XDG_CONFIG_HOME": "/custom/config",
            "XDG_DATA_HOME": "/custom/data",
            "XDG_CACHE_HOME": "/custom/cache"
        }
        with mock.patch.dict(os.environ, env_vars):
            with mock.patch("platform.system", return_value="Linux"):
                dirs = PlatformDirectories.detect()

                assert dirs.config_home == Path("/custom/config")
                assert dirs.data_home == Path("/custom/data")
                assert dirs.cache_home == Path("/custom/cache")

    def test_macos_directories_default(self):
        """Test macOS uses Library directories by default."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="Darwin"):
                dirs = PlatformDirectories.detect()

                assert dirs.platform_type == PlatformType.MACOS
                expected_config = Path.home() / "Library" / "Application Support"
                expected_cache = Path.home() / "Library" / "Caches"

                assert dirs.config_home == expected_config
                assert dirs.data_home == expected_config
                assert dirs.cache_home == expected_cache

    def test_macos_respects_xdg_override(self):
        """Test macOS respects XDG_CONFIG_HOME if set."""
        custom_config = "/custom/config"
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_config}):
            with mock.patch("platform.system", return_value="Darwin"):
                dirs = PlatformDirectories.detect()
                assert dirs.config_home == Path(custom_config)

    def test_windows_directories_default(self):
        """Test Windows uses APPDATA directories."""
        appdata = "C:\\Users\\Test\\AppData\\Roaming"
        localappdata = "C:\\Users\\Test\\AppData\\Local"

        env_vars = {
            "APPDATA": appdata,
            "LOCALAPPDATA": localappdata
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            with mock.patch("platform.system", return_value="Windows"):
                dirs = PlatformDirectories.detect()

                assert dirs.platform_type == PlatformType.WINDOWS
                assert dirs.config_home == Path(appdata)
                assert dirs.data_home == Path(appdata)
                assert dirs.cache_home == Path(localappdata)

    def test_windows_fallback_without_appdata(self):
        """Test Windows fallback when APPDATA not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="Windows"):
                dirs = PlatformDirectories.detect()

                expected_appdata = Path.home() / "AppData" / "Roaming"
                expected_local = Path.home() / "AppData" / "Local"

                assert dirs.config_home == expected_appdata
                assert dirs.cache_home == expected_local

    def test_windows_respects_xdg_override(self):
        """Test Windows respects XDG_CONFIG_HOME if set."""
        custom_config = "/custom/config"
        env_vars = {
            "XDG_CONFIG_HOME": custom_config,
            "APPDATA": "C:\\Users\\Test\\AppData\\Roaming"
        }

        with mock.patch.dict(os.environ, env_vars):
            with mock.patch("platform.system", return_value="Windows"):
                dirs = PlatformDirectories.detect()
                assert dirs.config_home == Path(custom_config)

    def test_unknown_platform_uses_xdg_fallback(self):
        """Test unknown platforms use XDG-like structure."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="FreeBSD"):
                dirs = PlatformDirectories.detect()

                assert dirs.platform_type == PlatformType.UNKNOWN
                assert dirs.config_home == Path.home() / ".config"
                assert dirs.data_home == Path.home() / ".local" / "share"
                assert dirs.cache_home == Path.home() / ".cache"

    def test_frozen_dataclass(self):
        """Test that PlatformDirectories is immutable."""
        dirs = PlatformDirectories.detect()

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            dirs.config_home = Path("/new/path")
