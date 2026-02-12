# PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-12
**Commit:** 41825c4
**Branch:** main

## OVERVIEW
GPU-accelerated video preprocessing toolkit for automated chapter generation. Built with Python using a modular Clean Architecture pipeline.

## STRUCTURE
```
.
├── src/video_chapter_automater/
│   ├── preprocessing/  # Core operations (encode, extract, scene)
│   │   └── strategies/ # Pluggable algorithms (codec, hash)
│   ├── pipeline/       # Multi-stage orchestration
│   ├── output/         # Organized file management
│   └── ui/             # Monitors and previews
└── tests/              # Parallel test structure
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| CLI Commands | `src/video_chapter_automater/cli*.py` | `vca` (legacy), `vca-pipeline` (new) |
| Core Logic | `src/video_chapter_automater/processor.py` | Legacy monolithic processor |
| GPU Encoding | `src/video_chapter_automater/preprocessing/video_encoder.py` | Handles fallbacks |
| Scene Detection | `src/video_chapter_automater/preprocessing/scene_extractor.py` | PySceneDetect + Perceptual Hash |
| Setup Wizard | `src/video_chapter_automater/setup_wizard.py` | Rich-based interactive setup |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `PreprocessingOperation` | ABC | `preprocessing/base.py` | Interface for all stages |
| `PipelineOrchestrator` | Class | `pipeline/orchestrator.py` | Orchestrates stages |
| `CodecStrategy` | ABC | `preprocessing/base.py` | Strategy for video encoding |
| `OutputManager` | Class | `output/manager.py` | Handles vca_output/ structure |

## CONVENTIONS
- **Clean Architecture**: Clear separation of concerns; interface-driven operations.
- **Strategy Pattern**: Codecs and hashing algorithms are runtime-selectable strategies.
- **GPU-First**: Intelligent detection with explicit user-approved CPU fallback.
- **XDG Compliance**: User config stored in platform-specific XDG paths.

## ANTI-PATTERNS
- **Silent Degradation**: Never fallback to CPU encoding without user approval.
- **Redundancy**: Avoid duplicating FFmpeg arg building (extract to strategies).
- **Direct Subprocess**: Use `run_command` wrappers with Rich progress bars when possible.

## COMMANDS
```bash
pip install -e .[all]  # Dev setup
vca video.mp4          # Basic usage
vca-pipeline video.mp4 # Pipeline usage
pytest                 # Run tests
```

## NOTES
- `setup.py` is an interactive wizard, NOT a build script (convention deviation).
- `processor.py` contains legacy logic; new features should use the `pipeline/` system.
- Perceptual hash deduplication uses Hamming distance (default threshold: 5).
