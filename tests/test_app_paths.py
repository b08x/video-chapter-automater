"""Tests for application path management."""

import os
import platform
from pathlib import Path
from unittest import mock

import pytest

from video_chapter_automater.app_paths import ApplicationPaths, APP_NAME
from video_chapter_automater.platform_dirs import PlatformDirectories, PlatformType


class TestApplicationPaths:
    """Test application-specific path resolution."""

    def test_for_current_platform_creates_instance(self):
        """Test factory method creates ApplicationPaths instance."""
        app_paths = ApplicationPaths.for_current_platform()
        assert isinstance(app_paths, ApplicationPaths)
        assert isinstance(app_paths.platform_dirs, PlatformDirectories)

    def test_config_dir_uses_app_name(self):
        """Test config_dir appends application name."""
        app_paths = ApplicationPaths.for_current_platform()
        assert app_paths.config_dir.name == APP_NAME

    def test_config_file_points_to_json(self):
        """Test config_file points to config.json."""
        app_paths = ApplicationPaths.for_current_platform()
        assert app_paths.config_file.name == "config.json"
        assert app_paths.config_file.parent == app_paths.config_dir

    def test_data_dir_uses_app_name(self):
        """Test data_dir appends application name."""
        app_paths = ApplicationPaths.for_current_platform()
        assert app_paths.data_dir.name == APP_NAME

    def test_cache_dir_uses_app_name(self):
        """Test cache_dir appends application name."""
        app_paths = ApplicationPaths.for_current_platform()
        assert app_paths.cache_dir.name == APP_NAME

    def test_all_paths_are_absolute(self):
        """Test all paths are absolute."""
        app_paths = ApplicationPaths.for_current_platform()
        assert app_paths.config_dir.is_absolute()
        assert app_paths.config_file.is_absolute()
        assert app_paths.data_dir.is_absolute()
        assert app_paths.cache_dir.is_absolute()

    def test_linux_config_path(self):
        """Test Linux config path structure."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="Linux"):
                app_paths = ApplicationPaths.for_current_platform()
                expected = Path.home() / ".config" / APP_NAME
                assert app_paths.config_dir == expected

    def test_macos_config_path(self):
        """Test macOS config path structure."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="Darwin"):
                app_paths = ApplicationPaths.for_current_platform()
                expected = Path.home() / "Library" / "Application Support" / APP_NAME
                assert app_paths.config_dir == expected

    def test_windows_config_path(self):
        """Test Windows config path structure."""
        appdata = "C:\\Users\\Test\\AppData\\Roaming"
        with mock.patch.dict(os.environ, {"APPDATA": appdata}, clear=True):
            with mock.patch("platform.system", return_value="Windows"):
                app_paths = ApplicationPaths.for_current_platform()
                expected = Path(appdata) / APP_NAME
                assert app_paths.config_dir == expected

    def test_xdg_config_home_override(self):
        """Test XDG_CONFIG_HOME override works across platforms."""
        custom_config = "/custom/config"
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_config}):
            for system_name in ["Linux", "Darwin", "Windows"]:
                with mock.patch("platform.system", return_value=system_name):
                    app_paths = ApplicationPaths.for_current_platform()
                    expected = Path(custom_config) / APP_NAME
                    assert app_paths.config_dir == expected

    def test_ensure_config_dir_creates_directory(self, tmp_path):
        """Test ensure_config_dir creates the directory."""
        app_paths = ApplicationPaths.for_testing(tmp_path)
        config_dir = app_paths.ensure_config_dir()

        assert config_dir.exists()
        assert config_dir.is_dir()
        assert config_dir == app_paths.config_dir

    def test_ensure_config_dir_idempotent(self, tmp_path):
        """Test ensure_config_dir can be called multiple times."""
        app_paths = ApplicationPaths.for_testing(tmp_path)

        # First call creates directory
        config_dir1 = app_paths.ensure_config_dir()
        assert config_dir1.exists()

        # Second call should succeed without error
        config_dir2 = app_paths.ensure_config_dir()
        assert config_dir2.exists()
        assert config_dir1 == config_dir2

    def test_ensure_data_dir_creates_directory(self, tmp_path):
        """Test ensure_data_dir creates the directory."""
        app_paths = ApplicationPaths.for_testing(tmp_path)
        data_dir = app_paths.ensure_data_dir()

        assert data_dir.exists()
        assert data_dir.is_dir()
        assert data_dir == app_paths.data_dir

    def test_ensure_cache_dir_creates_directory(self, tmp_path):
        """Test ensure_cache_dir creates the directory."""
        app_paths = ApplicationPaths.for_testing(tmp_path)
        cache_dir = app_paths.ensure_cache_dir()

        assert cache_dir.exists()
        assert cache_dir.is_dir()
        assert cache_dir == app_paths.cache_dir

    def test_for_testing_uses_tmp_path(self, tmp_path):
        """Test for_testing factory creates paths under tmp_path."""
        app_paths = ApplicationPaths.for_testing(tmp_path)

        # All paths should be under tmp_path
        assert tmp_path in app_paths.config_dir.parents or tmp_path == app_paths.config_dir.parent
        assert tmp_path in app_paths.data_dir.parents or tmp_path == app_paths.data_dir.parent
        assert tmp_path in app_paths.cache_dir.parents or tmp_path == app_paths.cache_dir.parent

    def test_for_testing_with_platform_override(self, tmp_path):
        """Test for_testing with explicit platform type."""
        app_paths = ApplicationPaths.for_testing(tmp_path, platform_type="linux")
        assert app_paths.platform_dirs.platform_type == PlatformType.LINUX

    def test_config_file_within_config_dir(self):
        """Test config_file is properly nested in config_dir."""
        app_paths = ApplicationPaths.for_current_platform()
        assert app_paths.config_dir in app_paths.config_file.parents

    def test_different_base_directories(self):
        """Test that config, data, and cache can have different base dirs."""
        # On Linux, these should be different
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch("platform.system", return_value="Linux"):
                app_paths = ApplicationPaths.for_current_platform()

                config_base = app_paths.config_dir.parent
                data_base = app_paths.data_dir.parent
                cache_base = app_paths.cache_dir.parent

                # On Linux: ~/.config, ~/.local/share, ~/.cache
                assert config_base.name == ".config"
                assert data_base.name == "share"
                assert cache_base.name == ".cache"

    def test_ensure_creates_parent_directories(self, tmp_path):
        """Test ensure methods create full directory tree."""
        app_paths = ApplicationPaths.for_testing(tmp_path)

        # Config directory should be created even if parents don't exist
        config_dir = app_paths.ensure_config_dir()
        assert config_dir.exists()

        # Parent should also exist
        assert config_dir.parent.exists()
