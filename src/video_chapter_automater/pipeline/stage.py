"""
Pipeline stage execution module for VideoChapterAutomater.

Defines individual stage execution units and result handling within
multi-stage preprocessing pipelines.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict

from ..preprocessing.base import PreprocessingOperation, PreprocessingResult
from ..preprocessing.audio_extractor import AudioExtractor
from ..preprocessing.video_encoder import VideoEncoder
from ..preprocessing.scene_extractor import SceneExtractor
from .config import PipelineStage, StageConfig


class StageStatus(Enum):
    """
    Status of a pipeline stage.

    Attributes:
        PENDING: Stage has not started
        RUNNING: Stage is currently executing
        COMPLETED: Stage completed successfully
        FAILED: Stage failed with error
        SKIPPED: Stage was skipped due to configuration or dependency failure
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """
    Result from executing a single pipeline stage.

    Attributes:
        stage: Stage type that was executed
        status: Execution status
        duration: Time taken in seconds
        preprocessing_result: Result from preprocessing operation
        error_message: Error details if stage failed
        metadata: Additional stage-specific metadata
    """
    stage: PipelineStage
    status: StageStatus
    duration: float = 0.0
    preprocessing_result: Optional[PreprocessingResult] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if stage completed successfully."""
        return self.status == StageStatus.COMPLETED

    @property
    def output_path(self) -> Optional[Path]:
        """Get output path from preprocessing result."""
        if self.preprocessing_result:
            return self.preprocessing_result.output_path
        return None

    def __repr__(self) -> str:
        """String representation of stage result."""
        return (
            f"StageResult("
            f"stage={self.stage.value}, "
            f"status={self.status.value}, "
            f"duration={self.duration:.2f}s)"
        )


class Stage:
    """
    Represents a single executable stage in a preprocessing pipeline.

    Encapsulates the logic for executing a specific preprocessing operation
    with proper error handling, timing, and result tracking.
    """

    # Map stage types to operation classes
    STAGE_OPERATIONS = {
        PipelineStage.VIDEO_ENCODING: VideoEncoder,
        PipelineStage.AUDIO_EXTRACTION: AudioExtractor,
        PipelineStage.SCENE_EXTRACTION: SceneExtractor,
    }

    def __init__(self, stage_config: StageConfig, verbose: bool = False):
        """
        Initialize pipeline stage.

        Args:
            stage_config: Configuration for this stage
            verbose: Enable verbose output
        """
        self.config = stage_config
        self.verbose = verbose
        self.status = StageStatus.PENDING
        self.operation = self._create_operation()

    def _create_operation(self) -> PreprocessingOperation:
        """
        Create preprocessing operation instance for this stage.

        Returns:
            PreprocessingOperation instance

        Raises:
            ValueError: If stage type is not supported
        """
        operation_class = self.STAGE_OPERATIONS.get(self.config.stage)

        if operation_class is None:
            raise ValueError(
                f"Unsupported stage type: {self.config.stage}. "
                f"Supported: {list(self.STAGE_OPERATIONS.keys())}"
            )

        # Instantiate operation with verbose flag
        if operation_class == VideoEncoder:
            return operation_class(verbose=self.verbose, interactive=True)
        else:
            return operation_class(verbose=self.verbose)

    def execute(
        self,
        input_path: Path,
        output_dir: Optional[Path] = None,
        **kwargs
    ) -> StageResult:
        """
        Execute this pipeline stage.

        Args:
            input_path: Path to input file
            output_dir: Directory for outputs (stage-specific handling)
            **kwargs: Additional arguments passed to operation

        Returns:
            StageResult with execution details
        """
        if not self.config.enabled:
            return StageResult(
                stage=self.config.stage,
                status=StageStatus.SKIPPED,
                metadata={"reason": "Stage disabled in configuration"}
            )

        start_time = time.time()
        self.status = StageStatus.RUNNING

        try:
            # Execute preprocessing operation
            result = self._execute_operation(input_path, output_dir, **kwargs)

            # Create successful stage result
            duration = time.time() - start_time
            self.status = StageStatus.COMPLETED

            return StageResult(
                stage=self.config.stage,
                status=StageStatus.COMPLETED,
                duration=duration,
                preprocessing_result=result,
                metadata={
                    "input_path": str(input_path),
                    "output_path": str(result.output_path) if result.output_path else None,
                }
            )

        except Exception as e:
            # Handle stage failure
            duration = time.time() - start_time
            self.status = StageStatus.FAILED

            error_msg = f"{type(e).__name__}: {str(e)}"

            if self.verbose:
                import traceback
                error_msg += f"\n{traceback.format_exc()}"

            return StageResult(
                stage=self.config.stage,
                status=StageStatus.FAILED,
                duration=duration,
                error_message=error_msg,
                metadata={
                    "input_path": str(input_path),
                    "exception_type": type(e).__name__,
                }
            )

    def _execute_operation(
        self,
        input_path: Path,
        output_dir: Optional[Path],
        **kwargs
    ) -> PreprocessingResult:
        """
        Execute the specific preprocessing operation.

        Args:
            input_path: Path to input file
            output_dir: Directory for outputs
            **kwargs: Additional arguments

        Returns:
            PreprocessingResult from operation
        """
        # Get stage configuration
        stage_config = self.config.config

        # Execute based on stage type
        if self.config.stage == PipelineStage.VIDEO_ENCODING:
            # Video encoding: requires codec name
            codec = kwargs.get('codec', 'h264_nvenc')
            return self.operation.execute(input_path, stage_config, codec_name=codec)

        elif self.config.stage == PipelineStage.AUDIO_EXTRACTION:
            # Audio extraction: uses default output path
            return self.operation.execute(input_path, stage_config)

        elif self.config.stage == PipelineStage.SCENE_EXTRACTION:
            # Scene extraction: requires output directory
            return self.operation.execute(input_path, stage_config, output_dir=output_dir)

        else:
            raise ValueError(f"Unknown stage type: {self.config.stage}")

    def estimate_duration(self, input_path: Path) -> float:
        """
        Estimate execution duration for this stage.

        Args:
            input_path: Path to input file

        Returns:
            Estimated duration in seconds
        """
        if not self.config.enabled:
            return 0.0

        return self.operation.estimate_duration(input_path)

    def get_operation_name(self) -> str:
        """
        Get human-readable operation name.

        Returns:
            Operation name string
        """
        return self.operation.get_operation_name()

    def __repr__(self) -> str:
        """String representation of stage."""
        return (
            f"Stage("
            f"type={self.config.stage.value}, "
            f"status={self.status.value}, "
            f"enabled={self.config.enabled})"
        )
