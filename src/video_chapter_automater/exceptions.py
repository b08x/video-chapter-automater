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