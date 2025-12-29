"""
Unit tests for perceptual hash strategy implementations.

Tests all three hash strategies (pHash, dHash, wHash) with mocked
image loading to avoid requiring actual image files.
"""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Mock imagehash module availability
imagehash_mock = MagicMock()
pil_mock = MagicMock()

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock imagehash and PIL dependencies."""
    with patch.dict('sys.modules', {
        'imagehash': imagehash_mock,
        'PIL': pil_mock,
        'PIL.Image': pil_mock.Image,
    }):
        yield


from video_chapter_automater.preprocessing.strategies.hash_strategies import (
    PerceptualHashStrategy,
    DifferenceHashStrategy,
    WaveletHashStrategy,
    get_hash_strategy,
)
from video_chapter_automater.exceptions import DependencyError, DeduplicationError


@pytest.fixture
def mock_image_hash():
    """Create a mock ImageHash object."""
    mock_hash = Mock()
    mock_hash.__sub__ = Mock(return_value=3)  # Hamming distance
    return mock_hash


@pytest.fixture
def test_image_path(tmp_path):
    """Create a temporary test image file."""
    image_file = tmp_path / "test_image.png"
    image_file.write_bytes(b"fake image data")
    return image_file


class TestPerceptualHashStrategy:
    """Test PerceptualHashStrategy."""

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_initialization(self):
        """Test strategy initialization."""
        strategy = PerceptualHashStrategy(hash_size=8)
        assert strategy.hash_size == 8

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.Image')
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.imagehash')
    def test_compute_hash(self, mock_imagehash, mock_Image, test_image_path):
        """Test hash computation."""
        # Setup mocks
        mock_img = Mock()
        mock_Image.open.return_value.__enter__ = Mock(return_value=mock_img)
        mock_Image.open.return_value.__exit__ = Mock(return_value=False)
        mock_hash = Mock()
        mock_imagehash.phash.return_value = mock_hash

        strategy = PerceptualHashStrategy()
        result = strategy.compute_hash(test_image_path)

        assert result == mock_hash
        mock_imagehash.phash.assert_called_once_with(mock_img, hash_size=8)

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_compare(self, mock_image_hash):
        """Test hash comparison."""
        strategy = PerceptualHashStrategy()

        hash1 = Mock()
        hash2 = Mock()
        hash1.__sub__ = Mock(return_value=5)

        distance = strategy.compare(hash1, hash2)
        assert distance == 5

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_are_similar_below_threshold(self):
        """Test similarity check below threshold."""
        strategy = PerceptualHashStrategy()

        hash1 = Mock()
        hash2 = Mock()
        hash1.__sub__ = Mock(return_value=3)

        assert strategy.are_similar(hash1, hash2, threshold=5) is True

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_are_similar_above_threshold(self):
        """Test similarity check above threshold."""
        strategy = PerceptualHashStrategy()

        hash1 = Mock()
        hash2 = Mock()
        hash1.__sub__ = Mock(return_value=7)

        assert strategy.are_similar(hash1, hash2, threshold=5) is False

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_are_similar_equal_threshold(self):
        """Test similarity check equal to threshold."""
        strategy = PerceptualHashStrategy()

        hash1 = Mock()
        hash2 = Mock()
        hash1.__sub__ = Mock(return_value=5)

        assert strategy.are_similar(hash1, hash2, threshold=5) is True

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_get_algorithm_name(self):
        """Test algorithm name retrieval."""
        strategy = PerceptualHashStrategy(hash_size=8)
        assert strategy.get_algorithm_name() == "Perceptual Hash (pHash-8)"


class TestDifferenceHashStrategy:
    """Test DifferenceHashStrategy."""

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.Image')
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.imagehash')
    def test_compute_hash(self, mock_imagehash, mock_Image, test_image_path):
        """Test dHash computation."""
        mock_img = Mock()
        mock_Image.open.return_value.__enter__ = Mock(return_value=mock_img)
        mock_Image.open.return_value.__exit__ = Mock(return_value=False)
        mock_hash = Mock()
        mock_imagehash.dhash.return_value = mock_hash

        strategy = DifferenceHashStrategy()
        result = strategy.compute_hash(test_image_path)

        assert result == mock_hash
        mock_imagehash.dhash.assert_called_once_with(mock_img, hash_size=8)

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_get_algorithm_name(self):
        """Test algorithm name retrieval."""
        strategy = DifferenceHashStrategy(hash_size=8)
        assert strategy.get_algorithm_name() == "Difference Hash (dHash-8)"


class TestWaveletHashStrategy:
    """Test WaveletHashStrategy."""

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.Image')
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.imagehash')
    def test_compute_hash(self, mock_imagehash, mock_Image, test_image_path):
        """Test wHash computation."""
        mock_img = Mock()
        mock_Image.open.return_value.__enter__ = Mock(return_value=mock_img)
        mock_Image.open.return_value.__exit__ = Mock(return_value=False)
        mock_hash = Mock()
        mock_imagehash.whash.return_value = mock_hash

        strategy = WaveletHashStrategy(mode="haar")
        result = strategy.compute_hash(test_image_path)

        assert result == mock_hash
        mock_imagehash.whash.assert_called_once_with(mock_img, hash_size=8, mode="haar")

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_initialization_with_mode(self):
        """Test strategy initialization with wavelet mode."""
        strategy = WaveletHashStrategy(hash_size=8, mode="db4")
        assert strategy.hash_size == 8
        assert strategy.mode == "db4"

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_get_algorithm_name(self):
        """Test algorithm name retrieval."""
        strategy = WaveletHashStrategy(hash_size=8, mode="haar")
        assert strategy.get_algorithm_name() == "Wavelet Hash (wHash-8-haar)"


class TestHashStrategyFactory:
    """Test get_hash_strategy factory function."""

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_get_phash_strategy(self):
        """Test factory creates PerceptualHashStrategy."""
        strategy = get_hash_strategy("phash", hash_size=8)
        assert isinstance(strategy, PerceptualHashStrategy)
        assert strategy.hash_size == 8

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_get_dhash_strategy(self):
        """Test factory creates DifferenceHashStrategy."""
        strategy = get_hash_strategy("dhash", hash_size=8)
        assert isinstance(strategy, DifferenceHashStrategy)
        assert strategy.hash_size == 8

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_get_whash_strategy(self):
        """Test factory creates WaveletHashStrategy."""
        strategy = get_hash_strategy("whash", hash_size=8, mode="haar")
        assert isinstance(strategy, WaveletHashStrategy)
        assert strategy.hash_size == 8
        assert strategy.mode == "haar"

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_case_insensitive(self):
        """Test factory is case-insensitive."""
        strategy1 = get_hash_strategy("PHASH")
        strategy2 = get_hash_strategy("PhAsH")
        assert isinstance(strategy1, PerceptualHashStrategy)
        assert isinstance(strategy2, PerceptualHashStrategy)

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_invalid_algorithm(self):
        """Test factory raises error for invalid algorithm."""
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            get_hash_strategy("invalid")


class TestHashStrategyErrorHandling:
    """Test error handling in hash strategies."""

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.Image')
    def test_compute_hash_file_error(self, mock_Image, test_image_path):
        """Test error handling when image file cannot be opened."""
        mock_Image.open.side_effect = IOError("Cannot open image")

        strategy = PerceptualHashStrategy()
        with pytest.raises(DeduplicationError, match="Failed to compute pHash"):
            strategy.compute_hash(test_image_path)

    @patch('video_chapter_automater.preprocessing.strategies.hash_strategies.IMAGEHASH_AVAILABLE', True)
    def test_compare_error(self):
        """Test error handling during hash comparison."""
        strategy = PerceptualHashStrategy()

        hash1 = Mock()
        hash2 = Mock()
        hash1.__sub__ = Mock(side_effect=Exception("Comparison failed"))

        with pytest.raises(DeduplicationError, match="Failed to compare hashes"):
            strategy.compare(hash1, hash2)
