"""
Unit tests for scene extraction module.

Tests SceneExtractor with mocked PySceneDetect calls to avoid
requiring actual video files and scenedetect installation.
"""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Mock scenedetect module availability
scenedetect_mock = MagicMock()

@pytest.fixture(autouse=True)
def mock_scenedetect():
    """Mock scenedetect dependency."""
    with patch.dict('sys.modules', {'scenedetect': scenedetect_mock}):
        yield


from video_chapter_automater.preprocessing.scene_extractor import (
    SceneExtractor,
    SceneExtractionConfig,
    SceneExtractionResult,
    SceneInfo,
)
from video_chapter_automater.exceptions import (
    SceneExtractionError,
    DependencyError,
)


@pytest.fixture
def scene_extractor():
    """Create SceneExtractor instance for testing."""
    with patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True):
        return SceneExtractor(verbose=False)


@pytest.fixture
def test_video_path(tmp_path):
    """Create a temporary test video file."""
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"fake video content")
    return video_file


@pytest.fixture
def default_config():
    """Create default SceneExtractionConfig."""
    return SceneExtractionConfig()


@pytest.fixture
def mock_frame_timecode():
    """Create mock FrameTimecode objects."""
    def create_timecode(seconds):
        tc = Mock()
        tc.get_seconds.return_value = seconds
        return tc
    return create_timecode


