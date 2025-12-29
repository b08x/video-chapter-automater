# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VideoChapterAutomater is a GPU-accelerated video preprocessing toolkit that automates chapter generation through scene detection. The codebase follows **Clean Architecture principles** with a modular pipeline system for video re-encoding, audio extraction, and scene boundary detection with perceptual hash deduplication.

## Essential Commands

### Development Setup

```bash
# Install with all dependencies (recommended for development)
pip install -e .[all]

# Minimal installation (runtime only)
pip install -e .

# Install with GPU support
pip install -e .[nvidia]  # NVIDIA GPUs
pip install -e .[intel]   # Intel GPUs
```

### Running the Application

```bash
# Basic chapter generation (original tool)
vca video.mp4
vca video.mp4 --threshold 27.0

# Advanced preprocessing pipeline (new modular system)
vca-pipeline video.mp4                           # Full pipeline
vca-pipeline video.mp4 --minimal                 # Audio + scenes only
vca-pipeline video.mp4 --codec hevc_nvenc        # Custom GPU codec
vca-pipeline video.mp4 --scenes-per-scene 5      # 5 images per scene
vca-pipeline video.mp4 --dedup-threshold 3       # Strict deduplication
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test module
pytest tests/preprocessing/test_scene_extractor.py

# Run only non-GPU tests (faster)
pytest -m "not gpu"

# Run only slow/GPU tests
pytest -m "gpu or slow"
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Type checking
mypy src/

# Lint
flake8 src/ tests/
```

## Configuration Storage

User preferences are stored in XDG-compliant, platform-specific locations:

- **Linux**: `$XDG_CONFIG_HOME/video-chapter-automater/config.json` (default: `~/.config/video-chapter-automater/`)
- **macOS**: `~/Library/Application Support/video-chapter-automater/config.json` (respects `$XDG_CONFIG_HOME` if set)
- **Windows**: `%APPDATA%\video-chapter-automater\config.json` (respects `$XDG_CONFIG_HOME` if set)

### Implementation

Config path resolution is handled by the `ApplicationPaths` class:

```python
from video_chapter_automater.app_paths import ApplicationPaths

# Get platform-appropriate paths
app_paths = ApplicationPaths.for_current_platform()
config_file = app_paths.config_file  # Platform-specific config.json path
```

The path management system is built on two modules:

1. **`platform_dirs.py`**: Low-level XDG Base Directory Specification implementation
   - Detects platform (Linux/macOS/Windows)
   - Resolves XDG environment variables
   - Provides config_home, data_home, cache_home

2. **`app_paths.py`**: Application-specific path management
   - Provides `config_dir`, `config_file` properties
   - Includes `data_dir`, `cache_dir` for future use (XDG_DATA_HOME, XDG_CACHE_HOME)
   - Factory methods: `for_current_platform()`, `for_testing(tmp_path)`

### Migration Notes

Old configuration location (`~/.video_chapter_automater/`) is no longer supported. Users upgrading from older versions need to:
- Manually copy config to new location, OR
- Re-run setup wizard (`vca --setup`)

## Architecture Overview

### Core Design Principles

1. **Clean Architecture**: Clear separation between preprocessing operations, pipeline orchestration, and output management
2. **Strategy Pattern**: Codec and hash algorithms are runtime-selectable via strategy implementations
3. **Progressive Enhancement**: Legacy `vca` command exists for backward compatibility; new `vca-pipeline` provides modular workflows
4. **GPU-First with CPU Fallback**: Intelligent detection and graceful degradation when GPU encoding fails

### Module Structure

```
src/video_chapter_automater/
├── preprocessing/              # Core preprocessing operations
│   ├── base.py                # Abstract base classes (PreprocessingOperation)
│   ├── audio_extractor.py     # Audio extraction with FFmpeg
│   ├── video_encoder.py       # GPU-accelerated video re-encoding
│   ├── scene_extractor.py     # Scene detection + perceptual hash dedup
│   └── strategies/
│       ├── codec_strategies.py    # H.264/H.265/VP9 encoding strategies
│       └── hash_strategies.py     # pHash/dHash/wHash implementations
├── pipeline/                   # Multi-stage orchestration
│   ├── config.py              # Pipeline configuration (ExecutionMode, stages)
│   ├── stage.py               # Individual stage execution + results
│   └── orchestrator.py        # Coordinate multi-stage workflows
├── output/
│   └── manager.py             # Organized output directory management
├── ui/
│   ├── monitors.py            # System resource monitoring (CPU/GPU/Memory)
│   └── previews.py            # Chapter visualization and FFmetadata export
├── cli.py                     # Legacy `vca` command
├── cli_pipeline.py            # New `vca-pipeline` command
├── processor.py               # Legacy processor (scene detection → chapters)
├── chapconv.py                # Chapter format conversion utilities
└── exceptions.py              # Custom exceptions
```

### Key Abstraction: PreprocessingOperation

All preprocessing stages implement this interface (see `preprocessing/base.py`):

```python
class PreprocessingOperation(ABC):
    def execute(self, input_path: Path, config: Any) -> PreprocessingResult
    def validate_input(self, input_path: Path) -> bool
    def estimate_duration(self, input_path: Path) -> float
```

This enables:
- Uniform error handling
- Progress estimation
- Input validation before expensive operations
- Pluggable pipeline stages

### Pipeline Execution Modes

Defined in `pipeline/config.py`:

