"""
Pipeline orchestration module for VideoChapterAutomater.

Coordinates multi-stage preprocessing workflows, managing execution order,
progress tracking, error handling, and result consolidation.
"""

from .orchestrator import PipelineOrchestrator, PipelineResult
from .config import PipelineConfig, PipelineStage
from .stage import Stage, StageResult

__all__ = [
    "PipelineOrchestrator",
    "PipelineResult",
    "PipelineConfig",
    "PipelineStage",
    "Stage",
    "StageResult",
]
