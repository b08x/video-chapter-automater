"""
Pipeline configuration module for VideoChapterAutomater.

Defines configuration structures for multi-stage preprocessing pipelines,
including stage ordering, execution modes, and result handling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..preprocessing.audio_extractor import AudioExtractionConfig
from ..preprocessing.scene_extractor import SceneExtractionConfig
from ..preprocessing.strategies.codec_strategies import VideoEncodingConfig


class PipelineStage(Enum):
    """
    Enumeration of available pipeline stages.

    Stages are executed in the order they appear in a pipeline configuration.
    Each stage corresponds to a specific preprocessing operation.
    """
    VIDEO_ENCODING = "video_encoding"
    AUDIO_EXTRACTION = "audio_extraction"
    SCENE_EXTRACTION = "scene_extraction"


class ExecutionMode(Enum):
    """
    Pipeline execution mode.

    Attributes:
        SEQUENTIAL: Execute stages one at a time (default)
        PARALLEL: Execute independent stages in parallel (future enhancement)
        RESILIENT: Continue execution even if individual stages fail
    """
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    RESILIENT = "resilient"


@dataclass
class StageConfig:
    """
    Configuration for a single pipeline stage.

    Attributes:
        stage: Stage type identifier
        enabled: Whether this stage should execute
        config: Stage-specific configuration object
        output_subdir: Optional subdirectory for stage outputs
        skip_on_error: Continue pipeline if this stage fails
    """
    stage: PipelineStage
    enabled: bool = True
    config: Optional[Any] = None
    output_subdir: Optional[str] = None
    skip_on_error: bool = False

    def __post_init__(self):
        """Set default configurations if none provided."""
        if self.config is None:
            self.config = self._get_default_config()

    def _get_default_config(self) -> Any:
        """Get default configuration for this stage type."""
        defaults = {
            PipelineStage.VIDEO_ENCODING: VideoEncodingConfig(),
            PipelineStage.AUDIO_EXTRACTION: AudioExtractionConfig(),
            PipelineStage.SCENE_EXTRACTION: SceneExtractionConfig(),
        }
        return defaults.get(self.stage)


@dataclass
class PipelineConfig:
    """
    Complete pipeline configuration.

    Defines the sequence of preprocessing stages to execute, execution mode,
    output directory management, and monitoring preferences.

    Attributes:
        stages: Ordered list of stage configurations
        execution_mode: How to execute stages (sequential/parallel/resilient)
        output_base_dir: Base directory for all pipeline outputs
        enable_monitoring: Enable resource monitoring during execution
        enable_progress_bars: Show progress bars for long-running operations
        max_parallel_stages: Maximum concurrent stages (for parallel mode)
        stop_on_error: Halt entire pipeline on first error
        cleanup_on_failure: Remove partial outputs if pipeline fails
        project_name: Optional project subfolder name
        copy_source: Whether to copy source video to project folder
        metadata: Additional pipeline metadata
    """
    stages: List[StageConfig] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    output_base_dir: Path = field(default_factory=lambda: Path("./vca_output"))
    enable_monitoring: bool = True
    enable_progress_bars: bool = True
    max_parallel_stages: int = 2
    stop_on_error: bool = True
    cleanup_on_failure: bool = False
    project_name: Optional[str] = None
    copy_source: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalize configuration."""
        # Ensure output_base_dir is Path
        if not isinstance(self.output_base_dir, Path):
            self.output_base_dir = Path(self.output_base_dir)

        # Validate max_parallel_stages
        if self.max_parallel_stages < 1:
            raise ValueError(
                f"max_parallel_stages must be >= 1, got {self.max_parallel_stages}"
            )

    def add_stage(
        self,
        stage: PipelineStage,
        config: Optional[Any] = None,
        enabled: bool = True,
        skip_on_error: bool = False
    ) -> PipelineConfig:
        """
        Add a stage to the pipeline.

        Args:
            stage: Stage type to add
            config: Stage-specific configuration (uses defaults if None)
            enabled: Whether stage should execute
            skip_on_error: Continue pipeline if stage fails

        Returns:
            Self for method chaining
        """
        stage_config = StageConfig(
            stage=stage,
            enabled=enabled,
            config=config,
            skip_on_error=skip_on_error
        )
        self.stages.append(stage_config)
        return self

    def get_enabled_stages(self) -> List[StageConfig]:
        """
        Get list of enabled stages in order.

        Returns:
            List of enabled stage configurations
        """
        return [s for s in self.stages if s.enabled]

    def has_stage(self, stage: PipelineStage) -> bool:
        """
        Check if pipeline includes a specific stage.

        Args:
            stage: Stage to check for

        Returns:
            True if stage is present and enabled
        """
        return any(s.stage == stage and s.enabled for s in self.stages)

    def get_stage_config(self, stage: PipelineStage) -> Optional[StageConfig]:
        """
        Get configuration for a specific stage.

        Args:
            stage: Stage to get configuration for

        Returns:
            StageConfig if found, None otherwise
        """
        for s in self.stages:
            if s.stage == stage:
                return s
        return None

    def validate(self) -> bool:
        """
        Validate pipeline configuration.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid
        """
        if not self.stages:
            raise ValueError("Pipeline must have at least one stage")

        enabled_stages = self.get_enabled_stages()
        if not enabled_stages:
            raise ValueError("Pipeline must have at least one enabled stage")

        # Validate stage configs
        for stage_config in self.stages:
            if stage_config.config is None:
                raise ValueError(
                    f"Stage {stage_config.stage.value} has no configuration"
                )

        return True

    @classmethod
    def create_default(cls) -> PipelineConfig:
        """
        Create a default pipeline configuration.

        Returns a pipeline with all three stages enabled using default settings.

        Returns:
            PipelineConfig with default settings
        """
        config = cls()
        config.add_stage(PipelineStage.VIDEO_ENCODING)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION)
        config.add_stage(PipelineStage.SCENE_EXTRACTION)
        return config

    @classmethod
    def create_minimal(cls) -> PipelineConfig:
        """
        Create a minimal pipeline configuration.

        Returns a pipeline with only audio and scene extraction (no re-encoding).

        Returns:
            PipelineConfig with minimal settings
        """
        config = cls()
        config.add_stage(PipelineStage.AUDIO_EXTRACTION)
        config.add_stage(PipelineStage.SCENE_EXTRACTION)
        return config

    @classmethod
    def create_encoding_only(cls, codec: str = "h264_nvenc") -> PipelineConfig:
        """
        Create a pipeline for video encoding only.

        Args:
            codec: Codec to use for encoding

        Returns:
            PipelineConfig with only video encoding enabled
        """
        from ..preprocessing.strategies.codec_strategies import VideoEncodingConfig

        config = cls()
        encoding_config = VideoEncodingConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING, config=encoding_config)
        return config

    def __repr__(self) -> str:
        """String representation of pipeline config."""
        enabled = self.get_enabled_stages()
        stage_names = [s.stage.value for s in enabled]
        return (
            f"PipelineConfig("
            f"stages={stage_names}, "
            f"mode={self.execution_mode.value}, "
            f"output={self.output_base_dir})"
        )
