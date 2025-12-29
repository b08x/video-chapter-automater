"""Custom exceptions for Video Chapter Automater."""

from __future__ import annotations


class VideoChapterAutomaterError(Exception):
    """Base exception for all Video Chapter Automater errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CommandExecutionError(VideoChapterAutomaterError):
    """Exception raised when external command execution fails."""

    def __init__(self, command: str, exit_code: int, stderr: str) -> None:
        message = f"Command '{command}' failed with exit code {exit_code}"
        super().__init__(message)
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr


class FileNotFoundError(VideoChapterAutomaterError):
    """Exception raised when required files are not found."""

    def __init__(self, file_path: str, context: str = "") -> None:
        message = f"File not found: {file_path}"
        if context:
            message += f" ({context})"
        super().__init__(message)
        self.file_path = file_path
        self.context = context


class DependencyError(VideoChapterAutomaterError):
    """Exception raised when required system dependencies are missing."""

    def __init__(self, dependency: str, suggestion: str = "") -> None:
        message = f"Missing dependency: {dependency}"
        if suggestion:
            message += f". {suggestion}"
        super().__init__(message)
        self.dependency = dependency
        self.suggestion = suggestion


# Preprocessing-specific exceptions

class PreprocessingError(VideoChapterAutomaterError):
    """Base exception for preprocessing operations."""
    pass


class GPUEncodingError(PreprocessingError):
    """Exception raised when GPU video encoding fails."""

    def __init__(self, codec: str, gpu_type: str, error_details: str = "") -> None:
        message = f"GPU encoding failed for codec '{codec}' on {gpu_type}"
        if error_details:
            message += f": {error_details}"
        super().__init__(message)
        self.codec = codec
        self.gpu_type = gpu_type
        self.error_details = error_details


class AudioExtractionError(PreprocessingError):
    """Exception raised when audio extraction fails."""

    def __init__(self, video_path: str, details: str = "") -> None:
        message = f"Audio extraction failed for '{video_path}'"
        if details:
            message += f": {details}"
        super().__init__(message)
        self.video_path = video_path
        self.details = details


class SceneExtractionError(PreprocessingError):
    """Exception raised when scene image extraction fails."""

    def __init__(self, video_path: str, scene_number: int, details: str = "") -> None:
        message = f"Scene extraction failed for '{video_path}' (scene {scene_number})"
        if details:
            message += f": {details}"
        super().__init__(message)
        self.video_path = video_path
        self.scene_number = scene_number
        self.details = details


class DeduplicationError(PreprocessingError):
    """Exception raised during image deduplication."""

    def __init__(self, details: str) -> None:
        message = f"Image deduplication failed: {details}"
        super().__init__(message)
        self.details = details


class InvalidConfigurationError(PreprocessingError):
    """Exception raised when preprocessing configuration is invalid."""

    def __init__(self, config_param: str, reason: str) -> None:
        message = f"Invalid configuration for '{config_param}': {reason}"
        super().__init__(message)
        self.config_param = config_param
        self.reason = reason