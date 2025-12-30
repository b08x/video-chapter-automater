"""
Unit tests for pipeline orchestrator.

Tests PipelineOrchestrator with mocked preprocessing operations.
"""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from video_chapter_automater.pipeline.orchestrator import PipelineOrchestrator, PipelineResult
from video_chapter_automater.pipeline.config import PipelineConfig, PipelineStage
from video_chapter_automater.pipeline.stage import StageStatus
from video_chapter_automater.output.manager import OutputManager


@pytest.fixture
def test_video_path(tmp_path):
    """Create a temporary test video file."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content")
    return video_file


@pytest.fixture
def output_manager(tmp_path):
    """Create OutputManager for testing."""
    return OutputManager(base_dir=tmp_path / "output", auto_create=True)


class TestPipelineResult:
    """Test PipelineResult dataclass."""

    def test_default_creation(self):
        """Test pipeline result creation."""
        result = PipelineResult(success=True, total_duration=10.5)
        assert result.success is True
        assert result.total_duration == 10.5
        assert result.stage_results == []
        assert result.input_path is None
        assert result.output_paths == {}
        assert result.metadata == {}
        assert result.error_summary is None

    def test_completed_stages(self):
        """Test getting completed stages."""
        from video_chapter_automater.pipeline.stage import StageResult

        result = PipelineResult(success=True, total_duration=10.0)
        result.stage_results = [
            StageResult(stage=PipelineStage.VIDEO_ENCODING, status=StageStatus.COMPLETED),
            StageResult(stage=PipelineStage.AUDIO_EXTRACTION, status=StageStatus.FAILED),
            StageResult(stage=PipelineStage.SCENE_EXTRACTION, status=StageStatus.SKIPPED),
        ]

        completed = result.completed_stages
        assert len(completed) == 1
        assert completed[0].stage == PipelineStage.VIDEO_ENCODING

    def test_failed_stages(self):
        """Test getting failed stages."""
        from video_chapter_automater.pipeline.stage import StageResult

        result = PipelineResult(success=False, total_duration=5.0)
        result.stage_results = [
            StageResult(stage=PipelineStage.VIDEO_ENCODING, status=StageStatus.COMPLETED),
            StageResult(stage=PipelineStage.AUDIO_EXTRACTION, status=StageStatus.FAILED),
        ]

        failed = result.failed_stages
        assert len(failed) == 1
        assert failed[0].stage == PipelineStage.AUDIO_EXTRACTION

    def test_get_stage_result(self):
        """Test getting result for specific stage."""
        from video_chapter_automater.pipeline.stage import StageResult

        result = PipelineResult(success=True, total_duration=10.0)
        audio_result = StageResult(stage=PipelineStage.AUDIO_EXTRACTION, status=StageStatus.COMPLETED)
        result.stage_results = [audio_result]

        found = result.get_stage_result(PipelineStage.AUDIO_EXTRACTION)
        assert found == audio_result

        not_found = result.get_stage_result(PipelineStage.SCENE_EXTRACTION)
        assert not_found is None


class TestPipelineOrchestrator:
    """Test PipelineOrchestrator class."""

    def test_initialization(self, output_manager):
        """Test orchestrator initialization."""
        config = PipelineConfig.create_minimal()
        orchestrator = PipelineOrchestrator(config, output_manager, verbose=False)

        assert orchestrator.config == config
        assert orchestrator.output_manager == output_manager
        assert orchestrator.verbose is False
        assert len(orchestrator.stages) == 2  # Minimal config has 2 stages

    def test_initialization_auto_creates_output_manager(self):
        """Test orchestrator creates output manager if not provided."""
        config = PipelineConfig.create_minimal()
        orchestrator = PipelineOrchestrator(config, verbose=False)

        assert orchestrator.output_manager is not None
        assert orchestrator.output_manager.base_dir == config.output_base_dir.resolve()

    def test_invalid_config(self):
        """Test initialization with invalid config."""
        config = PipelineConfig()  # Empty, invalid

        with pytest.raises(ValueError, match="must have at least one stage"):
            PipelineOrchestrator(config)

    def test_execute_nonexistent_file(self, output_manager, tmp_path):
        """Test execution with nonexistent input file."""
        config = PipelineConfig.create_minimal()
        orchestrator = PipelineOrchestrator(config, output_manager, verbose=False)

        nonexistent = tmp_path / "nonexistent.mp4"
        result = orchestrator.execute(nonexistent)

        assert result.success is False
        assert result.total_duration == 0.0
        assert "does not exist" in result.error_summary

    @patch('video_chapter_automater.pipeline.stage.Stage.execute')
    def test_execute_sequential_success(
        self,
        mock_stage_execute,
        test_video_path,
        output_manager
    ):
        """Test successful sequential pipeline execution."""
        from video_chapter_automater.pipeline.stage import StageResult
        from video_chapter_automater.preprocessing.base import PreprocessingResult

        # Mock stage execution to return successful results
        mock_result = PreprocessingResult(
            success=True,
            output_path=test_video_path,
            duration=1.0
        )
        mock_stage_result = StageResult(
            stage=PipelineStage.AUDIO_EXTRACTION,
            status=StageStatus.COMPLETED,
            preprocessing_result=mock_result
        )
        mock_stage_execute.return_value = mock_stage_result

        # Create and execute pipeline
        config = PipelineConfig.create_minimal()
        config.enable_progress_bars = False  # Disable for testing
        orchestrator = PipelineOrchestrator(config, output_manager, verbose=False)

        result = orchestrator.execute(test_video_path)

        assert result.success is True
        assert result.total_duration > 0
        assert len(result.stage_results) == 2
        assert result.error_summary is None

    @patch('video_chapter_automater.pipeline.stage.Stage.execute')
    def test_execute_with_failure_stop_on_error(
        self,
        mock_stage_execute,
        test_video_path,
        output_manager
    ):
        """Test pipeline stops on first error when stop_on_error=True."""
        from video_chapter_automater.pipeline.stage import StageResult

        # Mock first stage to fail
        mock_stage_execute.return_value = StageResult(
            stage=PipelineStage.AUDIO_EXTRACTION,
            status=StageStatus.FAILED,
            error_message="Test error"
        )

        config = PipelineConfig.create_minimal()
        config.enable_progress_bars = False
        config.stop_on_error = True
        orchestrator = PipelineOrchestrator(config, output_manager, verbose=False)

        result = orchestrator.execute(test_video_path)

        assert result.success is False
        assert result.error_summary is not None
        assert "Test error" in result.error_summary

    def test_estimate_total_duration(self, test_video_path, output_manager):
        """Test total duration estimation."""
        config = PipelineConfig.create_minimal()
        orchestrator = PipelineOrchestrator(config, output_manager, verbose=False)

        # Create file with known size
        test_video_path.write_bytes(b"x" * (1024 * 1024))  # 1MB
        duration = orchestrator.estimate_total_duration(test_video_path)

        assert duration > 0
        assert isinstance(duration, float)

    def test_repr(self, output_manager):
        """Test string representation."""
        config = PipelineConfig.create_minimal()
        orchestrator = PipelineOrchestrator(config, output_manager)

        repr_str = repr(orchestrator)
        assert "PipelineOrchestrator" in repr_str
        assert "stages=2" in repr_str
        assert "sequential" in repr_str

    @patch('video_chapter_automater.pipeline.stage.Stage.execute')
    def test_execute_with_project_and_copy_source(
        self,
        mock_stage_execute,
        test_video_path,
        tmp_path
    ):
        """Test execution with project name and source copying."""
        from video_chapter_automater.pipeline.stage import StageResult
        from video_chapter_automater.preprocessing.base import PreprocessingResult
        from video_chapter_automater.output.manager import OutputType

        # Mock stage execution
        mock_result = PreprocessingResult(success=True, output_path=test_video_path, duration=1.0)
        mock_stage_result = StageResult(
            stage=PipelineStage.AUDIO_EXTRACTION,
            status=StageStatus.COMPLETED,
            preprocessing_result=mock_result
        )
        mock_stage_execute.return_value = mock_stage_result

        # Config with project and copy_source
        project_name = "test_project"
        config = PipelineConfig.create_minimal()
        config.output_base_dir = tmp_path / "output"
        config.project_name = project_name
        config.copy_source = True
        config.enable_progress_bars = False

        orchestrator = PipelineOrchestrator(config)
        result = orchestrator.execute(test_video_path)

        assert result.success is True
        
        # Verify project folder
        expected_base = (tmp_path / "output" / project_name).resolve()
        assert orchestrator.output_manager.base_dir == expected_base
        
        # Verify source file was copied
        source_file = expected_base / "source" / test_video_path.name
        assert source_file.exists()
        assert source_file.read_bytes() == test_video_path.read_bytes()

        # Verify other subdirs exists
        assert (expected_base / "audio").exists()
        assert (expected_base / "scenes").exists()