- **SEQUENTIAL**: Stop on first error (default, best for reliability)
- **RESILIENT**: Continue through errors, collect results (best for batch processing)

Stages are configured as `PipelineStage` enums and executed by `PipelineOrchestrator`.

### GPU Encoding Strategy

Video encoding (`preprocessing/video_encoder.py`) follows this flow:

1. Detect GPU capabilities (`gpu_detection.py`)
2. Select codec strategy (e.g., `H264NvencStrategy` for NVIDIA)
3. Check `strategy.supports_gpu(gpu_type)`
4. Attempt GPU encoding
5. On failure → prompt user → use `get_fallback_strategy()` (libx264/libx265)

Codec strategies are in `preprocessing/strategies/codec_strategies.py`. Each strategy defines:
- FFmpeg arguments (`get_ffmpeg_args()`)
- GPU compatibility (`supports_gpu()`)
- CPU fallback (`get_fallback_strategy()`)

### Scene Detection + Deduplication

Scene extraction (`preprocessing/scene_extractor.py`) combines:

1. **PySceneDetect**: Content-aware scene boundary detection
2. **Image Extraction**: Extract N images per detected scene (configurable 1-9)
3. **Perceptual Hashing**: Compute hash for each image (pHash/dHash/wHash)
4. **Deduplication**: Remove visually similar images based on Hamming distance threshold

Hash strategies implement:
```python
class HashStrategy(ABC):
    def compute_hash(self, image_path: Path) -> Any
    def are_similar(self, hash1: Any, hash2: Any, threshold: int) -> bool
```

**Why deduplication matters**: Scene detection can produce consecutive similar frames. Perceptual hashing removes redundancy while preserving distinct visual changes.

## Important Implementation Details

### Audio Extraction Defaults

Audio extraction (`preprocessing/audio_extractor.py`) defaults to:
- **16kHz mono WAV**: Optimized for speech transcription (Whisper, etc.)
- Use `--sample-rate 44100 --normalize-audio` for music applications

### Output Directory Structure

`OutputManager` (`output/manager.py`) organizes outputs:

```
vca_output/
├── video/           # Re-encoded videos
├── audio/           # Extracted audio tracks
├── scenes/          # Scene images, organized by video name
│   └── my_video/
│       ├── scene_001_img_1.png
│       └── ...
└── metadata/        # JSON manifests with processing stats
```

### Testing Philosophy

- **Unit tests**: Mock FFmpeg/PySceneDetect to avoid external dependencies
- **Integration tests**: Marked `@pytest.mark.slow` or `@pytest.mark.gpu`
- **Fixtures**: `conftest.py` provides `temp_video_file`, `sample_video_metadata`, etc.

Use `tmp_path` (pytest fixture) for all test file I/O to ensure cleanup.

### Error Handling

Custom exceptions in `exceptions.py`:
- `VideoChapterAutomaterError`: Base exception
- Derive specific errors for clear failure modes

Always wrap external tool calls (FFmpeg, PySceneDetect) in try/except with context-aware error messages.

## Critical Considerations

### GPU Fallback UX

When GPU encoding fails, the user must explicitly approve CPU fallback (`video_encoder.py` uses `interactive=True` flag). This prevents silent performance degradation on GPU-enabled systems.

### Perceptual Hash Thresholds

Deduplication threshold recommendations (see `PREPROCESSING.md`):
- **0-5**: Conservative (recommended default: 5)
- **6-10**: Moderate deduplication
- **11-20**: Aggressive (may remove distinct scenes)

Lower thresholds = fewer duplicates removed. Higher = more aggressive.

### FFmpeg Integration

All FFmpeg calls go through subprocess with:
- Explicit codec selection (`-c:v`, `-c:a`)
- Quality control (`-crf` for variable bitrate, or `-b:v` for constant)
- GPU hardware acceleration flags (`-hwaccel cuda` for NVIDIA)

Check FFmpeg stderr for encoding warnings/errors.

### Legacy vs. Pipeline CLI

- **`vca`** (`cli.py`): Original monolithic tool, wraps `processor.py`
  - Simple scene detection → chapter embedding
  - Best for quick chapter generation

- **`vca-pipeline`** (`cli_pipeline.py`): Modular preprocessing
  - Granular control over encoding, audio, scenes
  - GPU acceleration, perceptual hash dedup
  - Suitable for batch processing and advanced workflows

Both CLIs coexist for backward compatibility. New features go into `vca-pipeline`.

## Common Pitfalls

1. **Not validating GPU support before encoding**: Always call `detect_gpu_capabilities()` or check codec strategy compatibility
2. **Hardcoding paths**: Use `OutputManager` to generate organized paths
3. **Ignoring interactive mode for GPU fallback**: Users expect control over CPU retry decision
4. **Skipping input validation**: Call `validate_input()` before `execute()` in preprocessing operations
5. **Assuming FFmpeg success**: Always check subprocess return codes and stderr

## Documentation References

- **Preprocessing Architecture**: See `docs/PREPROCESSING.md` for comprehensive module documentation, usage examples, and advanced topics
- **PySceneDetect**: Scene detection library (external dependency)
- **FFmpeg**: Video processing tool (external dependency)

## Version Information

- Python: 3.12+ required
- Key dependencies: scenedetect[opencv], imagehash, Pillow, psutil, rich, intel-extension-for-pytorch
- Entry points: `vca`, `vca-pipeline`, `video-chapter-setup` (setup wizard)
