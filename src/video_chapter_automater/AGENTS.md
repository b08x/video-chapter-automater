# CORE PACKAGE KNOWLEDGE BASE

**Generated:** 2026-02-12

## OVERVIEW
Project hub containing CLI entry points, legacy processor, and platform-aware path management.

## STRUCTURE
```
src/video_chapter_automater/
├── preprocessing/      # Modular operations
├── pipeline/           # Orchestration
├── output/             # File management
├── ui/                 # Rich interfaces
├── cli.py              # Legacy entry point
├── cli_pipeline.py     # New entry point
└── setup_wizard.py     # Interactive setup
```

## WHERE TO LOOK
| Component | File | Role |
|-----------|------|------|
| vca CLI | `cli.py` | Legacy monolithic interface |
| vca-pipeline CLI | `cli_pipeline.py` | Modular pipeline interface |
| Setup Wizard | `setup_wizard.py` | Configuration and GPU detection |
| Legacy Logic | `processor.py` | Monolithic scene detection logic |
| Path Utilities | `app_paths.py` | XDG-compliant path resolution |

## CONVENTIONS
- **Path Management**: Always use `ApplicationPaths.for_current_platform()` to resolve config/data dirs.
- **Exceptions**: Centralize all custom errors in `exceptions.py`.
- **CLI Design**: Prefer `cli_pipeline.py` for new features; keep `cli.py` for backward compatibility.

## ANTI-PATTERNS
- **Legacy Dependency**: Do not add new features to `processor.py`. Use the `pipeline` system.
- **Hardcoded Paths**: Never use `~/.config` or hardcoded strings. Use `ApplicationPaths`.
- **Silent Versions**: Unify version reporting across all CLI entry points.

## NOTES
- `setup.py` in root is a misnamed alias for `setup_wizard.py`.
