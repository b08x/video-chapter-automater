# Video Preprocessing Infrastructure

Comprehensive guide to the VideoChapterAutomater preprocessing system, built with Clean Architecture principles for GPU-accelerated video processing, audio extraction, and scene detection.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Concepts](#core-concepts)
- [Quick Start](#quick-start)
- [Module Reference](#module-reference)
- [Usage Examples](#usage-examples)
- [Advanced Topics](#advanced-topics)

## Architecture Overview

The preprocessing infrastructure follows Clean Architecture principles with clear separation of concerns:

```
preprocessing/
├── base.py                    # Abstract base classes and contracts
├── audio_extractor.py         # Audio extraction with FFmpeg
├── video_encoder.py           # GPU-accelerated video re-encoding
├── scene_extractor.py         # Scene detection and image extraction
└── strategies/
    ├── codec_strategies.py    # Video codec implementations
    └── hash_strategies.py     # Perceptual hashing algorithms

pipeline/
├── config.py                  # Pipeline configuration
├── stage.py                   # Individual stage execution
└── orchestrator.py            # Multi-stage coordination

output/
└── manager.py                 # Output directory management

ui/
├── monitors.py                # System resource monitoring
└── previews.py                # Chapter visualization
```

## Core Concepts

### 1. Operations

All preprocessing operations implement the `PreprocessingOperation` interface:

```python
from abc import ABC, abstractmethod
from pathlib import Path

class PreprocessingOperation(ABC):
    @abstractmethod
    def execute(self, input_path: Path, config: Any) -> PreprocessingResult:
        """Execute the preprocessing operation."""
        pass

    @abstractmethod
    def validate_input(self, input_path: Path) -> bool:
        """Validate input file before executing."""
        pass

    @abstractmethod
    def estimate_duration(self, input_path: Path) -> float:
        """Estimate operation duration for progress tracking."""
        pass
```

### 2. Strategies

Codec and hash strategies use the Strategy Pattern for runtime algorithm selection:

```python
# Video codec strategies
class CodecStrategy(ABC):
    def get_ffmpeg_args(self, input_path: Path, config: VideoEncodingConfig) -> List[str]:
        """Generate FFmpeg arguments for this codec."""
        pass

    def supports_gpu(self, gpu_type: str) -> bool:
        """Check if this codec supports the given GPU."""
        pass

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        """Get CPU fallback if GPU encoding fails."""
        pass

# Perceptual hash strategies
class HashStrategy(ABC):
    def compute_hash(self, image_path: Path) -> Any:
        """Compute perceptual hash for an image."""
        pass

    def are_similar(self, hash1: Any, hash2: Any, threshold: int) -> bool:
        """Determine if two images are similar."""
        pass
```

### 3. Pipeline Orchestration

Pipelines coordinate multi-stage workflows:

```python
from pipeline.config import PipelineConfig, PipelineStage
from pipeline.orchestrator import PipelineOrchestrator

# Configure pipeline
config = PipelineConfig.create_default()
config.execution_mode = ExecutionMode.SEQUENTIAL
config.enable_monitoring = True

# Execute
orchestrator = PipelineOrchestrator(config)
result = orchestrator.execute(Path("video.mp4"))

# Check results
if result.success:
    print(f"Completed in {result.total_duration:.2f}s")
    for stage_result in result.stage_results:
        print(f"{stage_result.stage.value}: {stage_result.status.value}")
```

## Quick Start

### Installation

```bash
# Install with all dependencies
pip install -e .[all]

# Or minimal installation
pip install -e .
```

### Basic Usage

**Using the CLI:**

```bash
# Full pipeline (re-encode + audio + scenes)
vca-pipeline video.mp4

# Minimal pipeline (audio + scenes only)
vca-pipeline video.mp4 --minimal

# Custom codec and settings
vca-pipeline video.mp4 --codec hevc_nvenc --preset slow --crf 18
```

**Using the Python API:**

```python
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.orchestrator import PipelineOrchestrator

# Create default pipeline
config = PipelineConfig.create_default()

# Execute
orchestrator = PipelineOrchestrator(config)
result = orchestrator.execute(Path("video.mp4"))

print(f"Success: {result.success}")
print(f"Output paths: {result.output_paths}")
```

## Module Reference

### Audio Extraction

Extract audio tracks and convert to WAV format optimized for speech transcription:

```python
from preprocessing.audio_extractor import AudioExtractor, AudioExtractionConfig

# Configure
config = AudioExtractionConfig(
    sample_rate=16000,    # 16kHz for speech
    channels=1,           # Mono
    format="wav",
    normalize=False
)

# Execute
extractor = AudioExtractor(verbose=False)
result = extractor.execute(Path("video.mp4"), config)

print(f"Output: {result.output_path}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(f"File size: {result.file_size_bytes} bytes")
```

**Supported Formats:**
- WAV (PCM 16-bit) - Recommended for speech
- MP3 (with bitrate option)
- FLAC (lossless compression)
- AAC (with bitrate option)

### Video Encoding

Re-encode videos with GPU acceleration and intelligent CPU fallback:

```python
from preprocessing.video_encoder import VideoEncoder
from preprocessing.strategies.codec_strategies import VideoEncodingConfig

# Configure
config = VideoEncodingConfig(
    preset="medium",      # ultrafast to veryslow
    crf=23,              # 0-51, lower = better quality
    pixel_format="yuv420p"
)

# Execute with GPU codec
encoder = VideoEncoder(verbose=False, interactive=True)
result = encoder.execute(
    Path("video.mp4"),
    config,
    codec_name="h264_nvenc"  # GPU-accelerated H.264
)

print(f"Codec used: {result.codec_used}")
print(f"GPU accelerated: {result.gpu_accelerated}")
print(f"Resolution: {result.resolution}")
```

**Supported Codecs:**

| Codec | Type | GPU Vendor | Fallback |
|-------|------|------------|----------|
| h264_nvenc | H.264/AVC | NVIDIA | libx264 |
| hevc_nvenc | H.265/HEVC | NVIDIA | libx265 |
| vp9 | VP9 | CPU/GPU | - |
| libx264 | H.264/AVC | CPU | - |
| libx265 | H.265/HEVC | CPU | - |

**GPU Fallback Behavior:**
1. Check GPU compatibility
2. Attempt GPU encoding
3. On failure, prompt user for CPU retry or abort
4. If retry selected, use CPU fallback codec

### Scene Extraction

Detect scene boundaries and extract representative images with deduplication:

```python
from preprocessing.scene_extractor import SceneExtractor, SceneExtractionConfig

# Configure
config = SceneExtractionConfig(
    num_images=5,             # 1-9 images per scene
    threshold=27.0,           # Scene detection sensitivity
    dedup_threshold=5,        # Hash similarity threshold
    hash_algorithm="phash",   # phash, dhash, or whash
    image_format="png"
)

# Execute
extractor = SceneExtractor(verbose=True)
result = extractor.execute(
    Path("video.mp4"),
    config,
    output_dir=Path("./scenes/")
)

print(f"Scenes detected: {result.num_scenes}")
print(f"Images extracted: {result.total_images_extracted}")
print(f"After deduplication: {result.images_after_dedup}")
print(f"Duplicates removed: {result.duplicates_removed}")

# Access scene information
for scene in result.scenes:
    print(f"Scene {scene.scene_number}: {scene.start_time:.2f}s - {scene.end_time:.2f}s")
    print(f"  Duration: {scene.duration:.2f}s")
    print(f"  Images: {len(scene.image_paths)}")
```

**Hash Algorithms:**

- **pHash** (Perceptual Hash): DCT-based, robust to scaling and color changes
- **dHash** (Difference Hash): Gradient-based, faster, sensitive to structural changes
- **wHash** (Wavelet Hash): DWT-based, excellent for high-resolution images

**Deduplication Thresholds:**
- 0: Only remove identical images
- 1-5: Remove very similar images (recommended)
- 6-10: Remove similar images
- 11-20: Aggressive deduplication

## Usage Examples

### Example 1: Custom Pipeline Configuration

```python
from pipeline.config import PipelineConfig, PipelineStage, ExecutionMode
from preprocessing.audio_extractor import AudioExtractionConfig
from preprocessing.scene_extractor import SceneExtractionConfig

# Create custom pipeline
config = PipelineConfig(
    execution_mode=ExecutionMode.RESILIENT,  # Continue on errors
    output_base_dir=Path("/custom/output"),
    enable_monitoring=True,
    enable_progress_bars=True
)

# Add audio extraction with custom settings
audio_config = AudioExtractionConfig(
    sample_rate=44100,
    channels=2,  # Stereo
    format="flac",
    normalize=True
)
config.add_stage(PipelineStage.AUDIO_EXTRACTION, config=audio_config)

# Add scene extraction with aggressive deduplication
scene_config = SceneExtractionConfig(
    num_images=7,
    threshold=25.0,
    dedup_threshold=3,
    hash_algorithm="dhash"
)
config.add_stage(PipelineStage.SCENE_EXTRACTION, config=scene_config)

# Execute
orchestrator = PipelineOrchestrator(config, verbose=True)
result = orchestrator.execute(Path("video.mp4"))
```

### Example 2: GPU Encoding with Custom Quality

```python
from preprocessing.video_encoder import VideoEncoder
from preprocessing.strategies.codec_strategies import VideoEncodingConfig

# High-quality encoding
config = VideoEncodingConfig(
    preset="slower",
    crf=18,  # Higher quality
    tune="film",
    pixel_format="yuv420p"
)

encoder = VideoEncoder(verbose=True, interactive=True)

# Try HEVC GPU encoding
result = encoder.execute(
    Path("video.mp4"),
    config,
    codec_name="hevc_nvenc"
)

if result.gpu_accelerated:
    print("GPU encoding successful!")
else:
    print("Fell back to CPU encoding")
```

### Example 3: Batch Processing

```python
from pathlib import Path
from pipeline.config import PipelineConfig
from pipeline.orchestrator import PipelineOrchestrator

# Configure once
config = PipelineConfig.create_minimal()  # Audio + scenes only
orchestrator = PipelineOrchestrator(config)

# Process multiple videos
video_dir = Path("/path/to/videos")
for video_file in video_dir.glob("*.mp4"):
    print(f"Processing {video_file.name}...")

    result = orchestrator.execute(video_file)

    if result.success:
        print(f"  ✓ Completed in {result.total_duration:.2f}s")
    else:
        print(f"  ✗ Failed: {result.error_summary}")
```

### Example 4: Chapter Export

```python
from ui.previews import ChapterPreview
from preprocessing.scene_extractor import SceneExtractor, SceneExtractionConfig

# Extract scenes
extractor = SceneExtractor()
config = SceneExtractionConfig(num_images=5, dedup_threshold=5)
result = extractor.execute(Path("video.mp4"), config)

# Convert to chapters
preview = ChapterPreview()
chapters = preview.from_scene_extraction_result(result)

# Display in terminal
preview.display_chapters(chapters, format="tree")

# Export for FFmpeg
preview.export_ffmetadata(chapters, Path("chapters.txt"))

# Export as JSON
preview.export_json(chapters, Path("chapters.json"))

# Embed chapters in video
import subprocess
subprocess.run([
    "ffmpeg", "-i", "video.mp4",
    "-i", "chapters.txt",
    "-map_metadata", "1",
    "-codec", "copy",
    "video_with_chapters.mp4"
])
```

## Advanced Topics

### Custom Codec Strategy

Implement your own codec strategy for specialized encoding:

```python
from preprocessing.strategies.codec_strategies import CodecStrategy, VideoEncodingConfig

class CustomCodecStrategy(CodecStrategy):
    def get_ffmpeg_args(self, input_path: Path, config: VideoEncodingConfig) -> List[str]:
        args = ["-c:v", "libvpx-vp9"]
        args.extend(["-crf", str(config.crf)])
        args.extend(["-b:v", "0"])  # Constant quality
        # Add custom args...
        return args

    def supports_gpu(self, gpu_type: str) -> bool:
        return True  # VP9 uses CPU

    def get_fallback_strategy(self) -> Optional[CodecStrategy]:
        return None  # No fallback
```

### Custom Hash Strategy

Implement custom perceptual hashing:

```python
from preprocessing.strategies.hash_strategies import HashStrategy

class ColorHashStrategy(HashStrategy):
    def compute_hash(self, image_path: Path) -> Any:
        from PIL import Image
        import numpy as np

        img = Image.open(image_path).resize((8, 8))
        pixels = np.array(img)
        avg_color = pixels.mean(axis=(0, 1))
        return avg_color

    def compare(self, hash1: Any, hash2: Any) -> int:
        import numpy as np
        distance = np.linalg.norm(hash1 - hash2)
        return int(distance)

    def are_similar(self, hash1: Any, hash2: Any, threshold: int = 50) -> bool:
        return self.compare(hash1, hash2) <= threshold
```

### Resource Monitoring

Monitor system resources during processing:

```python
from ui.monitors import ResourceMonitor

# Use as context manager
with ResourceMonitor(update_interval=1.0) as monitor:
    # Run processing
    result = orchestrator.execute(Path("video.mp4"))

    # Check resources during execution
    resources = monitor.get_resources()
    print(f"CPU: {resources.cpu_percent}%")
    print(f"Memory: {resources.memory_percent}%")
    print(f"GPU: {resources.gpu_utilization}%")

# Or start/stop manually
monitor = ResourceMonitor()
monitor.start()
# ... processing ...
monitor.stop()
```

### Output Management

Organize outputs with OutputManager:

```python
from output.manager import OutputManager, OutputType

manager = OutputManager(base_dir=Path("./vca_output"))

# Generate organized paths
video_path = manager.get_output_path(
    video_name="my_video",
    output_type=OutputType.VIDEO,
    extension="mp4",
    suffix="_reencoded"
)
# → ./vca_output/video/my_video_reencoded.mp4

# Get scene subdirectory
scenes_dir = manager.get_scene_subdir("my_video")
# → ./vca_output/scenes/my_video/

# Generate manifest
manager.generate_manifest(
    video_name="my_video",
    outputs={"video": video_path, "audio": audio_path},
    stats={"duration": 120.5}
)
# → ./vca_output/metadata/my_video_manifest.json

# Cleanup old files
deleted = manager.cleanup(
    output_type=OutputType.SCENES,
    older_than_days=7
)
print(f"Deleted {deleted} old scene files")
```

## Best Practices

1. **Always validate inputs**: Use `validate_input()` before processing
2. **Handle GPU fallbacks**: Enable interactive mode for user control
3. **Monitor resources**: Enable monitoring for long-running operations
4. **Use pipelines for multi-stage**: Leverage orchestrator for coordinated execution
5. **Configure deduplication**: Adjust thresholds based on video content type
6. **Check results**: Always verify `result.success` before using outputs
7. **Clean up outputs**: Use OutputManager cleanup for disk space management

## Troubleshooting

**GPU Encoding Fails:**
- Check GPU drivers are installed (`nvidia-smi` for NVIDIA)
- Verify FFmpeg has GPU support: `ffmpeg -encoders | grep nvenc`
- Enable verbose mode to see detailed error messages
- Use CPU fallback codecs (libx264, libx265)

**Scene Detection Misses Scenes:**
- Lower `threshold` value (try 20.0 or 15.0)
- Reduce `min_scene_length` to detect shorter scenes

**Too Many Duplicate Images:**
- Increase `dedup_threshold` for stricter matching
- Try different hash algorithms (dhash is more sensitive)

**Out of Disk Space:**
- Use OutputManager cleanup to remove old outputs
- Reduce `num_images` per scene
- Use compressed image formats (jpg instead of png)

## Performance Tips

- **GPU Encoding**: 2-5x faster than CPU for H.264/H.265
- **Audio Extraction**: Very fast, ~1-5% of video duration
- **Scene Detection**: ~1-5% of video duration, depends on content complexity
- **Deduplication**: Linear time, O(n²) comparisons for n images
- **Parallel Execution**: Not yet implemented, planned for future release

## API Reference

See individual module docstrings for detailed API documentation:
- `preprocessing.base` - Abstract base classes
- `preprocessing.audio_extractor` - Audio extraction
- `preprocessing.video_encoder` - Video encoding
- `preprocessing.scene_extractor` - Scene detection
- `preprocessing.strategies.codec_strategies` - Codec implementations
- `preprocessing.strategies.hash_strategies` - Hash implementations
- `pipeline.config` - Pipeline configuration
- `pipeline.orchestrator` - Pipeline execution
- `output.manager` - Output management
- `ui.monitors` - Resource monitoring
- `ui.previews` - Chapter visualization