class TestSceneExtractionConfig:
    """Test SceneExtractionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SceneExtractionConfig()
        assert config.num_images == 3
        assert config.threshold == 27.0
        assert config.dedup_threshold == 5
        assert config.hash_algorithm == "phash"
        assert config.image_format == "png"
        assert config.min_scene_length == 0.5

    def test_custom_config(self):
        """Test custom configuration."""
        config = SceneExtractionConfig(
            num_images=6,
            threshold=30.0,
            dedup_threshold=3,
            hash_algorithm="dhash",
            image_format="jpg",
            min_scene_length=1.0
        )
        assert config.num_images == 6
        assert config.threshold == 30.0
        assert config.dedup_threshold == 3
        assert config.hash_algorithm == "dhash"
        assert config.image_format == "jpg"
        assert config.min_scene_length == 1.0

    def test_invalid_num_images_too_low(self):
        """Test validation of num_images too low."""
        with pytest.raises(ValueError, match="num_images must be between 1-9"):
            SceneExtractionConfig(num_images=0)

    def test_invalid_num_images_too_high(self):
        """Test validation of num_images too high."""
        with pytest.raises(ValueError, match="num_images must be between 1-9"):
            SceneExtractionConfig(num_images=10)

    def test_invalid_threshold(self):
        """Test validation of negative threshold."""
        with pytest.raises(ValueError, match="threshold must be >= 0"):
            SceneExtractionConfig(threshold=-1.0)

    def test_invalid_dedup_threshold(self):
        """Test validation of dedup_threshold out of range."""
        with pytest.raises(ValueError, match="dedup_threshold must be between 0-20"):
            SceneExtractionConfig(dedup_threshold=25)

    def test_invalid_hash_algorithm(self):
        """Test validation of invalid hash algorithm."""
        with pytest.raises(ValueError, match="hash_algorithm must be"):
            SceneExtractionConfig(hash_algorithm="invalid")

    def test_invalid_image_format(self):
        """Test validation of invalid image format."""
        with pytest.raises(ValueError, match="image_format must be"):
            SceneExtractionConfig(image_format="bmp")


class TestSceneExtractor:
    """Test SceneExtractor class."""

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_initialization(self):
        """Test scene extractor initialization."""
        extractor = SceneExtractor(verbose=True)
        assert extractor.verbose is True
        assert extractor.hash_strategy is not None

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_validate_input_success(self, test_video_path):
        """Test successful input validation."""
        extractor = SceneExtractor()
        assert extractor.validate_input(test_video_path) is True

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_validate_input_nonexistent_file(self, tmp_path):
        """Test validation with nonexistent file."""
        extractor = SceneExtractor()
        nonexistent = tmp_path / "nonexistent.mp4"
        with pytest.raises(ValueError, match="does not exist"):
            extractor.validate_input(nonexistent)

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_validate_input_directory(self, tmp_path):
        """Test validation with directory instead of file."""
        extractor = SceneExtractor()
        with pytest.raises(ValueError, match="not a file"):
            extractor.validate_input(tmp_path)

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_validate_input_invalid_extension(self, tmp_path):
        """Test validation with unsupported file extension."""
        extractor = SceneExtractor()
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("text file")
        with pytest.raises(ValueError, match="Unsupported video format"):
            extractor.validate_input(invalid_file)

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_estimate_duration(self, test_video_path):
        """Test duration estimation."""
        extractor = SceneExtractor()
        # Create file with known size (1MB)
        test_video_path.write_bytes(b"x" * (1024 * 1024))
        duration = extractor.estimate_duration(test_video_path)
        assert duration > 0
        assert isinstance(duration, float)

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.scene_extractor.detect')
    @patch('video_chapter_automater.preprocessing.scene_extractor.open_video')
    @patch('video_chapter_automater.preprocessing.scene_extractor.save_images')
    def test_execute_success(
        self,
        mock_save_images,
        mock_open_video,
        mock_detect,
        test_video_path,
        default_config,
        tmp_path,
        mock_frame_timecode
    ):
        """Test successful scene extraction."""
        # Setup mock scenes
        scenes = [
            (mock_frame_timecode(0.0), mock_frame_timecode(10.5)),
            (mock_frame_timecode(10.5), mock_frame_timecode(25.0)),
        ]
        mock_detect.return_value = scenes

        # Setup mock images
        output_dir = tmp_path / "scenes"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_paths = [
            output_dir / "test_video-Scene-001-01.png",
            output_dir / "test_video-Scene-001-02.png",
            output_dir / "test_video-Scene-002-01.png",
        ]
        for img_path in image_paths:
            img_path.write_bytes(b"fake image data")

        mock_save_images.return_value = {
            0: [str(image_paths[0]), str(image_paths[1])],
            1: [str(image_paths[2])],
        }

        # Mock hash strategy
        mock_hash_strategy = Mock()
        mock_hash = Mock()
        mock_hash_strategy.compute_hash.return_value = mock_hash
        mock_hash_strategy.are_similar.return_value = False  # No duplicates

        extractor = SceneExtractor(hash_strategy=mock_hash_strategy)
        result = extractor.execute(test_video_path, default_config, output_dir=output_dir)

        assert result.success is True
        assert result.num_scenes == 2
        assert result.total_images_extracted == 3
        assert result.duplicates_removed == 0
        assert len(result.scenes) == 2

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.scene_extractor.detect')
    def test_execute_no_scenes(
        self,
        mock_detect,
        test_video_path,
        default_config,
        tmp_path
    ):
        """Test execution when no scenes are detected."""
        mock_detect.return_value = []  # No scenes

        extractor = SceneExtractor()
        result = extractor.execute(test_video_path, default_config, output_dir=tmp_path)

        assert result.success is True
        assert result.num_scenes == 0
        assert result.total_images_extracted == 0
        assert result.duplicates_removed == 0

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.scene_extractor.detect')
    @patch('video_chapter_automater.preprocessing.scene_extractor.open_video')
    @patch('video_chapter_automater.preprocessing.scene_extractor.save_images')
    def test_execute_with_deduplication(
        self,
        mock_save_images,
        mock_open_video,
        mock_detect,
        test_video_path,
        default_config,
        tmp_path,
        mock_frame_timecode
    ):
        """Test scene extraction with deduplication."""
        # Setup mock scenes
        scenes = [(mock_frame_timecode(0.0), mock_frame_timecode(10.0))]
        mock_detect.return_value = scenes

        # Setup mock images
        output_dir = tmp_path / "scenes"
        output_dir.mkdir(parents=True, exist_ok=True)

        image_paths = [
            output_dir / "test_video-Scene-001-01.png",
            output_dir / "test_video-Scene-001-02.png",
            output_dir / "test_video-Scene-001-03.png",
        ]
        for img_path in image_paths:
            img_path.write_bytes(b"fake image data")

        mock_save_images.return_value = {
            0: [str(p) for p in image_paths],
        }

        # Mock hash strategy - second and third images are duplicates
        mock_hash_strategy = Mock()
        mock_hash1 = Mock()
        mock_hash2 = Mock()
        mock_hash3 = Mock()

        mock_hash_strategy.compute_hash.side_effect = [mock_hash1, mock_hash2, mock_hash3]
        mock_hash_strategy.are_similar.side_effect = [
            False,  # hash1 vs nothing = keep
            True,   # hash2 vs hash1 = duplicate
            True,   # hash3 vs hash1 = duplicate
        ]

        extractor = SceneExtractor(hash_strategy=mock_hash_strategy)
        result = extractor.execute(test_video_path, default_config, output_dir=output_dir)

        assert result.success is True
        assert result.total_images_extracted == 3
        assert result.duplicates_removed == 2
        assert result.images_after_dedup == 1

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.scene_extractor.detect')
    def test_execute_scene_detection_failure(
        self,
        mock_detect,
        test_video_path,
        default_config,
        tmp_path
    ):
        """Test error handling when scene detection fails."""
        mock_detect.side_effect = Exception("Scene detection failed")

        extractor = SceneExtractor()
        with pytest.raises(SceneExtractionError, match="Scene extraction failed"):
            extractor.execute(test_video_path, default_config, output_dir=tmp_path)

    @patch('video_chapter_automater.preprocessing.scene_extractor.SCENEDETECT_AVAILABLE', True)
    def test_get_operation_name(self):
        """Test operation name retrieval."""
        extractor = SceneExtractor()
        assert extractor.get_operation_name() == "Scene Extraction"


class TestSceneInfo:
    """Test SceneInfo dataclass."""

    def test_scene_info_creation(self):
        """Test SceneInfo creation."""
        scene = SceneInfo(
            scene_number=1,
            start_time=0.0,
            end_time=10.5,
            duration=10.5,
            image_paths=[Path("scene1.png")]
        )
        assert scene.scene_number == 1
        assert scene.start_time == 0.0
        assert scene.end_time == 10.5
        assert scene.duration == 10.5
        assert len(scene.image_paths) == 1


class TestSceneExtractionResult:
    """Test SceneExtractionResult dataclass."""

    def test_result_creation(self):
        """Test result creation."""
        scene = SceneInfo(
            scene_number=1,
            start_time=0.0,
            end_time=10.0,
            duration=10.0
        )

        result = SceneExtractionResult(
            success=True,
            output_path=Path("/output"),
            duration=5.0,
            num_scenes=1,
            total_images_extracted=5,
            images_after_dedup=3,
            duplicates_removed=2,
            scenes=[scene]
        )

        assert result.success is True
        assert result.num_scenes == 1
        assert result.total_images_extracted == 5
        assert result.images_after_dedup == 3
        assert result.duplicates_removed == 2
        assert len(result.scenes) == 1
