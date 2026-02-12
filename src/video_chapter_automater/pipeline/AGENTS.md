# PIPELINE KNOWLEDGE BASE

**Generated:** 2026-02-12

## OVERVIEW
Orchestration layer coordinating multi-stage video preprocessing workflows with configurable execution modes.

## STRUCTURE
```
pipeline/
├── config.py       # Execution modes & stage enums
├── stage.py        # Individual stage logic
└── orchestrator.py # Multi-stage coordinator
```

## WHERE TO LOOK
| Component | File | Role |
|-----------|------|------|
| Orchestrator | `orchestrator.py` | Main execution engine |
| Stage Definitions | `config.py` | Available PipelineStage enums |
| Result Handling | `stage.py` | StageResult capture and logging |

## CONVENTIONS
- **Execution Modes**:
  - `SEQUENTIAL`: Fail-fast (stops on first error).
  - `RESILIENT`: Continue-on-error (collects all successes/failures).
- **Progress Bars**: Orchestrator uses `Rich.Progress` to track concurrent or sequential tasks.
- **Stage Isolation**: Stages should be independent and receive all necessary state via `PipelineConfig`.

## ANTI-PATTERNS
- **Implicit Dependencies**: Avoid stages relying on side-effects of previous stages without explicit configuration.
- **Global State**: Do not store pipeline state in module-level variables. Use `PipelineResult`.
- **Silent Failure**: Even in `RESILIENT` mode, errors must be captured and reported in the final manifest.

## NOTES
- Progress estimates are currently placeholders in some stages (base class lacks `estimate_duration` implementation).
