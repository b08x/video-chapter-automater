"""
Abstract base classes and protocols for preprocessing operations.

Defines the contracts that all preprocessing operations must implement,
enabling clean separation of concerns and testability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image
    from imagehash import ImageHash
    from ..gpu_detection import GPUInfo, GPUVendor


@dataclass
class PreprocessingResult:
    """Base result class for preprocessing operations."""

    success: bool
    output_path: Optional[Path] = None
    duration: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class PreprocessingOperation(ABC):
    """
    Abstract base class for all preprocessing operations.

    Each preprocessing operation (video encoding, audio extraction, etc.)
    must implement this interface to work with the pipeline orchestrator.
    """

    @abstractmethod
    def execute(self, input_path: Path, config: Any) -> PreprocessingResult:
        """
        Execute the preprocessing operation.

        Args:
            input_path: Path to input file (video, image, etc.)
            config: Operation-specific configuration object

        Returns:
            PreprocessingResult with operation outcome

        Raises:
            PreprocessingError: If operation fails
        """
        pass

    @abstractmethod
    def validate_input(self, input_path: Path) -> bool:
        """
        Validate input file before executing operation.

        Args:
            input_path: Path to input file

        Returns:
            True if input is valid, False otherwise

        Raises:
            ValueError: If input is invalid with explanation
        """
        pass

    @abstractmethod
    def estimate_duration(self, input_path: Path) -> float:
        """
        Estimate operation duration for progress tracking.

        Args:
            input_path: Path to input file

        Returns:
            Estimated duration in seconds
        """
        pass

    def get_operation_name(self) -> str:
        """Get human-readable operation name."""
        return self.__class__.__name__


class CodecStrategy(ABC):
    """
    Strategy pattern for video codec encoding.

    Each codec (h264_nvenc, hevc_nvenc, vp9, libx264, etc.) implements
    this interface to provide GPU-specific or CPU encoding logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable codec name."""
        pass

    @property
    @abstractmethod
    def encoder_name(self) -> str:
        """FFmpeg encoder name (e.g., 'h264_nvenc', 'libx264')."""
        pass

    @abstractmethod
    def get_ffmpeg_args(
        self, gpu_info: Optional[GPUInfo] = None, preset: str = "medium", crf: int = 23
    ) -> List[str]:
        """
        Generate FFmpeg arguments for this codec.

        Args:
            gpu_info: Detected GPU information (if available)
            preset: Encoding preset (ultrafast, fast, medium, slow)
            crf: Constant Rate Factor (quality, 0-51, lower=better)

        Returns:
            List of FFmpeg command-line arguments
        """
        pass

    @abstractmethod
    def supports_gpu(self, gpu_vendor: "GPUVendor") -> bool:
        """
        Check if this codec supports the given GPU vendor.

        Args:
            gpu_vendor: GPU vendor (NVIDIA, INTEL, etc.)

        Returns:
            True if codec supports this GPU, False otherwise
        """
        pass

    @abstractmethod
    def get_fallback_strategy(self) -> Optional["CodecStrategy"]:
        """
        Get CPU fallback strategy if GPU encoding fails.

        Returns:
            CPU-based codec strategy, or None if no fallback
        """
        pass

    def validate_preset(self, preset: str) -> bool:
        """Validate encoding preset."""
        valid_presets = {"ultrafast", "fast", "medium", "slow", "veryslow"}
        return preset in valid_presets

    def validate_crf(self, crf: int) -> bool:
        """Validate CRF value (0-51)."""
        return 0 <= crf <= 51


class HashStrategy(ABC):
    """
    Strategy pattern for perceptual image hashing.

    Different hashing algorithms (pHash, dHash, wHash) implement this
    interface for image similarity comparison and deduplication.
    """

    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        """Name of hashing algorithm (e.g., 'phash', 'dhash')."""
        pass

    @abstractmethod
    def compute_hash(self, image: "Image.Image") -> "ImageHash":
        """
        Compute perceptual hash of an image.

        Args:
            image: PIL Image object

        Returns:
            ImageHash object
        """
        pass

    @abstractmethod
    def compare(self, hash1: "ImageHash", hash2: "ImageHash") -> int:
        """
        Compare two image hashes using Hamming distance.

        Args:
            hash1: First image hash
            hash2: Second image hash

        Returns:
            Hamming distance (lower = more similar)
        """
        pass

    def are_similar(
        self, hash1: "ImageHash", hash2: "ImageHash", threshold: int = 5
    ) -> bool:
        """
        Check if two images are similar based on hash comparison.

        Args:
            hash1: First image hash
            hash2: Second image hash
            threshold: Hamming distance threshold (default: 5)

        Returns:
            True if images are similar, False otherwise
        """
        return self.compare(hash1, hash2) <= threshold
