"""
Unit tests for pipeline configuration module.

Tests PipelineConfig, StageConfig, and related configuration classes.
"""

from pathlib import Path

import pytest

from video_chapter_automater.pipeline.config import (
    PipelineConfig,
    StageConfig,
    PipelineStage,
    ExecutionMode,
)
from video_chapter_automater.preprocessing.audio_extractor import AudioExtractionConfig
from video_chapter_automater.preprocessing.scene_extractor import SceneExtractionConfig
from video_chapter_automater.preprocessing.strategies.codec_strategies import VideoEncodingConfig


class TestPipelineStage:
    """Test PipelineStage enum."""

    def test_stage_values(self):
        """Test stage enum values."""
        assert PipelineStage.VIDEO_ENCODING.value == "video_encoding"
        assert PipelineStage.AUDIO_EXTRACTION.value == "audio_extraction"
        assert PipelineStage.SCENE_EXTRACTION.value == "scene_extraction"


class TestExecutionMode:
    """Test ExecutionMode enum."""

    def test_mode_values(self):
        """Test execution mode enum values."""
        assert ExecutionMode.SEQUENTIAL.value == "sequential"
        assert ExecutionMode.PARALLEL.value == "parallel"
        assert ExecutionMode.RESILIENT.value == "resilient"


class TestStageConfig:
    """Test StageConfig dataclass."""

    def test_default_creation(self):
        """Test stage config creation with defaults."""
        config = StageConfig(stage=PipelineStage.AUDIO_EXTRACTION)
        assert config.stage == PipelineStage.AUDIO_EXTRACTION
        assert config.enabled is True
        assert config.config is not None  # Auto-created
        assert isinstance(config.config, AudioExtractionConfig)
        assert config.output_subdir is None
        assert config.skip_on_error is False

    def test_custom_creation(self):
        """Test stage config creation with custom values."""
        custom_config = VideoEncodingConfig(preset="slow", crf=18)
        config = StageConfig(
            stage=PipelineStage.VIDEO_ENCODING,
            enabled=False,
            config=custom_config,
            output_subdir="custom_output",
            skip_on_error=True
        )
        assert config.stage == PipelineStage.VIDEO_ENCODING
        assert config.enabled is False
        assert config.config == custom_config
        assert config.output_subdir == "custom_output"
        assert config.skip_on_error is True

    def test_default_config_video_encoding(self):
        """Test default config for video encoding."""
        config = StageConfig(stage=PipelineStage.VIDEO_ENCODING)
        assert isinstance(config.config, VideoEncodingConfig)

    def test_default_config_audio_extraction(self):
        """Test default config for audio extraction."""
        config = StageConfig(stage=PipelineStage.AUDIO_EXTRACTION)
        assert isinstance(config.config, AudioExtractionConfig)

    def test_default_config_scene_extraction(self):
        """Test default config for scene extraction."""
        config = StageConfig(stage=PipelineStage.SCENE_EXTRACTION)
        assert isinstance(config.config, SceneExtractionConfig)


