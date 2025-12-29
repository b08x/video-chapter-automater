# AGENTS.md

This file provides guidance to agentic coding assistants working in this repository.

## Essential Commands

### Testing
```bash
# Run all tests
pytest

# Run single test file
pytest tests/preprocessing/test_scene_extractor.py

# Run specific test function
pytest tests/preprocessing/test_scene_extractor.py::test_scene_detection_basic

# Run with verbose output (see test names as they run)
pytest -v

# Run with coverage
pytest --cov=src --cov-report=html

# Skip slow/GPU tests (faster)
pytest -m "not gpu and not slow"

# Run only GPU tests
pytest -m gpu
```

### Code Quality (run before committing)
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

### Build
```bash
# Install in development mode
pip install -e .[all]
```

## Code Style Guidelines

### Imports
- Always start with `from __future__ import annotations` for Python 3.12+
- Order: stdlib → third-party → local imports
- Group imports with blank lines between groups
- Use `TYPE_CHECKING` for imports only needed in type hints

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from .base import PreprocessingOperation
```

### Type Hints
- All functions must have return type annotations
- Use `Path` from pathlib, not strings for file paths
- Use `Optional[T]` for nullable types
- Abstract methods return generic types like `Any` or protocol types

### Naming Conventions
- Classes: `PascalCase` (e.g., `PreprocessingOperation`)
- Functions/variables: `snake_case` (e.g., `execute_operation`)
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`
- Abstract base classes: prefix with abstract concept name (e.g., `CodecStrategy`)

### Error Handling
- Use custom exceptions from `exceptions.py`
- Always derive from `VideoChapterAutomaterError` for domain errors
- Wrap external tool calls (FFmpeg, PySceneDetect) in try/except
- Store context in exception attributes (e.g., `exit_code`, `stderr`)

```python
from video_chapter_automater.exceptions import CommandExecutionError

try:
    subprocess.run(cmd, check=True)
except subprocess.CalledProcessError as e:
    raise CommandExecutionError(cmd, e.returncode, e.stderr)
```

### Abstract Base Classes
- Use `ABC` from `abc` module
- Decorate abstract methods with `@abstractmethod`
- Provide default implementations where appropriate
- Return concrete types in abstract methods for type safety

### Docstrings
- Google style or reStructuredText
- Include `Args:`, `Returns:`, `Raises:` sections
- Keep docstrings concise but informative

### Testing
- Use `tmp_path` fixture for all test file I/O
- Mock external dependencies (FFmpeg, PySceneDetect) in unit tests
- Mark GPU tests with `@pytest.mark.gpu`
- Mark slow tests with `@pytest.mark.slow`

### Dataclasses
- Use for simple data containers
- Implement `__post_init__` for default mutable fields
- Include type hints for all fields

## Architecture Patterns

### Strategy Pattern
- Use for pluggable algorithms (codecs, hash algorithms)
- Each strategy implements an abstract interface
- Provide `get_fallback_strategy()` for graceful degradation

### Clean Architecture
- Preprocessing operations implement `PreprocessingOperation` interface
- Pipeline orchestrates stages via `PipelineOrchestrator`
- Output organized by `OutputManager`

### GPU Fallback
- Always validate GPU support before GPU operations
- Prompt user before falling back to CPU (use `interactive=True`)
- Use `detect_gpu_capabilities()` from `gpu_detection.py`

## Common Patterns

### Path Handling
```python
from pathlib import Path
from video_chapter_automater.output.manager import OutputManager

manager = OutputManager()
output_dir = manager.get_scene_output_dir(video_name)
```

### Preprocessing Operation
```python
class MyOperation(PreprocessingOperation):
    def execute(self, input_path: Path, config: Any) -> PreprocessingResult:
        if not self.validate_input(input_path):
            raise PreprocessingError("Invalid input")
        # ... implementation ...
```

### FFmpeg Execution
```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    check=True
)
# Always check stderr for warnings/errors
```

## Key Files to Reference
- `src/video_chapter_automater/preprocessing/base.py` - Abstract interfaces
- `src/video_chapter_automater/exceptions.py` - Custom exceptions
- `tests/conftest.py` - Test fixtures
- `pyproject.toml` - Tool configurations
