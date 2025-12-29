"""
Perceptual hash strategy implementations for image deduplication.

Provides concrete implementations of HashStrategy for detecting similar/duplicate
images using various perceptual hashing algorithms (pHash, dHash, wHash).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False

from ..base import HashStrategy
from ...exceptions import DependencyError, DeduplicationError


class PerceptualHashStrategy(HashStrategy):
    """
    Perceptual Hash (pHash) strategy using DCT-based algorithm.

    pHash is robust to scaling, aspect ratio changes, and slight color modifications.
    Best for general-purpose image deduplication. Uses Discrete Cosine Transform (DCT)
    to generate a hash that captures the essential frequency domain characteristics.

    Hash size: 8x8 = 64 bits (default)
    """

    def __init__(self, hash_size: int = 8):
        """
        Initialize perceptual hash strategy.

        Args:
            hash_size: Size of the hash matrix (default: 8 for 64-bit hash)
        """
        if not IMAGEHASH_AVAILABLE:
            raise DependencyError(
                "imagehash",
                "Install with: pip install imagehash pillow"
            )
        self.hash_size = hash_size

    def compute_hash(self, image_path: Path) -> Any:
        """
        Compute perceptual hash for an image.

        Args:
            image_path: Path to image file

        Returns:
            ImageHash object containing the hash value

        Raises:
            DeduplicationError: If hash computation fails
        """
        try:
            with Image.open(image_path) as img:
                return imagehash.phash(img, hash_size=self.hash_size)
        except Exception as e:
            raise DeduplicationError(
                f"Failed to compute pHash for {image_path}: {str(e)}"
            ) from e

    def compare(self, hash1: Any, hash2: Any) -> int:
        """
        Compare two perceptual hashes.

        Args:
            hash1: First ImageHash object
            hash2: Second ImageHash object

        Returns:
            Hamming distance (0 = identical, higher = more different)
        """
        try:
            return hash1 - hash2  # imagehash uses - operator for Hamming distance
        except Exception as e:
            raise DeduplicationError(
                f"Failed to compare hashes: {str(e)}"
            ) from e

    def are_similar(self, hash1: Any, hash2: Any, threshold: int = 5) -> bool:
        """
        Determine if two images are similar based on hash comparison.

        Args:
            hash1: First ImageHash object
            hash2: Second ImageHash object
            threshold: Maximum Hamming distance to consider similar (default: 5)
                      0 = identical only
                      1-5 = very similar (recommended)
                      6-10 = similar
                      >10 = different

        Returns:
            True if images are similar within threshold, False otherwise
        """
        distance = self.compare(hash1, hash2)
        return distance <= threshold

    @property
    def algorithm_name(self) -> str:
        """Name of hashing algorithm (e.g., 'phash')."""
        return f"phash-{self.hash_size}"

    def get_algorithm_name(self) -> str:
        """Get human-readable algorithm name."""
        return f"Perceptual Hash ({self.algorithm_name})"


class PHashStrategy(PerceptualHashStrategy):
    """Alias for PerceptualHashStrategy focusing on pHash."""
    pass


class AverageHashStrategy(PerceptualHashStrategy):
    """
    Average Hash (aHash) strategy.

    aHash reduces the image to a small scale (e.g., 8x8), converts to grayscale,
    and then compares each pixel to the average color of the image.
    Robust to scaling and brightness changes.
    """

    def compute_hash(self, image_path: Path) -> Any:
        """
        Compute average hash for an image.

        Args:
            image_path: Path to image file

        Returns:
            ImageHash object containing the hash value

        Raises:
            DeduplicationError: If hash computation fails
        """
        try:
            with Image.open(image_path) as img:
                return imagehash.ahash(img, hash_size=self.hash_size)
        except Exception as e:
            raise DeduplicationError(
                f"Failed to compute aHash for {image_path}: {str(e)}"
            ) from e

    @property
    def algorithm_name(self) -> str:
        """Name of hashing algorithm (e.g., 'ahash')."""
        return f"ahash-{self.hash_size}"

    def get_algorithm_name(self) -> str:
        """Get human-readable algorithm name."""
        return f"Average Hash ({self.algorithm_name})"


class AHashStrategy(AverageHashStrategy):
    """Alias for AverageHashStrategy."""
    pass


class DifferenceHashStrategy(PerceptualHashStrategy):
    """
    Difference Hash (dHash) strategy using gradient-based algorithm.

    dHash tracks gradients between adjacent pixels, making it faster than pHash
    and more sensitive to structural changes. Good for detecting image transformations
    while being robust to brightness/contrast changes.

    Hash size: 8x8 = 64 bits (default)
    """

    def compute_hash(self, image_path: Path) -> Any:
        """
        Compute difference hash for an image.

        Args:
            image_path: Path to image file

        Returns:
            ImageHash object containing the hash value

        Raises:
            DeduplicationError: If hash computation fails
        """
        try:
            with Image.open(image_path) as img:
                return imagehash.dhash(img, hash_size=self.hash_size)
        except Exception as e:
            raise DeduplicationError(
                f"Failed to compute dHash for {image_path}: {str(e)}"
            ) from e

    @property
    def algorithm_name(self) -> str:
        """Name of hashing algorithm (e.g., 'dhash')."""
        return f"dhash-{self.hash_size}"

    def get_algorithm_name(self) -> str:
        """Get human-readable algorithm name."""
        return f"Difference Hash ({self.algorithm_name})"


class DHashStrategy(DifferenceHashStrategy):
    """Alias for DifferenceHashStrategy."""
    pass


class WaveletHashStrategy(PerceptualHashStrategy):
    """
    Wavelet Hash (wHash) strategy using Discrete Wavelet Transform.

    wHash uses DWT to analyze image at multiple scales, making it particularly
    effective for larger images and robust to rescaling. Good for high-resolution
    scene images where multi-scale analysis is beneficial.

    Hash size: 8x8 = 64 bits (default)
    """

    def __init__(self, hash_size: int = 8, mode: str = "haar"):
        """
        Initialize wavelet hash strategy.

        Args:
            hash_size: Size of the hash matrix (default: 8 for 64-bit hash)
            mode: Wavelet mode - "haar" (default), "db4" (Daubechies 4)
        """
        super().__init__(hash_size=hash_size)
        self.mode = mode

    def compute_hash(self, image_path: Path) -> Any:
        """
        Compute wavelet hash for an image.

        Args:
            image_path: Path to image file

        Returns:
            ImageHash object containing the hash value

        Raises:
            DeduplicationError: If hash computation fails
        """
        try:
            with Image.open(image_path) as img:
                return imagehash.whash(img, hash_size=self.hash_size, mode=self.mode)
        except Exception as e:
            raise DeduplicationError(
                f"Failed to compute wHash for {image_path}: {str(e)}"
            ) from e

    @property
    def algorithm_name(self) -> str:
        """Name of hashing algorithm (e.g., 'whash')."""
        return f"whash-{self.hash_size}-{self.mode}"

    def get_algorithm_name(self) -> str:
        """Get human-readable algorithm name."""
        return f"Wavelet Hash ({self.algorithm_name})"


class WHashStrategy(WaveletHashStrategy):
    """Alias for WaveletHashStrategy."""
    pass


def get_hash_strategy(algorithm: str = "phash", **kwargs) -> HashStrategy:
    """
    Factory function to create hash strategy instances.

    Args:
        algorithm: Algorithm name - "phash", "dhash", or "whash"
        **kwargs: Additional arguments passed to strategy constructor

    Returns:
        HashStrategy instance

    Raises:
        ValueError: If algorithm is not supported
        DependencyError: If required dependencies are not available

    Example:
        >>> strategy = get_hash_strategy("phash", hash_size=8)
        >>> hash1 = strategy.compute_hash(Path("image1.png"))
        >>> hash2 = strategy.compute_hash(Path("image2.png"))
        >>> if strategy.are_similar(hash1, hash2, threshold=5):
        ...     print("Images are similar!")
    """
    strategies = {
        "phash": PHashStrategy,
        "ahash": AHashStrategy,
        "dhash": DHashStrategy,
        "whash": WHashStrategy,
    }

    algorithm_lower = algorithm.lower()
    if algorithm_lower not in strategies:
        raise ValueError(
            f"Unsupported hash algorithm: {algorithm}. "
            f"Supported: {', '.join(strategies.keys())}"
        )

    strategy_class = strategies[algorithm_lower]
    return strategy_class(**kwargs)
