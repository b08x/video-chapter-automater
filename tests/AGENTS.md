# TEST SUITE KNOWLEDGE BASE

**Generated:** 2026-02-12

## OVERVIEW
Parallel test structure mirroring the core package with a focus on hardware-agnostic mocking of external tools.

## STRUCTURE
```
tests/
├── conftest.py      # Global fixtures (mock_gpu_info, temp_video)
├── preprocessing/   # Operation & strategy tests
└── pipeline/        # Orchestrator & stage tests
```

## WHERE TO LOOK
| Component | Directory | Notes |
|-----------|-----------|-------|
| GPU Mocking | `conftest.py` | Centralized hardware detection mocks |
| Codec Tests | `preprocessing/test_codec_strategies.py` | Strategy dispatch logic |
| Scene Tests | `preprocessing/test_scene_extractor.py` | Mocked PySceneDetect interactions |

## CONVENTIONS
- **Hardware Mocking**: Tests MUST mock GPU detection via `mock_gpu_info` to run on any runner.
- **External Tools**: Always mock FFmpeg and PySceneDetect calls to avoid binary dependencies.
- **File I/O**: Use the `tmp_path` fixture for all temporary file operations.
- **Markers**:
  - `@pytest.mark.gpu`: Reserved for integration tests requiring real hardware.
  - `@pytest.mark.slow`: Long-running integration tests.

## ANTI-PATTERNS
- **Real Subprocesses**: Do not execute real FFmpeg commands in unit tests.
- **System State**: Never modify user config or data dirs in tests. Use `ApplicationPaths.for_testing(tmp_path)`.
- **Global Fixtures**: Avoid `autouse` fixtures unless absolutely necessary (e.g., scenedetect mock).

## NOTES
- The test suite currently mocks GPU functionality entirely, even for `@pytest.mark.gpu` defined tests.
