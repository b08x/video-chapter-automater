"""
Scene extraction module for VideoChapterAutomater.

Detects scene boundaries using PySceneDetect and extracts representative images
with perceptual hash-based deduplication to eliminate similar/duplicate frames.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

try:
    from scenedetect import SceneManager, ContentDetector, save_images, open_video, detect
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False

from ..exceptions import SceneExtractionError, DependencyError, DeduplicationError
from .base import PreprocessingOperation, PreprocessingResult, HashStrategy
from .strategies.hash_strategies import PerceptualHashStrategy


@dataclass
class SceneExtractionConfig:
    """
    Configuration for scene extraction and deduplication.

    Attributes:
        num_images: Number of images to extract per scene (1-9)
        threshold: Content detection threshold (default: 27.0, higher = fewer scenes)
        dedup_threshold: Hash similarity threshold for deduplication (0-10)
                        0 = only remove identical
                        1-5 = remove very similar (recommended)
                        6-10 = remove similar
        hash_algorithm: Hash algorithm to use ("phash", "dhash", "whash")
        image_format: Output image format (png, jpg)
        min_scene_length: Minimum scene length in seconds (default: 0.5)
    """
    num_images: int = 3
    threshold: float = 27.0
    dedup_threshold: int = 5
    hash_algorithm: str = "phash"
    image_format: str = "png"
    min_scene_length: float = 0.5

    def __post_init__(self):
        """Validate configuration parameters."""
        if not 1 <= self.num_images <= 9:
            raise ValueError(
                f"num_images must be between 1-9, got {self.num_images}"
            )

        if self.threshold < 0:
            raise ValueError(
                f"threshold must be >= 0, got {self.threshold}"
            )

        if not 0 <= self.dedup_threshold <= 20:
            raise ValueError(
                f"dedup_threshold must be between 0-20, got {self.dedup_threshold}"
            )

        if self.hash_algorithm not in ["phash", "dhash", "whash"]:
            raise ValueError(
                f"hash_algorithm must be 'phash', 'dhash', or 'whash', "
                f"got {self.hash_algorithm}"
            )

        if self.image_format not in ["png", "jpg", "jpeg"]:
            raise ValueError(
                f"image_format must be 'png', 'jpg', or 'jpeg', "
                f"got {self.image_format}"
            )

        if self.min_scene_length < 0:
            raise ValueError(
                f"min_scene_length must be >= 0, got {self.min_scene_length}"
            )


@dataclass
class SceneInfo:
    """Information about a detected scene."""
    scene_number: int
    start_time: float
    end_time: float
    duration: float
    image_paths: List[Path] = field(default_factory=list)


@dataclass
class SceneExtractionResult(PreprocessingResult):
    """Result from scene extraction operation."""
    num_scenes: int = 0
    total_images_extracted: int = 0
    images_after_dedup: int = 0
    duplicates_removed: int = 0
    scenes: List[SceneInfo] = field(default_factory=list)


class SceneExtractor(PreprocessingOperation):
    """
    Detects scene boundaries and extracts representative images.

    Uses PySceneDetect for content-based scene detection and perceptual
    hashing for intelligent deduplication of similar frames.
    """

    def __init__(self, verbose: bool = False, hash_strategy: Optional[HashStrategy] = None):
        """
        Initialize scene extractor.

        Args:
            verbose: Enable verbose output for debugging
            hash_strategy: Custom hash strategy (default: PerceptualHashStrategy)
        """
        if not SCENEDETECT_AVAILABLE:
            raise DependencyError(
                "scenedetect",
                "Install with: pip install scenedetect opencv-python-headless"
            )

        self.verbose = verbose
        self.hash_strategy = hash_strategy or PerceptualHashStrategy()

    def execute(
        self,
        input_path: Path,
        config: SceneExtractionConfig,
        output_dir: Optional[Path] = None
    ) -> SceneExtractionResult:
        """
        Extract scenes and images from video file.

        Args:
            input_path: Path to input video file
            config: Scene extraction configuration
            output_dir: Directory to save scene images (default: input_path.parent / "scenes")

        Returns:
            SceneExtractionResult with extraction details

        Raises:
            SceneExtractionError: If scene extraction fails
            DependencyError: If PySceneDetect is not available
        """
        start_time = time.time()

        # Validate input
        self.validate_input(input_path)

        # Determine output directory
        if output_dir is None:
            output_dir = input_path.parent / "scenes" / input_path.stem

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Update hash strategy if needed
        if config.hash_algorithm != "phash" or not isinstance(self.hash_strategy, PerceptualHashStrategy):
            from .strategies.hash_strategies import get_hash_strategy
            self.hash_strategy = get_hash_strategy(config.hash_algorithm)

        video = None
        try:
            # Open video to get frame rate and share object between stages
            video = open_video(str(input_path))
            fps = video.frame_rate

            # Step 1: Detect scenes
            scenes = self._detect_scenes(video, config)

            if not scenes:
                return SceneExtractionResult(
                    success=True,
                    output_path=output_dir,
                    duration=time.time() - start_time,
                    num_scenes=0,
                    total_images_extracted=0,
                    images_after_dedup=0,
                    duplicates_removed=0,
                    scenes=[],
                    metadata={"message": "No scenes detected"}
                )

            # Step 2: Extract images from scenes
            image_paths = self._extract_images(
                video,
                scenes,
                output_dir,
                config
            )

            # Step 3: Deduplicate images
            kept_images, removed_count = self._deduplicate_images(
                image_paths,
                config.dedup_threshold
            )

            # Step 4: Organize results by scene
            scene_infos = self._organize_scene_info(scenes, kept_images)

            return SceneExtractionResult(
                success=True,
                output_path=output_dir,
                duration=time.time() - start_time,
                num_scenes=len(scenes),
                total_images_extracted=len(image_paths),
                images_after_dedup=len(kept_images),
                duplicates_removed=removed_count,
                scenes=scene_infos,
                metadata={
                    "threshold": config.threshold,
                    "dedup_threshold": config.dedup_threshold,
                    "hash_algorithm": config.hash_algorithm,
                    "num_images_per_scene": config.num_images,
                }
            )

        except Exception as e:
            if isinstance(e, (SceneExtractionError, DependencyError, DeduplicationError)):
                raise
            raise SceneExtractionError(
                str(input_path),
                0,
                f"Scene extraction failed: {str(e)}"
            ) from e
        finally:
            if video is not None:
                try:
                    video.release()
                except Exception:
                    pass

    def validate_input(self, input_path: Path) -> bool:
        """
        Validate input video file.

        Args:
            input_path: Path to video file

        Returns:
            True if valid

        Raises:
            ValueError: If input is invalid
        """
        if not input_path.exists():
            raise ValueError(f"Input file does not exist: {input_path}")

        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")

        # Check file extension
        valid_extensions = {
            '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv',
            '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'
        }

        if input_path.suffix.lower() not in valid_extensions:
            raise ValueError(
                f"Unsupported video format: {input_path.suffix}. "
                f"Supported: {', '.join(sorted(valid_extensions))}"
            )

        return True

    def estimate_duration(self, input_path: Path) -> float:
        """
        Estimate scene extraction duration.

        Scene detection is relatively fast, typically 1-5% of video duration.

        Args:
            input_path: Path to video file

        Returns:
            Estimated duration in seconds
        """
        # Rough estimate based on file size
        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        # Scene detection: ~20MB/sec, image extraction: ~50 images/sec
        estimated_seconds = max(file_size_mb / 20 + 2, 2.0)
        return estimated_seconds

    def _detect_scenes(
        self,
        video: Any,
        config: SceneExtractionConfig
    ) -> List[Tuple[Any, Any]]:
        """
        Detect scene boundaries using ContentDetector.

        Args:
            video: scenedetect VideoStream object
            config: Scene extraction configuration

        Returns:
            List of (start_time, end_time) tuples for each scene

        Raises:
            SceneExtractionError: If scene detection fails
        """
        try:
            # min_scene_len must be an integer (frames)
            # config.min_scene_length is in seconds
            min_scene_len = int(config.min_scene_length * video.frame_rate)
            
            detector = ContentDetector(
                threshold=config.threshold,
                min_scene_len=min_scene_len
            )

            # Use SceneManager instead of detect wrapper to avoid TypeErrors with VideoStream object
            scene_manager = SceneManager()
            scene_manager.add_detector(detector)
            scene_manager.detect_scenes(video=video, show_progress=self.verbose)
            scenes = scene_manager.get_scene_list()

            if self.verbose:
                print(f"Detected {len(scenes)} scenes")

            return scenes

        except Exception as e:
            raise SceneExtractionError(
                video.name if hasattr(video, 'name') else "unknown",
                0,
                f"Scene detection failed: {str(e)}"
            ) from e

    def _extract_images(
        self,
        video: Any,
        scenes: List[Tuple[Any, Any]],
        output_dir: Path,
        config: SceneExtractionConfig
    ) -> List[Path]:
        """
        Extract images from detected scenes.

        Args:
            video: scenedetect VideoStream object
            scenes: List of scene boundaries
            output_dir: Directory to save images
            config: Scene extraction configuration

        Returns:
            List of paths to extracted images

        Raises:
            SceneExtractionError: If image extraction fails
        """
        try:
            # Extract images
            image_filenames_dict = save_images(
                scenes,
                video,
                num_images=config.num_images,
                output_dir=str(output_dir),
                image_extension=config.image_format,
                show_progress=self.verbose
            )

            # Flatten to list of paths
            all_images = []
            for scene_idx, paths in image_filenames_dict.items():
                for img_path in paths:
                    # Convert to Path and ensure it exists
                    img_path = Path(img_path)
                    if not img_path.is_absolute():
                        img_path = output_dir / img_path

                    if img_path.exists():
                        all_images.append(img_path)

            # Sort for consistent ordering
            all_images.sort()

            if self.verbose:
                print(f"Extracted {len(all_images)} images total")

            return all_images

        except Exception as e:
            raise SceneExtractionError(
                video.name if hasattr(video, 'name') else "unknown",
                len(scenes),
                f"Image extraction failed: {str(e)}"
            ) from e

    def _deduplicate_images(
        self,
        image_paths: List[Path],
        threshold: int
    ) -> Tuple[List[Path], int]:
        """
        Deduplicate images using perceptual hashing.

        Args:
            image_paths: List of image paths to deduplicate
            threshold: Similarity threshold (Hamming distance)

        Returns:
            Tuple of (kept_images, num_removed)

        Raises:
            DeduplicationError: If deduplication fails
        """
        if threshold == 0:
            # No deduplication requested
            return image_paths, 0

        kept_images: List[Tuple[Path, Any]] = []  # (path, hash)
        removed_count = 0

        for img_path in image_paths:
            try:
                # Compute hash for current image
                curr_hash = self.hash_strategy.compute_hash(img_path)

                # Check against kept images
                is_duplicate = False
                for _, kept_hash in kept_images:
                    if self.hash_strategy.are_similar(curr_hash, kept_hash, threshold):
                        is_duplicate = True
                        break

                if is_duplicate:
                    # Remove duplicate image
                    img_path.unlink()
                    removed_count += 1
                else:
                    # Keep this image
                    kept_images.append((img_path, curr_hash))

            except Exception as e:
                if self.verbose:
                    print(f"Warning: Could not process image {img_path}: {e}")
                # Keep image if we can't process it
                kept_images.append((img_path, None))

        if self.verbose:
            print(f"Deduplication complete: removed {removed_count} duplicates")

        # Return only paths, not hashes
        return [path for path, _ in kept_images], removed_count

    def _organize_scene_info(
        self,
        scenes: List[Tuple[Any, Any]],
        image_paths: List[Path]
    ) -> List[SceneInfo]:
        """
        Organize extracted images by scene.

        Args:
            scenes: List of scene boundaries
            image_paths: List of image paths (after deduplication)

        Returns:
            List of SceneInfo objects
        """
        scene_infos = []

        for scene_idx, (start_time, end_time) in enumerate(scenes):
            # Extract start/end times from FrameTimecode objects
            start_secs = float(start_time.get_seconds())
            end_secs = float(end_time.get_seconds())

            # Find images for this scene (by filename pattern)
            scene_images = [
                img for img in image_paths
                if f"-Scene-{scene_idx + 1:03d}-" in img.name
            ]

            scene_info = SceneInfo(
                scene_number=scene_idx + 1,
                start_time=start_secs,
                end_time=end_secs,
                duration=end_secs - start_secs,
                image_paths=sorted(scene_images)
            )
            scene_infos.append(scene_info)

        return scene_infos

    def get_operation_name(self) -> str:
        """Get human-readable operation name."""
        return "Scene Extraction"