class TestPipelineConfig:
    """Test PipelineConfig dataclass."""

    def test_default_creation(self):
        """Test pipeline config creation with defaults."""
        config = PipelineConfig()
        assert config.stages == []
        assert config.execution_mode == ExecutionMode.SEQUENTIAL
        assert isinstance(config.output_base_dir, Path)
        assert config.output_base_dir == Path("./vca_output")
        assert config.enable_monitoring is True
        assert config.enable_progress_bars is True
        assert config.max_parallel_stages == 2
        assert config.stop_on_error is True
        assert config.cleanup_on_failure is False
        assert config.metadata == {}

    def test_custom_creation(self):
        """Test pipeline config creation with custom values."""
        config = PipelineConfig(
            execution_mode=ExecutionMode.RESILIENT,
            output_base_dir=Path("/custom/output"),
            enable_monitoring=False,
            max_parallel_stages=4,
            stop_on_error=False
        )
        assert config.execution_mode == ExecutionMode.RESILIENT
        assert config.output_base_dir == Path("/custom/output")
        assert config.enable_monitoring is False
        assert config.max_parallel_stages == 4
        assert config.stop_on_error is False

    def test_invalid_max_parallel_stages(self):
        """Test validation of max_parallel_stages."""
        with pytest.raises(ValueError, match="max_parallel_stages must be >= 1"):
            PipelineConfig(max_parallel_stages=0)

    def test_add_stage(self):
        """Test adding stages to pipeline."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION)

        assert len(config.stages) == 2
        assert config.stages[0].stage == PipelineStage.VIDEO_ENCODING
        assert config.stages[1].stage == PipelineStage.AUDIO_EXTRACTION

    def test_add_stage_method_chaining(self):
        """Test method chaining with add_stage."""
        config = PipelineConfig()
        result = config.add_stage(PipelineStage.VIDEO_ENCODING)

        assert result is config  # Returns self
        assert len(config.stages) == 1

    def test_add_stage_with_custom_config(self):
        """Test adding stage with custom configuration."""
        custom_config = AudioExtractionConfig(sample_rate=44100)
        config = PipelineConfig()
        config.add_stage(
            PipelineStage.AUDIO_EXTRACTION,
            config=custom_config,
            enabled=False,
            skip_on_error=True
        )

        assert len(config.stages) == 1
        assert config.stages[0].config == custom_config
        assert config.stages[0].enabled is False
        assert config.stages[0].skip_on_error is True

    def test_get_enabled_stages(self):
        """Test getting only enabled stages."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING, enabled=True)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION, enabled=False)
        config.add_stage(PipelineStage.SCENE_EXTRACTION, enabled=True)

        enabled = config.get_enabled_stages()
        assert len(enabled) == 2
        assert enabled[0].stage == PipelineStage.VIDEO_ENCODING
        assert enabled[1].stage == PipelineStage.SCENE_EXTRACTION

    def test_has_stage(self):
        """Test checking if pipeline has a specific stage."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING, enabled=True)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION, enabled=False)

        assert config.has_stage(PipelineStage.VIDEO_ENCODING) is True
        assert config.has_stage(PipelineStage.AUDIO_EXTRACTION) is False  # Disabled
        assert config.has_stage(PipelineStage.SCENE_EXTRACTION) is False  # Not present

    def test_get_stage_config(self):
        """Test getting configuration for specific stage."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION)

        video_config = config.get_stage_config(PipelineStage.VIDEO_ENCODING)
        assert video_config is not None
        assert video_config.stage == PipelineStage.VIDEO_ENCODING

        missing_config = config.get_stage_config(PipelineStage.SCENE_EXTRACTION)
        assert missing_config is None

    def test_validate_empty_pipeline(self):
        """Test validation fails with no stages."""
        config = PipelineConfig()
        with pytest.raises(ValueError, match="must have at least one stage"):
            config.validate()

    def test_validate_no_enabled_stages(self):
        """Test validation fails with no enabled stages."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING, enabled=False)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION, enabled=False)

        with pytest.raises(ValueError, match="must have at least one enabled stage"):
            config.validate()

    def test_validate_success(self):
        """Test successful validation."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING)
        config.add_stage(PipelineStage.AUDIO_EXTRACTION)

        assert config.validate() is True

    def test_create_default(self):
        """Test creating default pipeline configuration."""
        config = PipelineConfig.create_default()

        assert len(config.stages) == 3
        assert config.has_stage(PipelineStage.VIDEO_ENCODING)
        assert config.has_stage(PipelineStage.AUDIO_EXTRACTION)
        assert config.has_stage(PipelineStage.SCENE_EXTRACTION)

    def test_create_minimal(self):
        """Test creating minimal pipeline configuration."""
        config = PipelineConfig.create_minimal()

        assert len(config.stages) == 2
        assert not config.has_stage(PipelineStage.VIDEO_ENCODING)
        assert config.has_stage(PipelineStage.AUDIO_EXTRACTION)
        assert config.has_stage(PipelineStage.SCENE_EXTRACTION)

    def test_create_encoding_only(self):
        """Test creating encoding-only pipeline."""
        config = PipelineConfig.create_encoding_only(codec="hevc_nvenc")

        assert len(config.stages) == 1
        assert config.has_stage(PipelineStage.VIDEO_ENCODING)

    def test_repr(self):
        """Test string representation."""
        config = PipelineConfig()
        config.add_stage(PipelineStage.VIDEO_ENCODING)

        repr_str = repr(config)
        assert "PipelineConfig" in repr_str
        assert "video_encoding" in repr_str
        assert "sequential" in repr_str
